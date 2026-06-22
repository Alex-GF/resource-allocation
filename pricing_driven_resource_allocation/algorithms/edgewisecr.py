"""Core EdgeWiseCR algorithm port for the pricing-driven benchmark.

This module ports the two algorithmic cores of EdgeWiseCR to plain Python:

- ``edgewise_milp_solve``: the hybrid declarative + MILP placement.  The
  declarative stage is replaced by a Python filter that keeps only the
  candidate nodes compatible with the request (device types, providers,
  non-zero capacity).  The MILP stage is preserved verbatim using
  OR-Tools' SCIP backend.

- ``edgewise_greedy_solve``: a Python port of the ``binpack.pl`` greedy
  bin-packing heuristic used by the paper's pure-Prolog variant.

Both solvers operate on the same topology DataFrame and request dict used
by the pricing-driven benchmark and the RAOM4CC baselines, so their output
is evaluated under the same ``minimize_cost`` objective.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from ortools.linear_solver import pywraplp


SOLVER_NAME = "SCIP"
DEFAULT_TIMEOUT_SECONDS = 60.0


@dataclass(frozen=True)
class EdgeWiseResult:
    """Outcome of running an EdgeWiseCR variant on one scenario."""

    placement: Dict[str, str]
    cost: float
    time_seconds: float
    bins: int
    status: str
    feasible: bool
    reason: str = ""
    covered_resources: Dict[str, float] = field(default_factory=dict)
    selected_nodes: List[str] = field(default_factory=list)
    selected_layers: List[str] = field(default_factory=list)
    selected_features: List[str] = field(default_factory=list)
    moved_services: int = 0


def edgewise_milp_solve(
    devices,
    request: Mapping[str, Any],
    *,
    preprocess: bool = True,
    cr: bool = False,
    timeout_seconds: Optional[float] = DEFAULT_TIMEOUT_SECONDS,
    last_placement: Optional[Mapping[str, str]] = None,
    layer_column: str = "global_group",
    tolerance: float = 1e-6,
) -> EdgeWiseResult:
    """Hybrid declarative + MILP placement (EdgeWise / EdgeWiseCR).

    Parameters
    ----------
    devices:
        Topology DataFrame with one row per candidate node.  Must contain
        ``available_*`` capacity columns, ``unit_price_available_*`` price
        columns, and a device-type / provider label.
    request:
        Pricing-driven request dict with ``usageLimits`` (or ``resources``),
        ``features``/``device_types``, ``providers_to_consider``,
        ``maxSubscriptionSize``/``max_devices``, and ``maxPrice``/``budget``.
    preprocess:
        When True (default), only nodes compatible with the request
        constraints are forwarded to the MILP.  When False, all nodes are
        forwarded, mirroring the paper's ``_num`` configuration.
    cr:
        Continuous Reasoning flag.  In the static benchmark there is a
        single tick, so CR only affects ``moved_services`` accounting and
        the variant name.
    timeout_seconds:
        Solver wall-clock limit.  ``None`` lets SCIP run to optimality.
    last_placement:
        Previous placement used by CR to count moved services.
    """

    import time as _time

    start = _time.perf_counter()

    demand = _resource_demand(request)
    max_nodes = _max_subscription_size(request) or len(devices)
    budget = _budget(request)

    candidate_rows = _filter_candidates(devices, request, preprocess=preprocess, demand=demand)
    if not candidate_rows:
        elapsed = _time.perf_counter() - start
        return EdgeWiseResult(
            placement={},
            cost=float("inf"),
            time_seconds=elapsed,
            bins=0,
            status="INFEASIBLE",
            feasible=False,
            reason="no candidate node matched the request",
        )

    nids = [row["__node_id"] for row in candidate_rows]
    resources = list(demand.keys())
    N = len(nids)
    R = len(resources)

    solver = pywraplp.Solver.CreateSolver(SOLVER_NAME)
    if solver is None:
        elapsed = _time.perf_counter() - start
        return EdgeWiseResult(
            placement={},
            cost=float("inf"),
            time_seconds=elapsed,
            bins=0,
            status="NO_SOLVER",
            feasible=False,
            reason="SCIP backend unavailable",
        )
    if timeout_seconds is not None:
        solver.SetTimeLimit(int(timeout_seconds * 1000))

    b = {j: solver.BoolVar(f"b_{nids[j]}") for j in range(N)}
    a = {
        (j, r): solver.NumVar(0.0, solver.infinity(), f"a_{nids[j]}_{resources[r]}")
        for j in range(N)
        for r in range(R)
    }

    capacity = {
        (j, r): _capacity_for(candidate_rows[j], resources[r]) for j in range(N) for r in range(R)
    }
    price = {
        (j, r): _price_for(candidate_rows[j], resources[r]) for j in range(N) for r in range(R)
    }

    for j in range(N):
        for r in range(R):
            solver.Add(a[(j, r)] <= capacity[(j, r)] * b[j], name=f"link_{nids[j]}_{resources[r]}")

    for r in range(R):
        solver.Add(
            solver.Sum([a[(j, r)] for j in range(N)]) >= demand[resources[r]],
            name=f"cover_{resources[r]}",
        )

    solver.Add(solver.Sum([b[j] for j in range(N)]) <= max_nodes, name="max_nodes")

    if budget is not None:
        solver.Add(
            solver.Sum(
                [price[(j, r)] * a[(j, r)] for j in range(N) for r in range(R)]
            )
            <= budget,
            name="budget",
        )

    solver.Minimize(
        solver.Sum([price[(j, r)] * a[(j, r)] for j in range(N) for r in range(R)])
    )

    status = solver.Solve()
    elapsed = _time.perf_counter() - start

    if status == pywraplp.Solver.OPTIMAL or status == pywraplp.Solver.FEASIBLE:
        placement, covered, selected_idx = _extract_placement(
            a, b, nids, resources, candidate_rows, demand, tolerance
        )
        cost = solver.Objective().Value()
        feasible, reason = _check_feasibility(
            placement, covered, demand, len(selected_idx), max_nodes, cost, budget, tolerance
        )
        selected_nodes = [nids[j] for j in selected_idx]
        selected_layers = [_row_layer(candidate_rows[j], layer_column) for j in selected_idx]
        selected_features = [str(candidate_rows[j].get("device_type", "")) for j in selected_idx]
        moved = _count_moved_services(placement, last_placement) if cr else 0
        return EdgeWiseResult(
            placement=placement,
            cost=cost,
            time_seconds=elapsed,
            bins=len(selected_nodes),
            status="OPTIMAL" if status == pywraplp.Solver.OPTIMAL else "FEASIBLE",
            feasible=feasible,
            reason=reason,
            covered_resources=covered,
            selected_nodes=selected_nodes,
            selected_layers=selected_layers,
            selected_features=selected_features,
            moved_services=moved,
        )

    if status == pywraplp.Solver.INFEASIBLE:
        return EdgeWiseResult(
            placement={},
            cost=float("inf"),
            time_seconds=elapsed,
            bins=0,
            status="INFEASIBLE",
            feasible=False,
            reason="solver reported infeasible",
        )

    return EdgeWiseResult(
        placement={},
        cost=float("inf"),
        time_seconds=elapsed,
        bins=0,
        status="TIMEOUT" if status == pywraplp.Solver.ABNORMAL else "NOT_SOLVED",
        feasible=False,
        reason=f"solver status code {status}",
    )


def edgewise_greedy_solve(
    devices,
    request: Mapping[str, Any],
    *,
    preprocess: bool = True,
    cr: bool = False,
    last_placement: Optional[Mapping[str, str]] = None,
    layer_column: str = "global_group",
    tolerance: float = 1e-6,
) -> EdgeWiseResult:
    """Pure-heuristic greedy bin-packing placement (Prolog variant port).

    Mirrors ``binpack.pl``: rank resources by hardness, rank nodes by
    descending capacity (``1/HWCaps``), greedily assign preferring already
    selected nodes (bin-packing), enforce budget and max-nodes.
    """

    import time as _time

    start = _time.perf_counter()

    demand = _resource_demand(request)
    max_nodes = _max_subscription_size(request) or len(devices)
    budget = _budget(request)

    candidate_rows = _filter_candidates(devices, request, preprocess=preprocess, demand=demand)
    if not candidate_rows:
        elapsed = _time.perf_counter() - start
        return EdgeWiseResult(
            placement={},
            cost=float("inf"),
            time_seconds=elapsed,
            bins=0,
            status="INFEASIBLE",
            feasible=False,
            reason="no candidate node matched the request",
        )

    resources = list(demand.keys())
    resource_order = _rank_resources_by_hardness(candidate_rows, resources)
    node_order = _rank_nodes_by_capacity(candidate_rows, resources)

    covered: Dict[str, float] = {r: 0.0 for r in resources}
    selected: List[int] = []
    total_cost = 0.0
    placement: Dict[str, str] = {}

    for resource in resource_order:
        remaining = max(0.0, demand[resource] - covered[resource])
        if remaining <= tolerance:
            continue
        for node_idx in _greedy_node_iterator(node_order, selected):
            if remaining <= tolerance:
                break
            if len(selected) >= max_nodes and node_idx not in selected:
                continue
            capacity = _capacity_for(candidate_rows[node_idx], resource)
            if capacity <= tolerance:
                continue
            price = _price_for(candidate_rows[node_idx], resource)
            alloc = min(remaining, capacity)
            if node_idx not in selected:
                if budget is not None and total_cost + alloc * price > budget + tolerance:
                    continue
                selected.append(node_idx)
            else:
                if budget is not None and total_cost + alloc * price > budget + tolerance:
                    continue
            covered[resource] += alloc
            total_cost += alloc * price
            remaining = max(0.0, demand[resource] - covered[resource])

    selected_nodes = [candidate_rows[j]["__node_id"] for j in selected]
    selected_layers = [_row_layer(candidate_rows[j], layer_column) for j in selected]
    selected_features = [str(candidate_rows[j].get("device_type", "")) for j in selected]

    for idx, node_id in enumerate(selected_nodes):
        placement[f"slot_{idx}"] = node_id

    feasible, reason = _check_feasibility(
        placement, covered, demand, len(selected), max_nodes, total_cost, budget, tolerance
    )
    moved = _count_moved_services(placement, last_placement) if cr else 0
    elapsed = _time.perf_counter() - start

    status = "COMPLETED" if feasible else "INFEASIBLE"
    return EdgeWiseResult(
        placement=placement,
        cost=total_cost,
        time_seconds=elapsed,
        bins=len(selected_nodes),
        status=status,
        feasible=feasible,
        reason=reason,
        covered_resources=covered,
        selected_nodes=selected_nodes,
        selected_layers=selected_layers,
        selected_features=selected_features,
        moved_services=moved,
    )


def _filter_candidates(
    devices,
    request: Mapping[str, Any],
    *,
    preprocess: bool,
    demand: Mapping[str, float],
) -> List[Dict[str, Any]]:
    """Return the list of candidate node rows, optionally filtered.

    When ``preprocess`` is True, mirror the Prolog ``findCompatibles``:
    keep only nodes whose device type / provider match the request and
    that have non-zero capacity for at least one demanded resource.
    """

    rows: List[Dict[str, Any]] = []
    device_types = request.get("device_types") or request.get("features")
    providers = request.get("providers_to_consider")

    for index, row in devices.iterrows():
        node_id = str(index)
        record = {"__node_id": node_id, "__row_index": index}
        for col in devices.columns:
            record[str(col)] = row[col]

        if preprocess:
            if device_types:
                dtype = str(record.get("device_type", ""))
                if dtype not in device_types:
                    continue
            if providers:
                provider = str(record.get("provider", "")).lower()
                allowed = {str(p).lower() for p in providers}
                if provider not in allowed:
                    continue
            has_capacity = any(
                _capacity_for(record, resource) > 0 for resource in demand
            )
            if not has_capacity:
                continue

        rows.append(record)
    return rows


def _resource_demand(request: Mapping[str, Any]) -> Dict[str, float]:
    resources = request.get("resources")
    if not isinstance(resources, Mapping):
        resources = request.get("usageLimits")
        if not isinstance(resources, Mapping):
            resources = {}

    demand: Dict[str, float] = {}
    for resource, value in resources.items():
        name = str(resource)
        if name == "distance" or not name.startswith("available_"):
            continue
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            continue
        if numeric > 0:
            demand[name] = numeric
    return demand


def _budget(request: Mapping[str, Any]) -> Optional[float]:
    value = request.get("budget", request.get("maxPrice"))
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _max_subscription_size(request: Mapping[str, Any]) -> Optional[int]:
    value = request.get("max_devices", request.get("maxSubscriptionSize"))
    if value is None:
        return None
    try:
        return max(1, int(value))
    except (TypeError, ValueError):
        return None


def _capacity_for(record: Mapping[str, Any], resource: str) -> float:
    try:
        return max(0.0, float(record.get(resource, 0.0) or 0.0))
    except (TypeError, ValueError):
        return 0.0


def _price_for(record: Mapping[str, Any], resource: str) -> float:
    key = f"unit_price_{resource}"
    try:
        return float(record.get(key, 0.0) or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _row_layer(record: Mapping[str, Any], layer_column: str) -> str:
    group = record.get(layer_column)
    if group is None:
        return "unknown"
    try:
        gi = int(group)
    except (TypeError, ValueError):
        return str(group)
    if gi == 1:
        return "mist"
    if gi == 3:
        return "cloud"
    return "edge"


def _rank_resources_by_hardness(
    candidate_rows: Sequence[Mapping[str, Any]], resources: Sequence[str]
) -> List[str]:
    coverage_counts = {
        r: sum(1 for row in candidate_rows if _capacity_for(row, r) > 0) for r in resources
    }
    return sorted(resources, key=lambda r: (coverage_counts[r], r))


def _rank_nodes_by_capacity(
    candidate_rows: Sequence[Mapping[str, Any]], resources: Sequence[str]
) -> List[int]:
    def total_capacity(idx: int) -> float:
        row = candidate_rows[idx]
        return sum(_capacity_for(row, r) for r in resources)

    return sorted(
        range(len(candidate_rows)),
        key=lambda idx: (-total_capacity(idx), candidate_rows[idx]["__node_id"]),
    )


def _greedy_node_iterator(
    node_order: Sequence[int], selected: Sequence[int]
) -> List[int]:
    selected_set = set(selected)
    selected_ordered = [idx for idx in node_order if idx in selected_set]
    remaining = [idx for idx in node_order if idx not in selected_set]
    return selected_ordered + remaining


def _extract_placement(
    a: Dict,
    b: Dict,
    nids: List[str],
    resources: List[str],
    candidate_rows: List[Mapping[str, Any]],
    demand: Mapping[str, float],
    tolerance: float,
) -> Tuple[Dict[str, str], Dict[str, float], List[int]]:
    selected_idx: List[int] = []
    for j in range(len(nids)):
        if b[j].solution_value() > 0.5:
            selected_idx.append(j)

    covered: Dict[str, float] = {r: 0.0 for r in resources}
    for j in selected_idx:
        for r_idx, resource in enumerate(resources):
            val = a[(j, r_idx)].solution_value()
            if val > tolerance:
                covered[resource] += val

    placement: Dict[str, str] = {}
    for slot, j in enumerate(selected_idx):
        placement[f"slot_{slot}"] = nids[j]
    return placement, covered, selected_idx


def _check_feasibility(
    placement: Mapping[str, str],
    covered: Mapping[str, float],
    demand: Mapping[str, float],
    selected_count: int,
    max_nodes: int,
    total_cost: float,
    budget: Optional[float],
    tolerance: float,
) -> Tuple[bool, str]:
    if not placement:
        return False, "no node selected"
    for resource, requested in demand.items():
        if covered.get(resource, 0.0) + tolerance < requested:
            return False, f"resource {resource} requires {requested}, covered {covered.get(resource, 0.0)}"
    if selected_count > max_nodes:
        return False, f"selected {selected_count} nodes, max allowed {max_nodes}"
    if budget is not None and total_cost > budget + tolerance:
        return False, f"cost {total_cost} exceeds budget {budget}"
    return True, ""


def _count_moved_services(
    current: Mapping[str, str], previous: Optional[Mapping[str, str]]
) -> int:
    if previous is None:
        return 0
    current_nodes = set(current.values())
    previous_nodes = set(previous.values())
    return len(previous_nodes - current_nodes)
