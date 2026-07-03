"""Benchmark helpers for RAOM4CC algorithms.

These helpers run the offloading algorithms as heuristic baselines on the
existing pricing-driven resource-allocation scenarios.  They intentionally do
not generate SUMO mobility traces; callers provide the topology dataframe and
the already generated demand/request objects used by the paper benchmark.
"""

from __future__ import annotations

import csv
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from .raom4cc import (
    ComputingLayer,
    NetworkLink,
    Node,
    OrchestrationContext,
    Task,
    build_context_from_topology,
    estimate_delay,
    estimate_energy,
)


DEFAULT_TASK_PROFILES: Dict[str, Dict[str, float]] = {
    # Table 3 in the RAOM4CC paper, mapped to this benchmark's app labels.
    "health": {
        "input_size_bytes": 20 * 1024,
        "output_size_bytes": 2 * 1024,
        "cpu_mi": 2_000,
        "latency_constraint_seconds": 0.3,
    },
    "robot": {
        "input_size_bytes": 20 * 1024,
        "output_size_bytes": 2 * 1024,
        "cpu_mi": 2_000,
        "latency_constraint_seconds": 0.3,
    },
    "mixed_reality": {
        "input_size_bytes": 500 * 1024,
        "output_size_bytes": 100 * 1024,
        "cpu_mi": 4_000,
        "latency_constraint_seconds": 0.5,
    },
    "vr": {
        "input_size_bytes": 500 * 1024,
        "output_size_bytes": 100 * 1024,
        "cpu_mi": 4_000,
        "latency_constraint_seconds": 0.5,
    },
    "computer_vision": {
        "input_size_bytes": 200 * 1024,
        "output_size_bytes": 40 * 1024,
        "cpu_mi": 12_000,
        "latency_constraint_seconds": 1.5,
    },
    "cctv": {
        "input_size_bytes": 200 * 1024,
        "output_size_bytes": 40 * 1024,
        "cpu_mi": 12_000,
        "latency_constraint_seconds": 1.5,
    },
    "video": {
        "input_size_bytes": 200 * 1024,
        "output_size_bytes": 40 * 1024,
        "cpu_mi": 12_000,
        "latency_constraint_seconds": 1.5,
    },
    "lidar": {
        "input_size_bytes": 200 * 1024,
        "output_size_bytes": 40 * 1024,
        "cpu_mi": 12_000,
        "latency_constraint_seconds": 1.5,
    },
    "nlp": {
        "input_size_bytes": 500 * 1024,
        "output_size_bytes": 20 * 1024,
        "cpu_mi": 20_000,
        "latency_constraint_seconds": 2.5,
    },
}


@dataclass(frozen=True)
class BenchmarkSelection:
    """Result of running one RAOM4CC baseline on one scenario."""

    scenario_id: str
    algorithm: str
    status: str
    selected_node: str = ""
    selected_layer: str = ""
    objective: str = "minimize_cost"
    time_seconds: float = 0.0
    estimated_delay_seconds: Optional[float] = None
    estimated_energy_joules: Optional[float] = None
    estimated_cost: Optional[float] = None
    feasible: bool = False
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
            "estimated_delay_seconds": self.estimated_delay_seconds,
            "estimated_energy_joules": self.estimated_energy_joules,
            "estimated_cost": self.estimated_cost,
            "feasible": self.feasible,
            "reason": self.reason,
            "selected_features": self.selected_features,
            "selected_resources": self.selected_resources,
        }


@dataclass(frozen=True)
class _Deployment:
    nodes: List[Node]
    covered_resources: Dict[str, float]
    cost: float
    delay_seconds: float
    energy_joules: float
    feasible: bool
    reason: str


def representative_task_from_request(
    scenario_id: str,
    request: Mapping[str, Any],
    *,
    app: Optional[str] = None,
    origin_node_id: str,
    task_profiles: Optional[Mapping[str, Mapping[str, float]]] = None,
    cpu_mi_per_required_core: float = 1_000.0,
) -> Task:
    """Create a representative task from the benchmark's aggregate request."""

    resources = _request_resources(request)
    required_cores = max(1.0, float(resources.get("available_cpu_cores", 1.0) or 1.0))
    profiles = task_profiles or DEFAULT_TASK_PROFILES
    profile = profiles.get(str(app).lower(), {}) if app is not None else {}

    cpu_mi = float(profile.get("cpu_mi", required_cores * cpu_mi_per_required_core))
    return Task(
        task_id=scenario_id,
        origin_node_id=origin_node_id,
        cpu_mi=cpu_mi,
        input_size_bytes=float(profile.get("input_size_bytes", 0.0)),
        output_size_bytes=float(profile.get("output_size_bytes", 0.0)),
        required_cores=required_cores,
        latency_constraint_seconds=profile.get("latency_constraint_seconds"),
        metadata={"request_resources": dict(resources)},
    )


def run_raom4cc_benchmark(
    scenario_id: str,
    topology_devices,
    request: Mapping[str, Any],
    *,
    app: Optional[str] = None,
    algorithms: Optional[Sequence[str]] = None,
    computing_layers: Optional[Sequence[ComputingLayer]] = None,
    cap_mapping: Optional[Mapping[str, str]] = None,
    network_links: Optional[Mapping[Tuple[str, ComputingLayer], NetworkLink]] = None,
    alpha: float = 1.0,
) -> List[Dict[str, Any]]:
    """Run RAOM4CC baselines on one existing benchmark scenario."""

    context = build_context_from_topology(topology_devices, cap_mapping=cap_mapping)
    if network_links:
        context.network_links.update(network_links)

    available_layers = _available_layers(context)
    layers = list(computing_layers or available_layers)
    layers = [layer for layer in layers if layer in available_layers]
    if not layers:
        raise ValueError("No requested computing layers are available in the topology.")

    origin_node_id = _choose_origin_node(context)
    task = representative_task_from_request(
        scenario_id,
        request,
        app=app,
        origin_node_id=origin_node_id,
    )

    algorithm_names = list(algorithms or default_algorithm_names())
    results: List[Dict[str, Any]] = []
    for algorithm in algorithm_names:
        results.append(
            _run_algorithm(
                scenario_id=scenario_id,
                algorithm=algorithm,
                task=task,
                context=context,
                request=request,
                computing_layers=layers,
                alpha=alpha,
            ).as_row()
        )
    return results


def default_algorithm_names() -> List[str]:
    return [
        "one_layer_mist",
        "one_layer_edge",
        "one_layer_cloud",
        "round_robin",
        "delay_heuristics",
        "delay_energy_heuristics",
        "best_fit",
        "best_fit_delay",
        "best_fit_delay_energy",
    ]


def save_benchmark_results_to_csv(
    rows: Iterable[Mapping[str, Any]],
    results_dir: str,
    filename: str = "raom4cc_benchmark_results.csv",
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


def _run_algorithm(
    *,
    scenario_id: str,
    algorithm: str,
    task: Task,
    context: OrchestrationContext,
    request: Mapping[str, Any],
    computing_layers: Sequence[ComputingLayer],
    alpha: float,
) -> BenchmarkSelection:
    start = time.perf_counter()
    try:
        ordered_nodes = _candidate_order(algorithm, task, context, request, computing_layers, alpha)
        deployment = _build_deployment(ordered_nodes, request, task, context)
        elapsed = time.perf_counter() - start
        return BenchmarkSelection(
            scenario_id=scenario_id,
            algorithm=algorithm,
            status="COMPLETED",
            selected_node=str([node.node_id for node in deployment.nodes]),
            selected_layer=str([node.layer.value for node in deployment.nodes]),
            time_seconds=elapsed,
            estimated_delay_seconds=deployment.delay_seconds,
            estimated_energy_joules=deployment.energy_joules,
            estimated_cost=deployment.cost,
            feasible=deployment.feasible,
            reason=deployment.reason,
            selected_features=str([node.metadata.get("device_type") for node in deployment.nodes]),
            selected_resources=str(deployment.covered_resources),
        )
    except Exception as exc:
        elapsed = time.perf_counter() - start
        return BenchmarkSelection(
            scenario_id=scenario_id,
            algorithm=algorithm,
            status="FAILED",
            time_seconds=elapsed,
            feasible=False,
            reason=str(exc),
        )


def _candidate_order(
    algorithm: str,
    task: Task,
    context: OrchestrationContext,
    request: Mapping[str, Any],
    computing_layers: Sequence[ComputingLayer],
    alpha: float,
) -> List[Node]:
    normalized = algorithm.lower()
    if normalized == "one_layer_mist":
        return _nodes_for_layers(context, request, [ComputingLayer.MIST])
    if normalized == "one_layer_edge":
        return _nodes_for_layers(context, request, [ComputingLayer.EDGE])
    if normalized == "one_layer_cloud":
        return _nodes_for_layers(context, request, [ComputingLayer.CLOUD])
    if normalized == "round_robin":
        return _interleave_layers(context, request, computing_layers)
    if normalized == "delay_heuristics":
        layers = sorted(computing_layers, key=lambda layer: estimate_delay(task, layer, context))
        return _nodes_for_layers(context, request, layers)
    if normalized == "delay_energy_heuristics":
        layers = _delay_energy_layer_order(task, context, computing_layers, alpha)
        return _nodes_for_layers(context, request, layers)
    if normalized == "best_fit":
        return _best_fit_order(context, request)
    if normalized == "best_fit_delay":
        fastest_layer = min(computing_layers, key=lambda layer: estimate_delay(task, layer, context))
        if fastest_layer is ComputingLayer.MIST:
            return _nodes_for_layers(context, request, [ComputingLayer.MIST]) + _best_fit_order(context, request)
        return _best_fit_order(context, request)
    if normalized == "best_fit_delay_energy":
        preferred_layer = _delay_energy_layer_order(task, context, computing_layers, alpha)[0]
        if preferred_layer is ComputingLayer.MIST:
            return _nodes_for_layers(context, request, [ComputingLayer.MIST]) + _best_fit_order(context, request)
        return _best_fit_order(context, request)
    raise ValueError(f"Unknown RAOM4CC benchmark algorithm: {algorithm}")


def _available_layers(context: OrchestrationContext) -> List[ComputingLayer]:
    seen = {node.layer for node in context.nodes.values()}
    return [layer for layer in (ComputingLayer.MIST, ComputingLayer.EDGE, ComputingLayer.CLOUD) if layer in seen]


def _choose_origin_node(context: OrchestrationContext) -> str:
    mist_nodes = [node for node in context.nodes.values() if node.layer is ComputingLayer.MIST]
    candidates = mist_nodes or list(context.nodes.values())
    return min(candidates, key=lambda node: (node.queue_length, node.node_id)).node_id


def _build_deployment(
    ordered_nodes: Sequence[Node],
    request: Mapping[str, Any],
    task: Task,
    context: OrchestrationContext,
) -> _Deployment:
    demand = _resource_demand(request)
    max_nodes = _max_subscription_size(request) or len(ordered_nodes)
    budget = _budget(request)

    selected: List[Node] = []
    covered = {resource: 0.0 for resource in demand}
    total_cost = 0.0
    base_rank = {node.node_id: index for index, node in enumerate(_dedupe_nodes(ordered_nodes))}
    remaining_nodes = _dedupe_nodes(ordered_nodes)

    while len(selected) < max_nodes and not _demand_is_covered(demand, covered):
        node = _choose_next_node(
            remaining_nodes=remaining_nodes,
            demand=demand,
            covered=covered,
            selected_count=len(selected),
            max_nodes=max_nodes,
            base_rank=base_rank,
        )
        if node is None:
            break

        remaining_nodes = [candidate for candidate in remaining_nodes if candidate.node_id != node.node_id]
        if len(selected) >= max_nodes:
            break

        allocation = _node_allocation(node, demand, covered)
        selected.append(node)
        for resource, amount in allocation.items():
            covered[resource] += amount
        total_cost += _allocation_cost(node, allocation)

    if not demand and not selected:
        fallback = next((node for node in _dedupe_nodes(ordered_nodes) if _node_matches_request(node, request)), None)
        if fallback is not None:
            selected.append(fallback)

    delay = max((_estimate_delay_for_node(task, node, context) for node in selected), default=0.0)
    energy = sum(_estimate_energy_for_node(task, node, context) for node in selected)

    feasible, reason = _deployment_feasibility(
        selected=selected,
        demand=demand,
        covered=covered,
        total_cost=total_cost,
        budget=budget,
        max_nodes=max_nodes,
    )

    return _Deployment(
        nodes=selected,
        covered_resources=covered,
        cost=total_cost,
        delay_seconds=delay,
        energy_joules=energy,
        feasible=feasible,
        reason=reason,
    )


def _choose_next_node(
    *,
    remaining_nodes: Sequence[Node],
    demand: Mapping[str, float],
    covered: Mapping[str, float],
    selected_count: int,
    max_nodes: int,
    base_rank: Mapping[str, int],
) -> Optional[Node]:
    candidates = [
        node
        for node in remaining_nodes
        if _node_allocation(node, demand, covered)
    ]
    if not candidates:
        return None

    slots_after_pick = max_nodes - selected_count - 1
    viable: List[Node] = []
    completing: List[Node] = []
    for node in candidates:
        allocation = _node_allocation(node, demand, covered)
        covered_after = dict(covered)
        for resource, amount in allocation.items():
            covered_after[resource] = covered_after.get(resource, 0.0) + amount

        if _demand_is_covered(demand, covered_after):
            completing.append(node)
            viable.append(node)
            continue

        remaining_after = [candidate for candidate in candidates if candidate.node_id != node.node_id]
        if _can_still_cover(demand, covered_after, remaining_after, slots_after_pick):
            viable.append(node)

    if completing:
        return min(completing, key=lambda node: (_allocation_unit_cost(node, demand, covered), base_rank[node.node_id]))

    if viable:
        return min(viable, key=lambda node: (base_rank[node.node_id], _allocation_unit_cost(node, demand, covered)))

    return max(
        candidates,
        key=lambda node: (
            _coverage_gain(node, demand, covered),
            -_allocation_unit_cost(node, demand, covered),
            -base_rank[node.node_id],
        ),
    )


def _can_still_cover(
    demand: Mapping[str, float],
    covered: Mapping[str, float],
    remaining_nodes: Sequence[Node],
    remaining_slots: int,
) -> bool:
    if _demand_is_covered(demand, covered):
        return True
    if remaining_slots <= 0:
        return False

    for resource, requested in demand.items():
        missing = max(0.0, requested - covered.get(resource, 0.0))
        if missing <= 0:
            continue
        capacities = sorted(
            (_node_resource_capacity(node, resource) for node in remaining_nodes),
            reverse=True,
        )
        if sum(capacities[:remaining_slots]) + 1e-9 < missing:
            return False
    return True


def _deployment_feasibility(
    *,
    selected: Sequence[Node],
    demand: Mapping[str, float],
    covered: Mapping[str, float],
    total_cost: float,
    budget: Optional[float],
    max_nodes: int,
) -> Tuple[bool, str]:
    if not selected:
        return False, "no candidate node matched the request"

    for resource, requested in demand.items():
        available = covered.get(resource, 0.0)
        if available + 1e-9 < requested:
            return False, f"resource {resource} requires {requested}, covered {available}"

    if len(selected) > max_nodes:
        return False, f"selected {len(selected)} nodes, max allowed {max_nodes}"

    if budget is not None and total_cost > budget:
        return False, f"cost {total_cost} exceeds budget {budget}"

    return True, ""


def _node_allocation(
    node: Node,
    demand: Mapping[str, float],
    covered: Mapping[str, float],
) -> Dict[str, float]:
    resources = node.metadata.get("resources", {})
    if not isinstance(resources, Mapping):
        return {}

    allocation: Dict[str, float] = {}
    for resource, requested in demand.items():
        remaining = max(0.0, requested - covered.get(resource, 0.0))
        if remaining <= 0:
            continue
        try:
            capacity = max(0.0, float(resources.get(resource, 0.0)))
        except (TypeError, ValueError):
            capacity = 0.0
        amount = min(remaining, capacity)
        if amount > 0:
            allocation[resource] = amount
    return allocation


def _allocation_cost(node: Node, allocation: Mapping[str, float]) -> float:
    prices = node.metadata.get("unit_prices", {})
    if not isinstance(prices, Mapping):
        return 0.0
    total = 0.0
    for resource, amount in allocation.items():
        try:
            total += amount * float(prices.get(resource, 0.0))
        except (TypeError, ValueError):
            continue
    return total


def _allocation_unit_cost(
    node: Node,
    demand: Mapping[str, float],
    covered: Mapping[str, float],
) -> float:
    allocation = _node_allocation(node, demand, covered)
    total_allocated = sum(allocation.values())
    if total_allocated <= 0:
        return float("inf")
    return _allocation_cost(node, allocation) / total_allocated


def _coverage_gain(
    node: Node,
    demand: Mapping[str, float],
    covered: Mapping[str, float],
) -> float:
    allocation = _node_allocation(node, demand, covered)
    if not demand:
        return 0.0
    score = 0.0
    for resource, requested in demand.items():
        if requested <= 0:
            continue
        score += allocation.get(resource, 0.0) / requested
    return score / len(demand)


def _node_resource_capacity(node: Node, resource: str) -> float:
    resources = node.metadata.get("resources", {})
    if not isinstance(resources, Mapping):
        return 0.0
    try:
        return max(0.0, float(resources.get(resource, 0.0)))
    except (TypeError, ValueError):
        return 0.0


def _node_matches_request(node: Node, request: Mapping[str, Any]) -> bool:
    device_types = request.get("device_types") or request.get("features")
    if device_types and node.metadata.get("device_type") not in device_types:
        return False

    providers = request.get("providers_to_consider")
    if providers:
        provider = str(node.metadata.get("provider", "")).lower()
        allowed = {str(item).lower() for item in providers}
        if provider not in allowed:
            return False

    return True


def _nodes_for_layers(
    context: OrchestrationContext,
    request: Mapping[str, Any],
    layers: Sequence[ComputingLayer],
) -> List[Node]:
    demand = _resource_demand(request)
    order = {layer: idx for idx, layer in enumerate(layers)}
    nodes = [
        node
        for node in context.nodes.values()
        if node.layer in order and _node_matches_request(node, request)
    ]
    return sorted(nodes, key=lambda node: (order[node.layer], _node_unit_cost(node, demand), node.node_id))


def _interleave_layers(
    context: OrchestrationContext,
    request: Mapping[str, Any],
    layers: Sequence[ComputingLayer],
) -> List[Node]:
    by_layer = {layer: _nodes_for_layers(context, request, [layer]) for layer in layers}
    ordered: List[Node] = []
    max_len = max((len(nodes) for nodes in by_layer.values()), default=0)
    for index in range(max_len):
        for layer in layers:
            nodes = by_layer.get(layer, [])
            if index < len(nodes):
                ordered.append(nodes[index])
    return ordered


def _best_fit_order(context: OrchestrationContext, request: Mapping[str, Any]) -> List[Node]:
    demand = _resource_demand(request)
    edge = [
        node
        for node in context.nodes.values()
        if node.layer is ComputingLayer.EDGE and _node_matches_request(node, request)
    ]
    fallback = [
        node
        for node in context.nodes.values()
        if node.layer is not ComputingLayer.EDGE and _node_matches_request(node, request)
    ]
    edge_order = sorted(edge, key=lambda node: (-node.reserved_cores, _node_unit_cost(node, demand), node.node_id))
    fallback_order = sorted(
        fallback,
        key=lambda node: (node.layer is not ComputingLayer.CLOUD, _node_unit_cost(node, demand), node.node_id),
    )
    return edge_order + fallback_order


def _delay_energy_layer_order(
    task: Task,
    context: OrchestrationContext,
    layers: Sequence[ComputingLayer],
    alpha: float,
) -> List[ComputingLayer]:
    delays = {layer: estimate_delay(task, layer, context) for layer in layers}
    energies = {layer: estimate_energy(task, layer, context) for layer in layers}
    min_delay = max(min(delays.values()), 1e-12)
    min_energy = max(min(energies.values()), 1e-12)
    remaining = context.origin_node(task).remaining_battery_ratio
    depletion = 0.0 if remaining is None else 1.0 - remaining

    return sorted(
        layers,
        key=lambda layer: alpha * depletion * (energies[layer] / min_energy) + delays[layer] / min_delay,
    )


def _node_unit_cost(node: Node, demand: Mapping[str, float]) -> float:
    prices = node.metadata.get("unit_prices", {})
    resources = node.metadata.get("resources", {})
    if not isinstance(prices, Mapping) or not isinstance(resources, Mapping):
        return 0.0
    weighted_cost = 0.0
    covered = 0.0
    for resource, requested in demand.items():
        try:
            capacity = min(float(resources.get(resource, 0.0)), requested)
            price = float(prices.get(resource, 0.0))
        except (TypeError, ValueError):
            continue
        weighted_cost += capacity * price
        covered += capacity
    if covered <= 0:
        return float("inf")
    return weighted_cost / covered


def _request_resources(request: Mapping[str, Any]) -> Mapping[str, Any]:
    resources = request.get("resources")
    if isinstance(resources, Mapping):
        return resources

    usage_limits = request.get("usageLimits")
    if isinstance(usage_limits, Mapping):
        return usage_limits

    return {}


def _resource_demand(request: Mapping[str, Any]) -> Dict[str, float]:
    demand: Dict[str, float] = {}
    for resource, value in _request_resources(request).items():
        resource_name = str(resource)
        if resource_name == "distance" or not resource_name.startswith("available_"):
            continue
        try:
            numeric_value = float(value)
        except (TypeError, ValueError):
            continue
        if numeric_value > 0:
            demand[resource_name] = numeric_value
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


def _demand_is_covered(demand: Mapping[str, float], covered: Mapping[str, float]) -> bool:
    return all(covered.get(resource, 0.0) + 1e-9 >= requested for resource, requested in demand.items())


def _dedupe_nodes(nodes: Sequence[Node]) -> List[Node]:
    seen = set()
    result: List[Node] = []
    for node in nodes:
        if node.node_id in seen:
            continue
        seen.add(node.node_id)
        result.append(node)
    return result


def _estimate_delay_for_node(task: Task, node: Node, context: OrchestrationContext) -> float:
    link = context.network_link(task.origin_node_id, node.layer)
    processing_delay = task.cpu_mi / node.processing_capacity_mips
    network_delay = task.total_size_bytes / link.bandwidth_bytes_per_second + link.latency_seconds
    queue_delay = node.queue_length / node.service_rate_tasks_per_second + link.queue_delay_seconds
    weights = context.delay_weights
    return (
        weights.processing * processing_delay
        + weights.network * network_delay
        + weights.queue * queue_delay
    )


def _estimate_energy_for_node(task: Task, node: Node, context: OrchestrationContext) -> float:
    runtime_seconds = task.cpu_mi / node.processing_capacity_mips
    dynamic_power = max(0.0, node.power_peak_watts - node.power_idle_watts)
    compute_energy = runtime_seconds * dynamic_power
    if node.layer is ComputingLayer.MIST:
        return compute_energy

    link = context.network_link(task.origin_node_id, node.layer)
    return (
        compute_energy
        + link.upload_energy_joules_per_byte * task.input_size_bytes
        + link.download_energy_joules_per_byte * task.output_size_bytes
        + link.fixed_transfer_energy_joules
    )
