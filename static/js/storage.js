// localStorage helpers — sessions and reeds

const SESSIONS_KEY = 'bassoon_sessions';
const REEDS_KEY    = 'bassoon_reeds';

function _read(key) {
  try { return JSON.parse(localStorage.getItem(key)) ?? []; }
  catch { return []; }
}
function _write(key, val) { localStorage.setItem(key, JSON.stringify(val)); }

function uuid() {
  return crypto.randomUUID?.() ??
    'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => {
      const r = Math.random() * 16 | 0;
      return (c === 'x' ? r : (r & 0x3 | 0x8)).toString(16);
    });
}

// ── Sessions ─────────────────────────────────────────────────────────────────

export function getSessions() { return _read(SESSIONS_KEY); }

export function saveSession(data) {
  const sessions = getSessions();
  const session  = { ...data, id: uuid(), date: data.date ?? new Date().toISOString() };
  sessions.push(session);
  _write(SESSIONS_KEY, sessions);
  return session;
}

export function deleteSession(id) {
  _write(SESSIONS_KEY, getSessions().filter(s => s.id !== id));
}

// ── Reeds ─────────────────────────────────────────────────────────────────────

export function getReeds() { return _read(REEDS_KEY); }

export function saveReed(reed) {
  const reeds = getReeds();
  if (!reed.id) {
    reed = { comparisons: [], ...reed, id: uuid(),
             addedDate: new Date().toISOString().slice(0, 10) };
  }
  const idx = reeds.findIndex(r => r.id === reed.id);
  if (idx >= 0) reeds[idx] = reed; else reeds.push(reed);
  _write(REEDS_KEY, reeds);
  return reed;
}

export function deleteReed(id) {
  _write(REEDS_KEY, getReeds().filter(r => r.id !== id));
}

export function addReedComparison(reedId, comparison) {
  const reeds = getReeds();
  const reed  = reeds.find(r => r.id === reedId);
  if (!reed) return;
  reed.comparisons = reed.comparisons ?? [];
  reed.comparisons.push({ ...comparison, date: new Date().toISOString().slice(0, 10) });
  _write(REEDS_KEY, reeds);
}

// ── Export ────────────────────────────────────────────────────────────────────

export function exportCSV() {
  const sessions = getSessions();
  if (!sessions.length) return;
  const headers = ['date','name','mode','reed','duration','overallScore','low','tenor','high'];
  const rows = sessions.map(s => [
    s.date, s.name ?? '', s.mode ?? '', s.reed ?? '',
    s.duration ?? '', s.overallScore ?? '',
    s.registerScores?.low ?? '', s.registerScores?.tenor ?? '', s.registerScores?.high ?? '',
  ]);
  const escape = v => `"${String(v).replace(/"/g, '""')}"`;
  const csv = [headers, ...rows].map(r => r.map(escape).join(',')).join('\n');
  const a = Object.assign(document.createElement('a'), {
    href: URL.createObjectURL(new Blob([csv], { type: 'text/csv' })),
    download: 'bassoon_sessions.csv',
  });
  a.click();
}
