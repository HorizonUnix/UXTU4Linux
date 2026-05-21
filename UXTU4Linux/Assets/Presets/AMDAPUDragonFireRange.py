PRESETS = {
    "Eco": "--tctl-temp=95 --stapm-limit=35000 --fast-limit=45000 --stapm-time=64 --slow-limit=35000 --slow-time=128 --vrm-current=180000 --vrmmax-current=180000 --vrmsoc-current=180000 --vrmsocmax-current=180000 --vrmgfx-current=180000",
    "Balance": "--tctl-temp=95 --stapm-limit=65000 --fast-limit=75000 --stapm-time=64 --slow-limit=65000 --slow-time=128 --vrm-current=180000 --vrmmax-current=180000 --vrmsoc-current=180000 --vrmsocmax-current=180000 --vrmgfx-current=180000",
    "Performance": "--tctl-temp=95 --stapm-limit=100000 --fast-limit=120000 --stapm-time=64 --slow-limit=100000 --slow-time=128 --vrm-current=240000 --vrmmax-current=240000 --vrmsoc-current=240000 --vrmsocmax-current=240000 --vrmgfx-current=240000",
    "Extreme": "--tctl-temp=95 --stapm-limit=125000 --fast-limit=145000 --stapm-time=64 --slow-limit=125000 --slow-time=128 --vrm-current=240000 --vrmmax-current=240000 --vrmsoc-current=240000 --vrmsocmax-current=240000 --vrmgfx-current=240000",
    "AC": "--max-performance",
    "DC": "--power-saving"
}