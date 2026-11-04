// Last Mile 綠行臺北：前端。所有計算都在後端（/api/...），這裡只負責輸入、顯示與地圖。
const $ = id => document.getElementById(id);
const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const NAME = { walk: "走路", bike: "YouBike", bus: "公車" };
const WALK = 80;   // 公尺／分鐘，和後端 config 一致

const state = { mode: "trip", pts: [null, null], active: 0, choices: {}, trip: null, msg: "", busy: false, whatif: null };

// ---------- 地圖 ----------
const map = L.map("map", { zoomControl: true }).setView([25.045, 121.54], 13);
L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 19, attribution: "© OpenStreetMap contributors" }).addTo(map);
const stationLayer = L.layerGroup().addTo(map);
const layer = L.layerGroup().addTo(map);

// 慢行路網與事故圖層：勾選時才向後端要資料（約 1.7 MB，只抓一次）
const canvas = L.canvas({ padding: 0.3 });
const slowLayer = L.layerGroup(), crashLayer = L.layerGroup();
let layersLoaded = null;
function loadLayers() {
  layersLoaded ??= api("/api/layers").then(d => {
    for (const line of d.walk) L.polyline(line, { renderer: canvas, color: css("--walk"), weight: 1.5, opacity: 0.55, interactive: false }).addTo(slowLayer);
    for (const line of d.cycle) L.polyline(line, { renderer: canvas, color: css("--bike"), weight: 3, opacity: 0.9, interactive: false }).addTo(slowLayer);
    for (const [lat, lon, f] of d.crash) L.circleMarker([lat, lon], { renderer: canvas, radius: f & 4 ? 5 : 3, stroke: false, fillColor: css("--short"), fillOpacity: f & 4 ? 0.95 : 0.55 })
      .bindTooltip(`${d.year} 年${f & 4 ? " A1（死亡）" : ""}：${[f & 1 ? "行人" : "", f & 2 ? "自行車" : ""].filter(Boolean).join("、")}事故`).addTo(crashLayer);
  }).catch(e => { layersLoaded = null; state.msg = `圖層讀取失敗：${e.message}`; renderPanel(); });
  return layersLoaded;
}
L.control.layers(null, { "人行道（藍）與自行車道（綠）": slowLayer, "行人、自行車事故（紅）": crashLayer }, { collapsed: false, position: "topright" }).addTo(map);
map.on("overlayadd", loadLayers);

async function api(path, options) {
  const r = await fetch(path, options);
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(j.detail || `伺服器錯誤（${r.status}）`);
  return j;
}

// ---------- 地址查詢：瀏覽器直接呼叫 Nominatim ----------
// Render 等雲端主機的 IP 常被 Nominatim 擋，所以不經過後端；地址也因此不會送到本網站的伺服器。
// 規則同 backend/geocode.py：門牌先拆成「區、路、號」做結構化查詢，找不到退到只查路名，不像地址就當地標查。
// Nominatim 規定每秒最多 1 次、要快取、不可做自動完成（所以只在按 Enter 時查）。
const ADDRESS = /(\S+?區)?(\S+?(?:路|街|大道)(?:\S+?段)?(?:\d+巷)?(?:\d+弄)?)(\d+)號/;
const geoCache = new Map();
let bbox = null, lastGeo = 0;
async function nominatim(params) {
  const wait = 1000 - (Date.now() - lastGeo);
  if (wait > 0) await new Promise(r => setTimeout(r, wait));
  lastGeo = Date.now();
  const u = new URL("https://nominatim.openstreetmap.org/search");
  const box = bbox ? { viewbox: `${bbox[1]},${bbox[2]},${bbox[3]},${bbox[0]}`, bounded: 1 } : {};   // 只找研究範圍內
  for (const [k, v] of Object.entries({ format: "jsonv2", limit: 1, countrycodes: "tw", "accept-language": "zh-TW", ...box, ...params })) u.searchParams.set(k, v);
  const r = await fetch(u);
  if (!r.ok) throw new Error(`地址查詢服務暫時無法使用（${r.status}），請改在地圖上選點`);
  return r.json();
}
async function geocode(q) {
  if (geoCache.has(q)) return geoCache.get(q);
  const m = q.replace(/\s/g, "").match(ADDRESS);
  let hit = null, level = "place";
  if (m) {
    const [, , road, no] = m;
    [hit] = await nominatim({ street: `${no} ${road}`, city: "臺北市" }); level = "address";
    if (!hit) { [hit] = await nominatim({ street: road, city: "臺北市" }); level = "road"; }
    if (!hit && /巷|弄/.test(road)) [hit] = await nominatim({ street: road.replace(/\d+巷.*$/, ""), city: "臺北市" });   // 巷弄找不到就查主要道路
  }
  if (!hit) { [hit] = await nominatim({ q }); level = "place"; }
  if (!hit) throw new Error("研究範圍內找不到這個地址或地標，請換個寫法，或在地圖上選點");
  const out = { lat: +hit.lat, lon: +hit.lon, level };
  geoCache.set(q, out);
  return out;
}

async function loadStations() {
  const d = await api("/api/stations");
  const stations = d.stations;
  bbox = d.bbox;
  map.fitBounds([[bbox[0], bbox[1]], [bbox[2], bbox[3]]]);
  for (const s of stations) {
    L.circleMarker([s.lat, s.lon], { radius: 5, color: "#fff", weight: 2, fillColor: css("--ink"), fillOpacity: 1 })
      .bindTooltip(`${s.name}（${s.sys.join("、")}）`, { direction: "top" }).addTo(stationLayer);
  }
}

// ---------- 下雨效果：雨絲集中在四周，中間清楚 ----------
const mapbox = document.querySelector(".mapbox");
const blur = Object.assign(document.createElement("div"), { className: "rain-blur" });
const cv = Object.assign(document.createElement("canvas"), { className: "rain-canvas" });
mapbox.append(blur, cv);
let raf = null;
function setRain(on) {
  document.body.classList.toggle("raining", on);
  mapbox.classList.toggle("raining", on);
  cancelAnimationFrame(raf);
  const r = cv.getBoundingClientRect(), k = devicePixelRatio;
  cv.width = r.width * k; cv.height = r.height * k;
  const ctx = cv.getContext("2d"), W = cv.width, H = cv.height;
  ctx.clearRect(0, 0, W, H);
  if (!on) return;
  const drops = Array.from({ length: 220 }, () => ({ x: Math.random() * W, y: Math.random() * H, l: (10 + Math.random() * 14) * k, v: (9 + Math.random() * 7) * k }));
  const paint = () => {
    ctx.clearRect(0, 0, W, H);
    ctx.strokeStyle = css("--drop"); ctx.lineWidth = 1.2 * k; ctx.beginPath();
    for (const d of drops) { ctx.moveTo(d.x, d.y); ctx.lineTo(d.x - d.l * 0.25, d.y + d.l); }
    ctx.stroke();
    const g = ctx.createRadialGradient(W / 2, H / 2, Math.min(W, H) * 0.18, W / 2, H / 2, Math.max(W, H) * 0.62);
    g.addColorStop(0, "rgba(0,0,0,0.08)"); g.addColorStop(1, "rgba(0,0,0,1)");
    ctx.globalCompositeOperation = "destination-in"; ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);
    ctx.globalCompositeOperation = "source-over";
  };
  if (matchMedia("(prefers-reduced-motion: reduce)").matches) return paint();
  const step = () => {
    for (const d of drops) { d.y += d.v; d.x -= d.v * 0.25; if (d.y > H) { d.y = -d.l; d.x = Math.random() * (W + H * 0.25); } }
    paint(); raf = requestAnimationFrame(step);
  };
  step();
}

// ---------- 行程：輸入 ----------
const role = k => k === 0 ? "o" : k === state.pts.length - 1 ? "d" : "w";
const pin = k => k === 0 ? "起" : k === state.pts.length - 1 ? "終" : String(k);
function pointsCard() {
  return `<section class="card"><h2>行程</h2>
    <ol class="pts">${state.pts.map((p, k) => `<li class="${k === state.active ? "active" : ""}">
      <span class="pin ${role(k)}">${pin(k)}</span>
      <input data-pt="${k}" value="${p ? p.label : ""}" placeholder="${k === 0 ? "出發地" : role(k) === "d" ? "目的地" : "中繼站"}：輸入地址或地標後按 Enter" aria-label="${k === 0 ? "出發地" : role(k) === "d" ? "目的地" : `中繼站 ${k}`}">
      <button type="button" class="mini" data-pick="${k}" aria-pressed="${k === state.active}">選點</button>
      ${role(k) === "w" ? `<button type="button" class="mini" data-del="${k}">刪除</button>` : ""}</li>`).join("")}</ol>
    <div class="rowbtns"><button type="button" class="btn ghost" id="addwp" ${state.pts.length >= 5 ? "disabled" : ""}>＋ 中繼站</button><button type="button" class="btn ghost" id="swap">起訖對調</button></div>
    ${state.msg ? `<p class="msg">${state.msg}</p>` : ""}${state.busy ? `<p class="small muted">計算中…</p>` : ""}</section>`;
}

// ---------- 行程：結果 ----------
const step = (cls, no, what, sub, t) => `<li><span class="no ${cls}">${no}</span><div><div class="what">${what}</div>${sub ? `<div class="sub">${sub}</div>` : ""}</div><span class="t num">${t || ""}</span></li>`;
// e：可借車中的電輔車數（只有借車端有）
const count = (v, f, unit, e) => v == null ? `<span class="muted">沒有即時資料</span>` :
  `<span class="cnt ${v ? "" : "zero"}">${unit === "台" ? "可借" : "可還"} ${v} ${unit}</span>${e != null ? `其中電輔 ${e} 台 · ` : ""}${f != null ? `15 分鐘後約 ${f} ${unit}` : ""}`;
// 這段路有幾成在人行道／自行車道上、沿線 30 公尺內一年有幾件相關事故
const slowText = s => !s ? "" : ` · ${s.label} ${Math.round(s.share * 100)}% · <span class="${s.crashes ? "warn" : ""}">沿線 ${s.year} 年${s.label === "人行道" ? "行人" : "自行車"}事故 ${s.crashes} 件</span>`;
function mileSteps(m, roleName, stationName, placeName) {
  const to = roleName === "first" ? `<b>${stationName}</b>站` : placeName;
  if (m.mode === "walk") return [["walk", `走路到${to}`, `${Math.round(m.dist)} m${slowText(m.slow)}`, `${Math.round(m.mins)} 分`]];
  if (m.mode === "bike") {
    const rel = m.reliability ? ` · 過去 14 天同時段兩站都接得上 ${Math.round(m.reliability.share * 100)}%` : "";
    return [
      ["walk", `走到 <b>${m.borrow.name}</b> 借車`, count(m.borrow.rent, m.borrow.rent_15, "台", m.borrow.rent_e), `${Math.round(m.walk_before / WALK)} 分`],
      ["bike", `騎到 <b>${m.give.name}</b> 還車`, `${count(m.give.ret, m.give.ret_15, "格")} · ${(m.ride / 1000).toFixed(1)} km${slowText(m.slow)}${rel}`, `${Math.round(m.ride / 250 + 2)} 分`],
      ["walk", `走路到${to}`, `${Math.round(m.walk_after)} m`, `${Math.round(m.walk_after / WALK)} 分`],
    ];
  }
  const eta = m.board.uid ? `<button class="btn ghost" type="button" data-eta="${m.board.uid}">查到站時間</button>` : `<span class="muted">站牌尚未對應 TDX StopUID</span>`;
  return [
    ["walk", `走到公車站 <b>${m.board.name}</b>`, "", ""],
    ["bus", `搭公車到 <b>${m.alight.name}</b>`, eta, `${Math.round(m.ride)} 分`],
    ["walk", `走路到${to}`, "", ""],
  ];
}
function chooser(m, key, label) {
  return `<div class="chooser"><span class="small muted">${label}</span>${Object.entries(m.options).map(([k, v]) =>
    `<button type="button" data-choice="${key}:${k}" aria-pressed="${k === m.mode}">${NAME[k]} ${k === "bus" ? "≥" : ""}${Math.round(v)} 分</button>`).join("")}</div>`;
}
function legCard(l, n) {
  const name = p => (p.label || "選點").slice(0, 12);
  let h = `<section class="card"><div class="leghead"><h3>${n > 1 ? `第 ${l.k + 1} 段　` : ""}${name(l.from)} → ${name(l.to)}</h3>
    <span class="small muted num">大眾運輸 ${Math.round(l.total || 0)} 分 · 機車 ${l.moto ? Math.round(l.moto.mins) : "—"} 分</span></div>`;
  if (l.error) return h + `<p>${l.error}</p></section>`;
  if (l.direct) return h + `<ol class="steps">${step("walk", 1, `兩地很近，直接走路到${name(l.to)}`, `約 ${Math.round(l.dist)} m`, `${Math.round(l.total)} 分`)}</ol></section>`;
  let no = 0;
  const list = rows => rows.map(r => step(r[0], ++no, r[1], r[2], r[3])).join("");
  return h + `<ol class="steps">${list(mileSteps(l.first, "first", l.rail.from, name(l.from)))}</ol>${chooser(l.first, `${l.k}a`, "到車站：")}
    <ol class="steps">${list([["rail", `搭${l.rail.sys}：<b>${l.rail.from}</b> → <b>${l.rail.to}</b>`, `等 ${l.rail.wait} 分 · 車上約 ${Math.round(l.rail.ride)} 分${l.rail.transfer ? ` · 轉乘 ${l.rail.transfer} 分` : ""}`, `${Math.round(l.rail.mins)} 分`]])}
    ${list(mileSteps(l.last, "last", l.rail.to, name(l.to)))}</ol>${chooser(l.last, `${l.k}b`, "出站後：")}</section>`;
}
function summaryCard(t) {
  const max = Math.max(t.total, t.moto) || 1, diff = t.total - t.moto;
  return `<section class="card">${t.meta.rain ? `<p class="rainbox">正在下雨，首末段預設改搭公車。</p>` : ""}
    <div class="cb"><span>大眾運輸</span><div class="track"><i style="width:${t.mile / max * 100}%;background:var(--walk)"></i><i style="width:${t.ride / max * 100}%;background:var(--ink)"></i></div><b class="num">${Math.round(t.total)} 分</b></div>
    <div class="cb"><span>騎機車</span><div class="track"><i style="width:${t.moto / max * 100}%;background:var(--moto)"></i></div><b class="num">${Math.round(t.moto)} 分</b></div>
    <p class="small"><i class="sw" style="background:var(--walk)"></i>首末段　<i class="sw" style="background:var(--ink)"></i>等車與搭車</p>
    <p>大眾運輸比機車${diff > 0 ? "慢" : "快"} <b class="num">${Math.abs(Math.round(diff))}</b> 分鐘，其中首末段共 <b class="num">${Math.round(t.mile)}</b> 分，佔 <b class="num">${Math.round(t.mile / t.total * 100)}%</b>。</p>
    ${carbonText(t.carbon)}</section>`;
}
// 碳排：捷運係數含生命週期、機車只算排氣管，對機車有利，所以「少排」是保守估計
function carbonText(c) {
  if (!c) return "";
  const saved = c.saved_g > 0 ? `，改搭大眾運輸約少排 <b class="num">${c.saved_g}</b> g` : "";
  return `<p class="small">碳排估算：大眾運輸 <b class="num">${c.transit_g}</b> g、騎機車 <b class="num">${c.moto_g}</b> g CO₂e${saved}
    <span class="muted">（保守估計：捷運含生命週期，機車只算排氣管${c.draft.length ? `；${c.draft.join("、")}為暫定係數` : ""}）</span></p>`;
}

// ---------- 增設 YouBike 站 ----------
function whatIfPanel() {
  const a = state.whatif;
  let h = `<section class="card"><h2>在地圖上點一個位置</h2><p class="small muted">假設在那裡新增一個 YouBike 站，計算周邊 500 公尺內有多少路口往返軌道車站的時間變短。</p></section>`;
  if (!a) return h;
  if (a.error) return h + `<section class="card"><p>${a.error}</p></section>`;
  return h + `<section class="card"><div class="kpis">
    <div class="kpi"><span class="v num">${a.improved}</span><span class="k">時間變短的路口</span></div>
    <div class="kpi"><span class="v num">${a.under_threshold}</span><span class="k">因此變成 20 分鐘內可到車站</span></div>
    <div class="kpi"><span class="v num">${a.saved_avg.toFixed(1)}</span><span class="k">平均省下（分鐘）</span></div>
    <div class="kpi"><span class="v">${a.station}</span><span class="k">從這個車站騎過來</span></div></div></section>`;
}

// ---------- 畫面 ----------
function renderPanel() {
  let h = "";
  if (state.mode === "add") h = whatIfPanel();
  else {
    h = pointsCard();
    const t = state.trip;
    if (t) h += (t.legs.every(l => !l.error) ? summaryCard(t) : "") + t.legs.map(l => legCard(l, t.legs.length)).join("");
  }
  $("panel").innerHTML = h;
  bind();
}
function drawMap() {
  layer.clearLayers();
  const dot = { color: css("--walk"), weight: 3, dashArray: "2 6" };
  const badge = (b, kind, v) => L.marker([b.lat, b.lon], { icon: L.divIcon({ className: "yb-icon", iconSize: [0, 0], html: `<span class="${v ? "" : "zero"}">${kind} ${v ?? "?"}</span>` }) }).addTo(layer);
  const drawMile = m => {
    if (m.mode === "walk") L.polyline(m.pts, { color: css("--walk"), weight: 5, dashArray: "7 6" }).addTo(layer);
    if (m.mode === "bike") { L.polyline(m.pts, { color: css("--bike"), weight: 6 }).addTo(layer); badge(m.borrow, "借", m.borrow.rent); badge(m.give, "還", m.give.ret); }
    if (m.mode === "bus") L.polyline([[m.board.lat, m.board.lon], [m.alight.lat, m.alight.lon]], { color: css("--bus"), weight: 5, dashArray: "10 6" }).addTo(layer);
  };
  if (state.mode === "trip" && state.trip) for (const l of state.trip.legs) {
    if (l.moto) L.polyline(l.moto.path, { color: css("--moto"), weight: 3, opacity: 0.85 }).addTo(layer);
    if (l.error) continue;
    if (l.direct) { L.polyline([[l.from.lat, l.from.lon], [l.to.lat, l.to.lon]], dot).addTo(layer); continue; }
    drawMile(l.first); drawMile(l.last);
  }
  state.pts.forEach((p, k) => p && L.marker([p.lat, p.lon], { icon: L.divIcon({ className: "pt-icon", iconSize: [0, 0], html: `<span class="pin ${role(k)}">${pin(k)}</span>` }) }).bindTooltip(p.label).addTo(layer));
}
function render() {
  for (const b of document.querySelectorAll(".tabs button")) b.setAttribute("aria-selected", String(b.dataset.mode === state.mode));
  renderPanel(); drawMap();
  const m = state.trip && state.trip.meta;
  $("status").textContent = m ? `${m.rain ? "下雨中" : "沒有下雨"} · 即時資料 ${m.live_time ? m.live_time.slice(11, 16) : "沒有"}（${m.live_source}）` : "";
  $("status").className = "status small" + (m && m.rain ? " rain" : "");
  setRain(!!(m && m.rain));
}

async function compute() {
  if (state.pts.some(p => !p)) { state.trip = null; return render(); }
  state.busy = true; renderPanel();
  try {
    state.trip = await api("/api/trip", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ points: state.pts, choices: state.choices }) });
    state.msg = "";
  } catch (e) { state.msg = e.message; }
  state.busy = false; render();
  const pts = state.pts.map(p => [p.lat, p.lon]);
  if (state.trip) for (const l of state.trip.legs) if (l.moto) pts.push(...l.moto.path);
  map.fitBounds(L.latLngBounds(pts).pad(0.2), { maxZoom: 16 });
}
function setPoint(k, lat, lon, label) {
  state.pts[k] = { lat, lon, label: label || `地圖選點 ${lat.toFixed(4)}, ${lon.toFixed(4)}` };
  const next = state.pts.findIndex(p => !p);
  state.active = next >= 0 ? next : k;
  state.choices = {};
  compute();
}
function bind() {
  for (const inp of document.querySelectorAll("[data-pt]")) inp.addEventListener("keydown", async e => {
    if (e.key !== "Enter") return;
    const k = +inp.dataset.pt, q = inp.value.trim();
    if (q.length < 2) return;
    state.msg = "查詢中…"; renderPanel();
    try { const g = await geocode(q); state.msg = g.level === "road" ? "只定位到路，請在地圖上確認位置。" : ""; setPoint(k, g.lat, g.lon, q); }
    catch (err) { state.msg = err.message; renderPanel(); }
  });
  for (const b of document.querySelectorAll("[data-pick]")) b.addEventListener("click", () => { state.active = +b.dataset.pick; state.msg = "請在地圖上點位置"; renderPanel(); });
  for (const b of document.querySelectorAll("[data-del]")) b.addEventListener("click", () => { state.pts.splice(+b.dataset.del, 1); state.active = state.pts.length - 1; state.choices = {}; compute(); });
  const add = $("addwp"); if (add) add.addEventListener("click", () => { state.pts.splice(state.pts.length - 1, 0, null); state.active = state.pts.length - 2; state.trip = null; render(); });
  const swap = $("swap"); if (swap) swap.addEventListener("click", () => { state.pts.reverse(); state.choices = {}; compute(); });
  for (const b of document.querySelectorAll("[data-choice]")) b.addEventListener("click", () => { const [k, m] = b.dataset.choice.split(":"); state.choices[k] = m; compute(); });
  for (const b of document.querySelectorAll("[data-eta]")) b.addEventListener("click", async () => {
    b.textContent = "查詢中…";
    try { const r = await api(`/api/bus/eta?stop_uid=${encodeURIComponent(b.dataset.eta)}`); b.outerHTML = r.arrivals.map(a => `${a.route} ${a.minutes} 分`).join("　") || "目前沒有班次"; }
    catch (e) { b.outerHTML = `<span class="muted">${e.message}</span>`; }
  });
}

for (const b of document.querySelectorAll(".tabs button")) b.addEventListener("click", () => { state.mode = b.dataset.mode; render(); });
map.on("click", async e => {
  const { lat, lng } = e.latlng;
  if (state.mode === "trip") return setPoint(state.active, lat, lng, "");
  try { state.whatif = await api("/api/what-if", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ lat, lon: lng }) }); }
  catch (err) { state.whatif = { error: err.message }; }
  render();
  L.circle([lat, lng], { radius: 500, color: css("--accent"), weight: 1.5, dashArray: "5 4", fill: false }).addTo(layer);
});
window.addEventListener("resize", () => setRain(!!(state.trip && state.trip.meta.rain)));

loadStations().catch(e => { state.msg = `無法連到後端：${e.message}`; });
render();
