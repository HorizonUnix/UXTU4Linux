# Custom args

```
 Ryzen Power Management adjust tool.

    -h, --help                            show this help message and exit

Options
    -i, --info                            Show information and most important power metrics after adjustment
    --dump-table                          Show whole power metric table before and after adjustment

Settings
    -a, --stapm-limit=<u32>               Sustained Power Limit         - STAPM LIMIT (mW)
    -b, --fast-limit=<u32>                Actual Power Limit            - PPT LIMIT FAST (mW)
    -c, --slow-limit=<u32>                Average Power Limit           - PPT LIMIT SLOW (mW)
    -d, --slow-time=<u32>                 Slow PPT Constant Time (s)
    -e, --stapm-time=<u32>                STAPM constant time (s)
    -f, --tctl-temp=<u32>                 Tctl Temperature Limit (degree C)
    -g, --vrm-current=<u32>               VRM Current Limit             - TDC LIMIT VDD (mA)
    -j, --vrmsoc-current=<u32>            VRM SoC Current Limit         - TDC LIMIT SoC (mA)
    --vrmgfx-current=<u32>                VRM GFX Current Limit - TDC LIMIT GFX (mA)
    --vrmcvip-current=<u32>               VRM CVIP Current Limit - TDC LIMIT CVIP (mA)
    -k, --vrmmax-current=<u32>            VRM Maximum Current Limit     - EDC LIMIT VDD (mA)
    -l, --vrmsocmax-current=<u32>         VRM SoC Maximum Current Limit - EDC LIMIT SoC (mA)
    --vrmgfxmax_current=<u32>             VRM GFX Maximum Current Limit - EDC LIMIT GFX (mA)
    -m, --psi0-current=<u32>              PSI0 VDD Current Limit (mA)
    --psi3cpu_current=<u32>               PSI3 CPU Current Limit (mA)
    -n, --psi0soc-current=<u32>           PSI0 SoC Current Limit (mA)
    --psi3gfx_current=<u32>               PSI3 GFX Current Limit (mA)
    -o, --max-socclk-frequency=<u32>      Maximum SoC Clock Frequency (MHz)
    -p, --min-socclk-frequency=<u32>      Minimum SoC Clock Frequency (MHz)
    -q, --max-fclk-frequency=<u32>        Maximum Transmission (CPU-GPU) Frequency (MHz)
    -r, --min-fclk-frequency=<u32>        Minimum Transmission (CPU-GPU) Frequency (MHz)
    -s, --max-vcn=<u32>                   Maximum Video Core Next (VCE - Video Coding Engine) (MHz)
    -t, --min-vcn=<u32>                   Minimum Video Core Next (VCE - Video Coding Engine) (MHz)
    -u, --max-lclk=<u32>                  Maximum Data Launch Clock (MHz)
    -v, --min-lclk=<u32>                  Minimum Data Launch Clock (MHz)
    -w, --max-gfxclk=<u32>                Maximum GFX Clock (MHz)
    -x, --min-gfxclk=<u32>                Minimum GFX Clock (MHz)
    -y, --prochot-deassertion-ramp=<u32>  Ramp Time After Prochot is Deasserted: limit power based on value, higher values does apply tighter limits after prochot is over
    --apu-skin-temp=<u32>                 APU Skin Temperature Limit    - STT LIMIT APU (degree C)
    --dgpu-skin-temp=<u32>                dGPU Skin Temperature Limit   - STT LIMIT dGPU (degree C)
    --apu-slow-limit=<u32>                APU PPT Slow Power limit for A+A dGPU platform - PPT LIMIT APU (mW)
    --skin-temp-limit=<u32>               Skin Temperature Power Limit (mW)
    --gfx-clk=<u32>                       Forced Clock Speed MHz (Renoir Only)
    --oc-clk=<u32>                        Forced Core Clock Speed MHz (Renoir and up Only)
    --oc-volt=<u32>                       Forced Core VID: Must follow this calcuation (1.55 - [VID you want to set e.g. 1.25 for 1.25v]) / 0.00625 (Renoir and up Only)
    --enable-oc                           Enable OC (Renoir and up Only)
    --disable-oc                          Disable OC (Renoir and up Only)
    --set-coall=<u32>                     All core Curve Optimiser
    --set-coper=<u32>                     Per core Curve Optimiser
    --set-cogfx=<u32>                     iGPU Curve Optimiser
    --power-saving                        Hidden options to improve power efficiency (is set when AC unplugged): behavior depends on CPU generation, Device and Manufacture
    --max-performance                     Hidden options to improve performance (is set when AC plugged in): behavior depends on CPU generation, Device and Manufacture

P-State Functions

WARNING: Use at your own risk!
By Jiaxun Yang <jiaxun.yang@flygoat.com>, Under LGPL.
Version: v0.15.0
```
