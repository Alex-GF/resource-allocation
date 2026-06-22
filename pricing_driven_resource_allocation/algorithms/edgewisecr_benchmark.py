"""Benchmark helpers for the EdgeWiseCR variants.

These helpers run the EdgeWise / EdgeWiseCR / Prolog variants as baseline
placements on the existing pricing-driven resource-allocation scenarios,
mirroring the structure of ``benchmark.py`` used by the RAOM4CC baselines.

Six variants are exposed, matching the configurations evaluated in the
EdgeWiseCR paper:

- ``edgewise``             — hybrid declarative + MILP (preprocess=True, cr=False)
- ``edgewise_cr``          — hybrid declarative + MILP with CR (preprocess=True, cr=True)
- ``edgewise_num``         — MILP without declarative pre-filter (preprocess=False, cr=False)
- ``prolog``               — pure greedy heuristic (preprocess=True, cr=False)
- ``prolog_cr``            — pure greedy heuristic with CR (preprocess=True, cr=True)
- ``prolog_num``           — pure greedy heuristic without pre-filter (preprocess=False, cr=False)

All variants are evaluated under the same ``minimize_cost`` objective used
by PRIME and the RAOM4CC baselines.
"""

from __future__ import annotations

import csv
import os
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

from .edgewisecr import (
    DEFAULT_TIMEOUT_SECONDS,
    EdgeWiseResult,
    edgewise_greedy_solve,
    edgewise_milp_solve,
)


@dataclass(frozen=True)
class EdgeWiseSelection:
    """Result of running one EdgeWiseCR variant on one scenario."""

    scenario_id: str
    algorithm: str
    status: str
    selected_node: str = ""
    selected_layer: str = ""
    objective: str = "minimize_cost"
    time_seconds: float = 0.0
    estimated_cost: Optional[float] = None
    feasible: bool = False
    bins: int = 0
    moved_services: int = 0
    reason: str = ""
    selected_features: str = ""
    selected_resources: str = ""

    def as_row(self) -> Dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "algorithm": self.algorithm,
            "status": self.status,
            "selected_node": self.selected_node,
            "selected_layer": self.selected_layer,
            "objective": self.objective,
            "time_seconds": self.time_seconds,
            "estimated_cost": self.estimated_cost,
            "feasible": self.feasible,
            "bins": self.bins,
            "moved_services": self.moved_services,
            "reason": self.reason,
            "selected_features": self.selected_features,
            "selected_resources": self.selected_resources,
        }


_VARIANT_SPECS = {
    "edgewise":      {"engine": "milp",    "preprocess": True,  "cr": False},
    "edgewise_cr":   {"engine": "milp",    "preprocess": True,  "cr": True},
    "edgewise_num":  {"engine": "milp",    "preprocess": False, "cr": False},
    "prolog":        {"engine": "greedy",  "preprocess": True,  "cr": False},
    "prolog_cr":     {"engine": "greedy",  "preprocess": True,  "cr": True},
    "prolog_num":    {"engine": "greedy",  "preprocess": False, "cr": False},
}


def default_algorithm_names() -> List[str]:
    return list(_VARIANT_SPECS.keys())


def run_edgewisecr_benchmark(
    scenario_id: str,
    topology_devices,
    request: Mapping[str, Any],
    *,
    algorithms: Optional[Sequence[str]] = None,
    timeout_seconds: Optional[float] = DEFAULT_TIMEOUT_SECONDS,
    last_placement: Optional[Mapping[str, str]] = None,
) -> List[Dict[str, Any]]:
    """Run EdgeWiseCR baseline variants on one existing benchmark scenario."""

    variant_names = list(algorithms or default_algorithm_names())
    results: List[Dict[str, Any]] = []
    for variant in variant_names:
        results.append(
            _run_variant(
                scenario_id=scenario_id,
                variant=variant,
                devices=topology_devices,
                request=request,
                timeout_seconds=timeout_seconds,
                last_placement=last_placement,
            ).as_row()
        )
    return results


def save_benchmark_results_to_csv(
    rows: Iterable[Mapping[str, Any]],
    results_dir: str,
    filename: str = "edgewisecr_results.csv",
) -> str:
    """Append benchmark rows to a CSV file and return the output path."""

    os.makedirs(results_dir, exist_ok=True)
    csv_path = os.path.join(results_dir, filename)
    rows = list(rows)
    if not rows:
        return csv_path

    file_exists = os.path.isfile(csv_path)
    existing_fieldnames: Optional[List[str]] = None
    if file_exists:
        with open(csv_path, mode="r", newline="", encoding="utf-8") as rf:
            existing_fieldnames = csv.DictReader(rf).fieldnames

    fieldnames = list(existing_fieldnames or rows[0].keys())
    for row in rows:
        for key in row.keys():
            if key not in fieldnames:
                fieldnames.append(key)

    with open(csv_path, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        for row in rows:
            full_row = {name: "" for name in fieldnames}
            full_row.update(row)
            writer.writerow(full_row)

    return csv_path


def _run_variant(
    *,
    scenario_id: str,
    variant: str,
    devices,
    request: Mapping[str, Any],
    timeout_seconds: Optional[float],
    last_placement: Optional[Mapping[str, str]],
) -> EdgeWiseSelection:
    spec = _VARIANT_SPECS.get(variant)
    if spec is None:
        return EdgeWiseSelection(
            scenario_id=scenario_id,
            algorithm=variant,
            status="FAILED",
            reason=f"unknown variant {variant}",
        )

    try:
        if spec["engine"] == "milp":
            result: EdgeWiseResult = edgewise_milp_solve(
                devices,
                request,
                preprocess=spec["preprocess"],
                cr=spec["cr"],
                timeout_seconds=timeout_seconds,
                last_placement=last_placement if spec["cr"] else None,
            )
        else:
            result = edgewise_greedy_solve(
                devices,
                request,
                preprocess=spec["preprocess"],
                cr=spec["cr"],
                last_placement=last_placement if spec["cr"] else None,
            )
    except Exception as exc:
        return EdgeWiseSelection(
            scenario_id=scenario_id,
            algorithm=variant,
            status="FAILED",
            feasible=False,
            reason=str(exc),
        )

    return EdgeWiseSelection(
        scenario_id=scenario_id,
        algorithm=variant,
        status=result.status,
        selected_node=str(result.selected_nodes),
        selected_layer=str(result.selected_layers),
        time_seconds=result.time_seconds,
        estimated_cost=result.cost if result.cost != float("inf") else None,
        feasible=result.feasible,
        bins=result.bins,
        moved_services=result.moved_services,
        reason=result.reason,
        selected_features=str(result.selected_features),
        selected_resources=str(result.covered_resources),
    )
