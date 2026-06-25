// Transforms Flask API response data into the storage data model

// Convert 0–1 stability score to 0–100 integer
export function toScore(s) { return Math.round((s ?? 0) * 100); }

export function registerScores(registerStats) {
  const s = reg => {
    const d = registerStats?.[reg];
    return d?.mean != null ? Math.round(d.mean * 100) : null;
  };
  return { low: s('low'), tenor: s('tenor'), high: s('high') };
}

// Aggregate per-note stability from note_breakdown (preferred) or unstable_regions (fallback)
export function buildNoteScores(unstableRegions, noteBreakdown) {
  if (noteBreakdown && noteBreakdown.length) {
    const acc = {};
    for (const seg of noteBreakdown) {
      if (!seg.note || seg.note === '?') continue;
      acc[seg.note] ??= { totalScore: 0, totalVariance: 0, count: 0 };
      acc[seg.note].totalScore    += seg.stability_score ?? 0;
      acc[seg.note].totalVariance += seg.variance ?? 0;
      acc[seg.note].count++;
    }
    const out = {};
    for (const [note, d] of Object.entries(acc)) {
      out[note] = {
        score:    Math.round(100 * (d.totalScore / d.count)),
        variance: Math.round(d.totalVariance / d.count),
        count:    d.count,
      };
    }
    return out;
  }

  // Fallback: derive from unstable_regions only
  const acc = {};
  for (const r of (unstableRegions ?? [])) {
    if (!r.note || r.note === '?') continue;
    acc[r.note] ??= { count: 0, totalVariance: 0 };
    acc[r.note].count++;
    acc[r.note].totalVariance += r.variance ?? 0;
  }
  const out = {};
  for (const [note, d] of Object.entries(acc)) {
    const avg = d.totalVariance / d.count;
    out[note] = {
      score:    Math.round(100 * Math.exp(-avg / 400)),
      variance: Math.round(avg),
      count:    d.count,
    };
  }
  return out;
}

export function buildSessionData({ summary, results, name, reed, mode }) {
  return {
    date:           new Date().toISOString(),
    name:           name  ?? 'Untitled session',
    mode:           mode  ?? 'free',
    reed:           reed  ?? '',
    duration:       Math.round(summary.duration_s ?? 0),
    overallScore:   toScore(summary.overall_score),
    registerScores: registerScores(results.register_stats),
    noteScores:     buildNoteScores(results.unstable_regions, results.note_breakdown),
    noteBreakdown:  results.note_breakdown ?? [],
    tendency:       summary.tendency ?? 'centred',
    voicedPct:      summary.voiced_pct ?? 0,
  };
}

export function ratingLabel(score) {
  if (score >= 80) return 'Excellent';
  if (score >= 60) return 'Good';
  if (score >= 40) return 'Fair';
  return 'Needs work';
}

export function ratingMessage(score) {
  if (score >= 80) return 'Excellent — your intonation is very stable';
  if (score >= 60) return 'Good — a few notes need attention';
  if (score >= 40) return 'Fair — focus on the tenor register';
  return 'Needs work — try long tones on problem notes first';
}

export function scoreColor(score) {
  if (score >= 80) return '#22c55e';
  if (score >= 60) return '#14b8a6';
  if (score >= 40) return '#eab308';
  return '#ef4444';
}

// Find the weakest notes across recent sessions (used by guided exercise picker)
export function weakNotes(sessions, limit = 5, threshold = 60) {
  const acc = {};
  for (const s of sessions) {
    for (const [note, d] of Object.entries(s.noteScores ?? {})) {
      acc[note] ??= { total: 0, count: 0 };
      acc[note].total += d.score;
      acc[note].count++;
    }
  }
  return Object.entries(acc)
    .map(([note, d]) => ({ note, avg: Math.round(d.total / d.count) }))
    .filter(n => n.avg < threshold)
    .sort((a, b) => a.avg - b.avg)
    .slice(0, limit);
}
