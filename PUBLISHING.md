# Publishing TheBlockSurvival

How the TheBlockSurvival client modpack is published to Modrinth and CurseForge.
This file is maintainer-only — it is excluded from the distributed pack via
`.packwizignore`.

## Tooling

`scripts/publish.py` exports the pack with packwiz and uploads it. Each release
produces **five** artifacts per platform — one per OS, because StreamCraft Live
ships per-OS native libraries that can't ride together in a single pack file:

| Variant | Prism artifact (GitHub release) | CurseForge artifact |
|---------|-------------------|---------------------|
| Windows *(primary)* | `TheBlockSurvival-pc-X.Y.Z.mrpack` | `TheBlockSurvival-pc-X.Y.Z.zip` |
| Linux | `TheBlockSurvival-linux-x64-X.Y.Z.mrpack` | `TheBlockSurvival-linux-x64-X.Y.Z.zip` |
| Linux ARM64 | `TheBlockSurvival-linux-arm64-X.Y.Z.mrpack` | `TheBlockSurvival-linux-arm64-X.Y.Z.zip` |
| macOS Apple Silicon | `TheBlockSurvival-mac-arm64-X.Y.Z.mrpack` | `TheBlockSurvival-mac-arm64-X.Y.Z.zip` |
| macOS Intel | `TheBlockSurvival-mac-x64-X.Y.Z.mrpack` | `TheBlockSurvival-mac-x64-X.Y.Z.zip` |

Names match StreamCraft's system labels (`pc`, `mac-arm64`, `mac-x64`, `linux-x64`,
`linux-arm64`) since 2.0.0; earlier releases used `TheBlockSurvival-X.Y.Z[-<os>]`.

```bash
pip install -r scripts/requirements.txt        # requests + markdown
cp .env.example .env                           # then fill in tokens

python scripts/publish.py --platform both --variant all --dry-run    # export + print metadata
python scripts/publish.py --platform modrinth                        # exports all variants, uploads Windows only
python scripts/publish.py --platform both                            # both stores
```

The version is read from `pack.toml`; the changelog is the matching `## [X.Y.Z]`
section of `CHANGELOG.md`. Modrinth uploads are idempotent.

**Where each artifact goes** (changed after the 2026-06 Modrinth rejection):

- **Modrinth** receives ONLY the primary Windows `.mrpack`. Modrinth Content
  Rule 5.7 forbids uploading alternate variations of a project as additional
  files — the pack was rejected ("Unsupported Project") for attaching all five
  per-OS variants to one version. `publish.py` now refuses to upload variants
  to Modrinth.
- **GitHub releases** carry all five `.mrpack` variants — that is where
  Mac/Linux players download from (linked from the Modrinth description and
  README).
- **CurseForge** receives the Windows zip as primary + four additional files
  linked via `parentFileID`, matching the StreamCraft convention (additional
  files are supported on CurseForge).

### Post-publish verification (do not skip this)

A CurseForge upload that returns a fileID is **not** proof the release is
complete. CurseForge locks the primary a few seconds after it finishes ingest,
so a mid-run 500 / 1012 silently drops the remaining companions and leaves the
project Windows-only. That is exactly how **v1.4.0 shipped** — primary only, for
weeks — which meant every Mac and Linux player installing from the CurseForge
app got the Windows pack. That pack pins the Windows StreamCraft jar, whose
platform marker is `windows-x86_64`, so on macOS the native bundle never
extracts, capture is disabled, and the voice mic list collapses to just
"Default" with no warning.

`publish.py` now reads the release back after every CurseForge upload and fails
loudly when the expected companions are not attached. To check an existing
release at any time (uploads nothing):

```bash
python scripts/publish.py --platform curseforge --cf-verify-only \
    --cf-parent-file-id <primary file id> --variant all
```

Files still awaiting CurseForge moderation are reported but are not treated as a
failure — they are attached and go live on approval. A short **count** is a hard
failure. `--no-cf-verify` skips the check.

### Per-platform StreamCraft overlay

The canonical pack references the Windows StreamCraft jar. For non-Windows
variants, `publish.py` overlays the matching `streamcraft-live.pw.toml` from
`scripts/platform-sources/<variant>/mods/` at export time, then restores. When
StreamCraft publishes a new version, regenerate the four non-Windows files —
swap the `filename`, `url`, and SHA-512 to match the new variant jars. The
Modrinth API gives you the URLs and hashes:

```bash
curl "https://api.modrinth.com/v2/version/<new-version-id>" | \
  python -c "import sys,json; [print(f['filename'], f['hashes']['sha512']) for f in json.load(sys.stdin)['files']]"
```

## Release checklist

1. Add/update mods (**Modrinth-first for this pack** — see the License
   compliance section; CF-sourced mods become override jars and Modrinth
   rejects the pack), `packwiz refresh`.
2. Re-run the license check below if any mod was added.
3. Bump `version` in `pack.toml`; add a `## [X.Y.Z]` entry to `CHANGELOG.md`.
4. `python scripts/publish.py --platform modrinth --dry-run` — sanity-check.
5. `python scripts/publish.py --platform modrinth`.
6. Commit the pack changes inside this repo.

---

## One-time: create the Modrinth project

`publish.py` uploads versions to an *existing* project — it does not create one.
Create it once at <https://modrinth.com/> → **Create a project** → type **Modpack**,
then fill in the fields below and upload the icon + gallery screenshots.

### Project fields

| Field | Value |
|-------|-------|
| Name | `TheBlockSurvival` |
| Slug / URL | `theblocksurvival` |
| Summary | *(see below)* |
| Categories | `optimization`, `vanilla-like`, `multiplayer` |
| Environments | Client: **required** · Server: **unsupported** |
| License | Decision — see "License" below |
| Source / Issues | Link `github.com/slashdaemon/TBS-client` only if that repo is public |

### Summary (one sentence, ≤256 chars)

> An optional client-side modpack for Minecraft 26.1.2 that improves performance,
> visuals, audio, and quality-of-life without adding any gameplay content — so it
> works on any vanilla server.

### Description (paste into the Modrinth body)

```markdown
# TheBlockSurvival

**An optional client-side polish pack for vanilla-friendly Minecraft 26.1.2.**

TheBlockSurvival sharpens performance, lighting, audio, and quality-of-life for
long survival sessions — without touching a single gameplay mechanic. Every mod
is client-side or vanilla-protocol-safe, so the pack works on **any** vanilla
26.1.2 server. It is the companion client pack for *The Block Survival*, but
needs no special server to be worth installing.

## What's inside

- **Performance** — Sodium, Lithium, Krypton, FerriteCore, ImmediatelyFast,
  BadOptimizations, EntityCulling. More frames, smoother, on the same hardware.
- **Render distance & detail** — Voxy extended render distance, connected
  textures, Entity Model & Texture Features, subtle particles and ambience.
- **Camera, controls & animation** — Zoomify, Camera Utils, smooth item
  swapping, first-person body, 3D skin layers, Not Enough Animations.
- **HUD & quality-of-life** — JEI recipe search, WTHIT block tooltips,
  AppleSkin, BetterF3, Mod Menu, Controlling, Mouse Wheelie, and more.
- **Multiplayer** — StreamCraft Live (in-world video, screen share, and voice),
  optional per player and active only on servers that support it.

## Visual layer

**Complementary Shaders – Reimagined is on by default** for a dialed-in look out
of the box (switch to BSL or turn shaders off in the shader menu for more
performance), plus optional toggles chosen at import:

- Complementary Shaders – Reimagined (default)
- BSL Shaders (alternative)
- Patrix 32x — labPBR resource pack (optional toggle)
- Fresh Animations (+ Emissive, + Extensions)

## Vanilla-safe by design

No new blocks, items, mobs, or world generation. You get the **same game** as a
stock vanilla client — rendered better and easier to play — and you can join any
vanilla 26.1.2 server with it.

## Install

Import the `.mrpack` with **Prism Launcher** or the **Modrinth App**.

> **macOS / Linux:** StreamCraft Live ships per-platform native libraries; this
> pack references the Windows build. On macOS or Linux, download the matching
> per-OS `.mrpack` from the pack's
> [GitHub releases](https://github.com/slashdaemon/TBS-client/releases) instead
> (Modrinth hosts only the Windows build).

## Credits

Built with [packwiz](https://packwiz.infra.link/). Every mod, shader, and
resource pack is the work of its respective author — please support them.
```

### License

Modrinth requires a license on the project. The choice applies to **the pack's
own work** — the packwiz curation and metadata — not the bundled mods, which keep
their own licenses. Recommended: **All Rights Reserved**, the usual choice for a
modpack (it protects the curation without affecting how players use the pack).
Pick a permissive license instead only if re-packaging of the curation should be
allowed.

## One-time: credentials

Copy `.env.example` → `.env` (gitignored) and fill in:

- `MODRINTH_TOKEN` — PAT with the "Create version" scope, from
  <https://modrinth.com/settings/pats>
- `MODRINTH_PROJECT` — `theblocksurvival` (or the project ID)

---

## License compliance

**Audit — 2026-05-22, pack v1.1.2.** A Modrinth `.mrpack` URL-references mods
sourced from Modrinth and **bundles** mods sourced from CurseForge as override
jars. Bundling is redistribution, so every bundled mod must permit it.

- All ~23 currently-bundled (CurseForge-sourced) mods are permissively licensed
  (MIT / LGPL-3.0 / GPL-3.0 / Apache-2.0 / Unlicense) — redistribution allowed.
- Mods with restrictive licenses are **URL references**, not bundled, so their
  licenses do not gate the pack: Camera Utils (All-Rights-Reserved),
  Crash Assistant (custom), WTHIT (CC-BY-NC-SA) — all re-sourced from Modrinth
  in v1.1.2 for exactly this reason — plus the optional Patrix 32x (ARR) and
  Complementary (custom) visual packs.

**When adding a mod:** if it is CurseForge-sourced it will be bundled — confirm
its license permits modpack redistribution, or re-source it from Modrinth so it
becomes a URL reference instead.

**Update — 2026-07-12, pack v1.3.0.** Modrinth rejected the pack for "Excessive
Modpack Overrides" — 29 mods had drifted to CurseForge-canonical (against the
design above) and were riding as override jars, and three shaderpacks were
bundled as raw zips. All are now Modrinth-canonical URL references (same jars,
matched by sha1). The only remaining content override is
`resourcepacks/VanillaTweaks.zip` (not on Modrinth; generated at
vanillatweaks.net and credited per their terms, which permit inclusion in
modpacks with credit). **Keep it that way: every new mod is `mr install` first
here** — add a `scripts/cf-sources/mods/` swap if it should ride as a CF
reference in the CurseForge zip.

---

## CurseForge

### The CurseForge build differs from Modrinth — by design

A packwiz pack has one source per mod. The **canonical pack is
Modrinth-sourced**, which keeps the Modrinth build clean. For the CurseForge
build, `publish.py` applies two per-platform transformations at export time
(and restores the canonical state afterward, even on failure):

1. **Exclude** — five pack entries cannot ride along in the CurseForge package:

   | Entry | Why |
   |-------|-----|
   | `mods/voxy.pw.toml` | CurseForge does not permit Voxy in modpacks |
   | `shaderpacks/complementary-reimagined.pw.toml` | custom license, install separately |
   | `resourcepacks/fresh-animations.pw.toml` | custom "see terms" license |
   | `resourcepacks/fresh-animations-emissive.pw.toml` | ARR; rides with main FA |
   | `resourcepacks/fresh-animations-extensions.pw.toml` | ARR; rides with main FA |

   The list lives in `CURSEFORGE_EXCLUDED` at the top of `scripts/publish.py`.
   `publish.py` also appends a note to the CurseForge release changelog telling
   players what's missing and to install each separately. The **Modrinth** build
   keeps everything.

2. **Swap** — Modrinth-sourced mods that ARE referenceable on CurseForge get
   their `.pw.toml` temporarily replaced with a CurseForge-sourced equivalent so
   the CF manifest carries a proper project reference (instead of a bundled
   override). The CF metafiles live in **`scripts/cf-sources/`**, mirroring the
   pack's directory layout. There are currently 23 swap entries (19 mods,
   Patrix 32x, and the BSL / Photon / Solas shaderpacks).

After both transforms the Windows CF zip ends up with 50 manifest references and
**one** content override: `resourcepacks/VanillaTweaks.zip` (not a CurseForge
project — generated at vanillatweaks.net, credited in `credits.txt`). The rest of
`overrides/` is pack config and docs, which is what overrides are for.

**CurseForge rejection, 2026-07-25 (v1.4.0):** "The following files belong to
CurseForge-hosted projects, and should therefore not be added directly to zip
files" — `zoomify-2.16.0+26.1.jar` and `blur-fabric-6.2.0+26.1.jar`. Both had no
cf-source swap, so they rode as override jars. Fixed by adding swaps for both
(CF slug for Blur+ is **`blur-fabric`**, not `blur-plus`; CF ships 6.3.0 where
Modrinth pins 6.2.0, so this one entry drifts a patch release between builds) and,
pre-emptively, for the three bundled shaderpacks (BSL, Photon, Solas — CF has the
exact same filenames). **The rule is generic: anything in `overrides/` that is a
CurseForge-hosted project will be rejected**, so audit the exported zip before
every CF upload:

```bash
python -c "import zipfile;z=zipfile.ZipFile('dist/TheBlockSurvival-pc-<ver>.zip');\
print([n for n in z.namelist() if n.startswith('overrides/') and n.lower().endswith(('.jar','.zip'))])"
```

**Unsolvable case — the per-OS variant zips.** The four non-Windows CF files each
carry `mods/streamcraft-<ver>-<os>.jar` as an override. StreamCraft Live *is* a
CurseForge project (1451729), but the per-OS jars are **additional files** hanging
off the primary version, and CurseForge's public file list exposes only the primary
per (MC, loader) pair — there is no referenceable project/file pair for them. So
either the variants ship that one override (we are its author, so redistribution
permission is not in question) or CurseForge carries the Windows zip only, with
Mac/Linux players sent to GitHub releases exactly as on Modrinth.

**Decision (2026-07-25): keep all five files and explain the override.** The CF
release changelog now carries an "About the macOS / Linux downloads" section
(`CURSEFORGE_EXCLUSION_NOTE` in `scripts/publish.py`) stating why that one jar is
bundled, so every future upload explains itself to the reviewer without a separate
message. If a reviewer rejects it anyway, the fallback is Windows-only on
CurseForge.

### Maintaining `scripts/cf-sources/` when mods update

If you update or add a mod and want it referenced (not bundled) on CurseForge:

```bash
cd TBS-client
mkdir -p scripts/_mr_backup && cp -r mods resourcepacks shaderpacks scripts/_mr_backup/
./packwiz.exe cf install <slug> -y          # may create a different filename
cp <the-new-or-overwritten-cf-pw.toml> scripts/cf-sources/<original-relative-path>
rm -rf mods resourcepacks shaderpacks       # restore the canonical Modrinth state
cp -r scripts/_mr_backup/mods scripts/_mr_backup/resourcepacks scripts/_mr_backup/shaderpacks ./
rm -rf scripts/_mr_backup
./packwiz.exe refresh
```

If `cf install` creates a different-named metafile (e.g. `ferritecore-fabric.pw.toml`
when the canonical is `ferrite-core.pw.toml`), **rename the saved cf-source file
to match the canonical name** — the swap is path-for-path.

### CurseForge project description (paste into the CurseForge body)

The CurseForge build differs from the Prism build (Distant Horizons instead of Voxy, no
Fresh Animations, everything installed with defaults instead of import toggles), so it has
its own description. Updated for 2.0.0 (2026-10-05). `publish.py` does not set it; paste it
into the project's description on CurseForge by hand.

```markdown
# TheBlockSurvival

**An optional client-side polish pack for vanilla-friendly Minecraft 26.2.**

TheBlockSurvival sharpens performance, lighting, audio and quality of life for long survival sessions, without touching a single gameplay mechanic. Every mod is client-side and safe on a vanilla server, so the pack works on **any** vanilla 26.2 server. It's the companion client pack for *The Block Survival*, but it's worth installing without a special server too.

## Play on The Block Survival

The pack's home server is **The Block Survival**, a vanilla-friendly 26.2 survival SMP at `theblocksurvival.com`. It's already in your server list after a fresh install. Bedrock players can join too.

## What's inside

- **Performance** — Sodium, Lithium, Krypton, FerriteCore, ImmediatelyFast, BadOptimizations, EntityCulling.
- **Far terrain** — Distant Horizons draws the world far past your render distance.
- **Render detail** — Iris shaders, connected textures, Entity Model & Texture Features, falling leaves, subtle particles, Sound Physics Remastered and AmbientSounds.
- **Camera, controls & animation** — Zoomify, Camera Utils, smooth item swapping, first-person body, 3D skin layers, Not Enough Animations, Bridging Mod.
- **HUD & quality of life** — JEI recipe search, WTHIT block tooltips, AppleSkin, BetterF3, Xaero's Minimap and World Map, Open Parties and Claims, Mod Menu, Controlling, and more.
- **Multiplayer** — StreamCraft Live (in-world video, screen share and voice) and SlashRails (smooth curved rails). Both are optional per player and only do anything on servers that run them.

## Set up on first launch

A fresh install starts dialed in:

- **Complementary Shaders – Reimagined** is on, with **BSL** included as a lighter alternative. You can switch either off in the shader menu.
- **Resource packs on by default:** Vanilla Tweaks, Dramatic Skys custom skies, 3D lanterns, rails and ladders, the Unique Dark GUI, Icons, and Gentler Weather Sounds.
- **Patrix 32x** (labPBR) is included but off by default; turn it on in Resource Packs.
- **OpenGL** is the graphics backend. 26.2's Vulkan mode crashes with shaders.

Your own changes are never overwritten when the pack updates.

## Vanilla-safe by design

No new blocks, items, mobs or world generation. You get the **same game** as a stock vanilla client, rendered better and easier to play, and you can join any vanilla 26.2 server with it.

## Credits

Built with [packwiz](https://packwiz.infra.link/). Every mod, shader and resource pack is the work of its respective author. Please support them.
```

### Credentials and submission

Set `CURSEFORGE_TOKEN` (from <https://authors-old.curseforge.com/account/api-tokens>)
and `CURSEFORGE_PROJECT_ID` (numeric ID from the CF project dashboard) in `.env`.
Then `python scripts/publish.py --platform curseforge` exports + uploads.

> **One-time before the first CurseForge release: re-test on LocalServer.** Your
> `CLAUDE.md` requires testing untested version sets. A handful of swapped mods
> may pick a CurseForge version that differs slightly from the Modrinth-pinned
> one — most won't drift, but validate before submitting.
