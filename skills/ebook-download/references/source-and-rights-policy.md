# 来源与权利策略

只在统一脚本没有找到可直下副本，或需要评估新来源时读取本文件。

## 自动来源顺序

| 来源 | 自动下载门槛 | 说明 |
| --- | --- | --- |
| Project Gutenberg / Gutendex | `media_type=Text`、`copyright=false`、EPUB 直链 | 美国公版；保留地区提示，不抓取 Gutenberg 人用页面 |
| OAPEN Library | 明确 OA 许可、公开 bitstream、EPUB 优先 | 学术书；PDF 较常见 |
| Open Library / Internet Archive | `ebook_access=public`、`public_scan_b=true`、IA item/file 均不受限 | 拒绝 borrowable、printdisabled、private、encrypted、ACSM |
| Google Books | `FULL_PUBLIC_DOMAIN`、`publicDomain=true`、`restricted!=true`、直下链接 | 需要 API key；结果受访问国家影响 |

自动来源失败后，使用 `web_search` 进行发现，但不得仅凭搜索摘要下载。按以下顺序打开原始页面并核实许可：

1. 出版社或作者官网的 open-access/download 页面。
2. OAPEN、DOAB 和 Thoth 收录的出版社落地页。
3. 大学、研究机构、政府或国家图书馆仓储。
4. Wikisource 等明确公版/开放许可项目。
5. HathiTrust、Open Library、WorldCat 和当地公共/大学图书馆馆藏。

## 可接受证据

至少满足一项，并在结果中保存证据 URL、访问日期和适用地区：

- 页面明确写明 public domain，且适用于用户所在地。
- 页面给出 Creative Commons 或其他允许下载的开放许可。
- 权利人或出版社明确提供完整文件下载。
- 用户明确说明该文件属于自己、已购买、已获授权，且下载不绕过 DRM 或访问控制。

“可在线阅读”“免费预览”“搜索结果里有 EPUB”“能猜出下载 URL”都不是许可证据。DOAB 元数据为 CC0 不代表书本身自动获得 CC0；必须读取单本记录的许可。

## 必须停止的情况

- 付费墙、DRM、ACSM、设备授权、借阅会话或仅限无障碍用户的文件。
- CAPTCHA、Cloudflare/反机器人挑战、登录绕过、会话密钥提取。
- 影子书库、未授权网盘/论坛/社交媒体分享、来源不明镜像。
- 页面许可缺失、互相矛盾，或重定向到与证据无关的域名。

停止自动下载不等于停止任务：继续给出出版社、合法借阅、购买或馆际互借的最短路径。

## 隐私与网络

书名、作者和 ISBN 会出现在 HTTPS 查询中，也可能进入来源、DNS、代理或本地日志。不要把完整查询 URL、API key、Cookie、借阅 token 或用户账号信息写进报告。用户要求离线时，只使用本地目录；批量检索应遵守来源速率限制并缓存结果。

## 一手资料

- Gutendex API 与自建说明：https://github.com/garethbjohnson/gutendex
- Project Gutenberg 机器目录：https://www.gutenberg.org/ebooks/offline_catalogs.html
- Project Gutenberg robot policy：https://www.gutenberg.org/policy/robot_access.html
- OAPEN metadata：https://www.oapen.org/article/metadata
- OAPEN REST search：https://www.oapen.org/article/8185269-search-using-a-rest-api
- Open Library APIs：https://openlibrary.org/developers/api
- Open Library Search API：https://openlibrary.org/dev/docs/api/search
- Open Library 阅读/借阅边界：https://openlibrary.org/help/faq/reading
- Google Books Volumes API：https://developers.google.com/books/docs/v1/reference/volumes
- Standard Ebooks feeds：https://standardebooks.org/feeds
- DOAB API：https://www.doabooks.org/en/article/api-search-doab
