import subprocess
import os
import logging
import shutil
from collections import defaultdict

logger = logging.getLogger(__name__)

class WineManager:
    """
    Manages lightweight, isolated Copy-on-Write Wine prefixes.
    Symlinks static system folders and copies only isolated registry files (<600 KB total)
    enabling sub-second session spinning and complete isolation between sessions.
    """
    def __init__(self, wine_prefix: str):
        self.wine_prefix = wine_prefix
        self.env = os.environ.copy()
        self.env["WINEPREFIX"] = self.wine_prefix
        self.env["WINEDEBUG"] = "-all"
        self.env["WINEARCH"] = "win32"

    def apply_reg_batch(self, reg_entries):
        """Applies multiple registry entries using a single batch .reg file."""
        if not reg_entries:
            return

        reg_content = "Windows Registry Editor Version 5.00\n\n"
        grouped = defaultdict(list)
        for path, name, data in reg_entries:
            grouped[path].append((name, data))

        for path, values in grouped.items():
            reg_content += f"[{path}]\n"
            for name, data in values:
                if isinstance(data, str):
                    escaped_data = data.replace("\\", "\\\\").replace("\"", "\\\"").replace("\r", "").replace("\n", "")
                    reg_content += f"\"{name}\"=\"{escaped_data}\"\n"
                elif isinstance(data, int):
                    reg_content += f"\"{name}\"=dword:{data:08x}\n"
                else:
                    reg_content += f"\"{name}\"={data}\n"
            reg_content += "\n"

        reg_file_path = os.path.join(self.wine_prefix, "drive_c", "batch_config.reg")
        with open(reg_file_path, "w") as f:
            f.write(reg_content)

        subprocess.run(["wine", "regedit", "/S", "C:\\batch_config.reg"], env=self.env, check=False, capture_output=True)

    def get_security_policies(self):
        """Lockdown policies preventing shell exploitation."""
        return [
            ("HKEY_CURRENT_USER\\Software\\Microsoft\\Windows\\CurrentVersion\\Policies\\Explorer", "NoRun", 1),
            ("HKEY_CURRENT_USER\\Software\\Microsoft\\Windows\\CurrentVersion\\Policies\\Explorer", "NoDrives", 0x3FFFFFB),
            ("HKEY_CURRENT_USER\\Software\\Microsoft\\Windows\\CurrentVersion\\Policies\\Explorer", "NoFind", 1),
            ("HKEY_CURRENT_USER\\Software\\Microsoft\\Windows\\CurrentVersion\\Policies\\Explorer", "NoSetFolders", 1),
            ("HKEY_CURRENT_USER\\Software\\Microsoft\\Windows\\CurrentVersion\\Policies\\Explorer", "NoControlPanel", 1),
        ]

    def get_printer_entries(self, printer_name="PDF-Printer"):
        """Configures the default Windows GDI PostScript driver pointing to CUPS virtual PDF printer."""
        return [
            ("HKEY_CURRENT_USER\\Software\\Microsoft\\Windows NT\\CurrentVersion\\Windows", "Device", f"{printer_name},wineps.drv,CUPS:{printer_name}"),
            ("HKEY_CURRENT_USER\\Software\\Microsoft\\Windows NT\\CurrentVersion\\Windows", "IsMRUEstablished", 1),
            ("HKEY_CURRENT_USER\\Software\\Microsoft\\Windows NT\\CurrentVersion\\Windows", "LegacyDefaultPrinterMode", 1),
            ("HKEY_CURRENT_USER\\Software\\Microsoft\\Windows NT\\CurrentVersion\\Devices", printer_name, f"wineps.drv,CUPS:{printer_name}"),
        ]

    def initialize_prefix(self, template_prefix="/home/wineuser/.wine"):
        """
        Initializes an ultra-lightweight Copy-on-Write Wine prefix.
        Avoids 1.5 GB duplication per user, maintaining strict sandbox boundaries.
        """
        if os.path.exists(os.path.join(self.wine_prefix, "system.reg")):
            return

        os.makedirs(self.wine_prefix, exist_ok=True)
        drive_c = os.path.join(self.wine_prefix, "drive_c")
        os.makedirs(drive_c, exist_ok=True)

        # 1. dosdevices: c: -> ../drive_c; eliminate host drive letters (z:, d:, y:)
        dosdevices = os.path.join(self.wine_prefix, "dosdevices")
        os.makedirs(dosdevices, exist_ok=True)
        c_link = os.path.join(dosdevices, "c:")
        if not os.path.exists(c_link) and not os.path.islink(c_link):
            os.symlink("../drive_c", c_link)

        for drive in ["z:", "d:", "y:"]:
            d_path = os.path.join(dosdevices, drive)
            if os.path.islink(d_path):
                os.remove(d_path)
            elif os.path.exists(d_path):
                if os.path.isdir(d_path):
                    shutil.rmtree(d_path)
                else:
                    os.remove(d_path)

        # 2. Copy isolated registry databases (<600 KB total)
        for reg_file in ["system.reg", "user.reg", "userdef.reg"]:
            src = os.path.join(template_prefix, reg_file)
            dst = os.path.join(self.wine_prefix, reg_file)
            if os.path.exists(src) and not os.path.exists(dst):
                try:
                    shutil.copy2(src, dst)
                except Exception as e:
                    logger.warning(f"Could not copy {reg_file}: {e}")

        # 3. Symlink static system folders (0 MB overhead)
        template_drive_c = os.path.join(template_prefix, "drive_c")
        for static_folder in ["windows", "Program Files", "ProgramData"]:
            src = os.path.join(template_drive_c, static_folder)
            dst = os.path.join(drive_c, static_folder)
            if os.path.exists(src) and not os.path.exists(dst):
                try:
                    os.symlink(src, dst)
                except OSError:
                    pass

        # 4. Isolated user documents directory (C:\Documents)
        docs_dir = os.path.join(drive_c, "Documents")
        os.makedirs(docs_dir, exist_ok=True)

        # 5. Apply security policies and printer configuration
        entries = []
        entries.extend(self.get_security_policies())
        entries.extend(self.get_printer_entries())
        self.apply_reg_batch(entries)

        # 6. Configure win.ini for legacy Win32 reporting libraries (QuickReport / ReportBuilder)
        try:
            win_ini_path = os.path.join(self.wine_prefix, "drive_c", "windows", "win.ini")
            printer_name = "PDF-Printer"
            win_ini_content = (
                "[devices]\n"
                f"{printer_name}=wineps.drv,CUPS:{printer_name}\n\n"
                "[windows]\n"
                f"device={printer_name},wineps.drv,CUPS:{printer_name}\n\n"
                "[PrinterPorts]\n"
                f"{printer_name}=wineps.drv,CUPS:{printer_name},15,45\n"
            )
            with open(win_ini_path, "w") as f:
                f.write(win_ini_content)
        except Exception as e:
            logger.error(f"Failed to write win.ini printer config: {e}")
