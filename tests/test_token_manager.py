import unittest
import os
import tempfile
from orchestrator.utils.token_manager import TokenManager

class TestTokenManager(unittest.TestCase):
    def test_token_lifecycle(self):
        with tempfile.NamedTemporaryFile(delete=False) as tf:
            temp_path = tf.name

        try:
            mgr = TokenManager(token_file=temp_path)
            mgr.add_token("sess-123", "127.0.0.1", 5901)
            mgr.add_token("sess-456", "127.0.0.1", 5902)

            with open(temp_path, "r") as f:
                content = f.read()

            self.assertIn("sess-123: 127.0.0.1:5901", content)
            self.assertIn("sess-456: 127.0.0.1:5902", content)

            mgr.remove_token("sess-123")
            with open(temp_path, "r") as f:
                updated = f.read()

            self.assertNotIn("sess-123", updated)
            self.assertIn("sess-456: 127.0.0.1:5902", updated)

            # Verify permissions: 0o600
            mode = oct(os.stat(temp_path).st_mode & 0o777)
            self.assertEqual(mode, "0o600")
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

if __name__ == "__main__":
    unittest.main()
