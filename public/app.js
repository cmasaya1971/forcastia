/* ============================================================
   Verifiquemos · Banrural — lógica de front-end
   - Botones de escenario: llaman tools directamente (funciona sin voz)
   - Voz: Realtime API de OpenAI vía WebRTC; el modelo llama las tools
   ============================================================ */
"use strict";

const $ = (id) => document.getElementById(id);
const remoteAudio = $("remote-audio");

let pc = null, dc = null, micStream = null, live = false, muted = false, greeted = false;
let asstBuffer = "", asstMsgEl = null;
let audioCtx = null, analyser = null, freqData = null, waveRAF = null, speaking = false;

/* -------- Guía "How To": preguntas por tema --------
   Cada pregunta: {texto (lo que se le "dice" al asistente), tool, args} */
const CATEGORIES = [
  { titulo: "Riesgo de originación · la señal del día cero", icono: "⚠", clase: "orange", preguntas: [
    { texto: "¿Realmente el score de entrada me dice algo sobre la mora de hoy?", tool: "curva_mora_por_banda", args: {} },
    { texto: "¿Cuánta gente riesgosa por reputación tengo dentro de la cartera?", tool: "impacto_adverse_media", args: {} },
    { texto: "¿El dato de que el ingreso no cuadra con la actividad sirve para algo?", tool: "incongruencia_ingreso_actividad", args: {} },
    { texto: "¿La coincidencia facial vale la pena?", tool: "biometria_fraude", args: {} },
    { texto: "Tengo miles de PEP, ¿cuáles me deben quitar el sueño?", tool: "contraste_pep", args: {} },
    { texto: "¿Qué tan expuesto estoy a flujos internacionales de riesgo?", tool: "exposicion_sancionados", args: {} },
  ]},
  { titulo: "Monitoreo y tendencias · lo que cambió", icono: "🔄", clase: "", preguntas: [
    { texto: "Compara la última corrida con la anterior, ¿qué se movió?", tool: "comparativo_corridas", args: {} },
    { texto: "¿Estamos originando peor que antes?", tool: "evolucion_originacion", args: {} },
    { texto: "Busca riesgos futuros a partir de la característica PEP de la cartera.", tool: "crecimiento_pep", args: {} },
  ]},
  { titulo: "Oportunidades comerciales · colocación", icono: "✦", clase: "orange", preguntas: [
    { texto: "¿A quién puedo venderle sin arriesgarme?", tool: "segmento_precalificados", args: {} },
    { texto: "¿Tengo empresarios disfrazados de clientes individuales?", tool: "empresarios_ocultos", args: {} },
    { texto: "¿Le saco provecho a los contratistas del Estado?", tool: "proveedores_estado", args: {} },
    { texto: "¿Tengo mercado para productos en divisas?", tool: "segmento_internacional", args: {} },
    { texto: "Dame algo que baje el riesgo y genere ingreso a la vez.", tool: "oportunidad_seguros", args: {} },
    { texto: "¿Quién mejoró y está listo para el siguiente producto?", tool: "clientes_evolucionaron", args: {} },
  ]},
  { titulo: "Cruce entre fuentes · lo que ninguna ve sola", icono: "◈", clase: "", preguntas: [
    { texto: "¿Qué perfil de cliente concentra más mora en la cartera de consumo?", tool: "perfil_demografico_riesgo", args: {} },
    { texto: "¿El análisis de VERITAS predijo bien la mora real?", tool: "veritas_predice_mora", args: {} },
    { texto: "¿Hay clientes que pasaron limpios el onboarding pero hoy el modelo ve en riesgo?", tool: "riesgo_oculto", args: {} },
    { texto: "Dame los clientes con probabilidad de mora sobre 70%, por monto expuesto, y por qué.", tool: "clientes_alta_probabilidad", args: {} },
    { texto: "¿A quién le puedo colocar tarjeta con bajo riesgo en Suroccidente?", tool: "colocacion_segura", args: { region: "Suroccidente" } },
    { texto: "Cruza todo y dame el segmento de mayor riesgo emergente para el próximo año.", tool: "segmento_riesgo_emergente", args: {} },
  ]},
];

function initGuide() {
  const wrap = $("guide-cats");
  wrap.innerHTML = "";
  CATEGORIES.forEach((cat) => {
    const card = document.createElement("div");
    card.className = "cat " + (cat.clase || "");
    const head = `<div class="cat-head"><div class="cat-ico">${cat.icono}</div>
                  <div class="cat-title">${esc(cat.titulo)}</div></div>`;
    card.innerHTML = head;
    cat.preguntas.forEach((p) => {
      const b = document.createElement("button");
      b.className = "q-chip";
      b.textContent = p.texto;
      b.onclick = () => askQuestion(p);
      card.appendChild(b);
    });
    wrap.appendChild(card);
  });
}

/* Al elegir una pregunta:
   - en vivo: se la "decimos" al asistente para que la conteste por voz;
     él llamará la tool, que a su vez pinta el gráfico.
   - sin voz: ejecutamos la tool directamente y mostramos la información. */
function askQuestion(p) {
  if (live && dc && dc.readyState === "open") {
    sendUserText(p.texto);
  } else {
    callTool(p.tool, p.args);
  }
}

function showGuide() {
  $("stage-guide").hidden = false;
  $("stage-content").hidden = true;
}
function hideGuide() {
  $("stage-guide").hidden = true;
  $("stage-content").hidden = false;
}

/* -------- Llamar tool en el backend y renderizar -------- */
async function callTool(name, args) {
  setStatus("think", "Consultando…");
  try {
    const res = await fetch("/api/tool", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, arguments: args || {} }),
    }).then((r) => r.json());
    if (res.error) { console.warn(res.error); }
    else renderVisual(res);
    setStatus(live ? "live" : "idle", live ? "En vivo" : "Listo");
    return res;
  } catch (e) {
    console.error(e); setStatus("error", "Error de datos");
    return { error: String(e) };
  }
}

/* ============================================================
   RENDER
   ============================================================ */
function renderVisual(res) {
  if (res && res.error) return;
  hideGuide();
  $("viz-title").textContent = res.titulo || "";
  $("viz-resumen").textContent = res.resumen || "";
  renderKpis(res.kpis || []);
  const body = $("viz-body");
  body.innerHTML = "";
  const v = res.visual || { tipo: "none" };
  switch (v.tipo) {
    case "bar":          body.appendChild(barChart(v)); break;
    case "geo_bar":      body.appendChild(barChart({ ...v, orientacion: "horizontal" })); break;
    case "line":         body.appendChild(lineChart(v)); break;
    case "table":        body.appendChild(tableView(v)); break;
    case "client_detail":body.appendChild(clientDetail(v)); break;
    default: break; // kpi / none -> solo KPIs
  }
}

function renderKpis(kpis) {
  const row = $("viz-kpis"); row.innerHTML = "";
  kpis.forEach((k) => {
    const el = document.createElement("div");
    el.className = "kpi t-" + (k.tono || "neutro");
    el.innerHTML = `<div class="k-label">${esc(k.label)}</div>
      <div class="k-val">${esc(String(k.valor))}${k.sufijo ? `<span class="k-suf">${esc(k.sufijo)}</span>` : ""}</div>`;
    row.appendChild(el);
  });
}

const SVGNS = "http://www.w3.org/2000/svg";
function svgEl(tag, attrs) {
  const e = document.createElementNS(SVGNS, tag);
  for (const k in attrs) e.setAttribute(k, attrs[k]);
  return e;
}
function toneClass(t) {
  return t === "alerta" ? "c-alert" : t === "bueno" ? "c-good" : t === "teal" ? "c-teal" : "c-neutral";
}

/* ---- Bar chart (vertical u horizontal) ---- */
function barChart(v) {
  const series = v.series || [];
  const horizontal = v.orientacion === "horizontal";
  const maxV = Math.max(1, ...series.map((s) => s.valor));
  const W = 820, rowH = 46, padL = horizontal ? 170 : 40, padR = 60, padT = 12;

  if (horizontal) {
    const H = padT * 2 + series.length * rowH;
    const svg = svgEl("svg", { class: "chart", viewBox: `0 0 ${W} ${H}`, role: "img" });
    series.forEach((s, i) => {
      const y = padT + i * rowH + 8;
      const bw = (W - padL - padR) * (s.valor / maxV);
      svg.appendChild(svgEl("text", { x: padL - 12, y: y + 15, "text-anchor": "end", class: "axis-label" })).textContent = trunc(s.nombre, 28);
      svg.appendChild(svgEl("rect", { x: padL, y, width: W - padL - padR, height: 22, rx: 6, class: "bar-track" }));
      const fill = svgEl("rect", { x: padL, y, width: bw, height: 22, rx: 6, class: "bar-fill " + toneClass(s.tono) });
      svg.appendChild(fill);
      svg.appendChild(svgEl("text", { x: padL + bw + 8, y: y + 16, class: "val-label" })).textContent = fmt(s.valor);
    });
    return svg;
  }
  // vertical
  const H = 320, base = H - 46, colW = (W - padL - padR) / series.length;
  const svg = svgEl("svg", { class: "chart", viewBox: `0 0 ${W} ${H}`, role: "img" });
  [0, 0.25, 0.5, 0.75, 1].forEach((g) => {
    const y = padT + (base - padT) * (1 - g);
    svg.appendChild(svgEl("line", { x1: padL, y1: y, x2: W - padR, y2: y, class: "grid-line" }));
  });
  series.forEach((s, i) => {
    const bh = (base - padT) * (s.valor / maxV);
    const x = padL + i * colW + colW * 0.22, bw = colW * 0.56;
    svg.appendChild(svgEl("rect", { x, y: base - bh, width: bw, height: bh, rx: 7, class: "bar-fill " + toneClass(s.tono) }));
    svg.appendChild(svgEl("text", { x: x + bw / 2, y: base - bh - 9, "text-anchor": "middle", class: "val-label" })).textContent = fmt(s.valor);
    appendBarLabel(svg, s.nombre, x + bw / 2, base + 20, Math.max(10, Math.floor(colW / 8)));
  });
  return svg;
}

/* Etiqueta de barra: una línea, o dos si el nombre es largo (evita recortes) */
function appendBarLabel(svg, name, cx, y, maxLine) {
  name = String(name);
  maxLine = maxLine || 15;
  const put = (txt, yy) => {
    const t = svgEl("text", { x: cx, y: yy, "text-anchor": "middle", class: "axis-label" });
    t.textContent = txt; svg.appendChild(t);
  };
  if (name.length <= maxLine) { put(name, y + 4); return; }
  // partir en el espacio más cercano al centro
  const mid = Math.floor(name.length / 2);
  let sp = -1, best = 1e9;
  for (let i = 0; i < name.length; i++) {
    if (name[i] === " ") { const d = Math.abs(i - mid); if (d < best) { best = d; sp = i; } }
  }
  let l1, l2;
  if (sp < 0) { l1 = name.slice(0, maxLine); l2 = name.slice(maxLine); }
  else { l1 = name.slice(0, sp); l2 = name.slice(sp + 1); }
  put(trunc(l1, 20), y); put(trunc(l2, 20), y + 13);
}

/* ---- Line chart ---- */
function lineChart(v) {
  const pts = v.puntos || [];
  const W = 820, H = 320, padL = 52, padR = 30, padT = 20, base = H - 44;
  const maxV = Math.max(1, ...pts.map((p) => p.y)), minV = Math.min(...pts.map((p) => p.y), 0);
  const xAt = (i) => padL + (W - padL - padR) * (pts.length === 1 ? 0.5 : i / (pts.length - 1));
  const yAt = (val) => padT + (base - padT) * (1 - (val - minV) / (maxV - minV || 1));
  const svg = svgEl("svg", { class: "chart", viewBox: `0 0 ${W} ${H}`, role: "img" });
  const grad = svgEl("linearGradient", { id: "gold-grad", x1: 0, y1: 0, x2: 0, y2: 1 });
  grad.appendChild(svgEl("stop", { offset: "0%", "stop-color": "#d8b45a" }));
  grad.appendChild(svgEl("stop", { offset: "100%", "stop-color": "#d8b45a", "stop-opacity": 0 }));
  svg.appendChild(grad);
  [0, 0.5, 1].forEach((g) => {
    const y = padT + (base - padT) * (1 - g);
    svg.appendChild(svgEl("line", { x1: padL, y1: y, x2: W - padR, y2: y, class: "grid-line" }));
    svg.appendChild(svgEl("text", { x: padL - 10, y: y + 4, "text-anchor": "end", class: "axis-label" })).textContent = fmt(Math.round(minV + (maxV - minV) * g));
  });
  let d = "", area = `M ${xAt(0)} ${base} `;
  pts.forEach((p, i) => { const X = xAt(i), Y = yAt(p.y); d += (i ? "L" : "M") + ` ${X} ${Y} `; area += `L ${X} ${Y} `; });
  area += `L ${xAt(pts.length - 1)} ${base} Z`;
  svg.appendChild(svgEl("path", { d: area, class: "line-area" }));
  svg.appendChild(svgEl("path", { d, class: "line-path" }));
  pts.forEach((p, i) => {
    const X = xAt(i), Y = yAt(p.y);
    svg.appendChild(svgEl("circle", { cx: X, cy: Y, r: 5, class: p.proyectado ? "dot-proj" : "dot" }));
    svg.appendChild(svgEl("text", { x: X, y: Y - 14, "text-anchor": "middle", class: "val-label" })).textContent = fmt(p.y);
    svg.appendChild(svgEl("text", { x: X, y: base + 22, "text-anchor": "middle", class: "axis-label" })).textContent = p.x + (p.proyectado ? " ⌁" : "");
  });
  return svg;
}

/* ---- Table ---- */
function tableView(v) {
  const t = document.createElement("table");
  t.className = "tbl";
  const thead = document.createElement("thead");
  thead.innerHTML = "<tr>" + (v.columnas || []).map((c) => `<th>${esc(c)}</th>`).join("") + "</tr>";
  const tb = document.createElement("tbody");
  (v.filas || []).forEach((row) => {
    tb.innerHTML += "<tr>" + row.map((c) => `<td>${esc(String(c))}</td>`).join("") + "</tr>";
  });
  t.appendChild(thead); t.appendChild(tb);
  return t;
}

/* ---- Ficha 360 ---- */
function clientDetail(v) {
  const wrap = document.createElement("div");
  wrap.className = "detail-grid";
  const cards = [
    ["Solicitante", v.solicitante, ["genero", "edad", "estado_civil", "departamento", "region", "tipo_producto", "monto_credito", "cohorte"]],
    ["Verifiquemos (corrida 1)", v.validacion, ["score_total", "banda_score", "nivel_riesgo", "recomendacion", "pep", "match_pep", "coincidencia_facial"]],
    ["Comportamiento real", v.comportamiento, ["en_mora", "tuvo_atrasos", "cantidad_atrasos", "cobro_legal", "tiene_seguro_vida_credito", "meses_hasta_mora"]],
    ["VERITAS", v.veritas, ["scoring_crediticio", "comportamiento_pago", "capacidad_pago", "dependencia_clientes"]],
    ["Proyección LSTM", v.proyeccion, ["probabilidad_mora", "nivel_riesgo", "factores_explicativos"]],
  ];
  cards.forEach(([titulo, obj, keys]) => {
    if (!obj || Object.keys(obj).length === 0) return;
    const c = document.createElement("div"); c.className = "detail-card";
    c.innerHTML = `<h4>${esc(titulo)}</h4>` + keys.map((k) => {
      let val = obj[k]; if (val === null || val === undefined) return "";
      if (typeof val === "boolean") val = val ? "Sí" : "No";
      if (Array.isArray(val)) val = val.join(", ");
      return `<div class="detail-row"><span class="dk">${esc(k)}</span><span class="dv">${esc(String(val))}</span></div>`;
    }).join("");
    wrap.appendChild(c);
  });
  return wrap;
}

/* -------- utilidades -------- */
function esc(s) { return String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c])); }
function fmt(n) { return typeof n === "number" ? (Number.isInteger(n) ? n.toLocaleString("es-GT") : n) : n; }
function trunc(s, n) { s = String(s); return s.length > n ? s.slice(0, n - 1) + "…" : s; }

/* ============================================================
   VOZ — Realtime API (WebRTC)
   ============================================================ */
function setStatus(kind, text) {
  const el = $("status"); el.className = "status status--" + kind;
  $("status-text").textContent = text;
}
function setOrb(state) {
  const orb = $("orb");
  orb.classList.toggle("is-live", state !== "off");
  orb.classList.toggle("is-speaking", state === "speaking");
  speaking = state === "speaking";
  $("orb-caption").textContent =
    state === "speaking" ? "Forecast Lab está hablando…" :
    state === "listening" ? (muted ? "Micrófono silenciado" : "Escuchando…") :
    state === "off" ? "Presione para iniciar la conversación" : "Conectando…";
}

/* ---------- Onda de voz reactiva (sincronizada con la voz del asistente) ---------- */
function setupAnalyser(stream) {
  try {
    audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    if (audioCtx.state === "suspended") audioCtx.resume();
    const src = audioCtx.createMediaStreamSource(stream);
    analyser = audioCtx.createAnalyser();
    analyser.fftSize = 512;
    analyser.smoothingTimeConstant = 0.8;
    src.connect(analyser);   // solo se "escucha" para graficar; el <audio> reproduce el sonido
    freqData = new Uint8Array(analyser.frequencyBinCount);
    drawWave();
  } catch (e) { console.warn("analyser:", e); }
}

function roundRect(ctx, x, y, w, h, r) {
  r = Math.min(r, w / 2, h / 2);
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y, x + w, y + h, r);
  ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r);
  ctx.arcTo(x, y, x + w, y, r);
  ctx.closePath(); ctx.fill();
}

function drawWave() {
  waveRAF = requestAnimationFrame(drawWave);
  const c = $("wave"); if (!c || !analyser) return;
  const ctx = c.getContext("2d");
  const W = c.width, H = c.height, mid = H / 2;
  ctx.clearRect(0, 0, W, H);
  analyser.getByteFrequencyData(freqData);

  const bars = 40;
  const usable = Math.floor(freqData.length * 0.62);
  const step = Math.max(1, Math.floor(usable / bars));
  const bw = W / bars;
  const grad = ctx.createLinearGradient(0, 0, W, 0);
  grad.addColorStop(0, "#0a9d4e"); grad.addColorStop(0.55, "#38d47e"); grad.addColorStop(1, "#f18a00");
  ctx.fillStyle = grad;

  let energy = 0;
  for (let i = 0; i < bars; i++) {
    let v = 0;
    for (let j = 0; j < step; j++) v += freqData[i * step + j];
    v /= step; energy += v;
    // realce en el centro (forma de onda), mínimo visible aunque haya silencio
    const centerBoost = 0.55 + 0.45 * Math.sin((i / (bars - 1)) * Math.PI);
    const h = Math.max(3, (v / 255) * (H * 0.92) * centerBoost);
    roundRect(ctx, i * bw + bw * 0.22, mid - h / 2, bw * 0.56, h, bw * 0.28);
  }
  energy /= bars;

  // el orb "respira" con la energía de la voz del asistente
  const core = document.querySelector(".orb-core");
  if (core) core.style.transform = `scale(${1 + Math.min(0.28, (energy / 255) * 0.9)})`;
}

function teardownAnalyser() {
  if (waveRAF) cancelAnimationFrame(waveRAF);
  waveRAF = null;
  try { audioCtx && audioCtx.close(); } catch {}
  audioCtx = analyser = freqData = null;
  const c = $("wave"); if (c) c.getContext("2d").clearRect(0, 0, c.width, c.height);
  const core = document.querySelector(".orb-core"); if (core) core.style.transform = "";
}

function addMsg(who, text) {
  const el = document.createElement("div");
  el.className = "msg " + who;
  el.innerHTML = `<div class="who">${who === "user" ? "Directivo" : "Forecast Lab"}</div><div class="txt"></div>`;
  el.querySelector(".txt").textContent = text;
  $("transcript").appendChild(el);
  $("transcript").scrollTop = $("transcript").scrollHeight;
  return el;
}

async function toggleMic() {
  if (live) { stopVoice(); return; }
  try {
    setStatus("think", "Conectando…"); setOrb("connecting");
    const sess = await fetch("/api/session").then((r) => r.json());
    if (sess.error) { setStatus("error", "Sin sesión"); alert("No se pudo crear la sesión:\n" + (sess.detalle || sess.error)); return; }
    // GA: el token efímero viene en sess.value; (compat: client_secret.value)
    const EPHEMERAL = sess.value || sess.client_secret?.value || sess.client_secret;
    const model = sess.model || (await fetch("/api/config").then((r) => r.json())).model;

    pc = new RTCPeerConnection();
    pc.ontrack = (e) => { remoteAudio.srcObject = e.streams[0]; setupAnalyser(e.streams[0]); };
    // Cancelación de eco / supresión de ruido: evita que la voz del asistente por
    // los parlantes vuelva a entrar al micrófono y dispare respuestas falsas.
    micStream = await navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
    });
    pc.addTrack(micStream.getTracks()[0], micStream);

    dc = pc.createDataChannel("oai-events");
    dc.onmessage = onRealtimeEvent;
    dc.onopen = () => {
      live = true; muted = false; setStatus("live", "En vivo"); setOrb("listening");
      $("voice-controls").hidden = false; updateMuteBtn();
      // Saludo inicial UNA sola vez: el asistente se presenta y pregunta en qué puede ayudar.
      if (!greeted) { greeted = true; dc.send(JSON.stringify({ type: "response.create" })); }
    };

    const offer = await pc.createOffer();
    await pc.setLocalDescription(offer);
    const r = await fetch(`https://api.openai.com/v1/realtime/calls?model=${encodeURIComponent(model)}`, {
      method: "POST", body: offer.sdp,
      headers: { Authorization: `Bearer ${EPHEMERAL}`, "Content-Type": "application/sdp" },
    });
    if (!r.ok) { throw new Error("WebRTC " + r.status + ": " + (await r.text()).slice(0, 200)); }
    await pc.setRemoteDescription({ type: "answer", sdp: await r.text() });
  } catch (e) {
    console.error(e); setStatus("error", "Error de voz"); alert("Error iniciando la voz: " + e.message);
    stopVoice();
  }
}

function stopVoice() {
  live = false; muted = false; greeted = false; speaking = false;
  teardownAnalyser();
  try { dc && dc.close(); } catch {}
  try { pc && pc.close(); } catch {}
  try { micStream && micStream.getTracks().forEach((t) => t.stop()); } catch {}
  pc = dc = micStream = null;
  setStatus("idle", "Desconectado"); setOrb("off");
  $("voice-controls").hidden = true;
}

/* Silenciar / reactivar el micrófono (deshabilita la pista de audio de entrada) */
function toggleMute() {
  if (!micStream) return;
  muted = !muted;
  micStream.getAudioTracks().forEach((t) => { t.enabled = !muted; });
  updateMuteBtn();
}
function updateMuteBtn() {
  const b = $("mute-btn");
  b.classList.toggle("is-muted", muted);
  $("mute-ico").textContent = muted ? "🔇" : "🎙";
  $("mute-label").textContent = muted ? "Silenciado" : "Silenciar";
  setStatus(muted ? "think" : "live", muted ? "Micrófono silenciado" : "En vivo");
  $("orb-caption").textContent = muted ? "Micrófono silenciado" : (live ? "Escuchando…" : "");
}

async function onRealtimeEvent(ev) {
  let msg; try { msg = JSON.parse(ev.data); } catch { return; }
  switch (msg.type) {
    case "input_audio_buffer.speech_started": setOrb("listening"); break;
    // Transcripción de la voz del asistente (GA: output_audio_transcript; beta: audio_transcript)
    case "response.output_audio_transcript.delta":
    case "response.audio_transcript.delta":
      setOrb("speaking");
      asstBuffer += msg.delta || "";
      if (!asstMsgEl) asstMsgEl = addMsg("assistant", "");
      asstMsgEl.querySelector(".txt").textContent = asstBuffer;
      $("transcript").scrollTop = $("transcript").scrollHeight;
      break;
    case "response.output_audio_transcript.done":
    case "response.audio_transcript.done":
    case "response.done":
      asstBuffer = ""; asstMsgEl = null; if (live) setOrb("listening");
      break;
    case "conversation.item.input_audio_transcription.completed":
      if (msg.transcript) addMsg("user", msg.transcript.trim());
      break;
    // Llamada a tool (GA e intermedio): item type function_call
    case "response.output_item.done":
      if (msg.item && msg.item.type === "function_call") await handleFunctionCall(msg.item);
      break;
    case "response.function_call_arguments.done":
      // Algunos modelos solo emiten este evento; item lleva name/call_id/arguments
      if (msg.name && msg.call_id) await handleFunctionCall(msg);
      break;
  }
}

const _handledCalls = new Set();
/* Enviar una pregunta de texto (del usuario) al modelo para que la conteste por voz */
function sendUserText(texto) {
  addMsg("user", texto);
  dc.send(JSON.stringify({
    type: "conversation.item.create",
    item: { type: "message", role: "user", content: [{ type: "input_text", text: texto }] },
  }));
  dc.send(JSON.stringify({ type: "response.create" }));
}

async function handleFunctionCall(item) {
  const { name, call_id } = item;
  if (!call_id || _handledCalls.has(call_id)) return;   // dedupe
  _handledCalls.add(call_id);
  let args = {}; try { args = item.arguments ? JSON.parse(item.arguments) : {}; } catch {}
  const res = await callTool(name, args);   // ejecuta + pinta la pantalla
  // devolver al modelo un payload compacto para que lo narre
  const compact = { resumen: res.resumen, titulo: res.titulo, kpis: res.kpis, datos: res.datos };
  dc.send(JSON.stringify({
    type: "conversation.item.create",
    item: { type: "function_call_output", call_id, output: JSON.stringify(compact) },
  }));
  dc.send(JSON.stringify({ type: "response.create" }));
}

/* -------- init -------- */
initGuide();
// El orb (izquierda) es el control principal: al presionarlo inicia la conversación.
$("orb").onclick = () => { if (!live) toggleMic(); };
$("orb").onkeydown = (e) => { if ((e.key === "Enter" || e.key === " ") && !live) { e.preventDefault(); toggleMic(); } };
$("end-btn").onclick = () => { if (live) toggleMic(); };
$("mute-btn").onclick = toggleMute;
$("guide-btn").onclick = showGuide;
$("back-btn").onclick = showGuide;
setOrb("off");
