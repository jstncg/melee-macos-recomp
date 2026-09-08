# Credits and dependency provenance

This repository adds the Melee macOS integration, AppKit frontend, local build/import
scripts, configuration fixes, and runtime patches. It depends on the projects below.
Their authors retain credit for their work; upstream per-file notices are preserved.

| Project | Pinned revision | Role |
|---|---|---|
| [ModernGekko-Template](https://github.com/ExpansionPak/ModernGekko-Template) | `eedda2b02dde3aefc02796d859f0033b916aad03` | Recompilation template and pinned submodules |
| [ModernGekko](https://github.com/ExpansionPak/ModernGekko) | `5417826c31187d4dadf8588c7aa25bf107782936` | Runtime integration and frontend/netplay foundations |
| [DolRecomp](https://github.com/ExpansionPak/DolRecomp) | `1bec3554ecc4817cf78319ca3d8a0669477f29fa` | PowerPC-to-C recompilation and disc extraction |
| [RecompCore](https://github.com/ExpansionPak/RecompCore) | `55c7b023fa0f4eba1cf3fdbbb25b1c5ec468d5ac` | Dolphin-derived runtime and static execution core |
| [Dolphin](https://github.com/dolphin-emu/dolphin) | Through pinned RecompCore | Graphics, audio, input, system services, and netplay |
| [Melee decompilation](https://github.com/doldecomp/melee) | Reference only; not vendored or compiled | Executable validation and OS behavior reference |

Specific upstream acknowledgments include:

- **ExpansionPak / Hyperway** — ModernGekko, templates, and integration.
- **aharonahdoot / SpecialK** — RecompCore foundations referenced by ModernGekko.
- **The Dolphin team and contributors** — the runtime's foundation.
- **MrPoloGit / Literally God** — recompilation template work, macOS support,
  and prior Super Smash Bros. Melee recompilation work.
- **DolRecomp contributors** and **doldecomp/melee contributors**.
- **SDL, Cubeb, Dear ImGui**, and the other dependency authors represented by the
  recursively pinned upstream source and its license notices.

ModernGekko and DolRecomp include GPLv3 license texts. Dolphin's COPYING explains
that its aggregate source is GPLv3-compatible, with individual files and external
dependencies carrying their own notices/licenses. This repository preserves patch
context notices and supplies GPLv3 text in LICENSE; it does not relicense dependency
code or claim ownership of game data or artwork.
