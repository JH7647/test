import os
from PySide6.QtWidgets import (QWidget, QFormLayout, QLineEdit, QLabel, QTextEdit, 
                               QPushButton, QHBoxLayout, QVBoxLayout, QSplitter, QComboBox)
from PySide6.QtWidgets import QWidget, QVBoxLayout, QComboBox, QMessageBox
from PySide6.QtCore import QProcess, Qt
from src.core.openfast_io import OpenFastIO

class MainTab(QWidget):
    MODULE_SWITCHES = {
        "CompElast":  {"values": ["1", "2", "3"], "desc": "1=ElastoDyn; 2=BeamDyn; 3=Simplified ElastoDyn"},
        "CompInflow": {"values": ["0", "1", "2"], "desc": "0=still air; 1=InflowWind; 2=external from ExtInflow"},
        "CompAero":   {"values": ["0", "1", "2", "3"], "desc": "0=None; 1=AeroDisk; 2=AeroDyn; 3=ExtLoads"},
        "CompServo":  {"values": ["0", "1"], "desc": "0=None; 1=ServoDyn"},
        "CompSeaSt":  {"values": ["0", "1"], "desc": "0=None; 1=SeaState"},
        "CompHydro":  {"values": ["0", "1"], "desc": "0=None; 1=HydroDyn"},
        "CompSub":    {"values": ["0", "1", "2"], "desc": "0=None; 1=SubDyn; 2=External Platform MCKF"},
        "CompMooring":{"values": ["0", "1", "2", "3", "4"], "desc": "0=None; 1=MAP++; 2=FEAMooring; 3=MoorDyn; 4=OrcaFlex"},
        "CompIce":    {"values": ["0", "1", "2"], "desc": "0=None; 1=IceFloe; 2=IceDyn"},
        "CompSoil":   {"values": ["0", "1"], "desc": "0=None; 1=SoilDyn"},
    }
    INITIAL_CONDITIONS = {
        "OoPDefl":   "out-of-plane blade-tip displacement (meters)",
        "IPDefl":    "in-plane blade-tip deflection (meters)",
        "BlPitch(1)": "Blade 1 pitch (degrees)",
        "BlPitch(2)": "Blade 2 pitch (degrees)",
        "BlPitch(3)": "Blade 3 pitch (degrees)",
        "Azimuth":   "Azimuth angle for blade 1 (degrees)",
        "RotSpeed":  "Rotor speed (rpm)",
        "NacYaw":    "Nacelle-yaw angle (degrees)",
        "TTDspFA":   "Fore-aft tower-top displacement (meters)",
        "TTDspSS":   "Side-to-side tower-top displacement (meters)",
        "PtfmSurge": "Surge translational displacement (meters)",
        "PtfmSway":  "Sway translational displacement (meters)",
        "PtfmHeave": "Heave translational displacement (meters)",
        "PtfmRoll":  "Roll rotational displacement (degrees)",
        "PtfmPitch": "Pitch rotational displacement  (degrees)",
        "PtfmYaw":   "Yaw rotational displacement (degrees)",
    }

    def __init__(self, main_window=None, parent=None):
        super().__init__(parent)
        self.main_window = main_window  # 부모 윈도우 인스턴스 저장
        
        # 가상의 데이터 저장소 역할 (기존 부모가 제공하던 data_store 대응용)
        self.data_store = {} 
        self._original_switches = {}
        self._original_ic = {}
        self._original_tmax = ""
        self._original_dt = ""
        self._dirty = False
        
        # 최초 1회 화면 구조를 완벽하게 조립합니다.
        self.init_ui()

    def init_ui(self):
        """ 좌측 변수 입력 패널과 우측 콘솔 패널을 완전히 독립적으로 배치 """
        # 메인 가로 레이아웃
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)

        # 좌우 조절용 가로형 스플리터 생성
        main_splitter = QSplitter(Qt.Horizontal)

        # ================= [좌측 영역] 시뮬레이션 변수 입력 패널 =================
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 10, 0)
        left_layout.setSpacing(3)
        
        left_layout.addWidget(QLabel("<h3><b>⚙️ Module Select</b></h3>"))
        
        module_layout = QHBoxLayout()
        module_layout.setContentsMargins(0, 0, 0, 0)
        module_layout.setSpacing(3)
        
        self.cmb_module = QComboBox()
        self.cmb_module.setMinimumHeight(28)
        self.cmb_module.setStyleSheet("""
            QComboBox {
                background-color: #FFFFFF;
                color: #1F2937;
                font-size: 12px;
                border: 1px solid #D1D5DB;
                border-radius: 4px;
                padding: 2px 8px;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox QAbstractItemView {
                background-color: #FFFFFF;
                selection-background-color: #D1D5DB;
                selection-color: #374151;
                font-size: 12px;
            }
        """)
        
        self.cmb_value = QComboBox()
        self.cmb_value.setMinimumHeight(28)
        self.cmb_value.setMaximumWidth(70)
        self.cmb_value.setStyleSheet("""
            QComboBox {
                background-color: #FFFFFF;
                color: #1F2937;
                font-size: 12px;
                border: 1px solid #D1D5DB;
                border-radius: 4px;
                padding: 2px 6px;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox QAbstractItemView {
                background-color: #FFFFFF;
                selection-background-color: #D1D5DB;
                selection-color: #374151;
                font-size: 12px;
            }
            QComboBox QLineEdit {
                alignment: AlignRight;
            }
        """)
        
        module_layout.addWidget(self.cmb_module, stretch=1)
        module_layout.addWidget(self.cmb_value, stretch=0)
        left_layout.addLayout(module_layout)
        
        self._prev_module_val = ""
        self.cmb_module.currentIndexChanged.connect(self._on_module_selected)
        self.cmb_value.currentIndexChanged.connect(self._on_value_selected)
        
        form_param = QFormLayout()
        form_param.setSpacing(3)
        form_param.setContentsMargins(0, 0, 0, 0)
        
        # 입력 위젯 정의 및 기본값 셋팅
        self.txt_tmax = QLineEdit(self.data_store.get("TMax", "600.0"))
        self.txt_tmax.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.txt_dt = QLineEdit(self.data_store.get("DT", "0.0125"))
        self.txt_dt.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.txt_tmax.textChanged.connect(self._on_tmax_dt_changed)
        self.txt_dt.textChanged.connect(self._on_tmax_dt_changed)

        form_param.addRow("", QLabel(""))  # 한 줄 띄우기        
        form_param.addRow(QLabel("<h3><b>⚙️ Simulation Variables</b></h3>"))
        form_param.addRow("⏱️ Total Time (TMax):", self.txt_tmax)
        form_param.addRow("⏱️ Time Step (DT):", self.txt_dt)
        
        form_param.addRow("", QLabel(""))  # 한 줄 띄우기
        form_param.addRow(QLabel("<h3><b>⚙️ Initial Conditions</b></h3>"))
        
        self._ic_widgets = {}
        ic_values = self._load_ic_from_edfile()
        for key, desc in self.INITIAL_CONDITIONS.items():
            val = ic_values.get(key, "0")
            edit = QLineEdit(str(val))
            edit.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            edit.textChanged.connect(self._on_ic_changed)
            form_param.addRow(QLabel(f"📍 {key} ({desc})"), edit)
            self._ic_widgets[key] = edit
        
        left_layout.addLayout(form_param)
        left_layout.addStretch()  # 입력창들을 위로 밀착시킴
        
        bottom_btn_layout = QHBoxLayout()
        bottom_btn_layout.setContentsMargins(0, 0, 0, 0)
        bottom_btn_layout.setSpacing(6)
        
        self.btn_apply = QPushButton("Apply")
        self.btn_apply.setMinimumHeight(38)
        self.btn_apply.setMinimumWidth(230)
        self._update_apply_button(active=False)
        self.btn_apply.clicked.connect(self._on_apply_clicked)
        bottom_btn_layout.addWidget(self.btn_apply, alignment=Qt.AlignLeft)
        
        self.btn_discard = QPushButton("Discard")
        self.btn_discard.setMinimumHeight(38)
        self.btn_discard.setMinimumWidth(230)
        self.btn_discard.clicked.connect(self._on_discard_clicked)
        bottom_btn_layout.addWidget(self.btn_discard, alignment=Qt.AlignRight)
        
        left_layout.addLayout(bottom_btn_layout)
        
        main_splitter.addWidget(left_widget)

        # ================= [우측 영역] 시뮬레이션 진행 모니터링 패널 =================
        right_widget = QWidget()

        # 콘솔 작동 제어용 실행/중지 버튼 배치
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(10, 0, 0, 0)

        console_btn_layout = QHBoxLayout()


        main_splitter.addWidget(right_widget)

        # 💡 보내주신 요구사항 비율(좌측 450px : 우측 650px) 고정 및 메인 장착
        main_splitter.setSizes([450, 650])
        main_layout.addWidget(main_splitter)

        self.refresh_module_switches()



    def on_tab_leave(self):
        """ Main 탭을 떠날 때 변경사항 저장 여부 확인 """
        if self.is_dirty():
            main_win = self.window()
            if main_win:
                summary = self._change_summary()
                reply = QMessageBox.question(
                    main_win,
                    "변경사항 저장",
                    f"Main 탭에서 수정한 내용이 있습니다.\n\n{summary}\n\n변경사항을 적용하시겠습니까?",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.Yes
                )
                if reply == QMessageBox.Yes:
                    self.apply_module_switches()
                else:
                    self.revert_module_switches()

    def _change_summary(self):
        parts = []
        for key in self.MODULE_SWITCHES:
            orig = self._original_switches.get(key, "")
            curr = OpenFastIO.current_config.get(key, {}).get("current") or OpenFastIO.current_config.get(key, {}).get("default") or "0"
            if orig != curr:
                parts.append(f"- {key}: {orig} -> {curr}")
        if self._original_tmax != self.txt_tmax.text():
            parts.append(f"- TMax: {self._original_tmax} -> {self.txt_tmax.text()}")
        if self._original_dt != self.txt_dt.text():
            parts.append(f"- DT: {self._original_dt} -> {self.txt_dt.text()}")
        for key in self.INITIAL_CONDITIONS:
            orig = self._original_ic.get(key, "")
            curr = self._ic_widgets[key].text()
            if orig != curr:
                parts.append(f"- {key}: {orig} -> {curr}")
        return "\n".join(parts) if parts else "변경된 내용이 없습니다."

    def refresh_ui(self):
        """ 독립 위젯이 되면서 동적 레이아웃 재생성이 필요 없어졌습니다. 데이터 동기화가 필요하면 활용하세요. """
        pass

    def collect_inputs(self):
        """ 입력 데이터 취합 함수 """
        return {
            "TMax": self.txt_tmax.text(),
            "DT": self.txt_dt.text()
        }

    def _load_ic_from_edfile(self):
        main_fst = OpenFastIO.current_config.get("MainFST", {}).get("current", "").strip()
        ed_name = (
            OpenFastIO.current_config.get("EDFile", {}).get("current")
            or OpenFastIO.current_config.get("EDFile", {}).get("default", "")
        )
        if not main_fst or not ed_name:
            return {key: "0" for key in self.INITIAL_CONDITIONS}

        ed_path = OpenFastIO.get_absolute_path(main_fst, ed_name)
        if not os.path.exists(ed_path):
            return {key: "0" for key in self.INITIAL_CONDITIONS}

        result = {key: "0" for key in self.INITIAL_CONDITIONS}
        try:
            with open(ed_path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    parts = line.strip().split()
                    if len(parts) >= 2 and parts[0].isdigit() and parts[1] in result:
                        result[parts[1]] = parts[0]
        except Exception:
            pass
        return result

    def refresh_module_switches(self):
        """ 콤보박스 항목을 OpenFastIO.current_config 기준으로 갱신 """
        self.cmb_module.blockSignals(True)
        self.cmb_value.blockSignals(True)
        
        self.cmb_module.clear()
        
        for key in self.MODULE_SWITCHES:
            cfg = OpenFastIO.current_config.get(key, {})
            val = cfg.get("current") or cfg.get("default") or "0"
            desc = self.MODULE_SWITCHES[key].get("desc", "")
            self.cmb_module.addItem(f"{key} : {val} ({desc})", key)
        
        if self.cmb_module.count() > 0:
            self.cmb_module.setCurrentIndex(0)
            self._sync_module_ui()
        
        self.cmb_module.blockSignals(False)
        self.cmb_value.blockSignals(False)

        self._original_switches = {
            key: (OpenFastIO.current_config.get(key, {}).get("current") or OpenFastIO.current_config.get(key, {}).get("default") or "0")
            for key in self.MODULE_SWITCHES
        }
        ic_values = self._load_ic_from_edfile()
        self._original_ic = {key: ic_values.get(key, "0") for key in self.INITIAL_CONDITIONS}
        for key in self.INITIAL_CONDITIONS:
            if key in self._ic_widgets:
                self._ic_widgets[key].blockSignals(True)
                self._ic_widgets[key].setText(ic_values.get(key, "0"))
                self._ic_widgets[key].blockSignals(False)
        self._original_tmax = self.txt_tmax.text()
        self._original_dt = self.txt_dt.text()
        self._dirty = False
        self._update_apply_button(active=False)

    def _on_module_selected(self, index):
        """ 콤보박스 선택 변경 시 값 콤보 및 설명 동기화 """
        if index < 0:
            return
        self._sync_module_ui()

    def _sync_module_ui(self):
        index = self.cmb_module.currentIndex()
        if index < 0:
            return
        key = self.cmb_module.itemData(index)
        cfg = OpenFastIO.current_config.get(key, {})
        val = cfg.get("current") or cfg.get("default") or "0"
        
        allowed = self.MODULE_SWITCHES.get(key, {}).get("values", [])
        self.cmb_value.blockSignals(True)
        self.cmb_value.clear()
        self.cmb_value.addItems(allowed)
        if val in allowed:
            self.cmb_value.setCurrentText(val)
        elif allowed:
            self.cmb_value.setCurrentIndex(0)
        self.cmb_value.blockSignals(False)
        self._prev_module_val = val

    def _on_value_selected(self, index):
        """ 값 콤보 선택 변경 시 current_config 및 모듈 콤보 텍스트 갱신 """
        if index < 0:
            return
        key = self.cmb_module.currentData()
        if not key or key not in self.MODULE_SWITCHES:
            return
        text = self.cmb_value.currentText()
        allowed = self.MODULE_SWITCHES[key]["values"]
        if text in allowed:
            OpenFastIO.current_config[key]["current"] = text
            self._prev_module_val = text
            self.cmb_module.setItemText(self.cmb_module.currentIndex(), f"{key} : {text} ({self.MODULE_SWITCHES[key].get('desc', '')})")
            self._dirty = True
            self._update_apply_button(active=True)

    def _on_tmax_dt_changed(self, text):
        self._dirty = True
        self._update_apply_button(active=True)

    def _on_ic_changed(self, text):
        self._dirty = True
        self._update_apply_button(active=True)

    def _on_apply_clicked(self):
        if self.is_dirty():
            result = self.apply_module_switches()
            if result:
                self._update_apply_button(active=False)

    def _on_discard_clicked(self):
        self.revert_module_switches()
        self._update_apply_button(active=False)

    def _update_apply_button(self, active):
        style_active = """
            QPushButton {
                background-color: #2563EB;
                color: #FFFFFF;
                font-weight: bold;
                font-size: 12px;
                border: 1px solid #1D4ED8;
                border-radius: 4px;
                padding: 6px 12px;
            }
            QPushButton:hover { background-color: #1D4ED8; }
        """
        style_inactive = """
            QPushButton {
                background-color: #E5E7EB;
                color: #374151;
                font-weight: bold;
                font-size: 12px;
                border: 1px solid #D1D5DB;
                border-radius: 4px;
                padding: 6px 12px;
            }
            QPushButton:hover { background-color: #D1D5DB; }
        """
        style = style_active if active else style_inactive
        if hasattr(self, 'btn_apply'):
            self.btn_apply.setStyleSheet(style)
        if hasattr(self, 'btn_discard'):
            self.btn_discard.setStyleSheet(style)

    def is_dirty(self):
        return self._dirty

    def apply_module_switches(self):
        """ 변경된 스위치 값을 메인 .fst 파일에 저장하고, Initial Conditions는 EDFile에 저장 """
        main_fst = OpenFastIO.current_config.get("MainFST", {}).get("current", "")
        if not main_fst or not os.path.exists(main_fst):
            return False

        updated_data = {
            key: (OpenFastIO.current_config.get(key, {}).get("current") or OpenFastIO.current_config.get(key, {}).get("default") or "0")
            for key in self.MODULE_SWITCHES
        }
        updated_data["TMax"] = self.txt_tmax.text()
        updated_data["DT"] = self.txt_dt.text()
        fst_result = OpenFastIO.save_module_data(main_fst, updated_data)

        ed_name = (
            OpenFastIO.current_config.get("EDFile", {}).get("current")
            or OpenFastIO.current_config.get("EDFile", {}).get("default", "")
        )
        ed_result = True
        if ed_name:
            ed_path = OpenFastIO.get_absolute_path(main_fst, ed_name)
            if os.path.exists(ed_path):
                ic_data = {key: self._ic_widgets[key].text() for key in self.INITIAL_CONDITIONS}
                ed_result = OpenFastIO.save_module_data(ed_path, ic_data)

        if fst_result and ed_result:
            self._dirty = False
        return fst_result and ed_result

    def revert_module_switches(self):
        """ 콤보박스 변경사항을 원래 상태로 되돌림 """
        for key, val in self._original_switches.items():
            if key in OpenFastIO.current_config:
                OpenFastIO.current_config[key]["current"] = val
        self.txt_tmax.blockSignals(True)
        self.txt_dt.blockSignals(True)
        self.txt_tmax.setText(self._original_tmax)
        self.txt_dt.setText(self._original_dt)
        self.txt_tmax.blockSignals(False)
        self.txt_dt.blockSignals(False)
        for key, val in self._original_ic.items():
            if key in self._ic_widgets:
                self._ic_widgets[key].blockSignals(True)
                self._ic_widgets[key].setText(val)
                self._ic_widgets[key].blockSignals(False)
        self.refresh_module_switches()


