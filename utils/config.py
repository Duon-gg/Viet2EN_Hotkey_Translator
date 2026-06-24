import sys
import os
import json
import winreg

def get_app_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    else:
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

APP_DIR = get_app_dir()
CONFIG_FILE = os.path.join(APP_DIR, "config.json")
DEFAULT_CONFIG = {
    "hotkey": "f2",
    "startup": False,
    "model_installed": False,
    "auto_unload_minutes": 30,
    "restore_delay_seconds": 0.8
}

config = {}

def load_config():
    global config
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)
            # Điền các giá trị thiếu bằng default
            for k, v in DEFAULT_CONFIG.items():
                if k not in config:
                    config[k] = v
        except Exception:
            config = DEFAULT_CONFIG.copy()
    else:
        config = DEFAULT_CONFIG.copy()
    return config

def save_config():
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4, ensure_ascii=False)

def set_startup(enable):
    key = r"Software\Microsoft\Windows\CurrentVersion\Run"
    app_name = "Viet2EN_Translator"
    try:
        registry_key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key, 0, winreg.KEY_ALL_ACCESS)
        if enable:
            if getattr(sys, 'frozen', False):
                exe_path = sys.executable
                winreg.SetValueEx(registry_key, app_name, 0, winreg.REG_SZ, f'"{exe_path}"')
            else:
                vbs_path = os.path.join(APP_DIR, "run.vbs")
                winreg.SetValueEx(registry_key, app_name, 0, winreg.REG_SZ, f'wscript.exe "{vbs_path}"')
        else:
            try:
                winreg.DeleteValue(registry_key, app_name)
            except FileNotFoundError:
                pass
        winreg.CloseKey(registry_key)
    except Exception as e:
        print(f"Lỗi setup startup: {e}")
