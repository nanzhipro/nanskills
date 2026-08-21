# nanskills

> AI 智能体技能合集——可复用的自动化工作流。兼容 Claude Code、Codex CLI、Hermes Agent 等任何支持 SKILL.md 格式的智能体框架。

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Platform: macOS](https://img.shields.io/badge/platform-macOS-lightgrey)]()

---

## ⚠️ 免责声明

**本仓库中的所有技能仅供学习与研究目的使用，严禁用于任何违法违规行为。**

- 本仓库仅为自动化工具脚本，**不包含、不托管、不分发任何受版权保护的内容**。
- 使用者须自行确保其行为符合当地法律法规及服务条款。**因使用本仓库技能所造成的任何损失、纠纷或法律后果，作者概不负责。**
- 本仓库不进行任何形式的 DRM 破解或访问控制绕过。

如您是权利方且认为本仓库中任何内容侵犯了您的权益，请提交 Issue，我们将及时处理。

---

## 技能列表

| 技能 | 版本 | 说明 |
|-------|------|------|
| [`nan-ebook-download`](./skills/nan-ebook-download/SKILL.md) | v6.2.0 | 电子书搜索与下载（EPUB 优先，PDF 兜底）。多源流水线：libgen → Anna's Archive → VK.com → OceanofPDF。支持元数据解析、代理自动探测、流式下载与文件校验。 |
| [`codebase-architecture-atlas`](./skills/codebase-architecture-atlas/SKILL.md) | v1.0.0 | 代码库理解与架构可视化。本体论勘探（实体/关系/数据流/设计原则，证据驱动）→ 四层纵深交互式架构大图（全景 → 模块拓扑 → 模块内部 → 数据流时序），附布局校验、截图验收与单文件离线版。 |

## 命名规范

本仓库技能分为两类：`nan-` 前缀表示本仓库原创技能（如 `nan-ebook-download`）；自上游引入或已独立命名的技能保留原名（如 `codebase-architecture-atlas`）。

## 安装

```bash
npx skills add nanzhipro/nanskills
```

或手动安装单个技能：

```bash
git clone https://github.com/nanzhipro/nanskills.git
cp -r nanskills/skills/<技能名> ~/.agents/skills/
```

## 使用

技能在对话中命中触发条件时自动激活。例如，说"帮我找《思考，快与慢》的电子书"即会自动执行 `nan-ebook-download` 的多源搜索与下载流水线；说"为这个代码库生成一张交互式架构大图"则会触发 `codebase-architecture-atlas` 的勘探 → 建模 → 验证 → 交付流水线。

详细工作流、配置及踩坑记录请参阅各技能的 `SKILL.md`。

## 依赖

各技能的运行依赖不同，详见对应 `SKILL.md`：

- `nan-ebook-download`：Python 3.10+，`cloudscraper`（用于绕过 Cloudflare 防护的下载源）
- `codebase-architecture-atlas`：Node.js 18+（数据与布局校验）、Python 3.9+（本地预览与离线打包）、本机 Chrome（截图验收）

## 许可证

MIT 许可证——详见 [LICENSE](./LICENSE)。
