// Renders a single note on a small SVG staff for the guided exercise card.
// Supports bass, tenor, and treble clefs across the full bassoon range (B♭1–E♭5).

// Diatonic step index within an octave (C=0 … B=6)
const DIATONIC = { C:0, D:1, E:2, F:3, G:4, A:5, B:6 };

function parseNote(name) {
  const m = name.match(/^([A-G])([♭♯]?)(\d)$/);
  if (!m) return null;
  const [, letter, acc, octStr] = m;
  const octave = parseInt(octStr, 10);
  const semis  = { C:0,D:2,E:4,F:5,G:7,A:9,B:11 };
  const semi   = semis[letter] + (acc === '♭' ? -1 : acc === '♯' ? 1 : 0);
  const midi   = (octave + 1) * 12 + semi;
  return { letter, acc, octave, midi };
}

function diatonicPos(letter, octave) {
  return octave * 7 + (DIATONIC[letter] ?? 0);
}

function selectClef(midi) {
  if (midi < 67) return 'bass';
  if (midi < 78) return Math.random() < 0.55 ? 'bass' : 'tenor';
  return Math.random() < 0.5 ? 'tenor' : 'treble';
}

const W = 160, H = 80;
const LINE_GAP = 7;
const STAFF_TOP = 22;
const NOTE_X = 112;
const CLEF_X = 8;

function lineY(i) { return STAFF_TOP + i * LINE_GAP; }

function staffSlot(clef, letter, octave) {
  const pos = diatonicPos(letter, octave);
  const REF = { bass: 18, tenor: 22, treble: 30 };
  return pos - REF[clef];
}

function noteY(slot) {
  return lineY(4) - slot * (LINE_GAP / 2);
}

function svgStaffLines() {
  let s = '';
  for (let i = 0; i < 5; i++) {
    s += `<line x1="28" x2="${W - 8}" y1="${lineY(i)}" y2="${lineY(i)}" stroke="#64748b" stroke-width="0.8"/>`;
  }
  return s;
}

function svgLedgerLines(slot, acc) {
  const lw = 14;
  const ax = acc ? -8 : 0;
  let s = '';
  for (let st = -2; st >= slot; st -= 2) {
    const y = noteY(st);
    s += `<line x1="${NOTE_X + ax - lw/2}" x2="${NOTE_X + lw/2}" y1="${y}" y2="${y}" stroke="#64748b" stroke-width="0.8"/>`;
  }
  for (let st = 10; st <= slot; st += 2) {
    const y = noteY(st);
    s += `<line x1="${NOTE_X + ax - lw/2}" x2="${NOTE_X + lw/2}" y1="${y}" y2="${y}" stroke="#64748b" stroke-width="0.8"/>`;
  }
  return s;
}

function svgNoteHead(slot, acc) {
  const y  = noteY(slot);
  const rx = 5.2, ry = 3.8;
  let s = '';
  if (acc === '♭') {
    s += `<text x="${NOTE_X - 11}" y="${y + 4}" font-size="13" fill="#e2e8f0" font-family="serif">♭</text>`;
  } else if (acc === '♯') {
    s += `<text x="${NOTE_X - 12}" y="${y + 3}" font-size="11" fill="#e2e8f0" font-family="serif">♯</text>`;
  }
  s += `<ellipse cx="${NOTE_X}" cy="${y}" rx="${rx}" ry="${ry}"
           transform="rotate(-15,${NOTE_X},${y})" fill="#e2e8f0"/>`;
  s += `<line x1="${NOTE_X + rx - 1}" x2="${NOTE_X + rx - 1}"
           y1="${y}" y2="${y - 26}" stroke="#e2e8f0" stroke-width="1.2"/>`;
  return s;
}

function svgBassClef() {
  const cx = CLEF_X + 16;
  const d1y = lineY(1) - 1.5, d2y = lineY(1) + 5;
  return `
    <path d="M${cx+2},${lineY(0)+2} A9,10 0 0 0 ${cx-7},${lineY(2)} A9,10 0 0 0 ${cx+2},${lineY(4)-2}"
          fill="none" stroke="#64748b" stroke-width="2" stroke-linecap="round"/>
    <circle cx="${cx+8}" cy="${d1y}" r="1.8" fill="#64748b"/>
    <circle cx="${cx+8}" cy="${d2y}" r="1.8" fill="#64748b"/>`;
}

function svgTenorClef() {
  const x  = CLEF_X + 2;
  const cy = lineY(2);
  const top = lineY(0), bot = lineY(4);
  return `
    <rect x="${x}"   y="${top}" width="2.5" height="${bot-top}" rx="1" fill="#64748b"/>
    <rect x="${x+5}" y="${top}" width="2.5" height="${bot-top}" rx="1" fill="#64748b"/>
    <path d="M${x+8},${top} Q${x+19},${top} ${x+19},${cy-0.5}"
          fill="none" stroke="#64748b" stroke-width="2" stroke-linecap="round"/>
    <path d="M${x+8},${bot} Q${x+19},${bot} ${x+19},${cy+0.5}"
          fill="none" stroke="#64748b" stroke-width="2" stroke-linecap="round"/>
    <circle cx="${x+19}" cy="${cy}" r="2.2" fill="#64748b"/>`;
}

function svgTrebleClef() {
  const x = CLEF_X + 14, y = lineY(4) + 4;
  return `
    <path d="M${x},${y}
             C${x+10},${y-8} ${x+14},${y-20} ${x+5},${y-30}
             C${x-4},${y-40} ${x-10},${y-32} ${x-6},${y-24}
             C${x-2},${y-16} ${x+8},${y-18} ${x+8},${y-30}
             C${x+8},${y-44} ${x-2},${y-50} ${x-2},${y-50}"
          fill="none" stroke="#64748b" stroke-width="1.8" stroke-linecap="round"/>
    <line x1="${x-8}" x2="${x+4}" y1="${lineY(4)+8}" y2="${lineY(4)+8}"
          stroke="#64748b" stroke-width="1.5"/>`;
}

export function renderNoteOnStaff(noteName, containerEl) {
  const parsed = parseNote(noteName);
  if (!parsed) { containerEl.innerHTML = ''; return; }

  const { letter, acc, octave, midi } = parsed;
  const clef = selectClef(midi);
  const slot = staffSlot(clef, letter, octave);

  const clefSvg = clef === 'bass'  ? svgBassClef()
                : clef === 'tenor' ? svgTenorClef()
                :                   svgTrebleClef();

  containerEl.innerHTML = `
    <svg xmlns="http://www.w3.org/2000/svg"
         viewBox="0 0 ${W} ${H}" width="${W}" height="${H}"
         style="overflow:visible;display:block">
      ${svgStaffLines()}
      ${clefSvg}
      ${svgLedgerLines(slot, acc)}
      ${svgNoteHead(slot, acc)}
    </svg>`;
}
