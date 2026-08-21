/* ============================================================
 * 架构本体数据 · 最小示例(全部替换为你自己的本体)
 * 字段级说明见 references/ontology-modeling.md §3
 * ============================================================ */
"use strict";

const ATLAS = {
  meta: {
    title: "示例产品 Example Product",
    subtitle: "示例产品的本体架构",
    mark: "EX",            // 品牌角标字母(≤2 字符)
    product: "架构大图",    // 品牌名
    repos: ["example-repo"],
    theme: "light",       // 默认主题(light/dark/paper/sepia),可省略
  },
  },

  /* 实体种类词表(项目数据:按勘探剪除/改名/新增;form 选形态原语,见 ontology-modeling.md §2) */
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

  /* 关系类型(style: solid 同步 / dashed 网络 / dotted 广播 / thin 构建期;cls: k-kernel 加粗内核通道) */
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

  entities: {
    auth: {
      name: "身份服务商", kind: "external", module: "第三方",
      home: "overview",
      tagline: "SSO / OIDC",
      desc: "外部身份提供方。",
    },
    web: {
      name: "WebConsole", kind: "process", module: "web",
      home: "overview",
      tagline: "管理控制台前端",
      desc: "浏览器内的管理界面,全部数据经 API 拉取。",
    },
    core: {
      name: "CoreService", kind: "daemon", module: "core",
      home: "overview", drill: "core", big: true,
      tagline: "核心服务 · 决策中枢",
      desc: "常驻服务:认证鉴权、策略判定、任务编排汇聚于此。",
      resp: ["REST API 门面", "策略引擎", "任务编排"],
      files: ["core/cmd/server/main.go"],
      deploy: { 运行态: "systemd 常驻 · 独立账号" },
      notes: ["示例备注:历史包袱与坑写在这里"],
    },
    worker: {
      name: "TaskWorker", kind: "worker", module: "core",
      home: "overview",
      tagline: "异步任务执行",
      desc: "从队列消费任务,水平扩容。",
    },
    db: {
      name: "PostgreSQL", kind: "store", module: "基础设施",
      home: "core",
      tagline: "主存储",
      desc: "业务数据与审计事件。",
    },
    policy: {
      name: "PolicyEngine", kind: "manager", module: "core",
      home: "core",
      tagline: "策略引擎",
      desc: "core 内部的规则匹配单例。",
    },
  },

  relations: [
    { s: "web", t: "core", k: "http", l: "REST API(会话令牌)" },
    { s: "core", t: "auth", k: "http", l: "OIDC 校验" },
    { s: "core", t: "worker", k: "mq", l: "任务派发" },
    { s: "worker", t: "core", k: "rpc", l: "结果回传" },
    { s: "core", t: "db", k: "store", l: "业务数据 / 审计" },
    { s: "policy", t: "db", k: "store", l: "规则版本读取" },
  ],

  views: {
    overview: {
      name: "全景总览", layer: "L1", crumb: ["全景"],
      desc: "系统之系统:运行时、存储与外部世界。",
      canvas: [1600, 900],
      groups: [
        { x: 80, y: 100, w: 300, h: 500, label: "外部世界" },
        { x: 460, y: 100, w: 700, h: 500, label: "运行时" },
        { x: 1240, y: 100, w: 280, h: 500, label: "存储" },
      ],
      nodes: {
        auth:   [230, 250],
        web:    [600, 250],
        core:   [880, 350],
        worker: [880, 520],
        db:     [1380, 350],
      },
      edgeHide: [],
    },
    core: {
      name: "CoreService 内部", layer: "L2", crumb: ["全景", "CoreService"],
      desc: "核心服务内部:策略引擎与持久化。",
      canvas: [1200, 700],
      groups: [],
      nodes: {
        policy: [400, 300],
        db:     [700, 300],
      },
      edgeOnly: ["policy,db"],
    },
  },

  flows: [
    {
      id: "flow-a", name: "示例数据流",
      desc: "请求鉴权到策略执行。",
      lanes: ["web", "core", "db"],
      steps: [
        { s: "web", t: "core", label: "API 请求", d: "携带会话令牌。" },
        { s: "core", t: "db", label: "读规则版本", d: "取当前生效规则。" },
        { s: "core", t: "core", label: "策略判定", d: "进程内自环示例。" },
      ],
    },
  ],

  principles: [
    {
      name: "示例原则", refs: ["core"],
      body: "从代码反向提炼的结构性规律。",
      evi: "core/cmd/server/main.go",
    },
    {
      name: "已知的坑(如实标注)", refs: ["core"], debt: true,
      body: "死代码与历史包袱写在这里。",
      evi: "勘探报告证据",
    },
  ],
};
