import { getSessions, getReeds } from './storage.js';
import { ratingMessage, scoreColor } from './analysis.js';
import { initSidebar } from './sidebar.js';

function fmtDate(iso) {
  const d = new Date(iso);
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

function weeklyTrend(sessions) {
  if (sessions.length < 2) return null;
  const now   = Date.now();
  const week  = 7 * 24 * 3600 * 1000;
  const thisW = sessions.filter(s => now - new Date(s.date) < week);
  const lastW = sessions.filter(s => {
    const age = now - new Date(s.date);
    return age >= week && age < 2 * week;
  });
  if (!thisW.length || !lastW.length) return null;
  const avg = arr => arr.reduce((a, s) => a + (s.overallScore ?? 0), 0) / arr.length;
  return Math.round(avg(thisW) - avg(lastW));
}

function renderTrend(delta) {
  if (delta === null) return { text: '—', sub: '', cls: 'trend-flat' };
  if (delta > 0)  return { text: `+${delta}%`, sub: 'vs last week', cls: 'trend-up' };
  if (delta < 0)  return { text: `${delta}%`,  sub: 'vs last week', cls: 'trend-down' };
  return { text: '±0%', sub: 'vs last week', cls: 'trend-flat' };
}

function scoreCircle(score) {
  const color = scoreColor(score);
  return `<div class="session-score" style="background:${color}22;color:${color}">${score}</div>`;
}

function renderSessions(sessions) {
  const list = document.getElementById('recent-list');
  const recent = [...sessions].reverse().slice(0, 5);
  list.innerHTML = recent.map(s => `
    <a class="session-item" href="/practice?session=${s.id}">
      ${scoreCircle(s.overallScore ?? 0)}
      <div class="session-info">
        <div class="session-name">${s.name ?? 'Untitled'}</div>
        <div class="session-meta">${fmtDate(s.date)} · ${s.reed || 'No reed'} · ${s.mode ?? 'free'}</div>
      </div>
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--p-muted)" stroke-width="2"><polyline points="9 18 15 12 9 6"/></svg>
    </a>
  `).join('');
}

function currentReed(reeds) {
  if (!reeds.length) return '—';
  // Most recently added reed
  const sorted = [...reeds].sort((a, b) => (b.addedDate ?? '').localeCompare(a.addedDate ?? ''));
  return sorted[0].name ?? '—';
}

function init() {
  const sessions = getSessions();
  const reeds    = getReeds();

  document.getElementById('stat-sessions').textContent = sessions.length;

  const trend = weeklyTrend(sessions);
  const t     = renderTrend(trend);
  const tEl   = document.getElementById('stat-trend');
  tEl.textContent  = t.text;
  tEl.className    = `value ${t.cls}`;
  document.getElementById('stat-trend-sub').textContent = t.sub;

  document.getElementById('stat-reed').textContent = currentReed(reeds);

  if (sessions.length > 0) {
    document.getElementById('welcome-card').style.display = 'none';
    document.getElementById('recent-card').style.display  = 'block';
    renderSessions(sessions);
  }
}

init();
initSidebar();
