import unittest
from pathlib import Path
import sys
import types

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = ROOT / "pricing_driven_resource_allocation"
ALGORITHMS_ROOT = PACKAGE_ROOT / "algorithms"

package = types.ModuleType("pricing_driven_resource_allocation")
package.__path__ = [str(PACKAGE_ROOT)]
sys.modules.setdefault("pricing_driven_resource_allocation", package)

algorithms_package = types.ModuleType("pricing_driven_resource_allocation.algorithms")
algorithms_package.__path__ = [str(ALGORITHMS_ROOT)]
sys.modules.setdefault("pricing_driven_resource_allocation.algorithms", algorithms_package)

from pricing_driven_resource_allocation.algorithms.raom4cc import (
    ComputingLayer,
    NetworkLink,
    Node,
    OrchestrationContext,
    Task,
    best_fit_orchestrate,
    best_fit_with_delay_energy_heuristics_orchestrate,
    best_fit_with_delay_heuristics_orchestrate,
    build_context_from_topology,
    delay_energy_heuristics_orchestrate,
    delay_heuristics_orchestrate,
    estimate_delay,
    estimate_energy,
    one_layer_orchestrate,
    round_robin_orchestrate,
)
from pricing_driven_resource_allocation.algorithms.benchmark import run_raom4cc_benchmark


def make_context():
    nodes = {
        "u1": Node(
            "u1",
            ComputingLayer.MIST,
            total_cores=2,
            processing_capacity_mips=20_000,
            power_idle_watts=1,
            power_peak_watts=3.3,
            remaining_battery_ratio=0.4,
        ),
        "e1": Node(
            "e1",
            ComputingLayer.EDGE,
            total_cores=8,
            reserved_cores=3,
            processing_capacity_mips=80_000,
            power_idle_watts=100,
            power_peak_watts=150,
        ),
        "e2": Node(
            "e2",
            ComputingLayer.EDGE,
            total_cores=8,
            reserved_cores=6,
            processing_capacity_mips=80_000,
            power_idle_watts=100,
            power_peak_watts=150,
        ),
        "c1": Node(
            "c1",
            ComputingLayer.CLOUD,
            total_cores=64,
            processing_capacity_mips=640_000,
            power_idle_watts=800,
            power_peak_watts=5776,
        ),
    }
    return OrchestrationContext(
        nodes=nodes,
        cap_mapping={"u1": "e1"},
        cloud_node_id="c1",
        network_links={
            ("u1", ComputingLayer.MIST): NetworkLink(1_000_000_000),
            ("u1", ComputingLayer.EDGE): NetworkLink(
                10_000_000,
                latency_seconds=0.01,
                upload_energy_joules_per_byte=1e-9,
                download_energy_joules_per_byte=1e-9,
            ),
            ("u1", ComputingLayer.CLOUD): NetworkLink(
                1_000_000,
                latency_seconds=0.10,
                upload_energy_joules_per_byte=2e-9,
                download_energy_joules_per_byte=2e-9,
            ),
        },
    )


class RAOM4CCAlgorithmsTest(unittest.TestCase):
    def setUp(self):
        self.context = make_context()
        self.task = Task(
            "t1",
            origin_node_id="u1",
            cpu_mi=40_000,
            input_size_bytes=100_000,
            output_size_bytes=10_000,
            required_cores=2,
        )

    def test_one_layer_maps_to_origin_cap_and_cloud(self):
        self.assertEqual(one_layer_orchestrate(self.task, ComputingLayer.MIST, self.context).node_id, "u1")
        self.assertEqual(one_layer_orchestrate(self.task, ComputingLayer.EDGE, self.context).node_id, "e1")
        self.assertEqual(one_layer_orchestrate(self.task, ComputingLayer.CLOUD, self.context).node_id, "c1")

    def test_round_robin_cycles_per_origin(self):
        layers = [ComputingLayer.MIST, ComputingLayer.EDGE, ComputingLayer.CLOUD]
        self.assertEqual(round_robin_orchestrate(self.task, layers, self.context).node_id, "u1")
        self.assertEqual(round_robin_orchestrate(self.task, layers, self.context).node_id, "e1")
        self.assertEqual(round_robin_orchestrate(self.task, layers, self.context).node_id, "c1")

    def test_estimated_delay_and_energy_are_positive(self):
        self.assertGreater(estimate_delay(self.task, ComputingLayer.EDGE, self.context), 0)
        self.assertGreater(estimate_energy(self.task, ComputingLayer.EDGE, self.context), 0)

    def test_delay_heuristic_selects_fast_cloud_for_cpu_heavy_task(self):
        selected = delay_heuristics_orchestrate(
            self.task,
            [ComputingLayer.MIST, ComputingLayer.EDGE, ComputingLayer.CLOUD],
            self.context,
        )
        self.assertEqual(selected.node_id, "c1")

    def test_delay_energy_heuristic_returns_a_candidate_layer_node(self):
        selected = delay_energy_heuristics_orchestrate(
            self.task,
            [ComputingLayer.MIST, ComputingLayer.EDGE, ComputingLayer.CLOUD],
            self.context,
            alpha=1.5,
        )
        self.assertIn(selected.node_id, {"u1", "e1", "c1"})

    def test_best_fit_selects_fullest_edge_node_that_fits(self):
        self.assertEqual(best_fit_orchestrate(self.task, self.context).node_id, "e2")

    def test_best_fit_falls_back_to_cloud_when_edge_is_full(self):
        big_task = Task("t2", origin_node_id="u1", cpu_mi=1_000, required_cores=9)
        self.assertEqual(best_fit_orchestrate(big_task, self.context).node_id, "c1")

    def test_hybrid_algorithms_keep_mist_when_local_heuristic_selects_origin(self):
        tiny_task = Task("t3", origin_node_id="u1", cpu_mi=1, required_cores=1)
        layers = [ComputingLayer.MIST, ComputingLayer.EDGE, ComputingLayer.CLOUD]
        self.assertEqual(
            best_fit_with_delay_heuristics_orchestrate(tiny_task, layers, self.context).node_id,
            "u1",
        )
        self.assertEqual(
            best_fit_with_delay_energy_heuristics_orchestrate(tiny_task, layers, self.context).node_id,
            "u1",
        )

    def test_build_context_from_existing_topology_groups(self):
        df = pd.DataFrame(
            [
                {"global_group": 1, "available_cpu_cores": 2, "provider": "A"},
                {"global_group": 2, "available_cpu_cores": 8, "provider": "B"},
                {"global_group": 3, "available_cpu_cores": 64, "provider": "C"},
            ],
            index=["mist-node", "edge-node", "cloud-node"],
        )
        context = build_context_from_topology(df)
        self.assertEqual(context.nodes["mist-node"].layer, ComputingLayer.MIST)
        self.assertEqual(context.nodes["edge-node"].layer, ComputingLayer.EDGE)
        self.assertEqual(context.nodes["cloud-node"].layer, ComputingLayer.CLOUD)
        self.assertEqual(context.cloud_node_id, "cloud-node")

    def test_benchmark_adaptation_uses_common_cost_objective(self):
        df = pd.DataFrame(
            [
                {
                    "global_group": 1,
                    "available_cpu_cores": 1,
                    "available_ram_gb": 4,
                    "unit_price_available_cpu_cores": 1.0,
                    "unit_price_available_ram_gb": 1.0,
                    "device_type": "MOBILE",
                },
                {
                    "global_group": 3,
                    "available_cpu_cores": 8,
                    "available_ram_gb": 32,
                    "unit_price_available_cpu_cores": 0.1,
                    "unit_price_available_ram_gb": 0.1,
                    "device_type": "DATA_CENTER",
                },
            ],
            index=["mist-node", "cloud-node"],
        )
        request = {
            "usageLimits": {
                "available_cpu_cores": 3,
                "available_ram_gb": 12,
                "distance": 999,
            },
            "features": ["MOBILE", "DATA_CENTER"],
            "maxSubscriptionSize": 2,
            "maxPrice": 100,
        }

        rows = run_raom4cc_benchmark(
            "scenario",
            df,
            request,
            app="vr",
            algorithms=["one_layer_cloud"],
        )

        self.assertEqual(rows[0]["objective"], "minimize_cost")
        self.assertTrue(rows[0]["feasible"])
        self.assertEqual(rows[0]["selected_node"], "['cloud-node']")
        self.assertAlmostEqual(rows[0]["estimated_cost"], 1.5)

    def test_benchmark_selection_is_feasibility_aware(self):
        df = pd.DataFrame(
            [
                {
                    "global_group": 1,
                    "available_cpu_cores": 1,
                    "available_ram_gb": 4,
                    "unit_price_available_cpu_cores": 1.0,
                    "unit_price_available_ram_gb": 1.0,
                    "device_type": "MOBILE",
                },
                {
                    "global_group": 2,
                    "available_cpu_cores": 2,
                    "available_ram_gb": 8,
                    "unit_price_available_cpu_cores": 0.5,
                    "unit_price_available_ram_gb": 0.5,
                    "device_type": "COMPUTER",
                },
                {
                    "global_group": 3,
                    "available_cpu_cores": 8,
                    "available_ram_gb": 32,
                    "unit_price_available_cpu_cores": 0.1,
                    "unit_price_available_ram_gb": 0.1,
                    "device_type": "DATA_CENTER",
                },
            ],
            index=["mist-node", "edge-node", "cloud-node"],
        )
        request = {
            "usageLimits": {
                "available_cpu_cores": 3,
                "available_ram_gb": 12,
            },
            "features": ["MOBILE", "COMPUTER", "DATA_CENTER"],
            "maxSubscriptionSize": 1,
            "maxPrice": 100,
        }

        rows = run_raom4cc_benchmark(
            "scenario",
            df,
            request,
            app="vr",
            algorithms=["round_robin"],
        )

        self.assertTrue(rows[0]["feasible"])
        self.assertEqual(rows[0]["selected_node"], "['cloud-node']")


if __name__ == "__main__":
    unittest.main()
