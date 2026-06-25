import { getSessions, saveSession, getReeds } from './storage.js';
import { recordSession, fetchFullResults } from './audio.js';
import { buildSessionData, ratingMessage, scoreColor, weakNotes } from './analysis.js';
import { runRules, prioritisedFindings, fetchAIFeedback, severityColor } from './embouchure_feedback.js';
import { renderNoteOnStaff } from './sheet_music.js';
import { initSidebar } from './sidebar.js';

// ── Mode toggle ───────────────────────────────────────────────────
window.setMode = function(mode) {
  document.getElementById('panel-free').style.display    = mode === 'free'    ? '' : 'none';
  document.getElementById('panel-guided').style.display  = mode === 'guided'  ? '' : 'none';
  document.getElementById('mode-free').className         = mode === 'free'    ? 'p-btn' : 'p-btn-outline';
  document.getElementById('mode-guided').className       = mode === 'guided'  ? 'p-btn' : 'p-btn-outline';
};

// ── Gauge helper ──────────────────────────────────────────────────
function setGauge(fillId, score) {
  const el   = document.getElementById(fillId);
  const circ = 2 * Math.PI * 15.9;
  el.style.strokeDasharray  = `${circ} ${circ}`;
  el.style.strokeDashoffset = circ - (score / 100) * circ;
  // Color class
  el.classList.remove('score-excellent','score-good','score-fair','score-poor');
  if      (score >= 80) el.classList.add('score-excellent');
  else if (score >= 60) el.classList.add('score-good');
  else if (score >= 40) el.classList.add('score-fair');
  else                  el.classList.add('score-poor');
}

function regBarsHTML(registerStats) {
  return ['low','tenor','high'].map(reg => {
    const d     = registerStats?.[reg];
    const score = d?.mean != null ? Math.round(d.mean * 100) : null;
    const color = score != null ? scoreColor(score) : 'var(--p-muted)';
    const pct   = score ?? 0;
    return `
      <div class="reg-bar-row">
        <span class="reg-name">${reg}</span>
        <div class="reg-bar-track"><div class="reg-bar-fill" style="width:${pct}%;background:${color}"></div></div>
        <span class="reg-val" style="color:${color}">${score ?? '—'}</span>
      </div>`;
  }).join('');
}

// ── Free play state ───────────────────────────────────────────────
let _fpRecording = false;
let _fpLastData  = null;
let _fpLastResults = null;

window.toggleRecord = async function() {
  if (_fpRecording) return;
  _fpRecording = true;

  const btn       = document.getElementById('rec-btn');
  const label     = document.getElementById('rec-label');
  const statusBar = document.getElementById('fp-rec-status');
  const statusTxt = document.getElementById('fp-rec-status-text');
  const duration  = parseInt(document.getElementById('fp-duration').value, 10);
  const withVideo = document.getElementById('fp-with-video')?.checked ?? false;

  btn.classList.add('active');
  if (statusBar) statusBar.classList.add('visible');
  document.getElementById('fp-results').style.display = 'none';
  document.getElementById('fp-embouchure-panel').style.display = 'none';

  try {
    const data = await recordSession({
      duration,
      withVideo,
      onTick: r => {
        const msg = r > 0 ? `Recording… ${r}s remaining` : 'Analyzing…';
        label.textContent = msg;
        if (statusTxt) statusTxt.textContent = r > 0 ? `Recording — ${r}s remaining` : 'Analyzing…';
      },
    });
    label.textContent = 'Analysis complete.';
    if (statusBar) statusBar.classList.remove('visible');
    _fpLastData = data;

    const { results } = await fetchFullResults();
    _fpLastResults = results;

    showFreeResults(data.summary, results);

    if (data.summary.has_video) {
      showEmbouchure(results);
    }
  } catch (e) {
    label.textContent = 'Error: ' + e.message;
    if (statusBar) statusBar.classList.remove('visible');
  } finally {
    _fpRecording = false;
    btn.classList.remove('active');
  }
};

function showFreeResults(summary, results) {
  const score = Math.round((summary.overall_score ?? 0) * 100);
  document.getElementById('fp-score-num').textContent = score;
  document.getElementById('fp-rating').textContent    = ratingMessage(score);
  setGauge('fp-gauge-fill', score);

  // Pitch note + bassoon register context
  const noteEl = document.getElementById('fp-pitch-note');
  const regEl  = document.getElementById('fp-pitch-register');
  if (noteEl && summary.mean_note) {
    noteEl.textContent = summary.mean_note + (summary.mean_hz ? ' (' + summary.mean_hz + ' Hz)' : '');
  }
  if (regEl && summary.mean_hz) {
    const hz  = summary.mean_hz;
    const reg = hz < 116.54  ? 'Low register (below B♭2)'
              : hz <= 466.16 ? 'Tenor register (B♭2 – B♭4)'
              :                'High register (above B♭4)';
    regEl.textContent   = reg;
    regEl.style.display = '';
  }

  document.getElementById('fp-reg-bars').innerHTML =
    regBarsHTML(results.register_stats);

  // Per-note breakdown table

  // Per-note breakdown table
  const breakdown     = results.note_breakdown ?? [];
  const breakdownCard = document.getElementById('fp-note-breakdown-card');
  const breakdownBody = document.getElementById('fp-note-breakdown-body');
  if (breakdown.length && breakdownCard && breakdownBody) {
    const sorted = [...breakdown].sort((a, b) => a.stability_score - b.stability_score);
    breakdownBody.innerHTML = sorted.map(seg => {
      const score = Math.round((seg.stability_score ?? 0) * 100);
      const color = scoreColor(score);
      const dev   = seg.cents_deviation != null
        ? (seg.cents_deviation >= 0 ? '+' : '') + seg.cents_deviation.toFixed(1) + ' ¢'
        : '—';
      return `<tr>
        <td style="padding:0.35rem 0.5rem;border-bottom:1px solid var(--p-border);color:var(--p-text);font-weight:600">${seg.note}</td>
        <td style="padding:0.35rem 0.5rem;border-bottom:1px solid var(--p-border);color:var(--p-muted);font-size:0.78rem">${seg.register}</td>
        <td style="padding:0.35rem 0.5rem;border-bottom:1px solid var(--p-border);text-align:right;font-weight:700;color:${color}">${score}</td>
        <td style="padding:0.35rem 0.5rem;border-bottom:1px solid var(--p-border);text-align:right;color:var(--p-text-sub)">${dev}</td>
      </tr>`;
    }).join('');
    breakdownCard.style.display = '';
  } else if (breakdownCard) {
    breakdownCard.style.display = 'none';
  }

  document.getElementById('fp-results').style.display = '';
}

function showEmbouchure(results) {
  const emb  = results.embouchure;
  const corr = results.correlation;
  const interp = results.interpretation ?? [];

  if (!emb) return;

  const panel = document.getElementById('fp-embouchure-panel');
  panel.style.display = '';

  const fmt = (v, dec = 3) => v != null ? Number(v).toFixed(dec) : '—';

  document.getElementById('emb-consistency').textContent = fmt(emb.embouchure_consistency);
  document.getElementById('emb-jaw').textContent         = fmt(emb.jaw_stability);
  document.getElementById('emb-face').textContent        = emb.face_detected_pct != null ? emb.face_detected_pct.toFixed(1) + '%' : '—';
  document.getElementById('emb-mwv').textContent         = fmt(emb.mouth_width_variance, 2) + ' px²';
  document.getElementById('emb-ltv').textContent         = fmt(emb.lip_tension_variance, 4);

  const LABELS = {
    mouth_width_vs_stability:    'Mouth width vs stability',
    mouth_height_vs_stability:   'Mouth height vs stability',
    jaw_stability_vs_intonation: 'Jaw position vs stability',
    lip_tension_vs_stability:    'Lip tension vs stability',
  };

  const tbody = document.getElementById('emb-corr-body');
  tbody.innerHTML = '';
  if (corr) {
    for (const [key, label] of Object.entries(LABELS)) {
      const entry = corr[key] ?? {};
      const r = entry.r != null ? (entry.r >= 0 ? '+' : '') + Number(entry.r).toFixed(3) : '—';
      const p = entry.p != null ? Number(entry.p).toFixed(3) : '—';
      const sig = entry.p != null && entry.p < 0.05 ? ' *' : '';
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td style="padding:0.35rem 0.5rem;border-bottom:var(--p-rule);color:var(--p-text-sub)">${label}</td>
        <td style="padding:0.35rem 0.5rem;border-bottom:var(--p-rule);text-align:right;color:var(--p-text);font-weight:600">${r}${sig}</td>
        <td style="padding:0.35rem 0.5rem;border-bottom:var(--p-rule);text-align:right;color:var(--p-muted)">${p}</td>`;
      tbody.appendChild(tr);
    }
  }

  const interpCard = document.getElementById('emb-interp-card');
  const interpList = document.getElementById('emb-interp-list');
  if (interp.length) {
    interpList.innerHTML = interp.map(line =>
      `<li style="padding:0.4rem 0.6rem;background:var(--p-raised);border-left:2px solid var(--p-amber);border-radius:var(--p-radius-sm);font-size:0.85rem;color:var(--p-text-sub)">${line}</li>`
    ).join('');
    interpCard.style.display = '';
  }

  // ── Rule-based technique analysis ────────────────────────────────
  const findings = prioritisedFindings(runRules({
    emb,
    corr,
    summary: results.summary ?? {},
    regCorr: results.register_correlation ?? {},
  }));

  const rulesCard = document.getElementById('emb-rules-card');
  const rulesList = document.getElementById('emb-rules-list');
  if (findings.length) {
    rulesList.innerHTML = findings.map(f => {
      const color  = severityColor(f.severity);
      const icon   = f.severity === 'critical' ? '⚠' : f.severity === 'ok' ? '✓' : '•';
      return `<div style="display:flex;gap:0.6rem;align-items:flex-start;padding:0.5rem 0.65rem;
                           background:var(--p-raised);border-left:2px solid ${color};
                           border-radius:var(--p-radius-sm)">
        <span style="color:${color};font-size:0.85rem;flex-shrink:0;margin-top:0.05rem">${icon}</span>
        <span style="font-size:0.84rem;color:var(--p-text-sub);line-height:1.55">${f.text}</span>
      </div>`;
    }).join('');
    rulesCard.style.display = '';
  }

  // ── AI narrative feedback replaced with extended rule summary ────
  const aiCard    = document.getElementById('emb-ai-card');
  const aiLoading = document.getElementById('emb-ai-loading');
  const aiText    = document.getElementById('emb-ai-text');
  const aiError   = document.getElementById('emb-ai-error');

  aiCard.style.display    = '';
  aiLoading.style.display = 'none';
  aiError.style.display   = 'none';

  // Build a narrative from the rule findings — no API needed
  const criticals = findings.filter(f => f.severity === 'critical');
  const warnings  = findings.filter(f => f.severity === 'warning');
  const oks       = findings.filter(f => f.severity === 'ok');

  let narrative = '';

  if (oks.length) {
    narrative += `<strong>What's working:</strong> ${oks.map(f => f.text).join(' ')}<br><br>`;
  }

  if (criticals.length) {
    narrative += `<strong>Priority — fix this first:</strong> ${criticals[0].text}`;
    if (criticals.length > 1) narrative += ` ${criticals.slice(1).map(f => f.text).join(' ')}`;
    narrative += '<br><br>';
  }

  if (warnings.length) {
    narrative += `<strong>Also worth attention:</strong> ${warnings.slice(0, 2).map(f => f.text).join(' ')}<br><br>`;
  }

  // Practice exercise based on top issue
  const topIssue = criticals[0] ?? warnings[0];
  if (topIssue) {
    let exercise = '';
    if (topIssue.text.includes('jaw')) {
      exercise = '<strong>Exercise this week:</strong> Play long tones on a comfortable tenor note (e.g. A3). Press your back teeth lightly together and hold them there. Count the jaw movements — aim for zero. Record yourself and review.';
    } else if (topIssue.text.includes('sharp') || topIssue.text.includes('tension') || topIssue.text.includes('pinch')) {
      exercise = '<strong>Exercise this week:</strong> Play B♭4 long tones with a tuner. Start with a relaxed embouchure and gradually increase air speed until the note centres — not embouchure pressure. Aim for ±10 cents.';
    } else if (topIssue.text.includes('flat') || topIssue.text.includes('under-support') || topIssue.text.includes('airy')) {
      exercise = '<strong>Exercise this week:</strong> Play F3 and G3 long tones. Firm your lip seal slightly (not your jaw) and increase air support until the note centres. Compare against a tuner — aim for ±10 cents.';
    } else if (topIssue.text.includes('mouth') || topIssue.text.includes('collapse')) {
      exercise = '<strong>Exercise this week:</strong> Play a slow scale from C3 to C5, watching your mouth in a mirror. Your tooth spacing should stay constant throughout. Stop and reset if you see it change.';
    } else {
      exercise = '<strong>Exercise this week:</strong> Daily long tones — pick one note per register, hold for 30 seconds, repeat three times. Record each attempt and compare for consistency of tone and pitch.';
    }
    narrative += exercise;
  }

  aiText.innerHTML    = narrative || 'No significant issues detected — keep up the consistent practice.';
  aiText.style.display = '';
}

window.saveFreeSesssion = function() {
  if (!_fpLastData || !_fpLastResults) return;
  const name = document.getElementById('fp-session-name').value.trim() || 'Free play';
  const reed = document.getElementById('fp-reed-name').value.trim();
  saveSession(buildSessionData({
    summary: _fpLastData.summary,
    results: _fpLastResults,
    name, reed, mode: 'free',
  }));
  document.getElementById('fp-save-msg').style.display = '';
  const homeLink = document.getElementById('fp-home-link');
  if (homeLink) homeLink.style.display = '';
};

// ── Guided exercise state ─────────────────────────────────────────

// Full bassoon range pool — B♭1 to E5, one entry per playable note.
// Grouped by register so we can sample evenly across the range.
const NOTE_POOL = {
  low: [
    { note: 'B♭1', desc: 'Hold B♭1 — use relaxed embouchure and warm supported air.', target: 60 },
    { note: 'C2',  desc: 'Hold C2 — keep the embouchure open and air flowing steadily.', target: 60 },
    { note: 'D2',  desc: 'Hold D2 — focus on a consistent air column.',                  target: 62 },
    { note: 'E♭2', desc: 'Hold E♭2 — low register needs relaxed lips and full support.', target: 62 },
    { note: 'F2',  desc: 'Hold F2 — watch for flat tendency in the low register.',        target: 63 },
    { note: 'G2',  desc: 'Hold G2 — keep jaw stable and air warm.',                      target: 63 },
    { note: 'A2',  desc: 'Hold A2 — aim for a centred, full tone.',                      target: 64 },
    { note: 'B♭2', desc: 'Hold B♭2 — the start of the tenor register, stay relaxed.',   target: 64 },
  ],
  tenor: [
    { note: 'C3',  desc: 'Hold C3 — the most common starting note for long tones.',      target: 65 },
    { note: 'D3',  desc: 'Hold D3 — focus on steady air and a centred pitch.',           target: 65 },
    { note: 'E♭3', desc: 'Hold E♭3 — listen for any sharp tendency.',                   target: 65 },
    { note: 'F3',  desc: 'Hold F3 — keep the embouchure firm but not tight.',            target: 65 },
    { note: 'G3',  desc: 'Hold G3 — focus on steady air support.',                       target: 65 },
    { note: 'A3',  desc: 'Hold A3 — middle of the tenor register.',                      target: 65 },
    { note: 'B♭3', desc: 'Hold B♭3 — one of the most important notes in the range.',    target: 64 },
    { note: 'C4',  desc: 'Hold C4 (middle C) — balance air speed and embouchure support.', target: 63 },
    { note: 'D4',  desc: 'Hold D4 — tends flat in the tenor octave; add support.',       target: 62 },
    { note: 'E♭4', desc: 'Hold E♭4 — watch for sharpness; keep embouchure open.',       target: 62 },
    { note: 'F4',  desc: 'Hold F4 — the most demanding note in the tenor octave.',       target: 60 },
    { note: 'G4',  desc: 'Hold G4 — approaching the upper register, stay relaxed.',      target: 60 },
  ],
  high: [
    { note: 'A4',  desc: 'Hold A4 — use the flick key and increase air speed.',           target: 58 },
    { note: 'B♭4', desc: 'Hold B♭4 — flick the octave key; watch for sharpness.',        target: 55 },
    { note: 'B4',  desc: 'Hold B4 — firm but flexible embouchure, cool fast air.',        target: 54 },
    { note: 'C5',  desc: 'Hold C5 — one of the least stable notes; use "ee" voicing.',   target: 52 },
    { note: 'D5',  desc: 'Hold D5 — high register needs focused air and light reed contact.', target: 50 },
    { note: 'E♭5', desc: 'Hold E♭5 — the top of the standard range; maximum air speed.', target: 48 },
  ],
};

function randomFrom(arr, n) {
  const shuffled = [...arr].sort(() => Math.random() - 0.5);
  return shuffled.slice(0, n);
}

function noteToExercise(entry) {
  return {
    title:    `${entry.note} Long Tone`,
    note:     entry.note,
    desc:     entry.desc,
    duration: 15,
    target:   entry.target,
  };
}

let _exercises   = [];
let _exIdx       = 0;
let _exResults   = [];
let _gRecording  = false;
let _gReed       = '';

function buildExercises() {
  const sessions = getSessions().slice(-5);
  const weak     = weakNotes(sessions, 3, 60);
  const exercises = [];

  // First: targeted exercises for weak notes from past sessions
  for (const { note } of weak) {
    // Find matching entry in NOTE_POOL for correct target/desc
    const allNotes = [...NOTE_POOL.low, ...NOTE_POOL.tenor, ...NOTE_POOL.high];
    const poolEntry = allNotes.find(e => e.note === note);
    exercises.push(poolEntry ? noteToExercise(poolEntry) : {
      title: `${note} Long Tone`, note, desc: `Hold ${note} steadily. Relax embouchure pressure.`,
      duration: 15, target: 55,
    });
  }

  // Pad to 4 exercises with random notes, one from each register
  const needed = Math.max(0, 4 - exercises.length);
  if (needed > 0) {
    const usedNotes = new Set(exercises.map(e => e.note));
    // Pick evenly across registers
    const picks = [
      ...randomFrom(NOTE_POOL.low.filter(e => !usedNotes.has(e.note)), 1),
      ...randomFrom(NOTE_POOL.tenor.filter(e => !usedNotes.has(e.note)), Math.ceil(needed / 2)),
      ...randomFrom(NOTE_POOL.high.filter(e => !usedNotes.has(e.note)), 1),
    ].filter(Boolean);

    for (const entry of picks) {
      if (exercises.length >= 4) break;
      exercises.push(noteToExercise(entry));
    }
  }

  // Shuffle so the order is unpredictable each session
  return exercises.slice(0, 4).sort(() => Math.random() - 0.5);
}

window.startGuided = function() {
  const select = document.getElementById('g-reed-name');
  _gReed     = select ? select.value.trim() : '';
  _exercises = buildExercises();
  _exIdx     = 0;
  _exResults = [];
  document.getElementById('guided-intro').style.display    = 'none';
  document.getElementById('guided-exercise').style.display = '';
  showExercise(0);
};

function showExercise(idx) {
  const ex = _exercises[idx];
  document.getElementById('g-progress-label').textContent = `Exercise ${idx + 1} of ${_exercises.length}`;
  document.getElementById('g-exercise-title').textContent  = ex.title;
  document.getElementById('g-exercise-desc').textContent   = ex.desc;
  document.getElementById('g-target').textContent          = `${ex.target}/100 stability`;
  document.getElementById('g-rec-label').textContent       = 'Tap to record';
  document.getElementById('g-feedback').style.display      = 'none';
  document.getElementById('g-next-wrap').style.display     = 'none';
  document.getElementById('g-rec-btn').classList.remove('active');

  // Render sheet music diagram
  const staffEl = document.getElementById('g-staff-diagram');
  if (staffEl) {
    // Use ex.note if present, otherwise extract from title (e.g. "C3 Long Tone" → "C3")
    const noteName = ex.note ?? (ex.title.match(/^([A-G][♭♯]?\d)/)?.[1] ?? null);
    if (noteName) {
      renderNoteOnStaff(noteName, staffEl);
    } else {
      staffEl.innerHTML = '';
    }
  }
}

window.toggleGuidedRecord = async function() {
  if (_gRecording) return;
  _gRecording = true;

  const ex    = _exercises[_exIdx];
  const btn   = document.getElementById('g-rec-btn');
  const label = document.getElementById('g-rec-label');

  btn.classList.add('active');

  try {
    const data = await recordSession({
      duration: ex.duration,
      onTick:   r => { label.textContent = r > 0 ? `Recording… ${r}s` : 'Analyzing…'; },
    });
    label.textContent = 'Done.';

    const { results } = await fetchFullResults();
    const score = Math.round((data.summary.overall_score ?? 0) * 100);
    const pass  = score >= ex.target;

    _exResults.push({ title: ex.title, score, target: ex.target, pass });

    const fb  = document.getElementById('g-feedback');
    fb.className = `p-feedback ${pass ? 'pass' : 'fail'}`;
    fb.innerHTML = pass
      ? `<strong>Pass</strong> — ${score}/100 (target ${ex.target}). Good work!`
      : buildFailFeedback(score, ex, data.summary, results);
    fb.style.display = '';

    const isLast = _exIdx >= _exercises.length - 1;
    const nextBtn = document.getElementById('g-next-btn');
    nextBtn.textContent = isLast ? 'See Results' : 'Next Exercise';
    document.getElementById('g-next-wrap').style.display = '';

  } catch (e) {
    label.textContent = 'Error: ' + e.message;
  } finally {
    _gRecording = false;
    btn.classList.remove('active');
  }
};

function buildFailFeedback(score, ex, summary, results) {
  const bias  = summary.mean_bias_cents ?? 0;
  const dir   = bias > 5 ? 'sharp' : bias < -5 ? 'flat' : 'in tune';
  const dirTip = bias > 5
    ? 'Try relaxing embouchure pressure and dropping your jaw slightly.'
    : bias < -5
      ? 'Try firming your lip support and directing more air into the reed.'
      : 'Your pitch center is good — focus on reducing moment-to-moment wobble.';
  return `<strong>Score: ${score}/100</strong> (target ${ex.target}). Your ${ex.title} is running ${dir}. ${dirTip}`;
}

window.nextExercise = function() {
  const isLast = _exIdx >= _exercises.length - 1;
  if (isLast) {
    showGuidedSummary();
  } else {
    _exIdx++;
    showExercise(_exIdx);
  }
};

function showGuidedSummary() {
  document.getElementById('guided-exercise').style.display = 'none';
  document.getElementById('guided-summary').style.display  = '';

  const avg   = Math.round(_exResults.reduce((a, r) => a + r.score, 0) / _exResults.length);
  const passes = _exResults.filter(r => r.pass).length;

  document.getElementById('gs-score').textContent    = avg;
  document.getElementById('gs-rating').textContent   = ratingMessage(avg);
  document.getElementById('gs-title').textContent    = passes === _exResults.length ? 'All exercises passed!' : `${passes}/${_exResults.length} exercises passed`;
  document.getElementById('gs-subtitle').textContent = ratingMessage(avg);
  setGauge('gs-gauge-fill', avg);

  document.getElementById('gs-exercise-list').innerHTML = _exResults.map(r => `
    <div style="display:flex;justify-content:space-between;padding:0.5rem 0;border-bottom:1px solid var(--p-border);font-size:0.88rem">
      <span style="color:var(--p-text)">${r.title}</span>
      <span style="color:${r.pass ? 'var(--p-green)' : 'var(--p-red)'}">
        ${r.score}/100 ${r.pass ? '✓' : '✗'}
      </span>
    </div>`).join('');
}

window.saveGuidedSession = function() {
  const avg = Math.round(_exResults.reduce((a, r) => a + r.score, 0) / _exResults.length);
  saveSession({
    date:         new Date().toISOString(),
    name:         'Guided session',
    mode:         'guided',
    reed:         _gReed,
    duration:     _exercises.reduce((a, e) => a + e.duration, 0),
    overallScore: avg,
    exercises:    _exResults,
    registerScores: { low: null, tenor: null, high: null },
    noteScores:   {},
  });
  document.getElementById('gs-save-msg').style.display = '';
};

// Init: build exercise description + check webcam availability
(function initGuided() {
  const sessions = getSessions().slice(-5);
  const weak     = weakNotes(sessions, 3, 60);
  const desc     = document.getElementById('guided-desc');
  if (weak.length) {
    desc.textContent = `Based on your recent sessions, we'll focus on: ${weak.map(w => w.note).join(', ')}.`;
  } else {
    desc.textContent = 'No past data found — we\'ll pick a random set from across the bassoon range.';
  }

  // Populate reed dropdown from localStorage
  const reedSelect = document.getElementById('g-reed-name');
  if (reedSelect) {
    const reeds = getReeds();
    reedSelect.innerHTML = '';
    if (reeds.length === 0) {
      reedSelect.innerHTML = '<option value="">No reeds saved yet</option>';
    } else {
      reeds.forEach(r => {
        const opt = document.createElement('option');
        opt.value = r.name;
        opt.textContent = r.name;
        reedSelect.appendChild(opt);
      });
    }
  }

  // Disable webcam checkbox if MediaPipe is unavailable
  fetch('/api/status').then(r => r.json()).then(data => {
    const cb   = document.getElementById('fp-with-video');
    const hint = document.getElementById('fp-video-hint');
    if (!data.video_available && cb) {
      cb.disabled = true;
      cb.checked  = false;
      if (hint) {
        hint.textContent = 'Webcam tracking unavailable — install opencv-python and mediapipe to enable.';
        hint.style.color = 'var(--p-red-lt)';
      }
    }
  }).catch(() => {});
})();

initSidebar();
