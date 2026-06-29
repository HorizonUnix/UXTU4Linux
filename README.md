<picture><img align="center" src="/Img/Banner.gif"/></picture>
<h4>Powered by AMD SMU and Python</h4>

[![GitHub Downloads](https://img.shields.io/github/downloads/HorizonUnix/UXTU4Linux/total?style=flat-square&color=blue)](https://github.com/HorizonUnix/UXTU4Linux/releases)
[![Python](https://img.shields.io/badge/Python-3.10%2B-yellow?style=flat-square)](https://www.python.org/)
[![License](https://img.shields.io/github/license/HorizonUnix/UXTU4Linux?style=flat-square)](LICENSE)
[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/HorizonUnix/UXTU4Linux)

## Overview

UXTU4Linux is a power management tool for **AMD Ryzen APUs and desktop CPUs** on Linux. It talks to the CPU directly through PCI register access — no kernel module required on most systems. When Secure Boot is enabled, it uses the [ryzen_smu](https://github.com/amkillam/ryzen_smu) kernel module instead. Either way, you can change power limits, temperature limits and more without touching the BIOS. The interactive terminal UI runs as your normal user, and a small background daemon (systemd service) does the privileged work and auto-switches presets for you.

**What it can do:**
- Built-in Eco / Balance / Performance / Extreme presets for a wide range of Ryzen APUs, desktop CPUs and Framework Laptops
- Adaptive Mode that tunes the power limit, Curve Optimiser and iGPU clocks live based on temperature and load, with savable adaptive presets, optional auto-start, and per-tick ASUS power profile / NVIDIA GPU tuning
- Custom Preset Editor with around 65 tunable parameters on APUs: power and temperature limits, VRM currents, clock targets, Curve Optimiser (all-core, iGPU and per-core), static OC and more
- System settings in the same preset: power profile (the Linux equivalent of the Windows power mode), ASUS performance mode / GPU Eco / GPU MUX, and CCD affinity on dual-CCD chips
- NVIDIA dGPU clock limits and core/memory offsets via nvidia-smi and NVML
- Live Home dashboard with real-time CPU temperature, power, clock and usage graphs
- Automations: switch presets automatically on AC/battery changes and re-apply on resume from sleep, suspend or hibernation
- Auto-reapply on a timer, so competing power management tools can't silently undo your settings
- Per-command SMU feedback: the Status tab shows exactly which commands your CPU accepted and which it rejected, instead of failing silently
- Built-in updater that keeps your config and custom presets across updates

---

## Compatibility

| Platform | Status |
|----------|--------|
| Linux with systemd, Python 3.10+ | Actively supported |
| Linux without systemd (OpenRC, runit, etc.) | Supported — installer sets everything up, you start the daemon manually |
| Intel | Not supported |

> [!NOTE]
> **ryzen_smu is only needed when Secure Boot is enabled.** On most systems (Secure Boot off), UXTU4Linux uses PCI direct access and works out of the box. If Secure Boot is on, install ryzen_smu ≥ 0.1.7 and enroll the signing key — see the [Wiki](../../wiki) for per-distro instructions.

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
  <img src="/Img/home.png"/>
  <img src="/Img/premade.png"/>
  <img src="/Img/custom.png"/>
  <img src="/Img/adaptive.png"/>
  <img src="/Img/auto.png"/>
  <img src="/Img/info.png"/>
  <img src="/Img/status.png"/>
  <img src="/Img/settings.png"/>
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