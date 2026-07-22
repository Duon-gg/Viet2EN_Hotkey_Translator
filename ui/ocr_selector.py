"""Screen-region selector used by the OCR fallback."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable


def select_screen_region(root: tk.Misc, on_selected: Callable[[tuple[int, int, int, int]], None]) -> None:
    overlay = tk.Toplevel(root)
    overlay.attributes("-fullscreen", True)
    overlay.attributes("-topmost", True)
    overlay.attributes("-alpha", 0.28)
    overlay.configure(bg="black")
    overlay.title("Vitra OCR")

    canvas = tk.Canvas(overlay, bg="#08111f", highlightthickness=0, cursor="crosshair")
    canvas.pack(fill=tk.BOTH, expand=True)
    canvas.create_text(
        overlay.winfo_screenwidth() // 2,
        44,
        text="Kéo chuột quanh vùng cần dịch • Esc để hủy",
        fill="white",
        font=("Segoe UI", 15, "bold"),
    )

    start: dict[str, int | None] = {"x": None, "y": None, "rect": None}

    def cancel(_event=None) -> None:
        overlay.destroy()

    def mouse_down(event: tk.Event) -> None:
        start["x"], start["y"] = event.x, event.y
        if start["rect"] is not None:
            canvas.delete(start["rect"])
        start["rect"] = canvas.create_rectangle(
            event.x,
            event.y,
            event.x,
            event.y,
            outline="#38bdf8",
            width=3,
            fill="#0ea5e9",
            stipple="gray25",
        )

    def mouse_move(event: tk.Event) -> None:
        if start["rect"] is not None and start["x"] is not None and start["y"] is not None:
            canvas.coords(start["rect"], start["x"], start["y"], event.x, event.y)

    def mouse_up(event: tk.Event) -> None:
        if start["x"] is None or start["y"] is None:
            return
        x1, x2 = sorted((int(start["x"]), int(event.x)))
        y1, y2 = sorted((int(start["y"]), int(event.y)))
        if x2 - x1 < 8 or y2 - y1 < 8:
            cancel()
            return
        root_x, root_y = overlay.winfo_rootx(), overlay.winfo_rooty()
        bbox = (root_x + x1, root_y + y1, root_x + x2, root_y + y2)
        overlay.destroy()
        root.after(120, lambda: on_selected(bbox))

    overlay.bind("<Escape>", cancel)
    canvas.bind("<ButtonPress-1>", mouse_down)
    canvas.bind("<B1-Motion>", mouse_move)
    canvas.bind("<ButtonRelease-1>", mouse_up)
    overlay.focus_force()
