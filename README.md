# TBS-Client

**The Block Survival — Client modpack**

Fabric 1.x modpack for **Minecraft 26.1.2**, built with [packwiz](https://packwiz.infra.link/).

TBS-Client is **purely optional polish** — it is never required to play on The Block Survival.
Any player on stock vanilla 26.1.2 (+ StreamCraft) gets the full gameplay experience: same
world, items, shops, mail, and progression. This pack exists for players who want to dial in
visual fidelity, performance, and quality-of-life for long survival sessions.

Every mod here is safe against a vanilla server. Two mods — **StreamCraft Live** and
**SlashRails** — are shared with TBS-Server; both are optional per player, so a vanilla client without them still
connects and plays the full game (see the cross-side contract in
`docs/TBS-mod-strategy.md`).

## Install

| Launcher | How |
|----------|-----|
| Prism Launcher | Import the `TheBlockSurvival-X.Y.Z.mrpack` release file |
| CurseForge App | Import the exported `.zip` |

## Build / maintenance

```bash
./packwiz.exe cf install <mod-slug> -y   # add a mod from CurseForge (preferred)
./packwiz.exe mr install <mod-slug> -y   # Modrinth fallback (no CF 26.1.2 build)
./packwiz.exe update --all               # update every mod
./packwiz.exe refresh                     # rebuild index.toml after manual edits
./packwiz.exe modrinth export             # produce TBS-Client-X.Y.Z.mrpack
```

CurseForge is always tried first to stay compliant with the CurseForge distribution policy;
Modrinth is used only when a mod has no CurseForge build for 26.1.2.

## Mod tiers

Mods follow the five-tier layout from the strategy doc. See `CHANGELOG.md` for the exact
resolved state of every mod, and `docs/TBS-mod-strategy.md` for the full design rationale.

- **Tier 1 — Foundation:** Fabric API, Sodium, Iris Shaders, Lithium, FerriteCore,
  ImmediatelyFast, BadOptimizations, EntityCulling, Krypton
  (libs: Forge Config API Port, Default Options + Balm)
- **Tier 2 — Visual range & quality:** Voxy, Continuity, ETF + EMF, Falling Leaves,
  Visuality, Subtle Effects, Sound Physics Remastered, AmbientSounds
- **Tier 3 — Camera, controls, animations:** Camera Utils, Zoomify, Not Enough Animations,
  First-person Model, Skin Layers 3D, Smooth Swapping, Bridging Mod
- **Tier 4 — HUD, UI, utility:** BetterF3, Mod Menu, Cloth Config + YACL, AppleSkin, WTHIT,
  JEI, Paginated Advancements, Controlling, Status Effect Bars,
  Crash Assistant, Blur+, Open Parties and Claims (claim/party UI + Xaero map overlay;
  menu key defaults to `;`), Xaero's Minimap + Xaero's World Map (entity radar + cave
  maps off by default)
- **Tier 5 — Cross-side:** StreamCraft Live, SlashRails

## Resource packs & shader

TBS-Client also ships an **optional visual layer** — a shader plus a set of resource
packs — as packwiz *optional* entries (`[option] optional = true`). They are embedded in
the exported `.mrpack` only as Modrinth URL references, and appear as per-player toggles
when you import the pack in Prism Launcher or the CurseForge App. None of it is required;
leave it all off for a lighter client. See `docs/resource-packs.md` for the full rationale.

| Pack | Default | Notes |
|------|---------|-------|
| Complementary Shaders - Reimagined `r5.8` | off | Iris shader. After enabling, open **Shader Options → RP Support → labPBR** to unlock POM and the PBR pack's reflections. |
| Patrix 32x | off | 32x labPBR resource pack — adds PBR depth under the shader. |
| Fresh Animations `v1.10.5` | on | Smooth entity animations. Driven by the bundled **EMF + ETF**. |
| Fresh Animations: Emissive | on | Restores Fresh Animations glowing-eye textures under shaders. |
| Fresh Animations: Extensions | on | Extra Fresh Animations models (Classic Horses, Objects). |
| Vanilla Tweaks (curated) | on | 10 vanilla-friendly tweaks — Clearer Water, Borderless Glass, Variated Logs/Bookshelves/Cobblestone/Planks, Ore Borders, Brighter Nether, Lower Fire/Shield. **Bundled** (committed zip, not a per-player toggle); pure-vanilla textures, needs no extra mod. See `credits.txt`. |

**In-game resource-pack load order** (top wins, top → bottom):

1. Fresh Animations: Emissive
2. Fresh Animations: Extensions
3. Fresh Animations
4. Vanilla Tweaks (curated)
5. Patrix 32x

The Fresh Animations packs sit above both Vanilla Tweaks and Patrix so FA's entity models
take priority; the block-level texture packs apply underneath (FA and Vanilla Tweaks don't
overlap — one is entities, the other is blocks). The on-by-default selection is applied on
first launch by the **Default Options** mod (`config/defaultoptions/options.txt` →
`resourcePacks`); a player's later changes are never overwritten on update.

The shader is selected separately in the Iris menu, not the resource-pack list — but as of
1.2.3 **BSL Shaders v10.1.3** is pre-selected and enabled on first launch (seeded via
`config/defaultoptions/extra/config/iris.properties`). Turn it off in **Options → Video
Settings → Shader Packs** for a lighter client; the choice sticks. Complementary
Reimagined, Solas, and Photon also ship as alternatives. As of 1.3.0 all four shaders are
Modrinth-referenced pack entries (no bundled zips) — Solas installs as
`Solas Shader V3.7.zip`, its upstream filename. As of 1.3.1 all four packs are pinned to
builds that list MC 26.1.2 support (BSL 10.1.3, Photon v1.3b, Solas 3.7, Complementary
r5.8 — the 1.3.0 pins for the first three predated 26.1 support and broke under 26.1.2).

**Other first-launch defaults** (all seeded by Default Options, all freely changeable):
render distance **32**, simulation distance **32**, GUI scale **3×**, Ambient/Environment
sound volume **20%**, and **Xaero's minimap hidden** (press **`K`** to toggle it on).

**Performance:** the full stack (shader + Patrix + Fresh Animations) targets roughly an
RTX 3060 / 8 GB-VRAM-class machine at ~60 FPS / 1080p. On weaker hardware, drop
Complementary to a lower preset or leave the shader and PBR pack off.

## Pending mods

These mods from the strategy doc have **no 26.1.2 build** on CurseForge or Modrinth yet and
will be added once builds appear:

- **ModernFix** — load-time / memory fixes
- **Drip Sounds** — cave drip audio
- **Better Third Person** — third-person camera angles
- **Eating Animation** — visual eating
- **InvMove** — walk while inventory is open
- **Auto HUD** — hide HUD on demand
- **Mouse Wheelie** — removed in 2.0.0 until the fix for its non-daemon thread ships (mouse-wheelie#291 / PR #292); it blocked clean exit

`Voxy World Gen V2` from the doc is not a separate project — Voxy's V2 world generation is a
setting inside Voxy's own config, enabled in-game.

## Version coupling

TBS-Client and TBS-Server ship in **lockstep** (since v1.1.7) — every bump to either pack
is a synchronized bump of both, same version number. The mod whose jar version must match
across both packs is **StreamCraft Live**.
