# 复现说明与运行记录

本文件是课程论文配套仓库的实验记录，说明版本、环境、命令、评价协议、结果文件与结论适用范围。所有引用的数字都可在 `results/` 内按文件复核。

## 1. 复现对象与版本

| 项目 | 记录 |
|---|---|
| 论文 | HALLMARK: How to Diagnose LLM Citation Verifiers and When to Deploy Them（2026） |
| 官方仓库 | `https://github.com/rpatrik96/hallmark` |
| 固定 commit | `f774fa40675daa83eca6201637a94c4536b7bb3e` |
| 许可证 | MIT |
| 数据版本 | v1.2，metadata 1.2.3 |
| Python 要求 | ≥ 3.10；实测 3.12.14 |
| 核心依赖 | bibtexparser 2.1.0、requests 2.34.2、httpx 0.28.1、rapidfuzz 3.14.6 |
| 绘图依赖 | Matplotlib 3.11.2、NumPy 2.5.4、Pillow 12.3.0 |
| 硬件 | 无 GPU 的 CPU 环境 |

数据校验值：`dev_public.jsonl` 为 `e1d3fd8e66191dae1d9cc4317cec870a99966f4d558a8601ebf533b362ed263a`，`metadata.json` 为 `085047b5b4b6911249c4225ae4ef406f9e5872fc281ce483c3fed7e6e8e756da`。公开开发集 1,119 条（VALID 513、HALLUCINATED 606），公开测试集 831 条（VALID 312、HALLUCINATED 519），压力集 121 条且全部为幻觉样本。

## 2. 实验矩阵

| 实验 | 设置 | 主要输出 |
|---|---|---|
| 数据审计 | 三个公开划分共 2,071 条，统计字段完整度、DOI 比例、重复标题与跨划分交集 | `extended_summary.json`、`fig01_*`、`fig02_*` |
| 全量离线对照 | dev/test × 八条基线，共 15,600 条逐样本预测 | `predictions/*.jsonl`、`extended_summary.json`、`fig03_*`、`fig04_*` |
| 随机稳定性 | 两划分各 100 个固定种子（0–99） | `random_100_seeds.csv`、`fig05_*` |
| 样本量敏感性 | 规模 20/50/100/200/500/1119，各 500 次分层有放回抽样 | `sampling_uncertainty.csv`、`fig06_*` |
| 在线结果不确定性 | 固定 20 条结果的 5,000 次分层 bootstrap | `extended_summary.json` |
| 校准顺序敏感性 | 同一组预测随机排列 100 次，比较等频/等宽 ECE | `ece_order_sensitivity.csv` |
| 选择性输出 | 最低置信度阈值 0.50/0.60/0.75/0.85/0.90 | `smoke_threshold_analysis.csv`、`fig09_*` |
| 真实案例 | 20 条在线样本的完整标题、标签、预测、原因与服务状态；论文取其中 12 例 | `smoke_actual_cases.csv` |

八条参考线：恒预测 VALID、恒预测 HALLUCINATED、随机（seed 42）、DOI 存在性、年份边界、作者格式、年份与作者并集、venue oracle。最后一条是官方源码明确标注的数据构造偏差探针，不是可部署检测器。年份与作者规则直接调用官方局部检查函数，参考年份固定 2026，规则未命中统一输出 VALID@0.5；它们不是完整 prescreen/cascade。所有预测送出前先移除标签、错误类型、难度与解释字段。

## 3. 评价协议

正类为 HALLUCINATED，报告 Detection Rate（幻觉检出率）、FPR（真实引用误报率）、正类 F1、Macro-F1、MCC、AUROC、AUPRC、ECE、Coverage 与 Tier-weighted F1。每条基线同时调用官方评价函数与独立 TP/FP/TN/FN 计算，并对 DR、FPR、F1、Macro-F1、MCC 逐项断言一致；等宽 ECE 另与官方 `adaptive=False` 交叉核对；同时检查预测数量与 `bibtex_key` 唯一性。完整脚本退出码为 0，断言全部通过。

固定随机种子 20261015；重采样时给多次抽中的条目分配临时唯一 key，保证按抽中次数计权。百分位区间是条件于当前样本与预测的经验区间，不是独立测试集上的总体保证。

## 4. 在线观测

固定 20 条分层样本（11 条 HALLUCINATED、9 条 VALID）由官方 CLI 的 `--max-entries 20` 规则选取，使用 DOI-only 基线，读取 DOI 并访问 doi.org 及其重定向目标，输出标签、置信度、来源、API 调用数与耗时。观测日期 2026-10-14，逐样本记录含服务状态。

实测：Detection Rate 0.1818、FPR 0、hallucination F1 0.3077、Macro-F1 0.4872、MCC 0.3015、AUROC 0.5909、AUPRC 0.6359、ECE 0.26、Coverage 1.0、Tier-weighted F1 0.375；平均 API 调用数 0.3。标签 Coverage 为 1.0，但发起 API 查询的比例为 30%，其中具备明确「解析成功或未找到」证据的样本仅占 20%。官方汇总中的约 3.2 条/秒为样本数除以逐样本计时之和，不是含加载、评价与写盘的端到端吞吐。

## 5. 主要结果

- DOI 存在性规则在开发集/测试集的 F1 为 0.5004/0.5673，MCC 为 -0.0466/-0.0258；恒预测幻觉的 F1 达 0.7026/0.7689 但 MCC 为 0。单独报告正类 F1 不足以证明鉴别能力。
- 年份边界规则在开发集/测试集检出 30/29 条未来日期幻觉，无有效引用误报，检出率仅 0.0495/0.0559；作者格式规则未命中任何记录。
- 随机基线 100 次运行，开发集 F1 均值 0.5193（标准差 0.0167），测试集 0.5544（标准差 0.0174）；MCC 均值分别约 -0.0005 与 -0.0020。测试集 F1 更高来自类别比例，而非额外鉴别能力。
- 样本量 20 时 DOI 存在性 F1 的 500 次重采样区间为 0.235–0.720，规模 500 时收窄为 0.451–0.546。
- 等频十箱 ECE 在 100 次排列中于 0.06–0.46 间变化，等宽十箱固定为 0.06；ECE 必须连同分箱协议一起报告。
- 5,000 次 bootstrap 下 Detection Rate 的 95% 区间为 0–0.4545，F1 为 0–0.625，MCC 为 0–0.5222。

## 6. 结果范围与结论边界

- 在线结果属于固定 20 条分层样本、指定日期与指定服务状态下的一次可复核测量，不能外推为完整 1,119 条 dev 或原论文 headline cascade 的性能。
- 离线扩展覆盖两个完整公开划分，用于检验「分数是否来自类别比例、默认值或数据构造偏差」，不依赖网络。
- `hallmark_official_doi_dev_reference.json` 是上游发布的全量参考汇总，只用于核对划分名称与指标字段，未混入本仓库的实测结果与统计计算。
- 分层 bootstrap 固定标签比例，不反映标签比例本身的变化，也未处理同源扰动的组内相关性。
- 九组实验图以 220 dpi PNG 保存；绘图脚本只从 JSONL/JSON/CSV 读取结果，不在绘图阶段写入预测。论文表格与正文关键数值取自同一份汇总 JSON 和统计 CSV，避免手抄数字。
- 未开展选做的自主改进任务，论文按「复现与分析」组织。

## 7. 复现步骤

见仓库根目录 `README.md`：安装依赖 → `python code/verify_results.py` 校验 → `python code/run_extended_experiments.py` 重跑离线实验。所有路径均相对于仓库根目录。
