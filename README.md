<picture><img align="left" src="/Img/Logo.png"/></picture>
 
[![GitHub Downloads](https://img.shields.io/github/downloads/HorizonUnix/UXTU4Linux/total?style=flat-square&color=blue)](https://github.com/HorizonUnix/UXTU4Linux/releases)
[![Latest Release](https://img.shields.io/github/v/release/HorizonUnix/UXTU4Linux?style=flat-square&color=green)](https://github.com/HorizonUnix/UXTU4Linux/releases/latest)
[![Python](https://img.shields.io/badge/Python-3.10%2B-yellow?style=flat-square)](https://www.python.org/)
[![License](https://img.shields.io/github/license/HorizonUnix/UXTU4Linux?style=flat-square)](LICENSE)
  
## Overview
 
UXTU4Linux is a power management tool for **AMD Ryzen APUs and CPUs** on Linux (and formerly macOS). It wraps [RyzenAdj](https://github.com/FlyGoat/RyzenAdj) with an interactive terminal UI and a background systemd daemon, letting you apply and auto-switch power presets without touching the BIOS.
 
**Key features:**
- Premade presets for a wide range of AMD APUs
- Dynamic Mode - auto-switches between presets on AC vs. battery
- Auto-reapply on a configurable timer via background daemon
- Built-in updater with config backup and restore
---
 
## Compatibility
 
| Platform | Status |
|----------|--------|
| Linux - systemd, Python 3.10+ | ✅ Actively supported |
| macOS 11 -> 26 | ⚠️ Deprecated as of v0.5.22 [Wiki](https://github.com/HorizonUnix/UXTU4Linux/wiki/macOS-Installation-and-Troubleshooting) |
 
> [!IMPORTANT]
> **systemd is required.** Distros using OpenRC, runit, or other init systems are partially supported.
 
---
 
## Installation
 
```bash
curl -fsSL https://raw.githubusercontent.com/HorizonUnix/UXTU4Linux/main/install.sh | bash
```
 
For full details, troubleshooting, and manual steps see the **[Wiki](../../wiki)**.
 
## Usage

```bash
uxtu4linux
```

## Diagram

```mermaid

flowchart TD

subgraph group_client["Interactive client"]
  node_launcher["Launcher<br/>python entrypoint<br/>[UXTU4Linux.py]"]
  node_termui["TUI<br/>terminal ui<br/>[termui.py]"]
  node_ui["UI flow<br/>ui logic<br/>[ui.py]"]
end

subgraph group_control["Control plane"]
  node_ipc(("IPC<br/>local messaging<br/>[ipc.py]"))
  node_settings["Settings<br/>config state<br/>[settings.py]"]
  node_power["Power logic<br/>apply limits<br/>[power.py]"]
  node_daemon["Daemon<br/>background worker<br/>[daemon.py]"]
  node_service["Service<br/>systemd integration<br/>[service.py]"]
  node_config["Config<br/>[config.py]"]
end

subgraph group_platform["Platform boundary"]
  node_hardware["Hardware detect<br/>cpu detection<br/>[hardware.py]"]
  node_presets["Preset library<br/>device profiles"]
  node_ryzenadj{{"ryzenadj<br/>vendor binary"}}
  node_cpu[("AMD CPU/APU<br/>hardware target")]
end

subgraph group_support["Support and packaging"]
  node_updater["Updater<br/>maintenance<br/>[updater.py]"]
  node_setup["Installer<br/>bootstrap script<br/>[install.sh]"]
  node_modulesetup["Setup module<br/>bootstrap logic<br/>[setup.py]"]
end

node_launcher -->|"starts"| node_ui
node_launcher -->|"can start"| node_daemon
node_ui -->|"renders"| node_termui
node_ui -->|"controls"| node_ipc
node_termui -->|"reads/writes"| node_settings
node_ipc -->|"commands"| node_daemon
node_daemon -->|"runs under"| node_service
node_daemon -->|"loads"| node_settings
node_daemon -->|"enforces"| node_power
node_power -->|"targets"| node_hardware
node_hardware -->|"selects"| node_presets
node_presets -->|"supplies values"| node_power
node_power -->|"invokes"| node_ryzenadj
node_ryzenadj -->|"applies to"| node_cpu
node_settings -->|"uses defaults"| node_config
node_service -->|"reads"| node_config
node_updater -->|"preserves"| node_settings
node_setup -->|"bootstraps"| node_modulesetup
node_modulesetup -->|"installs"| node_service
node_cpu -.->|"discovered by"| node_hardware
node_ipc -.->|"syncs state"| node_settings

click node_launcher "https://github.com/horizonunix/uxtu4linux/blob/main/UXTU4Linux/UXTU4Linux.py"
click node_termui "https://github.com/horizonunix/uxtu4linux/blob/main/UXTU4Linux/Assets/Modules/termui.py"
click node_ui "https://github.com/horizonunix/uxtu4linux/blob/main/UXTU4Linux/Assets/Modules/ui.py"
click node_ipc "https://github.com/horizonunix/uxtu4linux/blob/main/UXTU4Linux/Assets/Modules/ipc.py"
click node_settings "https://github.com/horizonunix/uxtu4linux/blob/main/UXTU4Linux/Assets/Modules/settings.py"
click node_power "https://github.com/horizonunix/uxtu4linux/blob/main/UXTU4Linux/Assets/Modules/power.py"
click node_daemon "https://github.com/horizonunix/uxtu4linux/blob/main/UXTU4Linux/Assets/Modules/daemon.py"
click node_service "https://github.com/horizonunix/uxtu4linux/blob/main/UXTU4Linux/Assets/Modules/service.py"
click node_hardware "https://github.com/horizonunix/uxtu4linux/blob/main/UXTU4Linux/Assets/Modules/hardware.py"
click node_ryzenadj "https://github.com/horizonunix/uxtu4linux/tree/main/UXTU4Linux/Assets/Linux/ryzenadj"
click node_updater "https://github.com/horizonunix/uxtu4linux/blob/main/UXTU4Linux/Assets/Modules/updater.py"
click node_setup "https://github.com/horizonunix/uxtu4linux/blob/main/install.sh"
click node_config "https://github.com/horizonunix/uxtu4linux/blob/main/UXTU4Linux/Assets/Modules/config.py"
click node_modulesetup "https://github.com/horizonunix/uxtu4linux/blob/main/UXTU4Linux/Assets/Modules/setup.py"

classDef toneNeutral fill:#f8fafc,stroke:#334155,stroke-width:1.5px,color:#0f172a
classDef toneBlue fill:#dbeafe,stroke:#2563eb,stroke-width:1.5px,color:#172554
classDef toneAmber fill:#fef3c7,stroke:#d97706,stroke-width:1.5px,color:#78350f
classDef toneMint fill:#dcfce7,stroke:#16a34a,stroke-width:1.5px,color:#14532d
classDef toneRose fill:#ffe4e6,stroke:#e11d48,stroke-width:1.5px,color:#881337
classDef toneIndigo fill:#e0e7ff,stroke:#4f46e5,stroke-width:1.5px,color:#312e81
classDef toneTeal fill:#ccfbf1,stroke:#0f766e,stroke-width:1.5px,color:#134e4a
class node_launcher,node_termui,node_ui toneBlue
class node_ipc,node_settings,node_power,node_daemon,node_service,node_config toneAmber
class node_hardware,node_presets,node_ryzenadj,node_cpu toneMint
class node_updater,node_setup,node_modulesetup toneRose
```

---
 
## Preview
 
<p align="left">
  <img src="/Img/menu.png"/>
  <img src="/Img/power.png"/>
  <img src="/Img/power_status.png"/>
  <img src="/Img/settings.png"/>
  <img src="/Img/daemon.png"/>
  <img src="/Img/hardware.png"/>
</p>
 
## Acknowledgments
 
| Contributor | Contribution |
|-------------|-------------|
| [b00t0x](https://github.com/b00t0x) | Guidance on building ryzenadj with DirectHW and pciutils-osx |
| [FlyGoat](https://github.com/FlyGoat) | [RyzenAdj](https://github.com/FlyGoat/RyzenAdj) |
| [JamesCJ60](https://github.com/JamesCJ60) | [UXTU](https://github.com/JamesCJ60/Universal-x86-Tuning-Utility) preset design and inspiration |
| [corpnewt](https://github.com/corpnewt) | macOS `.command` launcher template |
| [NotchApple1703](https://github.com/NotchApple1703) | Advisor |
 
