# 上传 GitHub 与回填链接指南

本目录（`提交材料_GitHub/`）解压后即为仓库根目录 `citation-hallmark-repro/`，可直接 `git init` 推送。全程不需要改动 `code/`、`data/`、`results/`、`figures/`、`official/`。

## 0. 先看清任务书的字面要求

任务书第七节原文要求「代码和数据打包上传云盘，将可下载链接附在最终课程论文中」，并把「代码：作为可下载链接，放在以上飞书文档中」列入最终提交包。GitHub 的源码归档与 Release 附件提供等价的匿名可下载链接；**如果助教严格只认云盘**，按第 6 节做双通道，两个链接都给，不会丢分。

## 1. 上传前：替换占位符

全仓库搜索 `OWNER/REPO`，替换为你的 GitHub 用户名与仓库名。已知位置：

| 文件 | 位置 | 作用 |
|---|---|---|
| `README.md` | `git clone` 示例、归档下载地址 | 主页可复制的命令 |
| `paper.md` | 文件末尾 `[repo]: https://github.com/OWNER/REPO` | 论文「结论」与「代码与数据可用性」两处链接 |
| `paper_src/course_paper.tex` | 导言区 `\newcommand{\CodeDataURL}{...}` | PDF 中的可点击链接 |

替换后按 [paper_src/README.md](../paper_src/README.md) 重新编译，覆盖根目录 `paper.pdf`。若仓库名尚未确定，可以先上传再回填，但**提交课程论文之前必须完成**，否则论文里是无效链接。

## 2. 本地检查

在仓库根目录执行：

```bash
# 完整性校验（退出码 0 表示数据、逐样本预测、图表自洽）
python code/verify_results.py

# 文件哈希清单（Git Bash / Linux / macOS）
sha256sum -c MANIFEST.sha256

# 确认没有超大文件（本仓库最大约 1 MB，无需 Git LFS）
find . -type f -size +50M -print

# 下面引号内是待检查的模式（不是仓库内容），用于确认没有机器专属路径
grep -rIn -E "C:/Users|/tmp/|task2/|output/pdf|\.deps|before_expansion" code data results figures official docs/reproduction.md || echo "无命中"
```

再确认：目录里没有嵌套的 `.git`、没有 `__pycache__`、没有 `course_paper.aux/.log` 等 LaTeX 中间文件（`.gitignore` 已排除）。

## 3. 创建仓库并推送

命令行方式（Git Bash / 终端）：

```bash
cd citation-hallmark-repro
git init
git add .
git commit -m "Add course paper and reproducible HALLMARK experiments"
git branch -M main
git remote add origin https://github.com/<USER>/<REPO>.git
git push -u origin main
```

首次使用需先配置 `git config --global user.name "..."` 与 `user.email "..."`。也可以用 GitHub Desktop 或网页端「Add file → Upload files」，此时上传的是**仓库根目录里的文件**，不是外层的 `GitHub仓库_上传包.zip`。

推送后在网页端：设为 **Public**、填写简介与 topic（如 `citation-verification`、`reproducibility`、`hallmark`），并打开 `paper.md` 检查九张图是否显示、四张表是否变形、目录锚点与 15 条参考文献是否正常。

## 4. 生成稳定的可下载链接

三种任选（推荐第 2 或第 3 种，它们是真正的文件下载链接）：

| 形式 | 地址 | 说明 |
|---|---|---|
| 仓库主页 | `https://github.com/<USER>/<REPO>` | 直观，但不是直接下载 |
| 源码归档 | `https://github.com/<USER>/<REPO>/archive/refs/heads/main.zip` | 一键下载全部代码与数据，随分支更新 |
| Release 附件 | `https://github.com/<USER>/<REPO>/releases/download/v1.0/<附件名>.zip` | 打 tag 并上传 `GitHub仓库_上传包.zip`，地址固定、便于归档 |

用**无痕窗口**（未登录 GitHub）打开链接验证可以下载，再把地址回填到：

1. `paper.md` 末尾的 `[repo]:` 定义（改一处，正文两处自动生效）；
2. `paper_src/course_paper.tex` 的 `\CodeDataURL` 并重新编译 PDF；
3. 金山文档中粘贴的论文正文「结论」与「代码与数据可用性」两处。

URL 中含 `%`、`#`、`&` 时，LaTeX 里要写成 `\%`、`\#`、`\&`；GitHub 的 URL 一般不含这些字符。

## 5. 提交课程论文（任务书要求）

- 把论文正文粘贴到金山文档 <https://www.kdocs.cn/l/cdI5MClxriQ7> 的「最终课程论文」位置，**不是**上传附件。
- 在线文档通常不解析 `![](figures/xxx.png)`，需按【图 1】–【图 9】手动插图；图片在仓库 `figures/*.png`。若改用带图占位提示的粘贴版正文，按其中的编号提示插图即可。
- 四张表用 Markdown 表格粘贴或转成在线表格，粘贴后检查列数。
- 文档分享权限设为「互联网上获得链接的人，可阅读」，复制文档链接。
- 最终截止：2026 年 12 月 31 日。

## 6. 双通道（同时满足「云盘」字面要求）

把仓库的打包 zip 上传到云盘，权限设为「互联网上获得链接的人，可阅读/可下载」，复制可下载链接；论文里写成「代码与数据：GitHub 归档链接 / 云盘链接」，两者内容完全一致（同一份 SHA-256 清单可核对）。这样既保留 GitHub 的可复现性，也不与任务书字面表述冲突。

## 常见问题

- **需要 Git LFS 吗？** 不需要。全仓约 16 MB、最大单文件约 1 MB，远低于 GitHub 的 100 MB 单文件上限。
- **中文文件名会有问题吗？** 仓库内路径已全部改为 ASCII（`docs/reproduction.md`、`paper_src/README.md` 等）；仅 `data/` 里有一个上游数据文件名含空格，Git 与 GitHub 均可正常处理。
- **`paper.md` 图片不显示？** 确认 `figures/*.png` 一并推送，且图片路径为相对路径 `figures/fig01_split_composition.png`。
- **重跑实验后论文表格对不上？** `code/run_extended_experiments.py` 更新 `results/` 与 `figures/`；把 `results/` 下三份 `.tex` 复制回 `paper_src/` 再编译即可，见 `paper_src/README.md`。
- **提交前最容易被忽略的一项？** 匿名可下载权限与论文里的真实链接。仓库设为 Private 或论文里留着 `OWNER/REPO` 都会导致复核失败。
