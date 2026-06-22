"""Run adapted EdgeWiseCR variants over the PRIME benchmark scenarios.

Mirrors ``scripts/run_raom4cc_benchmark.py``: loads scenario filters from
the existing PRIME results CSV, maps each scenario to its topology
directory, and runs the six EdgeWiseCR variants.  Results are appended to
``results/edgewisecr_results.csv`` without overwriting existing files.
"""

from __future__ import annotations

import argparse
import ast
import csv
import importlib.util
import json
import re
import sys
import types
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
ALGORITHMS_ROOT = ROOT / "pricing_driven_resource_allocation" / "algorithms"
TOPOLOGIES_DIR = ROOT / "synthetic-dataset" / "synthetic-topologies"
RESULTS_DIR = ROOT / "results"
DEFAULT_RESULTS_CSV = RESULTS_DIR / "results.csv"
DEFAULT_NOTEBOOK = ROOT / "evaluation.ipynb"
DEFAULT_OUTPUT = RESULTS_DIR / "edgewisecr_results.csv"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-csv", type=Path, default=DEFAULT_RESULTS_CSV)
    parser.add_argument("--notebook", type=Path, default=DEFAULT_NOTEBOOK)
    parser.add_argument("--topologies-dir", type=Path, default=TOPOLOGIES_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--limit", type=int, default=None, help="Optional number of scenarios for smoke runs.")
    parser.add_argument("--timeout", type=float, default=60.0, help="MILP solver timeout in seconds.")
    parser.add_argument(
        "--variants",
        nargs="+",
        default=None,
        help="Subset of variants to run (default: all six).",
    )
    args = parser.parse_args()

    output_path = non_overwriting_path(args.output)
    benchmark = load_benchmark_module()
    topology_mapping = load_topology_mapping(args.notebook)
    rows = load_prime_result_rows(args.results_csv)

    if args.limit is not None:
        rows = rows[: args.limit]

    total_scenarios = 0
    total_rows = 0
    missing_mappings: List[str] = []

    for prime_row in rows:
        scenario_id = prime_row["scenario_id"]
        topology_id = topology_mapping.get(scenario_id)
        if topology_id is None:
            missing_mappings.append(scenario_id)
            continue

        devices_path = args.topologies_dir / topology_id / "devices.csv"
        if not devices_path.exists():
            missing_mappings.append(scenario_id)
            continue

        request = request_from_prime_row(prime_row)
        devices = pd.read_csv(devices_path, index_col=0)
        heuristic_rows = benchmark.run_edgewisecr_benchmark(
            scenario_id=scenario_id,
            topology_devices=devices,
            request=request,
            algorithms=args.variants,
            timeout_seconds=args.timeout,
        )
        for row in heuristic_rows:
            row["topology_id"] = topology_id

        append_rows(output_path, heuristic_rows)
        total_scenarios += 1
        total_rows += len(heuristic_rows)

        if total_scenarios % 250 == 0:
            print(f"Processed {total_scenarios} scenarios -> {total_rows} heuristic rows")

    if missing_mappings:
        missing_path = output_path.with_suffix(".missing.txt")
        missing_path.write_text("\n".join(missing_mappings), encoding="utf-8")
        print(f"Missing scenario/topology entries: {len(missing_mappings)} (see {missing_path})")

    print(f"Output CSV: {output_path}")
    print(f"Processed scenarios: {total_scenarios}")
    print(f"Written heuristic rows: {total_rows}")
    return 0


def load_benchmark_module():
    package = types.ModuleType("pricing_driven_resource_allocation")
    package.__path__ = [str(ROOT / "pricing_driven_resource_allocation")]
    sys.modules.setdefault("pricing_driven_resource_allocation", package)

    algorithms_package = types.ModuleType("pricing_driven_resource_allocation.algorithms")
    algorithms_package.__path__ = [str(ALGORITHMS_ROOT)]
    sys.modules.setdefault("pricing_driven_resource_allocation.algorithms", algorithms_package)

    edgewisecr_spec = importlib.util.spec_from_file_location(
        "pricing_driven_resource_allocation.algorithms.edgewisecr",
        ALGORITHMS_ROOT / "edgewisecr.py",
    )
    edgewisecr_module = importlib.util.module_from_spec(edgewisecr_spec)
    sys.modules[edgewisecr_spec.name] = edgewisecr_module
    edgewisecr_spec.loader.exec_module(edgewisecr_module)

    spec = importlib.util.spec_from_file_location(
        "pricing_driven_resource_allocation.algorithms.edgewisecr_benchmark",
        ALGORITHMS_ROOT / "edgewisecr_benchmark.py",
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_topology_mapping(notebook_path: Path) -> Dict[str, str]:
    notebook = json.loads(notebook_path.read_text(encoding="utf-8"))
    mapping: Dict[str, str] = {}
    pattern = re.compile(r"([a-z]+_[a-z]+_[a-z]+_[0-9]+_[0-9]+):\s*([0-9a-f-]{36})")

    for cell in notebook.get("cells", []):
        for output in cell.get("outputs", []):
            texts: Iterable[str] = []
            if "text" in output:
                text_obj = output["text"]
                texts = text_obj if isinstance(text_obj, list) else [text_obj]
            elif "data" in output and "text/plain" in output["data"]:
                text_obj = output["data"]["text/plain"]
                texts = text_obj if isinstance(text_obj, list) else [text_obj]

            for text in texts:
                for match in pattern.finditer(text):
                    mapping[match.group(1)] = match.group(2)
    return mapping


def load_prime_result_rows(results_csv: Path) -> List[Mapping[str, str]]:
    with results_csv.open(mode="r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def request_from_prime_row(row: Mapping[str, str]) -> Dict[str, object]:
    usage_limits: Dict[str, float] = {}
    for key, value in row.items():
        if not key.startswith("filter_usageLimits_") or value in ("", None):
            continue
        resource = key[len("filter_usageLimits_") :]
        try:
            numeric_value = float(value)
            usage_limits[resource] = int(numeric_value) if numeric_value.is_integer() else numeric_value
        except ValueError:
            continue

    return {
        "maxPrice": parse_number(row.get("filter_maxPrice")),
        "maxSubscriptionSize": parse_int(row.get("filter_maxSubscriptionSize")),
        "features": parse_literal(row.get("filter_features")) or [],
        "usageLimits": usage_limits,
    }


def append_rows(output_path: Path, rows: List[Mapping[str, object]]) -> None:
    if not rows:
        return
    output_path.parent.mkdir(parents=True, exist_ok=True)
    file_exists = output_path.exists()
    fieldnames = list(rows[0].keys())

    if file_exists:
        with output_path.open(mode="r", newline="", encoding="utf-8") as f:
            existing = csv.DictReader(f).fieldnames
        if existing:
            fieldnames = list(existing)
            for row in rows:
                for key in row.keys():
                    if key not in fieldnames:
                        fieldnames.append(key)

    with output_path.open(mode="a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        for row in rows:
            full_row = {name: "" for name in fieldnames}
            full_row.update(row)
            writer.writerow(full_row)


def non_overwriting_path(path: Path) -> Path:
    if not path.exists():
        return path
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return path.with_name(f"{path.stem}_{stamp}{path.suffix}")


def parse_literal(value: Optional[str]):
    if not value:
        return None
    try:
        return ast.literal_eval(value)
    except (SyntaxError, ValueError):
        return None


def parse_number(value: Optional[str]):
    if value in ("", None):
        return None
    try:
        numeric_value = float(value)
        return int(numeric_value) if numeric_value.is_integer() else numeric_value
    except ValueError:
        return None


def parse_int(value: Optional[str]):
    parsed = parse_number(value)
    return int(parsed) if parsed is not None else None


if __name__ == "__main__":
    raise SystemExit(main())
