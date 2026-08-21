# 本体建模细则

## §1 勘探阶段:子代理指令模板

按「仓库 / 高内聚模块 / 跨边界接口」切分 4–8 个勘探单元,并行派发(thorough 级)。每个子代理零上下文起步,指令必须包含:目标、范围、输出结构、取舍标准。可直接套用的模板:

> 你是一名代码考古学家。目标:为「<产品名>」绘制架构设计大图做前期勘探。
> 你负责的勘探范围是:<路径 + 一句话范围界定,含重点>。
>
> 请做 thorough 级探索,从本体论角度提取「实体」与「关系」,返回结构化报告(提炼后的结论 + 关键文件路径,不要源码 dump):
>
> 一、实体清单(每个一行):名称 | 类型(用领域语言命名:进程/服务/库/存储/协议/产物…不限于此)| 职责一句话 | 关键文件路径。具体到重要的类/服务级别,但不要罗列每个文件。
> 二、关系清单(每条一行):A → B | 关系类型(依赖注入/XPC/HTTP/MQTT/FFI/调用/读写/构建消费…)| 一句话说明。特别要找出跨模块、跨仓库的关系。
> 三、核心数据流:编号步骤描述 2–5 条最重要的运行时数据流。
> 四、部署与形态:进程/权限/bundle id/签名/系统框架依赖。
> 五、值得一提的架构细节:分层惯例、状态机、配置来源、已知坑与死代码。
>
> 先读该目录下的 AGENTS.md / README / 构建清单(package.json/Cargo.toml/go.mod/pom.xml/CMakeLists.txt/Podfile)摸清结构,再深入源码。抓主干、抓接口、抓跨边界调用,忽略 UI 细节与次要工具类。报告 1500–2500 字,信息密度要高。

**报告落盘(≥5 个勘探单元时建议)**:让子代理把报告写入 `designs/<slug>-architecture-atlas/exploration/<单元名>.md`,主代理再逐个 Read——多份 thorough 报告聚合返回会超过单次工具结果上限(约 50K 字符)被截断,落盘既避免截断,也留下可复查的考古记录(可随交付物一并保留)。

勘探单元划分建议:

- 多仓 workspace:每仓 1 个单元;最大的仓按模块再拆,拆法遵循「高内聚聚合」——同类前端模块并一个单元、核心后端/守护单独一个单元、构建与部署体系并一个单元、共享基础库并一个单元。
- 单仓 monolith:按顶层目录 / bounded context 拆;构建与部署体系单独一个单元。
- 跨边界(跨仓依赖、IPC 协议、FFI)要在相关单元的指令里都点到,确保两端说法能对上。

## §2 分型:形态原语(协议)× 语义词表(数据)

> **本体论不是填空,是推理。**模板不预设你的 codebase 里有什么——一个纯库项目
> 没有守护进程,一个编译器项目没有用户进程。种类词表(kinds/relKinds)和实体一样,
> 必须由勘探动态推理得出;引擎只绑定「长什么样」,不绑定「叫什么」。

### 2.1 形态原语 form(协议层,引擎绑定,勿增删)

节点的全部视觉形态只有这 11 种,CSS 绑定在 `Atlas.html` 的 `.node.k-f-<form>`:

| form | 视觉 | 语义暗示 |
|---|---|---|
| black | 黑底白字 | 最高权限/内核毗邻——**全图只给它**,滥用即失真 |
| bold | 白底加粗框 | 服务端、提供 API 的实体 |
| plain | 白底常规框(默认) | 普通进程内实体,不写 form 即此 |
| dashed | 白底虚线框 | 被链接/被加载的库(无独立控制面) |
| dashedgray | 浅灰虚线框 | 被托管的工作者/隔离服务 |
| gray | 浅灰底实线框 | 扩展类实体 |
| ext | 灰底疏虚线框 | 产品边界之外的参与者 |
| store | 白底灰框 | 数据存储 |
| mono | 白底+等宽字体名 | CLI/工具 |
| cicd | 白底灰框 | 流水线 |
| artifact | 极浅灰底 | 构建产物 |

关系线型同理,只有 4 种 style + 1 种修饰:

| style | 语义 |
|---|---|
| solid | 同步/强耦合(调用、RPC、exec、IPC…) |
| dashed | 网络通道(HTTP、WS、MQ…) |
| dotted | 异步广播/人机交互(通知、交互) |
| thin | 构建期/静态依赖(包依赖、读写、构建消费) |

`cls: "k-kernel"` 让 solid 边加粗(特权通道),`k-net`/`k-notify`/`k-build` 是默认词表
自带的修饰类,新增 relKind 沿用即可。

> **形态语义跨主题保真**:11 种 form 的语义(尤其 black=最高权限)是全图契约,不随主题改变——四套主题(light/dark/paper/sepia)只重映射视觉令牌,black 在暗色下反转为最亮节点,语义仍是最高权限。建模时不必为每个主题单独定词表。

### 2.2 kinds 词表(数据层,每项目重推)

模板 `data.js` 里的默认词表(daemon/service/process/lib/kernel…)只是**系统软件
领域的常见起点**,不是协议。建模第一步是推导本项目词表:

1. **剪除**:默认词表里本项目一个实体都对不上的种类,删掉(校验器会对僵尸条目告警)。
2. **改名**:label/desc 用领域语言。比如 Web 应用里 `daemon` 可以改成
   `{ label: "常驻服务", form: "black" }`;形式不变,语义贴合。
3. **新增**:默认词表覆盖不了的种类,直接加条目并选一个 form,例如
   `controller: { label: "控制器", desc: "调和循环(Reconcile)", form: "bold" }`。
   **新增 kind 不需要改引擎**——form 决定它的长相。
4. **检查**:图例由引擎按「实际用到的 kinds」自动生成,词表推导是否正确,截图一眼可见。

领域词表示例(推理方向,不是可抄的答案):

- 系统软件/CLI:daemon、process、cli、lib、kernel、external、store…
- Web 服务:service(bold)、worker(dashedgray)、store、external、lib、cicd、artifact…
- 库/SDK:engine/lib(dashed)、protocol、external、cicd、artifact、tool(mono)…
- 编译器/工具链:pipeline 各阶段(plain/subsystem)、lib、tool、artifact、cicd…

### 2.3 relKinds 词表(数据层,如实命名)

默认 relKinds(call/rpc/http/ws/notify/dep/store…)同样是起点。选 kind 的原则:
**如实命名协议,不抽象**——用了 gRPC 就标 `rpc`,不要泛化为 "http";表里没有就
加新条目(选 4 种 style 之一),而不是塞进近似的旧条目。图例同样按实际使用生成。

## §3 data.js 字段级 schema

```js
const ATLAS = {
  meta: { title, subtitle, mark/*品牌字母,2字符*/, product/*品牌名*/, repos:[], theme?/*light|dark|paper|sepia,默认 light*/ },
  kinds:    { <id>: { label, desc, form? } },     // 见 §2;form 省略即 plain
  relKinds: { <id>: { label, style, cls } },      // style: solid|dashed|dotted|thin
  entities: { <id>: {
    name, kind, module,                            // module 会显示在节点副标题
    home,            // 主归属视图 id(搜索/跳转落点),必须存在于 views
    drill,           // 可选:双击下钻到的视图 id
    big,             // 可选:大节点(核心实体)
    root,            // 可选:非 daemon 的 root 进程,加徽章
    tagline,         // 节点上一句话(≤22 字符,超出截断)
    desc, resp[], files[], deploy{k:v}, notes[],   // 详情抽屉内容,均可选
  }},
  relations: [ { s, t, k, l, note? } ],            // s/t 必须是实体 id;k 必须是 relKinds id
  views: { <id>: {
    name, layer/*"L1".."L4"*/, crumb[],            // crumb 末段 = 自身;前段可点击回跳
    // crumb 元素必须是字符串(如 ["全景", "Srv 内部"])——引擎用字符串做回跳表键,传 {id,label} 对象会渲染成 "[object Object]"
    desc, canvas: [w, h],
    groups: [ { x, y, w, h, label, sub? } ],       // 组框,先定组框再排节点
    nodes: { <实体id>: [cx, cy] },                  // 中心坐标
    edgeOnly: [ "s,t", ... ],                      // 可选:白名单(只画这些)
    edgeHide: [ "s,t", ... ],                      // 可选:黑名单(隐藏这些)
  }},
  flows: [ { id, name, desc,
    lanes: [实体id...],                             // 泳道,按出场顺序
    steps: [ { s, t, label, d } ],                 // s/t 必须在 lanes;s==t 画自环
  }],
  principles: [ { name, body, evi, refs:[实体id], debt? } ],
};
```

**id 字符集(硬约束)**:实体/视图/数据流/kind/relKind 的 id 只允许 `字母/数字/_/-`——视图 id 会进 URL hash(`#/view-id`),实体 id 会以逗号拼进 edgeOnly/edgeHide 的边键,含空格、逗号或中文会直接破坏路由与边寻址(校验器强制执行)。命名建议全小写:`santad-data`、`sync_engine`。

边默认规则:**两个端点都在视图内才画**;`edgeOnly`/`edgeHide` 做减法。同一对 s→t 多条关系会自动扇形展开;A↔B 双向自动两侧偏移。

## §4 建模规则

1. **词表先行**:填充实体之前,先按 §2.2 从勘探报告推导本项目的 kinds/relKinds 词表(剪除/改名/新增),落进 data.js 再填实体——词表来自证据,不来自模板默认值。
2. **证据原则**:每个实体至少一条代码证据进 `files` 或 `desc`;关系只连勘探报告里出现过的。
3. **合并原则**:同类小实体合并为"族"节点(如"插件注册表(约 20 个插件)""中间件链(6 层)"),数量写进 tagline;只有具有独立边界(进程/权限/部署)的实体才单列。
4. **分层原则**:L1 只放系统级参与者(≤20 节点);进程/库归 L2;类/管理器归 L3;每个 L3 实体 `home` 指向所属 L3 视图,`desc` 里说清与上下游的关系。
5. **双向语义**:A→B 是"调用/请求",B→A 是"回调/应答",分开建模,不要合并成无向边。
6. **坑与债**:死代码、历史拼写、版本错位,建为实体 `notes` 或 `principles` 里 `debt: true` 的卡片——它们是大图 credibility 的来源。
