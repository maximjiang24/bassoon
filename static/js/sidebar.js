import { getSessions, getReeds } from './storage.js';
import { weakNotes } from './analysis.js';

export function initSidebar() {
  const nav = document.querySelector('.app-nav');
  if (!nav) return;

  // ── Brand header ─────────────────────────────────────────────────
  const brand = document.createElement('div');
  brand.className = 'nav-brand';
  brand.innerHTML = `
    <img src="/static/bassoon-icon.svg" width="26" height="26" alt=""/>
    <div>
      <div class="nav-brand-text">Bassoon</div>
      <div class="nav-brand-sub">Intonation Analyzer</div>
    </div>`;
  nav.insertBefore(brand, nav.firstChild);

  // ── Data ──────────────────────────────────────────────────────────
  const sessions   = getSessions();
  const reeds      = getReeds();
  const recent5    = sessions.slice(-5);
  const last       = sessions.length ? sessions[sessions.length - 1] : null;
  const activeReed = reeds.find(r => r.lifecycle === 'peak')
                  ?? reeds.find(r => r.lifecycle === 'breaking-in')
                  ?? reeds.find(r => r.lifecycle === 'new')
                  ?? reeds[0] ?? null;

  const sc = s => s >= 80 ? '#65b556' : s >= 60 ? '#d4a547' : s >= 40 ? '#c99440' : '#c0392b';

  // Practice week — last 7 days with dots
  const days = ['M','T','W','T','F','S','S'];
  const now  = new Date();
  // Get Monday of current week
  const dayOfWeek = (now.getDay() + 6) % 7; // 0=Mon
  const weekDots  = days.map((label, i) => {
    const d = new Date(now);
    d.setDate(now.getDate() - dayOfWeek + i);
    const dateStr = d.toISOString().slice(0, 10);
    const practiced = sessions.some(s => s.date && s.date.slice(0, 10) === dateStr);
    const isToday   = i === dayOfWeek;
    return { label, practiced, isToday };
  });

  const dotsHTML = weekDots.map(d => `
    <div class="nav-week-day">
      <div class="nav-week-dot ${d.practiced ? 'done' : ''} ${d.isToday ? 'today' : ''}"></div>
      <span class="nav-week-label ${d.isToday ? 'today' : ''}">${d.label}</span>
    </div>`).join('');

  // Weak notes for "focus" section
  const weak = weakNotes(recent5, 3, 65);
  const focusHTML = weak.length
    ? weak.map(w => `<span class="nav-focus-note" style="color:${sc(w.avgScore ?? 0)}">${w.note}</span>`).join('')
    : `<span style="color:var(--p-muted);font-size:0.72rem">Play a session to unlock</span>`;

  // Last session
  const lastHTML = last
    ? `<div class="nav-stat-row">
        <span class="nav-stat-label">Last score</span>
        <span class="nav-stat-value" style="color:${last.overallScore != null ? sc(last.overallScore) : 'var(--p-text-sub)'}">
          ${last.overallScore != null ? last.overallScore + '/100' : '—'}
        </span>
       </div>
       <div class="nav-stat-row">
        <span class="nav-stat-label">Date</span>
        <span class="nav-stat-value">${last.date ? new Date(last.date).toLocaleDateString(undefined, { month:'short', day:'numeric' }) : '—'}</span>
       </div>`
    : `<div style="font-size:0.72rem;color:var(--p-muted)">No sessions yet</div>`;

  // Reed section
  const reedHTML = activeReed
    ? `<div class="nav-stat-row">
        <span class="nav-stat-label">Reed</span>
        <span class="nav-stat-value nav-mid-reed">${activeReed.name}</span>
       </div>
       <div class="nav-stat-row">
        <span class="nav-stat-label">Stage</span>
        <span class="nav-stat-value" style="text-transform:capitalize;color:${
          activeReed.lifecycle === 'peak' ? '#65b556'
          : activeReed.lifecycle === 'declining' ? '#c99440'
          : activeReed.lifecycle === 'dead' ? '#c0392b'
          : 'var(--p-text-sub)'
        }">${activeReed.lifecycle ?? 'new'}</span>
       </div>`
    : `<a href="/reeds" style="color:var(--p-amber);font-size:0.72rem;text-decoration:none">Add a reed →</a>`;

  // ── Mid block ─────────────────────────────────────────────────────
  const mid = document.createElement('div');
  mid.className = 'nav-mid';
  mid.innerHTML = `
    <div class="nav-mid-section">
      <div class="nav-mid-heading">This week</div>
      <div class="nav-week-row">${dotsHTML}</div>
    </div>

    <div class="nav-mid-section">
      <div class="nav-mid-heading">Focus notes</div>
      <div class="nav-focus-row">${focusHTML}</div>
      ${weak.length ? `<a href="/practice" style="font-size:0.68rem;color:var(--p-muted);text-decoration:none;margin-top:0.3rem;display:block">Practice these →</a>` : ''}
    </div>

    <div class="nav-mid-section">
      <div class="nav-mid-heading">Last session</div>
      ${lastHTML}
    </div>

    <div class="nav-mid-section">
      <div class="nav-mid-heading">Reed</div>
      ${reedHTML}
    </div>`;

  nav.appendChild(mid);

  // ── Footer CTA ────────────────────────────────────────────────────
  const footer = document.createElement('div');
  footer.className = 'nav-sidebar-footer';
  footer.innerHTML = `
    <a href="/practice" class="nav-footer-cta">
      <svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M9 10l3-3 3 3M12 7v10"/></svg>
      Start Session
    </a>`;
  nav.appendChild(footer);
}
