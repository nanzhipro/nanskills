/* ============================================================
 * Architecture Atlas · 通用渲染引擎
 * 无依赖原生 JS:SVG 图渲染 / 下钻 / 详情抽屉 / 时序数据流 / 搜索
 * 读取 data.js 定义的全局 ATLAS 对象,不含任何产品特定数据
 * ============================================================ */
"use strict";

const $ = (sel) => document.querySelector(sel);
const SVGNS = "http://www.w3.org/2000/svg";
const ENT = ATLAS.entities;
const RELS = ATLAS.relations;
const VIEWS = ATLAS.views;
const KINDS = ATLAS.kinds;
const RELK = ATLAS.relKinds;

/* 非 daemon 但 root 运行的实体加 `root: true`,自动获得 ROOT 徽章 */
const ROOT_BADGE = {};
for (const [id, e] of Object.entries(ENT)) if (e.root) ROOT_BADGE[id] = 1;
/* crumb → 视图:各视图 crumb 末段即其自身,由此构建回跳表 */
const CRUMB_VIEW = { "数据流": "flows", "设计原则": "principles" };
for (const [vid, v] of Object.entries(VIEWS)) {
  const c = v.crumb || [];
  if (c.length) CRUMB_VIEW[c[c.length - 1]] = vid;
}

const NODE_W = 208, NODE_H = 70, BIG_W = 250, BIG_H = 86;

/* ---------- 全局状态 ---------- */
const state = {
  view: "overview",          // 当前视图 id | "flows" | "principles"
  flow: (ATLAS.flows[0] || {}).id,   // 当前数据流(空数据时为 undefined)
  sel: null,                 // 选中实体 id
  selEdge: null,             // 选中关系 "s,t,idx"
  t: { x: 0, y: 0, k: 1 },   // 画布 transform
};

/* ============================================================
 * 工具
 * ============================================================ */
function el(tag, attrs = {}, parent) {
  const n = document.createElementNS(SVGNS, tag);
  for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
  if (parent) parent.appendChild(n);
  return n;
}
function trunc(s, n) { return s && s.length > n ? s.slice(0, n - 1) + "…" : s; }
function esc(s) { return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;"); }
function nodeSize(id) {
  const e = ENT[id];
  return e && e.big ? [BIG_W, BIG_H] : [NODE_W, NODE_H];
}
/* ============================================================
 * 形态映射(两层模型的协议侧):语义 kind → 视觉形态 form。
 * kinds 条目可用 form 字段显式指定形态;未指定时按内置默认词表回退;再兜底 plain。
 * 词表(有哪些 kind、叫什么)是项目数据,由勘探动态推理;形态(长什么样)才与引擎绑定。
 * ============================================================ */
const KIND_FORM = {
  daemon: "black", kernel: "black", service: "bold", worker: "dashedgray", xpc: "dashedgray",
  sysex: "gray", appex: "gray", external: "ext", store: "store", artifact: "artifact",
  cli: "mono", tool: "mono", cicd: "cicd", lib: "dashed", engine: "dashed",
};
function formOf(kind) {
  const k = KINDS[kind];
  return (k && k.form) || KIND_FORM[kind] || "plain";
}
function kindCls(kind) {
  const f = formOf(kind);
  return f === "plain" ? "node" : `node k-f-${f}`;
}
function relsOf(id) {
  const out = [], inn = [];
  RELS.forEach((r, i) => {
    if (r.s === id) out.push({ ...r, i });
    if (r.t === id) inn.push({ ...r, i });
  });
  return { out, inn };
}
function viewNameOf(id) {
  const e = ENT[id];
  if (!e) return "";
  const v = VIEWS[e.home];
  return v ? v.name : "";
}

/* ============================================================
 * 导航
 * ============================================================ */
function buildNav() {
  const nav = $("#nav");
  /* 导航由 ATLAS.views 动态生成:definition 顺序即导航顺序,layer 字段即层级标签 */
  const icoBox = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="3.5" y="3.5" width="7" height="7" rx="2"/><rect x="13.5" y="3.5" width="7" height="7" rx="2"/><rect x="3.5" y="13.5" width="7" height="7" rx="2"/><rect x="13.5" y="13.5" width="7" height="7" rx="2"/></svg>';
  const icoFlow = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><path d="M4 6h9M4 12h16M4 18h13"/><circle cx="17" cy="6" r="2.2"/></svg>';
  const icoPrin = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3 4 7v5c0 5 3.4 8 8 9 4.6-1 8-4 8-9V7l-8-4z"/></svg>';
  const maxLayer = Object.values(VIEWS).reduce((m, v) => {
    const n = parseInt(String(v.layer || "").replace(/\D/g, ""), 10);
    return isNaN(n) ? m : Math.max(m, n);
  }, 0);
  let html = `<div class="nav-group"><div class="nav-group-title">架构层级 <span class="layer-tag">${maxLayer ? `L1–L${maxLayer}` : "待填充"}</span></div>`;
  for (const [id, v] of Object.entries(VIEWS)) {
    html += `<div class="nav-item" data-nav="${id}"><span class="nav-ico">${icoBox}</span><span>${v.name}</span><span class="nav-meta">${v.layer || ""}</span></div>`;
  }
  html += `</div><div class="nav-group"><div class="nav-group-title">运行时 <span class="layer-tag">L4</span></div>`;
  html += `<div class="nav-item" data-nav="flows"><span class="nav-ico">${icoFlow}</span><span>数据流</span><span class="nav-meta">${ATLAS.flows.length}</span></div>`;
  html += `</div><div class="nav-group"><div class="nav-group-title">宏观</div>`;
  html += `<div class="nav-item" data-nav="principles"><span class="nav-ico">${icoPrin}</span><span>设计原则</span><span class="nav-meta">${ATLAS.principles.length}</span></div>`;
  html += `</div>`;
  nav.innerHTML = html;
  nav.addEventListener("click", (e) => {
    const item = e.target.closest("[data-nav]");
    if (item) navigate(item.dataset.nav);
  });
  $("#foot-stats").textContent =
    `${Object.keys(ENT).length} 实体 · ${RELS.length} 关系 · ${ATLAS.flows.length} 数据流 · ${ATLAS.meta.repos.length} 仓库`;
}

/* ============================================================
 * 路由
 * ============================================================ */
function navigate(view, opts = {}) {
  state.view = view;
  if (opts.flow) state.flow = opts.flow;
  if (opts.sel !== undefined) state.sel = opts.sel; else state.sel = null;
  state.selEdge = null;
  render();
  writeHash();
}
function writeHash() {
  let h = "#/" + state.view;
  if (state.view === "flows") h += "/" + state.flow;
  if (state.sel) h += "?sel=" + state.sel;
  history.replaceState(null, "", h);
}
function readHash() {
  const m = location.hash.match(/^#\/([\w-]+)(?:\/([\w-]+))?(?:\?sel=([\w-]+))?/);
  if (!m) return;
  const [, v, f, sel] = m;
  if (v === "flows" || v === "principles" || VIEWS[v]) {
    state.view = v;
    if (f && ATLAS.flows.some((x) => x.id === f)) state.flow = f;
    if (sel && ENT[sel]) state.sel = sel;
  }
}

/* ============================================================
 * 主渲染分发
 * ============================================================ */
function render() {
  const isFlow = state.view === "flows";
  const isPrin = state.view === "principles";
  $("#stage").style.display = !isFlow && !isPrin ? "" : "none";
  $("#flowwrap").classList.toggle("on", isFlow);
  $("#principles").classList.toggle("on", isPrin);

  document.querySelectorAll("[data-nav]").forEach((n) =>
    n.classList.toggle("active", n.dataset.nav === state.view));

  if (isFlow) renderFlow();
  else if (isPrin) renderPrinciples();
  else renderDiagram();

  if (state.sel && ENT[state.sel]) openDrawer(state.sel);
  else closeDrawer();
}

/* ============================================================
 * 架构图渲染
 * ============================================================ */
function renderDiagram() {
  const view = VIEWS[state.view];
  const svg = $("#canvas");
  /* 空数据防御:契约合法但尚未填充 views 时给出指引而不是崩溃 */
  if (!view) {
    svg.innerHTML = "";
    $("#view-title").textContent = ATLAS.meta.title || "Architecture Atlas";
    $("#view-desc").textContent = "data.js 是空骨架:请按契约填充 entities / relations / views(见 references/ontology-modeling.md §3–4)。";
    $("#crumbs").innerHTML = "";
    renderLegend();
    return;
  }
  svg.innerHTML = "";
  /* 不设 viewBox:canvas 单位即 CSS px,缩放/平移全由 fitView 的 viewport transform 负责。
     若设 viewBox,#stage svg{width/height:100%} 会先做 preserveAspectRatio=meet 缩放,
     与 fitView 的 scale 叠加:小窗口双倍缩小、大窗口(k 顶到 1.15 上限时)双倍放大裁掉右/下边缘。 */

  /* defs:箭头 */
  const defs = el("defs", {}, svg);
  const mk = (id) => {
    const m = el("marker", { id, viewBox: "0 0 10 10", refX: 9, refY: 5, markerWidth: 7.5, markerHeight: 7.5, orient: "auto-start-reverse" }, defs);
    el("path", { d: "M 0 1.5 L 9 5 L 0 8.5 z" }, m); /* fill 由 CSS marker#<id> path 令牌化 */
  };
  mk("arrow"); mk("arrow-mid"); mk("arrow-dark");

  const vp = el("g", { id: "viewport" }, svg);

  /* 组框 */
  for (const g of view.groups || []) {
    el("rect", { x: g.x, y: g.y, width: g.w, height: g.h, rx: 14, class: "group-box" }, vp);
    const t1 = el("text", { x: g.x + 16, y: g.y + 24, class: "group-label" }, vp);
    t1.textContent = g.label;
    if (g.sub) {
      const t2 = el("text", { x: g.x + 16, y: g.y + 40, class: "group-sub" }, vp);
      t2.textContent = g.sub;
    }
  }

  /* 边 */
  const edges = edgesInView(view);
  const edgeLayer = el("g", {}, vp);
  const nodeLayer = el("g", {}, vp);
  const geoms = computeEdgeGeoms(edges, view);
  edges.forEach((e, idx) => {
    const geom = geoms[idx];
    const g = el("g", { class: "edge " + (RELK[e.k].cls || ""), "data-edge": `${e.s},${e.t},${e.i}` }, edgeLayer);
    const kind = RELK[e.k];
    const marker = kind.cls === "k-kernel" ? "arrow-mid" : "arrow";
    el("path", { class: "wire", d: geom.d, "marker-end": `url(#${marker})` }, g);
    el("path", { class: "hitzone", d: geom.d }, g);
    const label = el("text", { x: geom.lx, y: geom.ly - 5, "text-anchor": "middle" }, g);
    label.textContent = trunc(e.l, 30);
    g.addEventListener("click", (ev) => { ev.stopPropagation(); selectEdge(e, g); });
  });

  /* 节点 */
  for (const [id, pos] of Object.entries(view.nodes)) {
    const e = ENT[id];
    const [w, h] = nodeSize(id);
    const [cx, cy] = pos;
    const g = el("g", { class: kindCls(e.kind), "data-node": id, transform: `translate(${cx - w / 2},${cy - h / 2})` }, nodeLayer);
    el("rect", { class: "node-box", x: 0, y: 0, width: w, height: h, rx: 10 }, g);
    const typeT = el("text", { class: "node-type", x: 14, y: 19 }, g);
    typeT.textContent = KINDS[e.kind].label + (e.module ? " · " + trunc(e.module, 18) : "");
    const nameT = el("text", { class: "node-name", x: 14, y: 40 }, g);
    nameT.textContent = trunc(e.name, e.big ? 24 : 20);
    if (e.name.length > (e.big ? 24 : 20)) nameT.setAttribute("font-size", "12");
    if (e.tagline) {
      const tagT = el("text", { class: "node-tag", x: 14, y: 58 }, g);
      tagT.textContent = trunc(e.tagline, e.big ? 26 : 22);
    }
    if (ROOT_BADGE[id]) {
      const bw = 34, bx = w - bw - 10;
      el("rect", { class: "root-badge", x: bx, y: 9, width: bw, height: 14, rx: 4 }, g);
      const rt = el("text", { class: "node-priv", x: bx + bw / 2, y: 19, "text-anchor": "middle" }, g);
      rt.textContent = "ROOT";
    }
    if (e.drill) {
      const dt = el("text", { class: "node-drill", x: w - 14, y: h - 10, "text-anchor": "end" }, g);
      dt.textContent = "下钻 →";
    }
    g.addEventListener("click", (ev) => { ev.stopPropagation(); selectNode(id); });
    g.addEventListener("dblclick", (ev) => { ev.stopPropagation(); if (e.drill) navigate(e.drill, { sel: id }); });
  }

  /* 顶栏 */
  $("#view-title").textContent = view.name;
  $("#view-desc").textContent = view.desc;
  renderCrumbs(view);
  renderLegend();
  fitView();
  bindPanZoom(svg);
  markSelection();
}

function edgesInView(view) {
  const present = new Set(Object.keys(view.nodes));
  const out = [];
  RELS.forEach((r, i) => {
    if (!present.has(r.s) || !present.has(r.t)) return;
    const key = `${r.s},${r.t}`;
    if (view.edgeOnly && !view.edgeOnly.includes(key)) return;
    if ((view.edgeHide || []).includes(key)) return;
    out.push({ ...r, i });
  });
  return out;
}

/* 边几何:锚点 + 三次贝塞尔 + 平行/往返偏移 */
function computeEdgeGeoms(edges, view) {
  const byPair = {};
  edges.forEach((e, idx) => {
    (byPair[`${e.s}→${e.t}`] = byPair[`${e.s}→${e.t}`] || []).push(idx);
  });
  const hasReverse = (e) => byPair[`${e.t}→${e.s}`];
  return edges.map((e, mapIdx) => {
    const [sx, sy] = view.nodes[e.s];
    const [tx, ty] = view.nodes[e.t];
    const [sw, sh] = nodeSize(e.s);
    const [tw, th] = nodeSize(e.t);
    const dx = tx - sx, dy = ty - sy;
    const horiz = Math.abs(dx) >= Math.abs(dy);
    let x1, y1, x2, y2, c1x, c1y, c2x, c2y;
    if (horiz) {
      const dir = dx >= 0 ? 1 : -1;
      x1 = sx + dir * sw / 2; y1 = sy;
      x2 = tx - dir * tw / 2; y2 = ty;
      const bend = Math.min(Math.max(Math.abs(dx) * 0.42, 36), 150);
      c1x = x1 + dir * bend; c1y = y1; c2x = x2 - dir * bend; c2y = y2;
    } else {
      const dir = dy >= 0 ? 1 : -1;
      x1 = sx; y1 = sy + dir * sh / 2;
      x2 = tx; y2 = ty - dir * th / 2;
      const bend = Math.min(Math.max(Math.abs(dy) * 0.42, 36), 150);
      c1x = x1; c1y = y1 + dir * bend; c2x = x2; c2y = y2 - dir * bend;
    }
    /* 平行偏移:法线必须取「规范方向」(字典序小→大)的法向——若取边自身方向
     * 的法向,反向对(A→B 与 B→A)的偏移会在画布上互相抵消,两条曲线与两个
     * 标签完全重合(实测 es↔santad 只渲染出一个标签);取规范法向后反向对
     * 获得相反偏移,曲线扇形展开、标签分开 */
    const group = byPair[`${e.s}→${e.t}`];
    const gIdx = group.indexOf(mapIdx);
    let off = (gIdx - (group.length - 1) / 2) * 17;
    if (hasReverse(e)) off += (e.s < e.t ? 1 : -1) * 11;
    if (off !== 0) {
      const flip = e.s < e.t ? 1 : -1;
      const len = Math.hypot(dx, dy) || 1;
      const nx = (-dy / len) * flip, ny = (dx / len) * flip;
      x1 += nx * off; y1 += ny * off; x2 += nx * off; y2 += ny * off;
      c1x += nx * off * 1.6; c1y += ny * off * 1.6; c2x += nx * off * 1.6; c2y += ny * off * 1.6;
    }
    /* 中点(t=0.5) */
    const mx = (x1 + 3 * c1x + 3 * c2x + x2) / 8;
    const my = (y1 + 3 * c1y + 3 * c2y + y2) / 8;
    return { d: `M ${x1} ${y1} C ${c1x} ${c1y}, ${c2x} ${c2y}, ${x2} ${y2}`, lx: mx, ly: my };
  });
}

/* crumbs */
function renderCrumbs(view) {
  const box = $("#crumbs");
  const crumbs = view.crumb || [view.name];
  box.innerHTML = crumbs.map((c, i) => {
    const last = i === crumbs.length - 1;
    const link = CRUMB_VIEW[c];
    return `${i ? '<span class="sep">/</span>' : ""}<span class="crumb ${last ? "now" : ""}" ${!last && link ? `data-crumb="${link}"` : ""}>${c}</span>`;
  }).join("");
  box.querySelectorAll("[data-crumb]").forEach((n) =>
    n.addEventListener("click", () => navigate(n.dataset.crumb)));
}

/* legend:由 data.js 实际用到的 kinds/relKinds 动态生成。
   词表是项目数据(每个 codebase 的种类由勘探推理),图例只呈现本项目真实存在的种类与线型 */
const FORM_SW = { black: "f-dark", gray: "f-gray", ext: "f-gray", store: "f-gray", artifact: "f-gray", dashed: "dash", dashedgray: "dash" };
const STYLE_LN = { solid: "", dashed: "dash", dotted: "dot", thin: "thin" };
function renderLegend() {
  const lg = $("#legend");
  const usedKinds = Object.keys(KINDS).filter((k) => Object.values(ENT).some((e) => e.kind === k));
  const chips = usedKinds.map((k) =>
    `<span class="lg"><span class="sw ${FORM_SW[formOf(k)] || ""}"></span>${esc(KINDS[k].label || k)}</span>`);
  const kindRows = [];
  for (let i = 0; i < chips.length; i += 4) kindRows.push(chips.slice(i, i + 4).join(""));
  const lineRows = [];
  for (const style of ["solid", "dashed", "dotted", "thin"]) {
    const labels = Object.keys(RELK)
      .filter((k) => RELS.some((r) => r.k === k) && (RELK[k].style || "solid") === style)
      .map((k) => (RELK[k].cls === "k-kernel" ? `<b>${esc(RELK[k].label)}</b>` : esc(RELK[k].label)));
    if (labels.length)
      lineRows.push(`<div class="legend-row"><span class="lg"><span class="ln ${STYLE_LN[style]}"></span>${labels.join(" / ")}</span></div>`);
  }
  lg.innerHTML = `
    <div class="legend-head">图例 <span class="chev">▾</span></div>
    <div class="legend-body">
      ${kindRows.map((r) => `<div class="legend-row">${r}</div>`).join("")}
      ${lineRows.join("")}
      <div class="legend-row" style="color:var(--ink-4)">单击看详情 · 双击下钻 · 拖动平移 · 滚轮缩放</div>
    </div>`;
  lg.querySelector(".legend-head").addEventListener("click", () => lg.classList.toggle("closed"));
  /* 截图/嵌屏场景:#/view?legend=0 让图例默认收起,避免遮挡左下角节点 */
  if (/[?&]legend=0\b/.test(location.hash)) lg.classList.add("closed");
}

/* ============================================================
 * 平移缩放
 * ============================================================ */
function applyTransform() {
  const vp = $("#viewport");
  if (vp) vp.setAttribute("transform", `translate(${state.t.x},${state.t.y}) scale(${state.t.k})`);
  $("#zoom-val").textContent = Math.round(state.t.k * 100) + "%";
}
function fitView() {
  const view = VIEWS[state.view];
  if (!view) return;
  const stage = $("#stage");
  const [cw, ch] = view.canvas;
  const rect = stage.getBoundingClientRect();
  const k = Math.min((rect.width - 56) / cw, (rect.height - 56) / ch, 1.15);
  state.t.k = k;
  state.t.x = (rect.width - cw * k) / 2;
  state.t.y = (rect.height - ch * k) / 2;
  applyTransform();
}
function bindPanZoom(svg) {
  svg.onmousedown = (e) => {
    if (e.button !== 0) return;
    /* 阻止浏览器把拖动手势当成文本选择:选中态会命中 ::selection(黑底白字),
       表现为节点名/边标签变黑块;同时清除已有选区 */
    e.preventDefault();
    window.getSelection()?.removeAllRanges();
    svg.classList.add("panning");
    const sx = e.clientX - state.t.x, sy = e.clientY - state.t.y;
    let raf = 0, px = sx, py = sy;
    const move = (ev) => {
      px = ev.clientX - sx; py = ev.clientY - sy;
      if (raf) return;
      raf = requestAnimationFrame(() => { raf = 0; state.t.x = px; state.t.y = py; applyTransform(); });
    };
    const up = () => {
      svg.classList.remove("panning");
      if (raf) { cancelAnimationFrame(raf); raf = 0; state.t.x = px; state.t.y = py; applyTransform(); }
      window.removeEventListener("mousemove", move);
      window.removeEventListener("mouseup", up);
    };
    window.addEventListener("mousemove", move);
    window.addEventListener("mouseup", up);
  };
  svg.onwheel = (e) => {
    e.preventDefault();
    const rect = svg.getBoundingClientRect();
    const mx = e.clientX - rect.left, my = e.clientY - rect.top;
    const dk = Math.exp(-e.deltaY * 0.0012);
    const nk = Math.min(Math.max(state.t.k * dk, 0.25), 2.6);
    state.t.x = mx - (mx - state.t.x) * (nk / state.t.k);
    state.t.y = my - (my - state.t.y) * (nk / state.t.k);
    state.t.k = nk;
    applyTransform();
  };
  svg.onclick = () => { clearSelection(); };
}
$("#zoom-in").addEventListener("click", () => zoomStep(1.22));
$("#zoom-out").addEventListener("click", () => zoomStep(1 / 1.22));
$("#zoom-fit").addEventListener("click", fitView);
$("#zoom-val").addEventListener("click", fitView);
function zoomStep(f) {
  const svg = $("#canvas");
  const rect = svg.getBoundingClientRect();
  const mx = rect.width / 2, my = rect.height / 2;
  const nk = Math.min(Math.max(state.t.k * f, 0.25), 2.6);
  state.t.x = mx - (mx - state.t.x) * (nk / state.t.k);
  state.t.y = my - (my - state.t.y) * (nk / state.t.k);
  state.t.k = nk;
  applyTransform();
}

/* ============================================================
 * 选中 & 详情抽屉
 * ============================================================ */
function markSelection() {
  document.querySelectorAll(".node").forEach((n) =>
    n.classList.toggle("selected", n.dataset.node === state.sel));
  document.querySelectorAll(".edge").forEach((n) =>
    n.classList.toggle("selected", n.dataset.edge === state.selEdge));
}
function selectNode(id) {
  state.sel = id; state.selEdge = null;
  markSelection(); openDrawer(id); writeHash();
}
function selectEdge(rel, gEl) {
  const key = `${rel.s},${rel.t},${rel.i}`;
  state.selEdge = key; state.sel = null;
  markSelection(); openRelDrawer(rel); writeHash();
}
function clearSelection() {
  state.sel = null; state.selEdge = null;
  markSelection(); closeDrawer(); writeHash();
}

function gotoEntity(id) {
  const e = ENT[id];
  if (!e) return;
  const home = e.home || "overview";
  const viewHas = VIEWS[state.view] && VIEWS[state.view].nodes[id];
  if (!viewHas && state.view !== home) navigate(home, { sel: id });
  else { state.sel = id; state.selEdge = null; markSelection(); openDrawer(id); writeHash(); }
  /* 居中 */
  if (VIEWS[state.view] && VIEWS[state.view].nodes[id]) {
    const [cx, cy] = VIEWS[state.view].nodes[id];
    const rect = $("#stage").getBoundingClientRect();
    state.t.x = rect.width / 2 - cx * state.t.k;
    state.t.y = rect.height / 2 - cy * state.t.k;
    applyTransform();
  }
}

function chip(text, cls = "") { return `<span class="chip ${cls}">${esc(text)}</span>`; }

function openDrawer(id) {
  const e = ENT[id];
  const d = $("#drawer");
  const chips = [chip(KINDS[e.kind].label, e.kind === "daemon" || e.kind === "kernel" ? "dark" : "")];
  if (e.module) chips.push(chip(e.module, "mono"));
  if (ROOT_BADGE[id]) chips.push(chip("ROOT", "dark"));
  $("#drawer-chips").innerHTML = chips.join("");
  $("#drawer-title").textContent = e.name;
  $("#drawer-tagline").textContent = e.tagline || "";

  let body = "";
  if (e.desc) body += `<section><h4>概述</h4><p class="desc">${esc(e.desc)}</p></section>`;
  if (e.resp && e.resp.length) {
    body += `<section><h4>职责</h4><ul class="resp">${e.resp.map((r) => `<li>${esc(r)}</li>`).join("")}</ul></section>`;
  }
  const { out, inn } = relsOf(id);
  if (out.length || inn.length) {
    body += `<section><h4>关系 · ${out.length + inn.length}</h4>`;
    for (const r of out) body += relRow("→", ENT[r.t] ? ENT[r.t].name : r.t, r, r.t);
    for (const r of inn) body += relRow("←", ENT[r.s] ? ENT[r.s].name : r.s, r, r.s);
    body += `</section>`;
  }
  if (e.files && e.files.length) {
    body += `<section><h4>关键文件</h4>${e.files.map((f) => `<div class="file-row">${esc(f)}</div>`).join("")}</section>`;
  }
  if (e.deploy) {
    body += `<section><h4>部署形态</h4><dl class="deploy-grid">${Object.entries(e.deploy).map(([k, v]) => `<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`).join("")}</dl></section>`;
  }
  if (e.notes && e.notes.length) {
    body += `<section><h4>架构备注</h4>${e.notes.map((n) => `<div class="note-row">${esc(n)}</div>`).join("")}</section>`;
  }
  $("#drawer-body").innerHTML = body;

  /* 动作 */
  let acts = "";
  if (e.drill) acts += `<button class="d-btn primary" data-act="drill">进入内部视图 →</button>`;
  acts += `<button class="d-btn" data-act="locate">在「${esc(viewNameOf(id))}」中定位</button>`;
  $("#drawer-actions").innerHTML = acts;
  $("#drawer-actions [data-act=drill]")?.addEventListener("click", () => navigate(e.drill, { sel: id }));
  $("#drawer-actions [data-act=locate]")?.addEventListener("click", () => gotoEntity(id));

  /* 关系行跳转 */
  $("#drawer-body").querySelectorAll("[data-goto]").forEach((n) =>
    n.addEventListener("click", () => gotoEntity(n.dataset.goto)));

  d.classList.add("open");
}
function relRow(dir, name, r, target) {
  return `<div class="rel-row" data-goto="${esc(target)}">
    <span class="rel-dir">${dir}</span>
    <span class="rel-kind-tag">${esc(RELK[r.k].label)}</span>
    <span class="rel-name">${esc(trunc(name, 18))}</span>
    <span class="rel-label">${esc(trunc(r.l, 34))}</span>
  </div>`;
}
function openRelDrawer(rel) {
  const d = $("#drawer");
  const s = ENT[rel.s], t = ENT[rel.t];
  $("#drawer-chips").innerHTML = chip(RELK[rel.k].label, "dark") + chip("关系");
  $("#drawer-title").innerHTML = `${esc(s ? s.name : rel.s)} <span style="color:var(--ink-4)">→</span> ${esc(t ? t.name : rel.t)}`;
  $("#drawer-tagline").textContent = rel.l;
  let body = `<section><h4>说明</h4><p class="desc">${esc(rel.note || rel.l)}</p></section>`;
  body += `<section><h4>类型</h4><p class="desc">${esc(RELK[rel.k].label)} — ${esc({ solid: "同步 / 强耦合通道", dashed: "网络通道", dotted: "异步广播", thin: "构建期 / 静态依赖" }[RELK[rel.k].style] || "")}</p></section>`;
  $("#drawer-body").innerHTML = body;
  $("#drawer-actions").innerHTML =
    `<button class="d-btn" data-goto="${esc(rel.s)}">来源:${esc(trunc(s ? s.name : rel.s, 14))}</button>
     <button class="d-btn" data-goto="${esc(rel.t)}">目标:${esc(trunc(t ? t.name : rel.t, 14))}</button>`;
  $("#drawer-actions").querySelectorAll("[data-goto]").forEach((n) =>
    n.addEventListener("click", () => gotoEntity(n.dataset.goto)));
  d.classList.add("open");
}
function closeDrawer() { $("#drawer").classList.remove("open"); }
$("#drawer-close").addEventListener("click", clearSelection);

/* ============================================================
 * 数据流视图
 * ============================================================ */
function renderFlow() {
  const flow = ATLAS.flows.find((f) => f.id === state.flow) || ATLAS.flows[0];
  /* 空数据防御:flows 为空时给出指引而不是崩溃 */
  if (!flow) {
    $("#flowlist").innerHTML = "";
    $("#view-title").textContent = "数据流";
    $("#view-desc").textContent = "data.js 是空骨架:请按契约填充 flows(lanes + steps)。";
    renderCrumbs({ crumb: ["全景", "数据流"], name: "数据流" });
    $("#flowcanvas").innerHTML = "";
    $("#flowsteps").innerHTML = "";
    return;
  }
  /* 列表 */
  $("#flowlist").innerHTML = ATLAS.flows.map((f, i) => `
    <div class="flow-item ${f.id === flow.id ? "active" : ""}" data-flow="${f.id}">
      <div class="f-name"><span class="f-idx">${String(i + 1).padStart(2, "0")}</span>${esc(f.name)}</div>
      <div class="f-desc">${esc(f.desc)}</div>
    </div>`).join("");
  $("#flowlist").querySelectorAll("[data-flow]").forEach((n) =>
    n.addEventListener("click", () => { state.flow = n.dataset.flow; renderFlow(); writeHash(); }));

  $("#view-title").textContent = flow.name;
  $("#view-desc").textContent = flow.desc;
  renderCrumbs({ crumb: ["全景", "数据流"], name: flow.name });

  /* 时序图 */
  const svg = $("#flowcanvas");
  svg.innerHTML = "";
  const stageW = Math.max($("#flowstage").clientWidth - 40, flow.lanes.length * 190);
  const laneX = {};
  const margin = 90;
  const span = flow.lanes.length > 1 ? (stageW - margin * 2) / (flow.lanes.length - 1) : 0;
  flow.lanes.forEach((l, i) => { laneX[l] = margin + i * span; });
  const stepH = 66, top = 108;
  const H = top + flow.steps.length * stepH + 60;
  svg.setAttribute("width", stageW);
  svg.setAttribute("height", H);

  const defs = el("defs", {}, svg);
  const m1 = el("marker", { id: "seq-arrow", viewBox: "0 0 10 10", refX: 9, refY: 5, markerWidth: 7, markerHeight: 7, orient: "auto-start-reverse" }, defs);
  el("path", { d: "M 0 1.5 L 9 5 L 0 8.5 z" }, m1);
  const m2 = el("marker", { id: "seq-arrow-hot", viewBox: "0 0 10 10", refX: 9, refY: 5, markerWidth: 7, markerHeight: 7, orient: "auto-start-reverse" }, defs);
  el("path", { d: "M 0 1.5 L 9 5 L 0 8.5 z" }, m2);

  /* 泳道 */
  flow.lanes.forEach((l) => {
    const e = ENT[l];
    const x = laneX[l];
    const g = el("g", { cursor: "pointer", "data-lane": l }, svg);
    const bw = 168, bh = 46;
    const lf = e ? formOf(e.kind) : "plain";
    const dark = lf === "black";
    const box = el("rect", { x: x - bw / 2, y: 34, width: bw, height: bh, rx: 9, class: "node-box" }, g);
    if (dark) { box.style.fill = "var(--f-black-fill)"; box.style.stroke = "var(--f-black-stroke)"; }
    else if (lf === "ext") { box.style.fill = "var(--f-fill-ext)"; box.style.stroke = "var(--f-stroke-ext)"; box.style.strokeDasharray = "2 3"; }
    else { box.style.fill = "var(--f-fill)"; box.style.stroke = "var(--f-stroke)"; }
    const nameT = el("text", { class: "seq-lane-name", x, y: 54, "text-anchor": "middle" }, g);
    nameT.textContent = trunc(e ? e.name : l, 16);
    if (dark) nameT.style.fill = "var(--f-black-ink)";
    const typeT = el("text", { class: "seq-lane-type", x, y: 70, "text-anchor": "middle" }, g);
    typeT.textContent = e ? KINDS[e.kind].label : "";
    if (dark) typeT.style.fill = "var(--f-black-ink-3)";
    el("line", { class: "seq-lane-line", x1: x, y1: 84, x2: x, y2: H - 30 }, g);
    g.addEventListener("click", () => { if (ENT[l]) gotoEntity(l); });
  });

  /* 步骤 */
  flow.steps.forEach((st, i) => {
    const y = top + i * stepH;
    const x1 = laneX[st.s], x2 = laneX[st.t];
    const g = el("g", { "data-step": i }, svg);
    if (st.s === st.t) {
      /* 自环 */
      const w = 46;
      el("path", { class: "seq-step-line", d: `M ${x1} ${y} C ${x1 + w} ${y - 16}, ${x1 + w} ${y + 16}, ${x1} ${y + 2}`, fill: "none", "marker-end": "url(#seq-arrow)" }, g);
      const label = el("text", { class: "seq-label", x: x1 + w + 10, y: y + 4 }, g);
      label.textContent = trunc(st.label, 34);
    } else {
      el("line", { class: "seq-step-line", x1, y1: y, x2, y2: y, "marker-end": "url(#seq-arrow)" }, g);
      const label = el("text", { class: "seq-label", x: (x1 + x2) / 2, y: y - 8, "text-anchor": "middle" }, g);
      label.textContent = trunc(st.label, 40);
    }
    el("circle", { class: "seq-num-bg", cx: x1, cy: y, r: 10 }, g);
    const num = el("text", { class: "seq-num", x: x1, y: y + 3.5, "text-anchor": "middle" }, g);
    num.textContent = i + 1;
    g.addEventListener("mouseenter", () => hotStep(i, true));
    g.addEventListener("mouseleave", () => hotStep(i, false));
    g.addEventListener("click", () => scrollToStep(i));
  });

  /* 步骤详表 */
  $("#flowsteps").innerHTML = `<div class="fs-title">步骤详解 · ${flow.steps.length} 步(点击定位)</div>` +
    flow.steps.map((st, i) => {
      const sn = ENT[st.s] ? ENT[st.s].name : st.s;
      const tn = ENT[st.t] ? ENT[st.t].name : st.t;
      return `<div class="fstep" data-fstep="${i}">
        <span class="fs-n">${i + 1}</span>
        <span class="fs-t"><b>${esc(sn)}</b>${st.s === st.t ? " 内部" : ` → <b>${esc(tn)}</b>`} · ${esc(st.d)}</span>
      </div>`;
    }).join("");
  $("#flowsteps").querySelectorAll("[data-fstep]").forEach((n) => {
    const i = +n.dataset.fstep;
    n.addEventListener("mouseenter", () => hotStep(i, true));
    n.addEventListener("mouseleave", () => hotStep(i, false));
    n.addEventListener("click", () => {
      const y = top + i * stepH;
      $("#flowstage").scrollTo({ top: y - 140, behavior: "smooth" });
    });
  });
}
function hotStep(i, on) {
  const g = $(`#flowcanvas [data-step="${i}"]`);
  if (g) {
    g.querySelectorAll(".seq-step-line").forEach((p) => {
      p.classList.toggle("hot", on);
      p.setAttribute("marker-end", on ? "url(#seq-arrow-hot)" : "url(#seq-arrow)");
    });
  }
  const row = $(`#flowsteps [data-fstep="${i}"]`);
  if (row) row.classList.toggle("hot", on);
}
function scrollToStep(i) {
  const y = 108 + i * 66;
  $("#flowstage").scrollTo({ top: y - 140, behavior: "smooth" });
}

/* ============================================================
 * 设计原则视图
 * ============================================================ */
function renderPrinciples() {
  $("#view-title").textContent = "设计原则";
  $("#view-desc").textContent = "从全部代码反向提炼的宏观架构观——它们不是文档里的口号,而是每个模块反复出现的结构同构。";
  renderCrumbs({ crumb: ["全景", "设计原则"], name: "设计原则" });
  const box = $("#principles");
  box.innerHTML = `
    <div class="p-intro">
      <h2>宏观设计观</h2>
      <p>${ATLAS.principles.length} 条原则,来自 ${Object.keys(ATLAS.entities).length} 个实体、${ATLAS.relations.length} 条关系的本体勘探。其中标为债务的是时间留下的真实痕迹——一并如实呈现。</p>
    </div>
    <div id="p-grid">${ATLAS.principles.map((p, i) => `
      <div class="p-card ${p.debt ? "debt" : ""}">
        <span class="p-idx">PRINCIPLE ${String(i + 1).padStart(2, "0")}</span>
        <h3>${esc(p.name)}</h3>
        <div class="p-body">${esc(p.body)}</div>
        <div class="p-evi">${esc(p.evi)}</div>
        <div class="p-refs">${p.refs.map((r) => `<span class="chip mono" style="cursor:pointer" data-ref="${esc(r)}">${esc(ENT[r] ? trunc(ENT[r].name, 18) : r)} →</span>`).join("")}</div>
      </div>`).join("")}
    </div>`;
  box.querySelectorAll("[data-ref]").forEach((n) =>
    n.addEventListener("click", () => gotoEntity(n.dataset.ref)));
}

/* ============================================================
 * 搜索
 * ============================================================ */
const sOvl = $("#search-ovl"), sInput = $("#search-input"), sRes = $("#search-results");
let sHot = 0, sList = [];
function openSearch() { sOvl.classList.add("on"); sInput.value = ""; doSearch(""); sInput.focus(); }
function closeSearch() { sOvl.classList.remove("on"); }
function doSearch(q) {
  q = q.trim().toLowerCase();
  sList = Object.entries(ENT).filter(([id, e]) => {
    if (!q) return true;
    const hay = [e.name, e.tagline, e.module, e.kind, KINDS[e.kind].label, id,
      ...(e.files || []), ...(e.resp || [])].join(" ").toLowerCase();
    return hay.includes(q);
  }).slice(0, 40);
  sHot = 0;
  sRes.innerHTML = sList.length ? sList.map(([id, e], i) => `
    <div class="sr ${i === sHot ? "hot" : ""}" data-sr="${id}">
      <span class="sr-kind">${esc(KINDS[e.kind].label)}</span>
      <span class="sr-name">${esc(e.name)}</span>
      <span class="sr-tag">${esc(trunc(e.tagline || "", 26))}</span>
      <span class="sr-view">${esc(viewNameOf(id))}</span>
    </div>`).join("") : `<div id="search-empty">没有匹配的实体</div>`;
  sRes.querySelectorAll("[data-sr]").forEach((n) =>
    n.addEventListener("click", () => { closeSearch(); gotoEntity(n.dataset.sr); }));
}
sInput.addEventListener("input", () => doSearch(sInput.value));
sInput.addEventListener("keydown", (e) => {
  if (e.key === "ArrowDown" || e.key === "ArrowUp") {
    e.preventDefault();
    sHot = (sHot + (e.key === "ArrowDown" ? 1 : -1) + sList.length) % Math.max(sList.length, 1);
    sRes.querySelectorAll(".sr").forEach((n, i) => n.classList.toggle("hot", i === sHot));
    sRes.querySelectorAll(".sr")[sHot]?.scrollIntoView({ block: "nearest" });
  } else if (e.key === "Enter" && sList[sHot]) {
    closeSearch(); gotoEntity(sList[sHot][0]);
  } else if (e.key === "Escape") closeSearch();
});
$("#btn-search").addEventListener("click", openSearch);
sOvl.addEventListener("click", (e) => { if (e.target === sOvl) closeSearch(); });
window.addEventListener("keydown", (e) => {
  if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") { e.preventDefault(); openSearch(); }
  else if (e.key === "Escape") { if (sOvl.classList.contains("on")) closeSearch(); else clearSelection(); }
});

/* ============================================================
 * 主题(视觉令牌覆盖层:data-theme 属性 + CSS 自定义属性)
 * 优先级: URL ?theme= > localStorage > meta.theme > light
 * 形态语义(尤其 black=最高权限)在任意主题下都由 CSS 令牌保真
 * ============================================================ */
const THEMES = ["light", "dark", "paper", "sepia"];
function applyTheme(name) {
  if (!THEMES.includes(name)) name = "light";
  document.documentElement.setAttribute("data-theme", name);
  try { localStorage.setItem("atlas-theme", name); } catch (_) {}
  const sel = $("#theme-sel");
  if (sel && sel.value !== name) sel.value = name;
}
function bootTheme() {
  const fromHash = (location.hash.match(/[?&]theme=([\w-]+)/) || [])[1];
  let stored = null;
  try { stored = localStorage.getItem("atlas-theme"); } catch (_) {}
  const metaTheme = (ATLAS.meta && ATLAS.meta.theme) || "light";
  applyTheme(fromHash || stored || metaTheme);
}
const themeSel = $("#theme-sel");
if (themeSel) themeSel.addEventListener("change", () => applyTheme(themeSel.value));

/* ============================================================
 * 启动
 * ============================================================ */
function hydrateBrand() {
  const m = ATLAS.meta || {};
  document.title = (m.title || "Architecture Atlas") + " · 架构大图";
  const mark = document.querySelector("#sidebar .brand .dot");
  if (mark) mark.textContent = m.mark || "AZ";
  const name = document.querySelector("#sidebar .brand .mark span:last-child");
  if (name) name.textContent = m.product || "架构大图";
  const sub = document.querySelector("#sidebar .brand .sub");
  if (sub) sub.textContent = m.subtitle || "";
}
hydrateBrand();
buildNav();
bootTheme();
readHash();
render();
window.addEventListener("resize", () => { if (VIEWS[state.view]) fitView(); });
