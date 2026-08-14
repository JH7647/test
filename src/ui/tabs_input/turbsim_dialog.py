import os
import subprocess
import tempfile
import sys
import shutil
import re
from datetime import datetime
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QLineEdit, 
                               QPushButton, QFileDialog, QMessageBox, QLabel, QHBoxLayout,
                               QDialogButtonBox, QInputDialog)
from PySide6.QtWidgets import (QSplitter, QWidget, QScrollArea, QFrame, QCheckBox, 
                               QComboBox, QTreeView, QAbstractItemView, QTreeWidget, QTreeWidgetItem)
from PySide6.QtCore import QSettings, Qt, QProcess
from PySide6.QtGui import QStandardItemModel, QStandardItem, QBrush, QColor, QTextCursor

from src.core.openfast_io import OpenFastIO
from PySide6.QtWidgets import QMenu
from PySide6.QtGui import QAction, QGuiApplication

# === 상태 상수 ===
PROCESS_TREE_STATUS_PENDING = 0
PROCESS_TREE_STATUS_RUNNING = 1
PROCESS_TREE_STATUS_COMPLETED = 2
PROCESS_TREE_STATUS_STOP = 3
PROCESS_TREE_STATUS_ERROR = 4


class TurbSimDialog(QDialog):
    """ TurbSim .inp 파일을 생성하고 turbsim.exe를 실행하여 .bts 파일을 생성하는 다이얼로그 """

    INP_PARAMS = {
        "RandSeed1":    {"widget": None, "value":"1", "original_value": "1"},
        "NumGrid_Z":    {"widget": None, "value": "63", "original_value": "63"},
        "NumGrid_X":    {"widget": None, "value": "63", "original_value": "63"},
        "NumGrid_Y":    {"widget": None, "value": "63", "original_value": "63"},
        "NumGrid_T":    {"widget": None, "value": "63", "original_value": "63"},
        "TimeStep":     {"widget": None, "value": "0.05", "original_value": "0.05"},
        "AnalysisTime": {"widget": None, "value":"660.0", "original_value": "660.0"},
        "UsableTime":   {"widget": None, "value": "600.0", "original_value": "600.0"},
        "HubHt":        {"widget": None, "value":"90.0", "original_value": "90.0"},
        "GridHeight":   {"widget": None, "value":"125.88", "original_value": "125.88"},
        "GridWidth":    {"widget": None, "value":"125.88", "original_value": "125.88"},
        "URef":         {"widget": None, "value":"11.737", "original_value": "11.737"},
        "IECturbc":     {"widget": None, "value":"1", "original_value": "1"},
        "IEC_WindType": {"widget": None, "value":"NTM", "original_value": "NTM"},
    }

    def __init__(self, parent=None, output_filename_widget=None, inflow_file_path=None):
        super().__init__(parent, Qt.Window)
        self.output_filename_widget = output_filename_widget
        self.turbsim_exe_path = ""
        self.inflow_file_path = inflow_file_path
        self._dirty = False

        self.process_logs = {}
        # 프로세스 실행 큐 및 관리
        self.process_tree_run_queue = {
            "pending": [],
            "running": [],
            "completed": [],
        }
        self.process_tree_max_concurrent = 3
        self.process_tree_process_map = {}

        self.setWindowTitle("TurbSim .bts File Generator")
        self.setModal(False)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.resize(1000, 600)

        self.init_ui()
        self.find_turbsim_exe()
        self.find_turbsim_inp()
        self.find_turbsim_dir()
        

    def init_ui(self):

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 10, 10)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: #C1C5CB;
            }
            QSplitter::handle:horizontal {
                width: 2px;
                margin: 5px;
            }
        """)
        main_layout.addWidget(splitter)

# region : [LEFT SIDE] Description, Toggles, Module Switches 
# ====================================================================================================
        left_widget = QWidget()
        left_layout = QFormLayout(left_widget)
        left_layout.setContentsMargins(10, 0, 10, 0)
        left_layout.setSpacing(10)

        general_lbl = QLabel("<b style='font-size:13px;'>⚙️ General settings</b>") 
        left_layout.addRow(general_lbl)

        turbsim_layout = QHBoxLayout()
        self.txt_turbsim_path = QLabel()
        self.txt_turbsim_path.setStyleSheet("background-color: white;")
        self.txt_turbsim_path.mouseDoubleClickEvent = lambda event: self.browse_for_turbsim_exe()
        turbsim_layout.addWidget(self.txt_turbsim_path)
        left_layout.addRow("📍 Turbsim .exe path:", turbsim_layout)

        dir_layout = QHBoxLayout()
        self.txt_dir_path = QLabel()
        self.txt_dir_path.setStyleSheet("background-color: white;")
        self.txt_dir_path.mouseDoubleClickEvent = lambda event: self.browse_for_dir()
        dir_layout.addWidget(self.txt_dir_path)
        left_layout.addRow("📍 Working direcotry path :", dir_layout)

        lbl_layout = QHBoxLayout()
        available_lbl = QLabel("📍 Available .inp file List")
        selected_lbl  = QLabel("  Selected & Running List")
        lbl_layout.addWidget(available_lbl)
        lbl_layout.addSpacing(50) # 중간 버튼 영역 크기만큼 이격
        lbl_layout.addWidget(selected_lbl)
        left_layout.addRow(lbl_layout)
        
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
        self.output0_tree.selectionModel().selectionChanged.connect(self.on_inp_file_selected)
        self.output0_tree.doubleClicked.connect(self.open_inp_file_in_editor)
        self.output0_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.output0_tree.customContextMenuRequested.connect(self.show_output0_tree_context_menu)
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
        self.output1_tree = QTreeWidget()
        self.output1_tree.setHeaderLabels(["File", "Status", "Start", "Finish"])
        self.output1_tree.setColumnWidth(0, 200)
        self.output1_tree.setColumnWidth(1, 80)
        self.output1_tree.setColumnWidth(2, 80)
        self.output1_tree.setSelectionMode(QAbstractItemView.ExtendedSelection)
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
        left_layout.addRow(output_selector_layout)
        splitter.addWidget(left_widget)
        # -----------------------------------------------------------------------------------------------
# endregion
# ====================================================================================================

# region : [RIGHT SIDE] Description, Toggles, Module Switches 
# ====================================================================================================
        right_widget = QWidget()
        right_layout = QFormLayout(right_widget)
        right_layout.setContentsMargins(10, 0, 10, 0)
        right_layout.setSpacing(10)

        right_layout.addRow(QLabel("<b style='font-size:13px;'>⚙️ TurbSim Params from Left File </b>"))
        
        inp_layout = QHBoxLayout()
        self.txt_inp_path = QLineEdit()
        self.txt_inp_path.setStyleSheet("background-color: white;")
        self.txt_inp_path.setReadOnly(True)
        btn_browse_inp = QPushButton("📂")
        btn_browse_inp.clicked.connect(self.browse_for_inp) 
        btn_browse_inp.setFixedWidth(35)
        inp_layout.addWidget(self.txt_inp_path)
        inp_layout.addWidget(btn_browse_inp)
        right_layout.addRow("📝 .inp Reference file :", inp_layout)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_content = QWidget()
        form_layout = QFormLayout(scroll_content)
        form_layout.setSpacing(10)

        for key, info in self.INP_PARAMS.items():
            edit = QLineEdit(info["value"])
            edit.textChanged.connect(self.mark_as_dirty)

            if key == "RandSeed1":
                label = QLabel(f"📍 {key}:")
                label.mouseDoubleClickEvent = self.open_randseed_file_dialog
                form_layout.addRow(label, edit)
            else:
                form_layout.addRow(f"📍 {key}:", edit)
            info["widget"] = edit

        scroll_area.setWidget(scroll_content)
        right_layout.addRow(scroll_area)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(5)
        btn_layout.addStretch()

        self.btn_generate_inp = QPushButton("📂 Generate .inp file")
        self.btn_generate_inp.clicked.connect(self.generate_inp_file)
        btn_layout.addWidget(self.btn_generate_inp)

        self.btn_discard_change = QPushButton("↩️ Discard changes")
        self.btn_discard_change.clicked.connect(self.discard_change)
        btn_layout.addWidget(self.btn_discard_change)

        right_layout.addRow(btn_layout)

        splitter.addWidget(right_widget)
        splitter.setSizes([600, 400])
# endregion
# ====================================================================================================
        self.update_buttons_state(False)


    @staticmethod
    def show_window(parent, output_filename_widget, inflow_file_path):
        """ TurbSimDialog를 모달리스로 띄웁니다. 중복 생성을 방지합니다. """

        # # 이미 열려있는 창이 있는지 확인하고, 있다면 새로 띄우지 않고 활성화합니다.
        # for widget in parent.findChildren(QDialog):
        #     if isinstance(widget, TurbSimDialog) and widget.isVisible():
        #         widget.activateWindow()
        #         widget.raise_()
        #         return

        dialog = TurbSimDialog(parent, output_filename_widget=output_filename_widget, inflow_file_path=inflow_file_path)
        dialog.show()

    def mark_as_dirty(self):
        """ Mark changes and activate buttons """
        self._dirty = True
        self.update_buttons_state(True)

    def update_buttons_state(self, is_dirty):
        """ Enable or disable generate and discard buttons """
        self.btn_generate_inp.setEnabled(is_dirty)
        self.btn_discard_change.setEnabled(is_dirty)


    def find_turbsim_exe(self):
        """ 설정 또는 일반적인 경로에서 turbsim.exe를 찾습니다. """
        settings = QSettings("JHLEE", "OFA")
        path = settings.value("TurbSimExePath", "")

        if path and os.path.exists(path):
            self.turbsim_exe_path = path
        else:
            # 일반적인 경로 탐색
            common_paths = [
                r"C:\TurbSim\TurbSim.exe",
                r"C:\Program Files\TurbSim\TurbSim.exe",
                r"C:\Users\jeong\Downloads\BU_openFAST\TurbSim.exe",
                os.path.join(os.path.dirname(sys.executable), "TurbSim.exe")
            ]
            for p in common_paths:
                if os.path.exists(p):
                    self.turbsim_exe_path = p
                    break
        
        if self.turbsim_exe_path:
            self.txt_turbsim_path.setText(self.turbsim_exe_path)
            settings.setValue("TurbSimExePath", self.turbsim_exe_path)
        else:
            self.txt_turbsim_path.setText("TurbSim.exe not found. Please specify the path.")

    def browse_for_turbsim_exe(self):
        """ TurbSim.exe 파일을 찾기 위한 파일 다이얼로그를 엽니다. """
        path, _ = QFileDialog.getOpenFileName(self, "Find TurbSim.exe", "", "Executable (*.exe)")
        if path:
            self.turbsim_exe_path = path
            self.txt_turbsim_path.setText(self.turbsim_exe_path)
            settings = QSettings("JHLEE", "OFA")
            settings.setValue("TurbSimExePath", self.turbsim_exe_path)

    def find_turbsim_dir(self):
        """ working dir. """
        if self.output_filename_widget:
            bts_path = self.output_filename_widget.text()
            print(bts_path)

            if bts_path and os.path.exists(os.path.dirname(bts_path)):
                inp_dir = os.path.dirname(bts_path)
                self.txt_dir_path.setText(inp_dir)
                self.load_inp_files_to_tree(inp_dir)
                return

    def browse_for_dir(self):
        """ TurbSim .inp 파일을 저장할 디렉토리를 선택하는 다이얼로그를 엽니다. """
        current_dir = self.txt_dir_path.text()
        if not current_dir or not os.path.isdir(current_dir):
            current_dir = os.path.dirname(self.inflow_file_path) if self.inflow_file_path else ""

        selected_dir = QFileDialog.getExistingDirectory(self, "Select .inp Directory", current_dir)
        if selected_dir:
            self.txt_dir_path.setText(selected_dir)
            self.load_inp_files_to_tree(selected_dir)

    def find_turbsim_inp(self):
        """ input reference file. """
        if self.output_filename_widget:
            bts_path = self.output_filename_widget.text()
            if bts_path:
                base_name, _ = os.path.splitext(bts_path)
                self.txt_inp_path.setText(f"{base_name}.inp")
            return

    def browse_for_inp(self):
        """ input reference file. 선택하는 다이얼로그를 엽니다. """
        current_path = self.txt_inp_path.text()
        start_dir = os.path.dirname(current_path) if current_path and os.path.exists(os.path.dirname(current_path)) else self.txt_dir_path.text()

        file_path, _ = QFileDialog.getOpenFileName(self, "Select .inp Reference File", start_dir, "TurbSim Input Files (*.inp);;All Files (*)")
        if file_path:
            self.txt_inp_path.setText(file_path)
            self.load_inp_files_to_editbox(file_path)

    def on_inp_file_selected(self, selected, deselected):
        """ 왼쪽 트리에서 .inp 파일을 선택했을 때 load_inp_files_to_editbox 를 호출합니다. """
        indexes = selected.indexes()
        if not indexes:
            return
        
        item = self.output0_model.itemFromIndex(indexes[0])
        if not item:
            return

        dir_path = self.txt_dir_path.text()
        file_path = os.path.join(dir_path, item.text())
        
        if os.path.exists(file_path):
            self.txt_inp_path.setText(file_path) # 선택된 파일 경로를 txt_inp_path에 출력
            self.load_inp_files_to_editbox(file_path)

    def show_output0_tree_context_menu(self, pos):
        """ output0_tree에서 우클릭 시 컨텍스트 메뉴를 표시합니다. """
        selected_indexes = self.output0_tree.selectionModel().selectedRows()
        if not selected_indexes:
            return

        menu = QMenu(self)
        delete_action = menu.addAction("🗑️ Delete selected file(s)")
        action = menu.exec(self.output0_tree.mapToGlobal(pos))

        if action == delete_action:
            self.delete_selected_inp_files()

    def delete_selected_inp_files(self):
        """ 선택된 .inp 파일들을 디스크에서 삭제합니다. """
        selected_indexes = self.output0_tree.selectionModel().selectedRows()
        if not selected_indexes:
            return

        files_to_delete = []
        for index in selected_indexes:
            item = self.output0_model.itemFromIndex(index)
            file_path = os.path.join(self.txt_dir_path.text(), item.text())
            if os.path.exists(file_path):
                files_to_delete.append(file_path)

        if not files_to_delete:
            return

        reply = QMessageBox.question(self, "파일 삭제 확인", f"{len(files_to_delete)}개의 파일을 정말로 삭제하시겠습니까?\n이 작업은 되돌릴 수 없습니다.", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            for file_path in files_to_delete:
                os.remove(file_path)
            self.load_inp_files_to_tree(self.txt_dir_path.text())

    def load_inp_files_to_editbox(self, file_path):
        """ Specified .inp file -> edit box """
        try:
            with open(file_path, 'r') as f:
                for line in f:
                    parts = line.strip().split()
                    key = parts[1] if len(parts) > 1 else None
                    if key in self.INP_PARAMS:
                        value = parts[0]
                        self.INP_PARAMS[key]["widget"].setText(value)
                        self.INP_PARAMS[key]["original_value"] = value # Store original value
            self.update_buttons_state(False) 

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load .inp file:\n{e}")

    def open_randseed_file_dialog(self, event):
        """RandSeed1 라벨을 더블클릭하면 파일 선택창을 열고, 선택된 파일명을 에딧박스에 설정합니다."""
        if event.button() == Qt.LeftButton:
            work_dir = self.txt_dir_path.text()
            if not work_dir or not os.path.isdir(work_dir):
                QMessageBox.warning(self, "경고", "워킹 디렉토리가 설정되지 않았습니다.")
                return

            file_path, _ = QFileDialog.getOpenFileName(self, "Select File for RandSeed1", work_dir, "All Files (*)")

            if file_path:
                file_name = os.path.basename(file_path)
                self.INP_PARAMS["RandSeed1"]["widget"].setText(file_name)

    def load_inp_files_to_tree(self, directory_path):
        """ 지정된 디렉토리에서 .inp 파일을 찾아 output0_tree에 로드합니다. """
        self.output0_model.clear()
        print(f"Loading files from: {directory_path}")
              
        if not directory_path or not os.path.isdir(directory_path):
            item = QStandardItem("🚫 Invalid directory.")
            item.setEditable(False)
            item.setEnabled(False)
            self.output0_model.appendRow(item)
            return

        try:
            inp_files = [f for f in os.listdir(directory_path) if f.lower().endswith('.inp')]
            if not inp_files:
                item = QStandardItem("🚫 No .inp files found.")
                item.setEditable(False)
                item.setEnabled(False)
                self.output0_model.appendRow(item)
                return

            for file_name in sorted(inp_files):
                item = QStandardItem(file_name)
                item.setEditable(False)
                self.output0_model.appendRow(item)

        except Exception as e:
            error_item = QStandardItem(f"❌ Error loading files: {e}")
            error_item.setEditable(False)
            error_item.setEnabled(False)
            self.output0_model.appendRow(error_item)

    def open_inp_file_in_editor(self, index):
        """ 왼쪽 트리에서 .inp 파일을 더블 클릭했을 때 Notepad++로 엽니다. """
        if not index.isValid():
            return

        item = self.output0_model.itemFromIndex(index)
        if not item:
            return

        dir_path = self.txt_dir_path.text()
        file_path = os.path.join(dir_path, item.text())

        if not os.path.exists(file_path):
            QMessageBox.warning(self, "파일 오류", "파일을 찾을 수 없습니다.")
            return

        npp_path = r"C:\Program Files\Notepad++\notepad++.exe"
        editor_path = npp_path if os.path.exists(npp_path) else "notepad.exe"
        subprocess.Popen([editor_path, file_path])

    def mark_as_dirty(self):
        """ Mark changes and activate buttons """
        self._dirty = True
        self.update_buttons_state(True)


    def generate_inp_file(self):
        """ Generate a new .inp file based on the reference and current UI values """
        randseed_text = self.INP_PARAMS["RandSeed1"]["widget"].text()
        work_dir = self.txt_dir_path.text()

        # Check if RandSeed1 is a file path for batch creation
        seed_file_path = os.path.join(work_dir, randseed_text)
        if os.path.isfile(seed_file_path):
            self.generate_batch_inp_files(seed_file_path)
        else:
            self.generate_single_inp_file()

    def generate_single_inp_file(self):
        """ Creates a single .inp file with a user-prompted name. """
        ref_path = self.txt_inp_path.text()
        work_dir = self.txt_dir_path.text()

        if not (os.path.exists(ref_path) and os.path.isdir(work_dir)):
            QMessageBox.warning(self, "Error", "Reference file or working directory is not valid.")
            return

        base_name = os.path.splitext(os.path.basename(ref_path))[0]
        new_name, ok = QInputDialog.getText(self, "New .inp File", "Enter a new name for the .inp file:", text=f"{base_name}_new.inp")

        if ok and new_name:
            new_path = os.path.join(work_dir, new_name)
            self._create_and_update_inp(ref_path, new_path)
            self.load_inp_files_to_tree(work_dir)
            self.update_buttons_state(False)

    def generate_batch_inp_files(self, seed_file_path):
        """ Creates multiple .inp files based on a seed file. """
        ref_path = self.txt_inp_path.text()
        work_dir = self.txt_dir_path.text()

        if not (os.path.exists(ref_path) and os.path.isdir(work_dir)):
            QMessageBox.warning(self, "Error", "Reference file or working directory is not valid.")
            return

        try:
            with open(seed_file_path, 'r') as f:
                lines = [line.strip() for line in f if line.strip()]
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to read seed file: {e}")
            return

        if not lines:
            QMessageBox.information(self, "Info", "Seed file is empty. No files will be created.")
            return

        reply = QMessageBox.question(self, "Confirm Batch Creation", f"This will create {len(lines)} new .inp files. Continue?",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.Yes:
            for line in lines:
                parts = line.split()
                if len(parts) < 2:
                    continue
                
                new_randseed = parts[0]
                new_filename_base = parts[1]
                new_path = os.path.join(work_dir, f"{new_filename_base}.inp")

                self._create_and_update_inp(ref_path, new_path, override_randseed=new_randseed)

            self.load_inp_files_to_tree(work_dir)
            self.update_buttons_state(False)

    def _create_and_update_inp(self, ref_path, new_path, override_randseed=None):
        """ Helper to copy and update a single .inp file. """
        try:
            shutil.copy(ref_path, new_path)
            updated_data = {}
            for key, info in self.INP_PARAMS.items():
                updated_data[key] = info["widget"].text()
            
            if override_randseed:
                updated_data["RandSeed1"] = override_randseed

            with open(new_path, 'r') as f:
                lines = f.readlines()
            with open(new_path, 'w') as f:
                for line in lines:
                    parts = line.strip().split()
                    key = parts[1] if len(parts) > 1 else None
                    if key in updated_data:
                        f.write(f"{updated_data[key]:<12}    {key}{line.split(key, 1)[1]}")
                    else:
                        f.write(line)
        except Exception as e:
            QMessageBox.critical(self, "File Creation Error", f"Failed to create or update {os.path.basename(new_path)}:\n{e}")

    def discard_change(self):
        """ Revert changes in the edit form to original values """
        for key, info in self.INP_PARAMS.items():
            info["widget"].setText(info["original_value"])
        self.update_buttons_state(False)


    def move_items_to_selected(self):
        """ 왼쪽(Available)에서 오른쪽(Selected)으로 아이템 이동 """
        selected_indexes = self.output0_tree.selectionModel().selectedRows()
        if not selected_indexes:
            return

        dir_path = self.txt_dir_path.text()
        for index in selected_indexes:
            item = self.output0_model.itemFromIndex(index)
            file_path = os.path.join(dir_path, item.text())
            
            # 중복 추가 방지
            if not self.process_tree_find_item_by_path(file_path):
                self.process_tree_add_to_pending(file_path)

    def move_items_to_available(self):
        """ 오른쪽(Selected)에서 왼쪽(Available)으로 아이템 이동 """
        selected_items = self.output1_tree.selectedItems()
        if not selected_items:
            return

        for item in selected_items:
            file_path = item.data(0, Qt.UserRole)
            status = item.data(1, Qt.UserRole)

            if status == PROCESS_TREE_STATUS_PENDING:
                if file_path in self.process_tree_run_queue["pending"]:
                    self.process_tree_run_queue["pending"].remove(file_path)
                root = self.output1_tree.invisibleRootItem()
                root.removeChild(item)

            elif status == PROCESS_TREE_STATUS_RUNNING:
                reply = QMessageBox.question(self, "실행 중단", f"프로세스가 실행 중입니다. 중단하시겠습니까?\n{os.path.basename(file_path)}", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                if reply == QMessageBox.Yes:
                    proc = self.process_tree_process_map.get(file_path)
                    if proc:
                        proc.kill() # 강제 종료
                        # finished 시그널이 자동으로 처리해줌

            else: # Completed, Error, Stopped
                root = self.output1_tree.invisibleRootItem()
                root.removeChild(item)

    def process_tree_add_to_pending(self, file_path):
        """런예정 리스트에 항목 추가 → 즉시 실행 가능 여부 확인"""
        item = QTreeWidgetItem([os.path.basename(file_path), "Pending", "", ""])
        item.setData(0, Qt.UserRole, file_path)
        item.setData(1, Qt.UserRole, PROCESS_TREE_STATUS_PENDING)
        self.process_tree_apply_status_style(item, PROCESS_TREE_STATUS_PENDING)
        
        self.output1_tree.addTopLevelItem(item)
        self.process_tree_run_queue["pending"].append(file_path)
        
        self.process_tree_try_start_next()

    def process_tree_try_start_next(self):
        """running process 개수 확인 → 설정 이하이면 런예정에서 실행 시작"""
        running_count = len(self.process_tree_run_queue["running"])
        
        while running_count < self.process_tree_max_concurrent:
            if not self.process_tree_run_queue["pending"]:
                break
            
            file_path = self.process_tree_run_queue["pending"].pop(0)
            
            item = self.process_tree_find_item_by_path(file_path)
            if item:
                self.process_tree_move_to_running(item, file_path)
                running_count += 1

    def process_tree_move_to_running(self, item, file_path):
        """런예정 → 런중으로 이동 및 TurbSim 실행"""
        start_time = datetime.now().strftime("%H:%M:%S")
        item.setText(2, start_time)
        item.setData(1, Qt.UserRole, PROCESS_TREE_STATUS_RUNNING)
        self.process_tree_apply_status_style(item, PROCESS_TREE_STATUS_RUNNING)
        
        self.process_tree_run_queue["running"].append(file_path)
        
        self.process_tree_execute_turbsim(item, file_path)

    def process_tree_execute_turbsim(self, item, file_path):
        """TurbSim 프로세스 실행 및 완료 콜백 설정"""
        proc = QProcess(self)
        self.process_tree_process_map[file_path] = proc

        if not self.turbsim_exe_path or not os.path.exists(self.turbsim_exe_path):
            QMessageBox.critical(self, "TurbSim.exe 없음", "TurbSim.exe 실행 파일을 찾을 수 없습니다.")
            self.process_tree_handle_process_finished(item, file_path, 1) # 1 for error
            return
        
        try:
            proc.setProgram(self.turbsim_exe_path)
            proc.setArguments([file_path])
            proc.setWorkingDirectory(os.path.dirname(file_path))
            
            proc.readyReadStandardOutput.connect(lambda: self.process_tree_stream_output(proc, file_path))
            proc.finished.connect(lambda exit_code, exit_status, it=item, fp=file_path: self.process_tree_handle_process_finished(it, fp, exit_code))
            
            proc.start()
            print(f"🚀 TurbSim 프로세스 시작: {file_path}")
            
        except Exception as e:
            QMessageBox.critical(self, "실행 오류", f"TurbSim 실행 실패:\n{str(e)}")
            self.process_tree_handle_process_finished(item, file_path, 1)

    def process_tree_stream_output(self, proc, file_path):
        """TurbSim 로그 스트리밍 + 진행률 파싱"""
        try:
            data = proc.readAllStandardOutput().data().decode('utf-8', errors='ignore')
            if data:
                if file_path not in self.process_logs:
                    self.process_logs[file_path] = ""
                self.process_logs[file_path] += data

                match = re.search(r"Time:\s*([\d.]+)\s*of\s*([\d.]+)\s*seconds", data)
                if match:
                    current_sec = float(match.group(1))
                    total_sec = float(match.group(2))
                    
                    item = self.process_tree_find_item_by_path(file_path)
                    if item and total_sec > 0:
                        progress_pct = int((current_sec / total_sec) * 100)
                        if item.data(1, Qt.UserRole) == PROCESS_TREE_STATUS_RUNNING:
                            item.setText(3, f"{progress_pct}%")
                # cmd_output가 정의되어 있는지 확인
                if hasattr(self, 'cmd_output') and getattr(self, 'current_viewing_path', '') == file_path:
                    self.cmd_output.append(data)
                    self.cmd_output.moveCursor(QTextCursor.End)
        except Exception as e:
            print(f"❌ 로그 스트리밍 중 예외 발생: {e}")

    def process_tree_handle_process_finished(self, item, file_path, exit_code):
        """TurbSim 실행 완료 콜백"""
        if file_path in self.process_tree_run_queue["running"]:
            self.process_tree_run_queue["running"].remove(file_path)

        if file_path in self.process_tree_process_map:
            del self.process_tree_process_map[file_path]

        current_item = self.process_tree_find_item_by_path(file_path)
        if current_item:
            success = (exit_code == 0)
            status = PROCESS_TREE_STATUS_COMPLETED if success else PROCESS_TREE_STATUS_ERROR
            self.process_tree_move_to_completed(current_item, file_path, status, is_error=not success)
        
        self.process_tree_try_start_next()

    def process_tree_move_to_completed(self, item, file_path, status, is_error=False):
        """running → completed 이동 """
        end_time = datetime.now().strftime("%H:%M:%S")
        item.setText(3, end_time)
        item.setData(1, Qt.UserRole, status) 
        self.process_tree_apply_status_style(item, status) 
        
        self.process_tree_run_queue["completed"].append({
            "path": file_path,
            "success": not is_error,
            "end_time": end_time
        })

    def process_tree_apply_status_style(self, item, status):
        """상태별 배경색 및 글자색 적용"""
        colors = {
            PROCESS_TREE_STATUS_PENDING:   {"bg": "#FFFFFF", "fg": "#000000", "text": "Pending"},
            PROCESS_TREE_STATUS_RUNNING:   {"bg": "#DCFCE7", "fg": "#15803D", "text": "Running"},
            PROCESS_TREE_STATUS_COMPLETED: {"bg": "#F3F4F6", "fg": "#4B5563", "text": "Completed"},
            PROCESS_TREE_STATUS_STOP:      {"bg": "#FEF2F2", "fg": "#991B1B", "text": "Stopped"},
            PROCESS_TREE_STATUS_ERROR:     {"bg": "#FEE2E2", "fg": "#EF4444", "text": "Error"},
        }
        
        style = colors.get(status)
        if not style: return
        
        for col in range(item.columnCount()):
            item.setBackground(col, QBrush(QColor(style["bg"])))
            item.setForeground(col, QBrush(QColor(style["fg"])))
        
        item.setText(1, style["text"])

    def process_tree_find_item_by_path(self, file_path):
        """파일 경로로 QTreeWidget에서 아이템 찾기"""
        for i in range(self.output1_tree.topLevelItemCount()):
            item = self.output1_tree.topLevelItem(i)
            if item and item.data(0, Qt.UserRole) == file_path:
                return item
        return None
  