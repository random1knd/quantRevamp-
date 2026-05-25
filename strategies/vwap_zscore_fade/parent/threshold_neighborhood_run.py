from __future__ import annotations

import csv
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from shared.validation.threshold_neighborhood import (
    NEIGHBOR_CSV_FIELDS,
    threshold_neighborhood_report,
)


ROOT = Path(__file__).resolve().parents[3]
CAMPAIGN_ID = "vwap_zscore_fade__NQ__5min__2014-11-28_2018-04-17"
DEFAULT_PLAN_PATH = (
    Path(__file__).resolve().parent
    / "campaigns"
    / CAMPAIGN_ID
    / "slicer_plan.json"
)

REPORT_JSON = "threshold_neighborhood_report.json"
REPORT_CSV = "threshold_neighborhood_report.csv"


def run_threshold_neighborhood_report(
    *,
    slicer_dir: str | Path | None = None,
    output_dir: str | Path | None = None,
    plan_path: str | Path = DEFAULT_PLAN_PATH,
) -> Path:
    source_dir = (
        Path(slicer_dir) if slicer_dir is not None else _latest_slicer_dir(plan_path)
    )
    destination = Path(output_dir) if output_dir is not None else source_dir
    destination.mkdir(parents=True, exist_ok=True)

    plan = _read_json(source_dir / "slicer_plan.json")
    candidate = _read_json(source_dir / "filter_candidate.json")
    scored_rules = _read_slice_report(source_dir / "slice_report.csv")

    anchor_rule, anchor_role = _anchor_rule(candidate)
    report = threshold_neighborhood_report(
        scored_rules,
        anchor_rule,
        anchor_rule_role=anchor_role,
    )
    report.update(
        {
            "campaign_id": candidate["campaign_id"],
            "plan_label": candidate["plan_label"],
            "parent_strategy": candidate["parent_strategy"],
            "source_slicer_dir": str(source_dir),
            "source_artifacts": {
                "slicer_plan": str(source_dir / "slicer_plan.json"),
                "filter_candidate": str(source_dir / "filter_candidate.json"),
                "slice_report": str(source_dir / "slice_report.csv"),
            },
            "candidate_status_at_slicer": candidate["candidate_status"],
            "no_candidate_reason_at_slicer": candidate.get("no_candidate_reason"),
            "report_label": _report_label(candidate),
            "coverage_only": candidate["candidate_status"] != "candidate_selected",
            "threshold_grid": plan["quantiles"],
        }
    )

    _write_json(destination / REPORT_JSON, report)
    _write_neighbor_csv(destination / REPORT_CSV, report["neighbors"])
    return destination


def _anchor_rule(candidate: Mapping[str, Any]) -> tuple[dict[str, Any], str]:
    selected_rule = candidate.get("selected_rule")
    if selected_rule is not None:
        return selected_rule, "selected_rule"
    best_rule = candidate.get("best_rule")
    if best_rule is None:
        raise ValueError("filter_candidate must contain selected_rule or best_rule")
    return best_rule, "best_rule"


def _report_label(candidate: Mapping[str, Any]) -> str:
    if candidate["candidate_status"] == "candidate_selected":
        return "train_side_discovery_contaminated_not_edge_validation"
    return "coverage_only_train_side_no_edge_claim"


def _latest_slicer_dir(plan_path: str | Path) -> Path:
    plan = _read_json(Path(plan_path))
    discovery_dir = _repo_path(plan["discovery_artifact"])
    candidates = sorted(
        [
            path
            for path in discovery_dir.iterdir()
            if path.is_dir()
            and (path / "slicer_plan.json").exists()
            and (path / "filter_candidate.json").exists()
            and (path / "slice_report.csv").exists()
        ],
        key=lambda path: path.name,
        reverse=True,
    )
    if not candidates:
        raise FileNotFoundError(f"no slicer artifact directory under {discovery_dir}")
    return candidates[0]


def _read_slice_report(path: Path) -> list[dict[str, Any]]:
    with path.open(newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def _write_neighbor_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=NEIGHBOR_CSV_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {field: _csv_value(row.get(field)) for field in NEIGHBOR_CSV_FIELDS}
            )


def _read_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as file:
        return json.load(file)


def _write_json(path: Path, content: dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8") as file:
        json.dump(_json_value(content), file, indent=2, sort_keys=True)
        file.write("\n")


def _repo_path(path_value: str) -> Path:
    path = Path(path_value)
    if path.is_absolute():
        return path
    return ROOT / path


def _csv_value(value: Any) -> Any:
    if value is None:
        return ""
    return value


def _json_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_value(item) for item in value]
    if hasattr(value, "item"):
        return value.item()
    return value


if __name__ == "__main__":
    print(run_threshold_neighborhood_report())
