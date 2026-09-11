# DUCTOOL

Ứng dụng Windows gộp các công cụ Facebook, Messenger và đổi tên ảnh trong một giao diện.

## Tải cho khách hàng

Tải bản mới nhất tại:

https://github.com/padphamduc/devtool/releases/latest

Khách hàng chỉ cần tải **`DUCTOOL-Setup.exe`** và mở bộ cài:

- Cài ứng dụng vào tài khoản Windows hiện tại, không yêu cầu cài Python.
- Tự tạo biểu tượng **DUCTOOL** ngoài Desktop và trong Start Menu.
- Tự mở ứng dụng sau khi cài xong.
- Giữ nguyên cấu hình và dữ liệu khi nâng cấp.

`DUCTOOL.exe` là bản portable dành cho trường hợp không muốn cài đặt.

## Tự động cập nhật

Ứng dụng kiểm tra GitHub Releases khi khởi động và khi người dùng bấm **Kiểm tra cập nhật**. Khi có phiên bản cao hơn, ứng dụng tải bộ cài mới, kiểm tra SHA-256, cài ngầm rồi mở lại.

Để phát hành phiên bản mới:

1. Sửa trường `version` và `changelog` trong `version.json`.
2. Push lên nhánh `main`.
3. GitHub Actions tự build `DUCTOOL.exe`, `DUCTOOL-Setup.exe`, tạo checksum và phát hành GitHub Release.

## Chạy từ mã nguồn

Yêu cầu Windows và Python 3.12:

```bat
SETUP_APP.bat
START_DUCTOOL.bat
```

## Bảo mật

`config.json`, `messages.db`, log và token cá nhân không được đưa lên GitHub. Chỉ commit `config.example.json` với các trường bí mật để trống.
