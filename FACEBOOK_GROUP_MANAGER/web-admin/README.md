# DUC TOOL – Facebook Group Manager

Web PHP/MySQL nhận danh sách nhóm từ Chrome Extension và hiển thị trong trang quản trị.

## Chạy localhost nhanh

1. Cài XAMPP để có PHP nếu máy chưa có.
2. Chạy `START_LOCALHOST.bat`.
3. Đăng nhập `http://127.0.0.1:8787` bằng mật khẩu mặc định `DUC@12345`.
4. Extension dùng API `http://127.0.0.1:8787/api/groups.php` và key `DUC_LOCAL_API_2026_CHANGE_ME`.

Hãy đổi mật khẩu và API key trong `config.php`, kể cả khi chỉ chạy trong mạng nội bộ.

## Cài lên hosting

1. Tạo database MySQL rồi import `db.sql`.
2. Sao chép `config.example.php` thành `config.php`.
3. Điền thông tin database, `EXTENSION_API_KEY` và mã băm mật khẩu quản trị.
4. Upload toàn bộ thư mục `web-admin` lên hosting.
5. Trong extension, nhập URL dạng `https://domain.com/web-admin/api/groups.php` cùng API key.

Không commit `config.php`. Không lưu cookie hoặc mật khẩu Facebook trên máy chủ.
