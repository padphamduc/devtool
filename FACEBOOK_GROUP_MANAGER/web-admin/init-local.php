<?php
declare(strict_types=1);
require_once __DIR__ . '/lib.php';
if (!is_dir(__DIR__ . '/data')) mkdir(__DIR__ . '/data', 0775, true);
db()->exec((string) file_get_contents(__DIR__ . '/db.sqlite.sql'));
echo "DUC TOOL: Local database ready.\n";
