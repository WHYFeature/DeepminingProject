# 学术引用幻觉检测中低成本书目信号的有效性与局限

《文献真实性校验与证据对齐》课程项目最终课程论文的**完整复现仓库**：论文正文、排版版 PDF、复现脚本、官方实现与数据、逐样本预测、九组实验图与运行记录。

> **上传后必做**：全仓库搜索 `OWNER/REPO` 并替换为你的 GitHub 用户名与仓库名（出现在 `README.md`、`paper.md` 末尾的链接定义、`paper_src/course_paper.tex` 的 `\CodeDataURL` 等处）。替换后重新编译 PDF，并把真实可下载链接回填到课程论文。步骤见 [docs/github-upload.md](docs/github-upload.md)。

## 导航

| 我想…… | 打开 |
|---|---|
| 读课程论文（Markdown，九图已内嵌、四表可直接渲染） | [paper.md](paper.md) |
| 看排版版 PDF（20 页） | [paper.pdf](paper.pdf) |
| 校验存档 / 重跑离线实验 | [docs/reproduction.md](docs/reproduction.md) |
| 上传到 GitHub 并回填链接 | [docs/github-upload.md](docs/github-upload.md) |
| 提交前逐条核对 | [docs/submission-checklist.md](docs/submission-checklist.md) |
| 重新编译 LaTeX 源码 | [paper_src/README.md](paper_src/README.md) |

## 研究问题与主要结论

本文区分「被引文献是否真实存在、书目字段是否准确」与「被引内容是否支持正文论断」，以公开实现 HALLMARK 为主复现对象，回答三个问题：低成本书目信号能否可靠检出幻觉、无需联网的字段规则能覆盖哪些错误、随机性与小样本会怎样影响指标排序。

- 固定 20 条 DOI 可解析性在线样本：Detection Rate 0.1818、F1 0.3077、MCC 0.3015；标签覆盖 1.0，但发起外部查询的仅 30%，具明确「解析成功或未找到」证据的仅 20%。
- 两个完整公开划分（开发集 1,119 条、测试集 831 条）上的八条离线参考线：DOI 存在性规则 F1 为 0.5004 / 0.5673，MCC 却为 −0.0466 / −0.0258；恒预测幻觉 F1 达 0.7026 / 0.7689 而 MCC 为 0。单独报告正类 F1 不足以证明鉴别能力。
- 年份规则检出 30 / 29 条未来日期幻觉且零误报，检出率仅 0.0495 / 0.0559；作者格式规则未命中任何记录。
- 100 个固定种子下随机基线 F1 均值为 0.5193 / 0.5544，测试集更高来自类别比例；样本量 20 时 DOI 规则 F1 的 500 次重采样区间为 0.235–0.720。

所有数字均可在 `results/` 内按文件逐样本复核；上游参考汇总仅用于核对划分名称与指标字段，未计入实测结果。

## 快速开始

```bash
git clone https://github.com/OWNER/REPO.git
cd REPO
python -m pip install -r code/requirements.txt
python code/verify_results.py              # 完整性校验：退出码 0 表示数据、预测、图表自洽
python code/run_extended_experiments.py    # 重跑离线实验（会覆盖 results/ 与 figures/ 的同名文件）
```

Python ≥ 3.10（实测 3.12.14）。无需 GPU、无需预训练权重；重跑离线实验不发出网络请求。在线观测是 2026-10-14 的一次带时间戳记录，作为历史证据保存，不重新测量。若控制台出现非 UTF-8 解码问题，设置 `PYTHONUTF8=1`。

## 目录结构

| 路径 | 内容 |
|---|---|
| `paper.md` | 课程论文 Markdown 版（10 章、4 表、9 图、15 条参考文献） |
| `paper.pdf` | 由 `paper_src/course_paper.tex` 编译的 20 页 A4 论文 |
| `paper_src/` | 自包含 LaTeX 源码（含 `.bbl`，可在无参考文献数据库时编译两遍） |
| `code/` | `run_extended_experiments.py`、`verify_results.py`、`requirements.txt` |
| `official/` | HALLMARK 官方 Python 包、`pyproject.toml`、MIT 许可证与固定版本号 |
| `data/` | 官方数据 v1.2（含公开开发集、公开测试集、压力集与官方基线结果） |
| `results/` | 16 份逐样本预测（15,600 条）、20 条在线观测、汇总 JSON、统计 CSV、三份 LaTeX 表格 |
| `figures/` | 九组实验图的矢量 PDF 与 220 dpi PNG（Markdown 与 LaTeX 共用） |
| `docs/` | 复现说明、GitHub 上传指南、提交核对清单 |
| `MANIFEST.sha256` | 全仓文件 SHA-256 校验清单 |

## 版本与许可

- 上游仓库：`https://github.com/rpatrik96/hallmark`，固定版本 `f774fa40675daa83eca6201637a94c4536b7bb3e`（`official/VERSION.txt`）。
- 官方实现按上游 **MIT** 许可原样保留，见 `official/LICENSE`；本仓库新增的脚本、文档与论文见根目录 [LICENSE](LICENSE)。
- 数据版本 v1.2（metadata 1.2.3）；`dev_public.jsonl` SHA-256 为 `e1d3fd8e66191dae1d9cc4317cec870a99966f4d558a8601ebf533b362ed263a`。
- 仓库不含 `.git`、Python 缓存、第三方依赖副本，也不含机器专属路径；全部路径相对于仓库根目录。

引用上游工作：

```bibtex
@article{hallmark2026,
  title   = {HALLMARK: How to Diagnose LLM Citation Verifiers and When to Deploy Them},
  author  = {Kim, K. and Brendel, W. and Reizinger, P.},
  journal = {arXiv preprint arXiv:2607.18360},
  year    = {2026},
  url     = {https://arxiv.org/abs/2607.18360}
}
```

## 实验范围

- 在线部分为公开开发集上由官方固定规则选出的 20 条分层样本；完整在线级联不在本仓库的测量范围内。
- 离线部分覆盖公开开发集与公开测试集上的八条参考线；压力集 121 条仅用于数据构造审计。
- 恒预测、随机与 venue oracle 是统计参考线或数据集偏差探针，不是可部署检测器。
- 未开展课程选做的自主改进任务，论文按「复现与分析」组织。

## 代码与数据可下载链接

GitHub 仓库本身提供可下载归档：

```
https://github.com/OWNER/REPO/archive/refs/heads/main.zip
```

也可以在 Release 中附上 `GitHub仓库_上传包.zip`。若课程助教只接受云盘链接，把同一份 zip 上传云盘并在论文中同时给出两个地址。任务书要求「可下载链接附在最终课程论文中」，因此无论选哪条通道，都需把真实地址回填到 [paper.md](paper.md) 与 [paper_src/course_paper.tex](paper_src/course_paper.tex)。
