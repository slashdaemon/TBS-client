#!/usr/bin/env python3
"""
Publish the TheBlockSurvival client modpack to Modrinth and/or CurseForge.

TheBlockSurvival is the public release of the TBS-Client packwiz modpack. Unlike
StreamCraft (a multi-band, multi-platform *mod*), a modpack is a single artifact
per platform: one `.mrpack` for Modrinth, one `.zip` for CurseForge. This script
exports the pack with packwiz, then uploads it.

Modelled on StreamCraft's scripts/publish-modrinth.py + publish-curseforge.py —
same `.env` auth, the same idempotent-Modrinth and CurseForge-catalog-resolution
patterns — collapsed into one script because a modpack has no band/platform/loader
matrix to fan out over.

Usage:
    # Dry-run: export the artifact(s) and print upload metadata, upload nothing
    python scripts/publish.py --platform both --dry-run

    # Publish to Modrinth only (the v1 launch target)
    python scripts/publish.py --platform modrinth

    # Publish to both platforms
    python scripts/publish.py --platform both

    # Re-use an artifact already in dist/ instead of re-exporting
    python scripts/publish.py --platform modrinth --no-export

    # Check an already-published CurseForge release still has its per-OS
    # companions attached (uploads nothing)
    python scripts/publish.py --platform curseforge --cf-verify-only \
        --cf-parent-file-id <primary file id> --variant all

The version is read from pack.toml; the changelog is the matching `## [X.Y.Z]`
section of CHANGELOG.md. Auth comes from a gitignored `.env` in the pack root
(TBS-client/.env) — see .env.example:

    MODRINTH_TOKEN          PAT with "Create version" scope — modrinth.com/settings/pats
    MODRINTH_PROJECT        project slug or ID (default: theblocksurvival)
    CURSEFORGE_TOKEN        token from authors-old.curseforge.com/account/api-tokens
    CURSEFORGE_PROJECT_ID   numeric project ID of the CurseForge modpack project

The Modrinth and CurseForge projects must be created manually on each site first —
this script uploads a version to an *existing* project, it does not create one.

Idempotent on Modrinth: an existing version with the same version_number is
skipped, so re-running after a partial failure won't double-upload. CurseForge has
no equivalent lookup — if a CF upload half-fails, delete the partial file via the
CF dashboard before retrying.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

try:
    import requests
except ImportError:
    print("ERR: requests not installed. Install with: pip install -r scripts/requirements.txt")
    sys.exit(1)

try:
    import markdown as _markdown
except ImportError:
    _markdown = None  # CurseForge changelog falls back to plain text if absent


MODRINTH_API = "https://api.modrinth.com/v2"
CURSEFORGE_API = "https://minecraft.curseforge.com/api"
# The upload API has no list/read endpoint, so post-publish verification reads
# back through the public website API instead (unauthenticated, no key needed).
CURSEFORGE_WEB_API = "https://www.curseforge.com/api/v1"
USER_AGENT = "slashdaemon/TheBlockSurvival publish.py (jon@papp.as)"

# CurseForge FileStatus enum. Only 4 is confirmed-live by observation; the rest
# are best-effort labels so the readback prints something meaningful, and any
# unknown code falls through to its raw number.
CF_FILE_STATUS = {
    1: "processing", 2: "changes-required", 3: "under-review", 4: "approved",
    5: "rejected", 6: "malware-detected", 7: "deleted", 8: "archived",
    9: "testing", 10: "released", 11: "ready-for-review", 12: "deprecated",
    13: "baking", 14: "awaiting-publishing", 15: "failed-publishing",
}

DEFAULT_MODRINTH_PROJECT = "theblocksurvival"
# Loader the .mrpack manifest declares. TheBlockSurvival is a Fabric pack.
PACK_LOADERS = ["fabric"]

# Per-platform variants. StreamCraft Live ships per-OS native libraries (one
# jar per platform), so a single modpack can't serve every OS — we produce one
# pack file per variant, each pointing at the matching StreamCraft jar. The
# canonical pack already references the Windows StreamCraft jar; for the other
# variants, publish.py overlays scripts/platform-sources/<variant>/ on top of
# the pack at export time, then restores.
#
# Distribution split: Modrinth carries ONLY the primary (windows) .mrpack —
# Modrinth Content Rule 5.7 forbids alternate variations as additional files
# on one project. The per-OS variants ship via GitHub releases; CurseForge
# keeps its primary+additional-files upload (allowed there).
PLATFORM_VARIANTS = ["windows", "linux", "linux-aarch64", "macos-arm64", "macos-x86_64"]
DEFAULT_VARIANT = "windows"  # canonical pack ≡ Windows; no swap needed for this one
PLATFORM_SOURCES_DIR = "scripts/platform-sources"


def variant_suffix(variant: str) -> str:
    """Filename suffix for a variant. Windows is the primary download and ships
    without a classifier suffix (matching the StreamCraft convention)."""
    return "" if variant == DEFAULT_VARIANT else f"-{variant}"

# The CurseForge build is produced from the canonical Modrinth-sourced pack by
# applying two per-platform transformations at export time, then restoring the
# canonical state. The Modrinth build is exported untouched.
#
# 1. EXCLUDE: pack entries that cannot ship in the CurseForge package at all.
#    Paths relative to the pack root.
CURSEFORGE_EXCLUDED = [
    "mods/voxy.pw.toml",                                 # not on CurseForge (Modrinth-only)
    "resourcepacks/fresh-animations.pw.toml",            # no 26.2-tagged file on CurseForge
    "resourcepacks/fresh-animations-extensions.pw.toml", # rides with main FA
]
# 2026-10-05: Complementary, Default Options + Balm and Xaero's Minimap/World Map came back
# into the CurseForge build as manifest references (scripts/cf-sources/). The old reason for
# leaving them out ("ARR / custom license, install separately") applied to bundling jars into a
# Modrinth-first pack; a CurseForge manifest only points at CurseForge-hosted files.

# 2. SWAP: pack entries whose canonical Modrinth-sourced .pw.toml is replaced
#    with a CurseForge-sourced equivalent so the CF zip carries a proper
#    manifest reference (not a bundled override). Files live in
#    scripts/cf-sources/, mirroring the pack's directory layout — every
#    .pw.toml in there is swapped into the pack for the CurseForge export,
#    then removed in the cleanup so the canonical pack stays Modrinth-sourced.
#
# To add a swap: cd into the pack, snapshot mods/resourcepacks/shaderpacks,
# `./packwiz.exe cf install <slug> -y`, copy the resulting CF metafile to
# scripts/cf-sources/<same-relative-path>, then restore the snapshot.
CF_SOURCES_DIR = "scripts/cf-sources"

# 3. EXTRA: files that ship ONLY in the CurseForge build. Any file under this
#    directory is copied to the matching path in the pack for a CurseForge
#    export, then removed again — the mirror image of CF_SOURCES_DIR, but for
#    plain files rather than .pw.toml metafiles.
#
#    Why it exists: the CurseForge build drops Default Options (ARR — the
#    author blocks modpack redistribution), and with it
#    config/defaultoptions/keybindings.txt, which is what moves Open Parties
#    and Claims off the apostrophe. OPAC hardcodes GLFW key 39 (') and so does
#    StreamCraft's menu key, so without this every CurseForge player gets a
#    hard keybind conflict while Modrinth players never see one. Vanilla reads
#    options.txt itself, so shipping it as an override applies the rebind with
#    no extra mod involved.
CF_EXTRA_DIR = "scripts/cf-extra"

# Appended to the CurseForge release changelog so the CF page always tells
# players what's missing relative to the Modrinth build, and why.
CURSEFORGE_EXCLUSION_NOTE = (
    "\n\n---\n"
    "### Not in the CurseForge build\n"
    "Two things can't ride along in the CurseForge package. "
    "Install them yourself if you want them:\n\n"
    "- **Voxy** (far render distance) — it isn't on CurseForge. Install it from "
    "its Modrinth page if you want it.\n"
    "- **Fresh Animations** (+ Extensions) — CurseForge has no 26.2 file yet. "
    "Add it from its page once one appears.\n\n"
    "### About the macOS / Linux downloads\n"
    "The Windows file is the primary download and references every mod through "
    "`manifest.json`. The macOS and Linux companion files are identical except for "
    "one bundled jar: **StreamCraft Live**, our own mod, ships per-OS native "
    "libraries, and its per-OS builds exist on CurseForge only as additional files "
    "attached to the primary version — there is no project/file pair a manifest can "
    "point at. So each companion file carries the matching StreamCraft build "
    "directly. Nothing else is bundled apart from the customized **VanillaTweaks** "
    "resource pack, which is generated at vanillatweaks.net (not distributed on "
    "CurseForge) and credited in `credits.txt`."
)


# --------------------------------------------------------------------------
# .env + pack metadata
# --------------------------------------------------------------------------

def load_dotenv(path: Path) -> None:
    """Minimal .env loader: KEY=VALUE per line, no quoting/expansion. Existing
    environment variables win over .env entries."""
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if key and value and key not in os.environ:
            os.environ[key] = value


def read_pack_field(pack_toml: Path, key: str, section: str | None = None) -> str:
    """Pull a `key = "value"` string out of pack.toml without a TOML lib
    (tomllib is 3.11+; the pack targets Python 3.10+). When `section` is given,
    only the lines under that `[section]` header are searched."""
    text = pack_toml.read_text(encoding="utf-8")
    if section:
        m = re.search(rf"^\[{re.escape(section)}\]\s*$(.*?)(?=^\[|\Z)", text,
                      re.MULTILINE | re.DOTALL)
        text = m.group(1) if m else ""
    m = re.search(rf'^\s*{re.escape(key)}\s*=\s*"([^"]+)"', text, re.MULTILINE)
    if not m:
        raise SystemExit(f"ERR: could not find `{key}` in {pack_toml}"
                         + (f" under [{section}]" if section else ""))
    return m.group(1)


def pw_filename(pw_toml: Path) -> str:
    """Best-effort read of a packwiz metafile's `filename = "..."` value.
    Returns "" when absent/unreadable — callers treat that as "can't compare"."""
    try:
        m = re.search(r'^\s*filename\s*=\s*"([^"]+)"',
                      pw_toml.read_text(encoding="utf-8"), re.MULTILINE)
        return m.group(1) if m else ""
    except OSError:
        return ""


def extract_changelog(changelog_path: Path, version: str) -> str:
    """Return the `## [X.Y.Z]` section of CHANGELOG.md (TBS-client uses the
    Keep-a-Changelog `## [version] — date` heading style)."""
    if not changelog_path.exists():
        return ""
    text = changelog_path.read_text(encoding="utf-8")
    pattern = rf"^## \[{re.escape(version)}\][^\n]*\n(.*?)(?=^## \[|\Z)"
    m = re.search(pattern, text, re.MULTILINE | re.DOTALL)
    return m.group(1).strip() if m else ""


def render_changelog(markdown_text: str, fmt: str) -> tuple[str, str]:
    """Returns (rendered, changelogType) for a CurseForge upload. CF's own
    "markdown" type renders raw markup unreliably, so by default we convert to
    HTML client-side and send changelogType="html"."""
    if fmt == "html":
        if _markdown is None:
            print("  WARN python-markdown not installed; sending changelogType=text. "
                  "Install with: pip install -r scripts/requirements.txt")
            return markdown_text, "text"
        return _markdown.markdown(markdown_text), "html"
    return markdown_text, fmt  # "markdown" / "text" sent verbatim


# --------------------------------------------------------------------------
# packwiz export
# --------------------------------------------------------------------------

def packwiz_export(pack_dir: Path, packwiz_exe: Path, platform: str, out_path: Path,
                   variant: str = DEFAULT_VARIANT,
                   bundle_sc_dir: Path | None = None,
                   bundle_sc_version: str | None = None) -> None:
    """Run `packwiz refresh` then `packwiz <platform> export` into out_path.

    Two per-platform transformations are applied to the pack in-place before
    export, then reverted in a finally block so the canonical Modrinth-sourced
    state is always restored — even on a failed export:

    - **CurseForge swap** (only when platform=="curseforge"): excludes
      CURSEFORGE_EXCLUDED entries and overlays the files in CF_SOURCES_DIR so
      the .zip carries proper CurseForge manifest references.
    - **CurseForge extras** (only when platform=="curseforge"): copies in the
      files under CF_EXTRA_DIR, which exist only in the CurseForge build.
    - **Platform overlay** (when variant != DEFAULT_VARIANT): overlays the
      files in PLATFORM_SOURCES_DIR/<variant>/ — currently a per-OS
      StreamCraft Live .pw.toml so each platform's .mrpack / .zip points at
      the matching StreamCraft jar. Layered on top of the CurseForge swap so
      the per-OS StreamCraft wins over the Windows CF reference for
      non-Windows CF builds.
    - **StreamCraft bundle** (when bundle_sc_dir is set): drops the
      streamcraft-live pin entirely and ships the matching per-OS jar as a
      bundled override instead. For prereleases of an unreleased StreamCraft
      build, which by definition has no Modrinth/CurseForge URL to pin."""

    out_path.parent.mkdir(parents=True, exist_ok=True)

    cf_excluded: list[Path] = []
    stash_only: list[Path] = []   # removed for the export, restored afterwards
    swaps: dict[Path, Path] = {}  # canonical-path-in-pack -> source-file-to-copy-in
    excluded_set: set[Path] = set()

    if platform == "curseforge":
        excluded_set = {pack_dir / rel for rel in CURSEFORGE_EXCLUDED}
        for pw in excluded_set:
            if pw.exists():
                cf_excluded.append(pw)
        cf_src_root = pack_dir / CF_SOURCES_DIR
        if cf_src_root.is_dir():
            for cf_src in sorted(cf_src_root.rglob("*.pw.toml")):
                canon = pack_dir / cf_src.relative_to(cf_src_root)
                # Exclusion wins over swap — a stray cf-source for an
                # excluded entry would otherwise sneak it back into the build.
                if canon in excluded_set:
                    continue
                swaps[canon] = cf_src

        # CF-only extra files (see CF_EXTRA_DIR). These have no canonical
        # counterpart in the pack, so the stash/restore below simply deletes
        # them again after the export — nothing to restore.
        cf_extra_root = pack_dir / CF_EXTRA_DIR
        if cf_extra_root.is_dir():
            for extra in sorted(cf_extra_root.rglob("*")):
                if not extra.is_file():
                    continue
                canon = pack_dir / extra.relative_to(cf_extra_root)
                if canon in excluded_set:
                    continue
                swaps[canon] = extra

        # Stale-swap guard. A CurseForge swap can silently rot: CurseForge may
        # still host only an older Minecraft build of a mod while the canonical
        # Modrinth source has already moved to this pack's MC version. Shipping
        # that stale CF file makes Fabric refuse to load the whole pack at launch
        # (the Zoomify 2.15.2+1.21.11-vs-2.16.0+26.1 incident: CF lagged a release
        # behind Modrinth). Catch it offline — no CF API needed: if the canonical
        # jar's filename embeds this pack's MC version token but the swapped CF
        # jar's filename does not, the swap is stale and must be dropped until
        # CurseForge catches up. (Conservative: only fires when the canonical
        # filename *proves* a matching build exists, so mods that simply don't
        # encode the MC version in their filename never false-positive.)
        mc_version = read_pack_field(pack_dir / "pack.toml", "minecraft",
                                     section="versions")
        mc_tokens = [t for t in (mc_version, mc_version.rsplit(".", 1)[0]) if t]
        stale: list[str] = []
        for canon, cf_src in swaps.items():
            canon_fn, swap_fn = pw_filename(canon), pw_filename(cf_src)
            if not canon_fn or not swap_fn:
                continue
            if (any(t in canon_fn for t in mc_tokens)
                    and not any(t in swap_fn for t in mc_tokens)):
                stale.append(
                    f"    {canon.relative_to(pack_dir).as_posix()}: "
                    f"Modrinth ships '{canon_fn}' but the CurseForge swap "
                    f"({cf_src.relative_to(pack_dir).as_posix()}) pins '{swap_fn}'")
        if stale:
            raise SystemExit(
                "ERR: stale CurseForge swap(s) — the pinned CurseForge file targets "
                f"an older Minecraft build than the canonical pack (MC {mc_version}):\n"
                + "\n".join(stale)
                + f"\n  CurseForge has no {mc_version} build for these mods yet. Delete "
                  "the offending scripts/cf-sources/<...>.pw.toml so the mod rides as a "
                  "bundled override, and re-add the swap once CurseForge catches up.")

    if variant != DEFAULT_VARIANT:
        plat_root = pack_dir / PLATFORM_SOURCES_DIR / variant
        if plat_root.is_dir():
            for plat_src in sorted(plat_root.rglob("*.pw.toml")):
                canon = pack_dir / plat_src.relative_to(plat_root)
                if canon in excluded_set:
                    continue
                # Platform overlay overrides any CF swap at the same path —
                # per-OS StreamCraft jar wins over the Windows CF reference.
                swaps[canon] = plat_src

    if bundle_sc_dir is not None:
        # Ship the jar itself rather than a pin. Must run AFTER the CF swap and
        # the platform overlay so it can drop whichever streamcraft pin they
        # selected — all three target the same path.
        mc_ver = read_pack_field(pack_dir / "pack.toml", "minecraft", section="versions")
        jar_name = (f"streamcraft-{bundle_sc_version}+mc{mc_ver}"
                    f"{variant_suffix(variant)}.jar")
        src_jar = Path(bundle_sc_dir) / jar_name
        if not src_jar.is_file():
            raise SystemExit(
                f"ERR: --bundle-streamcraft is set but {src_jar} does not exist.\n"
                f"  Build it first: cd StreamCraft/versions/26.1 && ./gradlew :band:build")
        sc_pin = pack_dir / "mods" / "streamcraft-live.pw.toml"
        swaps.pop(sc_pin, None)          # discard any CF / per-OS pin swap
        if sc_pin.exists():
            stash_only.append(sc_pin)    # stashed now, restored in the finally
        swaps[pack_dir / "mods" / jar_name] = src_jar
        print(f"  StreamCraft bundled as override: {jar_name}")

    # Files we'll move/replace and must restore afterward.
    affected = list(cf_excluded) + stash_only + list(swaps.keys())

    stash_dir: Path | None = None
    try:
        if affected:
            # Stash canonical state OUTSIDE pack_dir so packwiz can't re-index it.
            # Index-prefix to avoid name collisions across mods/ rp/ sp/.
            stash_dir = Path(tempfile.mkdtemp(prefix="tbs-export-stash-"))
            for i, p in enumerate(affected):
                if p.exists():
                    shutil.move(str(p), str(stash_dir / f"{i}_{p.name}"))
            # Apply swaps: copy each source over its canonical pack path.
            for canon, src in swaps.items():
                canon.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(src), str(canon))
            for p in cf_excluded:
                print(f"  excluded from CurseForge build: {p.relative_to(pack_dir).as_posix()}")
            if variant != DEFAULT_VARIANT:
                print(f"  platform overlay applied:       {variant}")

        for args in (["refresh"], [platform, "export", "-o", str(out_path)]):
            print(f"  $ packwiz {' '.join(args)}")
            r = subprocess.run([str(packwiz_exe), *args], cwd=pack_dir)
            if r.returncode != 0:
                raise SystemExit(
                    f"ERR: `packwiz {' '.join(args)}` exited {r.returncode}. "
                    "A non-zero curseforge export usually means a mod's CurseForge "
                    "file blocks third-party distribution — re-source it from Modrinth."
                )
    finally:
        if stash_dir is not None:
            # Remove swap-applied files first so the canonical restore is clean.
            for canon in swaps:
                if canon.exists():
                    canon.unlink()
            # Restore canonical files from the stash.
            for i, p in enumerate(affected):
                stashed = stash_dir / f"{i}_{p.name}"
                if stashed.exists():
                    p.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(stashed), str(p))
            stash_dir.rmdir()
            # Rebuild the index to match the restored canonical state.
            subprocess.run([str(packwiz_exe), "refresh"], cwd=pack_dir)

    if not out_path.exists():
        raise SystemExit(f"ERR: packwiz reported success but {out_path} is missing")
    size_mb = out_path.stat().st_size / 1_000_000
    print(f"  exported {out_path.name} ({size_mb:.2f} MB)")


# --------------------------------------------------------------------------
# Modrinth
# --------------------------------------------------------------------------

def modrinth_resolve_project(slug_or_id: str, token: str) -> str:
    """Modrinth's POST /version wants the project's base62 ID in the JSON body —
    a slug there fails with 'Base62 decoding overflowed'. URL paths take either."""
    r = requests.get(f"{MODRINTH_API}/project/{slug_or_id}",
                      headers={"Authorization": token, "User-Agent": USER_AGENT},
                      timeout=30)
    if r.status_code == 404:
        raise SystemExit(
            f"ERR: Modrinth project '{slug_or_id}' not found. Create the modpack "
            f"project at https://modrinth.com/ first, then set MODRINTH_PROJECT "
            f"(slug or ID) in .env or pass --modrinth-project."
        )
    r.raise_for_status()
    data = r.json()
    if data.get("project_type") != "modpack":
        print(f"  WARN Modrinth project '{slug_or_id}' has project_type="
              f"{data.get('project_type')!r}, expected 'modpack'")
    return data["id"]


def modrinth_find_version(project: str, version_number: str, token: str) -> str | None:
    r = requests.get(f"{MODRINTH_API}/project/{project}/version",
                      headers={"Authorization": token, "User-Agent": USER_AGENT},
                      timeout=30)
    r.raise_for_status()
    for v in r.json():
        if v["version_number"] == version_number:
            return v["id"]
    return None


def publish_modrinth(
    mrpacks: list[Path],
    project: str,
    version: str,
    game_versions: list[str],
    version_type: str,
    changelog: str,
    token: str,
    dry_run: bool,
) -> bool:
    """Upload one Modrinth version carrying ONLY the primary (windows/default)
    .mrpack. Modrinth Content Rule 5.7 forbids alternate variations of a project
    as additional files (the pack was rejected for exactly this), so the per-OS
    variant .mrpacks are never attached here — they are distributed via GitHub
    releases instead. Returns True on a successful upload."""
    if len(mrpacks) != 1:
        raise ValueError(
            "publish_modrinth: expected exactly the primary .mrpack — per-OS "
            "variants must not be uploaded to Modrinth (Content Rule 5.7)")
    primary = mrpacks[0]
    print(f"\n=== Modrinth: {project} v{version} ===")
    print(f"  game_versions: {game_versions}  loaders: {PACK_LOADERS}  type: {version_type}")
    print(f"  file: {primary.name}")

    metadata = {
        "name": f"v{version}",
        "version_number": version,
        "changelog": changelog,
        "dependencies": [],          # modpack deps are carried inside the .mrpack manifest
        "game_versions": game_versions,
        "version_type": version_type,
        "loaders": PACK_LOADERS,
        "featured": False,
        "file_parts": [primary.name],
        "primary_file": primary.name,
    }

    if dry_run:
        print(f"  DRY-RUN — would POST {MODRINTH_API}/version:\n"
              f"{json.dumps(metadata, indent=2)}")
        return False

    project_id = modrinth_resolve_project(project, token)
    metadata["project_id"] = project_id  # base62 ID — strict in the JSON body
    existing = modrinth_find_version(project, version, token)
    if existing:
        print(f"  SKIP — version {version} already published (id={existing})")
        return False

    primary_mb = primary.stat().st_size / 1_000_000
    print(f"  POST {MODRINTH_API}/version  ({primary_mb:.2f} MB) ...")
    with primary.open("rb") as fh:
        files = [
            ("data", (None, json.dumps(metadata), "application/json")),
            (primary.name, (primary.name, fh, "application/x-modrinth-modpack+zip")),
        ]
        r = requests.post(f"{MODRINTH_API}/version",
                          headers={"Authorization": token, "User-Agent": USER_AGENT},
                          files=files, timeout=600)
    if r.status_code >= 400:
        raise RuntimeError(f"Modrinth {r.status_code}: {r.text}")
    version_id = r.json()["id"]
    print(f"  OK id={version_id}  ({primary.name})  "
          f"https://modrinth.com/modpack/{project}/version/{version}")
    return True


# --------------------------------------------------------------------------
# CurseForge
# --------------------------------------------------------------------------

def cf_fetch_catalog(token: str) -> tuple[dict[tuple[int, str], int], dict[str, int]]:
    """Return ((typeId, name)->id catalog, version-type slug->id map). CurseForge
    lists each version name under several type buckets; uploads must reference the
    Minecraft-type ID for MC versions and the Modloader-type ID for "Fabric"."""
    hdr = {"X-Api-Token": token, "User-Agent": USER_AGENT}
    r = requests.get(f"{CURSEFORGE_API}/game/versions", headers=hdr, timeout=30)
    r.raise_for_status()
    catalog = {(v["gameVersionTypeID"], v["name"]): v["id"] for v in r.json()}
    r = requests.get(f"{CURSEFORGE_API}/game/version-types", headers=hdr, timeout=30)
    r.raise_for_status()
    type_ids = {t["slug"]: t["id"] for t in r.json()}
    return catalog, type_ids


def cf_type_slug(name: str) -> str | None:
    """Version-type slug a name lives under: "26.1.2" -> "minecraft-26-1",
    "1.21.11" -> "minecraft-1-21", "Fabric" -> "modloader"."""
    if name in ("Fabric", "NeoForge", "Quilt"):
        return "modloader"
    m = re.match(r"^(\d+)\.(\d+)(?:\.\d+)?$", name)
    return f"minecraft-{m.group(1)}-{m.group(2)}" if m else None


def cf_resolve_game_versions(
    catalog: dict[tuple[int, str], int],
    type_ids: dict[str, int],
    names: list[str],
) -> list[int]:
    ids, missing = [], []
    for name in names:
        slug = cf_type_slug(name)
        type_id = type_ids.get(slug) if slug else None
        cf_id = catalog.get((type_id, name)) if type_id else None
        if cf_id is None:
            missing.append(f"{name} (slug={slug})")
        else:
            ids.append(cf_id)
    if missing:
        print(f"  WARN CurseForge catalog missing {missing}; those entries "
              f"won't appear on the file's version list")
    return ids


def cf_read_file(project_id: int, file_id: int) -> dict | None:
    """Read one file's public metadata (fileName, status, additionalFilesCount).
    Returns None if CurseForge hasn't published it yet or the read fails —
    callers treat that as "not visible", never as success."""
    url = f"{CURSEFORGE_WEB_API}/mods/{project_id}/files/{file_id}"
    try:
        r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
        if r.status_code >= 400:
            return None
        return r.json().get("data") or None
    except Exception:
        return None


def cf_status_label(status) -> str:
    return CF_FILE_STATUS.get(status, f"status-{status}")


def cf_verify_release(
    project_id: int,
    primary_file_id: int,
    expected_additional: int,
    attempts: int = 6,
    delay: int = 15,
) -> bool:
    """Read the release back from CurseForge and confirm the primary carries
    `expected_additional` companion files.

    Why this exists: the upload API happily returns a fileID for an additional
    file and can STILL leave the release Windows-only — CurseForge locks the
    parent a few seconds after ingest, so a mid-run 500/1012 silently drops the
    companions. v1.4.0 shipped that way (primary only) and nothing in the
    pipeline noticed for weeks; Mac and Linux users got the Windows pack, which
    pins the Windows StreamCraft jar and breaks capture and voice on their OS.

    Ingest is asynchronous, so poll rather than checking once. A short count is
    a hard failure. Files still awaiting moderation are NOT a failure — they are
    attached and will go live on approval — but they are reported explicitly.
    """
    print(f"\n  --- verifying CurseForge release (project {project_id}, "
          f"primary {primary_file_id}) ---")
    for attempt in range(1, attempts + 1):
        data = cf_read_file(project_id, primary_file_id)
        if data is None:
            print(f"    primary not readable yet (attempt {attempt}/{attempts})")
        else:
            found = data.get("additionalFilesCount", 0) or 0
            label = cf_status_label(data.get("status"))
            print(f"    primary {data.get('fileName')} [{label}] — "
                  f"additional files: {found}/{expected_additional}")
            if found >= expected_additional:
                if data.get("status") != 4:
                    print(f"    NOTE primary is '{label}', not yet approved — "
                          f"files go live once CurseForge moderation clears them.")
                print("    VERIFIED — every expected companion is attached.")
                return True
        if attempt < attempts:
            time.sleep(delay)

    print(f"    FAILED — expected {expected_additional} additional file(s) on "
          f"primary {primary_file_id}; CurseForge does not report them.")
    print(f"    Mac/Linux players would receive the Windows pack. Re-run:")
    print(f"      python scripts/publish.py --platform curseforge --no-export \\")
    print(f"          --cf-parent-file-id {primary_file_id} --variant <the missing ones>")
    return False


def publish_curseforge(
    zips: list[Path],
    project_id: int,
    version: str,
    game_version_names: list[str],
    release_type: str,
    changelog: str,
    changelog_type: str,
    token: str,
    dry_run: bool,
    parent_file_id: int | None = None,
    verify: bool = True,
) -> bool:
    """Upload `zips[0]` as the primary CurseForge file; upload each subsequent
    entry as an additional file with `parentFileID` set to the primary's file
    id — matching StreamCraft's per-platform CurseForge convention. CurseForge
    rejects gameVersions on additional files (children inherit from parent),
    so only the primary carries the versions list.

    Recovery: pass `parent_file_id` (the file id of an already-uploaded primary)
    and EVERY zip in `zips` is uploaded as an additional file against it — the
    primary is not re-uploaded. CurseForge's upload endpoint intermittently 500s
    or returns 1012 (file locked) partway through a multi-file release; rerun
    with --parent-file-id <primary id> --variant <the ones that failed> instead
    of republishing the whole version."""
    if not zips:
        raise ValueError("publish_curseforge: empty zips list")
    recovery = parent_file_id is not None
    primary = zips[0]
    print(f"\n=== CurseForge: project {project_id} v{version} ===")
    if recovery:
        print(f"  RECOVERY — attaching {len(zips)} additional file(s) to "
              f"existing primary fileID={parent_file_id}")
        for p in zips:
            print(f"         {p.name}")
    else:
        print(f"  files: {len(zips)} (primary: {primary.name})")
        for p in zips[1:]:
            print(f"         {p.name}")

    catalog, type_ids, game_version_ids = {}, {}, []
    if token and not recovery:
        try:
            catalog, type_ids = cf_fetch_catalog(token)
            game_version_ids = cf_resolve_game_versions(catalog, type_ids, game_version_names)
            print(f"  game versions {game_version_names} -> ids {game_version_ids}")
        except Exception as e:
            print(f"  ERR could not fetch CurseForge catalog: {e}")
            if not dry_run:
                raise

    primary_meta = {
        "changelog": changelog,
        "changelogType": changelog_type,
        "displayName": primary.name,
        "gameVersions": game_version_ids,
        "releaseType": release_type,
    }

    if dry_run:
        if recovery:
            for p in zips:
                print(f"  DRY-RUN — would POST additional ({p.name}) to "
                      f"parentFileID={parent_file_id}")
            return False
        print(f"  DRY-RUN — would POST primary:\n{json.dumps(primary_meta, indent=2)}")
        for p in zips[1:]:
            extra_preview = {
                "changelog": "<same>", "changelogType": changelog_type,
                "displayName": p.name, "releaseType": release_type,
                "parentFileID": "<resolved from primary upload>",
            }
            print(f"  DRY-RUN — would POST additional ({p.name}):\n"
                  f"{json.dumps(extra_preview, indent=2)}")
        return False

    if not game_version_ids and not recovery:
        raise SystemExit("ERR: CurseForge upload needs at least one resolved gameVersion id")

    url = f"{CURSEFORGE_API}/projects/{project_id}/upload-file"

    def _upload(z: Path, meta: dict) -> int:
        size_mb = z.stat().st_size / 1_000_000
        print(f"  POST {url} ({size_mb:.2f} MB, {z.name}) ...")
        with z.open("rb") as fh:
            files = {
                "metadata": (None, json.dumps(meta), "application/json"),
                "file": (z.name, fh, "application/zip"),
            }
            r = requests.post(url, headers={"X-Api-Token": token, "User-Agent": USER_AGENT},
                              files=files, timeout=600)
        if r.status_code >= 400:
            raise RuntimeError(f"CurseForge {r.status_code}: {r.text}")
        fid = r.json().get("id")
        if not isinstance(fid, int):
            raise RuntimeError(f"CurseForge returned no file id: {r.json()}")
        return fid

    if recovery:
        primary_id = parent_file_id
        pending = list(zips)
        # A recovery run tops up a primary that may already carry companions
        # from the original publish, so the expected total is what is already
        # attached plus what we are about to add.
        existing = cf_read_file(project_id, primary_id) or {}
        baseline = existing.get("additionalFilesCount", 0) or 0
        if baseline:
            print(f"  primary already carries {baseline} additional file(s)")
    else:
        primary_id = _upload(primary, primary_meta)
        print(f"    OK primary fileID={primary_id}")
        pending = zips[1:]
        baseline = 0
    for p in pending:
        extra_meta = {
            "changelog": changelog,
            "changelogType": changelog_type,
            "displayName": p.name,
            "releaseType": release_type,
            "parentFileID": primary_id,
        }
        # CurseForge briefly locks a version while it ingests the previous
        # file; the next additional then comes back 500 or 1012 even though
        # the request was well-formed. Retry with backoff before giving up.
        for attempt in range(1, 4):
            try:
                extra_id = _upload(p, extra_meta)
                break
            except RuntimeError as e:
                if attempt == 3:
                    raise
                wait = 20 * attempt
                print(f"    retry {attempt}/2 in {wait}s after: {e}")
                time.sleep(wait)
        print(f"    OK additional fileID={extra_id}")

    # An upload that returned a fileID is not proof the release is complete —
    # read it back before calling this a success.
    if verify and pending:
        if not cf_verify_release(project_id, primary_id, baseline + len(pending)):
            raise RuntimeError(
                f"CurseForge release verification failed for project {project_id} "
                f"(primary {primary_id})")
    return True


# --------------------------------------------------------------------------

def main() -> int:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--platform", choices=["modrinth", "curseforge", "both"],
                   default="both", help="Where to publish (default: both)")
    p.add_argument("--variant", default="all",
                   help=f"Platform variant(s) to build: {'/'.join(PLATFORM_VARIANTS)} or "
                        f"'all' (default). All variants are exported to dist/, but only "
                        f"the primary ({DEFAULT_VARIANT}) .mrpack is uploaded to Modrinth "
                        f"(Content Rule 5.7); per-OS variants ship via GitHub releases. "
                        f"CurseForge uploads primary+additionals.")
    p.add_argument("--type", default="release", choices=["release", "beta", "alpha"],
                   help="Release channel (default: release)")
    p.add_argument("--modrinth-project", help="Modrinth slug or ID "
                   "(default: $MODRINTH_PROJECT or 'theblocksurvival')")
    p.add_argument("--cf-parent-file-id", type=int,
                   help="Recovery: attach the selected --variant zip(s) to this "
                        "already-uploaded primary CurseForge file id instead of "
                        "uploading a new primary. Use after a partial CurseForge "
                        "failure (500 / 1012 file-locked) to finish the release.")
    p.add_argument("--cf-project-id", type=int,
                   help="CurseForge numeric project ID (default: $CURSEFORGE_PROJECT_ID)")
    p.add_argument("--game-versions", help="Comma-separated MC versions to advertise "
                   "(default: the pack.toml [versions] minecraft value)")
    p.add_argument("--changelog-format", default="html",
                   choices=["html", "markdown", "text"],
                   help="CurseForge changelogType (default: html, converted client-side)")
    p.add_argument("--no-export", action="store_true",
                   help="Skip packwiz export; use the artifact already in dist/")
    p.add_argument("--bundle-streamcraft", metavar="DIR",
                   help="Ship StreamCraft as a bundled override from DIR instead of "
                        "pinning it, picking the per-OS jar matching each variant. For "
                        "prereleases of an unreleased build that has no public URL yet. "
                        "Requires --streamcraft-version.")
    p.add_argument("--streamcraft-version", metavar="VER",
                   help="StreamCraft version to bundle (e.g. 0.19.0). Used with "
                        "--bundle-streamcraft to resolve each variant's jar filename.")
    p.add_argument("--no-cf-verify", action="store_true",
                   help="Skip the post-publish readback that confirms the per-OS "
                        "companion files actually attached to the primary")
    p.add_argument("--cf-verify-only", action="store_true",
                   help="Upload nothing; just read the CurseForge release back and "
                        "report whether the expected companions are attached. "
                        "Requires --cf-parent-file-id.")
    p.add_argument("--dry-run", action="store_true",
                   help="Export and print upload metadata, but upload nothing")
    args = p.parse_args()

    # Windows consoles default to cp1252 — force UTF-8 so em-dashes in our own
    # output and in the echoed changelog don't turn into mojibake.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass

    pack_dir = Path(__file__).resolve().parent.parent
    load_dotenv(pack_dir / ".env")

    packwiz_exe = pack_dir / ("packwiz.exe" if os.name == "nt" else "packwiz")
    if not packwiz_exe.exists():
        # fall back to whichever name is present
        packwiz_exe = next(pack_dir.glob("packwiz*"), packwiz_exe)
    version = read_pack_field(pack_dir / "pack.toml", "version")
    mc_version = read_pack_field(pack_dir / "pack.toml", "minecraft", section="versions")
    game_versions = ([v.strip() for v in args.game_versions.split(",")]
                     if args.game_versions else [mc_version])

    changelog_md = extract_changelog(pack_dir / "CHANGELOG.md", version)
    if changelog_md:
        print(f"Version {version} — changelog: "
              f"{changelog_md.splitlines()[0]} ({len(changelog_md)} chars)")
    else:
        print(f"WARN no `## [{version}]` section found in CHANGELOG.md")

    do_modrinth = args.platform in ("modrinth", "both")
    do_curseforge = args.platform in ("curseforge", "both")

    # Determine variants to build.
    if args.variant == "all":
        variants = list(PLATFORM_VARIANTS)
    elif all(v.strip() in PLATFORM_VARIANTS for v in args.variant.split(",")):
        # Comma-separated list so a partial CurseForge failure can be finished
        # with exactly the variants that didn't land (see --cf-parent-file-id).
        variants = [v.strip() for v in args.variant.split(",")]
    else:
        print(f"ERR: unknown --variant {args.variant!r}; valid: {PLATFORM_VARIANTS} or 'all'")
        return 1
    print(f"Variants: {', '.join(variants)}")

    # ---- verify-only: read an existing release back, upload nothing --------
    if args.cf_verify_only:
        if not args.cf_parent_file_id:
            print("ERR: --cf-verify-only requires --cf-parent-file-id "
                  "(the primary file id to inspect)")
            return 1
        cf_pid = args.cf_project_id or int(
            os.environ.get("CURSEFORGE_PROJECT_ID", "0").strip() or 0)
        if not cf_pid:
            print("ERR: --cf-project-id not given and CURSEFORGE_PROJECT_ID not set")
            return 1
        expected = len([v for v in variants if v != DEFAULT_VARIANT])
        ok = cf_verify_release(cf_pid, args.cf_parent_file_id, expected)
        print(f"\nDone — {0 if ok else 1} failure(s)")
        return 0 if ok else 1

    bundle_sc_dir: Path | None = None
    if args.bundle_streamcraft:
        if not args.streamcraft_version:
            print("ERR: --bundle-streamcraft requires --streamcraft-version")
            return 1
        bundle_sc_dir = Path(args.bundle_streamcraft).expanduser().resolve()
        if not bundle_sc_dir.is_dir():
            print(f"ERR: --bundle-streamcraft directory not found: {bundle_sc_dir}")
            return 1
        print(f"Bundling StreamCraft {args.streamcraft_version} from {bundle_sc_dir}")

    dist = pack_dir / "dist"
    mrpacks: list[Path] = []
    cf_zips: list[Path] = []
    for v in variants:
        suf = variant_suffix(v)
        if do_modrinth:
            mrpacks.append(dist / f"TheBlockSurvival-{version}{suf}.mrpack")
        if do_curseforge:
            cf_zips.append(dist / f"TheBlockSurvival-{version}{suf}.zip")

    # ---- export -----------------------------------------------------------
    if not args.no_export:
        for idx, v in enumerate(variants):
            if do_modrinth:
                print(f"\n--- exporting .mrpack ({v}) ---")
                packwiz_export(pack_dir, packwiz_exe, "modrinth", mrpacks[idx], variant=v,
                               bundle_sc_dir=bundle_sc_dir,
                               bundle_sc_version=args.streamcraft_version)
            if do_curseforge:
                print(f"\n--- exporting CurseForge .zip ({v}) ---")
                packwiz_export(pack_dir, packwiz_exe, "curseforge", cf_zips[idx], variant=v,
                               bundle_sc_dir=bundle_sc_dir,
                               bundle_sc_version=args.streamcraft_version)

    failures = 0

    # ---- Modrinth (primary variant ONLY — Content Rule 5.7) ----------------
    # The per-OS variant .mrpacks are still exported above, but they ship via
    # GitHub releases; attaching them to a Modrinth version got the pack
    # rejected as an "Unsupported Project" (multiple variations as files).
    if do_modrinth:
        if DEFAULT_VARIANT not in variants:
            print(f"ERR: Modrinth publishing requires the '{DEFAULT_VARIANT}' (primary) "
                  f"variant; got --variant {args.variant!r}. Per-OS variants are "
                  f"GitHub-release-only.")
            return 1
        primary_mrpack = dist / f"TheBlockSurvival-{version}.mrpack"
        if not primary_mrpack.exists():
            raise SystemExit(f"ERR: {primary_mrpack} not found (run without --no-export)")
        token = os.environ.get("MODRINTH_TOKEN", "")
        if not token and not args.dry_run:
            print("ERR: MODRINTH_TOKEN not set (.env or env var)")
            return 1
        project = (args.modrinth_project or os.environ.get("MODRINTH_PROJECT")
                   or DEFAULT_MODRINTH_PROJECT)
        try:
            publish_modrinth([primary_mrpack], project, version, game_versions,
                             args.type, changelog_md, token, args.dry_run)
        except Exception as e:
            print(f"  FAILED: {e}")
            failures += 1

    # ---- CurseForge (primary + additionals via parentFileID) --------------
    if do_curseforge:
        for p in cf_zips:
            if not p.exists():
                raise SystemExit(f"ERR: {p} not found (run without --no-export)")
        token = os.environ.get("CURSEFORGE_TOKEN", "")
        if not token and not args.dry_run:
            print("ERR: CURSEFORGE_TOKEN not set (.env or env var)")
            return 1
        cf_pid = args.cf_project_id
        if cf_pid is None:
            env_pid = os.environ.get("CURSEFORGE_PROJECT_ID", "").strip()
            if not env_pid and not args.dry_run:
                print("ERR: --cf-project-id not given and CURSEFORGE_PROJECT_ID not set")
                return 1
            cf_pid = int(env_pid) if env_pid else 0
        # The CurseForge build ships without the CURSEFORGE_EXCLUDED entries —
        # append a note so the CF release page always explains what's missing.
        cf_changelog_md = changelog_md + CURSEFORGE_EXCLUSION_NOTE
        changelog_cf, changelog_type = render_changelog(cf_changelog_md, args.changelog_format)
        try:
            publish_curseforge(cf_zips, cf_pid, version, [*game_versions, "Fabric"],
                               args.type, changelog_cf, changelog_type, token, args.dry_run,
                               parent_file_id=args.cf_parent_file_id,
                               verify=not args.no_cf_verify)
        except Exception as e:
            print(f"  FAILED: {e}")
            failures += 1

    print(f"\nDone — {failures} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
