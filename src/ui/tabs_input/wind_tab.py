import os
import copy
import sys
import subprocess 
import json
import shutil

from datetime import datetime
from logging import config

from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QTabWidget, QLabel, QTreeView, QSplitter, QFormLayout  
from PySide6.QtWidgets import QMessageBox, QFileDialog, QWidget, QVBoxLayout, QFormLayout, QCheckBox
from PySide6.QtCore import QPoint, QSettings, Qt, QPoint, QSettings, QProcess
from PySide6.QtGui import QStandardItemModel, QStandardItem
from PySide6.QtWidgets import (QTextEdit, QPushButton, QHBoxLayout,QWidget, QVBoxLayout, QFormLayout, 
                               QCheckBox, QComboBox, QLineEdit, QLabel, QPushButton)

from PySide6.QtWidgets import QFileDialog, QInputDialog, QMessageBox, QWidget, QVBoxLayout, QTreeView, QWidget, QVBoxLayout, QFormLayout, QCheckBox, QComboBox
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, 
                               QLabel, QLineEdit, QCheckBox, QComboBox, 
                               QSplitter, QStackedWidget, QPushButton, QFileDialog,QFrame,
                               QTreeView, QAbstractItemView)

from src.core.openfast_io import OpenFastIO  # 코어 엔진 임포트

class WindTab(QWidget):
    WIND_KEYS = {
        "Echo":         {"value": "False"},
        "WindType":     {"value": "1"},
        "HWindSpeed":   {"value": "0.0"},
        "RefHt":        {"value": "0.0"},
        "PLExp":        {"value": "0.0"},
        "FileName_Uni": {"value": ""},
        "RefHt_Uni":    {"value": "0.0"},
        "RefLength":    {"value": "0.0"},
        "FileName_BTS": {"value": ""},
        "NWindVel":     {"value": "0"},
        "WindVziList":  {"value": ""},
        "SumPrint":     {"value": "False"},
        "TimeInterp":   {"value": "False"}, # Cubic Interpolation
    }

    OUTPUT_LIST = {
        "Wind1VelX":   {"value": "1", "desc": "X-direction wind velocity at point WindList(1)"},
        "Wind1VelY":   {"value": "1", "desc": "Y-direction wind velocity at point WindList(1)"},
        "Wind1VelZ":   {"value": "1", "desc": "Z-direction wind velocity at point WindList(1)"}
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        import copy
        self._dirty = False
        self.wind_data = copy.deepcopy(self.WIND_KEYS)
        self.init_ui()
        
    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)

#  [상단 영역] 파일 정보 및 저장 버튼 
# ---------------------------------------------------------------------------------------------------
        top_bar_layout = QHBoxLayout()
        top_bar_layout.setSpacing(15)

        # --- 1. 파일 경로 ---
        key_CompInflow = OpenFastIO.current_config.get("CompInflow", {}).get("current", "")
        
        is_still_wind = key_CompInflow in ("0", "")
        if key_CompInflow in ("0", ""):
            FileName = "Still Wind Case (CompInflow=0)"
            FilePath = ""
        else:
            FileName = "📝 File Name:"
            inflow_file_info = OpenFastIO.current_config.get("InflowFile", {})
            inflow_file_path = inflow_file_info.get("current") or inflow_file_info.get("default", "N/A")
            FilePath = OpenFastIO.get_absolute_path(OpenFastIO.current_config.get("MainFST", {}).get("current", ""), inflow_file_path)

        lbl_filename = QLabel(FileName)
        lbl_filename.setStyleSheet("font-weight: bold; font-size: 14px;")
        self.lbl_file_path = QLabel(FilePath)
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
        self.btn_apply.clicked.connect(self.apply_values_to_file)
        self.btn_discard.clicked.connect(self.discard_changes)
        top_bar_layout.addWidget(self.btn_apply)
        top_bar_layout.addWidget(self.btn_discard)

        main_layout.addLayout(top_bar_layout)

        # 좌우 조절용 가로형 스플리터 생성
        main_splitter = QSplitter(Qt.Horizontal)
# ---------------------------------------------------------------------------------------------------

# region : [LEFT SIDE] Description, Toggles, Module Switches 
# ====================================================================================================
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)    
        left_layout.setContentsMargins(10, 10, 10, 0)
        left_layout.setSpacing(3)

        left_layout.addWidget(QLabel("<b style='font-size:13px;'>⚙️ General settings</b>"))

        # --- Description, Echo, SumPrint ---
        form_layout = QFormLayout()
        form_layout.setSpacing(3)
        form_layout.setContentsMargins(0, 0, 0, 0)
        
        lbl_file_description = QLabel("📍Description :")
        self.txt_description = QLineEdit()
        self.txt_description.setStyleSheet("font-size: 12px; background-color: white;")
        self.txt_description.textChanged.connect(self.mark_asdirty)
        form_layout.addRow(lbl_file_description, self.txt_description)

        self.chk_echo = QCheckBox("Create file when check")
        self.chk_echo.stateChanged.connect(self.mark_asdirty)
        form_layout.addRow("📍Echo file (Echo) ", self.chk_echo)

        self.chk_sumprint = QCheckBox("Create file when check")
        self.chk_sumprint.stateChanged.connect(self.mark_asdirty)
        form_layout.addRow("📍Summary file (SumPrint) ", self.chk_sumprint)

        left_layout.addLayout(form_layout)

        # Separator line for visual separation
        separator = QFrame()
        separator.setStyleSheet("background-color: #C1C5CB; min-height: 1px; max-height: 1px; margin: 5px 0; border: none;")
        left_layout.addWidget(separator)

        # --- Module Switches ---
        left_layout.addWidget(QLabel("<b style='font-size:12px;'>⚙️ Wind define </b>"))
   
        module_form_layout = QFormLayout()
        module_form_layout.setSpacing(3)
        module_form_layout.setContentsMargins(0, 0, 0, 0)

        # WindType 콤보박스 (핵심 컨트롤러)
        self.combo_wind_type = QComboBox()
        self.combo_wind_type.addItems([
            "1: Steady Wind (정상류)",
            "2: Uniform Wind (균일풍)",
            "3: Binary TurbSim Full-Field (.bts)",
            "4: Binary Bladed-style FF (.wnd)",
            "5: HAWC format binary files",
            "7: Native Bladed FF"
        ])
        self.combo_wind_type.currentIndexChanged.connect(self.mark_asdirty)
        self.combo_wind_type.currentIndexChanged.connect(self.on_wind_type_changed)
        module_form_layout.addRow("📍 WindType :", self.combo_wind_type)

        # 출력 포인트 설정
        self.txt_nwindvel = QLineEdit("1")
        self.txt_nwindvel.setFixedWidth(80)
        self.txt_nwindvel.textChanged.connect(self.mark_asdirty)
        module_form_layout.addRow("📍 NWindVel (Points) :", self.txt_nwindvel)
        
        # 좌표 리스트 (단순화를 위해 콤마 분리 입력창으로 예시)
        self.txt_vzi_list = QLineEdit("87")
        self.txt_vzi_list.textChanged.connect(self.mark_asdirty)
        module_form_layout.addRow("📍 WindVziList (Z m) :", self.txt_vzi_list)
        left_layout.addLayout(module_form_layout)

        left_layout.addLayout(module_form_layout)
    
        # Separator line for visual separation
        separator = QFrame()
        separator.setStyleSheet("background-color: #C1C5CB; min-height: 1px; max-height: 1px; margin: 5px 0; border: none;")
        left_layout.addWidget(separator)

        # --- Output Options ---
        left_layout.addWidget(QLabel("<b style='font-size:12px;'>⚙️ Output Options</b>"))

        # Output Variable Selector
        # -----------------------------------------------------------------------------------------------
        output_selector_layout = QHBoxLayout()

        # 1. 좌측 트리 (Available)
        self.output0_tree = QTreeView()
        self.output0_tree.setHeaderHidden(True)
        self.output0_model = QStandardItemModel()
        self.output0_tree.setModel(self.output0_model)
        self.output0_tree.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.output0_tree.setMouseTracking(True)
        self.output0_tree.setIndentation(0)  
        self.output0_tree.entered.connect(self.on_output_tree_entered)
        self.output0_tree.viewport().setMouseTracking(True) # Viewport에서도 마우스 추적
        self.output0_tree.setStyleSheet("""
            QTreeView {
                background-color: #FFFFFF;
                border: 1px solid #D1D5DB;
                font-size: 12px;
                color: #1F2937;
            }
            QTreeView::item:selected {
                background-color: #D1D5DB;
                color: #1F2937;
                font-weight: bold;
            }
        """)

        for key in self.OUTPUT_LIST.keys():
            item = QStandardItem(key)
            item.setEditable(False)
            self.output0_model.appendRow(item)

        output_selector_layout.addWidget(self.output0_tree)

        # 2. 중간 버튼 (>, <)
        button_layout = QVBoxLayout()
        button_layout.addStretch()
        self.btn_move_to_selected = QPushButton(">")
        self.btn_move_to_selected.setFixedWidth(30)
        self.btn_move_to_selected.setStyleSheet("font-weight: bold; font-size: 18px;")
        self.btn_move_to_selected.clicked.connect(self.move_items_to_selected)
        button_layout.addWidget(self.btn_move_to_selected)

        self.btn_move_to_available = QPushButton("<")
        self.btn_move_to_available.setFixedWidth(30)
        self.btn_move_to_available.setStyleSheet("font-weight: bold; font-size: 18px;")
        self.btn_move_to_available.clicked.connect(self.move_items_to_available)
        button_layout.addWidget(self.btn_move_to_available)
        button_layout.addStretch()
        output_selector_layout.addLayout(button_layout)

        # 3. 우측 트리 (Selected)
        self.output1_tree = QTreeView()
        self.output1_tree.setHeaderHidden(True)
        self.output1_model = QStandardItemModel()
        self.output1_tree.setModel(self.output1_model)
        self.output1_tree.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.output1_tree.setIndentation(0)
        self.output1_tree.setStyleSheet("""
            QTreeView {
                background-color: #FFFFFF;
                border: 1px solid #D1D5DB;
                font-size: 12px;
                color: #1F2937;
            }
            QTreeView::item:selected {
                background-color: #D1D5DB;
                color: #1F2937;
                font-weight: bold;
            }
        """)
        output_selector_layout.addWidget(self.output1_tree)


        # 라벨 추가
        labels_layout = QHBoxLayout()
        available_label = QLabel("📍 Available Variable List")
        selected_label  = QLabel("  Selected Variable List")
        labels_layout.addWidget(available_label)
        labels_layout.addSpacing(50) # 버튼 공간만큼
        labels_layout.addWidget(selected_label)

        left_layout.addLayout(labels_layout)
        left_layout.addLayout(output_selector_layout)
        # -----------------------------------------------------------------------------------------------

        left_layout.addStretch()
        main_splitter.addWidget(left_widget)

 # endregion 
# ============================================================================  
      
        # ==========================================
        # [2] 우측 패널: 동적 Stacked Widget 영역
        # ==========================================
        self.stacked_panel = QStackedWidget()
        self.stacked_panel.setStyleSheet("background-color: #FAFAFA; border-left: 1px solid #E5E7EB;")
        
        # 페이지 등록 기능 함수 호출
        self.page_steady = self.create_steady_page()   # Type 1
        self.page_uniform = self.create_uniform_page() # Type 2
        self.page_turb_sim = self.create_bts_page()    # Type 3
        
        self.stacked_panel.addWidget(self.page_steady)
        self.stacked_panel.addWidget(self.page_uniform)
        self.stacked_panel.addWidget(self.page_turb_sim)
        
        main_splitter.addWidget(self.stacked_panel)
        
        # 스플리터 비율 조절 (좌측 4, 우측 6)
        main_splitter.setSizes([400, 600])
        main_layout.addWidget(main_splitter)

        # 컨트롤 패널과 안내 메시지를 모두 생성해두고, on_tab_enter에서 상태를 전환합니다.
        self.main_splitter = main_splitter
        self.info_label = QLabel("<h2>Still Wind Case</h2><p>No InflowFile is used when CompInflow is 0.</p>")
        self.info_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(self.info_label, 1)

        # 초기 상태 설정
        self.info_label.setVisible(is_still_wind)
        self.main_splitter.setVisible(not is_still_wind)

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
        """ Wind 탭에 진입할 때마다 UI를 새로고침합니다. """
        key_CompInflow = OpenFastIO.current_config.get("CompInflow", {}).get("current", "")
        is_still_wind = key_CompInflow in ("0", "")

        self.info_label.setVisible(is_still_wind)
        self.main_splitter.setVisible(not is_still_wind)

        if not is_still_wind:
            self.refresh_ui_from_file()
        else:
            self.update_apply_button(active=False)

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




    def on_output_tree_entered(self, index):
        """ 마우스가 Available 트리 아이템 위에 올라갔을 때 상태바에 설명 표시 """
        if not index.isValid():
            return

        item_key = index.data(Qt.DisplayRole)
        if item_key in self.OUTPUT_LIST:
            description = self.OUTPUT_LIST[item_key].get("desc", "No description available.")
            # 부모 윈도우(main_window)를 통해 상태바에 접근
            main_win = self.window()
            if hasattr(main_win, 'statusBar'):
                main_win.statusBar().showMessage(description, 3000) # 3초간 표시

    def move_items_to_selected(self):
        """ 왼쪽(Available)에서 오른쪽(Selected)으로 아이템 이동 """
        selected_indexes = self.output0_tree.selectionModel().selectedRows()
        if not selected_indexes:
            return

        # 뒤에서부터 제거해야 인덱스가 꼬이지 않음
        for index in sorted(selected_indexes, key=lambda idx: idx.row(), reverse=True):
            item = self.output0_model.takeRow(index.row())[0]
            self.output1_model.appendRow(item)
        self.mark_asdirty()

    def move_items_to_available(self):
        """ 오른쪽(Selected)에서 왼쪽(Available)으로 아이템 이동 """
        selected_indexes = self.output1_tree.selectionModel().selectedRows()
        if not selected_indexes:
            return

        for index in sorted(selected_indexes, key=lambda idx: idx.row(), reverse=True):
            item = self.output1_model.takeRow(index.row())[0]
            self.output0_model.appendRow(item)
        
        # 원래 순서대로 정렬
        original_order = list(self.OUTPUT_LIST.keys())
        current_items = [self.output0_model.item(i).text() for i in range(self.output0_model.rowCount())]
        
        # 정렬이 필요한 경우에만 수행
        if sorted(current_items, key=original_order.index) != current_items:
            # 임시 리스트에 아이템 저장
            items_to_sort = []
            while self.output0_model.rowCount() > 0:
                items_to_sort.append(self.output0_model.takeRow(0)[0])
            
            # 원래 순서에 따라 다시 추가
            sorted_items = sorted(items_to_sort, key=lambda item: original_order.index(item.text()))
            for item in sorted_items:
                self.output0_model.appendRow(item)

        self.mark_asdirty()





    # 페이지 생성 서브 함수들 (예시용 일부 구현) 
    # --------------------------------------------------------------------------------------------------------
    def create_steady_page(self):
        page = QWidget()
        layout = QFormLayout(page)
        layout.addWidget(QLabel("<b>🍃 Steady Wind Parameters (WindType = 1)</b>"))
        self.txt_hwindspeed = QLineEdit()
        self.txt_hwindspeed.textChanged.connect(self.mark_asdirty)
        self.txt_refht = QLineEdit()
        self.txt_refht.textChanged.connect(self.mark_asdirty)
        self.txt_plexp = QLineEdit()
        self.txt_plexp.textChanged.connect(self.mark_asdirty)
        layout.addRow("HWindSpeed (m/s) :", self.txt_hwindspeed)
        layout.addRow("RefHt (m) :", self.txt_refht)
        layout.addRow("PLExp (-) :", self.txt_plexp)
        return page

    def create_uniform_page(self):
        page = QWidget()
        layout = QFormLayout(page)
        layout.addWidget(QLabel("<b>💨 Uniform Wind Parameters (WindType = 2)</b>"))
        
        # 파일 브라우저 스타일 예시
        file_layout = QHBoxLayout()
        self.txt_filename_uni = QLineEdit("unused.hh")
        btn_browse = QPushButton("📂")
        btn_browse.setFixedWidth(35)
        file_layout.addWidget(self.txt_filename_uni)
        file_layout.addWidget(btn_browse)
        
        layout.addRow("FileName_Uni :", file_layout)
        layout.addRow("RefHt_Uni (m) :", QLineEdit("90.0"))
        layout.addRow("RefLength (m) :", QLineEdit("125.88"))
        return page

    def create_bts_page(self):
        page = QWidget()
        layout = QFormLayout(page)
        layout.addWidget(QLabel("<b>🌪️ TurbSim Full-Field Parameters (WindType = 3)</b>"))
        
        file_layout = QHBoxLayout()
        self.txt_filename_bts = QLineEdit()
        self.txt_filename_bts.textChanged.connect(self.mark_asdirty)
        txt_file = self.txt_filename_bts
        btn_browse = QPushButton("📂")
        btn_browse.setFixedWidth(35)
        file_layout.addWidget(txt_file)
        file_layout.addWidget(btn_browse)
        
        layout.addRow("FileName_BTS :", file_layout)
        return page

    def on_wind_type_changed(self, index):
        # 콤보박스 인덱스에 따라 stackedWidget 페이지를 전환 (1, 2, 3번 위주 맵핑 예시)
        if index in [0, 1, 2]:
            self.stacked_panel.setCurrentIndex(index)
        else:
            # 아직 구현 안 된 4, 5, 7번 선택 시 빈 페이지나 경고 뷰 처리
            self.stacked_panel.setCurrentIndex(0) 
    # --------------------------------------------------------------------------------------------------------
    
    def load_wind_data(self):
        main_fst = OpenFastIO.current_config.get("MainFST", {}).get("current", "").strip()
        wind_file_name = OpenFastIO.current_config.get("InflowFile", {}).get("current", "")
        if not main_fst or not wind_file_name:
            return copy.deepcopy(self.WIND_KEYS)

        wind_file_path = OpenFastIO.get_absolute_path(main_fst, wind_file_name)
        if not os.path.exists(wind_file_path):
            return copy.deepcopy(self.WIND_KEYS)

        result = copy.deepcopy(self.WIND_KEYS)
        try:
            with open(wind_file_path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    parts = line.strip().split()
                    if len(parts) < 2:
                        continue
                    
                    key = parts[1]
                    if key in result:
                        result[key]["value"] = parts[0].strip('"\'')
        except Exception as e:
            print(f"Error loading wind data: {e}")
        return result

    def refresh_ui_from_file(self):
        key_CompInflow = OpenFastIO.current_config.get("CompInflow", {}).get("current", "")
        if key_CompInflow in ("0", ""):
            # CompInflow가 0이면 UI 업데이트를 건너뜁니다.
            # init_ui에서 이미 메시지를 표시하도록 처리했습니다.
            return

        self.wind_data = self.load_wind_data()

        widgets_to_block = [
            self.chk_echo, self.chk_sumprint, self.combo_wind_type, self.txt_nwindvel,
            self.txt_vzi_list, self.chk_sumprint, self.txt_hwindspeed, self.txt_refht,
            self.txt_plexp, self.txt_filename_uni, self.txt_filename_bts
        ]
        for widget in widgets_to_block:
            widget.blockSignals(True)

        # General
        echo_val = str(self.wind_data["Echo"]["value"]).lower() == "true"
        self.chk_echo.setChecked(echo_val)
        sumprint_val = str(self.wind_data["TimeInterp"]["value"]).lower() == "true"
        self.chk_sumprint.setChecked(sumprint_val)
        wind_type = int(self.wind_data["WindType"]["value"])
        self.combo_wind_type.setCurrentIndex(wind_type - 1)
        self.txt_nwindvel.setText(self.wind_data["NWindVel"]["value"])
        self.txt_vzi_list.setText(self.wind_data["WindVziList"]["value"])
        sumprint_val = str(self.wind_data["SumPrint"]["value"]).lower() == "true"
        self.chk_sumprint.setChecked(sumprint_val)

        # Page specific
        self.txt_hwindspeed.setText(self.wind_data["HWindSpeed"]["value"])
        self.txt_refht.setText(self.wind_data["RefHt"]["value"])
        self.txt_plexp.setText(self.wind_data["PLExp"]["value"])
        self.txt_filename_uni.setText(self.wind_data["FileName_Uni"]["value"])
        self.txt_filename_bts.setText(self.wind_data["FileName_BTS"]["value"])

        # Unblock signals
        for widget in widgets_to_block:
            widget.blockSignals(False)

        self._dirty = False
        self.update_apply_button(active=False)

    def mark_asdirty(self, *args):
        self._dirty = True
        self.update_apply_button(active=True)

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
        main_fst = OpenFastIO.current_config.get("MainFST", {}).get("current", "")
        wind_file_name = OpenFastIO.current_config.get("InflowFile", {}).get("current", "")
        if not main_fst or not wind_file_name:
            QMessageBox.warning(self, "파일 오류", "InflowWind 파일 경로를 찾을 수 없습니다.")
            return False

        wind_file_path = OpenFastIO.get_absolute_path(main_fst, wind_file_name)

        updated_data = {
            "Echo": str(self.chk_echo.isChecked()).lower(),
            "TimeInterp": str(self.chk_sumprint.isChecked()).lower(),
            "WindType": str(self.combo_wind_type.currentIndex() + 1),
            "NWindVel": self.txt_nwindvel.text(),
            "WindVziList": self.txt_vzi_list.text(),
            "SumPrint": str(self.chk_sumprint.isChecked()).lower(),
            "HWindSpeed": self.txt_hwindspeed.text(),
            "RefHt": self.txt_refht.text(),
            "PLExp": self.txt_plexp.text(),
            "FileName_BTS": self.txt_filename_bts.text(),
            "FileName_Uni": self.txt_filename_uni.text(),
        }

        result = OpenFastIO.save_module_data(wind_file_path, updated_data)
        if result:
            self._dirty = False
            self.refresh_ui_from_file()
        return result

    def discard_changes(self):
        self.refresh_ui_from_file()

    def change_summary(self):
        parts = []
        
        def check_and_append(key, current_val, widget_name):
            orig_val = self.wind_data.get(key, {}).get("value", "")
            if str(orig_val).lower() != str(current_val).lower():
                parts.append(f"- {key}: {orig_val} -> {current_val}")

        check_and_append("Echo", self.chk_echo.isChecked(), "chk_echo")
        check_and_append("TimeInterp", self.chk_sumprint.isChecked(), "chk_sumprint")
        check_and_append("WindType", self.combo_wind_type.currentIndex() + 1, "combo_wind_type")
        check_and_append("NWindVel", self.txt_nwindvel.text(), "txt_nwindvel")
        check_and_append("WindVziList", self.txt_vzi_list.text(), "txt_vzi_list")
        check_and_append("SumPrint", self.chk_sumprint.isChecked(), "chk_sumprint")
        check_and_append("HWindSpeed", self.txt_hwindspeed.text(), "txt_hwindspeed")
        check_and_append("RefHt", self.txt_refht.text(), "txt_refht")
        check_and_append("PLExp", self.txt_plexp.text(), "txt_plexp")
        check_and_append("FileName_BTS", self.txt_filename_bts.text(), "txt_filename_bts")
        check_and_append("FileName_Uni", self.txt_filename_uni.text(), "txt_filename_uni")

        return "\n".join(parts) if parts else "변경된 내용이 없습니다."
