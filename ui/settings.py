import tkinter as tk
from tkinter import ttk, filedialog
import os
from utils import config
from core import engine

settings_window = None

def open_settings_window(root, on_save_callback):
    global settings_window
    if settings_window and settings_window.winfo_exists():
        settings_window.focus()
        return

    settings_window = tk.Toplevel(root)
    settings_window.title("Cài đặt Viet2EN Translator (Offline)")
    settings_window.geometry("450x450")
    settings_window.resizable(False, False)
    settings_window.attributes('-topmost', True)

    try:
        ICON_PATH = os.path.join(os.path.dirname(__file__), "..", "assets", "icon.ico")
        if os.path.exists(ICON_PATH):
            settings_window.iconbitmap(ICON_PATH)
    except Exception as e:
        print(f"[Settings] Lỗi nạp window icon: {e}")

    # Căn giữa màn hình

    settings_window.update_idletasks()
    w = settings_window.winfo_width()
    h = settings_window.winfo_height()
    x = (settings_window.winfo_screenwidth() // 2) - (w // 2)
    y = (settings_window.winfo_screenheight() // 2) - (h // 2)
    settings_window.geometry(f'{w}x{h}+{x}+{y}')

    # ── Model section ──
    model_frame = ttk.LabelFrame(settings_window, text="Mô hình dịch Offline (Tự động 2 chiều)")
    model_frame.pack(fill=tk.X, padx=15, pady=(15, 5))

    eng_status = engine.get_status()
    status_vi2en = "✅ VI->EN" if eng_status["vi2en"] else "❌ VI->EN"
    status_en2vi = "✅ EN->VI" if eng_status["en2vi"] else "❌ EN->VI"
    status_label = ttk.Label(model_frame, text=f"Trạng thái:  {status_vi2en}  |  {status_en2vi}")
    status_label.pack(pady=(8, 4), padx=10, anchor=tk.W)

    progress_var = tk.DoubleVar()
    progress_bar = ttk.Progressbar(model_frame, variable=progress_var, maximum=100)

    def on_status_update(msg):
        status_label.config(text=msg)
        
    def on_progress_update(percent, speed_text=""):
        if percent >= 0:
            if not progress_bar.winfo_ismapped():
                progress_bar.pack(fill=tk.X, padx=10, pady=(0, 5), before=btn_download)
            progress_var.set(percent)
        else:
            if progress_bar.winfo_ismapped():
                progress_bar.pack_forget()

    def on_complete(success, msg):
        btn_download.config(state=tk.NORMAL)
        btn_local.config(state=tk.NORMAL)
        on_progress_update(-1) # Hide
        
    def cmd_download():
        btn_download.config(state=tk.DISABLED)
        btn_local.config(state=tk.DISABLED)
        on_progress_update(0)
        engine.download_model(on_status_update, on_progress_update, on_complete)

    def cmd_local():
        file_path = filedialog.askopenfilename(
            title="Chọn file mô hình .argosmodel",
            filetypes=[("Argos Model", "*.argosmodel"), ("All files", "*.*")]
        )
        if not file_path:
            return
        btn_download.config(state=tk.DISABLED)
        btn_local.config(state=tk.DISABLED)
        engine.install_from_local_file(file_path, on_status_update, on_complete)

    btn_download = ttk.Button(model_frame, text="Tải mô hình (Download Model)", command=cmd_download)
    btn_download.pack(pady=(0, 5), padx=10)

    btn_local = ttk.Button(model_frame, text="Cài từ file (.argosmodel)", command=cmd_local)
    btn_local.pack(pady=(0, 5), padx=10)

    note_label = ttk.Label(model_frame, text="⚠ Nếu tải online lỗi, tải file .argosmodel thủ công rồi\n    dùng nút 'Cài từ file'", foreground="gray")
    note_label.pack(pady=(0, 8), padx=10, anchor=tk.W)

    # ── Hotkey ──
    hotkey_frame = ttk.Frame(settings_window)
    hotkey_frame.pack(fill=tk.X, padx=15, pady=8)
    ttk.Label(hotkey_frame, text="Phím tắt:").pack(side=tk.LEFT, padx=(0, 8))
    hotkey_var = tk.StringVar(value=config.config.get("hotkey", "f2").upper())
    hotkey_combo = ttk.Combobox(
        hotkey_frame, textvariable=hotkey_var,
        values=["F2", "F3", "F4", "F5", "F6", "F7", "F8"],
        state="readonly", width=10
    )
    hotkey_combo.pack(side=tk.LEFT)

    # ── System Settings ──
    sys_frame = ttk.Frame(settings_window)
    sys_frame.pack(fill=tk.X, padx=15, pady=8)
    
    startup_var = tk.BooleanVar(value=config.config.get("startup", False))
    ttk.Checkbutton(sys_frame, text="Khởi động cùng Windows", variable=startup_var).pack(anchor=tk.W)

    unload_frame = ttk.Frame(sys_frame)
    unload_frame.pack(fill=tk.X, pady=5)
    ttk.Label(unload_frame, text="Tự giải phóng RAM sau (phút):").pack(side=tk.LEFT, padx=(0, 8))
    unload_var = tk.IntVar(value=config.config.get("auto_unload_minutes", 30))
    ttk.Entry(unload_frame, textvariable=unload_var, width=5).pack(side=tk.LEFT)

    # ── Save ──
    def save():
        config.config["hotkey"] = hotkey_var.get().lower()
        config.config["startup"] = startup_var.get()
        try:
            config.config["auto_unload_minutes"] = int(unload_var.get())
        except:
            config.config["auto_unload_minutes"] = 30
            
        config.save_config()
        config.set_startup(config.config["startup"])
        
        on_save_callback()
        settings_window.destroy()
        print(f"[OK] Đã lưu. Nhấn {config.config['hotkey'].upper()} để dịch")

    ttk.Button(settings_window, text="Lưu cài đặt", command=save).pack(pady=12)
