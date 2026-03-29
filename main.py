"""Point d'entrée principal EBJFL-Broadcast."""

import sys
import os
from pathlib import Path

# Force UTF-8 on Windows
if sys.platform == "win32":
    os.environ["PYTHONIOENCODING"] = "utf-8"
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon
from ui.dashboard import Dashboard


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("EBJFL-Broadcast")

    logo = str(Path(__file__).parent / "assets" / "logo.png")
    app.setWindowIcon(QIcon(logo))

    window = Dashboard()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
