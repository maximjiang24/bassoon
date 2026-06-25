// Thin wrapper around the Flask recording/analysis API endpoints

export async function recordSession({ duration = 10, saveAs = null, withVideo = false, onTick } = {}) {
  if (withVideo) {
    throw new Error('Webcam embouchure recording is unavailable in hosted mode. Upload an audio/video pair from the analyzer page instead.');
  }
  if (!navigator.mediaDevices?.getUserMedia) {
    throw new Error('This browser does not support microphone recording.');
  }

  let remaining = duration;
  onTick?.(remaining);
  const ticker = setInterval(() => {
    remaining = Math.max(0, remaining - 1);
    onTick?.(remaining);
  }, 1000);

  try {
    const audioFile = await captureWav({ duration, saveAs });
    return await analyzeFile(audioFile);
  } finally {
    clearInterval(ticker);
  }
}

export async function analyzeFile(audioFile, videoFile = null) {
  const form = new FormData();
  form.append('file', audioFile);
  if (videoFile) form.append('video', videoFile);
  const res  = await fetch('/api/analyze_file', { method: 'POST', body: form });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error ?? 'Analysis failed');
  return data;
}

// Fetch full results (plots + numeric data) after a recording/analysis completes
export async function fetchFullResults() {
  const [pr, rr] = await Promise.all([fetch('/api/plots'), fetch('/api/results')]);
  const plots   = pr.ok  ? await pr.json()  : {};
  const results = rr.ok  ? await rr.json()  : {};
  return { plots, results };
}

export async function checkStatus() {
  try {
    const res = await fetch('/api/status');
    return await res.json();
  } catch {
    return { recording: false, has_results: false, video_available: false };
  }
}

async function captureWav({ duration, saveAs }) {
  const stream = await navigator.mediaDevices.getUserMedia({
    audio: {
      echoCancellation: false,
      noiseSuppression: false,
      autoGainControl: false,
    },
  });

  const AudioContext = window.AudioContext || window.webkitAudioContext;
  const context = new AudioContext();
  const sampleRate = context.sampleRate;
  const source = context.createMediaStreamSource(stream);
  const processor = context.createScriptProcessor(4096, 1, 1);
  const silence = context.createGain();
  silence.gain.value = 0;

  const chunks = [];
  processor.onaudioprocess = event => {
    chunks.push(new Float32Array(event.inputBuffer.getChannelData(0)));
  };

  source.connect(processor);
  processor.connect(silence);
  silence.connect(context.destination);

  try {
    if (context.state === 'suspended') await context.resume();
    await new Promise(resolve => setTimeout(resolve, duration * 1000));
  } finally {
    processor.disconnect();
    source.disconnect();
    silence.disconnect();
    stream.getTracks().forEach(track => track.stop());
    await context.close().catch(() => {});
  }

  const wav = encodeWav(mergeBuffers(chunks), sampleRate);
  const base = (saveAs || `recording_${Date.now()}`).replace(/[^a-z0-9_-]+/gi, '_');
  return new File([wav], `${base}.wav`, { type: 'audio/wav' });
}

function mergeBuffers(chunks) {
  const length = chunks.reduce((sum, chunk) => sum + chunk.length, 0);
  const merged = new Float32Array(length);
  let offset = 0;
  for (const chunk of chunks) {
    merged.set(chunk, offset);
    offset += chunk.length;
  }
  return merged;
}

function encodeWav(samples, sampleRate) {
  const buffer = new ArrayBuffer(44 + samples.length * 2);
  const view = new DataView(buffer);

  writeString(view, 0, 'RIFF');
  view.setUint32(4, 36 + samples.length * 2, true);
  writeString(view, 8, 'WAVE');
  writeString(view, 12, 'fmt ');
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  writeString(view, 36, 'data');
  view.setUint32(40, samples.length * 2, true);

  let offset = 44;
  for (const sample of samples) {
    const clamped = Math.max(-1, Math.min(1, sample));
    view.setInt16(offset, clamped < 0 ? clamped * 0x8000 : clamped * 0x7fff, true);
    offset += 2;
  }

  return new Blob([view], { type: 'audio/wav' });
}

function writeString(view, offset, value) {
  for (let i = 0; i < value.length; i++) {
    view.setUint8(offset + i, value.charCodeAt(i));
  }
}
