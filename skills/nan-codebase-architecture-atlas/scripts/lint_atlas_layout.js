#!/usr/bin/env node
/* lint_atlas_layout.js — 架构大图视图布局几何检查(截图前置,把目检问题机器化)
 * 用法: node lint_atlas_layout.js <path/to/data.js> [--window=WxH]
 * 检查项(与 references/visual-and-layout.md §3 目检清单一一对应):
 *   BAD  节点两两重叠(含 big 节点尺寸)
 *   BAD  节点越过画布边界
 *   BAD  节点跨越组框边界(半进半出;完全在内/完全在外都算合法)
 *   WARN 边穿过非端点节点(按引擎同款三次贝塞尔采样)
 *   WARN 两条边的标签中点过近(引擎把标签画在曲线 t=0.5 处,共享中点会互叠)
 *   WARN 节点落入图例死区(默认窗口 fit 截图时左下角被图例面板覆盖的近似区域)
 *   WARN 视图节点数 > 22(布局规则上限)
 * 退出码: 0 = 无 BAD; 1 = 存在 BAD; 2 = 文件无法解析
 */
"use strict";
const fs = require("fs");
const vm = require("vm");

const file = process.argv[2];
if (!file) { console.error("用法: node lint_atlas_layout.js <data.js> [--window=WxH]"); process.exit(2); }
const winArg = (process.argv.find((a) => a.startsWith("--window=")) || "--window=1680x1050").slice(9);
const [WIN_W, WIN_H] = winArg.split("x").map(Number);

let ATLAS;
try {
  const sandbox = {};
  vm.createContext(sandbox);
  vm.runInContext(fs.readFileSync(file, "utf8") + "\n;globalThis.__A = ATLAS;", sandbox, { filename: file });
  ATLAS = sandbox.__A;
} catch (e) {
  console.error("PARSE FAIL:", (e.stack || e.message).split("\n").slice(0, 3).join("\n"));
  process.exit(2);
}

/* ---- 与引擎一致的尺寸与边几何(改引擎参数时需同步) ---- */
const NODE_W = 208, NODE_H = 70, BIG_W = 250, BIG_H = 86;
const nodeSize = (id) => (ATLAS.entities[id] && ATLAS.entities[id].big ? [BIG_W, BIG_H] : [NODE_W, NODE_H]);
const boxOf = (id, [cx, cy]) => {
  const [w, h] = nodeSize(id);
  return { x1: cx - w / 2, y1: cy - h / 2, x2: cx + w / 2, y2: cy + h / 2 };
};
const intersects = (a, b, pad = 0) =>
  a.x1 < b.x2 + pad && a.x2 > b.x1 - pad && a.y1 < b.y2 + pad && a.y2 > b.y1 - pad;
const contains = (outer, inner) =>
  inner.x1 >= outer.x1 && inner.x2 <= outer.x2 && inner.y1 >= outer.y1 && inner.y2 <= outer.y2;

/* 引擎的边几何:锚点 → 弯度 → 平行偏移 → 贝塞尔;标签在 t=0.5 */
function edgeGeoms(view, edges) {
  const byPair = {};
  edges.forEach((e, idx) => { (byPair[`${e.s}→${e.t}`] = byPair[`${e.s}→${e.t}`] || []).push(idx); });
  const hasReverse = (e) => byPair[`${e.t}→${e.s}`];
  return edges.map((e, mapIdx) => {
    const [sx, sy] = view.nodes[e.s], [tx, ty] = view.nodes[e.t];
    const [sw, sh] = nodeSize(e.s), [tw, th] = nodeSize(e.t);
    const dx = tx - sx, dy = ty - sy;
    const horiz = Math.abs(dx) >= Math.abs(dy);
    let x1, y1, x2, y2, c1x, c1y, c2x, c2y;
    if (horiz) {
      const dir = dx >= 0 ? 1 : -1;
      x1 = sx + dir * sw / 2; y1 = sy; x2 = tx - dir * tw / 2; y2 = ty;
      const bend = Math.min(Math.max(Math.abs(dx) * 0.42, 36), 150);
      c1x = x1 + dir * bend; c1y = y1; c2x = x2 - dir * bend; c2y = y2;
    } else {
      const dir = dy >= 0 ? 1 : -1;
      x1 = sx; y1 = sy + dir * sh / 2; x2 = tx; y2 = ty - dir * th / 2;
      const bend = Math.min(Math.max(Math.abs(dy) * 0.42, 36), 150);
      c1x = x1; c1y = y1 + dir * bend; c2x = x2; c2y = y2 - dir * bend;
    }
    const group = byPair[`${e.s}→${e.t}`];
    let off = (group.indexOf(mapIdx) - (group.length - 1) / 2) * 17;
    if (hasReverse(e)) off += (e.s < e.t ? 1 : -1) * 11;
    if (off !== 0) {
      /* 与引擎一致:法线取规范方向(字典序小→大),反向对获得相反偏移 */
      const flip = e.s < e.t ? 1 : -1;
      const len = Math.hypot(dx, dy) || 1, nx = (-dy / len) * flip, ny = (dx / len) * flip;
      x1 += nx * off; y1 += ny * off; x2 += nx * off; y2 += ny * off;
      c1x += nx * off * 1.6; c1y += ny * off * 1.6; c2x += nx * off * 1.6; c2y += ny * off * 1.6;
    }
    const B = (t) => {
      const u = 1 - t;
      return [
        u * u * u * x1 + 3 * u * u * t * c1x + 3 * u * t * t * c2x + t * t * t * x2,
        u * u * u * y1 + 3 * u * u * t * c1y + 3 * u * t * t * c2y + t * t * t * y2,
      ];
    };
    const [lx, ly] = [(x1 + 3 * c1x + 3 * c2x + x2) / 8, (y1 + 3 * c1y + 3 * c2y + y2) / 8];
    return { e, B, lx, ly };
  });
}

/* 视图内可见边(与引擎规则一致:两端在场;edgeOnly 白名单;edgeHide 黑名单) */
function visibleEdges(vid, v) {
  const present = new Set(Object.keys(v.nodes));
  return ATLAS.relations
    .filter((r) => present.has(r.s) && present.has(r.t))
    .filter((r) => !v.edgeOnly || v.edgeOnly.includes(`${r.s},${r.t}`))
    .filter((r) => !(v.edgeHide || []).includes(`${r.s},${r.t}`))
    .map((r) => ({ s: r.s, t: r.t, l: r.l }));
}

/* 图例死区(近似):默认窗口 fit 截图时,图例面板覆盖屏幕左下;
 * 经验比例(WINDOW=1680x1050 实测拟合):x < canvasW*0.252 且 y > canvasH*0.66 */
const DEAD_X = 0.252 * (WIN_W / 1680), DEAD_Y = 1 - 0.34 * (WIN_H / 1050);

const bad = [], warn = [];
for (const [vid, v] of Object.entries(ATLAS.views)) {
  const ids = Object.keys(v.nodes);
  const boxes = {};
  for (const id of ids) boxes[id] = boxOf(id, v.nodes[id]);

  /* 节点数上限 */
  if (ids.length > 22) warn.push(`${vid}: ${ids.length} 个节点超过 22 上限,考虑拆分`);

  /* 画布边界 */
  if (Array.isArray(v.canvas)) {
    const [cw, ch] = v.canvas;
    for (const id of ids) {
      const b = boxes[id];
      if (b.x1 < 0 || b.y1 < 0 || b.x2 > cw || b.y2 > ch)
        bad.push(`${vid}: 节点 "${id}" 越过画布边界(${JSON.stringify(v.nodes[id])} vs canvas ${cw}x${ch})`);
    }
  }

  /* 节点两两重叠 */
  for (let i = 0; i < ids.length; i++)
    for (let j = i + 1; j < ids.length; j++)
      if (intersects(boxes[ids[i]], boxes[ids[j]], -2))
        bad.push(`${vid}: 节点 "${ids[i]}" 与 "${ids[j]}" 重叠`);

  /* 组框边界穿越(半进半出) */
  for (const [gi, g] of (v.groups || []).entries()) {
    const gr = { x1: g.x, y1: g.y, x2: g.x + g.w, y2: g.y + g.h };
    for (const id of ids) {
      const b = boxes[id];
      if (intersects(b, gr) && !contains(gr, b))
        bad.push(`${vid}: 节点 "${id}" 跨越组框 #${gi}(${g.label || "?"})边界——要么进要么出`);
    }
  }

  /* 图例死区 */
  if (Array.isArray(v.canvas)) {
    const dz = { x1: 0, y1: v.canvas[1] * DEAD_Y, x2: v.canvas[0] * DEAD_X, y2: v.canvas[1] };
    for (const id of ids)
      if (intersects(boxes[id], dz))
        warn.push(`${vid}: 节点 "${id}" 落入图例死区(fit 截图会被左下角图例遮挡;可挪节点或截图时用 NOLEGEND=1)`);
  }

  /* 边:穿越非端点节点 + 标签中点互叠 */
  const geoms = edgeGeoms(v, visibleEdges(vid, v));
  for (const g of geoms) {
    for (const id of ids) {
      if (id === g.e.s || id === g.e.t) continue;
      const b = boxes[id], ib = { x1: b.x1 + 8, y1: b.y1 + 8, x2: b.x2 - 8, y2: b.y2 - 8 };
      for (let t = 0.1; t <= 0.9; t += 0.04) {
        const [px, py] = g.B(t);
        if (px > ib.x1 && px < ib.x2 && py > ib.y1 && py < ib.y2) {
          warn.push(`${vid}: 边 ${g.e.s}→${g.e.t} 穿过节点 "${id}"(t≈${t.toFixed(2)})`);
          break;
        }
      }
    }
  }
  for (let i = 0; i < geoms.length; i++)
    for (let j = i + 1; j < geoms.length; j++) {
      const a = geoms[i], b = geoms[j];
      if (Math.hypot(a.lx - b.lx, a.ly - b.ly) < 18)
        warn.push(`${vid}: 边标签过近 ${a.e.s}→${a.e.t} 与 ${b.e.s}→${b.e.t}(中点相距 ${Math.round(Math.hypot(a.lx - b.lx, a.ly - b.ly))}px,可能互叠)`);
    }
}

const nb = bad.length, nw = warn.length;
console.log(`layout lint: ${Object.keys(ATLAS.views).length} views, BAD ${nb}, WARN ${nw}`);
if (bad.length) console.log("BAD:\n" + bad.map((x) => "  ✗ " + x).join("\n"));
if (warn.length) console.log("WARN:\n" + warn.map((x) => "  ~ " + x).join("\n"));
if (!nb && !nw) console.log("layout OK");
process.exit(nb ? 1 : 0);
