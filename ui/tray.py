import pystray
from PIL import Image, ImageDraw
import threading
import os
from utils import config
from core import engine

tray_icon = None
is_translating = False
is_enabled = True

ICON_PATH = os.path.join(os.path.dirname(__file__), "..", "assets", "icon.ico")

def create_image(is_busy=False):
    try:
        image = Image.open(ICON_PATH).convert('RGBA')
        if is_busy:
            # Draw a subtle orange/red dot indicator in the top right corner
            draw = ImageDraw.Draw(image)
            w, h = image.size
            r = max(4, int(w * 0.15))
            draw.ellipse((w - 2*r - 2, 2, w - 2, 2*r + 2), fill=(230, 81, 0, 255))
        return image
    except Exception as e:
        width = 64
        height = 64
        image = Image.new('RGBA', (width, height), (0, 0, 0, 0))
        dc = ImageDraw.Draw(image)
        
        # Đổi màu nền (Cam đỏ lúc bận, Xanh đen lúc rảnh)
        bg_color = (230, 81, 0) if is_busy else (44, 62, 80)
        dc.rounded_rectangle((4, 4, 60, 60), radius=10, fill=bg_color)
        
        # Chữ "V>E" màu trắng
        dc.text((22, 25), "V>E", fill="white")
        return image

def update_tray_state():
    """Cập nhật icon và tooltip theo trạng thái."""
    if not tray_icon:
        return
        
    hk = config.config.get("hotkey", "f2").upper()
    eng_status = engine.get_status()
    
    if eng_status["is_loading"]:
        model_status = "Đang tải..."
    elif eng_status["vi2en"] and eng_status["en2vi"]:
        model_status = "OK (Đã nạp)"
    else:
        model_status = "Ngủ/Thiếu Model"
        
    status_text = "Đang Tắt" if not is_enabled else "Bật"
    tray_icon.title = f"Viet2EN [{status_text}] | Phím: {hk} | Model: {model_status}"
    tray_icon.icon = create_image(is_translating)

def notify(title, message):
    if tray_icon:
        tray_icon.notify(message, title)

def set_translating_state(state):
    global is_translating
    is_translating = state
    update_tray_state()

def run_tray(toggle_callback, settings_callback, quit_callback):
    global tray_icon
    
    def on_toggle(icon, item):
        global is_enabled
        is_enabled = not is_enabled
        toggle_callback(is_enabled)
        update_tray_state()
        
    menu = pystray.Menu(
        pystray.MenuItem("Bật dịch", on_toggle, checked=lambda item: is_enabled),
        pystray.MenuItem("Cài đặt", settings_callback),
        pystray.MenuItem("Thoát", quit_callback)
    )

    image = create_image(False)
    hk = config.config.get("hotkey", "f2").upper()
    tray_icon = pystray.Icon("Viet2EN", image, f"Viet2EN | Phím: {hk} | Model: Đang kiểm tra...", menu)
    
    update_tray_state()
    threading.Thread(target=tray_icon.run, daemon=True).start()
    return tray_icon
