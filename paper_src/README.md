# LaTeX 源码编译说明

`course_paper.tex` 是课程论文的排版源文件；仓库根目录的 `paper.pdf` 即由它编译得到（20 页 A4）。本目录自包含，但图片取自仓库根目录 `figures/`，因此 `\graphicspath` 设为 `{{../figures/}}`。

## 编译环境

- TeX 发行版：TeX Live 2024+ 或 MiKTeX，需 `xelatex`、`biber`；
- 宏包：`ctex`、`fontspec`、`biblatex` + `biblatex-gb7714-2015`（GB/T 7714—2015 样式）、`hyperref`、`booktabs`、`longtable`、`tabularx`、`multirow` 等；
- 中文字体：由 `ctex` 自动选择系统字体，无需额外配置。

## 完整编译（含参考文献）

在 `paper_src/` 目录内执行：

```bash
xelatex -interaction=nonstopmode -halt-on-error course_paper.tex
biber course_paper
xelatex -interaction=nonstopmode -halt-on-error course_paper.tex
xelatex -interaction=nonstopmode -halt-on-error course_paper.tex
```

## 快速编译（不装 GB/T 7714 样式时）

仓库随附已生成的 `course_paper.bbl`，因此只需两遍 XeLaTeX，不需要运行 Biber：

```bash
xelatex -interaction=nonstopmode -halt-on-error course_paper.tex
xelatex -interaction=nonstopmode -halt-on-error course_paper.tex
```

编译产物 `course_paper.pdf` 被 `.gitignore` 排除；如需更新根目录的 `paper.pdf`，将其复制过去覆盖即可。

## 回填代码与数据链接

`course_paper.tex` 导言区有一个集中宏：

```tex
\newcommand{\CodeDataURL}{https://github.com/OWNER/REPO}
```

把 `OWNER/REPO` 换成实际用户名与仓库名后重新编译，正文「结论」与「代码与数据可用性」两处的 `\CodeDataLink{}` 会自动变成可点击链接。URL 中若含 `%`、`#`、`&`，需分别写成 `\%`、`\#`、`\&`。

相同的占位符也出现在 `paper.md` 末尾的引用式链接定义 `[repo]:`；两处应保持一致。

## 与本仓库其他目录的关系

- `extended_results.tex`、`baseline_table.tex`、`actual_cases_table.tex` 是 `results/` 下三份由脚本生成的表格在本目录的快照，保证单独分发本目录也能编译。
- 运行 `python code/run_extended_experiments.py` 会更新 `results/` 与 `figures/`；若表格内容随之变化，把 `results/` 下这三份 `.tex` 复制回本目录再编译。
- `references_gb.bib` 与 `results/references_gb.bib` 内容相同，供 Biber 使用。
- Markdown 版论文见根目录 `paper.md`，图片用 `figures/*.png`；LaTeX 版用 `figures/*.pdf`。
