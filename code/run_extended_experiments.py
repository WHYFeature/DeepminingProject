"""Reproducible offline experiments and figures for the HALLMARK course report.

The script deliberately separates legitimate field heuristics, degenerate reference
lines, and the venue-distribution diagnostic.  It never queries an online service.
The existing 20-example DOI run is read as immutable observational input.
"""

from __future__ import annotations

import csv
import hashlib
import json
import logging
import math
import os
import platform
import random
import re
import sys
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean, pstdev

# All resources are resolved relative to this archive root, so the pack can be
# unpacked anywhere and re-run without editing absolute or project-local paths.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "official"))

os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "hallmark-mplconfig"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from hallmark.baselines.degenerate import (
    always_hallucinated_baseline,
    always_valid_baseline,
    random_baseline,
    venue_oracle_baseline,
)
from hallmark.baselines.doi_presence import run_doi_presence_heuristic
from hallmark.baselines.prescreening import check_author_heuristics, check_year_bounds
from hallmark.dataset.loader import load_metadata, load_split
from hallmark.dataset.schema import BenchmarkEntry, Prediction, load_predictions, save_predictions
from hallmark.evaluation.metrics import evaluate, expected_calibration_error


DATA_DIR = ROOT / "data"
OUT_DIR = ROOT / "results"
FIG_DIR = ROOT / "figures"
SEED = 20261015
SPLITS = ("dev_public", "test_public")
COLORS = {
    "blue": "#2563EB",
    "cyan": "#0891B2",
    "green": "#15803D",
    "amber": "#D97706",
    "red": "#B91C1C",
    "gray": "#64748B",
    "light": "#E2E8F0",
}


def json_safe(value):
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    if isinstance(value, np.generic):
        return json_safe(value.item())
    return value


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(json_safe(value), ensure_ascii=False, indent=2), encoding="utf-8")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def get_commit() -> str:
    """Read the frozen upstream revision; the archive intentionally has no .git."""
    return (ROOT / "official" / "VERSION.txt").read_text(encoding="utf-8").strip()


def basic_metrics(entries: list[BenchmarkEntry], predictions: list[Prediction]) -> dict[str, float | int]:
    pred_map = {p.bibtex_key: p for p in predictions if p.evaluated and p.label != "UNCERTAIN"}
    tp = fp = tn = fn = 0
    confidences: list[float] = []
    correctness: list[int] = []
    for entry in entries:
        pred = pred_map.get(entry.bibtex_key)
        if pred is None:
            continue
        positive = entry.label == "HALLUCINATED"
        predicted_positive = pred.label == "HALLUCINATED"
        tp += int(positive and predicted_positive)
        fp += int((not positive) and predicted_positive)
        tn += int((not positive) and (not predicted_positive))
        fn += int(positive and (not predicted_positive))
        confidences.append(pred.confidence)
        correctness.append(int(pred.label == entry.label))
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    fpr = fp / (fp + tn) if fp + tn else 0.0
    valid_precision = tn / (tn + fn) if tn + fn else 0.0
    valid_recall = tn / (tn + fp) if tn + fp else 0.0
    valid_f1 = (
        2 * valid_precision * valid_recall / (valid_precision + valid_recall)
        if valid_precision + valid_recall
        else 0.0
    )
    denominator = math.sqrt((tp + fp) * (tp + fn) * (tn + fp) * (tn + fn))
    mcc = (tp * tn - fp * fn) / denominator if denominator else 0.0
    ece = 0.0
    if confidences:
        for bin_index in range(10):
            idx = [i for i, c in enumerate(confidences) if min(int(c * 10), 9) == bin_index]
            if idx:
                bin_acc = mean(correctness[i] for i in idx)
                bin_conf = mean(confidences[i] for i in idx)
                ece += len(idx) / len(confidences) * abs(bin_acc - bin_conf)
    return {
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
        "detection_rate": recall,
        "false_positive_rate": fpr,
        "precision": precision,
        "f1": f1,
        "macro_f1": (f1 + valid_f1) / 2,
        "mcc": mcc,
        "ece_fixed_width": ece,
        "coverage": len(pred_map) / len(entries) if entries else 0.0,
    }


def make_prescreen_predictions(entries, mode: str) -> list[Prediction]:
    predictions = []
    for blind in entries:
        year = check_year_bounds(blind, reference_year=2026)
        author = check_author_heuristics(blind)
        selected = []
        if mode in {"year", "combined"}:
            selected.append(year)
        if mode in {"author", "combined"}:
            selected.append(author)
        flags = [result for result in selected if result.label == "HALLUCINATED"]
        if flags:
            strongest = max(flags, key=lambda result: result.confidence)
            predictions.append(
                Prediction(
                    bibtex_key=blind.bibtex_key,
                    label="HALLUCINATED",
                    confidence=strongest.confidence,
                    reason="; ".join(result.reason for result in flags),
                    source="prescreening",
                )
            )
        else:
            predictions.append(
                Prediction(
                    bibtex_key=blind.bibtex_key,
                    label="VALID",
                    confidence=0.5,
                    reason=f"No {mode} heuristic alarm; conservative default",
                    source="prescreening",
                )
            )
    return predictions


def normalized(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", text.lower())


def audit_split(entries: list[BenchmarkEntry]) -> dict:
    label = Counter(entry.label for entry in entries)
    tiers = Counter(str(entry.difficulty_tier) for entry in entries if entry.label == "HALLUCINATED")
    types = Counter(entry.hallucination_type or "valid" for entry in entries)
    methods = Counter(entry.generation_method for entry in entries)
    by_label = {}
    for target in ("VALID", "HALLUCINATED"):
        subset = [entry for entry in entries if entry.label == target]
        by_label[target] = {
            "count": len(subset),
            "doi_present": sum(bool((entry.doi or "").strip()) for entry in subset),
            "title_missing": sum(not bool(entry.title.strip()) for entry in subset),
            "author_missing": sum(not bool(entry.author.strip()) for entry in subset),
            "year_missing": sum(not bool(entry.year.strip()) for entry in subset),
            "venue_missing": sum(not bool(entry.venue.strip()) for entry in subset),
        }
    title_counts = Counter(normalized(entry.title) for entry in entries if normalized(entry.title))
    doi_counts = Counter(normalized(entry.doi or "") for entry in entries if normalized(entry.doi or ""))
    return {
        "count": len(entries),
        "labels": dict(label),
        "hallucination_tiers": dict(tiers),
        "types": dict(types),
        "generation_methods": dict(methods),
        "field_audit": by_label,
        "duplicate_title_groups": sum(count > 1 for count in title_counts.values()),
        "entries_in_duplicate_title_groups": sum(count for count in title_counts.values() if count > 1),
        "duplicate_doi_groups": sum(count > 1 for count in doi_counts.values()),
    }


def cross_split_audit(left: list[BenchmarkEntry], right: list[BenchmarkEntry]) -> dict:
    left_titles = {normalized(entry.title) for entry in left if normalized(entry.title)}
    right_titles = {normalized(entry.title) for entry in right if normalized(entry.title)}
    left_dois = {normalized(entry.doi or "") for entry in left if normalized(entry.doi or "")}
    right_dois = {normalized(entry.doi or "") for entry in right if normalized(entry.doi or "")}
    return {
        "exact_normalized_title_overlap": len(left_titles & right_titles),
        "normalized_doi_overlap": len(left_dois & right_dois),
    }


def run_offline_baselines(entries: list[BenchmarkEntry], split: str) -> tuple[dict, dict[str, list[Prediction]]]:
    blind = [entry.to_blind() for entry in entries]
    (OUT_DIR / "predictions").mkdir(parents=True, exist_ok=True)
    runners = {
        "always_valid": lambda: always_valid_baseline(blind),
        "always_hallucinated": lambda: always_hallucinated_baseline(blind),
        "random_seed42": lambda: random_baseline(blind, seed=42, prevalence=0.5),
        "doi_presence": lambda: run_doi_presence_heuristic(blind),
        "year_only": lambda: make_prescreen_predictions(blind, "year"),
        "author_only": lambda: make_prescreen_predictions(blind, "author"),
        "year_author": lambda: make_prescreen_predictions(blind, "combined"),
        "venue_oracle_diagnostic": lambda: venue_oracle_baseline(blind),
    }
    results = {}
    all_predictions = {}
    for name, runner in runners.items():
        predictions = runner()
        all_predictions[name] = predictions
        save_predictions(predictions, OUT_DIR / "predictions" / f"{split}_{name}.jsonl")
        official = evaluate(entries, predictions, tool_name=name, split_name=split, compute_ci=False)
        assert len(predictions) == len(entries)
        assert len({p.bibtex_key for p in predictions}) == len(entries)
        independently = basic_metrics(entries, predictions)
        for official_key, independent_key in (
            ("detection_rate", "detection_rate"), ("false_positive_rate", "false_positive_rate"),
            ("f1_hallucination", "f1"), ("mcc", "mcc"), ("macro_f1", "macro_f1"),
        ):
            assert math.isclose(getattr(official, official_key), independently[independent_key], abs_tol=1e-12)
        results[name] = json_safe(official.to_dict())
        results[name]["independent_metrics"] = independently
    return results, all_predictions


def random_seed_stability(entries: list[BenchmarkEntry], split: str) -> list[dict]:
    blind = [entry.to_blind() for entry in entries]
    rows = []
    for seed in range(100):
        metrics = basic_metrics(entries, random_baseline(blind, seed=seed, prevalence=0.5))
        rows.append({"split": split, "seed": seed, **metrics})
    return rows


def stratified_resample(entries, predictions, sample_size: int, rng: random.Random):
    pred_map = {pred.bibtex_key: pred for pred in predictions}
    hall = [entry for entry in entries if entry.label == "HALLUCINATED"]
    valid = [entry for entry in entries if entry.label == "VALID"]
    hall_n = round(sample_size * len(hall) / len(entries))
    valid_n = sample_size - hall_n
    sampled_entries = [rng.choice(hall) for _ in range(hall_n)] + [rng.choice(valid) for _ in range(valid_n)]
    sampled_predictions = [pred_map[entry.bibtex_key] for entry in sampled_entries]
    # Assign synthetic unique keys so duplicate bootstrap draws remain present.
    cloned_entries = []
    cloned_predictions = []
    for index, (entry, pred) in enumerate(zip(sampled_entries, sampled_predictions)):
        entry_data = entry.to_dict()
        entry_data["bibtex_key"] = f"bootstrap_{index}_{entry.bibtex_key}"
        pred_data = pred.to_dict()
        pred_data["bibtex_key"] = entry_data["bibtex_key"]
        cloned_entries.append(BenchmarkEntry.from_dict(entry_data))
        cloned_predictions.append(Prediction.from_dict(pred_data))
    return cloned_entries, cloned_predictions


def sampling_uncertainty(entries, predictions) -> list[dict]:
    rng = random.Random(SEED)
    rows = []
    for size in (20, 50, 100, 200, 500, len(entries)):
        values = []
        for replicate in range(500):
            sampled_entries, sampled_predictions = stratified_resample(entries, predictions, size, rng)
            metrics = basic_metrics(sampled_entries, sampled_predictions)
            values.append(metrics["f1"])
        rows.append(
            {
                "sample_size": size,
                "replicates": len(values),
                "mean_f1": mean(values),
                "sd_f1": pstdev(values),
                "ci_lower": float(np.quantile(values, 0.025)),
                "ci_upper": float(np.quantile(values, 0.975)),
            }
        )
    return rows


def smoke_analysis(dev_entries: list[BenchmarkEntry]) -> dict:
    smoke_predictions = load_predictions(ROOT / "results" / "hallmark_doi_smoke.jsonl")
    entry_map = {entry.bibtex_key: entry for entry in dev_entries}
    smoke_entries = [entry_map[pred.bibtex_key] for pred in smoke_predictions]
    cases = []
    evidence_counts = Counter()
    for entry, pred in zip(smoke_entries, smoke_predictions):
        if "doi_resolves" not in pred.subtest_results:
            evidence = "not_checked_no_doi"
        elif pred.subtest_results["doi_resolves"] is True:
            evidence = "resolved"
        elif pred.subtest_results["doi_resolves"] is False:
            evidence = "not_found"
        else:
            evidence = "indeterminate"
        correct = pred.label == entry.label
        evidence_counts[evidence] += 1
        cases.append(
            {
                "bibtex_key": entry.bibtex_key,
                "title": entry.title,
                "gold": entry.label,
                "hallucination_type": entry.hallucination_type or "valid",
                "tier": entry.difficulty_tier,
                "prediction": pred.label,
                "confidence": pred.confidence,
                "correct": correct,
                "doi_evidence": evidence,
                "reason": pred.reason,
                "ground_truth_explanation": entry.explanation,
                "api_calls": pred.api_calls,
                "wall_clock_seconds": pred.wall_clock_seconds,
            }
        )

    threshold_rows = []
    for threshold in (0.50, 0.60, 0.75, 0.85, 0.90):
        keep = [i for i, pred in enumerate(smoke_predictions) if pred.confidence >= threshold]
        if keep:
            selected_entries = [smoke_entries[i] for i in keep]
            selected_predictions = [smoke_predictions[i] for i in keep]
            values = basic_metrics(selected_entries, selected_predictions)
            accuracy = mean(int(e.label == p.label) for e, p in zip(selected_entries, selected_predictions))
        else:
            values = {"f1": 0.0, "detection_rate": 0.0, "false_positive_rate": 0.0}
            accuracy = None
        threshold_rows.append(
            {
                "minimum_confidence": threshold,
                "retained": len(keep),
                "coverage": len(keep) / len(smoke_entries),
                "accuracy": accuracy,
                "f1": values["f1"],
                "detection_rate": values["detection_rate"],
                "false_positive_rate": values["false_positive_rate"],
            }
        )

    rng = random.Random(SEED)
    boot = defaultdict(list)
    metrics_logger = logging.getLogger("hallmark.evaluation.metrics")
    previous_level = metrics_logger.level
    metrics_logger.setLevel(logging.ERROR)
    for _ in range(5000):
        sampled_entries, sampled_predictions = stratified_resample(
            smoke_entries, smoke_predictions, len(smoke_entries), rng
        )
        metrics = basic_metrics(sampled_entries, sampled_predictions)
        for metric in ("detection_rate", "false_positive_rate", "f1", "mcc", "ece_fixed_width"):
            boot[metric].append(metrics[metric])
        boot["ece_adaptive_official"].append(expected_calibration_error(sampled_entries, sampled_predictions))
    point_metrics = basic_metrics(smoke_entries, smoke_predictions)
    point_metrics["ece_adaptive_official"] = expected_calibration_error(smoke_entries, smoke_predictions)
    assert math.isclose(point_metrics["ece_fixed_width"], expected_calibration_error(
        smoke_entries, smoke_predictions, adaptive=False), abs_tol=1e-12)
    permutation_rows = []
    for permutation_seed in range(100):
        order = list(range(len(smoke_entries)))
        random.Random(permutation_seed).shuffle(order)
        ordered_entries = [smoke_entries[i] for i in order]
        ordered_predictions = [smoke_predictions[i] for i in order]
        permutation_rows.append({
            "seed": permutation_seed,
            "adaptive_ece": expected_calibration_error(ordered_entries, ordered_predictions),
            "fixed_width_ece": expected_calibration_error(ordered_entries, ordered_predictions, adaptive=False),
        })
    save_csv(OUT_DIR / "ece_order_sensitivity.csv", permutation_rows)
    metrics_logger.setLevel(previous_level)
    bootstrap = {
        metric: {
            "point": point_metrics[metric],
            "ci_lower": float(np.quantile(values, 0.025)),
            "ci_upper": float(np.quantile(values, 0.975)),
        }
        for metric, values in boot.items()
    }

    return {
        "metrics": point_metrics,
        "ece_order_sensitivity": {
            name: {"min": min(row[name] for row in permutation_rows),
                   "max": max(row[name] for row in permutation_rows),
                   "mean": mean(row[name] for row in permutation_rows)}
            for name in ("adaptive_ece", "fixed_width_ece")
        },
        "evidence_counts": dict(evidence_counts),
        "effective_evidence_coverage": sum(
            evidence_counts[key] for key in ("resolved", "not_found")
        )
        / len(smoke_entries),
        "api_query_coverage": sum(pred.api_calls > 0 for pred in smoke_predictions) / len(smoke_predictions),
        "threshold_analysis": threshold_rows,
        "independent_stratified_bootstrap": bootstrap,
        "cases": cases,
    }


def save_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        return
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def style_axes(ax) -> None:
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", color="#CBD5E1", linewidth=0.7, alpha=0.65)
    ax.set_axisbelow(True)


def save_figure(fig, name: str) -> None:
    fig.tight_layout()
    fig.savefig(FIG_DIR / f"{name}.pdf", bbox_inches="tight")
    fig.savefig(FIG_DIR / f"{name}.png", dpi=220, bbox_inches="tight")
    plt.close(fig)


def create_figures(audits, baseline_results, stability, sampling, smoke) -> None:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 9,
            "axes.titlesize": 11,
            "axes.labelsize": 9,
            "figure.facecolor": "white",
            "axes.facecolor": "white",
        }
    )

    fig, ax = plt.subplots(figsize=(6.8, 3.6))
    names = ["Development", "Test", "Stress"]
    valid = [audits[s]["labels"].get("VALID", 0) for s in ("dev_public", "test_public", "stress_test")]
    hall = [audits[s]["labels"].get("HALLUCINATED", 0) for s in ("dev_public", "test_public", "stress_test")]
    x = np.arange(len(names))
    ax.bar(x, valid, label="VALID", color=COLORS["blue"])
    ax.bar(x, hall, bottom=valid, label="HALLUCINATED", color=COLORS["red"])
    for i, total in enumerate(np.array(valid) + np.array(hall)):
        ax.text(i, total + 18, str(total), ha="center", fontsize=9)
    ax.set_xticks(x, names)
    ax.set_ylabel("Entries")
    ax.set_title("HALLMARK v1.2 split composition")
    ax.legend(frameon=False, ncol=2, loc="upper right")
    ax.set_ylim(0, max(np.array(valid) + np.array(hall)) * 1.15)
    style_axes(ax)
    save_figure(fig, "fig01_split_composition")

    fig, ax = plt.subplots(figsize=(6.8, 3.8))
    groups = []
    values = []
    for split in SPLITS:
        for label in ("VALID", "HALLUCINATED"):
            row = audits[split]["field_audit"][label]
            groups.append(f"{split.split('_')[0]}\n{label[:5]}")
            values.append(row["doi_present"] / row["count"])
    bars = ax.bar(np.arange(len(groups)), values, color=[COLORS["blue"], COLORS["red"]] * 2)
    for bar, value in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, value + 0.02, f"{value:.1%}", ha="center")
    ax.set_xticks(np.arange(len(groups)), groups)
    ax.set_ylim(0, 1.08)
    ax.set_ylabel("DOI field presence")
    ax.set_title("DOI availability differs by class and split")
    style_axes(ax)
    save_figure(fig, "fig02_doi_presence")

    display = ["always_valid", "always_hallucinated", "random_seed42", "doi_presence", "year_author", "venue_oracle_diagnostic"]
    labels = ["Always valid", "Always hall.", "Random", "DOI presence", "Year+author", "Venue oracle*"]
    fig, axes = plt.subplots(1, 2, figsize=(10.2, 3.8), sharey=True)
    for ax, split, title in zip(axes, SPLITS, ("Development split", "Test split")):
        f1s = [baseline_results[split][name]["independent_metrics"]["f1"] for name in display]
        mccs = [baseline_results[split][name]["independent_metrics"]["mcc"] for name in display]
        x = np.arange(len(display))
        ax.bar(x - 0.18, f1s, width=0.36, label="F1", color=COLORS["blue"])
        ax.bar(x + 0.18, mccs, width=0.36, label="MCC", color=COLORS["amber"])
        ax.set_xticks(x, labels, rotation=28, ha="right")
        ax.set_title(title)
        ax.set_ylim(-0.35, 1.05)
        style_axes(ax)
    axes[0].set_ylabel("Score")
    axes[1].legend(frameon=False, ncol=2)
    fig.suptitle("Offline baseline comparison (*diagnostic, not a detector)", y=1.03)
    save_figure(fig, "fig03_baseline_comparison")

    type_names = sorted(
        key for key in baseline_results["dev_public"]["doi_presence"]["per_type_metrics"] if key != "valid"
    )
    model_names = ["doi_presence", "year_only", "author_only", "year_author", "venue_oracle_diagnostic"]
    matrix = np.array(
        [
            [baseline_results["dev_public"][model]["per_type_metrics"].get(kind, {}).get("detection_rate", 0) for kind in type_names]
            for model in model_names
        ]
    )
    matrix = matrix.T
    fig, ax = plt.subplots(figsize=(8.3, 5.5))
    image = ax.imshow(matrix, cmap="YlOrRd", vmin=0, vmax=1, aspect="auto")
    ax.set_yticks(np.arange(len(type_names)), [name.replace("_", " ") for name in type_names])
    ax.set_xticks(np.arange(len(model_names)),
                  ["DOI presence", "Year", "Author", "Year+author", "Venue oracle*"],
                  rotation=15, ha="right")
    for i in range(matrix.shape[0]):
        for j in range(matrix.shape[1]):
            ax.text(j, i, f"{matrix[i, j]:.2f}", ha="center", va="center", fontsize=9,
                    color="white" if matrix[i, j] > 0.55 else "black")
    fig.colorbar(image, ax=ax, label="Detection rate", fraction=0.025, pad=0.02)
    ax.set_title("Development-set detection rate by hallucination type")
    save_figure(fig, "fig04_type_heatmap")

    fig, axes = plt.subplots(1, 2, figsize=(9.2, 3.5), sharex=True, sharey=True)
    for ax, split, color in zip(axes, SPLITS, (COLORS["cyan"], COLORS["green"])):
        values = [row["f1"] for row in stability if row["split"] == split]
        ax.hist(values, bins=12, color=color, edgecolor="white")
        ax.axvline(mean(values), color="black", linestyle="--", linewidth=1.2, label=f"mean={mean(values):.3f}")
        ax.set_title(split.replace("_", " "))
        ax.set_xlabel("Hallucination F1")
        ax.legend(frameon=False)
        style_axes(ax)
    axes[0].set_ylabel("Seeds (n=100)")
    fig.suptitle("Random-baseline stability across fixed seeds", y=1.03)
    save_figure(fig, "fig05_random_stability")

    fig, ax = plt.subplots(figsize=(6.8, 3.8))
    xs = [row["sample_size"] for row in sampling]
    means = np.array([row["mean_f1"] for row in sampling])
    lower = np.array([row["ci_lower"] for row in sampling])
    upper = np.array([row["ci_upper"] for row in sampling])
    ax.plot(xs, means, marker="o", color=COLORS["blue"], label="Bootstrap mean")
    ax.fill_between(xs, lower, upper, color=COLORS["blue"], alpha=0.18, label="95% percentile interval")
    ax.set_xscale("log")
    ax.set_xticks(xs, [str(x) for x in xs])
    ax.set_xlabel("Stratified sample size (log scale)")
    ax.set_ylabel("DOI-presence F1")
    ax.set_title("Sampling uncertainty decreases with evaluation size")
    ax.legend(frameon=False)
    style_axes(ax)
    save_figure(fig, "fig06_sample_size_uncertainty")

    cm = smoke["metrics"]
    matrix = np.array([[cm["tn"], cm["fp"]], [cm["fn"], cm["tp"]]])
    fig, ax = plt.subplots(figsize=(4.6, 4.0))
    image = ax.imshow(matrix, cmap="Blues", vmin=0, vmax=max(matrix.flatten()))
    for i in range(2):
        for j in range(2):
            ax.text(j, i, str(matrix[i, j]), ha="center", va="center", fontsize=18,
                    color="white" if matrix[i, j] > matrix.max() / 2 else "black")
    ax.set_xticks([0, 1], ["Pred. VALID", "Pred. HALL"])
    ax.set_yticks([0, 1], ["True VALID", "True HALL"])
    ax.set_title("DOI-only smoke-test confusion matrix")
    fig.colorbar(image, ax=ax, fraction=0.045, pad=0.04)
    save_figure(fig, "fig07_smoke_confusion")

    fig, ax = plt.subplots(figsize=(7.0, 3.8))
    order = ["not_checked_no_doi", "indeterminate", "not_found", "resolved"]
    labels = ["No DOI / not checked", "Indeterminate", "DOI not found", "Resolved"]
    correct = []
    incorrect = []
    for evidence in order:
        subset = [case for case in smoke["cases"] if case["doi_evidence"] == evidence]
        correct.append(sum(case["correct"] for case in subset))
        incorrect.append(sum(not case["correct"] for case in subset))
    x = np.arange(len(order))
    ax.bar(x, correct, label="Correct", color=COLORS["green"])
    ax.bar(x, incorrect, bottom=correct, label="Incorrect", color=COLORS["red"])
    ax.set_xticks(x, labels, rotation=15, ha="right")
    ax.set_ylabel("Samples")
    ax.set_title("Prediction outcome by observed DOI evidence")
    ax.legend(frameon=False, ncol=2)
    style_axes(ax)
    save_figure(fig, "fig08_smoke_evidence")

    fig, ax1 = plt.subplots(figsize=(6.8, 3.8))
    rows = smoke["threshold_analysis"]
    x = [row["minimum_confidence"] for row in rows]
    coverage = [row["coverage"] for row in rows]
    accuracy = [row["accuracy"] if row["accuracy"] is not None else float("nan") for row in rows]
    ax1.plot(x, coverage, marker="o", color=COLORS["blue"], label="Coverage")
    ax1.plot(x, accuracy, marker="s", color=COLORS["green"], label="Accuracy on retained")
    ax1.set_ylim(0, 1.05)
    ax1.set_xlabel("Minimum prediction confidence")
    ax1.set_ylabel("Fraction")
    ax1.set_title("Selective prediction trade-off on 20 DOI cases")
    ax1.legend(frameon=False)
    style_axes(ax1)
    save_figure(fig, "fig09_selective_threshold")


def latex_escape(text: str) -> str:
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    return "".join(replacements.get(char, char) for char in text)


def write_latex_data(summary: dict) -> None:
    smoke = summary["smoke"]
    dev = summary["baseline_results"]["dev_public"]
    test = summary["baseline_results"]["test_public"]
    macros = [
        "% Generated by code/run_extended_experiments.py; do not edit manually.",
        rf"\newcommand{{\DevCount}}{{{summary['audits']['dev_public']['count']}}}",
        rf"\newcommand{{\TestCount}}{{{summary['audits']['test_public']['count']}}}",
        rf"\newcommand{{\StressCount}}{{{summary['audits']['stress_test']['count']}}}",
        rf"\newcommand{{\SmokeEvidenceCoverage}}{{{smoke['effective_evidence_coverage'] * 100:.1f}\%}}",
        rf"\newcommand{{\SmokeApiCoverage}}{{{smoke['api_query_coverage'] * 100:.1f}\%}}",
        rf"\newcommand{{\DevDoiFone}}{{{dev['doi_presence']['independent_metrics']['f1']:.4f}}}",
        rf"\newcommand{{\TestDoiFone}}{{{test['doi_presence']['independent_metrics']['f1']:.4f}}}",
        rf"\newcommand{{\DevDoiMcc}}{{{dev['doi_presence']['independent_metrics']['mcc']:.4f}}}",
        rf"\newcommand{{\TestDoiMcc}}{{{test['doi_presence']['independent_metrics']['mcc']:.4f}}}",
    ]
    (OUT_DIR / "extended_results.tex").write_text("\n".join(macros) + "\n", encoding="utf-8")

    table = [r"\begin{table}[htbp]", r"\centering\small",
             r"\caption{全量离线实测结果。DR 为幻觉检出率；FPR 为真实引用误报率。最后一行仅作偏差诊断。}",
             r"\label{tab:offline-results}",
             r"\begin{tabular}{lrrrrrrrr}", r"\toprule",
             r" & \multicolumn{4}{c}{开发集（$n=1119$）} & \multicolumn{4}{c}{测试集（$n=831$）}\\",
             r"方法 & DR & FPR & F1 & MCC & DR & FPR & F1 & MCC\\", r"\midrule"]
    names = {"always_valid": "恒预测真实", "always_hallucinated": "恒预测幻觉",
             "random_seed42": "随机（seed=42）", "doi_presence": "DOI存在性",
             "year_only": "仅年份", "author_only": "仅作者", "year_author": "年份+作者",
             "venue_oracle_diagnostic": "Venue oracle*"}
    for model, name in names.items():
        values = []
        for split in SPLITS:
            metrics = summary["baseline_results"][split][model]["independent_metrics"]
            values.extend(f"{metrics[key]:.4f}" for key in ("detection_rate", "false_positive_rate", "f1", "mcc"))
        table.append(name + " & " + " & ".join(values) + r"\\")
    table.extend([r"\bottomrule", r"\end{tabular}", r"\end{table}"])
    (OUT_DIR / "baseline_table.tex").write_text("\n".join(table) + "\n", encoding="utf-8")

    selected = []
    desired = [
        "arxiv_version_mismatch",
        "near_miss_title",
        "nonexistent_venue",
        "partial_author_list",
        "plausible_fabrication",
        "preprint_as_published",
        "swapped_authors",
        "merged_citation",
    ]
    for kind in desired:
        match = next((case for case in smoke["cases"] if case["hallucination_type"] == kind), None)
        if match and match not in selected:
            selected.append(match)
    selected.extend(case for case in smoke["cases"] if case["gold"] == "VALID" and case not in selected)
    selected = selected[:12]
    lines = [
        "% Generated actual-case table.",
        r"\begingroup\small\setlength{\tabcolsep}{3pt}\raggedright",
        r"\begin{longtable}{>{\raggedright\arraybackslash}p{2.05cm}>{\raggedright\arraybackslash}p{4.1cm}>{\raggedright\arraybackslash}p{2.0cm}>{\raggedright\arraybackslash}p{1.15cm}>{\raggedright\arraybackslash}p{1.7cm}>{\raggedright\arraybackslash}p{2.4cm}}",
        r"\caption{固定在线子集的十二个真实样本案例}\label{tab:actual-cases}\\",
        r"\toprule",
        r"Key & 标题（截断） & 真实类型 & 预测 & DOI证据 & 结果解释\\",
        r"\midrule",
        r"\endfirsthead",
        r"\toprule Key & 标题（截断） & 真实类型 & 预测 & DOI证据 & 结果解释\\ \midrule",
        r"\endhead",
    ]
    evidence_zh = {
        "not_checked_no_doi": "无DOI，未检查",
        "indeterminate": "状态不确定",
        "not_found": "404未找到",
        "resolved": "成功解析",
    }
    types_zh = {"arxiv_version_mismatch": "版本错配", "near_miss_title": "近似标题",
                "nonexistent_venue": "虚构刊会", "partial_author_list": "作者截断",
                "plausible_fabrication": "合理伪造", "preprint_as_published": "预印本误引",
                "swapped_authors": "作者交换", "merged_citation": "合并引用", "valid": "有效引用"}
    for case in selected:
        title = case["title"][:58] + ("..." if len(case["title"]) > 58 else "")
        result = "正确" if case["correct"] else "漏检/误判"
        lines.append(
            " & ".join(
                [
                    rf"\texttt{{{case['bibtex_key'][:6]}\allowbreak{{}}{case['bibtex_key'][6:]}}}",
                    latex_escape(title),
                    types_zh[case["hallucination_type"]],
                    "HALL" if case["prediction"] == "HALLUCINATED" else "VALID",
                    evidence_zh[case["doi_evidence"]],
                    f"{result}；置信度 {case['confidence']:.2f}",
                ]
            )
            + r"\\"
        )
    lines.extend([r"\bottomrule", r"\end{longtable}", r"\endgroup"])
    (OUT_DIR / "actual_cases_table.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    entries_by_split = {
        split: load_split(split, version="v1.2", data_dir=DATA_DIR)
        for split in (*SPLITS, "stress_test")
    }
    audits = {split: audit_split(entries) for split, entries in entries_by_split.items()}
    audits["cross_split"] = cross_split_audit(
        entries_by_split["dev_public"], entries_by_split["test_public"]
    )

    baseline_results = {}
    predictions_by_split = {}
    for split in SPLITS:
        baseline_results[split], predictions_by_split[split] = run_offline_baselines(
            entries_by_split[split], split
        )

    stability = []
    for split in SPLITS:
        stability.extend(random_seed_stability(entries_by_split[split], split))
    sampling = sampling_uncertainty(
        entries_by_split["dev_public"], predictions_by_split["dev_public"]["doi_presence"]
    )
    smoke = smoke_analysis(entries_by_split["dev_public"])

    metadata = load_metadata(version="v1.2", data_dir=DATA_DIR)
    summary = {
        "experiment": {
            "script": "code/run_extended_experiments.py",
            "seed": SEED,
            "python": sys.version,
            "matplotlib": matplotlib.__version__,
            "numpy": np.__version__,
            "platform": platform.platform(),
            "hallmark_commit": get_commit(),
            "dataset_version": "v1.2",
            "metadata_version": metadata.get("version"),
            "dev_sha256": sha256(DATA_DIR / "v1.2" / "dev_public.jsonl"),
            "test_sha256": sha256(DATA_DIR / "v1.2" / "test_public.jsonl"),
            "online_requests": 0,
            "notes": "All extended baselines are offline; the 20-case DOI run is reused read-only.",
        },
        "audits": audits,
        "baseline_results": baseline_results,
        "random_seed_stability": {
            split: {
                metric: {
                    "mean": mean(row[metric] for row in stability if row["split"] == split),
                    "sd": pstdev(row[metric] for row in stability if row["split"] == split),
                    "min": min(row[metric] for row in stability if row["split"] == split),
                    "max": max(row[metric] for row in stability if row["split"] == split),
                }
                for metric in ("f1", "mcc", "detection_rate", "false_positive_rate")
            }
            for split in SPLITS
        },
        "sampling_uncertainty": sampling,
        "smoke": smoke,
    }

    write_json(OUT_DIR / "extended_summary.json", summary)
    save_csv(OUT_DIR / "random_100_seeds.csv", stability)
    save_csv(OUT_DIR / "sampling_uncertainty.csv", sampling)
    save_csv(OUT_DIR / "smoke_actual_cases.csv", smoke["cases"])
    save_csv(OUT_DIR / "smoke_threshold_analysis.csv", smoke["threshold_analysis"])
    create_figures(audits, baseline_results, stability, sampling, smoke)
    write_latex_data(summary)
    print(json.dumps({
        "audits": audits,
        "doi_presence": {
            split: baseline_results[split]["doi_presence"]["independent_metrics"] for split in SPLITS
        },
        "year_author": {
            split: baseline_results[split]["year_author"]["independent_metrics"] for split in SPLITS
        },
        "smoke": {key: value for key, value in smoke.items() if key != "cases"},
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
