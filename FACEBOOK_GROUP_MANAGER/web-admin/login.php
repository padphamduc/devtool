<?php
declare(strict_types=1);
require_once __DIR__ . '/lib.php';
if (session_status() !== PHP_SESSION_ACTIVE) session_start();
$error = '';
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $password = (string) ($_POST['password'] ?? '');
    $valid = defined('ADMIN_PASSWORD') ? hash_equals(ADMIN_PASSWORD, $password) : password_verify($password, ADMIN_PASSWORD_HASH);
    if ($valid) {
        session_regenerate_id(true); $_SESSION['duc_admin'] = true; header('Location: index.php'); exit;
    }
    $error = 'Mật khẩu không đúng.';
}
?>
<!doctype html><html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>DUC TOOL Login</title><link rel="stylesheet" href="assets/style.css"></head><body class="login-page"><form method="post" class="login-card"><pre>╔══════════════════════╗
║       DUC TOOL       ║
╚══════════════════════╝</pre><h1>Đăng nhập quản trị</h1><?php if ($error): ?><p class="error"><?= htmlspecialchars($error) ?></p><?php endif; ?><input type="password" name="password" placeholder="Mật khẩu" required autofocus><button>Đăng nhập</button></form></body></html>
