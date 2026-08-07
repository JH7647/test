import os
import subprocess
from sqlite3 import Time
from PySide6.QtWidgets import (QWidget, QFormLayout, QLineEdit, QLabel, QTextEdit, 
                               QPushButton, QHBoxLayout, QVBoxLayout, QSplitter, QComboBox, QCheckBox, QScrollArea, QFrame)
from PySide6.QtWidgets import QWidget, QVBoxLayout, QComboBox, QMessageBox, QStyleFactory
from PySide6.QtCore import QProcess, Qt
from src.core.openfast_io import OpenFastIO

class MainTab(QWidget):
    MODULE_SWITCHES = {
        "CompElast":  {"value": "", "values": ["1", "2", "3"], "desc": "1=ElastoDyn; 2=BeamDyn; 3=Simplified ElastoDyn"},
        "CompInflow": {"value": "", "values": ["0", "1", "2"], "desc": "0=still air; 1=InflowWind; 2=external from ExtInflow"},
        "CompAero":   {"value": "", "values": ["0", "1", "2", "3"], "desc": "0=None; 1=AeroDisk; 2=AeroDyn; 3=ExtLoads"},
        "CompServo":  {"value": "", "values": ["0", "1"], "desc": "0=None; 1=ServoDyn"},
        "CompSeaSt":  {"value": "", "values": ["0", "1"], "desc": "0=None; 1=SeaState"},
        "CompHydro":  {"value": "", "values": ["0", "1"], "desc": "0=None; 1=HydroDyn"},
        "CompSub":    {"value": "", "values": ["0", "1", "2"], "desc": "0=None; 1=SubDyn; 2=External Platform MCKF"},
        "CompMooring":{"value": "", "values": ["0", "1", "2", "3", "4"], "desc": "0=None; 1=MAP++; 2=FEAMooring; 3=MoorDyn; 4=OrcaFlex"},
        "CompIce":    {"value": "", "values": ["0", "1", "2"], "desc": "0=None; 1=IceFloe; 2=IceDyn"},
        "CompSoil":   {"value": "", "values": ["0", "1"], "desc": "0=None; 1=SoilDyn"},
    }

    INITIAL_CONDITIONS = {
        "OoPDefl":    {"value": "", "desc": "out-of-plane blade-tip displacement (meters)"},
        "IPDefl":     {"value": "", "desc": "in-plane blade-tip deflection (meters)"},
        "BlPitch(1)": {"value": "", "desc": "Blade 1 pitch (degrees)"},
        "BlPitch(2)": {"value": "", "desc": "Blade 2 pitch (degrees)"},
        "BlPitch(3)": {"value": "", "desc": "Blade 3 pitch (degrees)"},
        "Azimuth":    {"value": "", "desc": "Azimuth angle for blade 1 (degrees)"},
        "RotSpeed":   {"value": "", "desc": "Rotor speed (rpm)"},
        "NacYaw":     {"value": "", "desc": "Nacelle-yaw angle (degrees)"},
        "TTDspFA":    {"value": "", "desc": "Fore-aft tower-top displacement (meters)"},
        "TTDspSS":    {"value": "", "desc": "Side-to-side tower-top displacement (meters)"},
        "PtfmSurge":  {"value": "", "desc": "Surge translational displacement (meters)"},
        "PtfmSway":   {"value": "", "desc": "Sway translational displacement (meters)"},
        "PtfmHeave":  {"value": "", "desc": "Heave translational displacement (meters)"},
        "PtfmRoll":   {"value": "", "desc": "Roll rotational displacement (degrees)"},
        "PtfmPitch":  {"value": "", "desc": "Pitch rotational displacement  (degrees)"},
        "PtfmYaw":    {"value": "", "desc": "Yaw rotational displacement (degrees)"},
    }

    MAIN_FST_KEYS = {
        "Description": {"value": "", "desc": "Description of the simulation"}, # Description은 파일의 2번째 줄에 위치
        "Echo":        {"value": "", "desc": "Echo input file parameters to <RootName>.ech"},
        "SumPrint":    {"value": "", "desc": "Print summary data to <RootName>.sum"},
        "TMax":        {"value": "", "desc": "Total run time (s)"},
        "DT":          {"value": "", "desc": "Recommended module time step (s)"},
        "SttsTime":    {"value": "", "desc": "Amount of time between screen status messages (s)"},
        "DT_Out":      {"value": "", "desc": "Time step for tabular output (s) (or 'default')"},
        "TStart":      {"value": "", "desc": "Time to begin tabular output (s)"},
        "OutFileFmt":  {"value": "", "desc": "Format for tabular (time-marching) output file (switch) (1: text file [<RootName>.out], 2: binary file [<RootName>.outb], 3: both 1 and 2, 4: uncompressed binary [<RootName>.outb, 5: both 1 and 4)"},
        "OutFmt":      {"value": "", "desc": "Format used for text tabular output, excluding the time channel.  Resulting field should be 10 characters. (quoted string)"},
    }


    def __init__(self, main_window=None, parent=None):
        super().__init__(parent)
        import copy
        self.main_window = main_window  # 부모 윈도우 인스턴스 저장
        self._dirty = False
        self.module_switches_data = copy.deepcopy(self.MODULE_SWITCHES)
        self.initial_conditions_data = copy.deepcopy(self.INITIAL_CONDITIONS)
        self.main_fst_keys_data = copy.deepcopy(self.MAIN_FST_KEYS)

        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)

#  [상단 영역] 파일 정보 및 저장 버튼 ===========================================================================
        top_bar_layout = QHBoxLayout()
        top_bar_layout.setSpacing(15)

        # --- 1. 파일 경로 ---
        lbl_filename = QLabel("📝 File Name:")
        lbl_filename.setStyleSheet("font-weight: bold; font-size: 14px;")
        self.lbl_file_path = QLabel("N/A")
        self.lbl_file_path.setStyleSheet("font-weight: bold; font-size: 14px;")
        self.lbl_file_path.mouseDoubleClickEvent = self.open_file_in_editor
        top_bar_layout.addWidget(lbl_filename)
        top_bar_layout.addWidget(self.lbl_file_path, 1)
        top_bar_layout.addStretch()

        # --- 2. 저장/취소 버튼 ---
        self.btn_apply = QPushButton("Apply")
        self.btn_discard = QPushButton("Discard")
        self.btn_apply.setStyleSheet("font-size: 14px; font-weight: bold;")
        self.btn_discard.setStyleSheet("font-size: 14px; font-weight: bold;")
        self.btn_apply.setMinimumSize(120, 34)
        self.btn_discard.setMinimumSize(120, 34)
        self.update_apply_button(active=False)
        self.btn_apply.clicked.connect(self.on_apply_clicked)
        self.btn_discard.clicked.connect(self.on_discard_clicked)
        top_bar_layout.addWidget(self.btn_apply)
        top_bar_layout.addWidget(self.btn_discard)

        main_layout.addLayout(top_bar_layout)

        # 좌우 조절용 가로형 스플리터 생성
        main_splitter = QSplitter(Qt.Horizontal)

# region : [LEFT SIDE] Description, Toggles, Module Switches 
# ====================================================================================================
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(10, 10, 10, 0)
        left_layout.setSpacing(3)

        main_left_form = QFormLayout()
        main_left_form.setSpacing(3)
        main_left_form.setContentsMargins(0, 0, 0, 0)

        # --- Section 1: General Settings ---
        gs_title = QLabel("<b>⚙️ General Settings</b>")
        gs_title.setStyleSheet("font-size: 12px; margin-bottom: 3px;")
        main_left_form.addRow(gs_title)

        lbl_file_description = QLabel("📍Description :")
        lbl_file_description.setStyleSheet("font-size: 12px;")
        self.txt_description = QLineEdit()
        self.txt_description.setStyleSheet("font-size: 12px; background-color: white;")
        self.txt_description.textChanged.connect(self.mark_asdirty)
        main_left_form.addRow(lbl_file_description, self.txt_description)

        self.chk_echo = QCheckBox("Create file when check")
        self.chk_echo.setStyleSheet("font-size: 12px;")
        self.chk_echo.stateChanged.connect(self.mark_asdirty)
        
        lbl_echo = QLabel("📍Echo file (Echo) ")
        lbl_echo.setStyleSheet("font-size: 12px;")
        main_left_form.addRow(lbl_echo, self.chk_echo)

        self.chk_sumprint = QCheckBox("Create file when check")
        self.chk_sumprint.setStyleSheet("font-size: 12px;")
        self.chk_sumprint.stateChanged.connect(self.mark_asdirty)
        
        lbl_sum = QLabel("📍Summary file (SumPrint) ")
        lbl_sum.setStyleSheet("font-size: 12px;")
        main_left_form.addRow(lbl_sum, self.chk_sumprint)

        # Separator line for visual separation
        separator = QFrame()
        separator.setStyleSheet("background-color: #C1C5CB; min-height: 1px; max-height: 1px; margin: 5px 0; border: none;")
        main_left_form.addRow(separator)

        # --- Section 2: Module Switches ---
        ms_title = QLabel("<b>⚙️ Module Switches</b>")
        ms_title.setStyleSheet("font-size: 12px; margin-bottom: 3px;")
        main_left_form.addRow(ms_title)
        
        self.module_widgets = {}
        for key, info in self.MODULE_SWITCHES.items():
            combo = QComboBox()

            line_edit = QLineEdit()
            line_edit.setAlignment(Qt.AlignCenter)
            line_edit.setReadOnly(True) 
            combo.setLineEdit(line_edit)

            combo.addItems(info["values"])
            combo.setToolTip(info["desc"])
            combo.setStyleSheet("font-size: 12px; background-color: white;")
            combo.currentIndexChanged.connect(self.mark_asdirty)
            
            ms_label = QLabel(f"📍 {key} : {info['desc']}")
            ms_label.setStyleSheet("font-size: 12px;")
            main_left_form.addRow(ms_label, combo)
            self.module_widgets[key] = combo

        # Separator line for visual separation
        separator = QFrame()
        separator.setStyleSheet("background-color: #C1C5CB; min-height: 1px; max-height: 1px; margin: 5px 0; border: none;")
        main_left_form.addRow(separator)

        # --- Section 3: Output Options ---
        oo_title = QLabel("<b>⚙️ Output Options</b>")
        oo_title.setStyleSheet("font-size: 12px; margin-bottom: 3px;")
        main_left_form.addRow(oo_title)
        
        # 입력 위젯 정의 및 기본값 셋팅
        self.txt_screen_step = QLineEdit()
        self.txt_screen_step.setStyleSheet("background-color: white;")
        self.txt_screen_step.setAlignment(Qt.AlignCenter | Qt.AlignVCenter)
        self.txt_screen_step.textChanged.connect(self.on_output_changed)

        self.txt_write_step = QLineEdit()
        self.txt_write_step.setStyleSheet("background-color: white;")
        self.txt_write_step.setAlignment(Qt.AlignCenter | Qt.AlignVCenter)
        self.txt_write_step.textChanged.connect(self.on_output_changed)

        self.txt_write_time = QLineEdit()
        self.txt_write_time.setStyleSheet("background-color: white;")
        self.txt_write_time.setAlignment(Qt.AlignCenter | Qt.AlignVCenter)
        self.txt_write_time.textChanged.connect(self.on_output_changed)
        
        self.txt_write_binary = QLineEdit()
        self.txt_write_binary.setStyleSheet("background-color: white;")
        self.txt_write_binary.setAlignment(Qt.AlignCenter | Qt.AlignVCenter)   
        self.txt_write_binary.textChanged.connect(self.on_output_changed)

        self.txt_write_digit = QLineEdit()
        self.txt_write_digit.setStyleSheet("background-color: white;")
        self.txt_write_digit.setAlignment(Qt.AlignCenter | Qt.AlignVCenter)
        self.txt_write_digit.textChanged.connect(self.on_output_changed)

        lbl_screen = QLabel("⏱️ Screen Update Interval (SttsTime):")
        lbl_screen.setStyleSheet("font-size: 12px;")
        main_left_form.addRow(lbl_screen, self.txt_screen_step)
        
        lbl_wstep = QLabel("⏱️ File Write Time Step (DT_Out):")
        lbl_wstep.setStyleSheet("font-size: 12px;")
        main_left_form.addRow(lbl_wstep, self.txt_write_step)
        
        lbl_wtime = QLabel("⏱️ Start Time for Output (TStart):")
        lbl_wtime.setStyleSheet("font-size: 12px;")
        main_left_form.addRow(lbl_wtime, self.txt_write_time)
        
        lbl_wbinary = QLabel("💾 Binary Output (OutFileFmt):")
        lbl_wbinary.setStyleSheet("font-size: 12px;")
        main_left_form.addRow(lbl_wbinary, self.txt_write_binary)
        
        lbl_wdigit = QLabel("🔢 Output Precision (OutFmt):")
        lbl_wdigit.setStyleSheet("font-size: 12px;")
        main_left_form.addRow(lbl_wdigit, self.txt_write_digit)

        left_layout.addLayout(main_left_form)
        left_layout.addStretch()
        
        main_splitter.addWidget(left_widget)

# endregion 
# ============================================================================

# region : [RIGHT SIDE] 시뮬레이션 변수 입력 패널 
# ============================================================================
        right_widget = QWidget()
        main_right_layout = QVBoxLayout(right_widget)  # 💡 변수명 충돌 방지를 위해 명칭 변경
        main_right_layout.setContentsMargins(10, 0, 0, 0)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("QScrollArea { border: none; }")
        scroll_content = QWidget()
        scroll_area.setWidget(scroll_content)
        
        scroll_form_layout = QVBoxLayout(scroll_content)
        scroll_form_layout.setSpacing(10)

        main_form_layout = QFormLayout()
        main_form_layout.setSpacing(3)
        main_form_layout.setContentsMargins(0, 0, 0, 0)
        
        # 입력 위젯 정의 및 기본값 셋팅
        self.txt_tmax = QLineEdit()
        self.txt_tmax.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.txt_dt = QLineEdit()
        self.txt_dt.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.txt_tmax.textChanged.connect(self.on_output_changed)
        self.txt_dt.textChanged.connect(self.on_output_changed)

        # Simulation Control 타이틀 행 추가
        sc_title = QLabel("<b>⚙️ Simulation Control</b>")
        sc_title.setStyleSheet("font-size: 12px; margin-bottom: 3px;")
        main_form_layout.addRow(sc_title)
        
        # 💡 styleSheet 인자 오류를 setStyleSheet 문법 혹은 HTML 방식으로 안전하게 수정
        tmax_label = QLabel("⏱️ Total Time (TMax):")
        tmax_label.setStyleSheet("font-size: 12px;")
        main_form_layout.addRow(tmax_label, self.txt_tmax)
        
        dt_label = QLabel("⏱️ Time Step (DT):")
        dt_label.setStyleSheet("font-size: 12px;")
        main_form_layout.addRow(dt_label, self.txt_dt)

        # Separator line for visual separation
        separator = QFrame()
        separator.setStyleSheet("background-color: #C1C5CB; min-height: 1px; max-height: 1px; margin: 5px 0; border: none;")
        main_form_layout.addRow(separator)

        # Initial Conditions 타이틀 행 추가
        ic_title = QLabel("<b>⚙️ Initial Conditions</b>")
        ic_title.setStyleSheet("font-size: 12px; margin-bottom: 3px;")
        main_form_layout.addRow(ic_title)

        # Initial Conditions 항목 리스트 동적 추가
        self.ic_widgets = {}
        for key, info in self.INITIAL_CONDITIONS.items():
            edit = QLineEdit()
            edit.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            edit.textChanged.connect(self.on_ic_changed)
            
            ic_label = QLabel(f"📍 {key} ({info['desc']})")
            ic_label.setStyleSheet("font-size: 12px;")
            
            # 💡 하나의 통합 폼 레이아웃에 순서대로 누적해 줍니다.
            main_form_layout.addRow(ic_label, edit)
            self.ic_widgets[key] = edit
            
        # 💡 스크롤 내부 레이아웃에 통합된 폼 레이아웃 장착 (중복 addLayout 코드 모두 삭제)
        scroll_form_layout.addLayout(main_form_layout)
        scroll_form_layout.addStretch()
        
        # 최상단 메인 레이아웃에 스크롤 영역 최종 조립
        main_right_layout.addWidget(scroll_area)
        main_splitter.addWidget(right_widget)
        
        main_layout.addWidget(main_splitter)
        main_splitter.setSizes([400, 500])

# endregion 
# ============================================================================================================

    def open_file_in_editor(self, event):
        """ lbl_file_path를 더블 클릭했을 때 Notepad++로 파일을 엽니다. """
        file_path = self.lbl_file_path.text()
        if not file_path or not os.path.exists(file_path):
            QMessageBox.warning(self, "파일 오류", "유효한 파일 경로가 아닙니다.")
            return

        npp_path = r"C:\Program Files\Notepad++\notepad++.exe"
        try:
            if os.path.exists(npp_path):
                subprocess.Popen([npp_path, file_path])
                print(f"🚀 Notepad++ 오픈 완수: {os.path.basename(file_path)}")
            else:
                # Notepad++가 없으면 기본 메모장으로 엽니다.
                subprocess.Popen(["notepad.exe", file_path])
                print(f"📝 Notepad++ 미설치로 기본 메모장 우회 구동: {os.path.basename(file_path)}")
        except Exception as e:
            QMessageBox.critical(self, "실행 오류", f"파일을 여는 중 오류가 발생했습니다:\n{str(e)}")

    def on_tab_enter(self):
        """ 탭에 들어올 때마다 UI를 새로고침합니다. """
        self.refresh_ui()

    def on_tab_leave(self):
        """ Main 탭을 떠날 때 변경사항 저장 여부 확인 """
        if self.isdirty():
            main_win = self.window()
            if main_win:
                summary = self.change_summary()
                reply = QMessageBox.question(
                    main_win,
                    "변경사항 저장",
                    f"Main 탭에서 수정한 내용이 있습니다.\n\n{summary}\n\n변경사항을 적용하시겠습니까?",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.Yes
                )
                if reply == QMessageBox.Yes:
                    self.apply_values_to_file()
                else:
                    self.discard_changes()

    def change_summary(self):
        parts = []
        for key, info in self.module_switches_data.items():
            orig = info.get("value", "0")
            curr = self.module_widgets[key].currentText()
            if orig != curr: 
                parts.append(f"- {key}: {orig} -> {curr}")

        if self.main_fst_keys_data["TMax"]["value"]                  != self.txt_tmax.text():         parts.append(f"- TMax: {self.main_fst_keys_data['TMax']['value']} -> {self.txt_tmax.text()}")
        if self.main_fst_keys_data["DT"]["value"]                    != self.txt_dt.text():           parts.append(f"- DT: {self.main_fst_keys_data['DT']['value']} -> {self.txt_dt.text()}")
        if self.main_fst_keys_data["Description"]["value"]           != self.txt_description.text():  parts.append(f"- Description: ... -> ...")
        if str(self.main_fst_keys_data["Echo"]["value"]).lower()     != str(self.chk_echo.isChecked()).lower():       parts.append(f"- Echo: {self.main_fst_keys_data['Echo']['value']} -> {self.chk_echo.isChecked()}")
        if str(self.main_fst_keys_data["SumPrint"]["value"]).lower() != str(self.chk_sumprint.isChecked()).lower():   parts.append(f"- SumPrint: {self.main_fst_keys_data['SumPrint']['value']} -> {self.chk_sumprint.isChecked()}")
        if self.main_fst_keys_data["SttsTime"]["value"]              != self.txt_screen_step.text():  parts.append(f"- SttsTime: {self.main_fst_keys_data['SttsTime']['value']} -> {self.txt_screen_step.text()}")
        if self.main_fst_keys_data["DT_Out"]["value"]                != self.txt_write_step.text():   parts.append(f"- DT_Out: {self.main_fst_keys_data['DT_Out']['value']} -> {self.txt_write_step.text()}")
        if self.main_fst_keys_data["TStart"]["value"]                != self.txt_write_time.text():   parts.append(f"- TStart: {self.main_fst_keys_data['TStart']['value']} -> {self.txt_write_time.text()}")
        if self.main_fst_keys_data["OutFileFmt"]["value"]            != self.txt_write_binary.text(): parts.append(f"- OutFileFmt: {self.main_fst_keys_data['OutFileFmt']['value']} -> {self.txt_write_binary.text()}")
        if self.main_fst_keys_data["OutFmt"]["value"]                != self.txt_write_digit.text():  parts.append(f"- OutFmt: {self.main_fst_keys_data['OutFmt']['value']} -> {self.txt_write_digit.text()}")

        for key, info in self.initial_conditions_data.items():
            orig = info.get("value", "")
            curr = self.ic_widgets[key].text()
            if orig != curr: 
                parts.append(f"- {key}: {orig} -> {curr}")

        return "\n".join(parts) if parts else "변경된 내용이 없습니다."


    def load_ic_from_edfile(self): # _load_ic_from_edfile에서 이름 변경
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

        result = {key: {"value": "0"} for key in self.INITIAL_CONDITIONS}
        try:
            with open(ed_path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    parts = line.strip().split()
                    # parts[0]이 숫자이고 parts[1]이 INITIAL_CONDITIONS의 키에 해당하는 경우
                    if len(parts) >= 2 and parts[1] in result:
                        result[parts[1]]["value"] = parts[0].strip('"\'') # value 필드에 값 저장
        except Exception:
            pass
        return result

    def load_main_from_fst(self):
        """ MAIN_FST_KEYS에 정의된 주요 파라미터들을 메인 .fst 파일에서 직접 읽어옵니다. """
        main_fst = OpenFastIO.current_config.get("MainFST", {}).get("current", "").strip()
        if not main_fst or not os.path.exists(main_fst):
            return {key: {"value": info["value"]} for key, info in self.main_fst_keys_data.items()}

        result = {key: {"value": info["value"]} for key, info in self.main_fst_keys_data.items()}
        try:
            with open(main_fst, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
                if len(lines) > 1:
                    result["Description"]["value"] = lines[1].strip()

                for line in lines:
                    parts = line.strip().split()
                    if len(parts) < 2:
                        continue
                    
                    key = parts[1]
                    if key in result: # MAIN_FST_KEYS에 정의된 키인 경우
                        value = parts[0].strip()
                        result[key]["value"] = value
        except Exception:
            pass
        return result
    
    def refresh_ui(self):
        """ 콤보박스 항목을 OpenFastIO.current_config 기준으로 갱신 """
        # Block signals for all module widgets
        widgets_to_block = list(self.module_widgets.values()) + list(self.ic_widgets.values()) + \
                           [self.txt_tmax, self.txt_dt, self.txt_description, self.chk_echo, self.chk_sumprint, self.txt_screen_step, self.txt_write_step, self.txt_write_time, self.txt_write_binary, self.txt_write_digit]
        for widget in widgets_to_block:
            widget.blockSignals(True)
        
        main_fst_data = self.load_main_from_fst()

        main_fst_path = OpenFastIO.current_config.get("MainFST", {}).get("current", "")
        if main_fst_path and os.path.exists(main_fst_path):
            self.lbl_file_path.setText(main_fst_path)
        else:
            self.lbl_file_path.setText("N/A")

        # Update self.main_fst_keys_data with loaded values
        for key, data in main_fst_data.items():
            if key in self.main_fst_keys_data:
                self.main_fst_keys_data[key]["value"] = data["value"]

        description = self.main_fst_keys_data["Description"]["value"]
        self.txt_description.setText(description)

        echo_val = str(self.main_fst_keys_data["Echo"]["value"]).lower() == "true"
        sumprint_val = str(self.main_fst_keys_data["SumPrint"]["value"]).lower() == "true"
        self.chk_echo.setChecked(echo_val)
        self.chk_sumprint.setChecked(sumprint_val)

        tmax = self.main_fst_keys_data["TMax"]["value"]
        dt = self.main_fst_keys_data["DT"]["value"]
        self.txt_tmax.setText(tmax)
        self.txt_dt.setText(dt)
        
        sttstime = self.main_fst_keys_data["SttsTime"]["value"]
        dt_out = self.main_fst_keys_data["DT_Out"]["value"]
        tstart = self.main_fst_keys_data["TStart"]["value"]
        outfilefmt = self.main_fst_keys_data["OutFileFmt"]["value"]
        outfmt = self.main_fst_keys_data["OutFmt"]["value"]
        
        self.txt_screen_step.setText(sttstime)
        self.txt_write_step.setText(dt_out)
        self.txt_write_time.setText(tstart)
        self.txt_write_binary.setText(outfilefmt)
        self.txt_write_digit.setText(outfmt)
        for key, combo in self.module_widgets.items():
            cfg = OpenFastIO.current_config.get(key, {})
            val = cfg.get("current") or cfg.get("default") or "0"
            self.module_switches_data[key]["value"] = val # 원본 값 저장
            if combo.findText(val) != -1:
                combo.setCurrentText(val)
            else:
                combo.setCurrentIndex(0)

        # Unblock signals
        for widget in widgets_to_block:
            widget.blockSignals(False)
            
        # --- 원본 값 저장 (변경사항 추적용) ---
        ic_values = self.load_ic_from_edfile()
        self.initial_conditions_data = ic_values
        for key in self.INITIAL_CONDITIONS:
            if key in self.ic_widgets:
                self.ic_widgets[key].blockSignals(True)
                self.ic_widgets[key].setText(ic_values.get(key, {}).get("value", "0"))
                self.ic_widgets[key].blockSignals(False)
        self._dirty = False
        self.update_apply_button(active=False)

    def on_tab_enter(self):
        """ 탭에 들어올 때마다 UI를 새로고침합니다. """
        self.refresh_ui()

    def mark_asdirty(self, *args): 
        self._dirty = True
        self.update_apply_button(active=True)

        # 💡 [수정] 변경된 콤보박스 값을 OpenFastIO.current_config에 즉시 반영
        sender = self.sender()
        if isinstance(sender, QComboBox):
            for key, widget in self.module_widgets.items():
                if widget == sender:
                    OpenFastIO.current_config[key]["current"] = sender.currentText()

    def on_output_changed(self, text):
        self._dirty = True
        self.update_apply_button(active=True)

    def on_ic_changed(self, text):
        self._dirty = True
        self.update_apply_button(active=True)

    def on_apply_clicked(self):
        if self.isdirty(): 
            result = self.apply_values_to_file()
            if result:
                self.update_apply_button(active=False)

    def on_discard_clicked(self):
        self.discard_changes() # discard_change에서 이름 변경
        self.update_apply_button(active=False)

    def update_apply_button(self, active):
        style_active = """
            QPushButton {
                background-color: #2563EB;
                color: #FFFFFF; font-weight: bold; font-size: 14px; padding: 6px 22px;
                border: 1px solid #1D4ED8;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #1D4ED8; }
        """
        style_inactive = """
            QPushButton {
                background-color: #E5E7EB;
                color: #9CA3AF; font-weight: bold; font-size: 14px; padding: 6px 22px;
                border: 1px solid #D1D5DB;
                border-radius: 4px;
            }
        """
        style = style_active if active else style_inactive
        self.btn_apply.setStyleSheet(style)
        self.btn_discard.setStyleSheet(style)

    def isdirty(self): 
        return self._dirty

    def apply_values_to_file(self):
        """ 변경된 스위치 값을 메인 .fst 파일에 저장하고, Initial Conditions는 EDFile에 저장 """
        main_fst = OpenFastIO.current_config.get("MainFST", {}).get("current", "")
        if not main_fst or not os.path.exists(main_fst):
            return False

        updated_data = {
            key: combo.currentText()
            for key, combo in self.module_widgets.items()
        }
        updated_data["TMax"] = self.txt_tmax.text()
        updated_data["DT"] = self.txt_dt.text()
        updated_data["Echo"] = str(self.chk_echo.isChecked()).lower()
        updated_data["SumPrint"] = str(self.chk_sumprint.isChecked()).lower()
        updated_data["SttsTime"] = self.txt_screen_step.text()
        updated_data["DT_Out"] = self.txt_write_step.text()
        updated_data["TStart"] = self.txt_write_time.text()
        updated_data["OutFileFmt"] = self.txt_write_binary.text()
        updated_data["OutFmt"] = self.txt_write_digit.text()
        # Description은 특수 처리
        fst_result = OpenFastIO.save_module_data(main_fst, updated_data, description=self.txt_description.text()) # save_module_data에 description 전달

        ed_name = (
            OpenFastIO.current_config.get("EDFile", {}).get("current", "")
            or OpenFastIO.current_config.get("EDFile", {}).get("default", "")
        )
        ed_result = True
        if ed_name:
            ed_path = OpenFastIO.get_absolute_path(main_fst, ed_name)
            if os.path.exists(ed_path):
                ic_data = {key: self.ic_widgets[key].text() for key in self.INITIAL_CONDITIONS}
                ed_result = OpenFastIO.save_module_data(ed_path, ic_data)

        if fst_result and ed_result:
            self._dirty = False
            self.refresh_ui() # 저장 후 원본 값들을 다시 로드하여 동기화
        return fst_result and ed_result

    def discard_changes(self): 
        """ 콤보박스 변경사항을 원래 상태로 되돌림 """
        # Block signals for all module widgets
        widgets_to_revert = list(self.module_widgets.values()) + list(self.ic_widgets.values()) + \
                            [self.txt_tmax, self.txt_dt, self.txt_description, self.chk_echo, self.chk_sumprint, self.txt_screen_step, self.txt_write_step, self.txt_write_time, self.txt_write_binary, self.txt_write_digit]
        for widget in widgets_to_revert:
            widget.blockSignals(True)

        self.txt_description.setText(self.main_fst_keys_data["Description"]["value"])
        self.chk_echo.setChecked(str(self.main_fst_keys_data["Echo"]["value"]).lower() == 'true')
        self.chk_sumprint.setChecked(str(self.main_fst_keys_data["SumPrint"]["value"]).lower() == 'true')
        self.txt_tmax.setText(self.main_fst_keys_data["TMax"]["value"])
        self.txt_dt.setText(self.main_fst_keys_data["DT"]["value"])
        self.txt_screen_step.setText(self.main_fst_keys_data["SttsTime"]["value"])
        self.txt_write_step.setText(self.main_fst_keys_data["DT_Out"]["value"])
        self.txt_write_time.setText(self.main_fst_keys_data["TStart"]["value"])
        self.txt_write_binary.setText(self.main_fst_keys_data["OutFileFmt"]["value"])
        self.txt_write_digit.setText(self.main_fst_keys_data["OutFmt"]["value"])

        for key, info in self.initial_conditions_data.items():
            if key in self.ic_widgets:
                self.ic_widgets[key].setText(info.get("value", "0"))

        for key, combo in self.module_widgets.items():
            combo.setCurrentText(self.module_switches_data[key].get("value", "0"))

        for widget in widgets_to_revert:
            widget.blockSignals(False)

        self._dirty = False
        self.update_apply_button(active=False)
