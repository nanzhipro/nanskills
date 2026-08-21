#!/usr/bin/env node
/* validate_atlas_data.js — 架构大图 data.js 引用完整性校验
 * 用法: node validate_atlas_data.js <path/to/data.js>
 * 退出码: 0 = 全绿; 1 = 存在 BAD(引用悬空/视图缺节点等); 2 = 文件本身无法解析
 */
"use strict";
const fs = require("fs");

const file = process.argv[2];
if (!file) { console.error("用法: node validate_atlas_data.js <data.js>"); process.exit(2); }

let ATLAS;
try {
  const vm = require("vm");
  const src = fs.readFileSync(file, "utf8");
  const sandbox = {};
  vm.createContext(sandbox);
  vm.runInContext(src + "\n;globalThis.__A = ATLAS;", sandbox, { filename: file });
  ATLAS = sandbox.__A;
} catch (e) {
  /* vm 带 filename,stack 首行即 "文件:行号",便于定位括号/逗号错误 */
  console.error("PARSE FAIL:", (e.stack || e.message).split("\n").slice(0, 3).join("\n"));
  console.error("HINT: 实体/视图 id 含连字符(如 exec-server)作对象键时必须加引号:\"exec-server\": {...};对象键漏逗号/花括号不配对也会在此报错");
  process.exit(2);
}

/* ---- 结构形状(协议形状):字段类型与必填项 ---- */
const isNumPair = (a) => Array.isArray(a) && a.length === 2 && a.every((n) => typeof n === "number");
const isObj = (v) => v && typeof v === "object" && !Array.isArray(v);
if (!isObj(ATLAS.entities) || !Array.isArray(ATLAS.relations) || !isObj(ATLAS.views)
  || !Array.isArray(ATLAS.flows) || !Array.isArray(ATLAS.principles)
  || !isObj(ATLAS.kinds) || !isObj(ATLAS.relKinds)) {
  console.error("SCHEMA FAIL: kinds/relKinds/entities/relations/views/flows/principles 结构缺失或类型错误");
  process.exit(2);
}

const ids = new Set(Object.keys(ATLAS.entities));
const viewIds = new Set(Object.keys(ATLAS.views));
const kindIds = new Set(Object.keys(ATLAS.kinds));
const relKindIds = new Set(Object.keys(ATLAS.relKinds));
const bad = [], warn = [];

/* ---- id 字符集:id 会进 URL hash 与 edge 键(edgeOnly/edgeHide 以逗号拼接),
 *      只允许字母/数字/下划线/连字符;含空格或逗号会直接破坏路由与边寻址 ---- */
const ID_OK = /^[\w-]+$/;
for (const id of ids) if (!ID_OK.test(id)) bad.push(`entity id "${id}": 含非法字符(仅允许字母/数字/_/-)`);
for (const id of viewIds) if (!ID_OK.test(id)) bad.push(`view id "${id}": 含非法字符(仅允许字母/数字/_/-)`);
for (const f of ATLAS.flows) if (f.id && !ID_OK.test(f.id)) bad.push(`flow id "${f.id}": 含非法字符(仅允许字母/数字/_/-)`);
for (const id of kindIds) if (!ID_OK.test(id)) bad.push(`kind id "${id}": 含非法字符(仅允许字母/数字/_/-)`);
for (const id of relKindIds) if (!ID_OK.test(id)) bad.push(`relKind id "${id}": 含非法字符(仅允许字母/数字/_/-)`);

/* ---- 词表合法性(两层模型):form/style 是协议层,写错 = 节点/边无样式 ---- */
const FORMS = new Set(["black", "bold", "plain", "dashed", "dashedgray", "gray", "ext", "store", "mono", "cicd", "artifact"]);
const STYLES = new Set(["solid", "dashed", "dotted", "thin"]);
for (const [id, k] of Object.entries(ATLAS.kinds)) {
  if (k.form !== undefined && !FORMS.has(k.form))
    bad.push(`kind ${id}: 未知 form "${k.form}"(可用:${[...FORMS].join("/")})`);
  if (typeof k.label !== "string" || !k.label) warn.push(`kind ${id}: 缺 label`);
}
for (const [id, k] of Object.entries(ATLAS.relKinds)) {
  if (k.style !== undefined && !STYLES.has(k.style))
    bad.push(`relKind ${id}: 未知 style "${k.style}"(可用:solid/dashed/dotted/thin)`);
  if (typeof k.label !== "string" || !k.label) warn.push(`relKind ${id}: 缺 label`);
}

/* ---- 僵尸词表:定义了但本项目没用到——图例按实际使用生成,剪除更干净 ---- */
const usedKinds = new Set(Object.values(ATLAS.entities).map((e) => e.kind));
for (const k of kindIds) if (!usedKinds.has(k) && usedKinds.size)
  warn.push(`kind ${k}: 词表条目未被任何实体使用(可从本项目词表剪除)`);
const usedRelKinds = new Set(ATLAS.relations.map((r) => r.k));
for (const k of relKindIds) if (!usedRelKinds.has(k) && usedRelKinds.size)
  warn.push(`relKind ${k}: 词表条目未被任何关系使用(可从本项目词表剪除)`);

if (!isObj(ATLAS.meta) || typeof ATLAS.meta.title !== "string" || !ATLAS.meta.title)
  warn.push("meta.title 为空(骨架待填充)");
const THEME_IDS = new Set(["light", "dark", "paper", "sepia"]);
if (ATLAS.meta && ATLAS.meta.theme && !THEME_IDS.has(ATLAS.meta.theme))
  warn.push(`meta.theme "${ATLAS.meta.theme}" 未知(可用:light/dark/paper/sepia)`);
for (const [id, e] of Object.entries(ATLAS.entities)) {
  if (typeof e.name !== "string" || !e.name) bad.push(`entity ${id}: 缺 name`);
  if (e.tagline && e.tagline.length > 28) warn.push(`entity ${id}: tagline ${e.tagline.length} 字符偏长,节点上会截断`);
}
ATLAS.relations.forEach((r, i) => {
  if (typeof r.s !== "string" || typeof r.t !== "string" || typeof r.k !== "string")
    bad.push(`rel#${i}: s/t/k 必须为字符串`);
  if (typeof r.l !== "string" || !r.l) warn.push(`rel#${i}: 缺标签 l`);
});
for (const [vid, v] of Object.entries(ATLAS.views)) {
  if (!isNumPair(v.canvas)) bad.push(`view ${vid}: canvas 须为 [w, h] 数字对`);
  if (!isObj(v.nodes)) bad.push(`view ${vid}: nodes 缺失或不是对象`);
  else for (const [n, pos] of Object.entries(v.nodes))
    if (!isNumPair(pos)) bad.push(`view ${vid}: 节点 "${n}" 坐标须为 [cx, cy] 数字对`);
  (v.groups || []).forEach((g, gi) => {
    if (!(typeof g.x === "number" && typeof g.y === "number" && typeof g.w === "number" && typeof g.h === "number"))
      bad.push(`view ${vid} group#${gi}: x/y/w/h 须为数字`);
    if (!g.label) warn.push(`view ${vid} group#${gi}: 缺 label`);
  });
}
for (const f of ATLAS.flows) {
  if (!f.id || !f.name) bad.push(`flow ${f.id || "?"}: 缺 id 或 name`);
  if (!Array.isArray(f.lanes)) bad.push(`flow ${f.id}: lanes 须为数组`);
  if (!Array.isArray(f.steps)) bad.push(`flow ${f.id}: steps 须为数组`);
}
for (const p of ATLAS.principles) {
  if (!p.name || !p.body) bad.push(`principle "${p.name || "?"}": 缺 name 或 body`);
}

/* ---- 引用完整性 ---- */
/* 实体:kind / home / drill 合法 */
for (const [id, e] of Object.entries(ATLAS.entities)) {
  if (!kindIds.has(e.kind)) bad.push(`entity ${id}: 未知 kind "${e.kind}"`);
  if (!e.home) bad.push(`entity ${id}: 缺 home 视图`);
  else if (!viewIds.has(e.home)) bad.push(`entity ${id}: home 视图 "${e.home}" 不存在`);
  if (e.drill && !viewIds.has(e.drill)) bad.push(`entity ${id}: drill 视图 "${e.drill}" 不存在`);
}

/* 关系:端点与 kind 合法 */
ATLAS.relations.forEach((r, i) => {
  if (!ids.has(r.s)) bad.push(`rel#${i}: 源 "${r.s}" 不存在`);
  if (!ids.has(r.t)) bad.push(`rel#${i}: 目标 "${r.t}" 不存在`);
  if (!relKindIds.has(r.k)) bad.push(`rel#${i}(${r.s}→${r.t}): 未知 relKind "${r.k}"`);
  if (r.s === r.t) warn.push(`rel#${i}: 自环 ${r.s}(架构图建议只出现在数据流里)`);
});

/* 视图:节点存在、edgeOnly/edgeHide 端点在场、孤立节点警告 */
for (const [vid, v] of Object.entries(ATLAS.views)) {
  const present = new Set(Object.keys(v.nodes));
  for (const n of present) if (!ids.has(n)) bad.push(`view ${vid}: 节点 "${n}" 不是实体`);
  for (const k of v.edgeOnly || []) {
    const [a, b] = k.split(",");
    if (!present.has(a) || !present.has(b)) bad.push(`view ${vid}: edgeOnly "${k}" 端点不在场`);
  }
  for (const k of v.edgeHide || []) {
    const [a, b] = k.split(",");
    if (!present.has(a) && !present.has(b)) warn.push(`view ${vid}: edgeHide "${k}" 两端都不在场(无效条目)`);
  }
  const hasEdge = new Set();
  ATLAS.relations.forEach((r) => {
    if (!present.has(r.s) || !present.has(r.t)) return;
    const key = `${r.s},${r.t}`;
    if (v.edgeOnly && !v.edgeOnly.includes(key)) return;
    if ((v.edgeHide || []).includes(key)) return;
    hasEdge.add(r.s); hasEdge.add(r.t);
  });
  for (const n of present) if (!hasEdge.has(n)) warn.push(`view ${vid}: 节点 "${n}" 孤立无边`);
}

/* 数据流:lanes 是实体,steps 端点在 lanes 内 */
for (const f of ATLAS.flows) {
  const lanes = new Set(f.lanes);
  for (const l of f.lanes) if (!ids.has(l)) bad.push(`flow ${f.id}: lane "${l}" 不是实体`);
  f.steps.forEach((st, i) => {
    if (!lanes.has(st.s)) bad.push(`flow ${f.id} step#${i}: s "${st.s}" 不在 lanes`);
    if (!lanes.has(st.t)) bad.push(`flow ${f.id} step#${i}: t "${st.t}" 不在 lanes`);
  });
}

/* 设计原则:refs 是实体 */
for (const p of ATLAS.principles)
  for (const r of p.refs || []) if (!ids.has(r)) bad.push(`principle "${p.name}": ref "${r}" 不是实体`);

console.log(`entities: ${Object.keys(ATLAS.entities).length}  relations: ${ATLAS.relations.length}  views: ${viewIds.size}  flows: ${ATLAS.flows.length}  principles: ${ATLAS.principles.length}`);
if (warn.length) console.log("WARN:\n" + warn.map((w) => "  ~ " + w).join("\n"));
if (bad.length) { console.log("BAD:\n" + bad.map((b) => "  ✗ " + b).join("\n")); process.exit(1); }
console.log("all refs OK");
