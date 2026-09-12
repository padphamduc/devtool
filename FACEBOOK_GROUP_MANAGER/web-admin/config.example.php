<?php
declare(strict_types=1);

// Sao chép file này thành config.php và thay toàn bộ giá trị bên dưới.
const DB_HOST = 'localhost';
const DB_NAME = 'your_database';
const DB_USER = 'your_database_user';
const DB_PASS = 'your_database_password';

// Khóa extension gửi trong header X-API-Key. Hãy dùng chuỗi dài, khó đoán.
const EXTENSION_API_KEY = 'CHANGE_THIS_TO_A_LONG_RANDOM_KEY';

// Tạo bằng: php -r "echo password_hash('mat-khau-admin', PASSWORD_DEFAULT), PHP_EOL;"
const ADMIN_PASSWORD_HASH = '$2y$10$REPLACE_WITH_REAL_PASSWORD_HASH';

// Để [] khi chưa biết extension ID. Khi cài xong nên thêm:
// ['chrome-extension://abcdefghijklmnopabcdefghijklmnop']
const ALLOWED_ORIGINS = [];
