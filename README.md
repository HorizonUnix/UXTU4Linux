<picture><img align="left" src="/Img/Logo.png"/></picture>
<h4>Powered by RyzenAdj and Python</h4>

[![GitHub Downloads](https://img.shields.io/github/downloads/HorizonUnix/UXTU4Linux/total?style=flat-square&color=blue)](https://github.com/HorizonUnix/UXTU4Linux/releases)
[![Latest Release](https://img.shields.io/github/v/release/HorizonUnix/UXTU4Linux?style=flat-square&color=green)](https://github.com/HorizonUnix/UXTU4Linux/releases/latest)
[![Python](https://img.shields.io/badge/Python-3.10%2B-yellow?style=flat-square)](https://www.python.org/)
[![License](https://img.shields.io/github/license/HorizonUnix/UXTU4Linux?style=flat-square)](LICENSE)

## Overview

UXTU4Linux is a power management tool for **AMD Ryzen APUs** on Linux. It wraps [RyzenAdj](https://github.com/FlyGoat/RyzenAdj) with an interactive terminal UI and a background systemd daemon, letting you apply and auto-switch power presets without touching the BIOS.

**Key features:**
- Premade presets for a wide range of AMD APUs
- Custom Preset Editor: build your own preset with per-field hints and live value adjustment
- Automations: automatically switch presets when plugging in or unplugging, even without reapply
- Auto-reapply on a configurable timer via background daemon
- Built-in updater with config and custom preset backup and restore

---

## Compatibility

| Platform | Status |
|----------|--------|
| Linux with systemd, Python 3.10+ | ✅ Actively supported |
| macOS 11 → 26 | ⚠️ Deprecated as of v0.5.22 — [Wiki](https://github.com/HorizonUnix/UXTU4Linux/wiki/macOS-Installation-and-Troubleshooting) |

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

---

## Preview

<p align="left">
  <img src="/Img/menu.png"/>
  <img src="/Img/power.png"/>
  <img src="/Img/power_status.png"/>
  <img src="/Img/custom.png"/>
  <img src="/Img/automations.png"/>
  <img src="/Img/settings.png"/>
  <img src="/Img/hardware.png"/>
</p>

---

## Acknowledgments

| Contributor | Contribution |
|-------------|-------------|
| [b00t0x](https://github.com/b00t0x) | Guidance on building ryzenadj with DirectHW and pciutils-osx |
| [FlyGoat](https://github.com/FlyGoat) | [RyzenAdj](https://github.com/FlyGoat/RyzenAdj) |
| [JamesCJ60](https://github.com/JamesCJ60) | [UXTU](https://github.com/JamesCJ60/Universal-x86-Tuning-Utility) preset design and inspiration |
| [corpnewt](https://github.com/corpnewt) | macOS `.command` launcher template |
| [NotchApple1703](https://github.com/NotchApple1703) | Advisor |
