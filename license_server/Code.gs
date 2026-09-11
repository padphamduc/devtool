// Deploy as a Web app executing as the owner of this license spreadsheet.
const LICENSE_SHEET_ID = '1-M7C_FKjCYAdeWOCKgYjuDRluyTNYfofpuJlhU5Jcr8';
const LICENSE_TAB_ID = 0;

function normalizeHeader(value) {
  return String(value).normalize('NFD').replace(/[\u0300-\u036f]/g, '')
    .replace(/đ/g, 'd').replace(/Đ/g, 'D').toLowerCase().replace(/[^a-z0-9]/g, '');
}

function licenseColumns(headers) {
  const aliases = {key: ['makey', 'key', 'licensekey'], hwid: ['mamayhwid', 'mamay', 'hwid'],
    expiry: ['ngayhethan', 'expiredate', 'expirydate'], status: ['trangthai', 'status']};
  const columns = {};
  Object.keys(aliases).forEach(name => {
    const found = headers.map((h, i) => aliases[name].includes(normalizeHeader(h)) ? i : -1).filter(i => i >= 0);
    if (found.length !== 1) throw new Error('Cấu hình cột bản quyền chưa hợp lệ.');
    columns[name] = found[0];
  });
  return columns;
}

function licenseDate(value, zone) {
  if (value instanceof Date && !isNaN(value.getTime())) return Utilities.formatDate(value, zone, 'yyyy-MM-dd');
  const text = String(value).trim();
  let match = text.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  let year, month, day;
  if (match) [, year, month, day] = match;
  else {
    match = text.match(/^(\d{2})[/-](\d{2})[/-](\d{4})$/);
    if (!match) return null;
    [, day, month, year] = match;
  }
  const date = new Date(Date.UTC(+year, +month - 1, +day));
  return date.getUTCFullYear() === +year && date.getUTCMonth() === +month - 1 && date.getUTCDate() === +day
    ? `${year}-${month}-${day}` : null;
}

function checkLicenseRequest(payload) {
  const key = String(payload.key || '').trim().toUpperCase();
  const hwid = String(payload.hwid || '').trim().toUpperCase();
  const action = String(payload.action || 'check');
  if (!key || key.length > 200 || !/^DUC-[A-F0-9]{4}-[A-F0-9]{4}-[A-F0-9]{4}$/.test(hwid))
    return {status: 'INVALID_INPUT', message: 'Vui lòng nhập key và mã máy hợp lệ.'};
  if (!['activate', 'check'].includes(action)) return {status: 'INVALID_INPUT', message: 'Yêu cầu không hợp lệ.'};
  const lock = LockService.getScriptLock();
  if (!lock.tryLock(10000)) return {status: 'BUSY', message: 'Hệ thống đang bận. Vui lòng thử lại.'};
  try {
    const book = SpreadsheetApp.openById(LICENSE_SHEET_ID);
    const sheet = book.getSheets().find(item => item.getSheetId() === LICENSE_TAB_ID);
    if (!sheet) throw new Error('Không có bảng bản quyền.');
    const rows = sheet.getDataRange().getValues();
    const col = licenseColumns(rows[0]);
    const matches = [];
    for (let i = 1; i < rows.length; i++)
      if (String(rows[i][col.key]).trim().toUpperCase() === key) matches.push(i);
    if (!matches.length) return {status: 'NOT_FOUND', message: 'Key không hợp lệ.'};
    if (matches.length !== 1) return {status: 'ERROR', message: 'Key bị trùng trong hệ thống. Liên hệ Admin.'};
    const index = matches[0], row = rows[index];
    const state = normalizeHeader(row[col.status]);
    if (['blocked', 'khoa', 'block'].includes(state)) return {status: 'BLOCKED', message: 'Key đã bị khóa.'};
    if (!['active', 'hoatdong', 'ok'].includes(state)) return {status: 'ERROR', message: 'Key chưa được phép kích hoạt.'};
    const zone = book.getSpreadsheetTimeZone();
    const expiry = licenseDate(row[col.expiry], zone);
    if (!expiry) return {status: 'ERROR', message: 'Ngày hết hạn không hợp lệ. Liên hệ Admin.'};
    const today = Utilities.formatDate(new Date(), zone, 'yyyy-MM-dd');
    if (today > expiry) return {status: 'EXPIRED', expire_date: expiry, message: 'Key đã hết hạn.'};
    const assigned = String(row[col.hwid] || '').trim().toUpperCase();
    if (assigned && assigned !== hwid) return {status: 'HWID_MISMATCH', message: 'Key đã được kích hoạt trên máy khác.'};
    if (!assigned) {
      if (action !== 'activate') return {status: 'NOT_ACTIVATED', message: 'Bấm Kích hoạt bản quyền để đăng ký máy này.'};
      const cell = sheet.getRange(index + 1, col.hwid + 1);
      if (cell.getFormula()) return {status: 'ERROR', message: 'Cột mã máy cần là ô nhập dữ liệu, không dùng công thức.'};
      cell.setValue(hwid);
      SpreadsheetApp.flush(); // Persist the binding before another activation obtains the lock.
    }
    return {status: 'ACTIVE', key, hwid, hwid_bound: true, expire_date: expiry,
      days_left: Math.round((Date.parse(expiry + 'T00:00:00Z') - Date.parse(today + 'T00:00:00Z')) / 86400000),
      message: 'Bản quyền hợp lệ.'};
  } finally {
    lock.releaseLock();
  }
}

function doPost(e) {
  let result;
  try {
    result = checkLicenseRequest(JSON.parse(e.postData.contents));
  } catch (_) {
    result = {status: 'ERROR', message: 'Không thể kiểm tra key. Liên hệ Admin.'};
  }
  return ContentService.createTextOutput(JSON.stringify(result)).setMimeType(ContentService.MimeType.JSON);
}

function doGet() {
  return ContentService.createTextOutput(JSON.stringify({status: 'READY', service: 'DUCTOOL license'}))
    .setMimeType(ContentService.MimeType.JSON);
}
