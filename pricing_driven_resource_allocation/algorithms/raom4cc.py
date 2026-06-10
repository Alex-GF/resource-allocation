"""Offloading orchestrators from the RAOM4CC paper.

The paper evaluates these algorithms in a SUMO/PureEdgeSim simulation.  This
module keeps only the algorithmic core and exposes plain Python data
structures, so the existing resource-allocation scenarios can provide the
topology, demand, and resource state.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from math import isfinite
from typing import Dict, Iterable, Mapping, MutableMapping, Optional, Sequence, Tuple, Union


class ComputingLayer(str, Enum):
    """Computing continuum layers used by the paper."""

    MIST = "mist"
    EDGE = "edge"
    CLOUD = "cloud"


@dataclass(frozen=True)
class DelayWeights:
    """Weights for Equation (8): processing, network, and queue delay."""

    processing: float = 1.0 / 3.0
    network: float = 1.0 / 3.0
    queue: float = 1.0 / 3.0

    def __post_init__(self) -> None:
        values = (self.processing, self.network, self.queue)
        if any(v < 0 for v in values):
            raise ValueError("Delay weights must be non-negative.")
        total = sum(values)
        if abs(total - 1.0) > 1e-9:
            raise ValueError("Delay weights must sum to 1.")


@dataclass(frozen=True)
class NetworkLink:
    """Network metrics between an origin node and a target layer."""

    bandwidth_bytes_per_second: float
    latency_seconds: float = 0.0
    queue_delay_seconds: float = 0.0
    upload_energy_joules_per_byte: float = 0.0
    download_energy_joules_per_byte: float = 0.0
    fixed_transfer_energy_joules: float = 0.0

    def __post_init__(self) -> None:
        if self.bandwidth_bytes_per_second <= 0:
            raise ValueError("bandwidth_bytes_per_second must be greater than 0.")
        if self.latency_seconds < 0 or self.queue_delay_seconds < 0:
            raise ValueError("Network delays must be non-negative.")
        if (
            self.upload_energy_joules_per_byte < 0
            or self.download_energy_joules_per_byte < 0
            or self.fixed_transfer_energy_joules < 0
        ):
            raise ValueError("Network energy parameters must be non-negative.")


@dataclass
class Node:
    """A computing node available for task offloading."""

    node_id: str
    layer: ComputingLayer
    total_cores: float
    processing_capacity_mips: float
    reserved_cores: float = 0.0
    queue_length: float = 0.0
    service_rate_tasks_per_second: float = 1.0
    power_idle_watts: float = 0.0
    power_peak_watts: float = 0.0
    remaining_battery_ratio: Optional[float] = None
    is_orchestrator: bool = False
    metadata: Dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.total_cores <= 0:
            raise ValueError("total_cores must be greater than 0.")
        if self.processing_capacity_mips <= 0:
            raise ValueError("processing_capacity_mips must be greater than 0.")
        if self.reserved_cores < 0 or self.queue_length < 0:
            raise ValueError("reserved_cores and queue_length must be non-negative.")
        if self.service_rate_tasks_per_second <= 0:
            raise ValueError("service_rate_tasks_per_second must be greater than 0.")
        if self.power_idle_watts < 0 or self.power_peak_watts < 0:
            raise ValueError("Power values must be non-negative.")
        if self.remaining_battery_ratio is not None and not 0.0 <= self.remaining_battery_ratio <= 1.0:
            raise ValueError("remaining_battery_ratio must be between 0 and 1.")

    @property
    def available_cores(self) -> float:
        return max(0.0, self.total_cores - self.reserved_cores)

    def can_fit(self, task: "Task") -> bool:
        return self.available_cores >= task.required_cores


@dataclass(frozen=True)
class Task:
    """A task to place in the computing continuum."""

    task_id: str
    origin_node_id: str
    cpu_mi: float
    input_size_bytes: float = 0.0
    output_size_bytes: float = 0.0
    required_cores: float = 1.0
    latency_constraint_seconds: Optional[float] = None
    metadata: Dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.cpu_mi < 0:
            raise ValueError("cpu_mi must be non-negative.")
        if self.input_size_bytes < 0 or self.output_size_bytes < 0:
            raise ValueError("Task sizes must be non-negative.")
        if self.required_cores <= 0:
            raise ValueError("required_cores must be greater than 0.")

    @property
    def total_size_bytes(self) -> float:
        return self.input_size_bytes + self.output_size_bytes


@dataclass
class OrchestrationContext:
    """Mutable state required by the RAOM4CC orchestrators."""

    nodes: MutableMapping[str, Node]
    cap_mapping: MutableMapping[str, str] = field(default_factory=dict)
    cloud_node_id: Optional[str] = None
    last_layer_by_origin: MutableMapping[str, ComputingLayer] = field(default_factory=dict)
    network_links: MutableMapping[Tuple[str, ComputingLayer], NetworkLink] = field(default_factory=dict)
    delay_weights: DelayWeights = field(default_factory=DelayWeights)
    default_network_link: NetworkLink = field(
        default_factory=lambda: NetworkLink(bandwidth_bytes_per_second=125_000_000.0)
    )

    def __post_init__(self) -> None:
        if not self.nodes:
            raise ValueError("At least one node is required.")
        if self.cloud_node_id is None:
            cloud_nodes = [n for n in self.nodes.values() if n.layer is ComputingLayer.CLOUD]
            if cloud_nodes:
                self.cloud_node_id = max(cloud_nodes, key=lambda n: n.processing_capacity_mips).node_id

    def origin_node(self, task: Task) -> Node:
        return _node(self, task.origin_node_id)

    def cap_node(self, task_or_origin: Union[Task, str]) -> Node:
        origin_id = task_or_origin.origin_node_id if isinstance(task_or_origin, Task) else task_or_origin
        cap_id = self.cap_mapping.get(origin_id)
        if cap_id is not None:
            return _node(self, cap_id)

        edge_nodes = [n for n in self.nodes.values() if n.layer is ComputingLayer.EDGE]
        if not edge_nodes:
            raise ValueError("No CAP mapping exists and no edge nodes are available.")
        return min(edge_nodes, key=lambda n: (n.queue_length, -n.available_cores, n.node_id))

    def cloud_node(self) -> Node:
        if self.cloud_node_id is None:
            raise ValueError("No cloud node is configured.")
        return _node(self, self.cloud_node_id)

    def network_link(self, origin_node_id: str, layer: ComputingLayer) -> NetworkLink:
        return self.network_links.get((origin_node_id, layer), self.default_network_link)


def one_layer_orchestrate(
    task: Task,
    computing_layer: Union[ComputingLayer, str],
    context: OrchestrationContext,
) -> Node:
    """Algorithm 1: map a task to mist, edge/CAP, or cloud."""

    layer = _layer(computing_layer)
    if layer is ComputingLayer.MIST:
        return context.origin_node(task)
    if layer is ComputingLayer.EDGE:
        return context.cap_node(task)
    return context.cloud_node()


def round_robin_orchestrate(
    task: Task,
    computing_layers: Sequence[Union[ComputingLayer, str]],
    context: OrchestrationContext,
) -> Node:
    """Algorithm 2: cycle through the available layers per origin node."""

    layers = _layers(computing_layers)
    if not layers:
        raise ValueError("computing_layers cannot be empty.")

    last_layer = context.last_layer_by_origin.get(task.origin_node_id)
    if last_layer in layers:
        next_layer = layers[(layers.index(last_layer) + 1) % len(layers)]
    else:
        next_layer = layers[0]

    context.last_layer_by_origin[task.origin_node_id] = next_layer
    return one_layer_orchestrate(task, next_layer, context)


def estimate_delay(
    task: Task,
    computing_layer: Union[ComputingLayer, str],
    context: OrchestrationContext,
) -> float:
    """Equations (8) and (9): weighted processing, network, and queue delay."""

    layer = _layer(computing_layer)
    node = one_layer_orchestrate(task, layer, context)
    link = context.network_link(task.origin_node_id, layer)

    processing_delay = task.cpu_mi / node.processing_capacity_mips
    network_delay = task.total_size_bytes / link.bandwidth_bytes_per_second + link.latency_seconds
    queue_delay = node.queue_length / node.service_rate_tasks_per_second + link.queue_delay_seconds
    weights = context.delay_weights

    return (
        weights.processing * processing_delay
        + weights.network * network_delay
        + weights.queue * queue_delay
    )


def delay_heuristics_orchestrate(
    task: Task,
    computing_layers: Sequence[Union[ComputingLayer, str]],
    context: OrchestrationContext,
) -> Node:
    """Algorithm 3: choose the layer with the smallest estimated delay."""

    layers = _layers(computing_layers)
    if not layers:
        raise ValueError("computing_layers cannot be empty.")

    layer = min(layers, key=lambda item: estimate_delay(task, item, context))
    return one_layer_orchestrate(task, layer, context)


def estimate_energy(
    task: Task,
    computing_layer: Union[ComputingLayer, str],
    context: OrchestrationContext,
) -> float:
    """Equations (10), (11), and (12): CPU dynamic energy plus link energy."""

    layer = _layer(computing_layer)
    node = one_layer_orchestrate(task, layer, context)
    runtime_seconds = task.cpu_mi / node.processing_capacity_mips
    dynamic_power = max(0.0, node.power_peak_watts - node.power_idle_watts)
    compute_energy = runtime_seconds * dynamic_power

    if layer is ComputingLayer.MIST:
        return compute_energy

    link = context.network_link(task.origin_node_id, layer)
    link_energy = (
        link.upload_energy_joules_per_byte * task.input_size_bytes
        + link.download_energy_joules_per_byte * task.output_size_bytes
        + link.fixed_transfer_energy_joules
    )
    return compute_energy + link_energy


def delay_energy_heuristics_orchestrate(
    task: Task,
    computing_layers: Sequence[Union[ComputingLayer, str]],
    context: OrchestrationContext,
    *,
    alpha: float = 1.0,
    epsilon: float = 1e-12,
) -> Node:
    """Algorithm 4: minimize alpha * battery depletion * energy ratio + delay ratio."""

    if alpha < 0:
        raise ValueError("alpha must be non-negative.")
    layers = _layers(computing_layers)
    if not layers:
        raise ValueError("computing_layers cannot be empty.")

    delays = {layer: estimate_delay(task, layer, context) for layer in layers}
    energies = {layer: estimate_energy(task, layer, context) for layer in layers}
    min_delay = _positive_min(delays.values(), epsilon)
    min_energy = _positive_min(energies.values(), epsilon)

    origin = context.origin_node(task)
    remaining = origin.remaining_battery_ratio
    depletion_factor = 0.0 if remaining is None else 1.0 - remaining

    def cost(layer: ComputingLayer) -> float:
        energy_ratio = energies[layer] / min_energy
        delay_ratio = delays[layer] / min_delay
        return alpha * depletion_factor * energy_ratio + delay_ratio

    selected_layer = min(layers, key=cost)
    return one_layer_orchestrate(task, selected_layer, context)


def best_fit_orchestrate(task: Task, context: OrchestrationContext) -> Node:
    """Algorithm 5: choose the fullest edge node that can still run the task."""

    edge_nodes = [node for node in context.nodes.values() if node.layer is ComputingLayer.EDGE and node.can_fit(task)]
    if not edge_nodes:
        return context.cloud_node()

    cap_id = context.cap_mapping.get(task.origin_node_id)

    def rank(node: Node) -> Tuple[float, int, int, str]:
        prefers_cap = 1 if cap_id is not None and node.node_id == cap_id else 0
        prefers_orchestrator = 1 if node.is_orchestrator else 0
        return (node.reserved_cores, prefers_cap, prefers_orchestrator, node.node_id)

    return max(edge_nodes, key=rank)


def best_fit_with_delay_heuristics_orchestrate(
    task: Task,
    computing_layers: Sequence[Union[ComputingLayer, str]],
    context: OrchestrationContext,
) -> Node:
    """Algorithm 6: keep local execution only when delay heuristic chooses mist."""

    local_decision = delay_heuristics_orchestrate(task, computing_layers, context)
    if local_decision.node_id == task.origin_node_id:
        return local_decision
    return best_fit_orchestrate(task, context)


def best_fit_with_delay_energy_heuristics_orchestrate(
    task: Task,
    computing_layers: Sequence[Union[ComputingLayer, str]],
    context: OrchestrationContext,
    *,
    alpha: float = 1.0,
) -> Node:
    """Algorithm 7: keep local execution only when delay-energy heuristic chooses mist."""

    local_decision = delay_energy_heuristics_orchestrate(task, computing_layers, context, alpha=alpha)
    if local_decision.node_id == task.origin_node_id:
        return local_decision
    return best_fit_orchestrate(task, context)


def build_context_from_topology(
    devices,
    *,
    layer_column: str = "computing_layer",
    group_column: str = "global_group",
    node_id_column: Optional[str] = None,
    cap_mapping: Optional[Mapping[str, str]] = None,
    cloud_node_id: Optional[str] = None,
    mips_per_core: float = 10_000.0,
    default_service_rate_tasks_per_second: float = 1.0,
    default_power_idle_watts: Optional[Mapping[ComputingLayer, float]] = None,
    default_power_peak_watts: Optional[Mapping[ComputingLayer, float]] = None,
) -> OrchestrationContext:
    """Build an orchestration context from a topology dataframe.

    If `layer_column` is absent, the existing scenario `global_group` values are
    mapped as 1 -> mist, 2 -> edge, 3 -> cloud.
    """

    default_power_idle_watts = default_power_idle_watts or {
        ComputingLayer.MIST: 1.0,
        ComputingLayer.EDGE: 100.0,
        ComputingLayer.CLOUD: 800.0,
    }
    default_power_peak_watts = default_power_peak_watts or {
        ComputingLayer.MIST: 3.3,
        ComputingLayer.EDGE: 150.0,
        ComputingLayer.CLOUD: 5776.0,
    }

    nodes: Dict[str, Node] = {}
    for index, row in devices.iterrows():
        node_id = str(row[node_id_column]) if node_id_column else str(index)
        layer = _row_layer(row, layer_column=layer_column, group_column=group_column)
        total_cores = _first_present(row, ("available_cpu_cores", "cpu_cores", "cores"), default=1.0)
        total_cores = max(1.0, float(total_cores))
        processing_capacity = total_cores * float(mips_per_core)
        nodes[node_id] = Node(
            node_id=node_id,
            layer=layer,
            total_cores=total_cores,
            processing_capacity_mips=processing_capacity,
            service_rate_tasks_per_second=default_service_rate_tasks_per_second,
            power_idle_watts=float(default_power_idle_watts[layer]),
            power_peak_watts=float(default_power_peak_watts[layer]),
            metadata={
                "provider": row.get("provider"),
                "device_type": row.get("device_type"),
                "global_group": row.get(group_column),
                "resources": _resource_values(row),
                "unit_prices": _unit_price_values(row),
            },
        )

    return OrchestrationContext(
        nodes=nodes,
        cap_mapping=dict(cap_mapping or {}),
        cloud_node_id=cloud_node_id,
    )


def _node(context: OrchestrationContext, node_id: str) -> Node:
    try:
        return context.nodes[node_id]
    except KeyError as exc:
        raise KeyError(f"Unknown node_id: {node_id}") from exc


def _layer(value: Union[ComputingLayer, str]) -> ComputingLayer:
    if isinstance(value, ComputingLayer):
        return value
    return ComputingLayer(str(value).lower())


def _layers(values: Sequence[Union[ComputingLayer, str]]) -> Sequence[ComputingLayer]:
    return [_layer(value) for value in values]


def _positive_min(values: Iterable[float], epsilon: float) -> float:
    finite_values = [value for value in values if isfinite(value)]
    if not finite_values:
        return epsilon
    return max(min(finite_values), epsilon)


def _row_layer(row, *, layer_column: str, group_column: str) -> ComputingLayer:
    if layer_column in row and not _is_missing(row[layer_column]):
        return _layer(row[layer_column])

    group_value = int(row.get(group_column, 2))
    if group_value == 1:
        return ComputingLayer.MIST
    if group_value == 3:
        return ComputingLayer.CLOUD
    return ComputingLayer.EDGE


def _first_present(row, names: Sequence[str], *, default: float) -> float:
    for name in names:
        if name in row and not _is_missing(row[name]):
            value = row[name]
            try:
                if isfinite(float(value)):
                    return float(value)
            except (TypeError, ValueError):
                continue
    return default


def _resource_values(row) -> Dict[str, float]:
    resources: Dict[str, float] = {}
    for key in row.index:
        if str(key).startswith("available_") and not str(key).startswith("available_unit_price_"):
            if not _is_missing(row[key]):
                try:
                    resources[str(key)] = float(row[key])
                except (TypeError, ValueError):
                    continue
    return resources


def _unit_price_values(row) -> Dict[str, float]:
    prices: Dict[str, float] = {}
    for key in row.index:
        key_str = str(key)
        if not key_str.startswith("unit_price_") or _is_missing(row[key]):
            continue
        resource_name = key_str[len("unit_price_") :]
        try:
            prices[resource_name] = float(row[key])
        except (TypeError, ValueError):
            continue
    return prices


def _is_missing(value: object) -> bool:
    if value is None:
        return True
    try:
        return bool(value != value)
    except Exception:
        return False
