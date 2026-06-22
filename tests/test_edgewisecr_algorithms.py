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

from pricing_driven_resource_allocation.algorithms.edgewisecr import (
    edgewise_greedy_solve,
    edgewise_milp_solve,
)
from pricing_driven_resource_allocation.algorithms.edgewisecr_benchmark import (
    default_algorithm_names,
    run_edgewisecr_benchmark,
)


def make_devices():
    return pd.DataFrame(
        [
            {
                "global_group": 1,
                "provider": "TELSTRA",
                "device_type": "SENSOR",
                "available_ram_gb": 4,
                "unit_price_available_ram_gb": 1.0,
                "available_cpu_cores": 1,
                "unit_price_available_cpu_cores": 2.0,
                "available_storage_gb": 2,
                "unit_price_available_storage_gb": 0.5,
            },
            {
                "global_group": 2,
                "provider": "OPTUS",
                "device_type": "COMPUTER",
                "available_ram_gb": 8,
                "unit_price_available_ram_gb": 0.5,
                "available_cpu_cores": 2,
                "unit_price_available_cpu_cores": 1.0,
                "available_storage_gb": 4,
                "unit_price_available_storage_gb": 0.2,
            },
            {
                "global_group": 3,
                "provider": "VODAFONE",
                "device_type": "DATA_CENTER",
                "available_ram_gb": 32,
                "unit_price_available_ram_gb": 0.1,
                "available_cpu_cores": 8,
                "unit_price_available_cpu_cores": 0.1,
                "available_storage_gb": 16,
                "unit_price_available_storage_gb": 0.05,
            },
        ],
        index=["mist-node", "edge-node", "cloud-node"],
    )


def make_request(overrides=None):
    req = {
        "usageLimits": {
            "available_ram_gb": 12,
            "available_cpu_cores": 3,
            "available_storage_gb": 6,
        },
        "features": ["SENSOR", "COMPUTER", "DATA_CENTER"],
        "maxSubscriptionSize": 2,
        "maxPrice": 100,
    }
    if overrides:
        req.update(overrides)
    return req


class EdgeWiseCRMilpTest(unittest.TestCase):
    def setUp(self):
        self.devices = make_devices()
        self.request = make_request()

    def test_milp_finds_feasible_minimum_cost(self):
        result = edgewise_milp_solve(self.devices, self.request, preprocess=True, timeout_seconds=10)
        self.assertTrue(result.feasible, msg=result.reason)
        self.assertEqual(result.status, "OPTIMAL")
        self.assertGreater(result.cost, 0)
        self.assertLessEqual(len(result.selected_nodes), 2)

    def test_milp_preprocess_excludes_non_matching_device_types(self):
        request = make_request({"features": ["DATA_CENTER"]})
        result = edgewise_milp_solve(self.devices, request, preprocess=True, timeout_seconds=10)
        self.assertTrue(result.feasible)
        self.assertEqual(result.selected_features, ["DATA_CENTER"])

    def test_milp_num_includes_all_nodes(self):
        request = make_request({"features": ["DATA_CENTER"]})
        result = edgewise_milp_solve(self.devices, request, preprocess=False, timeout_seconds=10)
        self.assertTrue(result.feasible)

    def test_milp_respects_max_nodes(self):
        request = make_request({"maxSubscriptionSize": 1})
        result = edgewise_milp_solve(self.devices, request, preprocess=True, timeout_seconds=10)
        self.assertTrue(result.feasible, msg=result.reason)
        self.assertEqual(len(result.selected_nodes), 1)

    def test_milp_respects_budget(self):
        request = make_request({"maxPrice": 0.5})
        result = edgewise_milp_solve(self.devices, request, preprocess=True, timeout_seconds=10)
        self.assertFalse(result.feasible)
        self.assertIn(result.status, {"INFEASIBLE", "TIMEOUT", "NOT_SOLVED"})

    def test_milp_infeasible_when_demand_exceeds_capacity(self):
        request = make_request({
            "usageLimits": {
                "available_ram_gb": 1000,
                "available_cpu_cores": 1000,
                "available_storage_gb": 1000,
            },
            "maxSubscriptionSize": 10,
            "maxPrice": 100000,
        })
        result = edgewise_milp_solve(self.devices, request, preprocess=True, timeout_seconds=10)
        self.assertFalse(result.feasible)


class EdgeWiseCRGreedyTest(unittest.TestCase):
    def setUp(self):
        self.devices = make_devices()
        self.request = make_request()

    def test_greedy_finds_feasible_placement(self):
        result = edgewise_greedy_solve(self.devices, self.request, preprocess=True)
        self.assertTrue(result.feasible, msg=result.reason)
        self.assertGreater(result.cost, 0)

    def test_greedy_respects_max_nodes(self):
        request = make_request({"maxSubscriptionSize": 1})
        result = edgewise_greedy_solve(self.devices, request, preprocess=True)
        self.assertLessEqual(len(result.selected_nodes), 1)

    def test_greedy_respects_budget(self):
        request = make_request({"maxPrice": 0.5})
        result = edgewise_greedy_solve(self.devices, request, preprocess=True)
        self.assertFalse(result.feasible)

    def test_greedy_infeasible_when_demand_exceeds_capacity(self):
        request = make_request({
            "usageLimits": {
                "available_ram_gb": 1000,
                "available_cpu_cores": 1000,
                "available_storage_gb": 1000,
            },
            "maxSubscriptionSize": 10,
            "maxPrice": 100000,
        })
        result = edgewise_greedy_solve(self.devices, request, preprocess=True)
        self.assertFalse(result.feasible)


class EdgeWiseCRBenchmarkTest(unittest.TestCase):
    def setUp(self):
        self.devices = make_devices()
        self.request = make_request()

    def test_default_algorithm_names_returns_six_variants(self):
        names = default_algorithm_names()
        self.assertEqual(len(names), 6)
        for name in names:
            self.assertIn(name, {
                "edgewise", "edgewise_cr", "edgewise_num",
                "prolog", "prolog_cr", "prolog_num",
            })

    def test_benchmark_runs_all_variants(self):
        rows = run_edgewisecr_benchmark(
            "scenario_test",
            self.devices,
            self.request,
            timeout_seconds=10,
        )
        self.assertEqual(len(rows), 6)
        for row in rows:
            self.assertEqual(row["objective"], "minimize_cost")
            self.assertIn(row["algorithm"], default_algorithm_names())

    def test_benchmark_subset_variants(self):
        rows = run_edgewisecr_benchmark(
            "scenario_test",
            self.devices,
            self.request,
            algorithms=["edgewise", "prolog"],
            timeout_seconds=10,
        )
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["algorithm"], "edgewise")
        self.assertEqual(rows[1]["algorithm"], "prolog")

    def test_benchmark_unknown_variant_reports_failed(self):
        rows = run_edgewisecr_benchmark(
            "scenario_test",
            self.devices,
            self.request,
            algorithms=["unknown_variant"],
            timeout_seconds=10,
        )
        self.assertEqual(rows[0]["status"], "FAILED")
        self.assertFalse(rows[0]["feasible"])


if __name__ == "__main__":
    unittest.main()
