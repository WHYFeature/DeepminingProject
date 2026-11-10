# 学术引用幻觉检测中低成本书目信号的有效性与局限

> 《文献真实性校验与证据对齐》课程项目最终课程论文 · [代码与数据存档](https://github.com/WHYFeature/DeepminingProject) · [复现说明](docs/reproduction.md)

## 目录

- [摘要](#摘要)
- [1 引言](#1-引言)
- [2 问题定义与能力边界](#2-问题定义与能力边界)
- [3 相关工作](#3-相关工作)
- [4 方法与实验设置](#4-方法与实验设置)
- [5 实验结果与分析](#5-实验结果与分析)
- [6 局限性与讨论](#6-局限性与讨论)
- [7 结论](#7-结论)
- [代码与数据可用性](#代码与数据可用性)
- [参考文献](#参考文献)

## 摘要

学术写作中的引用核验包含两个相互联系但不能混同的问题：被引文献是否真实存在且书目信息准确，以及被引内容是否真正支持正文论断。本文复现具有公开代码和数据的 HALLMARK，在无 GPU 的 CPU 环境完成 236 项核心测试与固定 20 条 DOI 可解析性在线样本，并新增三组可重复实验：对 v1.2 的开发集、测试集和压力集共 2,071 条记录做字段与分布审计；在开发集 1,119 条和测试集 831 条上运行八种离线参考线及规则消融；以 100 个固定种子、每种规模 500 次分层重采样和 5,000 次在线结果 bootstrap 评估随机性与小样本不确定性。20 条在线实测得到 Detection Rate 0.1818、F1 0.3077、MCC 0.3015，但只有 30% 样本发起 API 请求，具有明确“解析成功或未找到”证据的有效覆盖仅 20%。全量离线实验显示，DOI 存在性启发式在两个划分上的 F1 为 0.5004 和 0.5673，MCC 却为 -0.0466 和 -0.0258；年份与作者规则零误报，却只能检出约 5% 的幻觉。九组实验图、逐样本预测与运行脚本均收录于随文提交的代码与数据存档，全文据此分析低成本信号的能力边界、覆盖率含义与数据偏差。

**关键词：** 文献真实性；引用幻觉；证据对齐；BibTeX；HALLMARK；可复现研究

## 1 引言

生成式模型降低了学术文本生产成本，也使引用错误更易规模化出现：一条看似规范的参考文献可能完全不存在，也可能只在标题、作者、年份、venue 或 DOI 中存在局部错误；更隐蔽的是文献存在，但正文对其结论方向描述有误。前者属文献实体真实性校验，后者属引用内容与原文证据的语义对齐，两者共享检索基础设施，却有不同的标签、证据与评价协议。

文献真实存在不等于文献支持该论断，“未检索到”也不等于“文献虚构”，故系统须保存来源、版本、查询时间与不确定性。本文以复现与分析为主线，用 HALLMARK 的公开实现建立从数据、预测到统计图的闭环，回答三类问题：两类核验各含哪些技术环节；公开实现在普通 CPU 与受限网络下能否稳定复现；轻量字段核验基线能发现与遗漏哪些错误。

扩展实验增加两个完整公开划分上的八类离线对照、数据构造偏差审计、随机基线重复运行和样本量敏感性分析，其价值在于解释看似不错的分数究竟来自鉴别信号、类别比例还是输出默认值。四个研究问题为：DOI 字段缺失能否成为可靠捷径；不需网络的作者与年份规则能覆盖哪些错误；随机基线在不同类别比例与种子下如何变化、小规模在线子集是否足以排序方法；默认输出 VALID 时标签覆盖、查询覆盖和有效证据覆盖是否一致。实验保持官方标签、冻结基线规则与参考年份，不以测试集结果反向设计新算法。

## 2 问题定义与能力边界

### 文献真实性校验

文献真实性校验的输入可以是 BibTeX 条目、参考文献列表或由解析器抽取的标题、作者、年份、venue、卷期页码和 DOI；输出包含实体是否存在、字段匹配状态、检索来源、检索时间与无法判断的原因。完整系统通常包含引用结构解析、候选实体检索、字段级匹配、冲突诊断和不确定性聚合五步，检索可调用 DOI 注册机构、Crossref、OpenAlex、Semantic Scholar、DBLP 或预印本服务，字段匹配需处理大小写、作者缩写、版本和期刊简称等变体。

本文在 HALLMARK 实验中将 HALLUCINATED 设为正类、VALID 为负类，UNCERTAIN 单独记录于覆盖率与指标。三个边界分别记录：DOI 无法解析不必然表示文献不存在；数据库未返回全文不等于文献虚构；标题相似不代表作者、venue、年份和版本相符。故字段级证据与来源覆盖率和最终标签同样重要。

### 证据对齐与支持关系判断

证据对齐的输入是一个待核验论断、一个被引文献及其摘要或全文，以及可选的候选证据句；输出包含文档级关系标签和句子、段落、表格或图的位置。关系标签可有支持、部分支持、矛盾和证据不足，但复现实验必须优先保留数据集原有标签体系。其流程包含论断规范化、证据检索、候选重排、文档级判断、细粒度定位和置信度校准六个环节。

两者的区别可用一个例子说明：某篇论文确实存在且 DOI 正确，但正文声称“方法在所有数据集上均显著优于基线”，而原文只在一个数据集上报告提升。这条引用在实体层面为真实，在语义层面却只能得到部分支持或证据不足；反过来，主题相似的摘要若来自错误文献，也不能替代原被引文献。因此本文将两个任务分别评价，不把 HALLMARK 的书目 F1 与 SciFact 的证据 F1 直接比较。

### 将检索状态、实体状态与支持状态分别建模

为避免概念混淆，可将一次引用核验记为三元输出 (s_access,s_entity,s_support)：是否获得数据及原因、标识符指向的实体与字段是否一致、原文证据与具体论断之间的支持关系。三项在流水线中有先后依赖却不能互相代替：HTTP 200 属于获取层信号，不足以决定作者字段正确；全文下载失败属于证据范围限制，不直接等价于原文矛盾。

这一拆分对评价的影响十分具体：排除未获取全文的记录后只报准确率，结果可能反映数据库覆盖而非核验能力；把服务失败记作幻觉，误报率会随网络波动上升。本文实验只测量第二项中的少量书目信号，对第一项做状态审计；第三项通过文献调研讨论，实证部分不纳入该层级分数。混淆矩阵对应书目标签，HTTP 与 DOI 分组对应证据获取，二者分母和含义分别给出。

## 3 相关工作

### 证据对齐基准

SciFact 将科学论断与候选摘要组成论断与摘要配对，标注支持、反驳和无信息关系并提供 rationale 句[1]；MultiVerS 用 Longformer 联合编码论断与完整摘要上下文，同时预测文档级标签和 rationale[2]；SciFact-Open 将语料扩展到约五十万篇摘要，用 pooling 标注构造开放域检索评价集，说明候选召回误差会显著影响端到端性能[3]。三者构成句子级评价、联合建模与开放域检索的递进路线，但语料以摘要为主，不能代表完整 PDF 审查。

### 真实性与引用幻觉工作

HALLMARK 把引用幻觉拆分为十四种错误类型和三个难度层级，含 DOI 解析、标题匹配、作者一致性、venue 验证与跨数据库一致性等子测试[4]。CiteAudit 用低成本记忆、DOI 或 URL 先处理简单样本，再将难例交给检索服务或模型[5]；CiteTracer 拆分引用解析、证据收集、字段匹配与 Real/Potential/Hallucinated 判别[6]；RefVerifier 提供阶段性复核包并暴露全文获取率[7]。这类工作更接近真实性核验，但通常依赖外部数据库或网络服务。

### 一般来源归因与引用生成工作

ALCE 关注带引用的答案生成和引用精度、召回[8]；RAGTruth 提供片段级幻觉标注[9]；AttributionBench 研究生成文本能否被给定来源支撑[10]；MiniCheck 以轻量模型判断陈述是否被文档支撑[11]；RefChecker 做基于参考文档的细粒度检测[12]；SemanticCite 组合论断规范化、混合检索、重排与解释性判断[13]。它们为检索器、重排器和细粒度评价提供可迁移思路，但正类、来源类型与评价对象和学术书目真实性并不相同。

### 方法联系与区别

上述工作沿三条轴线展开。证据对齐路线从 SciFact 的句子级标注[1]，经 MultiVerS 的联合编码[2]，扩展到 SciFact-Open 的开放域检索[3]：评价对象从关系标签与证据句变为召回质量与端到端标签，故检索 Recall@k、证据 F1 与标签 F1 必须分别报告；语料以摘要为主，不能据此声称完成全文图表与附录的核验。真实性路线以结构化 BibTeX 条目为单位[4]，错误可分散在标题、作者、年份、venue 与 DOI 等多个字段，字段级子测试的 True、False、None 要求区分“没有 DOI”与“对存在的 DOI 检查失败”。

来源归因路线[8,9,10,11,12]处理生成陈述与给定来源的支撑关系，其指标分母是生成内容或引用关系，而非 BibTeX 条目数量；以 LLM 为评价者、以小模型做支撑判断都需额外确认权重、推理框架与评价协议。CiteCheck[14]与相关综述[15]也提示任务定义先于模型选择。三类工作共享检索与重排模块，但正类定义、证据范围与标签协议不同：本文实证部分聚焦书目真实性，不把书目标签重新解释为支持关系标签，也不把摘要级证据 F1 与书目 F1 直接比较。

**表 1：代表性工作与复现条件比较**

| 工作 | 主要任务与方法 | 数据或规模 | 核心指标 | 开源情况与主要限制 |
|---|---|---|---|---|
| SciFact | 论断—摘要关系与证据句 | 约 1,400 条论断、5,183 篇摘要 | label F1、句子 F1 | 数据和评价公开；摘要级，测试标签部分不可见 |
| MultiVerS | Longformer 完整上下文、多任务、弱监督 | SciFact、CovidFact、HealthVer | abstract F1、sentence F1 | MIT 代码公开；依赖预训练权重与旧版深度学习栈 |
| SciFact-Open | 开放域摘要检索与验证 | 约 50 万篇摘要、279 条 claim | evidence F1、Recall@k | 代码和数据公开；pooling 标注不等于穷尽负例 |
| HALLMARK | BibTeX 引用幻觉与字段核验 | v1.2 dev 1,119 条 | Detection Rate、F1、MCC、ECE | MIT，CPU 友好；完整基线依赖外部服务 |
| CiteAudit | 级联式引用真实性审计 | 生成与真实引用混合集 | F1、成本、覆盖率 | 代码与数据公开；检索 API 和费用影响复现 |
| ALCE / RAGTruth | 生成答案归因与片段幻觉 | ASQA、QAMPARI、ELI5 等 | 引用精度召回、片段 F1 | 可迁移到来源归因；不是专门书目真实性基准 |

## 4 方法与实验设置

### 复现对象选择

本项目选择 HALLMARK 作为主复现对象，依据是其官方实现以 MIT 许可公开，随仓库提供带金标签的公开划分与统一评价器，核心依赖仅为书目解析、HTTP 客户端与字符串相似度库，不依赖 GPU 或大模型权重，因而可在固定数据版本上完成完全离线、可逐样本复核的对照实验。与之相对，以证据对齐为目标的联合编码系统需要预训练权重、特定版本的深度学习框架与较长输入上下文，其资源条件应单独核算；本文将其作为技术路线对照，实证部分聚焦书目真实性模块。该选择同时界定了能力边界：书目字段核验不等价于论断与原文证据的语义支持判断。

### 版本、数据与基线设置

复现对象 HALLMARK 的官方仓库固定版本为
`f774fa40675daa83eca6201637a94c4536b7bb3e`，许可证为 MIT，要求 Python 3.10 以上。核心依赖为 BibTeX parser、HTTP 客户端和字符串相似度库，不依赖 CUDA、torch 或大模型。固定数据为 v1.2 的 `dev_public`，包含 1,119 条记录，其中 VALID 513 条、HALLUCINATED 606 条，覆盖 Tier 1–3 和多种生成方式。数据文件 SHA-256 为 e1d3fd8e66191dae1d9cc4317cec870a99966f4d558a8601ebf533b362ed263a，metadata SHA-256 为 085047b5b4b6911249c4225ae4ef406f9e5872fc281ce483c3fed7e6e8e756da。

在线部分使用官方 DOI-only baseline，离线部分使用两个完整划分上的八条参考线。DOI-only 读取 DOI 并访问 doi.org 及其重定向目标，输出标签、置信度、来源和耗时。离线规则则仅访问书目字段，不发出 HTTP 请求。两类设置都不是完整 HALLMARK headline cascade；将它们分开，能够分别考察服务证据与字段捷径。本文的最小在线闭环回答：*仅使用 DOI 可解析性时，能够识别哪些错误，覆盖率和误报之间呈现怎样的关系？* 全量离线对照回答上述结论是否可能被类别比例和样本规模误导。

### 评价指标与公平性

将 HALLUCINATED 作为正类，报告 Detection Rate、FPR、F1、Macro-F1、MCC、AUROC、AUPRC、ECE、Coverage 和 Tier-weighted F1；MCC 对类别不平衡更稳健，Coverage 说明给出可评分输出的样本比例。所有预测保留 `bibtex_key`、标签、置信度、reason、来源与耗时，评价结果可从逐样本文件重新计算。

在线部分固定为官方命令行按分层规则选出的 20 条样本（`--max-entries 20`），选择不依赖运行结果，用于控制外部请求数量与延迟；离线部分覆盖两个完整公开划分。上游全量参考汇总仅用于核对划分名称、规模与指标字段，不计入本文实测结果。两类设置分开报告，使样本选择规则与证据强度可追溯。

混淆矩阵使用 DR=TP/(TP+FN)、FPR=FP/(FP+TN) 和 F_1=2TP/(2TP+FP+FN)，分母为零时按官方实现返回 0；MCC 为

MCC = (TP×TN − FP×FN) / sqrt((TP+FP)(TP+FN)(TN+FP)(TN+FN))

退化常量预测的 MCC 分母为零，按实现记为 0。置信度表示预测标签正确的概率，并非统一的幻觉概率；ECE 按箱内样本权重聚合置信度与准确率之差，分箱方式必须同时声明。

离线消融冻结参考年份 2026，作者规则检查明显占位和格式异常，规则未命中统一返回 VALID@0.5。随机参考线固定种子 42，稳定性实验另用 0–99 共一百个种子；样本量分析按金标签比例分层有放回抽取、每个规模重复 500 次，在线 bootstrap 固定 11/9 标签构成、重复 5,000 次。百分位区间是条件于当前样本与预测的经验区间，不是独立测试集上的总体保证；所有重采样使用临时唯一 key，确保多次抽中的条目按次数计权。

## 5 实验结果与分析

### 扩展实验矩阵与数据审计

在固定 20 条在线样本之外，本文增加完全离线的全量实验：开发集 1,119 条（606 幻觉、513 有效）、测试集 831 条（519 幻觉、312 有效）、压力集 121 条且全为幻觉。每条记录先移除标签、错误类型、难度与解释字段再传给基线，测试集标签只在预测完成后用于统一评价；扩展脚本不调用网络，随机种子固定为 20261015，并保存每个 split、每种基线的逐样本 JSONL。

审计显示，开发集有效/幻觉样本含 DOI 的比例为 47.0% 和 51.7%，测试集为 44.6% 和 47.2%；标题和作者字段均完整，venue 在开发集缺失 22/61 条、测试集 13/35 条。开发集有 228 个重复标题组、测试集 184 个；跨 split 仅 1 个归一化标题交集和 2 个 DOI 交集。重复组不删除，以免改变官方分布；审计结果与标签预测分开保存，避免把分布统计误当成模型性能。

![图 1](figures/fig01_split_composition.png)

**图 1** HALLMARK v1.2 三个公开划分的数据审计。压力集全部为幻觉样本，因此不适合单独计算真实引用误报率。

扩展矩阵包含恒预测 VALID、恒预测 HALLUCINATED、50% 随机、DOI 存在性、年份边界、作者占位、年份与作者并集、venue oracle 八条线。前三条是统计参考；DOI 存在性用官方函数，无 DOI 输出 HALLUCINATED@0.8、有 DOI 输出 VALID@0.6；年份和作者规则未命中时输出 VALID@0.5；venue oracle 被官方定义为数据集偏差诊断，图表加星号，不视为可部署检测器。所有方法共用官方评价函数，并另以独立 TP/FP/TN/FN 核对。

![图 2](figures/fig02_doi_presence.png)

**图 2** 开发集和测试集按真实标签分组的 DOI 字段存在比例。两类比例接近，字段有无缺乏稳定的鉴别信号。

图 2 中开发集真实引用含 DOI 的比例反而低于幻觉引用，测试集方向相同；按缺 DOI 判幻觉的规则因此同时损失精度和召回。这里测量的是字段存在性，并未访问任何注册机构，更未确认 DOI 对应的实体。

### 全量离线基线与消融

**表 2：全量离线实测结果。DR 为幻觉检出率；FPR 为真实引用误报率。最后一行仅作偏差诊断。**

| 方法 | 开发集 DR | 开发集 FPR | 开发集 F1 | 开发集 MCC | 测试集 DR | 测试集 FPR | 测试集 F1 | 测试集 MCC |
|---|---|---|---|---|---|---|---|---|
| 恒预测真实 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| 恒预测幻觉 | 1.0000 | 1.0000 | 0.7026 | 0.0000 | 1.0000 | 1.0000 | 0.7689 | 0.0000 |
| 随机（seed=42） | 0.4785 | 0.4893 | 0.5057 | -0.0107 | 0.4836 | 0.4904 | 0.5439 | -0.0066 |
| DOI存在性 | 0.4835 | 0.5302 | 0.5004 | -0.0466 | 0.5279 | 0.5545 | 0.5673 | -0.0258 |
| 仅年份 | 0.0495 | 0.0000 | 0.0943 | 0.1527 | 0.0559 | 0.0000 | 0.1058 | 0.1474 |
| 仅作者 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| 年份+作者 | 0.0495 | 0.0000 | 0.0943 | 0.1527 | 0.0559 | 0.0000 | 0.1058 | 0.1474 |
| Venue oracle* | 0.2525 | 0.0097 | 0.4005 | 0.3473 | 0.2697 | 0.0064 | 0.4236 | 0.3388 |

表 2 显示，恒预测 HALLUCINATED 在两个划分上的正类 F1 为 0.7026 与 0.7689，但 FPR 均为 1、MCC 均为 0；恒预测 VALID 的 F1 为 0。类别不均衡会使常量预测获得看似可观的 F1。DOI 存在性规则在开发集检出率 0.4835、FPR 0.5302、F1 0.5004、MCC -0.0466，测试集 0.5279、0.5545、0.5673、MCC -0.0258；MCC 为负说明 DOI 缺失的相关性不足以抵消误报，“有 DOI”也不能代替字段比对。

年份规则在开发集找到 30 条、测试集 29 条未来日期幻觉，无误报，检出率仅 0.0495 和 0.0559；作者规则未命中任何记录，因其只覆盖明显占位符而非比对外部元数据。venue oracle 的 MCC 为 0.3473/0.3388，须解释为数据构造偏差探针，无法代表开放世界的新会议、新期刊与别名处理。

![图 3](figures/fig03_baseline_comparison.png)

**图 3** 两个完整划分上的 F1 与 MCC。常量预测的 F1 与 MCC 分离，venue oracle 仅作偏差诊断。

![图 4](figures/fig04_type_heatmap.png)

**图 4** 开发集不同幻觉类型的离线检出率。规则覆盖集中于窄的、可由局部格式触发的类型。

类型热图表明，年份规则几乎只响应 future date，作者正则未覆盖交换作者和部分作者列表，DOI 存在性会同时标记多个缺 DOI 类型并误报缺 DOI 的有效记录，venue oracle 对 venue 类错误更敏感但其高分来自标签与 venue 分布关联。没有一条离线规则均匀覆盖标题近似、合理伪造、合并引用和版本错配，故应支持多字段、来源绑定与逐项证据输出。

### 随机性与样本量敏感性

![图 5](figures/fig05_random_stability.png)

**图 5** 随机基线在 100 个固定种子下的 F1 分布。测试集正类比例更高，因此同一机制的 F1 中心也更高。

开发集随机基线 100 次运行的 F1 均值为 0.5193、标准差 0.0167，范围 0.4844–0.5590；MCC 均值为 -0.0005、标准差 0.0299。测试集 F1 均值为 0.5544、标准差 0.0174，范围 0.5173–0.6070；MCC 均值为 -0.0020、标准差 0.0342。测试集 F1 更高是类别比例效应，而非随机工具获得额外知识；MCC 接近零才反映其无鉴别能力。

![图 6](figures/fig06_sample_size_uncertainty.png)

**图 6** 固定 DOI 存在性预测在六种分层评价规模下的 500 次重采样 F1。阴影为 95% 百分位区间。

样本量为 20 时，DOI 存在性 F1 的重采样区间为 0.235–0.720；规模 100 时收窄为 0.388–0.604；规模 500 时为 0.451–0.546；模拟全量规模时为 0.468–0.531。区间围绕全量点估计 0.5004，说明二十条子集容易受样本构成影响。重采样保留重复抽样的临时 key，避免把同一条目多次抽中后被字典映射静默去重。

### 环境、版本与代码验证

实验在无 GPU 的 CPU 环境完成，Python 3.12.14，绘图依赖 Matplotlib 3.11.2、NumPy 2.5.4。运行记录保存解释器版本、操作系统、固定官方版本、两个公开划分的 SHA-256 与固定种子；离线扩展不发出网络请求，在线样本沿用 2026 年 10 月 14 日的既有观测。

安装官方核心依赖后，数据加载、模式校验、指标实现、数据完整性与命令行入口相关的 236 项测试全部通过；依赖外部服务的基线测试不计入这一核心通过数。该结果界定了在线范围：在线结论仅对应固定分层子集与当日服务状态，完整在线级联不在本文测量范围内。

### DOI 可解析性在线子集结果

20 条固定分层样本中有 11 条 HALLUCINATED、9 条 VALID。DOI-only 检出 2 条幻觉，Detection Rate 0.1818、FPR 0、F1 0.3077、Macro-F1 0.4872、MCC 0.3015、AUROC 0.5909、AUPRC 0.6359、ECE 0.26、Coverage 1.0、Tier-weighted F1 0.375。平均 API 调用数 0.3；官方汇总的约 3.2 条/秒由样本数除以逐样本计时之和得到，并非端到端吞吐；全程未触发错误回退。20 条逐样本记录与汇总指标均保存在代码与数据存档（`hallmark_doi_smoke.jsonl` 与 `hallmark_doi_smoke.json`）。

**表 3：固定 20 条在线子集的实测结果**

| 样本数 | HALL | VALID | DR | FPR | F1 | MCC | AUROC | Coverage |
|---|---|---|---|---|---|---|---|---|
| 20 | 11 | 9 | 0.1818 | 0.0000 | 0.3077 | 0.3015 | 0.5909 | 1.0000 |

按难度分解，Tier 1 和 Tier 2 在该子集上的 F1 均为 0，Tier 3 F1 为 0.5714。按错误类型分解，唯一的 `arxiv_version_mismatch` 样本被检出，`near_miss_title` 检出 1/2；`partial_author_list`、`plausible_fabrication`、`preprint_as_published` 和 `swapped_authors` 等类型在本次子集上没有被 DOI-only 识别。由于每类样本数很小，不能将这些比例解释成稳定的总体性能，但它们能揭示信号覆盖范围。

![图 7](figures/fig07_smoke_confusion.png)

**图 7** 固定 20 条 DOI-only 样本的混淆矩阵：两条真阳性、九条真阴性、九条假阴性，无假阳性。

![图 8](figures/fig08_smoke_evidence.png)

**图 8** 按 DOI 证据状态分组的正确与错误数量。无 DOI 和 HTTP 202 样本均使用低置信度默认输出。

### 在线证据覆盖、校准与选择性输出

为检查校准结论，对二十条预测随机打乱顺序一百次，保持标签、置信度与样本配对不变：官方等频十箱 ECE 在 0.06–0.46 间变化、均值 0.239，等宽十箱 ECE 恒为 0.06 并与独立计算一致，原因是大量相同置信度记录被按原顺序拆入多个箱。原顺序自适应 ECE 为 0.26，其 bootstrap 区间 0.365–0.520 未包含点估计，暴露小样本、重复置信度与分箱顺序的敏感性；等宽 ECE 的对应区间为 0.025–0.2325，同样偏宽。本文保留原指标并显式报告协议依赖性。

标签 Coverage 为 1.0，但图 8 显示有效证据覆盖仅 20.0%：14 条无 DOI 样本未发起解析，2 条 HTTP 202 不确定，仅 2 条明确 404 和 2 条成功重定向；API 查询覆盖 30.0%。Coverage 只说明程序返回了标签，不说明得到外部证据。官方自适应 ECE 点值 0.26 与独立等宽计算 0.06 的差异来自分箱定义，本文保留两者并以 FPR、证据状态和逐样本 reason 为主要解释依据。

对 20 条在线结果做 5,000 次分层 bootstrap，Detection Rate 的 95% 百分位区间为 0–0.4545，F1 为 0–0.625，MCC 为 0–0.5222；FPR 因 9 条有效样本无误报而保持点估计 0，不能解释为总体 FPR 必然为 0。更稳妥的结论是：在本次服务状态与固定样本上，404/成功解析信号没有误报，但默认 VALID 的 16 条低置信度记录仍是主要漏检来源。

![图 9](figures/fig09_selective_threshold.png)

**图 9** 对 20 条在线样本设置最低置信度后的保留覆盖率与保留集准确率。阈值分析是后验诊断，不是调参后的新模型。

如图 9，阈值 0.5 保留全部 20 条、准确率 55%；0.6 或 0.75 只保留 4 条、准确率 75%，Coverage 降至 20%；0.85 只保留 2 条且准确率降回 50%。高置信度不自动意味着充分证据，选择性预测的收益依赖样本类型，且必须同时报告拒答比例。该图只解释已有输出风险，不改变官方预测。

### 真实样本案例

表 4 的十二个案例覆盖有效引用、标题近似、合理伪造、作者截断、预印本误引、venue 虚构、合并引用、作者交换与版本错配。两个明确 404 的样本被正确标为 HALLUCINATED，但 DOI 可解析而作者被替换的样本仍判 VALID；缺 DOI 的合理伪造等全部落入 VALID 默认值，构成 16 条低置信度漏检。完整标题、解释与耗时见代码与数据存档的 `smoke_actual_cases.csv` 与在线逐样本文件。

**表 4：固定在线子集的十二个真实样本案例**

| Key | 标题（截断） | 真实类型 | 预测 | DOI证据 | 结果解释 |
|---|---|---|---|---|---|
| d28797194fbf | WavBench: Benchmarking Reasoning, Colloquialism, and Paral... | 版本错配 | HALL | 404未找到 | 正确；置信度 0.75 |
| 6ce5917cf1a3 | Detecting Overflow in Compressed Token Representations tow... | 近似标题 | HALL | 404未找到 | 正确；置信度 0.75 |
| f1411ce61763 | Differentiable Stereopsis: Meshes from multiple views usin... | 虚构刊会 | VALID | 状态不确定 | 漏检/误判；置信度 0.50 |
| db228049d7a9 | Communication-efficient Distributed Learning for Large Bat... | 作者截断 | VALID | 无DOI，未检查 | 漏检/误判；置信度 0.50 |
| c0ccffd5b02e | Enhancing Large Language Models with Structured Knowledge ... | 合理伪造 | VALID | 无DOI，未检查 | 漏检/误判；置信度 0.50 |
| aa6d3a6b533d | BR-SNIS: Bias Reduced Self-Normalized Importance Sampling | 预印本误引 | VALID | 无DOI，未检查 | 漏检/误判；置信度 0.50 |
| d453d206147d | The Linear Distance Traveling Tournament Problem Allows an... | 作者交换 | VALID | 成功解析 | 漏检/误判；置信度 0.85 |
| d25471c7f969 | Transformer-based Working Memory for Multiagent Reinforcem... | 合并引用 | VALID | 无DOI，未检查 | 漏检/误判；置信度 0.50 |
| b21fd5158fdc | Object-Aware Distillation Pyramid for Open-Vocabulary Obje... | 有效引用 | VALID | 状态不确定 | 正确；置信度 0.50 |
| fa842b5a03c5 | Aiming towards the minimizers: fast convergence of SGD for... | 有效引用 | VALID | 无DOI，未检查 | 正确；置信度 0.50 |
| ec546fd82e8b | How Faithful is your Synthetic Data? Sample-level Metrics ... | 有效引用 | VALID | 无DOI，未检查 | 正确；置信度 0.50 |
| f58304cfea58 | Empirical or Invariant Risk Minimization? A Sample Complex... | 有效引用 | VALID | 无DOI，未检查 | 正确；置信度 0.50 |

### 案例分析与误差来源

以下十二例均来自固定在线样本，金标签来自公开数据，HTTP 状态与预测来自原始实测记录，BibTeX key 可在代码与数据存档中逐条检索。

- **标题扰动被附带检出（`6ce5917cf1a3`）。** DOI 404 触发 HALLUCINATED@0.75，但证据只是解析失败，未发现把 for 改为 towards 的词语差异；DOI 有效时该错误未必被检出。
- **相同类型漏检（`a7b8e368f9ac`）。** 同属标题近似但无 DOI，输出 VALID@0.5；决定预测的是 DOI 状态而非标题语义，1/2 检出率不能归纳为标题匹配能力。
- **版本错配的偶然命中（`d28797194fbf`）。** arXiv 版本不匹配并含 venue、年份错配，DOI 404 触发正确预测；过程未读取版本历史或比对正式会议目录。
- **venue 虚构且服务不确定（`f1411ce61763`）。** 来源写作虚构期刊，HTTP 202 下预测 VALID@0.5；服务状态不确定与字段核验通过必须分开记录。
- **真实 DOI 与错误作者并存（`d453d206147d`）。** DOI 可解析到真实 AAAI 论文但作者被替换，输出 VALID@0.85，构成高置信度漏检，直接反驳“可解析标识符足以保证整条书目正确”。
- **明确解析的真阴性（`b83bed7600b1`）。** 有效引用 DOI 成功解析，输出 VALID@0.85；与上一例同样的服务成功和置信度可对应正确或错误书目，提高阈值无法替代目标元数据的字段核对。
- **二人作者列表被截断（`db228049d7a9`）。** 两位作者变一位且无 DOI，默认 VALID@0.5；官方作者正则不核对原始作者集合，格式检查与实体字段匹配的证据需求不同。
- **多人作者列表被截断（`f60287fa0074`）。** 四位作者缩减为两位、无 DOI，同样漏检；错误判定遵循数据集完整书目标签，不将一般展示中的 et al. 一概判错。
- **合理伪造通过局部检查（`c0ccffd5b02e`）。** 流畅标题与看似合理的 2026 年元数据、缺 DOI，标为 VALID@0.5；年份未越界、姓名无占位符都不构成真实性证据。
- **真实事件来源的伪造（`ac6ca276f55a`）。** 来自真实事件收集的合理伪造，无 DOI 未检出；只有检索来源、绑定目标实体并核对字段，才能区分它与主题类似的真实研究。
- **预印本误引为会议论文（`aa6d3a6b533d`）。** BR-SNIS 被写作 ICML 发表记录、无 DOI，得 VALID@0.5；本次并未查询 ICML 目录，单字段检查无法判别预印本与正式版本的关系。
- **两个实体的字段拼接（`d25471c7f969`）。** 合并两个真实论文的元数据，缺 DOI 仍预测 VALID@0.5；局部字段各自合理但整体不对应同一文献，需要候选绑定后的联合一致性检查。

这些案例表明，真实性校验应输出字段级证据与不确定性，而非单一二分类标签；对真实文献误报的代价尤其高，故 FPR、MCC、ECE 与覆盖率须与检出率同时报告。

## 6 局限性与讨论

### 复现可行性与外部依赖

“开源代码公开”与“在给定资源条件下可完成原论文全部实验”不是同一命题。证据对齐系统依赖预训练权重、特定版本框架与较长输入上下文，替换依赖版本可能改变模型行为；HALLMARK 依赖轻量并随仓库提供带标签数据，适合在数据审计、核心测试与可离线评价的对照实验上建立闭环。涉及外部数据库或模型服务的实验须记录接口许可、速率限制与调用成本，本文据此把在线部分固定为可复核的分层子集，把全量对照放在离线部分。

### 摘要、全文与实体层级

证据对齐工作须明确报告证据范围。SciFact 与 MultiVerS 主要以摘要为证据主体，定位到摘要句也不能声称完成表格、附录和全文条件的核验；HALLMARK 的 DOI-only 更早停在实体标识符层面。完整流水线应先判断引用实体是否存在，再检索摘要或全文，最后判断具体论断是否被支持；任一阶段受阻时输出状态，而不是把它压缩成 HALLUCINATED 或 REFUTES。

### 结果可信度与限制

20 条在线样本量小、置信区间宽，不能推断 HALLMARK 在全部 1,119 条 dev 上的性能。服务重定向、HTTP 状态与时间变化也会影响输出，故结果应视为指定日期、指定服务条件下的可复核测量；运行记录中的命令、数据校验值、逐样本结果与服务状态构成完整证据链。

### 统计解释、标签偏差与可部署风险

第一，评价指标须和数据生成机制一起解释。主 split 幻觉比例超过 50%，恒预测幻觉因而得到较高正类 F1，MCC 与 FPR 才揭示它没有区分能力；venue oracle 的高 MCC 读取的是基准构造中稳定的 venue 集合，不能转化为生产价值。DOI 存在性 F1 约 0.50 也不表示已验证 DOI 指向的论文：它既把缺 DOI 的有效论文当幻觉，也把有 DOI 但作者或标题错误的记录当真实。把数据分布捷径误解为实体证据，换领域或换年份后会产生性能坍塌。

第二，bootstrap 只能回答与抽样协议相称的问题。分层重采样反映固定样本与预测下的样本级波动，不能消除同源扰动的相关性或代表未来引用分布；二十条在线样本区间很宽。100 个种子的重复用于展示单次运行在类别比例下的自然波动，而非给随机方法一个“最佳分数”。

第三，拒答与低置信度须进入主结果。Coverage=1 只说明每条记录返回 Prediction，但 14/20 条缺 DOI 记录未被外部核验、2/20 条处于 HTTP 202 不确定；把默认 VALID 与明确解析成功的 VALID 混在一起会高估证据强度。选择性阈值虽提高小子集准确率，却牺牲绝大部分覆盖，最高阈值的两条样本仍只有一半正确。

### 工程成本、缓存与可复核性

在线实验的主要成本不是 CPU 算力，而是外部请求延迟、重定向链和服务状态：20 条样本总 API 调用数 6、平均 0.3，完整 1,119 条 cascade 会访问更多来源且策略可能随日期变化。本文把在线逐样本记录作为带时间戳的观测，不作为永久缓存；离线扩展使用固定数据，不随网络状态变化。

九组实验图以 PNG 保存，绘图脚本只从结果文件读取；论文表格与正文关键数值取自同一份汇总 JSON 和统计 CSV，独立计算的混淆矩阵与官方评价函数的 DR、FPR、F1、Macro-F1、MCC 逐项断言核对。运行记录固定官方版本、数据 SHA-256、Python 版本与脚本种子。

## 7 结论

本文围绕文献真实性校验与证据对齐完成调研、复现和扩展分析。实体真实性、字段一致性、证据检索和语义支持关系是不同层次的能力，不能用单一准确率概括。选择 HALLMARK 后，本文在 CPU 环境完成数据审计、236 项核心测试、20 条 DOI 可解析性在线实测，以及两个完整划分上的八条离线基线、100 种子稳定性、500 次重采样和 5,000 次 bootstrap。20 条样本的幻觉检出率 0.1818、F1 0.3077、FPR 0，但有效 DOI 证据覆盖仅 20.0%，不能解释为完整核验能力；全量 DOI 存在性规则 MCC 为负，年份规则零误报但只检出约 5% 幻觉，证明局部字段捷径不能替代字段级实体匹配。

代码、数据版本、逐样本预测、运行记录、图表源文件与九组实验图已打包为单一存档，可通过 [本项目的公开代码与数据存档][repo] 获取，材料构成见下文。实验结果分别报告实体真实性、证据获取和语义支持关系，避免将不同错误来源混合在一个分数中。

## 代码与数据可用性

为支持结果复核，本文提交一份自包含存档：复现脚本与依赖清单；固定的官方实现版本与 v1.2 公开数据（附 SHA-256）；两个公开划分上八条基线的 16 份逐样本预测共 15,600 条及 20 条在线观测记录；汇总 JSON、统计 CSV 与九组实验图；版本、环境、命令与评价协议说明。存档不含机器专属路径，解压后可在任意目录校验完整性并重跑离线实验；离线实验不发出网络请求，在线观测作为带日期的服务状态记录单独保存。存档可通过 [本项目的公开代码与数据存档][repo] 获取，归档压缩包可直接下载：<https://github.com/WHYFeature/DeepminingProject/archive/refs/heads/main.zip>。

## 参考文献

[1] WADDEN D, LIN S, LO K, et al. Fact or Fiction: Verifying Scientific Claims[C/OL]//Proceedings of the 2020 Conference on Empirical Methods in Natural Language Processing. Online: Association for Computational Linguistics, 2020: 7534-7550 [2026-10-15]. https://aclanthology.org/2020.emnlp-main.609/. DOI: 10.18653/v1/2020.emnlp-main.609.

[2] WADDEN D, LO K, WANG L L, et al. MultiVerS: Improving Scientific Claim Verification with Weak Supervision and Full-Document Context[C/OL]//Proceedings of the 2022 Conference of the North American Chapter of the Association for Computational Linguistics: Human Language Technologies. Seattle, United States: Association for Computational Linguistics, 2022: 813-825 [2026-10-15]. https://aclanthology.org/2022.naacl-main.59/. DOI: 10.18653/v1/2022.naacl-main.59.

[3] WADDEN D, LO K, KUEHL B, et al. SciFact-Open: Towards Open-Domain Scientific Claim Verification[J/OL]. arXiv preprint arXiv:2210.13777, 2022 [2026-10-15]. https://arxiv.org/abs/2210.13777.

[4] KIM K, BRENDEL W, REIZINGER P. HALLMARK: How to Diagnose LLM Citation Verifiers and When to Deploy Them[J/OL]. arXiv preprint arXiv:2607.18360, 2026 [2026-10-15]. https://arxiv.org/abs/2607.18360.

[5] SHI K, SUN W, ZHANG Z, et al. CiteAudit: You Cited It, But Did You Read It? A Benchmark for Verifying Scientific References in the LLM Era[J/OL]. arXiv preprint arXiv:2602.23452, 2026 [2026-10-15]. https://arxiv.org/abs/2602.23452.

[6] LI M, LIN Z, MA S. Source or It Did not Happen: A Multi-Agent Framework for Citation Hallucination Detection[J/OL]. arXiv preprint arXiv:2605.08583, 2026 [2026-10-15]. https://arxiv.org/abs/2605.08583.

[7] MOCAN S, ANGERMEIR F, KREITZ M. RefVerifier: Semi-Automated Reference Claim Verification for Scientific Manuscripts[J/OL]. arXiv preprint arXiv:2609.07652, 2026 [2026-10-15]. https://arxiv.org/abs/2609.07652.

[8] GAO T, YEN H, YU J, et al. Enabling Large Language Models to Generate Text with Citations[C/OL]//Proceedings of the 2023 Conference on Empirical Methods in Natural Language Processing. Singapore: Association for Computational Linguistics, 2023: 6465-6488 [2026-10-15]. https://aclanthology.org/2023.emnlp-main.398/. DOI: 10.18653/v1/2023.emnlp-main.398.

[9] NIU C, WU Y, ZHU J, et al. RAGTruth: A Hallucination Corpus for Developing Trustworthy Retrieval-Augmented Language Models[J/OL]. arXiv preprint arXiv:2401.00396, 2024 [2026-10-15]. https://arxiv.org/abs/2401.00396.

[10] LI Y, YUE X, LIAO Z, et al. AttributionBench: How Hard is Automatic Attribution Evaluation?[J/OL]. arXiv preprint arXiv:2402.15089, 2024 [2026-10-15]. https://arxiv.org/abs/2402.15089.

[11] TANG L, LABAN P, DURRETT G. MiniCheck: Efficient Fact-Checking of LLMs on Grounding Documents[C/OL]//Proceedings of the 2024 Conference on Empirical Methods in Natural Language Processing. Association for Computational Linguistics, 2024 [2026-10-15]. https://aclanthology.org/2024.emnlp-main.119/.

[12] HU X, RU D, QIU L, et al. RefChecker: Reference-Based Fine-Grained Hallucination Checker and Benchmark for Large Language Models[J/OL]. arXiv preprint arXiv:2405.14486, 2024 [2026-10-15]. https://arxiv.org/abs/2405.14486.

[13] HAAN S. SemanticCite: Citation Verification with AI-Powered Full-Text Analysis and Evidence-Based Reasoning[J/OL]. arXiv preprint arXiv:2511.16198, 2025 [2026-10-15]. https://arxiv.org/abs/2511.16198.

[14] XU Z, WEI S, HAN Z, et al. CiteCheck: Towards Accurate Citation Faithfulness Detection[J/OL]. arXiv preprint arXiv:2502.10881, 2025 [2026-10-15]. https://arxiv.org/abs/2502.10881.

[15] VLADIKA J, MATTHES F. Scientific Fact-Checking: A Survey of Resources and Approaches[C/OL]//Findings of the Association for Computational Linguistics: ACL 2023. Association for Computational Linguistics, 2023 [2026-10-15]. https://aclanthology.org/2023.findings-acl.387/. DOI: 10.18653/v1/2023.findings-acl.387.

[repo]: https://github.com/WHYFeature/DeepminingProject
