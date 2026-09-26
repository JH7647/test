import sys
sys.path.append(r"C:\TEST\OFA")
sys.path.append(r"C:\TEST\OFA\src")

from PySide6.QtWidgets import QApplication
from src.main_window import MainWindow

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

