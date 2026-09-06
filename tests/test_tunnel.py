import unittest
from orchestrator.tunnel_manager import TunnelManager

class TestTunnelManager(unittest.TestCase):
    def test_valid_parameters(self):
        tm = TunnelManager("db.example.com", 1433)
        self.assertEqual(tm.target_host, "db.example.com")
        self.assertEqual(tm.target_port, 1433)

    def test_invalid_parameters_rejected(self):
        # Injected comma into host
        with self.assertRaises(ValueError):
            TunnelManager("db.example.com,exec:/bin/sh", 1433)

        # Invalid port
        with self.assertRaises(ValueError):
            TunnelManager("db.example.com", 99999)

        with self.assertRaises(ValueError):
            TunnelManager("db.example.com", -1)

if __name__ == "__main__":
    unittest.main()
