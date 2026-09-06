import unittest
from unittest.mock import patch
from orchestrator.utils.memory_guard import get_cgroup_memory, can_admit_new_session

class TestMemoryGuard(unittest.TestCase):
    def test_memory_metrics_fallback(self):
        metrics = get_cgroup_memory()
        self.assertIn("usage_mb", metrics)
        self.assertIn("limit_mb", metrics)
        self.assertIn("available_mb", metrics)
        self.assertIn("percent_used", metrics)
        self.assertGreaterEqual(metrics["available_mb"], 0)

    def test_admission_control_logic(self):
        with patch("orchestrator.utils.memory_guard.get_cgroup_memory") as mock_mem:
            mock_mem.return_value = {
                "available_mb": 500.0,
                "percent_used": 50.0,
                "usage_mb": 500.0,
                "limit_mb": 1000.0
            }
            admitted, msg, _ = can_admit_new_session(required_headroom_mb=200.0, max_utilization_pct=85.0)
            self.assertTrue(admitted)

            mock_mem.return_value = {
                "available_mb": 100.0,
                "percent_used": 90.0,
                "usage_mb": 900.0,
                "limit_mb": 1000.0
            }
            admitted, msg, _ = can_admit_new_session(required_headroom_mb=200.0, max_utilization_pct=85.0)
            self.assertFalse(admitted)

if __name__ == "__main__":
    unittest.main()
