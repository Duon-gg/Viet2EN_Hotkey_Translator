"""Tkinter settings window. All worker callbacks are marshalled to the Tk thread."""

from __future__ import annotations

import os
import tkinter as tk
from collections.abc import Callable
from tkinter import filedialog, messagebox, ttk

from core import clipboard, engine, ocr
from utils import config

settings_window: tk.Toplevel | None = None


def open_settings_window(root: tk.Misc, on_save_callback: Callable[[], None]) -> None:
    global settings_window
    if settings_window and settings_window.winfo_exists():
        settings_window.deiconify()
        settings_window.lift()
        settings_window.focus_force()
        return

    settings_window = tk.Toplevel(root)
    settings_window.title("Cài đặt Viet2EN Translator")
    settings_window.geometry("660x690")
    settings_window.minsize(620, 620)
    settings_window.attributes("-topmost", True)

    try:
        icon_path = config.APP_DIR / "assets" / "icon-v2.ico"
        if icon_path.exists():
            settings_window.iconbitmap(icon_path)
    except Exception:
        pass

    notebook = ttk.Notebook(settings_window)
    notebook.pack(fill=tk.BOTH, expand=True, padx=14, pady=14)

    general_tab = ttk.Frame(notebook, padding=16)
    model_tab = ttk.Frame(notebook, padding=16)
    integration_tab = ttk.Frame(notebook, padding=16)
    glossary_tab = ttk.Frame(notebook, padding=16)
    notebook.add(general_tab, text="Chung")
    notebook.add(model_tab, text="Model")
    notebook.add(integration_tab, text="Browser & OCR")
    notebook.add(glossary_tab, text="Glossary")

    # General
    hotkey_var = tk.StringVar(value=str(config.config.get("hotkey", "f2")).upper())
    direction_labels = {
        "Tự nhận diện": "auto",
        "Việt → Anh": "vi_en",
        "Anh → Việt": "en_vi",
    }
    current_direction = str(config.config.get("direction", "auto"))
    direction_var = tk.StringVar(
        value=next(
            (label for label, value in direction_labels.items() if value == current_direction), "Tự nhận diện"
        )
    )
    performance_labels = {
        "Hiệu năng — giữ model trong RAM": "performance",
        "Cân bằng — tự giải phóng khi rảnh": "balanced",
        "Tiết kiệm RAM — nạp khi cần": "low_memory",
    }
    current_mode = str(config.config.get("performance_mode", "balanced"))
    performance_var = tk.StringVar(
        value=next(
            (label for label, value in performance_labels.items() if value == current_mode),
            list(performance_labels)[1],
        )
    )
    startup_var = tk.BooleanVar(value=bool(config.config.get("startup", False)))
    unload_var = tk.IntVar(value=int(config.config.get("auto_unload_minutes", 30)))
    restore_var = tk.DoubleVar(value=float(config.config.get("restore_delay_seconds", 0.35)))
    compute_var = tk.StringVar(value=str(config.config.get("compute_type", "auto")))
    device_var = tk.StringVar(value=str(config.config.get("device", "cpu")))
    normalize_accentless_var = tk.BooleanVar(
        value=bool(config.config.get("normalize_accentless_vietnamese", True))
    )

    def row(parent: tk.Misc, label: str, widget: tk.Widget, index: int) -> None:
        ttk.Label(parent, text=label).grid(row=index, column=0, sticky=tk.W, padx=(0, 14), pady=8)
        widget.grid(row=index, column=1, sticky=tk.EW, pady=8)

    general_tab.columnconfigure(1, weight=1)
    row(general_tab, "Hotkey toàn hệ thống", ttk.Entry(general_tab, textvariable=hotkey_var), 0)
    row(
        general_tab,
        "Chiều dịch mặc định",
        ttk.Combobox(
            general_tab, textvariable=direction_var, values=list(direction_labels), state="readonly"
        ),
        1,
    )
    row(
        general_tab,
        "Chế độ hiệu năng",
        ttk.Combobox(
            general_tab, textvariable=performance_var, values=list(performance_labels), state="readonly"
        ),
        2,
    )
    row(
        general_tab,
        "Unload sau (phút)",
        ttk.Spinbox(general_tab, from_=1, to=1440, textvariable=unload_var),
        3,
    )
    row(
        general_tab,
        "Khôi phục clipboard sau (giây)",
        ttk.Spinbox(general_tab, from_=0.05, to=5, increment=0.05, textvariable=restore_var),
        4,
    )
    row(
        general_tab,
        "CTranslate2 compute type",
        ttk.Combobox(
            general_tab,
            textvariable=compute_var,
            values=["auto", "int8", "int8_float32", "float32", "float16"],
            state="readonly",
        ),
        5,
    )
    row(
        general_tab,
        "Thiết bị",
        ttk.Combobox(general_tab, textvariable=device_var, values=["cpu", "cuda", "auto"], state="readonly"),
        6,
    )
    ttk.Checkbutton(general_tab, text="Khởi động cùng Windows", variable=startup_var).grid(
        row=7, column=0, columnspan=2, sticky=tk.W, pady=12
    )
    ttk.Checkbutton(
        general_tab,
        text="Tự thêm dấu cho một số từ tiếng Việt không dấu",
        variable=normalize_accentless_var,
    ).grid(row=8, column=0, columnspan=2, sticky=tk.W, pady=6)
    ttk.Label(
        general_tab,
        text="Thay đổi compute type hoặc thiết bị có hiệu lực đầy đủ sau khi khởi động lại app.",
        foreground="#64748b",
        wraplength=560,
    ).grid(row=9, column=0, columnspan=2, sticky=tk.W, pady=(8, 0))

    # Models
    model_status_var = tk.StringVar(value="Đang kiểm tra…")
    ttk.Label(model_tab, textvariable=model_status_var, font=("Segoe UI", 11, "bold")).pack(anchor=tk.W)
    progress_var = tk.DoubleVar(value=0)
    progress = ttk.Progressbar(model_tab, variable=progress_var, maximum=100)
    progress.pack(fill=tk.X, pady=14)
    model_buttons = ttk.Frame(model_tab)
    model_buttons.pack(fill=tk.X)

    def refresh_model_status() -> None:
        status = engine.get_status()
        model_status_var.set(
            f"VI→EN: {'đã cài' if status['vi2en'] else 'thiếu'}  •  "
            f"EN→VI: {'đã cài' if status['en2vi'] else 'thiếu'}  •  "
            f"Trạng thái: {status['state']}"
        )

    def ui_call(callback: Callable[[], None]) -> None:
        if settings_window and settings_window.winfo_exists():
            root.after(0, callback)

    def set_model_busy(busy: bool) -> None:
        state = tk.DISABLED if busy else tk.NORMAL
        download_button.configure(state=state)
        local_button.configure(state=state)

    def model_status(message: str) -> None:
        ui_call(lambda: model_status_var.set(message))

    def model_progress(value: float) -> None:
        ui_call(lambda: progress_var.set(max(0, min(100, value))))

    def model_complete(success: bool, message: str) -> None:
        def finish() -> None:
            set_model_busy(False)
            refresh_model_status()
            if not success:
                messagebox.showerror("Viet2EN", message, parent=settings_window)

        ui_call(finish)

    def download_models() -> None:
        set_model_busy(True)
        progress_var.set(0)
        engine.download_model(model_status, model_progress, model_complete)

    def install_local() -> None:
        file_path = filedialog.askopenfilename(
            parent=settings_window,
            title="Chọn model Argos",
            filetypes=[("Argos Model", "*.argosmodel"), ("Tất cả file", "*.*")],
        )
        if file_path:
            set_model_busy(True)
            engine.install_from_local_file(file_path, model_status, model_complete)

    download_button = ttk.Button(model_buttons, text="Tải đủ model VI↔EN", command=download_models)
    download_button.pack(side=tk.LEFT)
    local_button = ttk.Button(model_buttons, text="Cài từ file…", command=install_local)
    local_button.pack(side=tk.LEFT, padx=10)
    ttk.Button(model_buttons, text="Làm mới trạng thái", command=refresh_model_status).pack(side=tk.LEFT)
    ttk.Label(
        model_tab,
        text="Model được lưu cạnh ứng dụng để hỗ trợ offline bundle. Cấu hình và log được lưu trong LocalAppData.",
        foreground="#64748b",
        wraplength=570,
    ).pack(anchor=tk.W, pady=20)
    refresh_model_status()

    # Browser / OCR
    bridge_enabled_var = tk.BooleanVar(value=bool(config.config.get("browser_bridge_enabled", True)))
    bridge_port_var = tk.IntVar(value=int(config.config.get("browser_bridge_port", 8765)))
    token_var = tk.StringVar(value=str(config.config.get("browser_bridge_token", "")))
    uia_var = tk.BooleanVar(value=bool(config.config.get("uiautomation_enabled", True)))
    ocr_var = tk.BooleanVar(value=bool(config.config.get("ocr_enabled", True)))
    ocr_confidence_var = tk.DoubleVar(value=float(config.config.get("ocr_min_confidence", 0.45)))

    integration_tab.columnconfigure(1, weight=1)
    ttk.Checkbutton(integration_tab, text="Bật Browser Bridge", variable=bridge_enabled_var).grid(
        row=0, column=0, columnspan=2, sticky=tk.W, pady=6
    )
    row(
        integration_tab,
        "Port localhost",
        ttk.Spinbox(integration_tab, from_=1024, to=65535, textvariable=bridge_port_var),
        1,
    )
    token_entry = ttk.Entry(integration_tab, textvariable=token_var, state="readonly")
    row(integration_tab, "Bridge token", token_entry, 2)
    ttk.Button(integration_tab, text="Copy token", command=lambda: clipboard.safe_copy(token_var.get())).grid(
        row=3, column=1, sticky=tk.W
    )
    ttk.Button(
        integration_tab,
        text="Mở thư mục extension",
        command=lambda: os.startfile(config.APP_DIR / "browser_extension"),
    ).grid(row=4, column=1, sticky=tk.W, pady=8)
    ttk.Checkbutton(integration_tab, text="Dùng Windows UI Automation", variable=uia_var).grid(
        row=5, column=0, columnspan=2, sticky=tk.W, pady=6
    )
    ttk.Checkbutton(integration_tab, text="Bật OCR offline fallback", variable=ocr_var).grid(
        row=6, column=0, columnspan=2, sticky=tk.W, pady=6
    )
    row(
        integration_tab,
        "OCR confidence tối thiểu",
        ttk.Spinbox(integration_tab, from_=0, to=1, increment=0.05, textvariable=ocr_confidence_var),
        7,
    )
    ttk.Label(
        integration_tab,
        text=("OCR dependency: sẵn sàng" if ocr.SERVICE.available else "OCR dependency: chưa cài")
        + "\nExtension cần cùng port/token và phải bật quyền file URL khi thử HTML cục bộ.",
        foreground="#64748b",
        wraplength=570,
    ).grid(row=8, column=0, columnspan=2, sticky=tk.W, pady=14)

    # Glossary
    ttk.Label(glossary_tab, text="Mỗi dòng: thuật ngữ nguồn = bản dịch bắt buộc").pack(anchor=tk.W)
    glossary_text = tk.Text(glossary_tab, wrap=tk.NONE, undo=True)
    glossary_text.pack(fill=tk.BOTH, expand=True, pady=10)
    glossary = config.config.get("glossary", {})
    if isinstance(glossary, dict):
        glossary_text.insert("1.0", "\n".join(f"{source} = {target}" for source, target in glossary.items()))

    footer = ttk.Frame(settings_window, padding=(14, 0, 14, 14))
    footer.pack(fill=tk.X)

    def save() -> None:
        try:
            glossary_values: dict[str, str] = {}
            for line_number, line in enumerate(glossary_text.get("1.0", "end-1c").splitlines(), start=1):
                if not line.strip():
                    continue
                if "=" not in line:
                    raise ValueError(f"Glossary dòng {line_number} thiếu dấu '='")
                source, target = (part.strip() for part in line.split("=", 1))
                if not source or not target:
                    raise ValueError(f"Glossary dòng {line_number} không hợp lệ")
                glossary_values[source] = target

            config.config.update(
                {
                    "hotkey": hotkey_var.get().strip().lower(),
                    "direction": direction_labels[direction_var.get()],
                    "startup": startup_var.get(),
                    "performance_mode": performance_labels[performance_var.get()],
                    "auto_unload_minutes": int(unload_var.get()),
                    "restore_delay_seconds": float(restore_var.get()),
                    "compute_type": compute_var.get(),
                    "device": device_var.get(),
                    "normalize_accentless_vietnamese": normalize_accentless_var.get(),
                    "browser_bridge_enabled": bridge_enabled_var.get(),
                    "browser_bridge_port": int(bridge_port_var.get()),
                    "uiautomation_enabled": uia_var.get(),
                    "ocr_enabled": ocr_var.get(),
                    "ocr_min_confidence": float(ocr_confidence_var.get()),
                    "glossary": glossary_values,
                }
            )
            config.save_config()
            if not config.set_startup(config.config["startup"]):
                raise RuntimeError("Không thể thay đổi cấu hình khởi động cùng Windows")
            on_save_callback()
            settings_window.destroy()
        except (ValueError, RuntimeError, OSError, tk.TclError) as exc:
            messagebox.showerror("Cấu hình không hợp lệ", str(exc), parent=settings_window)

    ttk.Button(footer, text="Lưu cài đặt", command=save).pack(side=tk.RIGHT)
    ttk.Button(footer, text="Hủy", command=settings_window.destroy).pack(side=tk.RIGHT, padx=8)
