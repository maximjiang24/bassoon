/* Tab switching */
document.querySelectorAll(".tab").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
    document.querySelectorAll(".tab-content").forEach(c => c.classList.remove("active"));
    btn.classList.add("active");
    document.getElementById("tab-" + btn.dataset.tab).classList.add("active");
  });
});

/* Duration slider */
const durationSlider = document.getElementById("duration");
const durationLabel  = document.getElementById("duration-label");
durationSlider.addEventListener("input", () => {
  durationLabel.textContent = durationSlider.value + " s";
});

/* Plot tab switching */
let _plots = {};
let _currentPlotKey = "pitch_contour";

document.querySelectorAll(".plot-tab").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".plot-tab").forEach(t => t.classList.remove("active"));
    btn.classList.add("active");
    showPlot(btn.dataset.plot);
  });
});

function showPlot(key) {
  const img = document.getElementById("plot-img");
  if (_plots[key]) {
    img.src = "data:image/png;base64," + _plots[key];
    img.alt = key.replace(/_/g, " ");
    _currentPlotKey = key;
  }
}

/* Download */
document.getElementById("btn-download-plot").addEventListener("click", () => {
  if (!_plots[_currentPlotKey]) return;
  const a = document.createElement("a");
  a.href = "data:image/png;base64," + _plots[_currentPlotKey];
  a.download = _currentPlotKey + ".png";
  a.click();
});

/* Status helper */
function setStatus(msg, type = "") {
  const bar = document.getElementById("status-bar");
  bar.textContent = msg;
  bar.className = "status" + (type ? " " + type : "");
  bar.classList.remove("hidden");
}

/* Show summary */
function showSummary(summary) {
  document.getElementById("s-rating").textContent   = summary.rating;
  document.getElementById("s-score").textContent    = summary.overall_score.toFixed(3);
  document.getElementById("s-note").textContent     = summary.mean_note +
    (summary.mean_hz ? ` (${summary.mean_hz} Hz)` : "");

  // Show which bassoon register the mean pitch falls in
  const regEl = document.getElementById("s-register");
  if (regEl && summary.mean_hz) {
    const hz = summary.mean_hz;
    const reg = hz < 116.54 ? "Low register (below B♭2)"
              : hz <= 466.16 ? "Tenor register (B♭2 – B♭4)"
              : "High register (above B♭4)";
    regEl.textContent = reg;
  }
  document.getElementById("s-bias").textContent     =
    summary.mean_bias_cents != null ? (summary.mean_bias_cents > 0 ? "+" : "") + summary.mean_bias_cents + " ¢" : "—";
  document.getElementById("s-tendency").textContent = summary.tendency;
  document.getElementById("s-voiced").textContent   = summary.voiced_pct + "%";
  document.getElementById("s-duration").textContent = summary.duration_s.toFixed(1) + " s";
  document.getElementById("s-unstable").textContent = summary.unstable_count;

  const embStat = document.getElementById("stat-emb");
  const corrStat = document.getElementById("stat-corr");
  const faceStat = document.getElementById("stat-face");

  if (summary.has_video) {
    embStat.classList.remove("hidden");
    faceStat.classList.remove("hidden");
    document.getElementById("s-embouchure").textContent =
      summary.embouchure_score != null ? summary.embouchure_score.toFixed(3) : "—";
    document.getElementById("s-face").textContent =
      summary.face_detected_pct != null ? summary.face_detected_pct.toFixed(1) + "%" : "—";
    if (summary.overall_correlation != null) {
      corrStat.classList.remove("hidden");
      document.getElementById("s-correlation").textContent = summary.overall_correlation.toFixed(3);
    } else {
      corrStat.classList.add("hidden");
    }
  } else {
    embStat.classList.add("hidden");
    corrStat.classList.add("hidden");
    faceStat.classList.add("hidden");
  }

  if (summary.video_warning) {
    setStatus(summary.video_warning, "error");
  }

  document.getElementById("summary-panel").classList.remove("hidden");
}

function showRegions(regions) {
  const tbody = document.getElementById("regions-body");
  const noData = document.getElementById("no-regions");
  tbody.innerHTML = "";

  if (!regions.length) {
    noData.classList.remove("hidden");
  } else {
    noData.classList.add("hidden");
    regions.forEach(r => {
      const tr = document.createElement("tr");
      tr.innerHTML = `<td>${r.start}</td><td>${r.end}</td><td>${r.note}</td><td>${r.variance}</td>`;
      tbody.appendChild(tr);
    });
  }
  document.getElementById("regions-panel").classList.remove("hidden");
}

function showRegisterStats(reg, unstableCounts) {
  const tbody = document.getElementById("register-body");
  tbody.innerHTML = "";
  ["low", "tenor", "high"].forEach(name => {
    const d = reg[name] || {};
    const tr = document.createElement("tr");
    const score   = d.mean != null ? d.mean.toFixed(3) : "—";
    const frac    = d.time_fraction != null ? (d.time_fraction * 100).toFixed(1) + "%" : "—";
    const uCount  = unstableCounts && unstableCounts[name] != null ? unstableCounts[name] : "—";
    tr.innerHTML = `<td style="text-transform:capitalize">${name}</td><td>${frac}</td><td>${score}</td><td>${uCount}</td>`;
    tbody.appendChild(tr);
  });
  document.getElementById("register-panel").classList.remove("hidden");
}

function showEmbouchure(embData, corrData, regCorr, interpretation) {
  const panel = document.getElementById("embouchure-panel");
  if (!embData) {
    panel.classList.add("hidden");
    return;
  }

  const set = (id, val, decimals = 3, suffix = "") => {
    const el = document.getElementById(id);
    el.textContent = (val == null) ? "—" : (val.toFixed(decimals) + suffix);
  };

  set("e-consistency", embData.embouchure_consistency, 3);
  set("e-jaw",         embData.jaw_stability,          3);
  set("e-mw",          embData.mean_mouth_width,       1, " px");
  set("e-mwv",         embData.mouth_width_variance,   2, " px²");
  set("e-lt",          embData.mean_lip_tension,       3);
  set("e-ltv",         embData.lip_tension_variance,   4);

  const labels = {
    mouth_width_vs_stability:    "Mouth width vs Stability",
    mouth_height_vs_stability:   "Mouth height vs Stability",
    jaw_stability_vs_intonation: "Jaw position vs Stability",
    lip_tension_vs_stability:    "Lip tension vs Stability",
  };
  const cbody = document.getElementById("correlation-body");
  cbody.innerHTML = "";
  Object.keys(labels).forEach(key => {
    const entry = (corrData && corrData[key]) || { r: null, p: null };
    const r = entry.r;
    const p = entry.p;
    const strength = (r == null) ? "—" :
      (Math.abs(r) >= 0.7 ? "strong" : Math.abs(r) >= 0.4 ? "moderate" : "weak");
    const sig = (p != null && p < 0.05) ? " *" : "";
    const tr = document.createElement("tr");
    tr.innerHTML = `<td>${labels[key]}</td>
                    <td>${r == null ? "—" : (r >= 0 ? "+" : "") + r.toFixed(3) + sig}</td>
                    <td>${p == null ? "—" : p.toFixed(3)}</td>
                    <td>${strength}</td>`;
    cbody.appendChild(tr);
  });

  const rbody = document.getElementById("reg-corr-body");
  rbody.innerHTML = "";
  ["low", "tenor", "high"].forEach(reg => {
    const v = regCorr ? regCorr[reg] : null;
    const tr = document.createElement("tr");
    tr.innerHTML = `<td style="text-transform:capitalize">${reg}</td>
                    <td>${v == null ? "—" : v.toFixed(3)}</td>`;
    rbody.appendChild(tr);
  });

  const ul = document.getElementById("interpretation-list");
  ul.innerHTML = "";
  (interpretation || []).forEach(line => {
    const li = document.createElement("li");
    li.textContent = line;
    ul.appendChild(li);
  });

  panel.classList.remove("hidden");
}

function updatePlotTabs(hasVideo) {
  const videoTabs = ["embouchure_timeline", "embouchure_intonation", "correlation_heatmap"];
  videoTabs.forEach(key => {
    const tab = document.querySelector(`.plot-tab[data-plot="${key}"]`);
    if (tab) tab.classList.toggle("hidden", !hasVideo);
  });
}

async function loadPlots(hasVideo) {
  const res = await fetch("/api/plots");
  if (!res.ok) return;
  _plots = await res.json();
  updatePlotTabs(hasVideo);
  document.getElementById("plots-panel").classList.remove("hidden");
  showPlot("pitch_contour");
  document.querySelectorAll(".plot-tab").forEach(t => t.classList.remove("active"));
  const first = document.querySelector('.plot-tab[data-plot="pitch_contour"]');
  if (first) first.classList.add("active");
}

async function loadResults() {
  const res = await fetch("/api/results");
  if (!res.ok) return;
  const data = await res.json();
  showRegions(data.unstable_regions || []);
  showRegisterStats(data.register_stats || {}, data.register_unstable_counts || {});
  showEmbouchure(data.embouchure, data.correlation, data.register_correlation, data.interpretation);
}

/* Help modal */
document.getElementById("btn-help").addEventListener("click", () => {
  document.getElementById("help-overlay").classList.remove("hidden");
  document.body.style.overflow = "hidden";
});
document.getElementById("btn-help-close").addEventListener("click", closeHelp);
document.getElementById("help-overlay").addEventListener("click", e => {
  if (e.target === document.getElementById("help-overlay")) closeHelp();
});
document.addEventListener("keydown", e => {
  if (e.key === "Escape") closeHelp();
});
function closeHelp() {
  document.getElementById("help-overlay").classList.add("hidden");
  document.body.style.overflow = "";
}

/* Status check at load — show webcam-availability hint */
async function checkStatus() {
  try {
    const res = await fetch("/api/status");
    const data = await res.json();
    const cb = document.getElementById("with-video");
    const hint = document.getElementById("video-hint");
    if (!data.video_available) {
      cb.disabled = true;
      cb.checked = false;
      hint.textContent = "Webcam tracking unavailable (install opencv-python and mediapipe).";
      hint.style.color = "var(--danger)";
    }
  } catch (e) { /* ignore */ }
}
checkStatus();

/* Record */
document.getElementById("btn-record").addEventListener("click", async () => {
  const btn      = document.getElementById("btn-record");
  const btnText  = document.getElementById("btn-record-text");
  const duration = parseInt(durationSlider.value, 10);
  const saveAs   = document.getElementById("save-as").value.trim() || null;
  const withVideo = document.getElementById("with-video").checked;

  btn.disabled = true;
  btnText.textContent = "Recording…";
  btnText.classList.add("recording");

  let remaining = duration;
  setStatus(`Recording — ${remaining}s remaining… ${withVideo ? "face the camera and " : ""}play now`);
  const countdown = setInterval(() => {
    remaining--;
    if (remaining > 0) {
      setStatus(`Recording — ${remaining}s remaining…`);
    } else {
      setStatus("Analyzing…");
      clearInterval(countdown);
    }
  }, 1000);

  try {
    const res = await fetch("/api/record", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ duration, save_as: saveAs, with_video: withVideo }),
    });
    const data = await res.json();

    if (!res.ok) {
      setStatus("Error: " + (data.error || "Unknown error"), "error");
      return;
    }

    setStatus("Analysis complete.", "success");
    showSummary(data.summary);
    await Promise.all([loadPlots(data.summary.has_video), loadResults()]);

  } catch (err) {
    setStatus("Network error: " + err.message, "error");
  } finally {
    clearInterval(countdown);
    btn.disabled = false;
    btnText.textContent = "Start Recording";
    btnText.classList.remove("recording");
  }
});

/* Upload */
document.getElementById("btn-upload").addEventListener("click", async () => {
  const fileInput  = document.getElementById("wav-file");
  const videoInput = document.getElementById("video-file");
  if (!fileInput.files.length) {
    setStatus("Please select a WAV file first.", "error");
    return;
  }

  const btn = document.getElementById("btn-upload");
  btn.disabled = true;
  setStatus(videoInput.files.length ? "Analyzing audio + video…" : "Analyzing file…");

  const form = new FormData();
  form.append("file", fileInput.files[0]);
  if (videoInput.files.length) {
    form.append("video", videoInput.files[0]);
  }

  try {
    const res = await fetch("/api/analyze_file", { method: "POST", body: form });
    const data = await res.json();

    if (!res.ok) {
      setStatus("Error: " + (data.error || "Unknown error"), "error");
      return;
    }

    setStatus("Analysis complete.", "success");
    showSummary(data.summary);
    await Promise.all([loadPlots(data.summary.has_video), loadResults()]);

  } catch (err) {
    setStatus("Network error: " + err.message, "error");
  } finally {
    btn.disabled = false;
  }
});
