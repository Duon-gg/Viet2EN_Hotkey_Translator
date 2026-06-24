import time
import keyboard
import pyperclip
import re
from utils import config

def safe_paste(max_retries=3, delay=0.1):
    """Lấy nội dung Clipboard với cơ chế Retry chống nhiễu"""
    for attempt in range(max_retries):
        try:
            return pyperclip.paste()
        except Exception as e:
            if attempt == max_retries - 1:
                print(f"[Clipboard] Lỗi paste: {e}")
                return ""
            time.sleep(delay)
    return ""

def safe_copy(text, max_retries=3, delay=0.1):
    """Copy nội dung vào Clipboard với cơ chế Retry"""
    for attempt in range(max_retries):
        try:
            pyperclip.copy(text)
            return True
        except Exception as e:
            if attempt == max_retries - 1:
                print(f"[Clipboard] Lỗi copy: {e}")
                return False
            time.sleep(delay)
    return False

def wait_for_clipboard_change(old_value, timeout=1.5, interval=0.03):
    """Poll clipboard cho đến khi nội dung thay đổi so với old_value, hoặc hết timeout."""
    start = time.time()
    while time.time() - start < timeout:
        current = safe_paste()
        if current != old_value:
            return current
        time.sleep(interval)
    return None

def smart_strip(text):
    """
    Bóc tách các khoảng trắng/xuống dòng ở đầu và cuối chuỗi.
    Trả về: (leading_space, stripped_text, trailing_space)
    """
    match = re.match(r'^(\s*)(.*?)(\s*)$', text, re.DOTALL)
    if match:
        return match.group(1), match.group(2), match.group(3)
    return "", text, ""

def execute_translation_cycle(engine_translate_func, on_status_notify):
    """Thực thi luồng bôi đen, copy, dịch, dán"""
    
    # [Khôi phục Clipboard] Lưu lại clipboard cũ trước khi copy
    original_clipboard = safe_paste()

    # Lấy text đang bôi đen
    safe_copy('')
    if original_clipboard != '':
        wait_for_clipboard_change(original_clipboard, timeout=0.5, interval=0.03)

    keyboard.send('ctrl+c')
    # Đợi clipboard nhận dữ liệu mới từ Ctrl+C (thay đổi so với rỗng)
    raw_text = wait_for_clipboard_change('', timeout=1.0, interval=0.03)
    
    if raw_text is None:
        print("[Warning] Timeout chờ clipboard thay đổi sau Ctrl+C. Không thể copy từ ứng dụng đích.")
        on_status_notify("Viet2EN", "Không thể dịch — nếu ứng dụng đích đang chạy quyền Administrator, hãy chạy Viet2EN với quyền Administrator tương ứng.")
        safe_copy(original_clipboard)
        return

    if not raw_text.strip():
        on_status_notify("Viet2EN", "Chưa bôi đen văn bản cần dịch")
        safe_copy(original_clipboard)
        return

    # Tách khoảng trắng để bảo toàn định dạng
    leading_space, text_to_translate, trailing_space = smart_strip(raw_text)

    # Hiện placeholder "..." trong khi dịch
    safe_copy("...")
    wait_for_clipboard_change(raw_text, timeout=0.5, interval=0.03)
    keyboard.send('ctrl+v')
    time.sleep(0.1)

    try:
        # Gọi engine dịch (có thể tốn thời gian lazy load ở lần đầu)
        translated = engine_translate_func(text_to_translate)

        if not translated or translated.strip() == text_to_translate:
            # Nếu kết quả giống hệt → có thể đã là tiếng Anh
            on_status_notify("Viet2EN", "Đã là tiếng Anh hoặc không dịch được")
            safe_copy(raw_text)
            wait_for_clipboard_change("...", timeout=0.5, interval=0.03)
        else:
            # Gắn lại khoảng trắng đầu/cuối
            final_text = leading_space + translated.strip() + trailing_space
            safe_copy(final_text)
            wait_for_clipboard_change("...", timeout=0.5, interval=0.03)

    except Exception as e:
        on_status_notify("Viet2EN", f"Lỗi dịch: {str(e)[:60]}")
        safe_copy(raw_text)
        wait_for_clipboard_change("...", timeout=0.5, interval=0.03)

    # Paste kết quả đè lên "..."
    # Dùng Backspace 3 lần để xóa chắc chắn 3 dấu "..." vừa dán
    time.sleep(0.1)
    for _ in range(3):
        keyboard.send('backspace')
        time.sleep(0.02)
    time.sleep(0.1)
    keyboard.send('ctrl+v')
    
    # [Khôi phục Clipboard] Trả lại clipboard cũ sau khi dán xong
    # Trễ cấu hình để app đích dán xong trước khi khôi phục
    delay = config.config.get("restore_delay_seconds", 0.8)
    time.sleep(delay)
    safe_copy(original_clipboard)

