import { getReeds, saveReed, deleteReed, addReedComparison } from './storage.js';
import { recordSession, fetchFullResults } from './audio.js';
import { scoreColor } from './analysis.js';
import { initSidebar } from './sidebar.js';

let _compRecording = false;

// ── Lifecycle config ──────────────────────────────────────────────

const LIFECYCLE = {
  'new':         { label: 'New',         cls: 'lifecycle-new',       tip: 'Just got it'           },
  'breaking-in': { label: 'Breaking in', cls: 'lifecycle-breaking',  tip: 'First 1–3 days'        },
  'peak':        { label: 'Peak',        cls: 'lifecycle-peak',      tip: 'Playing at its best'   },
  'declining':   { label: 'Declining',   cls: 'lifecycle-declining', tip: 'Past its best'         },
  'dead':        { label: 'Dead',        cls: 'lifecycle-dead',      tip: 'No longer usable'      },
};

// ── Star rating widget ────────────────────────────────────────────

function initStars() {
  const stars = document.querySelectorAll('#response-stars .star');
  stars.forEach(s => {
    s.addEventListener('click', () => {
      const val = parseInt(s.dataset.val, 10);
      document.getElementById('reed-response-input').value = val;
      stars.forEach(st => st.classList.toggle('active', parseInt(st.dataset.val, 10) <= val));
    });
    s.addEventListener('mouseenter', () => {
      const val = parseInt(s.dataset.val, 10);
      stars.forEach(st => st.classList.toggle('active', parseInt(st.dataset.val, 10) <= val));
    });
    s.addEventListener('mouseleave', () => {
      const cur = parseInt(document.getElementById('reed-response-input').value, 10) || 0;
      stars.forEach(st => st.classList.toggle('active', parseInt(st.dataset.val, 10) <= cur));
    });
  });
}

// ── Toggle button groups ──────────────────────────────────────────

function initToggleGroup(containerId, hiddenId) {
  const btns = document.querySelectorAll(`#${containerId} .lc-btn`);
  btns.forEach(b => {
    b.addEventListener('click', () => {
      btns.forEach(x => x.classList.remove('selected'));
      b.classList.add('selected');
      document.getElementById(hiddenId).value = b.dataset.val;
    });
  });
}

function initLifecycleGroup() {
  const btns = document.querySelectorAll('#lifecycle-btns .lc-btn');
  btns.forEach(b => {
    b.addEventListener('click', () => {
      btns.forEach(x => x.classList.remove('selected'));
      b.classList.add('selected');
      document.getElementById('reed-lifecycle-input').value = b.dataset.val;
    });
  });
}

// ── Reed list ─────────────────────────────────────────────────────

function renderReedList() {
  const reeds    = getReeds();
  const list     = document.getElementById('reeds-list');
  const empty    = document.getElementById('reeds-empty');
  const compCard = document.getElementById('record-comparison-card');
  const select   = document.getElementById('comp-reed-select');

  if (!reeds.length) {
    empty.style.display    = '';
    list.innerHTML         = '';
    compCard.style.display = 'none';
    return;
  }
  empty.style.display    = 'none';
  compCard.style.display = '';

  // Only non-dead reeds in the test selector
  select.innerHTML = reeds
    .filter(r => r.lifecycle !== 'dead')
    .map(r => `<option value="${r.id}">${r.name}</option>`)
    .join('');
  if (!select.options.length)
    select.innerHTML = '<option value="">No active reeds</option>';

  list.innerHTML = reeds.map(r => {
    const comps  = r.comparisons ?? [];
    const latest = comps.length ? comps[comps.length - 1] : null;
    const score  = latest?.overallScore;
    const color  = score != null ? scoreColor(score) : 'var(--p-border)';
    const lc     = LIFECYCLE[r.lifecycle ?? 'new'];

    const starsHtml = r.response
      ? '★'.repeat(parseInt(r.response, 10)) + '☆'.repeat(5 - parseInt(r.response, 10))
      : '';

    const lifecycleOptions = Object.entries(LIFECYCLE).map(([k, v]) =>
      `<button type="button" class="lc-btn${(r.lifecycle ?? 'new') === k ? ' selected' : ''}"
        data-id="${r.id}" data-val="${k}" onclick="setLifecycle('${r.id}','${k}')"
        title="${v.tip}">${v.label}</button>`
    ).join('');

    return `
      <div class="reed-card" id="reed-card-${r.id}">
        <div style="display:flex;align-items:flex-start;gap:0.75rem">
          <div class="reed-score-circle" style="border-color:${color};color:${color}">
            ${score != null ? score : '—'}
          </div>
          <div style="flex:1;min-width:0">
            <div style="display:flex;align-items:center;gap:0.4rem;flex-wrap:wrap">
              <span style="font-weight:700;color:var(--p-text);font-size:0.95rem">${r.name}</span>
              <span class="lifecycle-badge ${lc.cls}">${lc.label}</span>
            </div>
            ${r.response ? `<div style="color:#b07d2e;font-size:0.85rem;letter-spacing:0.08em;margin-top:0.15rem" title="Response ${r.response}/5">${starsHtml}</div>` : ''}
            <div class="reed-detail-row">
              ${r.tendency   ? `<div class="reed-detail"><span class="lbl">Intonation</span><span class="val">${r.tendency}</span></div>` : ''}
              ${r.resistance ? `<div class="reed-detail"><span class="lbl">Air resistance</span><span class="val">${r.resistance}</span></div>` : ''}
              ${score != null ? `<div class="reed-detail"><span class="lbl">Stability score</span><span class="val" style="color:${color}">${score}/100</span></div>` : ''}
              ${comps.length > 1 ? `<div class="reed-detail"><span class="lbl">Tests recorded</span><span class="val">${comps.length}</span></div>` : ''}
            </div>
            ${r.notes ? `<div style="font-size:0.75rem;color:var(--p-muted);margin-top:0.35rem;line-height:1.5">${r.notes}</div>` : ''}
          </div>
          <button onclick="removeReed('${r.id}')"
            style="background:none;border:none;color:var(--p-muted);cursor:pointer;font-size:1.2rem;line-height:1;padding:0;flex-shrink:0;min-width:32px;min-height:32px;display:flex;align-items:center;justify-content:center"
            title="Remove reed" aria-label="Remove ${r.name}">×</button>
        </div>

        <!-- Lifecycle updater -->
        <div style="margin-top:0.65rem">
          <div style="font-size:0.68rem;color:var(--p-muted);text-transform:uppercase;letter-spacing:0.06em;margin-bottom:0.3rem">Update stage:</div>
          <div style="display:flex;gap:0.35rem;flex-wrap:wrap">${lifecycleOptions}</div>
        </div>
      </div>`;
  }).join('');

  renderComparisonResults();
}

window.addReed = function() {
  const name = document.getElementById('reed-name-input').value.trim();
  if (!name) {
    document.getElementById('reed-name-input').focus();
    document.getElementById('reed-name-input').style.borderColor = 'var(--p-red-lt)';
    setTimeout(() => document.getElementById('reed-name-input').style.borderColor = '', 1500);
    return;
  }

  saveReed({
    name,
    response:   document.getElementById('reed-response-input').value || null,
    tendency:   document.getElementById('reed-tendency-input').value || null,
    resistance: document.getElementById('reed-resistance-input').value || null,
    lifecycle:  document.getElementById('reed-lifecycle-input').value || 'new',
    notes:      document.getElementById('reed-notes-input').value.trim() || null,
    addedDate:  new Date().toISOString().slice(0, 10),
  });

  // Reset form
  document.getElementById('reed-name-input').value  = '';
  document.getElementById('reed-notes-input').value = '';
  document.getElementById('reed-response-input').value   = '';
  document.getElementById('reed-tendency-input').value   = '';
  document.getElementById('reed-resistance-input').value = '';
  document.getElementById('reed-lifecycle-input').value  = 'new';
  document.querySelectorAll('#response-stars .star').forEach(s => s.classList.remove('active'));
  document.querySelectorAll('#tendency-btns .lc-btn').forEach(b => b.classList.remove('selected'));
  document.querySelectorAll('#resistance-btns .lc-btn').forEach(b => b.classList.remove('selected'));
  document.querySelectorAll('#lifecycle-btns .lc-btn').forEach(b => {
    b.classList.toggle('selected', b.dataset.val === 'new');
  });

  const msg = document.getElementById('add-reed-msg');
  msg.textContent   = `"${name}" saved!`;
  msg.style.display = '';
  setTimeout(() => { msg.style.display = 'none'; }, 2500);

  renderReedList();
};

window.removeReed = function(id) {
  deleteReed(id);
  renderReedList();
};

window.setLifecycle = function(id, stage) {
  const reeds = getReeds();
  const reed  = reeds.find(r => r.id === id);
  if (!reed) return;
  reed.lifecycle = stage;
  saveReed(reed);
  renderReedList();
};

// ── Record comparison ─────────────────────────────────────────────

window.recordComparison = async function() {
  if (_compRecording) return;
  const reedId = document.getElementById('comp-reed-select').value;
  if (!reedId) return;

  _compRecording = true;
  const btn       = document.getElementById('comp-rec-btn');
  const label     = document.getElementById('comp-rec-label');
  const statusBar = document.getElementById('comp-rec-status');
  const statusTxt = document.getElementById('comp-rec-status-text');

  btn.classList.add('active');
  if (statusBar) statusBar.classList.add('visible');

  try {
    const data = await recordSession({
      duration: 15,
      onTick: r => {
        const msg = r > 0 ? `Recording — ${r}s remaining` : 'Analyzing…';
        label.textContent = msg;
        if (statusTxt) statusTxt.textContent = msg;
      },
    });
    label.textContent = 'Done!';
    if (statusBar) statusBar.classList.remove('visible');

    const { results } = await fetchFullResults();
    const score = Math.round((data.summary.overall_score ?? 0) * 100);
    const regStats = results.register_stats ?? {};
    addReedComparison(reedId, {
      overallScore: score,
      registerScores: {
        low:   regStats.low?.mean   != null ? Math.round(regStats.low.mean   * 100) : null,
        tenor: regStats.tenor?.mean != null ? Math.round(regStats.tenor.mean * 100) : null,
        high:  regStats.high?.mean  != null ? Math.round(regStats.high.mean  * 100) : null,
      },
      noteBreakdown: results.note_breakdown ?? [],
    });
    renderReedList();
    renderComparisonResults();

  } catch (e) {
    label.textContent = 'Error: ' + e.message;
    if (statusBar) statusBar.classList.remove('visible');
  } finally {
    _compRecording = false;
    btn.classList.remove('active');
  }
};

// ── Comparison chart ──────────────────────────────────────────────

let _compChart = null;

function renderComparisonResults() {
  const reeds = getReeds().filter(r => (r.comparisons ?? []).length > 0);
  const card  = document.getElementById('comparison-results-card');
  if (reeds.length < 2) { card.style.display = 'none'; return; }
  card.style.display = '';

  const labels  = reeds.map(r => r.name);
  const overall = reeds.map(r => (r.comparisons ?? []).slice(-1)[0]?.overallScore ?? 0);
  const colors  = overall.map(s => scoreColor(s));

  if (_compChart) _compChart.destroy();
  _compChart = new Chart(document.getElementById('chart-comparison'), {
    type: 'bar',
    data: {
      labels,
      datasets: [{
        label: 'Stability score',
        data: overall,
        backgroundColor: colors.map(c => c + '33'),
        borderColor: colors,
        borderWidth: 2,
        borderRadius: 6,
      }],
    },
    options: {
      responsive: true,
      plugins: { legend: { display: false } },
      scales: {
        x: { ticks: { color: '#94a3b8' }, grid: { color: '#1e293b' } },
        y: { ticks: { color: '#94a3b8' }, grid: { color: '#1e293b' }, min: 0, max: 100 },
      },
    },
  });

  const bestIdx  = overall.indexOf(Math.max(...overall));
  const others   = overall.filter((_, i) => i !== bestIdx);
  const diff     = others.length ? Math.round(overall[bestIdx] - Math.max(...others)) : null;
  const rec      = document.getElementById('comparison-recommendation');
  rec.textContent = diff != null && diff > 0
    ? `${reeds[bestIdx].name} is your most stable reed — ${diff} points ahead of the next best.`
    : `${reeds[bestIdx].name} is currently your top performer.`;
  rec.style.display = '';

  const breakdown = document.getElementById('comparison-reg-breakdown');
  breakdown.innerHTML = `<div class="p-section-label">Register scores per reed</div>` +
    reeds.map(r => {
      const latest   = (r.comparisons ?? []).slice(-1)[0];
      const rs       = latest?.registerScores ?? {};
      const noteData = latest?.noteBreakdown ?? [];
      const lc       = LIFECYCLE[r.lifecycle ?? 'new'];

      const regBars = ['low','tenor','high'].map(reg => {
        const s     = rs[reg];
        const color = s != null ? scoreColor(s) : 'var(--p-muted)';
        const hint  = reg === 'low' ? '(below B♭2)' : reg === 'tenor' ? '(B♭2–B♭4)' : '(above B♭4)';
        return `<div class="reg-bar-row">
          <span class="reg-name" title="${hint}">${reg}</span>
          <div class="reg-bar-track"><div class="reg-bar-fill" style="width:${s ?? 0}%;background:${color}"></div></div>
          <span class="reg-val" style="color:${color}">${s ?? '—'}</span>
        </div>`;
      }).join('');

      let noteTable = '';
      if (noteData.length) {
        const sorted = [...noteData].sort((a, b) => a.stability_score - b.stability_score);
        noteTable = `
          <div style="margin-top:0.6rem">
            <div style="font-size:0.68rem;font-weight:600;color:var(--p-muted);text-transform:uppercase;letter-spacing:0.06em;margin-bottom:0.3rem">Note breakdown</div>
            <table style="width:100%;border-collapse:collapse;font-size:0.78rem">
              <thead><tr>
                <th style="text-align:left;padding:0.25rem 0.4rem;color:var(--p-muted);font-weight:600;border-bottom:var(--p-rule);font-size:0.65rem;text-transform:uppercase">Note</th>
                <th style="text-align:left;padding:0.25rem 0.4rem;color:var(--p-muted);font-weight:600;border-bottom:var(--p-rule);font-size:0.65rem;text-transform:uppercase">Reg.</th>
                <th style="text-align:right;padding:0.25rem 0.4rem;color:var(--p-muted);font-weight:600;border-bottom:var(--p-rule);font-size:0.65rem;text-transform:uppercase">Score</th>
                <th style="text-align:right;padding:0.25rem 0.4rem;color:var(--p-muted);font-weight:600;border-bottom:var(--p-rule);font-size:0.65rem;text-transform:uppercase">Dev.</th>
              </tr></thead>
              <tbody>${sorted.map(seg => {
                const sc    = Math.round((seg.stability_score ?? 0) * 100);
                const color = scoreColor(sc);
                const dev   = seg.cents_deviation != null
                  ? (seg.cents_deviation >= 0 ? '+' : '') + seg.cents_deviation.toFixed(1) + ' ¢'
                  : '—';
                return `<tr>
                  <td style="padding:0.25rem 0.4rem;border-bottom:1px solid var(--p-border);color:var(--p-text);font-weight:600">${seg.note}</td>
                  <td style="padding:0.25rem 0.4rem;border-bottom:1px solid var(--p-border);color:var(--p-muted);font-size:0.72rem">${seg.register}</td>
                  <td style="padding:0.25rem 0.4rem;border-bottom:1px solid var(--p-border);text-align:right;font-weight:700;color:${color}">${sc}</td>
                  <td style="padding:0.25rem 0.4rem;border-bottom:1px solid var(--p-border);text-align:right;color:var(--p-text-sub)">${dev}</td>
                </tr>`;
              }).join('')}</tbody>
            </table>
          </div>`;
      }

      return `
        <div style="margin-bottom:1rem;padding-bottom:0.85rem;border-bottom:var(--p-rule)">
          <div style="font-size:0.85rem;font-weight:700;color:var(--p-text);margin-bottom:0.5rem">
            ${r.name} <span class="lifecycle-badge ${lc.cls}">${lc.label}</span>
          </div>
          ${regBars}${noteTable}
        </div>`;
    }).join('');
}

// ── Init ──────────────────────────────────────────────────────────

initStars();
initToggleGroup('tendency-btns',  'reed-tendency-input');
initToggleGroup('resistance-btns','reed-resistance-input');
initLifecycleGroup();
renderReedList();
initSidebar();
