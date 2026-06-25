/**
 * embouchure_feedback.js
 *
 * Rule-based embouchure assessment grounded in published bassoon pedagogy,
 * plus an optional Claude AI call for richer narrative feedback.
 *
 * Rule sources:
 *   - A Modern Guide to Teaching and Playing the Bassoon (SUNY)
 *   - Bret Pimentel — Bassoon Jaw Movement Survey
 *   - Response and Intonation Tips by Register (SUNY)
 *   - Council of Canadian Bassoonists — Tenor Octave
 *   - Cayla Bellamy — Intonation
 */

// ── Register boundaries (Hz) ──────────────────────────────────────
const BB2 = 116.54;
const BB4 = 466.16;

function getRegister(hz) {
  if (!hz) return null;
  if (hz < BB2)   return 'low';
  if (hz <= BB4)  return 'tenor';
  return 'high';
}

// ── Optimal lip tension ranges by register ────────────────────────
const LIP_TENSION_RANGE = {
  low:   { min: 0.25, max: 0.50 },
  tenor: { min: 0.45, max: 0.70 },
  high:  { min: 0.65, max: 0.90 },
};

// ── Rule engine ───────────────────────────────────────────────────
// Returns an array of { severity: 'critical'|'warning'|'ok', text: string }
export function runRules({ emb, corr, summary, regCorr }) {
  const findings = [];
  const reg = getRegister(summary?.mean_hz);

  // 1. Jaw stability
  const jaw = emb?.jaw_stability;
  if (jaw != null) {
    if (jaw < 0.40) {
      findings.push({ severity: 'critical',
        text: `Jaw stability is very low (${jaw.toFixed(2)}). Your jaw is moving significantly during playing. This is one of the most harmful habits in bassoon technique — it slows articulation and directly disrupts pitch. Focus on keeping your jaw completely still; let only your tongue move.` });
    } else if (jaw < 0.70) {
      findings.push({ severity: 'warning',
        text: `Jaw stability (${jaw.toFixed(2)}) needs improvement. Some jaw movement was detected. Try lightly pressing your back teeth together and keeping them there throughout a phrase — only your tongue should move.` });
    } else {
      findings.push({ severity: 'ok',
        text: `Jaw stability is good (${jaw.toFixed(2)}). Your jaw stayed mostly still during playing.` });
    }
  }

  // 2. Jaw–intonation correlation
  const jawR = corr?.jaw_stability_vs_intonation?.r;
  if (jawR != null && Math.abs(jawR) > 0.45) {
    const dir = jawR > 0 ? 'higher jaw position → more stable pitch'
                         : 'jaw movement is destabilising your pitch';
    findings.push({ severity: 'warning',
      text: `Your jaw movement is strongly correlated with your intonation (r = ${jawR > 0 ? '+' : ''}${jawR.toFixed(2)}): ${dir}. Stabilising your jaw should be your top priority.` });
  }

  // 3. Lip tension
  const lt = emb?.mean_lip_tension;
  if (lt != null && reg) {
    const range = LIP_TENSION_RANGE[reg];
    if (lt < range.min) {
      findings.push({ severity: 'warning',
        text: `Lip tension is too low for the ${reg} register (${lt.toFixed(2)}, target ${range.min}–${range.max}). This causes an airy tone and flat pitch. Firm your lip seal slightly — not your jaw — so all the air goes through the reed rather than around it.` });
    } else if (lt > range.max) {
      findings.push({ severity: reg === 'high' && lt < 0.95 ? 'warning' : 'critical',
        text: `Lip tension is too high for the ${reg} register (${lt.toFixed(2)}, target ${range.min}–${range.max}). Over-pinching produces a thin, pinched tone and sharp pitch. Imagine gently hugging the reed rather than squeezing it — relax your embouchure grip and let more air do the work.` });
    } else {
      findings.push({ severity: 'ok',
        text: `Lip tension is well-matched to the ${reg} register (${lt.toFixed(2)}).` });
    }
  }

  // 4. Lip tension variance
  const ltVar = emb?.lip_tension_variance;
  if (ltVar != null && ltVar > 0.02) {
    findings.push({ severity: 'warning',
      text: `Lip tension varied considerably during the session (variance ${ltVar.toFixed(4)}). Inconsistent embouchure pressure causes pitch instability. Long tones with a tuner will train your muscles to maintain consistent pressure.` });
  }

  // 5. Mouth width variance
  const mwVar = emb?.mouth_width_variance;
  if (mwVar != null && mwVar > 40) {
    findings.push({ severity: mwVar > 100 ? 'critical' : 'warning',
      text: `Your mouth opening changed significantly during playing (width variance ${Math.round(mwVar)} px²). This is called embouchure collapse. Keep the same "hot pizza mouth" space between your teeth from the start to the end of every phrase, even in the high register.` });
  }

  // 6. Intonation tendency
  const bias    = summary?.mean_bias_cents;
  const tendency = summary?.tendency;
  if (tendency === 'sharp' && bias != null) {
    const cause = lt != null && lt > (LIP_TENSION_RANGE[reg]?.max ?? 0.8)
      ? 'Your lip tension is too high — this is the likely cause.'
      : 'This often means embouchure pressure is too high for this register.';
    findings.push({ severity: 'warning',
      text: `Your intonation is running sharp (+${Math.abs(bias).toFixed(1)} cents on average). ${cause} Try relaxing your embouchure grip, voicing lower ("ooh" instead of "ee"), and increasing air speed.` });
  } else if (tendency === 'flat' && bias != null) {
    const cause = lt != null && reg && lt < LIP_TENSION_RANGE[reg]?.min
      ? 'Your lip tension is below the target for this register — increase your lip seal slightly.'
      : 'This often means under-support. Increase air speed and check your reed hardness.';
    findings.push({ severity: 'warning',
      text: `Your intonation is running flat (${Math.abs(bias).toFixed(1)} cents below centre on average). ${cause}` });
  }

  // 7. Note-specific rules
  const note = summary?.mean_note;
  if (note) {
    const noteRules = {
      'B♭4': 'B♭4 tends sharp on bassoon. Loosen your lip grip, keep your jaw stable, voice lower ("ooh"), and direct more air through the reed.',
      'A4':  'A4 above the bass staff can run sharp. Relax embouchure pressure and increase air speed.',
      'B4':  'B4 tends sharp. Loosen your embouchure and try an alternate fingering if needed.',
      'C5':  'C5 is one of the most unstable notes on bassoon. Use the highest vowel voicing ("ee"), fast cool air, and firm but flexible embouchure.',
      'F3':  'F3 tends flat. Firm your lip seal slightly, add more air support, and maintain an open mouth shape.',
      'G3':  'G3 tends flat. Add more air support and check your reed — a harder reed makes this easier.',
      'D4':  'D4 in the tenor octave has the best tone when played slightly flat. Use embouchure support and choose a brighter alternate fingering if tuning is an issue.',
      'F4':  'F4 is the most demanding note in the tenor octave. It requires both embouchure and air support working together to stabilise pitch.',
    };
    if (noteRules[note]) {
      findings.push({ severity: 'warning', text: noteRules[note] });
    }
  }

  // 8. Embouchure consistency
  const cons = emb?.embouchure_consistency;
  if (cons != null) {
    if (cons >= 0.80) {
      findings.push({ severity: 'ok',
        text: `Overall embouchure consistency is excellent (${cons.toFixed(2)}). Your technique is stable and repeatable.` });
    } else if (cons >= 0.60) {
      findings.push({ severity: 'warning',
        text: `Embouchure consistency is moderate (${cons.toFixed(2)}). Some variation was detected across the session. Daily long tones — same note, same dynamic, three attempts — will help lock in consistent muscle memory.` });
    } else {
      findings.push({ severity: 'critical',
        text: `Embouchure consistency is low (${cons.toFixed(2)}). Your embouchure is still searching for its position. Focus on a single long tone every day: pick one note, hold it for 30 seconds, and compare three attempts until they sound identical.` });
    }
  }

  return findings;
}

// ── Prioritise findings for display ──────────────────────────────
export function prioritisedFindings(findings) {
  const order = { critical: 0, warning: 1, ok: 2 };
  return [...findings].sort((a, b) => order[a.severity] - order[b.severity]);
}

// ── AI feedback via Flask endpoint ───────────────────────────────
export async function fetchAIFeedback({ emb, corr, summary, regCorr }) {
  const res = await fetch('/api/embouchure_feedback', {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify({
      embouchure:            emb,
      correlation:           corr,
      summary,
      register_correlation:  regCorr,
    }),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error ?? 'AI feedback failed');
  return data.feedback;
}

// ── Severity colour helper ────────────────────────────────────────
export function severityColor(severity) {
  if (severity === 'critical') return 'var(--p-red-lt)';
  if (severity === 'warning')  return 'var(--p-amber)';
  return 'var(--p-green-lt)';
}
