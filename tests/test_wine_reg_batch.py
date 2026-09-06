import unittest
import tempfile
import os
from orchestrator.wine_manager import WineManager

class TestWineManager(unittest.TestCase):
    def test_wine_security_policies(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            wm = WineManager(tmpdir)
            policies = wm.get_security_policies()
            self.assertGreaterEqual(len(policies), 4)
            keys = [p[0] for p in policies]
            self.assertTrue(all("Policies\\Explorer" in k for k in keys))

    def test_wine_printer_entries(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            wm = WineManager(tmpdir)
            entries = wm.get_printer_entries("MyPDF")
            self.assertTrue(any("MyPDF" in e[2] or "MyPDF" in e[1] for e in entries))

    def test_wine_reg_batch_escaping(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            wm = WineManager(tmpdir)
            os.makedirs(os.path.join(tmpdir, "drive_c"), exist_ok=True)
            entries = [
                ("HKEY_CURRENT_USER\\Software\\Test", "SafeString", "Hello \"World\"\r\nNewSection")
            ]
            wm.apply_reg_batch(entries)
            reg_path = os.path.join(tmpdir, "drive_c", "batch_config.reg")
            self.assertTrue(os.path.exists(reg_path))
            with open(reg_path, "r") as f:
                content = f.read()
            # Verify newlines are stripped and quotes escaped
            self.assertIn('"SafeString"="Hello \\"World\\"NewSection"', content)
            self.assertNotIn("\r", content.split('"SafeString"=')[1].split("\n")[0])

if __name__ == "__main__":
    unittest.main()
