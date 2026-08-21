---
name: nan-codebase-architecture-atlas
description: 深入理解代码库,从本体论提炼实体与关系,生成交互式架构大图网页(多层下钻、点击组件看详情、时序数据流、设计原则)。当用户要求"理解代码库 / 画架构大图 / 架构可视化 / 系统全景图 / 实体关系本体 / 交互式架构网页 / 架构设计大图"时使用。适配多仓 workspace 或单仓,技术栈不限。
---

# Codebase Architecture Atlas

代码库 → 本体(实体 / 关系 / 数据流 / 设计原则)→ 可下钻的交互式架构网页。

## 交付物

`designs/<slug>-architecture-atlas/`:

- 多文件工程:`<Name> Atlas.html` + `data.js`(本体数据)+ `app.js`(渲染引擎)
- 单文件离线版 HTML:可双击打开、可直接分发
- 四层纵深:L1 全景总览 → L2 模块级拓扑 → L3 模块内部 ×N → L4 数据流时序图;附设计原则页
- 交互:单击组件看详情抽屉(职责/关系/关键文件/部署/备注)、双击下钻、⌘K 全局搜索、平移缩放、URL hash 定位、顶栏主题切换(浅色/深色/纸面/暖黄)

## 三个关键认知

1. **渲染引擎已就绪,不要重写前端**。`assets/template/` 的引擎读取全局 `ATLAS` 对象,你的全部创作是 `data.js`(本体)+ 视图坐标。引擎只绑定「形态原语」(黑底/虚线框/等宽字体等 11 种 form 与 4 种线型),不绑定任何具体种类。
2. **本体靠勘探,不靠想象——包括词表本身**。每个实体/关系必须有代码证据(文件路径、类名、协议名);不确定的写进实体 `notes`,禁止虚构。kinds/relKinds 词表同样要从勘探报告推导:不是每个 codebase 都有守护进程或用户进程,图例按实际用到的种类自动生成。坑与债是最有信息量的本体,如实建模。
3. **布局是设计,不是算法**。手工排布坐标;流水线只走一个方向(左→右或上→下);出现长对角线 = 重排信号。

## 工作流(五阶段,按序执行)

### 0. 主题(可选,生成前定一次)

用户指定了主题(如「用深色主题」)就照办;未指定时可默认 light,或主动问一句偏好。确定的主题写进 `data.js` 的 `meta.theme`(light/dark/paper/sepia),生成的图默认落在该主题;查看者仍可在顶栏切换,或经 URL `?theme=<name>` 指定。主题只重映射视觉令牌,不改变形态语义(见 `references/visual-and-layout.md` §6)。

### 1. 并行勘探

- 按「仓库 / 高内聚模块 / 跨边界接口」切分 4–8 个勘探单元,并行子代理(thorough 级)。最重要的模块单独占一个单元;跨仓/跨进程/跨语言边界(IPC/FFI/协议)必须有人专门负责。切分遵循高内聚聚合,不按目录机械切——monorepo 按 bounded context,巨型仓把核心大脑、执行手脚、入口壳拆开;小仓(单 crate / 单包 / <20 个顶层文件)1–2 个单元即可,不必凑数。按技术栈的切分指南与规模刻度(实体/关系/视图/数据流/原则的预期深度)见 `references/ontology-modeling.md` §1。
- **深度下限(防"浅勘探")**:每个单元指令里写明「实体 ≥15 条、关系 ≥12 条、数据流 ≥3 条」,并强制「六、修正与纠偏」一节——子代理对任务假设的纠正(如"X 实际不是 Y")是最高价值情报,漏掉即失真。
- 每个子代理返回六段式报告:实体清单、关系清单、核心数据流、部署形态、架构细节与坑、修正与纠偏。
- ≥5 个单元时让子代理把报告写入 `designs/<slug>-architecture-atlas/exploration/*.md` 再逐个读取——聚合返回超单次结果上限会被截断,落盘也便于复查。
- **报告以落盘文件为准**:子代理写盘早于批次完成回执,回执可能迟到甚至出现在交付之后。读完 `exploration/*.md` 全量即可建模,不要等回执,也不要因为回执迟到而重做。
- **建模前做事实核对**:对每份报告的「修正与纠偏」条,挑 2–4 个最关键论断在仓库里 grep 验证(双向语义、数据流向、弃用状态),核对结论写进实体 notes 或 principles。
- 指令模板(直接套用):`references/ontology-modeling.md` §1。

### 2. 本体建模

0. **工具链预检(一次,建模前)**:`bash <skill>/scripts/preflight.sh <dir>`——node/python3/PIL/Chrome 缺什么早报,别等截图才发现。顺手 `node validate_atlas_data.js <dir>/data.js` 跑一次模板,确认工具链基线。
1. `cp -r <skill>/assets/template designs/<slug>-architecture-atlas/`(平铺时禁止 `mv` 覆盖同名文件,见硬性规则)。
2. `cp data.js data.js.bak` 留退路,再开始改。
3. **先推词表**:从勘探报告归纳本项目实际存在的实体/关系种类,改写 `data.js` 的 kinds/relKinds——剪除默认词表里对不上的僵尸种类、按领域语言改 label、按需新增 kind(选一个形态 form 即可,不用改引擎)。推导方法:`references/ontology-modeling.md` §2。
4. 再填数据:entities/relations/views/flows/principles 全部由勘探动态推理填充。字段级 schema、建模规则:`references/ontology-modeling.md` §3–4;完整示例(仅学习):`assets/template/data.example.js`。深度对照规模刻度表,达不到下限继续回勘探报告挖。
5. **修正类论断进本体**:读完每份报告,把「修正与纠偏」条里的关键事实 grep 一遍 data.js——没进本体的要么补实体/关系,要么写进相关实体的 notes,禁止建模成旧假设。
6. 铁律:实体必有 `home` 视图;关系两端必须存在;相似小实体合并为"族"节点,宁合勿碎;**id 只允许字母/数字/`_`/`-`**(视图 id 进 URL hash,实体 id 拼进边键)。**id 作对象键一律加引号**——含 `-` 的键(`"exec-server": {...}`)漏引号 = JS 语法错误,validate 报 PARSE FAIL 整文件不可解析;id 优先用 `_` 不用 `-`。

### 3. 视图布局

- 视图数量按规模刻度(见 `references/ontology-modeling.md` §1):小仓 4 视图起,中型 5–6,大仓 7–8。每个 L2 域至少有 1 个 L3 下钻视图(该域实体 ≥8 必拆);数据流时序图按「每条 L2 域 ≥1 条 + 至少 1 条端到端跨域流」配。
- 每视图 ≤22 节点;先画组框(group)再排节点坐标。**首版布局就按 lint 几何模型排**:普通节点 208×70、大节点 250×86;横向中心距 ≥260、纵向 ≥130;lint 判定 = 贝塞尔 t∈[0.1,0.9] 步进 0.04 采样、节点盒内缩 8px 判定命中、标签中点距 <18px 互叠(参数见 `references/visual-and-layout.md` §4 末尾)。按此初排,修正轮次可压到 2–4 轮。
- 规则与视觉语义:`references/visual-and-layout.md`。

### 4. 验证(全绿才可交付)

```bash
node <skill>/scripts/validate_atlas_data.js <dir>/data.js   # 引用完整性,须输出 0 BAD;解析错误带 文件:行号
node <skill>/scripts/lint_atlas_layout.js <dir>/data.js     # 布局几何:重叠/越界/边穿节点/标签互叠/图例死区
bash <skill>/scripts/shoot_atlas.sh <dir> 4311 overview,endpoint,srv   # 逐视图截图(需本机 Chrome)
```

- 先 validate 再 lint 最后截图:lint 能在截图前把大部分几何问题列成清单,把「截图—目检—改坐标」压缩到 1–2 轮;lint 的 WARN 逐条过,确认无安全问题再进截图。
- 端口被别的 server 占用时,shoot 脚本会自动顺延探测空闲端口并打印实际使用的端口——注意看输出里的"提示: 端口 ... 改用 ..."。新起的 server 会记入 `<dir>/.atlas-server.pid`,清理用 `shoot_atlas.sh <dir> --stop`。
- 图例面板遮挡左下角节点时,用 `NOLEGEND=1 bash shoot_atlas.sh ...` 收起图例再截(引擎支持 `#/view?legend=0`)。
- 截图若出现 "Error response / 404":说明端口上的 server 根目录不对;手动确认 `http://localhost:<port>/<dir名>/` 可达后重截。**手动起 server 注意 URL 形态**:`python3 -m http.server <port>` 根目录即当前目录,URL 是 `/Atlas.html`(无目录前缀),与 shoot 脚本的 `/<dir名>/` 前缀不同——先 curl 确认实际路径再截。
- 无视觉环境的 DOM 验证:Chrome `--dump-dom` 必须带 `--virtual-time-budget=12000` 等 JS 执行时间参数,否则返回几百字节空壳(引擎未渲染)。引擎预渲染全部视图到同一 SVG,各视图 dump 大小相同是正常现象——一份 dump 全量 grep 所有视图名 + 关键实体名即可。墨迹覆盖率用 PIL(`pip3 install pillow` 缺则装),正常区间 2–9%。
- 需要精确复查某条边/某坐标时,用 node 探针:`cp data.js /tmp/probe.js && echo "module.exports = ATLAS;" >> /tmp/probe.js` 后 `node -e` require 按 §4 公式手算——**不要用正则剥注释后 eval**(字符串里的 `sessions/*.jsonl` 会被 `/*…*/` 误伤,实测踩坑)。

逐张读图目检:节点重叠 / 孤立节点 / 标签遮挡(含边标签互叠)/ 组框包含错误 / 黑底无字 / 图例死区 → 修复 → 重截。目检清单:`references/visual-and-layout.md` §3。**不允许"应该没问题"**。无视觉模型按 `references/visual-and-layout.md` §5 做等价验证,并在交付说明里声明「未经人眼目检」。

### 5. 交付

```bash
python3 <skill>/scripts/build_standalone.py <dir> "<入口文件名>.html"
rm <dir>/data.example.js          # 模板示例,勿带入交付
```

向用户交代:HTTP 访问 URL、单文件路径、本体统计(实体/关系/数据流数)、已知局限(如长跨组边)。

**源工程是唯一编辑入口**:用户若要求只保留单文件版,先告知「删源后改图需反向解包」;若源已删且单文件版未被手改,可用 `scripts/extract_standalone.py` 还原源工程(往返字节守恒校验,恢复后先 validate 再重建)。

## 硬性规则

- 先勘探后建模——跳过勘探的大图必然失真;勘探报告只要结论与路径,不要源码 dump。
- 词表(kinds/relKinds)是数据不是协议——必须由本项目勘探推导,禁止带着默认词表的僵尸种类交付;形态原语(form/线型)才是协议,新增 kind 选 form,不改引擎。
- `data.js` 每次改动后立即跑 validate;改动前先 `cp data.js data.js.bak`;**不要对数据文件做模糊正则的破坏性替换**——分段重写,或从备份恢复。
- **id 作对象键必须加引号**;实体/视图 id 优先用 `_` 不用 `-`(连字符键漏引号 = validate PARSE FAIL)。
- 建模前跑 `scripts/preflight.sh` 预检工具链——Chrome/PIL 缺失要在建模阶段就发现,不要拖到 shoot 才报。
- 模板目录平铺时(把 `template/` 里的 Atlas.html/app.js/data.js 移到工程根)**禁止 `mv` 覆盖同名文件**——`mv template/data.js .` 会静默覆盖已写好的本体数据;先 `cp` 或确认目标不存在。
- 截图必须逐张目检;发现一处修一处,修完重截同一视图确认。
- 单文件版只由 `build_standalone.py` 生成,生成后不手改;要改就改源文件再重新生成。
- 视觉默认遵循模板内置的 OpenAI 式单色系统(白底、发丝线、黑底=最高权限实体);内置 light/dark/paper/sepia 四主题经 CSS 令牌覆盖,切换不改变形态语义,新增主题只加令牌块不改引擎,也不要引入彩色与渐变。
