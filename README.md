<picture><img align="left" src="/Img/Logo.png"/></picture>
<h4>Powered by ryzen_smu and Python</h4>

[![GitHub Downloads](https://img.shields.io/github/downloads/HorizonUnix/UXTU4Linux/total?style=flat-square&color=blue)](https://github.com/HorizonUnix/UXTU4Linux/releases)
[![Python](https://img.shields.io/badge/Python-3.10%2B-yellow?style=flat-square)](https://www.python.org/)
[![License](https://img.shields.io/github/license/HorizonUnix/UXTU4Linux?style=flat-square)](LICENSE)
[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/HorizonUnix/UXTU4Linux)

## Overview

UXTU4Linux is a power management tool for **AMD Ryzen APUs and desktop CPUs** on Linux. It talks to the CPU directly through the [ryzen_smu](https://github.com/amkillam/ryzen_smu) kernel module, so you can change power limits, temperature limits and more without touching the BIOS. The interactive terminal UI runs as your normal user, and a small background daemon (systemd service) does the privileged work and auto-switches presets for you.

**What it can do:**
- Built-in Eco / Balance / Performance / Extreme presets for a wide range of Ryzen APUs, desktop CPUs and Framework Laptops
- Custom Preset Editor with around 65 tunable parameters on APUs: power and temperature limits, VRM currents, clock targets, Curve Optimiser (all-core, iGPU and per-core), static OC and more
- System settings in the same preset: power profile (the Linux equivalent of the Windows power mode), ASUS performance mode / GPU Eco / GPU MUX, and CCD affinity on dual-CCD chips
- NVIDIA dGPU clock limits and core/memory offsets via nvidia-smi and NVML
- Automations: switch presets automatically on AC/battery changes and on resume from suspend
- Auto-reapply on a timer, so competing power management tools can't silently undo your settings
- Built-in updater that keeps your config and custom presets across updates

---

## Compatibility

| Platform | Status |
|----------|--------|
| Linux with systemd, Python 3.10+ | Actively supported |
| Linux without systemd (OpenRC, runit, etc.) | Works, but you start the daemon yourself |
| Intel | Not supported |

> [!IMPORTANT]
> Requires the **ryzen_smu** kernel module, version 0.1.7 or newer. The [Wiki](../../wiki) has build instructions for each distro.

---

## Installation

```bash
curl -fsSL https://raw.githubusercontent.com/HorizonUnix/UXTU4Linux/main/install.sh | bash
```

Then run:

```bash
uxtu4linux
```

The first run walks you through setting up the daemon and detecting your hardware. For the full setup guide, ryzen_smu build steps and troubleshooting, see the **[Wiki](../../wiki)**.

---

## Star History

<a href="https://www.star-history.com/?repos=HorizonUnix%2FUXTU4Linux&type=date&legend=top-left">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/chart?repos=HorizonUnix/UXTU4Linux&type=date&theme=dark&legend=top-left" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/chart?repos=HorizonUnix/UXTU4Linux&type=date&legend=top-left" />
   <img alt="Star History Chart" src="https://api.star-history.com/chart?repos=HorizonUnix/UXTU4Linux&type=date&legend=top-left" />
 </picture>
</a>

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
| [FlyGoat](https://github.com/FlyGoat) | [RyzenAdj](https://github.com/FlyGoat/RyzenAdj) |
| [JamesCJ60](https://github.com/JamesCJ60) | [UXTU](https://github.com/JamesCJ60/Universal-x86-Tuning-Utility) preset design and inspiration |
| [amkillam](https://github.com/amkillam) | [ryzen_smu](https://github.com/amkillam/ryzen_smu) DKMS fork |
| [utajum](https://github.com/utajum) | [g-helper-linux](https://github.com/utajum/g-helper-linux) reference for ASUS WMI and power profile support |
| [b00t0x](https://github.com/b00t0x) | Guidance on ryzenadj build dependencies |
| [NotchApple1703](https://github.com/NotchApple1703) | Advisor |