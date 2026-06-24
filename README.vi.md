# Viet2EN Hotkey Translator

**🌐 [English](README.md) | Tiếng Việt**

**Dịch ngay tại chỗ bạn đang gõ — bôi đen, nhấn F2, xong.**

![Python](https://img.shields.io/badge/Python-3.12-blue?logo=python&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green)
![Platform](https://img.shields.io/badge/Platform-Windows-0078D6?logo=windows&logoColor=white)

---



## 📑 Mục lục

- [Tính năng](#-tính-năng)
- [Yêu cầu hệ thống](#-yêu-cầu-hệ-thống)
- [Cài đặt](#-cài-đặt)
- [Cách sử dụng](#-cách-sử-dụng)
- [Cấu hình nâng cao](#-cấu-hình-nâng-cao)
- [Troubleshooting](#-troubleshooting)
- [Contributing](#-contributing)
- [License & Credits](#-license--credits)

---

## ✨ Tính năng

- ⚡ **Dịch tức thì bằng phím tắt** — bôi đen text ở bất kỳ app nào, nhấn `F2`, kết quả dán đè ngay tại chỗ. Không cần mở trình duyệt, không cần copy-paste qua Google Translate.
- 🔌 **100% offline** — model dịch chạy cục bộ trên máy bạn. Không gửi dữ liệu đi đâu, không cần internet sau khi cài model.
- 🧠 **Tự nhận diện chiều dịch** — gõ tiếng Việt thì dịch sang Anh, gõ tiếng Anh thì dịch sang Việt. Không cần chọn tay.
- 💤 **Tự giải phóng RAM khi rảnh** — model tự unload khỏi bộ nhớ nếu bạn không dịch gì trong 30 phút (cấu hình được), tự load lại lần tiếp theo cần.
- 🚀 **Khởi động gần như ngay lập tức** — app không load model khi mở, chỉ load lần đầu bạn nhấn dịch (Lazy Load).
- 🔒 **Chống mở trùng** — chạy app lần hai sẽ tự thoát, không tạo bản sao.
- 📋 **Bảo toàn clipboard** — sau khi dịch xong, clipboard cũ của bạn được tự động khôi phục.

---

## 💻 Yêu cầu hệ thống

| Thành phần | Yêu cầu |
|---|---|
| Hệ điều hành | Windows 10 / 11 |
| Python | 3.10+ (nếu chạy từ source) |
| Dung lượng đĩa | ~150 MB cho 2 model dịch (VI↔EN) |
| RAM | ~500 MB khi model đang load |

---

## 📦 Cài đặt

### Cách 1 — Chạy bản `.exe` đóng gói sẵn

1. Tải file `Viet2EN.exe` từ trang [Releases](https://github.com/Duon-gg/Viet2EN_Hotkey_Translator/releases)
2. Đặt vào thư mục riêng (ví dụ `C:\Tools\Viet2EN\`)
3. Chạy `Viet2EN.exe` — icon xuất hiện ở khay hệ thống (system tray)
4. Lần đầu: cửa sổ cài đặt tự mở → click **Tải mô hình (Download Model)** để tải model dịch (~150 MB, cần internet cho bước này)

### Cách 2 — Chạy từ source

```bash
git clone https://github.com/Duon-gg/Viet2EN_Hotkey_Translator.git
cd Viet2EN_Hotkey_Translator

python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

copy config.example.json config.json
python main.py
```

Lần chạy đầu tiên, cửa sổ cài đặt sẽ tự mở để bạn tải model dịch. Sau khi tải xong, các lần chạy sau không cần internet nữa.

Chạy ẩn (không hiện console): click đúp file `run.vbs`.

---

## 🎯 Cách sử dụng

1. Bôi đen đoạn văn bản cần dịch — ở bất kỳ app nào (trình duyệt, Word, Notepad, IDE...)
2. Nhấn **`F2`**
3. Text hiện `...` trong lúc xử lý, rồi tự thay bằng bản dịch

Không cần chuyển tab, không cần mở app nào khác. Clipboard cũ được tự động khôi phục sau khi dán.

### Phím tắt & tùy chọn

| Tùy chọn | Mặc định | Thay đổi qua |
|---|---|---|
| Phím dịch | `F2` | Cài đặt (chuột phải icon tray → **Cài đặt**) |
| Phím khả dụng | `F2` đến `F8` | Dropdown trong cửa sổ Cài đặt |
| Bật / tắt dịch | Bật | Menu chuột phải icon tray → **Bật dịch** |

---

## ⚙ Cấu hình nâng cao

Sửa file `config.json` ở thư mục gốc (hoặc dùng giao diện Cài đặt):

| Field | Mô tả | Mặc định |
|---|---|---|
| `hotkey` | Phím tắt kích hoạt dịch. Nhận giá trị `f2` đến `f8` | `"f2"` |
| `startup` | Tự chạy khi khởi động Windows | `false` |
| `auto_unload_minutes` | Số phút không dùng trước khi tự giải phóng model khỏi RAM | `30` |
| `restore_delay_seconds` | Thời gian chờ (giây) trước khi khôi phục lại clipboard gốc sau khi dán kết quả | `0.8` |

> Không có `config.json`? App tự tạo với giá trị mặc định. Hoặc copy từ `config.example.json`.

---

## 🔧 Troubleshooting

**Nhấn F2 nhưng không có phản hồi gì:**
→ Kiểm tra icon tray có hiện không. Nếu không thấy, app chưa chạy hoặc đã crash — mở file `viet2en.log` để xem chi tiết lỗi.

**Dịch không hoạt động trên một số cửa sổ (Task Manager, Command Prompt chạy Admin...):**
→ Giới hạn bảo mật của Windows: process chạy quyền User không thể gửi phím tắt vào process chạy quyền Administrator. Cách xử lý: tắt Viet2EN, chuột phải → **Run as Administrator** rồi chạy lại.

**Lần đầu nhấn F2 bị chậm (~2-5 giây):**
→ Bình thường. Model dịch dùng Lazy Load — chỉ nạp vào RAM lần đầu bạn dịch. Các lần sau nhanh hơn nhiều, cho tới khi model tự unload do không sử dụng.

**Tải model online bị lỗi:**
→ Mở Cài đặt → dùng nút **Cài từ file (.argosmodel)** để cài thủ công. Tải file `.argosmodel` cho cặp `vi→en` và `en→vi` từ [Argos Translate packages](https://www.argosopentech.com/argospm/index/).

---

## 🤝 Contributing

Phát hiện bug, có ý tưởng cải thiện, hoặc muốn gửi pull request — mở [Issue](https://github.com/Duon-gg/Viet2EN_Hotkey_Translator/issues) trên GitHub. Mọi đóng góp đều được hoan nghênh.

---

## 📄 License & Credits

Phát hành theo giấy phép [MIT](LICENSE).

Dự án được xây dựng trên nền các thư viện mã nguồn mở:

- [Argos Translate](https://github.com/argosopentech/argos-translate) — engine dịch offline
- [CTranslate2](https://github.com/OpenNMT/CTranslate2) — runtime inference cho model dịch
- [pystray](https://github.com/moses-palmer/pystray) — system tray icon
- [keyboard](https://github.com/boppreh/keyboard) — bắt phím tắt toàn hệ thống
- [pyperclip](https://github.com/asweigart/pyperclip) — tương tác clipboard
