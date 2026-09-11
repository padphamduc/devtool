const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const source = fs.readFileSync(__dirname + '/Code.gs', 'utf8');
const machine = 'DUC-1111-2222-3333';
const other = 'DUC-AAAA-BBBB-CCCC';
let passed = 0;
function setup({state='ACTIVE', expiry='2099-12-31', hwid='', duplicate=false, formula=false, busy=false}={}) {
  const rows = [['Tên Khách Hàng','Mã Key','Ngày Hết Hạn','Trạng Thái','Ghi Chú','Mã Máy (HWID)'],
    ['Test','KEY-TEST',expiry,state,'',hwid]];
  if (duplicate) rows.push([...rows[1]]);
  let writes = 0, locked = false;
  const context = vm.createContext({Date, Math, JSON, String, Object, Error,
    Utilities: {formatDate: d => d.toISOString().slice(0,10)},
    LockService: {getScriptLock: () => ({tryLock: () => {if (busy) return false; locked=true; return true;}, releaseLock: () => {locked=false;}})},
    SpreadsheetApp: {flush() {assert.ok(locked);}, openById: () => ({getSpreadsheetTimeZone: () => 'Asia/Saigon', getSheets: () => [{
      getSheetId: () => 0, getDataRange: () => ({getValues: () => rows}),
      getRange: (row, col) => ({getFormula: () => formula ? '=A1' : '', setValue: value => {assert.ok(locked); rows[row-1][col-1]=value; writes++;}})
    }]})}
  });
  vm.runInContext(source, context);
  return {call: (action='activate', key='KEY-TEST', hwid=machine) => context.checkLicenseRequest({action,key,hwid}), rows,
    writes: () => writes, locked: () => locked};
}
function test(name, run) {run(); passed++; console.log('OK', name);}
test('First activation binds once; same machine remains valid; second machine refused', () => {
  const s=setup(); assert.equal(s.call('check').status,'NOT_ACTIVATED'); assert.equal(s.writes(),0);
  assert.equal(s.call().status,'ACTIVE'); assert.equal(s.rows[1][5],machine); assert.equal(s.writes(),1);
  assert.equal(s.call('check').status,'ACTIVE'); assert.equal(s.call().status,'ACTIVE');
  assert.equal(s.call('activate','KEY-TEST',other).status,'HWID_MISMATCH'); assert.equal(s.writes(),1); assert.equal(s.locked(),false);
});
for (const [options,status] of [[{state:'BLOCKED'},'BLOCKED'],[{state:''},'ERROR'],[{expiry:'2000-01-01'},'EXPIRED'],
  [{expiry:'2099-02-31'},'ERROR'],[{duplicate:true},'ERROR'],[{formula:true},'ERROR'],[{busy:true},'BUSY']])
  test('Reject without binding: '+JSON.stringify(options), () => {const s=setup(options); assert.equal(s.call().status,status); assert.equal(s.writes(),0);});
test('Wrong key cannot use the HWID of another row', () => {const s=setup({hwid:machine}); assert.equal(s.call('activate','wrong').status,'NOT_FOUND'); assert.equal(s.writes(),0);});
test('Malformed machine rejected', () => {const s=setup(); assert.equal(s.call('activate','KEY-TEST','hostname').status,'INVALID_INPUT');});
console.log(`${passed} server tests passed`);
