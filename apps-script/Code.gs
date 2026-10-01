// Open Freelance Agent — Google Sheet backend (bound Apps Script).
// Paste this into Extensions > Apps Script of YOUR copy of the tracker sheet.
// Replace OWNER_EMAIL with your own email, then run setupTracker once
// and approve the permission prompts (it is your own script asking for
// send-email + spreadsheet access on YOUR account).

var OWNER_EMAIL = 'your-email@gmail.com';
var SENDER_NAME = 'Freelance Agent';
var LOG_TAB = 'السجل';
var TODAY_TAB = 'قايمة اليوم';
var APPROVALS_TAB = 'الموافقات';

function setupTracker() {
  var ss = SpreadsheetApp.getActive();
  if (!ss.getSheetByName(LOG_TAB)) {
    var sh = ss.insertSheet(LOG_TAB);
    sh.appendRow(['التاريخ', 'ID', 'المنصة', 'النوع', 'العنوان', 'الرابط', 'الميزانية',
                  'سعري المقدم', 'الحالة', 'آخر تطور', 'الخطوة الجاية', 'موافقة']);
  }
  if (!ss.getSheetByName(TODAY_TAB)) {
    var sh = ss.insertSheet(TODAY_TAB);
    sh.appendRow(['التاريخ', 'ID', 'المنصة', 'العنوان', 'الرابط', 'السبب', 'قرار', 'ملاحظات']);
  }
  if (!ss.getSheetByName(APPROVALS_TAB)) {
    var sh = ss.insertSheet(APPROVALS_TAB);
    sh.appendRow(['id', 'status', 'time', 'note']);
  }
  Logger.log('TRACKER_READY');
}

// Append one row to the log (dedup by id/url/title markers in cols B/E/F).
function logToday() {
  var ss = SpreadsheetApp.getActive();
  var sh = ss.getSheetByName(LOG_TAB);
  var rows = [
    ['2026-01-01', 'example-1', 'platform', 'type', 'title', 'url', 'budget', 'my price',
     'مقدّم', 'submitted after approval', 'follow up', '✓']
  ];
  var data = sh.getDataRange().getValues();
  function exists(marker) {
    for (var i = 0; i < data.length; i++) {
      if (String(data[i][1]).indexOf(marker) !== -1 || String(data[i][4]).indexOf(marker) !== -1 ||
          String(data[i][5]).indexOf(marker) !== -1) return true;
    }
    return false;
  }
  var added = 0;
  for (var j = 0; j < rows.length; j++) {
    if (!exists(rows[j][1])) { sh.appendRow(rows[j]); added++; }
  }
  Logger.log('ADDED=' + added + ' LASTROW=' + sh.getLastRow());
}

// Email a proposal for approval (reply with the word "approve" to confirm).
function sendProposalEmail(id, subject, body) {
  var ss = SpreadsheetApp.getActive();
  var sh = ss.getSheetByName(APPROVALS_TAB);
  if (!sh) { sh = ss.insertSheet(APPROVALS_TAB); sh.appendRow(['id', 'status', 'time', 'note']); }
  sh.appendRow([id, 'pending', new Date(), 'email sent']);
  var html = '<div dir=rtl style="font-family:Tahoma,Arial;font-size:15px;line-height:1.9>' +
    '<h3 style=color:#1a73e8>' + subject + '</h3>' +
    '<div style=white-space:pre-wrap;background:#f7f9fc;border:1px solid #e0e6ef;border-radius:10px;padding:16px>' + body + '</div>' +
    '<p style=margin-top:24px><b>Reply to this email with the word approve to confirm submission.</b></p></div>';
  MailApp.sendEmail(OWNER_EMAIL, subject, body, {htmlBody: html, name: SENDER_NAME});
  Logger.log('SENT id=' + id);
}

// Mark a proposal as approved in the approvals tab.
function markApproved(id) {
  var ss = SpreadsheetApp.getActive();
  var sh = ss.getSheetByName(APPROVALS_TAB);
  if (!sh) return 'NO_TAB';
  var rows = sh.getDataRange().getValues();
  for (var i = 1; i < rows.length; i++) {
    if (String(rows[i][0]) === String(id)) {
      sh.getRange(i + 1, 2).setValue('approved');
      sh.getRange(i + 1, 3).setValue(new Date());
      return 'MARKED row=' + (i + 1);
    }
  }
  return 'NOT_FOUND';
}
