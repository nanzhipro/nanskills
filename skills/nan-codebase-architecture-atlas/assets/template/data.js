/* ============================================================
 * Architecture Atlas · 数据契约骨架
 *
 * 本体论两层模型(先理解这个再填充):
 *   协议层(与引擎绑定,跨项目复用):
 *     ① 形态原语 form —— 节点的视觉形态(black/bold/dashed/…),CSS 绑定在
 *        Atlas.html 的 .node.k-f-<form> 规则;关系线型 style(solid/dashed/
 *        dotted/thin)与修饰 cls(k-kernel 加粗)。
 *     ② 字段级 schema —— references/ontology-modeling.md §3,由校验器强制执行。
 *   数据层(每个项目由勘探动态推理,禁止照抄):
 *     ① kinds / relKinds 词表 —— 本项目有哪些实体种类、各叫什么、各映射到哪个
 *        形态。下面的默认词表只是"系统软件"领域的常见起点:剪除本项目没有的
 *        种类(一个纯库项目没有守护进程)、按领域语言改写 label/desc、按需新增
 *        kind(选一个 form 即可,不用改引擎)。
 *     ② entities / relations / views / flows / principles —— 全部由勘探填充。
 *
 * 图例由引擎按"实际用到的 kinds/relKinds"自动生成——词表写错、写死、塞进
 * 本项目没有的僵尸种类,都会直接在图里露馅。
 *
 * 填充规则(合并/分层/证据/债务):references/ontology-modeling.md §4
 * 布局与视觉语义:references/visual-and-layout.md
 * 完整示例(仅学习用,勿带入交付):assets/template/data.example.js
 * ============================================================ */
"use strict";

const ATLAS = {
  /* 项目元信息:mark 为品牌角标字母(≤2 字符),repos 为仓库名列表;
   * theme 为默认主题(light/dark/paper/sepia),生成时确定,运行时仍可切换 */
  meta: { title: "", subtitle: "", mark: "", product: "", repos: [], theme: "light" },

  /* ---- 形态原语词表(协议层,引擎绑定,勿增删 id) ----
   * black      黑底白字:最高权限/内核毗邻实体专用,全图只给它
   * bold       白底加粗框:服务端/提供 API 的实体
   * plain      白底常规框(默认,不写 form 即 plain)
   * dashed     白底虚线框:被链接/被加载的库
   * dashedgray 浅灰虚线框:被托管的工作者/隔离服务
   * gray       浅灰底:扩展类实体
   * ext        灰底疏虚线框:产品边界之外的参与者
   * store      白底灰框:数据存储
   * mono       白底+等宽字体名:CLI/工具
   * cicd       白底灰框:流水线
   * artifact   极浅灰底:构建产物
   */
  /* ---- 默认 kind 词表(数据层,系统软件领域起点——按本项目勘探结果剪改) ---- */
  kinds: {
    daemon:   { label: "守护进程",   desc: "特权/常驻后台进程",       form: "black" },
    service:  { label: "后端服务",   desc: "提供 API 的服务进程",     form: "bold" },
    process:  { label: "用户进程",   desc: "用户会话内运行的进程/前端" },
    worker:   { label: "Worker",   desc: "后台任务工作者",           form: "dashedgray" },
    sysex:    { label: "系统扩展",   desc: "操作系统扩展(内核毗邻)",  form: "gray" },
    appex:    { label: "应用扩展",   desc: "宿主应用的扩展组件",       form: "gray" },
    xpc:      { label: "隔离服务",   desc: "进程隔离的托管服务(XPC 等)", form: "dashedgray" },
    cli:      { label: "命令行工具", desc: "运维/诊断 CLI",           form: "mono" },
    lib:      { label: "库 / 包",    desc: "构建期链接的库",           form: "dashed" },
    engine:   { label: "引擎库",     desc: "独立演进的能力引擎",       form: "dashed" },
    kernel:   { label: "内核/系统",  desc: "操作系统内核或系统级接口",  form: "black" },
    external: { label: "外部实体",   desc: "产品边界之外的参与者",     form: "ext" },
    store:    { label: "数据存储",   desc: "DB / 缓存 / 文件等持久化",  form: "store" },
    tool:     { label: "工具",       desc: "构建/发布期工具",          form: "mono" },
    cicd:     { label: "CI/CD",    desc: "持续集成流水线",           form: "cicd" },
    artifact: { label: "构建产物",   desc: "打包/签名产物",            form: "artifact" },
    manager:  { label: "管理器",     desc: "进程内核心管理器(单例)" },
    subsystem:{ label: "子系统",     desc: "进程内功能子系统" },
    protocol: { label: "协议",       desc: "跨边界通信协议" },
  },

  /* ---- 默认关系词表(数据层):如实命名协议,没有就新增条目并选一个 style ---- */
  relKinds: {
    call:   { label: "进程内调用",  style: "solid",  cls: "" },
    rpc:    { label: "RPC",        style: "solid",  cls: "" },
    ffi:    { label: "FFI",        style: "solid",  cls: "" },
    sys:    { label: "系统 API",   style: "solid",  cls: "" },
    exec:   { label: "exec",       style: "solid",  cls: "" },
    kernel: { label: "内核通道",    style: "solid",  cls: "k-kernel" },
    ipc:    { label: "IPC",        style: "solid",  cls: "" },
    http:   { label: "HTTP/REST",  style: "dashed", cls: "k-net" },
    ws:     { label: "WebSocket",  style: "dashed", cls: "k-net" },
    mq:     { label: "消息队列",    style: "dashed", cls: "k-net" },
    bridge: { label: "桥接",        style: "dashed", cls: "k-net" },
    notify: { label: "异步通知",    style: "dotted", cls: "k-notify" },
    use:    { label: "人机交互",    style: "dotted", cls: "k-notify" },
    dep:    { label: "包依赖",      style: "thin",   cls: "k-build" },
    link:   { label: "动态链接",    style: "thin",   cls: "k-build" },
    dlopen: { label: "dlopen",     style: "thin",   cls: "k-build" },
    store:  { label: "读写",        style: "thin",   cls: "k-build" },
    build:  { label: "构建消费",    style: "thin",   cls: "k-build" },
    git:    { label: "Git 同步",   style: "thin",   cls: "k-build" },
  },

  /* ---- 动态填充区(数据层):勘探 → 本体建模 → 视图布局 → 校验 ---- */
  entities: {},
  relations: [],
  views: {},
  flows: [],
  principles: [],
};
