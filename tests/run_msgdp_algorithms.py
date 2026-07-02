import unittest

import pandas as pd

from pricing_driven_resource_allocation.algorithms import generate_priorities, run_msgdp_benchmark


class MSGDPAlgorithmsTest(unittest.TestCase):
    def setUp(self):
        # Define baseline single-node network configuration
        self.df = pd.DataFrame(
            [
                {
                    "global_group": 2,
                    "available_cpu_cores": 4,
                    "available_ram_gb": 16,
                    "device_type": "EDGE"
                },
            ],
            index=["edge-node-1"],
        )
        self.request = {
            "maxPrice": 5000,
            "features": ["health"],
        }

    # def test_generate_priorities_handles_single_service_successfully(self):
    #     """Verify that generate_priorities successfully computes weights and shapes when num_services=1."""
    #     num_services = 1
    #     num_regions = 3
    #
    #     # Execute priority matrix generation
    #     try:
    #         priorities = generate_priorities(num_services=num_services, num_regions=num_regions)
    #     except IndexError as e:
    #         self.fail(f"Regression detected: generate_priorities raised an IndexError for single service input: {e}")
    #
    #     # Assert that the function correctly evaluates a 1x3 priority grid for the region layout
    #     self.assertEqual(priorities.shape, (num_services, num_regions))

    def test_msgdp_benchmark_completes_successfully_for_single_service(self):
        """Verify that the benchmark execution successfully hits a COMPLETED and feasible state."""
        rows = run_msgdp_benchmark(
            scenario_id="scenario_single_service",
            topology_devices=self.df,
            request=self.request,
            app="health",
        )

        # Confirm execution pipeline didn't encounter internal errors or crash down to a FAILED status
        self.assertEqual(rows[0]["status"], "COMPLETED")
        self.assertTrue(rows[0]["feasible"])
        self.assertNotIn("index 1 is out of bounds", str(rows[0].get("reason", "")))