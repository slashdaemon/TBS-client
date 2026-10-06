# TBS-Client

**The Block Survival — Client modpack**

Fabric modpack for **Minecraft 26.2**, built with [packwiz](https://packwiz.infra.link/).

TBS-Client is **purely optional polish** — it is never required to play on The Block Survival.
Any player on stock vanilla 26.2 gets the full gameplay experience: same world, items, shops,
and progression. The server sends one small resource pack for its terrain slabs, which every
player accepts on join; that is the only requirement. This pack exists for players who want to
dial in visual fidelity, performance, and quality-of-life for long survival sessions.

Every mod here is safe against a vanilla server. Two mods — **StreamCraft Live** and
**SlashRails** — are shared with TBS-Server; both are optional per player, so a vanilla client
without them still connects and plays the full game (see the cross-side contract in
`docs/TBS-mod-strategy.md`). With SlashRails installed you see smoothed rail runs as curved track.

## Install

| Launcher | How |
|----------|-----|
| Prism Launcher | Import the `TheBlockSurvival-X.Y.Z.mrpack` release file |
| CurseForge App | Import the exported `.zip` |

## Build / maintenance

```bash
./packwiz.exe mr install <mod-slug> -y   # add a mod — MODRINTH FIRST in this pack
./packwiz.exe cf install <mod-slug> -y   # only when the mod isn't on Modrinth
./packwiz.exe update --all               # update every mod
./packwiz.exe refresh                     # rebuild index.toml after manual edits
python scripts/publish.py --platform both --variant all --dry-run   # build every variant locally
```

This pack is Modrinth-sourced (CurseForge-sourced entries would ride as bundled override jars).
CurseForge distribution uses the swaps in `scripts/cf-sources/`, applied by `scripts/publish.py`.
See `CLAUDE.md` and `PUBLISHING.md`.

## Mod tiers

Mods follow the five-tier layout from the strategy doc. See `CHANGELOG.md` for the exact
resolved state of every mod, and `docs/TBS-mod-strategy.md` for the full design rationale.

- **Tier 1 — Foundation:** Fabric API, Sodium, Iris Shaders, Lithium, FerriteCore,
  ImmediatelyFast, BadOptimizations, EntityCulling, Krypton
  (libs: Forge Config API Port, Default Options + Balm, Fabric Language Kotlin, CreativeCore,
  Fzzy Config, Text Placeholder API, bad packets)
- **Tier 2 — Visual range & quality:** Voxy, Continuity, ETF + EMF, Falling Leaves,
  Visuality, Subtle Effects, Sound Physics Remastered, AmbientSounds, Nuit + Nuit Interop
  (custom skyboxes, for Dramatic Skys)
- **Tier 3 — Camera, controls, animations:** Camera Utils, Zoomify, Not Enough Animations,
  First-person Model, 3D Skin Layers, Smooth Swapping, Bridging Mod
- **Tier 4 — HUD, UI, utility:** BetterF3, Mod Menu, Cloth Config + YACL, AppleSkin, WTHIT,
  JEI, Searchables, Paginated Advancements, Controlling, Status Effect Bars,
  Crash Assistant, Blur+, Open Parties and Claims (claim/party UI + Xaero map overlay;
  menu key defaults to `;`), Xaero's Minimap + Xaero's World Map (entity radar + cave
  maps off by default)
- **Tier 5 — Cross-side:** StreamCraft Live, SlashRails

## Resource packs & shader

Every resource pack and shader is a Modrinth-linked pack entry (never bundled), except the
curated Vanilla Tweaks zip. Default Options turns the selection below on for a **fresh install
only**; a player's later changes are never overwritten, and an existing install has to enable new
packs by hand.

**On by default** (load order bottom to top; the last entry wins):

1. Vanilla Tweaks (curated, bundled): Clearer Water, Borderless Glass, Variated
   Logs/Bookshelves/Cobblestone/Planks, Ore Borders, Brighter Nether, Lower Fire/Shield. Rebuilt
   for 26.2. See `credits.txt`.
2. Fresh Animations, then Fresh Animations: Extensions (which include Emissive).
3. Fresh Animations add-ons: Fresh Skeleton Physics, AL's Skeletons / Enderman / Creepers
   Revamped, FA: Player Extension.
4. 3D models: Better Lanterns, RAY's 3D Rails, RAY's 3D Ladders, MB-3D Items.
5. Enchantment Outlines.
6. GUI: Unique Dark (Lite), Clearer Slot Highlight.
7. Sound: Gentler Weather Sounds.
8. Sky: Dramatic Skys (the free Demo build, All Rights Reserved; the author allows linking).
   Needs Nuit, which the pack includes.
9. Icons, at the top.

**Optional, off by default:** **Patrix 32x** (32x labPBR). It stays off because SlashSlabs' grass
slabs are 16x textures from the server pack, which outranks any client pack, so they look flat
next to Patrix's 32x grass under every shader (checked 2026-10-05).

**Shaders:** **Complementary Reimagined r5.9.3** is selected and enabled on first launch. BSL
10.1.8 ships as an alternative. Photon and Solas were removed in 2.0.0 (Photon has no 26.2 build;
Solas 3.7b renders broken on 26.2). Turn
shaders off in **Options → Video Settings → Shader Packs** for a lighter client; the choice
sticks. With Complementary and Patrix, open **Shader Options → RP Support → labPBR** for POM and
reflections.

**Other first-launch defaults** (all seeded by Default Options, all freely changeable):
render distance **32**, simulation distance **32**, GUI scale **3×**, Ambient/Environment
sound volume **20%**, **Xaero's minimap hidden** (press **`K`** to toggle it on), and the
**OpenGL** graphics backend. 26.2's Vulkan backend crashes this pack (Iris is OpenGL-only); a
player who switches to Vulkan in Video Settings will hit that crash.

**Performance:** the full stack (shader + Fresh Animations + Voxy) targets roughly an
RTX 3060 / 8 GB-VRAM-class machine at ~60 FPS / 1080p. On weaker hardware, switch to BSL, drop
the shader to a lower preset, or turn it off.

## Pending mods

These mods aren't in the pack yet:

- **Auto HUD** — hide HUD on demand. Has a 26.2 build; not added yet.
- **Mouse Wheelie** — removed in 2.0.0 until the fix for its non-daemon thread ships
  (mouse-wheelie#291 / PR #292); it blocked clean exit.
- **Drip Sounds** — cave drip audio. Not found on Modrinth under that name.
- **InvMove** — walk while inventory is open. Not yet checked for 26.2.

Dropped in 2.0.0 (no 26.x builds): ModernFix, Better Third Person, Eating Animation.

**Far terrain differs by build:** the Prism/`.mrpack` build uses **Voxy**; the CurseForge build
uses **Distant Horizons** instead, because Voxy isn't on CurseForge. The CurseForge build also
leaves out Fresh Animations and its add-ons and four packs with no 26.2 file on CurseForge (see
`CHANGELOG.md`).

`Voxy World Gen V2` from the doc is not a separate client mod — Voxy's V2 world generation is a
setting inside Voxy's own config, enabled in-game.

## Version coupling

TBS-Client and TBS-Server ship in **lockstep** (since v1.1.7) — every bump to either pack
is a synchronized bump of both, same version number. The mod whose jar version must match
across both packs are **StreamCraft Live** and **SlashRails**.
