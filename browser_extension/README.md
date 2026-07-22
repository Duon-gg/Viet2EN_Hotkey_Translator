# Vitra Bridge

1. Mở `chrome://extensions` hoặc `edge://extensions`.
2. Bật **Developer mode**.
3. Chọn **Load unpacked** và trỏ tới thư mục `browser_extension`.
4. Mở **Details** và bật **Allow access to file URLs** nếu muốn thử `test_anti_copy.html`.
5. Mở Options của extension, nhập port và token hiển thị trong Settings của Vitra Desktop.

Extension chạy ở `document_start`, trong mọi frame phù hợp, nên vẫn hoạt động trong popup không có thanh công cụ. Kết nối WebSocket chỉ tới `127.0.0.1` và được xác thực bằng token.
