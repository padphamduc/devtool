# Chọn Telegram hoặc Zalo

1. Chạy `START_DUCTOOL.bat`, mở SETUP của Messenger → Telegram / Zalo.
2. Bấm Telegram hoặc Zalo ở mục Kênh nhận thông báo.
3. Chỉ bảng thông tin của kênh đang chọn xuất hiện. Nhập Bot Token và Chat ID của kênh đó; đổi kênh vẫn giữ thông tin đã nhập.
4. Bấm TEST TELEGRAM hoặc TEST ZALO để gửi một tin thử bằng thông tin đang nhập.
5. Bấm LƯU CẤU HÌNH. Thông báo tiếp theo dùng kênh đã lưu, kể cả khi watcher đang chạy. Tin đang gửi dở vẫn dùng kênh cũ.

Mặc định vẫn là Telegram cho cấu hình cũ. Chọn Zalo không yêu cầu cấu hình Telegram. Test một kênh không tự đổi kênh đang lưu.

Zalo dùng Bot Token của Zalo Bot Platform và Chat ID nhận từ sự kiện Bot API, không dùng số điện thoại hay token Zalo OA. Có thể nhắn cho bot rồi đọc `message.chat.id` trong dữ liệu nhận từ `getUpdates` theo tài liệu chính thức.

## Lấy Chat ID Zalo ngay trong tool

Chọn Zalo → nhập Bot Token → bấm **LẤY CHAT ID ZALO** → gửi một tin nhắn cho bot từ cuộc trò chuyện muốn nhận thông báo trong lúc tool chờ khoảng 30 giây. Chat ID từ sự kiện nhận được sẽ được điền vào ô. Bấm **TEST ZALO** để kiểm tra đúng nơi nhận, sau đó **LƯU CẤU HÌNH**. Việc lấy ID chưa tự lưu cấu hình và không gửi tin nhắn.

Nếu chưa nhận được tin, bấm lại và nhắn lại cho bot. Nếu bot đang dùng Webhook, lấy Chat ID từ hệ thống nhận Webhook; tool không tự xóa cấu hình Webhook. Khi đổi token hoặc chuyển sang Telegram trong lúc chờ, kết quả cũ sẽ không được điền.

- https://bot.zaloplatforms.com/docs/apis/sendMessage/
- https://bot.zaloplatforms.com/docs/apis/getUpdates/

Tin dài được chia thành nhiều tin (Zalo tối đa 2.000 ký tự mỗi phần, đếm UTF-16 bảo thủ). Nếu API lỗi, snapshot chưa được đánh dấu gửi thành công và còn đủ mới sẽ được thử lại ở lượt quét tiếp theo. Nếu đã gửi một số phần rồi lỗi, hoặc máy chủ nhận tin nhưng kết nối mất trước khi trả kết quả, thử lại có thể trùng phần đã gửi.

Cấu hình lưu tại `C:\duc\config.json`. Không chia sẻ token trong mã nguồn hoặc ảnh chụp màn hình.

Bản này là mã nguồn; chưa build lại EXE. Chạy từ source sẽ dùng module trong cùng thư mục, tránh nạp nhầm bản cũ tại `C:\duc\code`. Kiểm thử API bằng mock không gửi tin thật. Chạy kiểm thử: `python -m unittest test_notifications test_channel_integration -v`.
