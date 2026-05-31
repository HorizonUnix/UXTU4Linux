import json
import os
import subprocess

_PRESETS_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "device_presets.json")
_PRESETS_CACHE = None

def _load_presets():
    global _PRESETS_CACHE
    if _PRESETS_CACHE is not None:
        return _PRESETS_CACHE
    try:
        if os.path.exists(_PRESETS_FILE):
            with open(_PRESETS_FILE, "r") as f:
                data = json.load(f)
                _PRESETS_CACHE = data.get("devices", [])
                return _PRESETS_CACHE
    except Exception:
        pass
    return []

def _has_discrete_gpu(gpu_flag: str) -> bool:
    try:
        result = subprocess.run(
            ["lspci"],
            capture_output=True, text=True, timeout=5,
        )
        lines = [l for l in result.stdout.splitlines() if "VGA" in l or "Display" in l]
        vga = "\n".join(lines).lower()
        return gpu_flag.lower() in vga
    except Exception:
        return False

def match_device(manufacturer: str, product_name: str) -> str:
    devices = _load_presets()
    mfr_lower = manufacturer.lower()
    prod_lower = product_name.lower()
    
    for device in devices:
        # Check manufacturer
        if "manufacturer_contains" in device:
            if device["manufacturer_contains"].lower() not in mfr_lower:
                continue
                
        # Check product name ALL (AND condition)
        if "product_name_contains" in device:
            reqs = device["product_name_contains"]
            if isinstance(reqs, list):
                if not all(r.lower() in prod_lower for r in reqs):
                    continue
            elif isinstance(reqs, str):
                if reqs.lower() not in prod_lower:
                    continue
                    
        # Check product name ANY (OR condition)
        if "product_name_contains_any" in device:
            reqs = device["product_name_contains_any"]
            if isinstance(reqs, list):
                if not any(r.lower() in prod_lower for r in reqs):
                    continue
                    
        # Check discrete GPU requirement
        if "requires_discrete_gpu" in device:
            if not _has_discrete_gpu(device["requires_discrete_gpu"]):
                continue
                
        return device.get("variant_name", "")
        
    return ""

def get_device_preset(variant_name: str) -> dict | None:
    devices = _load_presets()
    for device in devices:
        if device.get("variant_name") == variant_name:
            return device.get("preset")
    return None
