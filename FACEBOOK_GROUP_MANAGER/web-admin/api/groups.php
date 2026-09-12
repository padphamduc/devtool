<?php
declare(strict_types=1);

require_once dirname(__DIR__) . '/lib.php';

$origin = $_SERVER['HTTP_ORIGIN'] ?? '';
if ($origin !== '' && (ALLOWED_ORIGINS === [] || in_array($origin, ALLOWED_ORIGINS, true))) {
    header('Access-Control-Allow-Origin: ' . $origin);
    header('Vary: Origin');
}
header('Access-Control-Allow-Headers: Content-Type, X-API-Key');
header('Access-Control-Allow-Methods: POST, OPTIONS');
if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') exit;
if ($_SERVER['REQUEST_METHOD'] !== 'POST') json_response(['ok' => false, 'error' => 'Method not allowed'], 405);

$apiKey = $_SERVER['HTTP_X_API_KEY'] ?? '';
if (!hash_equals(EXTENSION_API_KEY, $apiKey)) json_response(['ok' => false, 'error' => 'API key không hợp lệ'], 401);

$payload = json_decode((string) file_get_contents('php://input'), true);
if (!is_array($payload)) json_response(['ok' => false, 'error' => 'JSON không hợp lệ'], 400);
$deviceName = trim((string) ($payload['device_name'] ?? ''));
$groups = $payload['groups'] ?? null;
if ($deviceName === '' || mb_strlen($deviceName) > 120 || !is_array($groups)) json_response(['ok' => false, 'error' => 'Thiếu device_name hoặc groups'], 422);
if (count($groups) > 10000) json_response(['ok' => false, 'error' => 'Tối đa 10.000 nhóm mỗi lần đồng bộ'], 413);

$pdo = db();
$pdo->beginTransaction();
try {
    if (is_sqlite()) {
        $pdo->prepare("INSERT INTO devices (name, last_sync_at) VALUES (?, datetime('now')) ON CONFLICT(name) DO UPDATE SET last_sync_at=datetime('now')")->execute([$deviceName]);
        $findDevice = $pdo->prepare('SELECT id FROM devices WHERE name=?');
        $findDevice->execute([$deviceName]);
        $deviceId = (int) $findDevice->fetchColumn();
        $upsert = $pdo->prepare("INSERT INTO facebook_groups (device_id, facebook_key, facebook_id, group_name, group_url, image_url, last_seen_at) VALUES (?, ?, ?, ?, ?, ?, datetime('now')) ON CONFLICT(device_id, facebook_key) DO UPDATE SET facebook_id=excluded.facebook_id, group_name=excluded.group_name, group_url=excluded.group_url, image_url=excluded.image_url, last_seen_at=datetime('now'), updated_at=datetime('now')");
    } else {
        $stmt = $pdo->prepare('INSERT INTO devices (name, last_sync_at) VALUES (?, NOW()) ON DUPLICATE KEY UPDATE last_sync_at = NOW(), id = LAST_INSERT_ID(id)');
        $stmt->execute([$deviceName]);
        $deviceId = (int) $pdo->lastInsertId();
        $upsert = $pdo->prepare('INSERT INTO facebook_groups (device_id, facebook_key, facebook_id, group_name, group_url, image_url, last_seen_at) VALUES (?, ?, ?, ?, ?, ?, NOW()) ON DUPLICATE KEY UPDATE facebook_id=VALUES(facebook_id), group_name=VALUES(group_name), group_url=VALUES(group_url), image_url=VALUES(image_url), last_seen_at=NOW()');
    }
    $received = 0;
    foreach ($groups as $group) {
        if (!is_array($group)) continue;
        $url = trim((string) ($group['url'] ?? ''));
        $name = trim((string) ($group['name'] ?? ''));
        if ($name === '' || !preg_match('~^https://(www|web)\.facebook\.com/groups/([^/?#]+)~i', $url, $match)) continue;
        $upsert->execute([$deviceId, strtolower($match[2]), trim((string) ($group['id'] ?? '')) ?: null, mb_substr($name, 0, 255), mb_substr($url, 0, 500), trim((string) ($group['image'] ?? '')) ?: null]);
        $received++;
    }
    $pdo->prepare('INSERT INTO sync_logs (device_id, received_count, ip_address) VALUES (?, ?, ?)')->execute([$deviceId, $received, $_SERVER['REMOTE_ADDR'] ?? null]);
    $pdo->commit();
    json_response(['ok' => true, 'received' => $received]);
} catch (Throwable $error) {
    $pdo->rollBack();
    error_log($error->getMessage());
    json_response(['ok' => false, 'error' => 'Lỗi lưu dữ liệu'], 500);
}
