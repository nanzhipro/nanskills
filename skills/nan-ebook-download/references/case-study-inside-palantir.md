# Case Study: “Inside Palantir” 错误书名恢复

- 测试日期：2026-07-09
- 测试版本：`ebook-search-and-download` v5.0.0；修正后的流程进入 v5.1.0

## 挑战

用户请求的书名是：

> *Inside Palantir: How a Secretive Tech Titan is Shaping the Future of AI,
> Warfare, and Global Data*

这个标题在主书源和 Open Library 中均不存在。实际对应的书是 Michael Steinberger
于 2025 年出版的 *The Philosopher in the Valley: Alex Karp, Palantir, and the Rise
of the Surveillance State*，ISBN-13 为 `9781668012956`。

因此，原始标题检索失败并不意味着目标书不存在；问题出在用户提供的是错误或营销化标题。

## 实测路径

| 查询 | 结果 | 耗时 |
| --- | --- | ---: |
| `Inside Palantir Titan AI Warfare Global Data` | 0 个候选 | 3.51 秒 |
| `Inside Palantir` | 0 个候选 | 2.62 秒 |
| `Palantir Secretive Tech Titan` | 0 个候选 | 1.95 秒 |
| `Palantir Steinberger` | 2 个候选 | 0.74 秒 |
| `Philosopher Valley Steinberger` | 下载并验证成功 | 6.19 秒 |

最终得到 1,154,427 字节的英文 EPUB，共 39 个 ZIP 条目。文件内 OPF 元数据确认了
正式书名与作者，ISBN 身份则通过 Open Library 接口复核。

完整的“元数据解析 → 精确检索 → 下载 → 验证”流程约耗时 15 秒。对正常书名的
回归测试中，搜索 *Storyworthy* 用时 3.06 秒，搜索 *Atomic Habits* 用时 2.49 秒。

以上数据来自特定日期和网络环境，只用于解释设计依据，不构成持续性能承诺。

## 暴露出的设计缺陷

早期实现会把查询逐步退化到单个最长词。测试中，`Secretive` 返回了 100 个无关候选，
并触发一个 35 MB 错误文件的下载，最终超时。

这证明单纯扩大文本召回率会破坏书目检索精度：脚本无法仅靠离线关键词规则可靠判断
错误标题真正对应哪本书。

## 固化的修正

1. 将脚本的查询梯度限制为“完整查询 → 去停用词查询”，不再退化到单个通用词。
2. 使用 `resolve_metadata.py` 从 Open Library 和豆瓣获取正式书名、作者与 ISBN 候选。
3. 由智能体结合主题、人物、年份和作者进行语义消歧，再生成精确查询。
4. 使用 Open Library ISBN 接口确认身份，避免依赖容易触发验证码的通用搜索引擎。
5. 将 `<50 KB` 文件视为高风险存根，并保持 `epub > azw3 > mobi > fb2 > pdf > djvu`
   的默认格式顺序。

## 可复用结论

- 零搜索结果首先应触发书目身份恢复，而不是立即切换下载站点。
- 非英语译名、营销标题和记忆中的近似标题都应视为不可信输入。
- 确定性脚本负责执行与验证，语义模型负责书目消歧；两者不应互相替代。
- 只有文件结构与书内元数据验证通过，才能把任务报告为成功。
