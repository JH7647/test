from PySide6.QtWidgets import QFormLayout, QComboBox, QLabel
from src.ui.tabs_input.base_input import BaseInputTab

class AeroTab(BaseInputTab):
    def __init__(self, parent=None):
        super().__init__("AeroDyn", parent)
        
    def refresh_ui(self):
        for i in reversed(range(self.form_layout.count())): 
            self.form_layout.itemAt(i).widget().setParent(None)
            
        form = QFormLayout()
        
        self.cmb_wake = QComboBox()
        self.cmb_wake.addItems(["0: None", "1: BEM", "2: DBEM", "3: OLAF"])
        self.cmb_wake.setCurrentIndex(int(self.data_store.get("WakeMod", "1")))
        
        form.addRow(QLabel("<b>[AeroDyn 공력 옵션 제어]</b>"))
        form.addRow("🦅 Wake Model (WakeMod):", self.cmb_wake)
        
        self.form_layout.addLayout(form)

    def collect_inputs(self):
        return {
            "WakeMod": str(self.cmb_wake.currentIndex())
        }
