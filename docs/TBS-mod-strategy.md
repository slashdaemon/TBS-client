# The Block Survival — Mod Strategy

**Document version:** v1.0 (draft)
**Last updated:** 2026-05-17
**Target Minecraft version:** 26.1.2 / Fabric

## Architecture

The Block Survival ships **two independently-versioned modpacks** that augment a vanilla 26.1.2 server:

| Pack | Runs on | Purpose |
|------|---------|---------|
| **TBS-Client** | Player machines | Visuals, audio, UI, controls, optimization, render quality |
| **TBS-Server** | Game server | Admin tooling, performance, gameplay augments via vanilla protocol |

### Player experience principle

**TBS-Client is purely optional polish — never a requirement to play.**

The server is designed so a player with stock vanilla 26.1.2 (+ StreamCraft) gets the **full gameplay experience**: same world, same items, same shops, same mail, same custom features, same progression. Nothing is gated behind owning the client pack. A casual visitor, a streamer dropping in, or a friend who doesn't want a 200-mod install can join and play the same game as everyone else.

TBS-Client exists for **gamers who want to really game** — players who want to dial in their setup and squeeze every drop of fidelity, performance, and quality-of-life out of a long survival session:

- Want render distances measured in hundreds of chunks → install Voxy
- Want shaders, sound physics, particle polish → install the visuals tier
- Want third-person camera tuning, smooth animations, polished swapping → install the camera/controls tier
- Want HUD redesigns, recipe viewers, schematic build planners → install the UI/utility tier
- Want frame-perfect optimization on a marginal machine → install the perf tier alone

The server treats all three personas as first-class:

| Persona | Setup | Experience |
|---------|-------|------------|
| **Casual / first-time joiner** | Vanilla 26.1.2 + StreamCraft | Full gameplay, vanilla aesthetics, zero install friction |
| **Streamer / one-off visitor** | Vanilla 26.1.2 + StreamCraft | Same as above; viewers see vanilla — keeps stream broadly accessible |
| **Resident / serious player** | Vanilla 26.1.2 + TBS-Client + StreamCraft | Full gameplay + tuned rendering, audio, and QoL for long sessions |

No player tier sees less *content* than another. The difference is **how it looks and feels on your screen**, not what you can do in the world. A vanilla player and a fully-modded player can stand next to each other, trade items, share a base, and see the same Lootr chest contents — one just sees prettier trees and hears better cave audio.

### The cross-side contract

- The base server is **vanilla 26.1.2**.
- **StreamCraft Live and SlashRails are the only mods shipped on both sides** (SlashRails from 2.0.0). Each is in both packs at the same version, upgraded synchronously, and each is optional per player.
- No other mod appears in both packs. No mod requires both sides to function: SlashRails' server-only build lets vanilla clients join and ride its curves.
- Any client running stock vanilla 26.1.2 + StreamCraft can connect and play.
- Any server-side gameplay augment must be invisible to vanilla clients at the protocol level — see Polymer below.

### How server augments stay vanilla-client-safe

For TBS-Server to add features without breaking the vanilla-client contract, every server mod must satisfy one of two conditions:

1. **Adds no new client-visible content** — modifies how vanilla mechanics behave (sleep voting, tree-felling, anvil costs, villager trade restocking) without introducing new blocks / items / entities / sounds / packets the client doesn't already know about. **Every TBS-Server v1.0 gameplay mod takes this path.**
2. **Translates new content into vanilla packets** — uses a library like **Polymer** (Patbox) to spoof custom items as vanilla items with `CustomModelData` NBT, custom GUIs as standard chest UIs, and custom blocks as `block_display` entities. TBS-Server v1.0 ships no mods of this kind. Polymer remains an option for future expansion (custom shops, mail systems, custom items) without breaking the vanilla-client contract.

---

## TBS-Client modpack

**Goal:** maximize visual polish, performance, and quality-of-life when joining TBS. Every mod below is purely client-side and safe against a vanilla server.

### Tier 1 — Foundation (install first)
- **Fabric API** — universal dependency
- **Sodium** — rendering optimizer
- **Iris Shaders** — shader loader
- **Lithium** — game-logic perf (client-safe)
- **FerriteCore** — memory dedup
- **ModernFix** — load-time / memory fixes
- **ImmediatelyFast** — HUD / GUI render perf
- **BadOptimizations** — misc perf
- **EntityCulling** — render culling
- **Krypton** — network stack perf

### Tier 2 — Visual range & quality
- **Voxy** + **Voxy World Gen V2** — far-LOD rendering for huge perceived render distance, purely client-side
- **Continuity** — connected textures (pair with a CTM resource pack)
- **Entity Texture Features (ETF)** + **Entity Model Features (EMF)** — pairs with Fresh Animations and custom entity textures
- **Falling Leaves** — visual leaf particles
- **Visuality** + **Subtle Effects** — vanilla particle polish
- **Sound Physics Remastered** — reverb / occlusion DSP
- **AmbientSounds** *or* **Atmosfera** — pick one biome-ambience mod
- **Drip Sounds** — cave drip audio

### Tier 3 — Camera, controls, animations
- **Better Third Person** — third-person camera angles
- **Camera Utils** — free cam, smooth movements
- **Zoomify** — zoom keybind
- **Not Enough Animations** — third-person animation overhaul
- **First-person Model** — render arms / body in first person
- **Eating Animation** — visual eating
- **Skin Layers 3D** — 3D layer rendering on player skins
- **Smooth Swapping** — inventory slot-slide animations

### Tier 4 — HUD, UI, utility
- **BetterF3** — F3 redesign
- **Mod Menu** — required to access mod configs
- **Cloth Config API** + **YACL** — config GUI dependencies
- **AppleSkin** — food info overlay
- **WTHIT** — look-at tooltip (uses vanilla data only)
- **JEI** *or* **REI** — recipe viewer (vanilla recipes only — pick one)
- **Paginated Advancements** — better advancement screen
- **Mouse Wheelie** — scroll-through inventory features (client subset)
- **Controlling** — keybind search GUI
- **Status Effect Bars** — visual potion timers
- **Crash Assistant** — better crash dialog
- **Blur+** — menu background blur
- **InvMove** — walk while inventory is open
- **Auto HUD** — hide HUD on demand

### Tier 5 — Cross-side
- **StreamCraft Live** — required on both client and server. Same jar version as the server pack.
- **SlashRails** — draws smoothed rail runs as curved track. Same jar version as the server pack; optional (without it, curves ride smoothly but look like vanilla rails).

### Explicitly excluded from TBS-Client
- Any content mod that adds blocks / items / entities (Macaw's, Supplementaries, Farmer's Delight, etc.) — would desync with a vanilla server
- Worldgen / structure / mob mods
- Distant Horizons (Voxy is the chosen LOD solution instead)
- Simple Voice Chat (requires server companion; out of scope unless the StreamCraft-only constraint is relaxed — was shipped cross-side v1.0.1–1.1.12, removed in v1.1.13 as voice consolidates into StreamCraft)
- Movement-modifying mods (Do a Barrel Roll, Better Climbing, Accurate Block Placement Reborn) — may trigger server anti-cheat or get rejected
- Any mod that requires server-side install to function (Carry On, Trinkets, AxiomTool, Effortless, FallingTree client variant, WorldEdit, etc.)

---

## TBS-Server modpack

**Goal:** make the server fast, observable, well-administered, and gameplay-rich while staying joinable by any vanilla 26.1.2 client (with only StreamCraft installed).

### Tier S1 — Performance core
- **Fabric API** — universal dep
- **Lithium** — server game-logic / AI / pathfinding perf
- **Krypton** — network packet stack perf
- **FerriteCore** — memory dedup
- **Noisium** — worldgen chunk perf
- **C2ME** — concurrent chunk management
- **ModernFix** *(server build)* — load-time / memory fixes
- **Chunky** — admin tool for pre-generating chunks

### Tier S2 — Observability & operations
- **Spark** — profiler (`/spark profiler start`, heap summaries)
- **Connectivity** — keep-alive timeout adjustments, fixes timeout-disconnects
- **Advanced Backups** — differential world backups; configure retention
- **Ledger** — audit log of who broke / placed / took what, when
- **AutoWhitelist** — Discord-role-linked whitelist sync

### Tier S3 — Permissions & admin
- **LuckPerms** — permissions backbone
- **luckperms-placeholders** — group / prefix data for chat & UI
- **Essential Permissions** — permission node coverage for Fabric API events
- **Gamemode Unrestrictor** — `/gm` cross-world / per-player flexibility
- **WorldEdit** — region / schematic ops, restricted to admin role via LuckPerms

### Tier S4 — Communication
- **Text Placeholder API** — placeholder substitution lib (dep for Styled Chat)
- **Styled Chat** — per-role chat formatting, hover / click events, mentions
- **Fabricord** — two-way Discord ↔ in-game chat bridge

### Tier S5 — Gameplay augmentation (vanilla-packet-only)
- **Better Sleep** — percentage-based sleep voting
- **Lootr** — per-player loot views in vanilla container GUIs
- **FallingTree** *(server-side variant)* — break one log, whole tree falls
- **Saplanting** — sapling drops auto-plant on grass
- **Universal Bone Meal** — bone meal works on more vanilla blocks
- **Trade Cycling** — villager trade restock on right-click *(server-side variant)*
- **NoExpensive** — removes "Too Expensive" cap from anvils

### Tier S6 — Discoverability
- **BlueMap** — web-served live map of the world; standalone web service, no client jar needed

### Tier S7 — Cross-side
- **StreamCraft Live** — identical jar in both TBS-Server and TBS-Client packs
- **SlashRails** — identical jar in both packs. Server-only build: the Track Smoother turns rail staircases into smooth curves that vanilla minecarts ride; it reaches vanilla clients through Polymer.

### Explicitly excluded from TBS-Server
- All content mods that register new blocks / items / entities without Polymer (Macaw's, Supplementaries, Farmer's Delight, etc.) — would break vanilla-client joinability
- Worldgen / structure / mob mods that rely on client knowledge of new content (Incendium, Nullscape, Friends & Foes, etc.)
- All client-only mods (Sodium, Iris, ETF/EMF, etc.) — don't load on a dedicated server
- Simple Voice Chat — requires the SVC client mod, violating the StreamCraft-only contract (was shipped cross-side v1.0.1–1.1.12, removed in v1.1.13 as voice consolidates into StreamCraft)
- JourneyMap / Xaero's server companions — would require corresponding client install

### Server resource pack (optional)
TBS-Server v1.0 ships no mods that require a server-side resource pack. If we later add Polymer-based custom items or want branded textures, distribute via vanilla's `server-resource-pack` setting (bundled in the deployment archive or hosted at a stable CDN URL). Vanilla clients can decline without losing functionality.

---

## Distribution & deployment

Both packs follow the same packwiz → mrpack → GitHub release → mrpack4server pipeline:

```
TBS-Client/  → packwiz modrinth export → TBS-Client-X.Y.Z.mrpack → players' Prism Launcher / CurseForge App
TBS-Server/  → packwiz modrinth export → TBS-Server-X.Y.Z.mrpack → server host (mrpack4server)
```

### Version coupling
- **TBS-Client and TBS-Server versions are decoupled.** Bumping a client visual mod doesn't require a server restart, and vice versa.
- **The only mod whose version must match across packs is StreamCraft Live.** Coordinate StreamCraft updates as a synchronized release (e.g., TBS-Client 1.2.0 + TBS-Server 1.3.0 both pin StreamCraft 0.7.x).

### Vanilla-joiner support
Advertise prominently: anyone with a stock 26.1.2 client can join. Streamers, one-off visitors, and friends without the modpack don't need to install anything beyond StreamCraft (only required if they want to participate in stream-triggered events — otherwise even StreamCraft is optional for casual visitors).

---

## Pre-launch compatibility checks

Before pinning the first release, confirm 26.1.x builds exist for:

- **Voxy + Voxy World Gen V2** — LOD renderer for TBS-Client
- **Lootr, FallingTree (server-side variant), Trade Cycling, Saplanting, Universal Bone Meal, NoExpensive** — Tier S5 gameplay augments
- **Styled Chat, Text Placeholder API, Fabricord** — Tier S4 communication stack
- **C2ME, Noisium, Lithium, Krypton, ModernFix** — perf-core mods that historically lag a few weeks behind major MC releases

If any S4 / S5 mod lacks a 26.1.x build at launch:
- Ship TBS-Server v1.0 with Tiers S1–S3 + S6 only (perf, ops, perms, BlueMap)
- Add Tiers S4 / S5 incrementally as builds appear
- No TBS-Client change required — the architecture absorbs server-side gaps cleanly
