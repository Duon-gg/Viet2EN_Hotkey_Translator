import threading
import time
import re
from utils import config

# Globals để giữ model trong RAM
translation_obj_vi2en = None
translation_obj_en2vi = None
is_model_loaded = False
is_loading = False

# Auto-unload timer
last_used_time = time.time()
unload_timer = None

def get_status():
    return {
        "vi2en": translation_obj_vi2en is not None,
        "en2vi": translation_obj_en2vi is not None,
        "is_loading": is_loading
    }

def _unload_timer_thread():
    """Background thread kiểm tra thời gian không sử dụng để giải phóng RAM"""
    global translation_obj_vi2en, translation_obj_en2vi, is_model_loaded
    while True:
        time.sleep(60) # Kiểm tra mỗi phút
        if not is_model_loaded:
            continue
            
        idle_minutes = (time.time() - last_used_time) / 60.0
        max_idle = config.config.get("auto_unload_minutes", 30)
        
        if idle_minutes >= max_idle:
            print(f"[Engine] Giải phóng model khỏi RAM do không hoạt động trong {max_idle} phút.")
            translation_obj_vi2en = None
            translation_obj_en2vi = None
            is_model_loaded = False
            
            # Kích hoạt callback nếu có module nào đăng ký
            if on_status_change_callback:
                on_status_change_callback()

on_status_change_callback = None

def set_status_callback(callback):
    global on_status_change_callback
    on_status_change_callback = callback

# Khởi động luồng dọn dẹp RAM
threading.Thread(target=_unload_timer_thread, daemon=True).start()

def load_translation_model():
    """Load cả 2 chiều dịch vào RAM. Chỉ load nếu chưa có."""
    global translation_obj_vi2en, translation_obj_en2vi, is_model_loaded, is_loading, last_used_time
    
    if is_model_loaded:
        last_used_time = time.time()
        return True
        
    if is_loading:
        return False
        
    is_loading = True
    if on_status_change_callback:
        on_status_change_callback()
        
    try:
        import argostranslate.translate
        installed = argostranslate.translate.get_installed_languages()
        
        lang_vi = next((l for l in installed if l.code == "vi"), None)
        lang_en = next((l for l in installed if l.code == "en"), None)

        loaded_any = False
        print(f"[Engine] installed languages: {[l.code for l in installed]}")
        for l in installed:
            print(f"[Engine] Lang {l.code} has translations to: {[t.to_lang.code for t in l.translations_from]}")
            
        if lang_vi and lang_en:
            translation_obj_vi2en = lang_vi.get_translation(lang_en)
            if translation_obj_vi2en:
                print("[OK] Model vi->en đã load")
            else:
                print("[ERROR] translation_obj_vi2en IS NONE!")
                
            translation_obj_en2vi = lang_en.get_translation(lang_vi)
            if translation_obj_en2vi:
                print("[OK] Model en->vi đã load")
            else:
                print("[ERROR] translation_obj_en2vi IS NONE!")

        if translation_obj_vi2en is not None and translation_obj_en2vi is not None:
            is_model_loaded = True
            last_used_time = time.time()
            config.config["model_installed"] = True
            config.save_config()
            is_loading = False
            if on_status_change_callback:
                on_status_change_callback()
            return True

        print("[WARN] Chưa cài đặt đủ model vi→en và en→vi")
        is_loading = False
        if on_status_change_callback:
            on_status_change_callback()
        return False
        
    except Exception as e:
        print(f"[ERROR] Không load được model: {e}")
        is_loading = False
        if on_status_change_callback:
            on_status_change_callback()
        return False

def download_model(on_status_update, on_progress_update, on_complete):
    """Tải model vi→en từ Argos package index."""
    def _download():
        global is_loading
        is_loading = True
        if on_status_change_callback:
            on_status_change_callback()
            
        try:
            on_status_update("Đang tải package index...")
            import argostranslate.package
            argostranslate.package.update_package_index()
            available = argostranslate.package.get_available_packages()

            pkg_vi2en = next((p for p in available if p.from_code == "vi" and p.to_code == "en"), None)
            pkg_en2vi = next((p for p in available if p.from_code == "en" and p.to_code == "vi"), None)

            if not pkg_vi2en or not pkg_en2vi:
                on_status_update("❌ Không tìm thấy đủ package trên server")
                is_loading = False
                on_complete(False, "Thiếu package")
                return

            on_status_update("Đang tải model VI->EN...")
            
            import urllib.request
            import tempfile
            import os
            
            temp_dir = tempfile.gettempdir()
            
            def download_pkg(pkg, start_pct, end_pct):
                link = pkg.links[0]
                filename = f"{pkg.from_code}_{pkg.to_code}.argosmodel"
                filepath = os.path.join(temp_dir, filename)
                
                def reporthook(count, block_size, total_size):
                    if total_size > 0:
                        downloaded = count * block_size
                        pct = downloaded / total_size
                        if pct > 1.0: pct = 1.0
                        
                        # Scale to start_pct -> end_pct
                        current_pct = start_pct + (end_pct - start_pct) * pct
                        on_progress_update(current_pct)
                        
                urllib.request.urlretrieve(link, filepath, reporthook)
                return filepath

            path_vi2en = None
            path_en2vi = None
            try:
                if pkg_vi2en: 
                    path_vi2en = download_pkg(pkg_vi2en, 0, 50)
                    argostranslate.package.install_from_path(path_vi2en)
                    
                on_status_update("Đang tải model EN->VI...")
                if pkg_en2vi:
                    path_en2vi = download_pkg(pkg_en2vi, 50, 100)
                    argostranslate.package.install_from_path(path_en2vi)

                is_loading = False
                success = load_translation_model()

                if success:
                    on_status_update("✅ Đã cài đủ mô hình 2 chiều!")
                    on_complete(True, "Thành công")
                else:
                    on_status_update("❌ Cài xong nhưng không load được model")
                    on_complete(False, "Không load được model")
            finally:
                for path in (path_vi2en, path_en2vi):
                    if path and os.path.exists(path):
                        try:
                            os.remove(path)
                            print(f"[Engine] Đã xóa file tạm: {path}")
                        except Exception as e:
                            print(f"[Engine] Lỗi xóa file tạm {path}: {e}")

        except Exception as e:
            is_loading = False
            err = str(e)
            on_status_update(f"❌ Lỗi: {err[:60]}")
            on_complete(False, err)
            
        if on_status_change_callback:
            on_status_change_callback()

    threading.Thread(target=_download, daemon=True).start()

def install_from_local_file(file_path, on_status_update, on_complete):
    """Cài model từ file .argosmodel đã tải sẵn trên máy."""
    def _install():
        global is_loading
        is_loading = True
        if on_status_change_callback:
            on_status_change_callback()
            
        try:
            on_status_update("Đang cài đặt model...")
            import argostranslate.package
            argostranslate.package.install_from_path(file_path)

            is_loading = False
            success = load_translation_model()
            if success:
                on_status_update("✅ Đã nạp model mới thành công!")
                on_complete(True, "Thành công")
            else:
                on_status_update("❌ File không phải model vi→en")
                on_complete(False, "Sai model")
        except Exception as e:
            is_loading = False
            on_status_update(f"❌ Lỗi: {str(e)[:60]}")
            on_complete(False, str(e))
            
        if on_status_change_callback:
            on_status_change_callback()

    threading.Thread(target=_install, daemon=True).start()

def is_vietnamese(text):
    """Sử dụng Regex để phát hiện tiếng Việt"""
    vi_chars = re.compile(r'[àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ]', re.IGNORECASE)
    return bool(vi_chars.search(text))

def translate_text(text):
    """Dịch tự động 2 chiều dựa theo ngôn ngữ nhận diện."""
    global last_used_time
    
    # Lazy load: Nếu model bị auto-unload hoặc chưa nạp, hãy nạp nó.
    if not is_model_loaded:
        success = load_translation_model()
        if not success:
            raise RuntimeError("Model chưa được load đủ (hoặc đang load)")
            
    last_used_time = time.time()
    
    if is_vietnamese(text):
        return translation_obj_vi2en.translate(text)
    else:
        return translation_obj_en2vi.translate(text)
