# Vitra 2.0

**[English](README.md) | Tiếng Việt**

Công cụ dịch Việt ↔ Anh cho Windows: bôi đen nội dung, nhấn hotkey và nhận bản dịch ngay trong ứng dụng đang dùng khi ô đích có thể chỉnh sửa; nếu không an toàn để thay trực tiếp, bản dịch được copy âm thầm vào clipboard. Vitra ưu tiên xử lý offline, đồng thời có extension để đọc những website chặn copy/bôi đen và OCR cho ảnh, canvas hoặc PDF scan.

## Điểm mới trong 2.0

- Pipeline lấy nội dung: **Browser DOM → Windows UI Automation → Clipboard → OCR**.
- Không còn dán `...` rồi Backspace; chỉ thay nội dung sau khi dịch thành công.
- Kiểm tra cửa sổ/control vẫn đúng trước khi paste; nếu người dùng đổi vị trí hoặc không thể thay trực tiếp, kết quả chỉ được copy vào clipboard.
- Clipboard transaction giữ nhiều format và không ghi đè clipboard mới của người dùng.
- Engine thread-safe, preload nền, ba chế độ hiệu năng và tùy chọn CPU/CUDA/INT8.
- Nhận diện tiếng Việt không dấu tốt hơn và có bước phục hồi dấu từ vựng phổ biến.
- Glossary bảo vệ thuật ngữ, URL, email, code và placeholder.
- Chrome/Edge Manifest V3 extension xử lý popup, iframe và nhiều cơ chế anti-copy.
- Windows UI Automation `TextPattern` fallback.
- RapidOCR/ONNX Runtime chạy offline, kèm giao diện chọn vùng màn hình.
- Config/log trong `%LOCALAPPDATA%\Vitra`, atomic config write và rotating log.
- Pytest, Ruff, mypy, GitHub Actions và PyInstaller onedir build.

## Yêu cầu

- Windows 10/11.
- Python 3.12 nếu chạy từ source.
- Khoảng 154 MB cho hai model Argos; OCR và Python runtime làm bản đóng gói lớn hơn.
- Khoảng 500 MB RAM khi cả hai model đang nạp.

## Chạy từ source

```bat
git clone https://github.com/Duon-gg/Viet2EN_Hotkey_Translator.git
cd Viet2EN_Hotkey_Translator
py -3.12 -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
python main.py
```

Lần đầu chạy, Settings tự mở nếu thiếu model. Chọn **Tải đủ model VI↔EN** hoặc cài từng file `.argosmodel`.

## Cách dùng

- `F2`: tự nhận diện chiều dịch.
- `Ctrl+F2`: buộc Việt → Anh.
- `Shift+F2`: buộc Anh → Việt.
- Tray → **Dịch vùng màn hình (OCR)**: kéo chuột quanh ảnh/canvas/PDF scan, kết quả được copy vào clipboard.
- Tray → **Cài đặt**: hiệu năng, model, browser bridge, OCR và glossary.

Hotkey gốc có thể đổi trong Settings. Nếu hotkey đã là một tổ hợp, hai hotkey ép chiều sẽ không được đăng ký tự động.

## Cài extension chống anti-copy

1. Mở `chrome://extensions` hoặc `edge://extensions`.
2. Bật **Developer mode**.
3. Chọn **Load unpacked** và trỏ tới thư mục `browser_extension`.
4. Trong Settings của Vitra Desktop, copy **Bridge token** và ghi lại port.
5. Mở Options của extension, nhập đúng token/port rồi lưu.
6. Khi thử `test_anti_copy.html`, mở Details của extension và bật **Allow access to file URLs**.

Extension chạy từ `document_start`, tự hoạt động trong popup không có toolbar và mọi iframe phù hợp. Kết nối chỉ bind `127.0.0.1`, yêu cầu token và từ chối Origin không phải extension.

## Chế độ hiệu năng

- **Hiệu năng:** giữ model trong RAM.
- **Cân bằng:** preload nền và unload sau thời gian cấu hình.
- **Tiết kiệm RAM:** chỉ nạp model khi cần.

`compute_type=auto` để CTranslate2 tự chọn. Có thể thử `int8` trên CPU và `device=cuda` trên máy NVIDIA tương thích; nên benchmark trước khi dùng mặc định.

## Glossary

Mỗi dòng trong tab Glossary:

```text
hotkey = phím tắt
clipboard = bảng tạm
deployment = triển khai
```

Vitra cũng bảo vệ URL, email, code inline và placeholder như `{name}`, `{{value}}`, `%s`.

## Dữ liệu và quyền riêng tư

- Argos và RapidOCR chạy cục bộ.
- Browser bridge chỉ lắng nghe trên `127.0.0.1`.
- Log không ghi nội dung được dịch.
- Extension cần quyền trang để đọc DOM; có thể tắt hoàn toàn trong Settings hoặc Options.
- Công cụ chỉ xử lý nội dung người dùng đã có quyền xem; không vượt đăng nhập, mã hóa hoặc DRM.

## Cấu hình và log

```text
%LOCALAPPDATA%\Vitra\config.json
%LOCALAPPDATA%\Vitra\logs\vitra.log
```

`config.json` cũ cạnh ứng dụng được tự động migrate. Model vẫn nằm trong thư mục `models` cạnh source/EXE để hỗ trợ offline bundle.

## Kiểm thử

```bat
python -m pytest -q
python -m ruff check main.py core ui utils scripts tests
python -m mypy main.py core ui utils scripts
node --check browser_extension\service-worker.js
node --check browser_extension\content.js
```

Kiểm thử end-to-end trên Chromium thật với trang anti-copy, extension, bridge và model dịch:

```bat
python -m playwright install chromium
python scripts\test_anti_copy_browser.py
```

`test_anti_copy.html` mở popup tối giản và chặn bôi đen, copy, paste, cut, chuột phải, kéo thả cùng các phím tắt phổ biến.

## Build

```bat
build.bat
```

Tạo bản onedir tại `dist\Vitra\`. Để copy model vào bundle:

```bat
build.bat --offline
```

Onedir được chọn để giảm thời gian khởi động và để thư mục extension có thể được load trực tiếp. Build chạy `pip check`, Ruff, mypy và pytest trước PyInstaller, sau đó chép extension cùng toàn bộ license/notice của dependency runtime.

## Giới hạn

- Chất lượng phụ thuộc model Argos; câu không dấu hoặc rất ngắn vẫn có thể mơ hồ.
- Extension không chạy trên một số trang đặc quyền của trình duyệt, profile khác hoặc WebView không cài extension.
- UI Automation phụ thuộc ứng dụng có expose `TextPattern`.
- OCR phù hợp với nội dung nhìn thấy; kết quả dịch OCR được copy vào clipboard và không tự thay text ở vị trí không xác định.
- Một số format clipboard dùng native handle không thể snapshot hoàn hảo; Vitra bảo toàn các format dữ liệu phổ biến và tránh restore khi clipboard đã thay đổi.

## License

Phần mã nguồn riêng của Vitra phát hành theo MIT. Bộ dependency runtime có MiniSBD dùng AGPL-3.0, vì vậy cần xem nghĩa vụ phân phối trước khi công bố bản binary đã đóng gói. Xem [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) để biết chi tiết và attribution model OPUS-MT/CC BY 4.0.
