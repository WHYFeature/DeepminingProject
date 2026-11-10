"""完整性校验：核对存档内的数据、逐样本预测、汇总与图表是否齐全。

只做文件级与记录级校验，不重新计算实验指标、不发出网络请求。
用法：python code/verify_results.py
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "v1.2"
RESULTS = ROOT / "results"
FIGURES = ROOT / "figures"

EXPECTED_SHA256 = {
    "dev_public.jsonl": "e1d3fd8e66191dae1d9cc4317cec870a99966f4d558a8601ebf533b362ed263a",
    "metadata.json": "085047b5b4b6911249c4225ae4ef406f9e5872fc281ce483c3fed7e6e8e756da",
}
SPLIT_COUNTS = {"dev_public": 1119, "test_public": 831}
FIGURE_STEMS = [
    "fig01_split_composition",
    "fig02_doi_presence",
    "fig03_baseline_comparison",
    "fig04_type_heatmap",
    "fig05_random_stability",
    "fig06_sample_size_uncertainty",
    "fig07_smoke_confusion",
    "fig08_smoke_evidence",
    "fig09_selective_threshold",
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def check(condition: bool, message: str, errors: list[str]) -> None:
    print(("  OK   " if condition else "  FAIL ") + message)
    if not condition:
        errors.append(message)


def main() -> int:
    errors: list[str] = []
    print("== 数据文件 ==")
    for name, expected in EXPECTED_SHA256.items():
        path = DATA / name
        check(path.is_file() and sha256(path) == expected, f"{name} 存在且 SHA-256 匹配", errors)
    for split, count in SPLIT_COUNTS.items():
        path = DATA / f"{split}.jsonl"
        rows = path.read_text(encoding="utf-8").splitlines() if path.is_file() else []
        check(len(rows) == count, f"{split}.jsonl 共 {count} 条（实际 {len(rows)}）", errors)

    print("== 逐样本预测 ==")
    predictions = sorted((RESULTS / "predictions").glob("*.jsonl"))
    check(len(predictions) == 16, f"预测文件 16 个（实际 {len(predictions)}）", errors)
    total = 0
    for path in predictions:
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
        count = SPLIT_COUNTS["dev_public"] if path.name.startswith("dev_public_") else SPLIT_COUNTS["test_public"]
        unique = len({row["bibtex_key"] for row in rows})
        ok = len(rows) == count == unique
        check(ok, f"{path.name}: {len(rows)} 条、key 唯一 {unique}", errors)
        total += len(rows)
    check(total == 15600, f"逐样本预测合计 15,600 条（实际 {total}）", errors)

    print("== 在线观测与汇总 ==")
    smoke = RESULTS / "hallmark_doi_smoke.jsonl"
    smoke_rows = [json.loads(line) for line in smoke.read_text(encoding="utf-8").splitlines() if line] if smoke.is_file() else []
    check(len(smoke_rows) == 20, f"在线 DOI-only 逐样本 20 条（实际 {len(smoke_rows)}）", errors)
    for name in (
        "hallmark_doi_smoke.json",
        "hallmark_official_doi_dev_reference.json",
        "extended_summary.json",
        "latest_run_summary.json",
        "expansion_validation.json",
        "random_100_seeds.csv",
        "sampling_uncertainty.csv",
        "smoke_actual_cases.csv",
        "smoke_threshold_analysis.csv",
        "ece_order_sensitivity.csv",
    ):
        check((RESULTS / name).is_file(), f"results/{name}", errors)

    print("== 实验图 ==")
    for stem in FIGURE_STEMS:
        check((FIGURES / f"{stem}.png").is_file(), f"figures/{stem}.png", errors)

    print("== 官方源码 ==")
    check((ROOT / "official" / "hallmark" / "dataset" / "loader.py").is_file(), "官方 hallmark 包完整", errors)
    check((ROOT / "official" / "VERSION.txt").read_text(encoding="utf-8").strip()
          == "f774fa40675daa83eca6201637a94c4536b7bb3e", "固定 commit 记录一致", errors)

    print()
    if errors:
        print(f"校验未通过：{len(errors)} 项异常。")
        return 1
    print("校验通过：存档内数据、预测、汇总与图表齐全且自洽。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
