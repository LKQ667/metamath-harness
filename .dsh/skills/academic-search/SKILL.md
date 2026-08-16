---
name: academic-search
description: |
  仅手动触发的学术论文搜索与元数据提取 Skill。只有当用户明确点名 `$academic-search`（例如“$academic-search 搜索……”）时才使用；即使用户提出论文搜索、文献综述、引用分析、BibTeX、PDF 或学术数据库相关请求，也禁止自动触发。本 Skill 可处理多学科论文检索、引用关系、开放获取判定和结构化元数据提取。
metadata:
  version: "1.2.0"
---

# academic-search Skill

## 触发规则（必须遵守）

- 本 Skill **仅允许手动触发**。
- 只有用户在当前消息中明确点名 `$academic-search`，才可以加载并执行本 Skill。
- 用户仅提出“搜索论文”“查文献”“做综述”“查引用”“导出 BibTeX”等请求时，**禁止自动加载或自动触发**本 Skill。
- 用户没有明确点名 `$academic-search` 时，应忽略本 Skill，不得以本 Skill 的工作流、脚本或平台矩阵替代普通处理流程。

## 前置检查

在开始前，检查环境就绪状态：

```bash
bash ~/.claude/skills/academic-search/scripts/check-deps.sh
```

- **Node.js 22+**：必需（用于 CDP 浏览器模式）。仅使用 API 平台时可不检查。
- **Chrome remote-debugging**：仅在访问 Google Scholar 或其他需要浏览器自动化的平台时必需。在 Chrome 地址栏打开 `chrome://inspect/#remote-debugging`，勾选 **Allow remote debugging for this browser instance**。
- **curl**：必需，用于 API 调用。

arXiv、Semantic Scholar、PubMed、Papers with Code 等 API 平台无需 Chrome 远程调试即可使用。

**S2 API Key（强烈建议）**：无 Key 时 S2 速率上限极低，单 session 多次调用必触发 429。免费注册即可获得更高配额：https://www.semanticscholar.org/product/api#api-key-form。有 Key 时在请求头加 `x-api-key: {your_key}`。

## 搜索哲学

**明确目标，选对平台，提取结构化数据，完成即止。**

学术搜索不同于通用网页浏览——目标是获取**准确、结构化**的论文元数据，而不是浏览网页内容。

**① 明确检索目标，定义成功标准**：执行前先明确什么算完成了。

- 关键词搜索？精确论文？某作者的全部论文？某 venue 的论文列表？
- 学科是什么？是否需要使用 MeSH、JEL、MSC、ACM CCS 等受控词表？
- 文献类型是什么：期刊论文、会议论文、预印本、系统综述、临床试验、工作论文、专著/章节？
- 需要什么字段：仅标题和引用数 / 完整元数据 / PDF / BibTeX / 代码链接？
- 年份范围？领域限定？返回几篇？
- **成功标准**：用户要的是摘要表（第一遍）还是完整元数据（第二遍）？数量够了吗？字段都有了吗？这是后续所有决策的锚点。

**② 选对平台**：不同需求对应不同平台（见下方矩阵）。API 平台优先，CDP 用于无 API 的平台。

**③ 提取结构化数据，先筛后深**：搜索的时间瓶颈不在"搜"，在"筛"。默认采用两遍策略：

- **第一遍（轻量扫描）**：先拉 20-30 条结果，输出轻量摘要表——标题、作者、年份、venue、引用数、是否有开放 PDF/代码。不拉完整摘要。
- **用户或任务确认核心论文**（引用数高、venue 等级高、与目标最相关的 5-10 篇）后，**第二遍**再深入拉摘要、PDF、BibTeX 等完整信息。

所有结果输出为统一 schema（见 `references/metadata-schema.md`），不要输出原始 HTML 或非结构化文本。多平台结果用 DOI/arXiv ID 去重合并。

**④ 过程校验，用失败信号更新方向**：每一步的结果都是信息，不只是成功或失败的二元信号。

| 失败信号 | 含义 | 方向调整 |
|---------|------|---------|
| API 429 / Rate exceeded | 本次会话消耗超配额，不是暂时波动 | 等待 15s+ 或切换 CDP 模式；不要同一请求重试 |
| Jina/WebFetch 超时 | 该页面对静态抓取不友好 | 改用 curl 直接调 API 或切换 CDP |
| S2 返回结果为空 | query 措辞问题，或该平台无收录 | 换关键词组合，或换 arXiv/PubMed |
| 平台返回"内容不存在" | 未必真的不存在，可能是访问方式问题 | 检查 URL 参数是否完整，换平台验证 |
| 同一方式重试 3 次无改善 | 路径错了，不是还没找到方法 | 重新评估目标，换平台或换访问方式 |

**⑤ 完成判断**：对照①定义的成功标准确认任务完成后停止，不为"更完整"而过度操作。

## 平台选择矩阵

根据任务特征选择最合适的平台和访问方式：

| 需求 | 首选平台 | 访问方式 | 备注 |
|------|---------|---------|------|
| CS/Math/Physics/统计 论文搜索 | **arXiv** | REST API | 完全开放，PDF 直链 |
| 引用数、引用/被引关系 | **Semantic Scholar** | REST API | 免费 Key 可提升速率 |
| 作者主页、全部论文 | **Semantic Scholar** | REST API | /author/{id}/papers |
| 生物医学、生命科学 | **PubMed** | NCBI E-utilities | 完全开放 |
| 跨学科 DOI / 元数据核对 | **Crossref** | REST API | DOI、期刊、出版商、ISSN、参考文献基础信息 |
| 跨学科作者/机构/概念/引用 | **OpenAlex** | REST API | 适合作为 Semantic Scholar 的跨学科补充 |
| 开放获取状态 / OA PDF | **Unpaywall** | REST API | 判断 gold/green/hybrid/closed OA 与合法开放全文 |
| ML 论文 + 代码仓库 | **Papers with Code** | REST API | 无需鉴权 |
| ACM 顶会论文 (SIGKDD/WWW 等) | **ACM DL** | WebFetch + Jina | BibTeX 导出端点可直接访问 |
| IEEE 期刊/会议论文 | **IEEE Xplore** | WebFetch / Jina | 有机构 Key 时用官方 API |
| 广泛引用数 / 全平台覆盖 | **Google Scholar** | **CDP（必须）** | 无 API，反爬严重 |
| 论文是否存在 / 基础元数据 | **Semantic Scholar** | REST API | 支持 DOI / arXiv ID 互查 |
| **中文文献**（期刊/学位论文/会议） | **CNKI（知网）** | **CDP（必须）** | 无公开 API；机构登录后全文可得 |

**API 平台访问方式**：

- **WebSearch**：用于发现论文来源、查找 DOI/作者 ID 等信息入口
- **WebFetch / Jina**：URL 已知时从页面提取，Jina（`r.jina.ai/{url}`）节省 token，适合文章类页面
- **curl**：直接调用结构化 API，返回 JSON/XML
- **CDP**：仅 Google Scholar 必须；其他平台在 API/WebFetch 无效时作为兜底

详细 API 调用模板见 `references/api-cookbook.md`。

## 学科路由

先按用户问题判断学科，再读取对应 `references/disciplines/*.md`。如果用户问题跨学科，优先读取最核心学科的 profile，再用 OpenAlex / Crossref / Unpaywall 做跨学科补全。

| 学科 | 读取文件 | 首选方向 |
|------|----------|----------|
| 计算机 / AI | `references/disciplines/computer-science.md` | arXiv、Semantic Scholar、ACM DL、IEEE、DBLP、Papers with Code |
| 医学 / 生命科学 | `references/disciplines/biomedicine.md` | PubMed、PMC、Europe PMC、ClinicalTrials、bioRxiv、medRxiv |
| 物理 / 数学 | `references/disciplines/physics-math.md` | arXiv categories、NASA ADS、INSPIRE HEP、MSC |
| 化学 / 材料 | `references/disciplines/chemistry-materials.md` | Crossref、OpenAlex、ChemRxiv、ACS、RSC、Springer、Wiley |
| 经济 / 社科 | `references/disciplines/economics-social-science.md` | RePEc、NBER、SSRN、OSF、PsyArXiv、JEL |
| 人文 / 法律 | `references/disciplines/humanities-law.md` | Google Scholar、图书馆目录、JSTOR/Project MUSE/HeinOnline 访问状态 |

学科 profile 决定 query expansion、排序标准、输出字段和全文访问边界。不要把 CCF 或 CS 顶会规则套到非 CS 学科。

## 核心能力

### 关键词搜索

1. 先按“学科路由”读取 discipline profile：CS/ML → arXiv + Semantic Scholar；生医 → PubMed/Europe PMC；跨领域 → OpenAlex + Crossref + Semantic Scholar
2. **扩展 query**：用户自然语言输入往往只是一个切入点，需要主动展开为 2-3 个互补 query 覆盖不同命名习惯：
   - 同义词替换：`agent` → `agentic` / `multi-agent` / `autonomous`
   - 子概念拆分：`time series agent` → `time series LLM agent` + `time series agentic reasoning` + `time series automated analysis`
   - 缩写与全称并用：`TS` / `time series`，`LLM` / `large language model`
   - 学科受控词表：医学用 MeSH，经济用 JEL，数学用 MSC，计算机用 ACM CCS，化学可补 CAS/化合物同义词
   - 不同 query 结果合并去重，覆盖率比单 query 提升 30-50%
3. 构造查询：arXiv 用 `search_query` 字段前缀语法；S2 用 `query` 参数；PubMed 用 `term` 布尔表达式
4. **计划多次 S2 调用时优先用 batch API**（`/paper/batch`）而非多次 search，节省速率配额
5. **第一遍输出轻量摘要表**（必含：标题、年份、venue、引用数、是否有开放 PDF），**不默认拉完整摘要**
6. **意图判断**：用户明确说"只要前 N 篇"或"摘要表即可"时，直接输出第一遍结果，无需等待确认再停下
7. 用户需要第二遍时，再深拉完整元数据

多平台并行查询时，用子 Agent 分治（见"并行分治策略"一节）。

**轻量摘要表输出格式示例**：

| 标题 | 年份 | Venue | 引用数 | PDF |
|------|------|-------|--------|-----|
| Attention Is All You Need | 2017 | NeurIPS [CCF-A] | 120,000+ | ✓ arXiv |
| BERT: Pre-training... | 2019 | NAACL [CCF-B] | 80,000+ | ✓ arXiv |

Venue 等级标注规则：CS 会议参考 `references/venue-rankings.md`（CCF 分级）；非 CS 学科先读取 `references/disciplines/*.md` 和 `references/rankings/*.md`，按该学科的证据等级、文献类型或期刊/来源规则排序。期刊显示 JCR 分区（若可从平台字段获取）时必须标明来源。

### 结果筛选

搜索后用以下维度缩小范围，**优先帮用户筛出值得读的论文，而不是把所有结果都呈现**：

| 筛选维度 | 数据来源 | 说明 |
|---------|---------|------|
| 引用数阈值 | S2 `citationCount` | 经典论文通常引用数高；新兴方向可适当放低阈值 |
| 发表年份 | 所有平台 | 综述类需要覆盖历史；最新进展限定近 2-3 年 |
| Venue 等级 | S2 `venue` + `references/venue-rankings.md` | CS 会议参考 CCF 分级；优先 CCF-A/B |
| 学科证据等级 | discipline profile + ranking reference | 医学、社科、人文等不要套用 CCF；按学科规则排序 |
| 开放 PDF | S2 `externalIds.ArXiv` 存在即可得 | **只要有 ArXiv ID 就标 ✓**，不依赖 openAccessPdf（该字段经常为 null） |
| 代码可用性 | Papers with Code API | ML 论文用 `paperswithcode.com/api/v1/papers/?arxiv_id={id}` 自动补全代码列 |

**排序建议**：面向学术前沿性的综合排序，优先级依次为：

1. **时效性（最高权重）**：近 6 个月内发表的论文标注 `[新]` 并置顶展示，不因引用数低而降权——前沿方向的新论文引用数天然偏低，但代表最新进展
2. **引用数（次要权重）**：同一时间段内按引用数降序，高引用代表社区认可度
3. **学科评价规则（参考项）**：CS 用 CCF/顶会；医学用证据等级和研究类型；社科用期刊/工作论文体系和方法类型；人文允许专著、章节和档案来源优先于引用数。

**实操分组示例**：
- 第一组：近 6 个月论文，按引用数降序（含 `[新]` 标注）
- 第二组：更早论文，按引用数降序，CCF-A/B 同引用数时优先

**筛选后的典型结论格式**：

> 共找到 28 篇，按引用数 + venue 等级筛选后，推荐优先阅读以下 6 篇：[列表]
> 其余 22 篇可按需查阅。

### 精确论文查找

已知 DOI 或 arXiv ID 时，直接用 Semantic Scholar 精确查询：
```bash
# DOI 查询
curl -s "https://api.semanticscholar.org/graph/v1/paper/DOI:{doi}?fields=title,authors,year,abstract,citationCount,openAccessPdf"

# arXiv ID 查询
curl -s "https://api.semanticscholar.org/graph/v1/paper/ARXIV:{arxiv_id}?fields=title,authors,year,abstract,citationCount,openAccessPdf"
```

### 元数据提取

所有提取结果必须转换为 `references/metadata-schema.md` 定义的标准 JSON schema。输出时：

- **单篇**：Markdown 表格格式，字段清晰
- **多篇**：Markdown 列表表格（标题、作者、年份、Venue、引用数、PDF 链接）
- **批量导出**：JSON 数组

### PDF / 全文获取

只获取合法可公开访问的全文。按以下优先级尝试，**每步失败后才进入下一步**，并在结果中记录 `full_text_status`：

1. **arXiv PDF 直链**：`externalIds.ArXiv` 存在时，直接构造 `https://arxiv.org/pdf/{arxiv_id}`（S2 的 `openAccessPdf` 字段经常为 null，但 arXiv PDF 实际可得，不依赖该字段）

2. **Semantic Scholar openAccessPdf**：读取 API 响应 `openAccessPdf.url`，可作 arXiv 之外的 OA 补充

3. **OpenAlex OA 检查**（有 DOI 时必须执行，不可跳过）：
   ```bash
   curl -s "https://api.openalex.org/works?filter=doi:{doi}&select=id,open_access,best_oa_location" \
     -H "User-Agent: academic-search-skill/1.x (mailto:your@email.com)"
   ```
   响应中 `best_oa_location.pdf_url` 非 null 时直接用；`open_access.is_oa=false` 时记录并进入下一步

4. **Unpaywall**（有 DOI 时必须执行）：
   ```bash
   curl -s "https://api.unpaywall.org/v2/{doi}?email=your@email.com"
   ```
   返回 `best_oa_location.url_for_pdf` 字段；`is_oa=false` 时说明出版商无授权 OA 版本

5. **领域专用预印本库**（根据论文领域判断）：
   - 地球科学 / 地质学 / 海洋 / 大气：EarthArXiv `https://eartharxiv.org/repository/search/?q={title_keywords}`
   - 生物医学：Europe PMC `https://europepmc.org/search?query=DOI:{doi}`
   - 物理 / 天文：INSPIRE-HEP `https://inspirehep.net/search?p=doi:{doi}`
   - 心理 / 社科：PsyArXiv / SocArXiv

6. **作者版预印本搜索**（前 5 步全失败时）：
   WebSearch 查 `"{first_author_last_name}" "{paper_title_keywords}" filetype:pdf` 或 `site:researchgate.net`，寻找作者自存档版本

7. **告知用户**：如以上均无法获取，明确说明：
   - 该论文无公开 OA 版本（引用步骤 3/4 的检查结果作为依据）
   - 建议通过机构图书馆、作者邮件索取、或 ILL（馆际互借）获取

**Springer HTML 全文的特殊处理**：若 PDF 路由返回 HTML 而非 PDF 二进制（Content-Type 检查），说明该论文为"HTML 全文"形式（常见于 2024+ online-first 文章）。此时：
- 记录为"HTML 全文可读，无独立 PDF"，不算获取失败
- 返回文章 HTML 页面 URL 供用户在浏览器中阅读

**Cloudflare/403 拦截处理**：Wiley、AGU/Wiley 等出版商对自动请求有强 bot 防护，CDP 浏览器模式也可能被 Cloudflare 拦截。遇到此情况：
- 不要反复重试（会触发更严格封锁）
- 直接跳到步骤 3（OpenAlex）和步骤 4（Unpaywall）检查是否有合法 OA 版本
- 步骤 7 告知用户原因

`full_text_status` 枚举：

| 状态 | 含义 |
|------|------|
| `open_pdf` | 找到可公开访问 PDF |
| `needs_institution` | 论文页可访问，但全文需要机构权限 |
| `no_open_pdf` | 没有发现合法开放全文 |
| `anti_bot_blocked` | 被 Cloudflare、验证码或反爬限制拦截 |
| `html_not_pdf` | PDF 路由返回 HTML 页面而不是 PDF |
| `unknown` | 当前证据不足，无法可靠判断 |

### 开放 PDF 下载与 manifest 导出

Academic-Search 可以下载合法开放访问 PDF，但边界必须清楚：

- 只下载 `full_text_status="open_pdf"` 且存在 `pdf_url` 的论文。
- 不得调用 Sci-Hub、LibGen、shadow library、WebVPN、CARSI、Tor 或 Cloudflare 绕过工具。
- 遇到 `needs_institution`、`no_open_pdf`、`anti_bot_blocked`、`html_not_pdf`、`unknown` 时，不下载，只写入 manifest 并说明原因。
- 批量任务先生成 manifest，再由用户确认是否下载，除非用户明确要求“下载所有开放 PDF”。

推荐流程：

1. 搜索/精确查询论文，生成标准 metadata schema。
2. 通过 arXiv、Semantic Scholar、OpenAlex、Unpaywall、PubMed Central 判断 `full_text_status` 和 `pdf_url`。
3. 调用 `scripts/oa-pdf-download.mjs --input <metadata.json> --manifest <manifest.json>` 生成下载清单。
4. 用户确认后，调用 `scripts/oa-pdf-download.mjs --input <metadata.json> --manifest <manifest.json> --download --out-dir <dir>` 下载开放 PDF。
5. 输出下载结果表：标题、DOI/arXiv ID、状态、本地路径、跳过原因。

CLI 示例：

```bash
node scripts/oa-pdf-download.mjs \
  --input /tmp/academic-search-results.json \
  --manifest /tmp/academic-search-download-manifest.json

node scripts/oa-pdf-download.mjs \
  --input /tmp/academic-search-results.json \
  --manifest /tmp/academic-search-download-manifest.json \
  --download \
  --out-dir /tmp/academic-search-pdfs
```

输出 JSON 计数字段：

```json
{"total":3,"eligible":2,"downloaded":1,"skipped":1,"failed":0,"not_pdf":1}
```

`download_status` 枚举：`not_requested`、`eligible`、`downloaded`、`skipped`、`failed`、`not_pdf`。详细字段定义见 `references/metadata-schema.md`。

分工规则：

- 用户要“找论文 / 筛论文 / 查引用 / 生成开放 PDF 清单” → 使用 Academic-Search。
- 用户要“尽可能下载这些 DOI 的 PDF / 用 WebVPN / 多源下载 / Sci-Hub / LibGen” → 明确说明这超出 Academic-Search 边界，并建议切换 scansci-pdf。

如果用户需要下载非开放获取论文，应建议使用机构图书馆、作者邮件、馆际互借，或切换到 scansci-pdf 这类专门的论文获取工具；Academic-Search 不负责绕过访问限制。

不要尝试访问任何需要绕过付费墙的第三方服务。遇到 Elsevier、Wiley、Springer、ACS、Taylor & Francis、JSTOR 等商业出版平台时，先判定开放获取状态；若需要机构访问，停止自动下载并报告 `needs_institution`。

### BibTeX 导出

优先级：

1. **arXiv**：`https://arxiv.org/bibtex/{arxiv_id}` 直接获取
2. **ACM DL**：先试 `https://dl.acm.org/action/exportCitation?doi={encoded_doi}&format=bibtex`；若返回 challenge/HTML 错页，回退 CDP
3. **Semantic Scholar**：无直接端点，根据 `references/metadata-schema.md` 的模板从字段拼装
4. **其他平台**：CDP 点击页面上的 "Export Citation" / "Cite" 按钮

### 作者主页解析

```bash
# Semantic Scholar 作者搜索
curl -s "https://api.semanticscholar.org/graph/v1/author/search?query={author_name}&fields=name,affiliations,paperCount,citationCount"

# 获取作者全部论文（分页）
curl -s "https://api.semanticscholar.org/graph/v1/author/{author_id}/papers?fields=title,year,citationCount,externalIds&limit=100&offset=0"
```

Google Scholar 作者页需 CDP，见 `references/site-patterns/scholar.google.com.md`。

## CDP 模式（Google Scholar 及其他需要浏览器自动化的平台）

通过 CDP Proxy 直连用户日常 Chrome，天然携带登录态。

所有操作在自己创建的后台 tab 中进行，不干扰用户已有 tab，完成后关闭。

### 启动

```bash
bash ~/.claude/skills/academic-search/scripts/check-deps.sh
```

脚本自动检查并启动 CDP Proxy（默认 `127.0.0.1:3456`，可通过 `CDP_PROXY_PORT` 覆盖）。

### 操作方式

进入浏览器层后，用 HTTP API 操控页面：

```bash
# 创建新 tab，导航到目标页
TARGET=$(curl -s "http://127.0.0.1:${CDP_PROXY_PORT:-3456}/new?url=https://scholar.google.com" | node -p "JSON.parse(require('fs').readFileSync(0, 'utf8')).targetId")

# 执行 JS 提取数据
curl -s -X POST "http://127.0.0.1:${CDP_PROXY_PORT:-3456}/eval?target=$TARGET" -d 'document.title'

# 点击元素（CSS 选择器）
curl -s -X POST "http://127.0.0.1:${CDP_PROXY_PORT:-3456}/click?target=$TARGET" -d 'button[type=submit]'

# 完成后关闭 tab
curl -s "http://127.0.0.1:${CDP_PROXY_PORT:-3456}/close?target=$TARGET"
```

完整 API 参考见 `references/cdp-api.md`。

**三种点击方式**：

| 方式 | 端点 | 适用场景 |
|------|------|---------|
| JS click | `/click` | 通用，速度快 |
| 真实鼠标 | `/clickAt` | 需要触发文件对话框或绕过反自动化检测 |
| 文件上传 | `/setFiles` | 直接设置 file input，绕过对话框 |

**先了解页面结构，再决定动作**：用 `/eval document.body.innerText.slice(0, 500)` 或截图快速了解当前页面状态。

## 并行分治策略

任务包含多个**独立**目标时（如同时查询 N 篇论文、N 个来源），分发子 Agent 并行执行。

**好处**：速度 = 单子任务时长；抓取内容不进入主 Agent context，节省 token。

**子 Agent Prompt 写法**：
- 必须写：`必须加载 academic-search skill 并遵循指引`
- 描述**目标**（获取/提取/查找），不要指定具体步骤
- 说明需要哪些字段（标题/引用数/PDF 等）
- **注意用词**：「搜索 BERT 的引用数」会把子 Agent 锚定到 WebSearch；应写「获取 BERT 的引用数」——描述目标，不暗示手段

**典型分治场景**：

| 适合分治 | 不适合分治 |
|---------|-----------|
| 多平台并发查同一论文（arXiv + S2 + PubMed） | 查询有依赖关系（先搜索再按结果查详情） |
| 批量查询 N 篇不相关论文 | 简单单平台单次 API 查询 |
| 多个作者主页并行抓取 | 几次 curl 就能完成的轻量任务 |

**多平台并发查同一论文时的去重**：

子 Agent 返回结果后，主 Agent 按 `references/metadata-schema.md` 中的去重规则合并：DOI 为主键 → arXiv ID 次之 → 标题+年份模糊匹配。

## 信息核实

学术搜索的一手来源是**论文本身**和**平台官方 API**，不是二手报道。

| 核实目标 | 一手来源 |
|---------|---------|
| 论文元数据（标题、作者、DOI）| 发表平台（ACM DL / IEEE / arXiv）官方页面、Crossref、OpenAlex |
| 引用数 | Google Scholar（最全）> Semantic Scholar |
| 开放获取状态 | Unpaywall > 出版商页面 > 仓储页面 |
| 代码实现 | Papers with Code / 论文官方 GitHub |
| 会议/期刊信息 | 主办方官网 |

多平台引用数不一致时正常——不同平台收录范围不同，Google Scholar 通常最高。

## 站点经验

操作中积累的特定网站经验，按域名存储在 `references/site-patterns/` 下。

已预置经验的平台：arXiv、Semantic Scholar、Google Scholar、ACM DL、IEEE Xplore、PubMed、Papers with Code、CNKI（知网），以及 ScienceDirect、Wiley、Springer、ACS 等主要出版商访问限制。

确定目标平台后，**必须**读取对应文件获取先验知识（平台特征、有效模式、已知陷阱）。经验内容标注发现日期，当作**可能有效的提示，不是保证正确的事实**——按经验操作失败时，回退通用模式，并**更新经验文件**（记录失败原因和发现日期）。操作成功后若发现了新模式或陷阱，同样主动写入。

## References 索引

| 文件 | 何时加载 |
|------|---------|
| `references/api-cookbook.md` | 需要 API 调用示例、参数说明、响应字段映射时 |
| `references/metadata-schema.md` | 整理提取结果、多平台去重合并、生成 BibTeX 时 |
| `references/cdp-api.md` | 需要 CDP 浏览器操作时（Google Scholar、CNKI 等） |
| `references/disciplines/*.md` | 需要按学科选择平台、扩展 query、排序和输出字段时 |
| `references/rankings/*.md` | 需要非 CS 学科证据等级或来源评价规则时 |
| `references/workflows/*.md` | 需要执行系统综述、核心论文清单、快速综述等研究工作流时 |
| `references/venue-rankings.md` | 标注 CS 会议/期刊等级（CCF 分级）时 |
| `references/site-patterns/{domain}.md` | 确定目标平台后，读取对应站点经验 |
| `references/site-patterns/cnki.net.md` | 知网检索时必读：登录态要求、DOM 选择器、数据库代码 |
