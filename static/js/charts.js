import { getSessions, getReeds, exportCSV } from './storage.js';
import { scoreColor } from './analysis.js';
import { initSidebar } from './sidebar.js';

window.exportData = exportCSV;
initSidebar();

const CHART_DEFAULTS = {
  responsive: true,
  plugins: { legend: { labels: { color: '#94a3b8', font: { size: 11 } } } },
  scales: {
    x: { ticks: { color: '#94a3b8', font: { size: 10 } }, grid: { color: '#1e293b' } },
    y: { ticks: { color: '#94a3b8', font: { size: 10 } }, grid: { color: '#1e293b' },
         min: 0, max: 100 },
  },
};

function fmtDate(iso) {
  return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

function show(id) { document.getElementById(id).style.display = ''; }

function buildTrendChart(sessions) {
  const labels = sessions.map(s => fmtDate(s.date));
  const scores = sessions.map(s => s.overallScore ?? 0);
  new Chart(document.getElementById('chart-trend'), {
    type: 'line',
    data: {
      labels,
      datasets: [{
        label: 'Stability score',
        data: scores,
        borderColor: '#14b8a6',
        backgroundColor: 'rgba(20,184,166,0.1)',
        fill: true,
        tension: 0.3,
        pointRadius: 4,
        pointBackgroundColor: scores.map(s => scoreColor(s)),
      }],
    },
    options: { ...CHART_DEFAULTS, plugins: { ...CHART_DEFAULTS.plugins } },
  });
}

function buildRegisterChart(sessions) {
  const labels = sessions.map(s => fmtDate(s.date));
  const reg = key => sessions.map(s => s.registerScores?.[key] ?? null);
  const colors = { low: '#818cf8', tenor: '#14b8a6', high: '#f472b6' };
  new Chart(document.getElementById('chart-registers'), {
    type: 'line',
    data: {
      labels,
      datasets: ['low','tenor','high'].map(k => ({
        label: k.charAt(0).toUpperCase() + k.slice(1),
        data: reg(k),
        borderColor: colors[k],
        backgroundColor: 'transparent',
        tension: 0.3,
        pointRadius: 3,
        spanGaps: true,
      })),
    },
    options: { ...CHART_DEFAULTS },
  });
}

function buildNoteHeatmap(sessions) {
  const acc = {};
  for (const s of sessions) {
    for (const [note, d] of Object.entries(s.noteScores ?? {})) {
      acc[note] ??= { total: 0, count: 0 };
      acc[note].total += d.score ?? 0;
      acc[note].count++;
    }
  }
  const container = document.getElementById('note-heatmap');
  const entries = Object.entries(acc)
    .map(([note, d]) => ({ note, avg: Math.round(d.total / d.count) }))
    .sort((a, b) => a.avg - b.avg);

  if (!entries.length) {
    container.innerHTML = '<span style="color:var(--p-muted);font-size:0.85rem">No note data yet.</span>';
    return;
  }

  container.innerHTML = entries.map(({ note, avg }) => {
    const color = scoreColor(avg);
    return `<div title="${note}: ${avg}/100"
      style="background:${color}22;border:1px solid ${color}44;border-radius:4px;
             padding:0.4rem 0.6rem;font-size:0.78rem;color:${color};font-weight:600;
             display:flex;flex-direction:column;align-items:center;gap:2px;min-width:44px">
      <span>${note}</span><span>${avg}</span>
    </div>`;
  }).join('');
}

function buildReedChart(sessions, reeds) {
  const reedNames = [...new Set(sessions.map(s => s.reed).filter(Boolean))];
  if (!reedNames.length) return;

  const colors = ['#14b8a6','#f472b6','#818cf8','#fb923c','#a3e635'];
  const datasets = reedNames.map((name, i) => {
    const reedSessions = sessions.filter(s => s.reed === name);
    return {
      label: name,
      data: reedSessions.map(s => ({ x: fmtDate(s.date), y: s.overallScore ?? 0 })),
      borderColor: colors[i % colors.length],
      backgroundColor: 'transparent',
      tension: 0.3,
      pointRadius: 4,
      showLine: false,
    };
  });

  new Chart(document.getElementById('chart-reeds'), {
    type: 'scatter',
    data: { datasets },
    options: {
      ...CHART_DEFAULTS,
      scales: {
        ...CHART_DEFAULTS.scales,
        x: { ...CHART_DEFAULTS.scales.x, type: 'category' },
      },
    },
  });
}

function buildHighlightCards(sessions) {
  const sorted = [...sessions].sort((a, b) => (b.overallScore ?? 0) - (a.overallScore ?? 0));
  const best   = sorted[0];
  const worst  = sorted[sorted.length - 1];

  document.getElementById('best-name').textContent  = `${best.overallScore}/100`;
  document.getElementById('best-meta').textContent  = `${best.name ?? 'Session'} · ${fmtDate(best.date)}`;
  document.getElementById('worst-name').textContent = `${worst.overallScore}/100`;
  document.getElementById('worst-meta').textContent = `${worst.name ?? 'Session'} · ${fmtDate(worst.date)}`;
}

function buildImprovementCard(sessions) {
  const month   = 30 * 24 * 3600 * 1000;
  const now     = Date.now();
  const recent  = sessions.filter(s => now - new Date(s.date) < month);
  const older   = sessions.filter(s => now - new Date(s.date) >= month);
  if (!recent.length || !older.length) return;

  const recentNotes = {};
  const olderNotes  = {};
  for (const s of recent) for (const [n,d] of Object.entries(s.noteScores ?? {})) {
    recentNotes[n] ??= []; recentNotes[n].push(d.score ?? 0);
  }
  for (const s of older) for (const [n,d] of Object.entries(s.noteScores ?? {})) {
    olderNotes[n]  ??= []; olderNotes[n].push(d.score ?? 0);
  }
  const avg = arr => arr.reduce((a,b) => a+b, 0) / arr.length;
  let best = null, bestDelta = -Infinity;
  for (const note of Object.keys(recentNotes)) {
    if (!olderNotes[note]) continue;
    const delta = avg(recentNotes[note]) - avg(olderNotes[note]);
    if (delta > bestDelta) { bestDelta = delta; best = note; }
  }
  if (best && bestDelta > 2) {
    document.getElementById('improvement-text').textContent =
      `Your most improved note this month: ${best} (+${Math.round(bestDelta)} points more stable)`;
    show('improvement-card');
  }
}

function init() {
  const sessions = getSessions();
  const reeds    = getReeds();

  if (sessions.length < 3) {
    show('empty-state');
    return;
  }

  buildHighlightCards(sessions);
  const hc = document.getElementById('highlight-cards');
  hc.style.display = 'grid';

  buildImprovementCard(sessions);
  buildTrendChart(sessions);     show('trend-card');
  buildRegisterChart(sessions);  show('reg-card');
  buildNoteHeatmap(sessions);    show('heatmap-card');

  const reedNames = [...new Set(sessions.map(s => s.reed).filter(Boolean))];
  if (reedNames.length > 1) {
    buildReedChart(sessions, reeds);
    show('reed-history-card');
  }
}

init();
