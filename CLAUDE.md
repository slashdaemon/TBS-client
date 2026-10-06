# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> Read the parent `TBS/CLAUDE.md` too — it covers the two-pack architecture, the
> vanilla-client contract, `server-config.py`, and the shared CurseForge-first policy.
> This file only covers what is specific to **TBS-Client**.

## What this repo is

TBS-Client is a **packwiz modpack** — there is no application code, no build system, no
tests. The repo is a tree of TOML metadata: `pack.toml` (pack manifest), `index.toml`
(file index with hashes), and one `mods/<slug>.pw.toml` per mod. Each `.pw.toml` names a
mod, its target `side`, and a `[download]` URL + hash plus an `[update]` block pointing at
the CurseForge or Modrinth project. `packwiz.exe` resolves these into a distributable
`.mrpack`. "Working on the codebase" here means editing pack metadata, not writing code.

This is its **own git repo**, versioned independently from `TBS-server/` and the TBS root.
Commit pack changes here, inside `TBS-client/`.

## The hard constraint: client-side-only

Every mod in this pack must be **client-side-only and safe against a vanilla server** — it
must run when the player connects to a stock vanilla 26.2 server (which TBS's base server
effectively is). Concretely:

- No content mods, no worldgen/structure/mob mods, no mod that needs a server companion.
- The `side` field in each `.pw.toml` should be `client` for every mod **except
  StreamCraft Live and SlashRails**, which are `side = "both"` — the two mods shared with
  TBS-Server.
- Before adding any mod, confirm it is client-only. See the exclusion lists in
  `docs/TBS-mod-strategy.md`.

StreamCraft Live's and SlashRails' jar versions must stay **identical** to the TBS-Server
copies. Bumping either is a synchronized release of both packs; do not bump it here alone.
SlashRails is pinned from CurseForge in both packs (TBS distributes on CurseForge only) and has
no per-OS overlays. Every other mod's
version is independent of TBS-Server.

## Mod organization

Mods follow a five-tier scheme (Foundation → Visual range/quality → Camera/controls/
animations → HUD/UI/utility → Cross-side). The tiers are documentation only — they live in
`README.md` and `CHANGELOG.md`, not in the pack metadata. `mods/` is a flat directory.

Mods with no 26.2 build yet are tracked under "Pending mods" in `README.md` and
"Not yet included" in `CHANGELOG.md` — add them when builds appear, don't silently drop them.

## Commands

```bash
./packwiz.exe mr install <slug> -y    # add a mod — MODRINTH FIRST in this pack (see below)
./packwiz.exe cf install <slug> -y    # only when the mod genuinely isn't on Modrinth
./packwiz.exe update --all            # update every mod
./packwiz.exe refresh                 # rebuild index.toml hashes after ANY manual edit
./packwiz.exe modrinth export         # produce TheBlockSurvival-X.Y.Z.mrpack
```

**⚠️ This pack inverts the Projects-wide CurseForge-first rule.** The canonical
pack must be **Modrinth-sourced**: `packwiz modrinth export` bundles every
CF-sourced entry as an override jar, and Modrinth **rejected the pack** for
excessive overrides (2026-06, fixed in v1.3.0). CurseForge compliance is handled
separately — `scripts/publish.py` swaps in CF-sourced metafiles from
`scripts/cf-sources/mods/` when building the CurseForge `.zip`. To keep a mod
CF-referenced on CurseForge, add/refresh its swap file there (and mind the
stale-swap guard). See `PUBLISHING.md`.

`index.toml` tracks `README.md`, `CHANGELOG.md`, and `docs/` alongside the `.pw.toml`
files — so editing any of those by hand requires a `refresh` afterward to fix the index
and `pack.toml` hashes. The pack targets MC 26.2 (since 2.0.0); only mods tagged for 26.2 are
safe to assume work.

## Adding or changing a mod — full checklist

1. `./packwiz.exe mr install <slug> -y` (Modrinth first — see the sourcing warning
   above; CurseForge only if the mod isn't on Modrinth, and then confirm its license
   permits bundling since it will ride as an override jar).
2. Verify the mod is client-side-only and the new `.pw.toml` has `side = "client"`.
3. If switching a mod Modrinth↔CurseForge, delete the old `.pw.toml` first — packwiz
   writes a fresh file and the stale one will linger.
4. Bump `version` in `pack.toml` (semver: patch for mod add/fix, minor for larger changes).
5. Update `CHANGELOG.md` (new version entry, dated) and `README.md` (tier list, mod count,
   pending-mods list).
6. `./packwiz.exe refresh`, then `./packwiz.exe modrinth export`.
7. Commit inside this repo.

`packwiz modrinth export` **aborts** if a mod's CurseForge file forbids third-party API
distribution (error mentions "manual download"). Fix: re-source that mod from Modrinth —
delete its `.pw.toml`, `mr install` it — so the `.mrpack` can embed it by URL.

## The two builds differ (remember this)

- **Far terrain:** the Prism/`.mrpack` build ships **Voxy**; the CurseForge `.zip` ships
  **Distant Horizons** (`scripts/cf-extra/mods/distant-horizons.pw.toml`), because Voxy isn't on
  CurseForge. Never ship both in one build.
- **CurseForge leaves out** (`CURSEFORGE_EXCLUDED` in `scripts/publish.py`): Voxy, Fresh
  Animations and its add-ons, and resource packs with no 26.2 file on CurseForge.
- **Every CurseForge swap must be the Prism build's exact file** (and the server's exact file for
  cross-side mods); `publish.py` refuses stale, orphan or server-mismatched swaps.

## Distribution

TBS-Client is published as a `.mrpack` (and exported `.zip`) for players to import into
Prism Launcher or the CurseForge App. Unlike TBS-Server, it is **not** deployed by
`server-config.py` — that tool only touches the server pack.
