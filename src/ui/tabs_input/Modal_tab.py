import os
import copy
import sys
import io
import subprocess 
import json
import shutil

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))


from datetime import datetime
from logging import config

from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QTabWidget, QLabel, QTreeView, QSplitter, QFormLayout  
from PySide6.QtWidgets import QMessageBox, QFileDialog, QWidget, QVBoxLayout, QFormLayout, QCheckBox
from PySide6.QtCore import QPoint, QSettings, Qt, QProcess
from PySide6.QtGui import QStandardItemModel, QStandardItem
from PySide6.QtWidgets import (QTextEdit, QPushButton, QHBoxLayout,QWidget, QVBoxLayout, QFormLayout, 
                               QCheckBox, QComboBox, QLineEdit, QLabel, QPushButton)

from PySide6.QtWidgets import QFileDialog, QInputDialog, QMessageBox, QWidget, QVBoxLayout, QTreeView, QWidget, QVBoxLayout, QFormLayout, QCheckBox, QComboBox
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, 
                               QLabel, QLineEdit, QCheckBox, QComboBox, 
                               QSplitter, QStackedWidget, QPushButton, QFileDialog,QFrame,
                               QTreeView, QAbstractItemView)

from src.core.openfast_io import OpenFastIO  # 코어 엔진 임포트



class ModalTab(QWidget):
    OUTPUT_LIST = {
        "Wind1VelX":   {"value": "1", "desc": "X-direction wind velocity at point WindList(1)"},
        "Wind1VelY":   {"value": "1", "desc": "Y-direction wind velocity at point WindList(1)"},
        "Wind1VelZ":   {"value": "1", "desc": "Z-direction wind velocity at point WindList(1)"}
    }

    def __init__(self, parent=None):
        super().__init__(parent)

        self._dirty = False
        self.init_ui()
        
    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)

#  [상단 영역] 파일 정보 및 저장 버튼 
# ---------------------------------------------------------------------------------------------------
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
        self.btn_discard.clicked.connect(self.on_discard_clicked) # 💡 이 부분도 수정이 필요합니다.
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
        left_layout.setSpacing(5)

        left_layout.addWidget(QLabel("<b style='font-size:13px;'>⚙️ Linearization File Selection</b>"))

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

        # on_tab_enter에서 동적으로 채워집니다.
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
        # [2] 우측 패널: 결과 출력 영역
        # ==========================================
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.addWidget(QLabel("<b style='font-size:13px;'>⚙️ Analysis Result</b>"))
        self.result_display = QTextEdit()
        self.result_display.setReadOnly(True)
        self.result_display.setStyleSheet("font-family: Consolas, 'Courier New', monospace; background-color: #FDFDFD;")
        self.result_display.setPlaceholderText("Click 'Apply' to see the analysis results from eig_A.")
        right_layout.addWidget(self.result_display)
        
        main_splitter.addWidget(right_widget)
        
        # 스플리터 비율 조절 (좌측 4, 우측 6)
        main_splitter.setSizes([400, 600])
        main_layout.addWidget(main_splitter)



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
        fst_file_info = OpenFastIO.current_config.get("MainFST", {})
        main_fst_path = fst_file_info.get("current", "")
        if main_fst_path and os.path.exists(main_fst_path):
            self.lbl_file_path.setText(main_fst_path)
        else:
            self.lbl_file_path.setText("N/A")
        
        self.refresh_ui_from_file()

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
                lines = f.readlines()
                if len(lines) > 1:
                    # InflowWind 파일의 두 번째 줄을 설명으로 간주하여 읽어옵니다.
                    result["Description"]["value"] = lines[1].strip()

                for line in lines: # 모든 라인을 순회하며 다른 키들을 찾습니다.
                    parts = line.strip().split()
                    if len(parts) >= 2:
                        key = parts[1]
                        if key in result and key != "Description": # Description 키는 이미 처리했으므로 건너뜁니다.
                            result[key]["value"] = parts[0].strip('"\'')
        except Exception as e:
            print(f"Error loading wind data: {e}")
        return result

    def refresh_ui_from_file(self):
        key_CompInflow = OpenFastIO.current_config.get("MainFST", {}).get("current", "")
        if key_CompInflow in ("0", ""):
            # CompInflow가 0이면 UI 업데이트를 건너뜁니다.
            # init_ui에서 이미 메시지를 표시하도록 처리했습니다.
            return
        
        self.wind_data = self.load_wind_data()

        widgets_to_block = [
            self.chk_echo, self.chk_sumprint, self.combo_wind_type, self.txt_nwindvel,
            self.txt_vzi_list, self.txt_hwindspeed, self.txt_refht,
            self.txt_plexp, self.txt_filename_uni, self.txt_filename_bts,
            self.txt_refht_uni, self.txt_reflength # 누락된 위젯 추가
        ]
        for widget in widgets_to_block:
            widget.blockSignals(True)

        # General
        self.txt_description.setText(self.wind_data["Description"]["value"]) # Description 필드 값 설정
        echo_val = str(self.wind_data["Echo"]["value"]).lower() == "true"
        self.chk_echo.setChecked(echo_val)        
        sumprint_val = str(self.wind_data["SumPrint"]["value"]).lower() == "true"
        self.chk_sumprint.setChecked(sumprint_val) 
        wind_type = int(3)
        print(f"[DEBUG]    - 파일에서 읽어온 WindType: {wind_type}")
        self.combo_wind_type.setCurrentIndex(wind_type - 1)
        self.txt_nwindvel.setText(self.wind_data["NWindVel"]["value"])
        self.txt_vzi_list.setText(self.wind_data["WindVziList"]["value"])
        sumprint_val = str(self.wind_data["SumPrint"]["value"]).lower() == "true"
        self.chk_sumprint.setChecked(sumprint_val)

        # Page specific
        self.txt_hwindspeed.setText(self.wind_data["HWindSpeed"]["value"])
        self.txt_refht.setText(self.wind_data["RefHt"]["value"])
        self.txt_refht_uni.setText(self.wind_data["RefHt_Uni"]["value"]) # Uniform Wind 페이지 값 설정 추가
        self.txt_reflength.setText(self.wind_data["RefLength"]["value"]) # Uniform Wind 페이지 값 설정 추가
        self.txt_plexp.setText(self.wind_data["PLExp"]["value"])

        # InflowWind 파일의 절대 경로를 기준으로 다른 파일들의 경로를 계산합니다.
        main_fst_path = OpenFastIO.current_config.get("MainFST", {}).get("current", "")
        inflow_file_name = OpenFastIO.current_config.get("InflowFile", {}).get("current", "")
        inflow_file_path = OpenFastIO.get_absolute_path(main_fst_path, inflow_file_name)

        self.txt_filename_uni.setText(OpenFastIO.get_absolute_path(inflow_file_path, self.wind_data["FileName_Uni"]["value"]))
        self.txt_filename_bts.setText(OpenFastIO.get_absolute_path(inflow_file_path, self.wind_data["FileName_BTS"]["value"]))
        print(f"FileName_BTS = {self.wind_data["FileName_BTS"]["value"]}")

        # Unblock signals
        for widget in widgets_to_block:
            widget.blockSignals(False)
            
        # 💡 [수정] UI 값 설정이 모두 끝난 후, 현재 WindType에 맞는 페이지를 명시적으로 표시
        self.on_wind_type_changed(self.combo_wind_type.currentIndex())

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

    def refresh_ui_from_file(self):
        """ .fst 파일과 동일한 이름의 .lin 파일을 찾아 Available 리스트를 업데이트합니다. """
        self.output0_model.clear()
        self.output1_model.clear() # Selected 리스트도 함께 초기화
        main_fst_path = OpenFastIO.current_config.get("MainFST", {}).get("current", "")
        if not main_fst_path or not os.path.exists(main_fst_path):
            item = QStandardItem("🚫 .fst 파일이 선택되지 않았습니다.")
            item.setEnabled(False)
            self.output0_model.appendRow(item)
            return

        fst_dir = os.path.dirname(main_fst_path)
        fst_basename, _ = os.path.splitext(os.path.basename(main_fst_path))

        lin_files = []
        try:
            for f in os.listdir(fst_dir):
                if f.lower().startswith(fst_basename.lower()) and f.lower().endswith('.lin'):
                    lin_files.append(f)
        except OSError as e:
            print(f"Error reading directory {fst_dir}: {e}")

        if not lin_files:
            item = QStandardItem("🚫 관련된 .lin 파일이 없습니다.")
            item.setEnabled(False)
            self.output0_model.appendRow(item)
        else:
            for lin_file in sorted(lin_files):
                item = QStandardItem(lin_file)
                item.setEditable(False)
                self.output0_model.appendRow(item)
        
        self._dirty = False
        self.update_apply_button(active=False)

    def on_apply_clicked__(self):
        """ Apply 버튼 클릭 시 파일 저장 """
        if self.isdirty():
            if self.apply_values_to_file():
                self.update_apply_button(active=False)

    def on_apply_clicked(self):
        """ Apply 버튼 클릭 시 선택된 .lin 파일에 대해 eig_A 함수를 실행하고 결과를 UI에 표시합니다. """
        main_fst_path = OpenFastIO.current_config.get("MainFST", {}).get("current", "")
        if not main_fst_path or not os.path.exists(main_fst_path):
            QMessageBox.warning(self, "파일 오류", ".fst 파일이 선택되지 않았습니다.")
            return

        fst_dir = os.path.dirname(main_fst_path)
        item_count = self.output1_model.rowCount()

        if item_count == 0:
            QMessageBox.information(self, "선택된 파일이 없습니다.")
            return

        self.result_display.clear()
        QApplication.processEvents() # UI 갱신

        for i in range(item_count):
            item = self.output1_model.item(i)
            lin_file_name = item.text()
            lin_file_path = os.path.join(fst_dir, lin_file_name)

            if os.path.exists(lin_file_path):
                sys.stdout = captured_output = io.StringIO()

                try:
                    current_dir    = os.path.dirname(os.path.abspath(__file__)) # tabs_input
                    project_root   = os.path.dirname(os.path.dirname(os.path.dirname(current_dir))) # OFA
                    test_file_path = os.path.join(project_root, "src", "core", "test.py")

                    print(f"code_to_run ={test_file_path}")
                    
                    with open(test_file_path, "r", encoding="utf-8") as f:
                        code_to_run = f.read()

                    custom_globals = {"file_path": lin_file_path}
                    exec(code_to_run, custom_globals)

                    # 캡처된 출력을 UI에 추가
                    self.result_display.append(captured_output.getvalue())
                    self.result_display.append("\n" + "="*80 + "\n")

                except Exception as e:
                    print(f"실시간 코드 실행 중 에러 발생: {e}")

            else:
                QMessageBox.warning(self, "파일 없음", f"파일을 찾을 수 없습니다: {lin_file_path}")

    


    def on_discard_clicked(self):
        """ Discard 버튼 클릭 시 변경사항 취소 """
        self.discard_changes()

    def discard_changes(self):
        self.refresh_ui_from_file()
        self.update_apply_button(active=False)

    def change_summary(self):
        parts = []
        return "\n".join(parts) if parts else "변경된 내용이 없습니다."
