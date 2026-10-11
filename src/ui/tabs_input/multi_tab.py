""" 다중 케이스 실행 설정 모달리스 창 (MultiCaseRunWindow) """
import os
import tempfile
import shutil
import json
import openpyxl
import platform
import subprocess

from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QInputDialog,
    QComboBox, QTableWidget, QTableWidgetItem, QAbstractItemView, QFrame,
    QFileDialog, QMessageBox, QToolBar, QToolButton,
    QApplication, QMainWindow, QSizePolicy, QHeaderView    
)
from PySide6.QtGui import (
    QBrush, QColor, QFont, QGuiApplication,
    QShortcut, QKeySequence
    # 💡 에러가 나던 QMimeData를 여기서 삭제했습니다.
)
from PySide6.QtCore import Qt, QCoreApplication, QMimeData




class MultiCaseRunWindow(QDialog):
    """ 모달리스 다중 케이스 실행 설정 창 (Streamlit 스타일 UI) """
    
    parameter_map = {
        "WaveHs"        : { "Target_File": ".sea", "File_Symbol": "Hs", "Description": "Hs" },
        "WaveTp"        : { "Target_File": ".sea", "File_Symbol": "Tp", "Description": "Tp" },
        "PropagationDir": { "Target_File": ".inf", "File_Symbol": "WD", "Description": "Wind Direction" },
        "WaveDir"       : { "Target_File": ".sea", "File_Symbol": "AD", "Description": "Wave Direction" },
        "CurrSSDir"     : { "Target_File": ".sea", "File_Symbol": "CD", "Description": "Current Direction" },
        "NacYaw"        : { "Target_File": ".ela", "File_Symbol": "YE", "Description": "Yaw Error" },
        "FileName_BTS"  : { "Target_File": ".inf", "File_Symbol": "WS", "Description": "Wind Seed" },
        "WaveSeed(1)"   : { "Target_File": ".sea", "File_Symbol": "AS", "Description": "Wave Seed" },
    }

    CHECKED_BG = "#D1FAE5"
   

    def __init__(self, parent, file_path, ref_name, excel_path):
        super().__init__(parent, Qt.Window)
        self.file_path = file_path
        self.ref_name = ref_name
        self.excel_path = excel_path
        self.excel_path_local = excel_path
        self.excel_read = [""]
        self.current_wb = None
        self.current_ws = None
        self.apply_all_policy = None
        self._clipboard = None
        self._hidden_rows = set()
        self._hidden_cols = set()
        # Undo/redo 히스토리
        self._history = []
        self._history_index = -1
        self._max_history = 50

        self.setWindowTitle("다중 케이스 실행 설정")
        self.resize(1100, 650)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        lbl_ref = QLabel("참조파일: " + file_path)
        lbl_ref.setToolTip(file_path)
        lbl_ref.setWordWrap(True)
        lbl_ref.setStyleSheet("font-weight: bold; color: #1F2937; font-size: 14px;")
        layout.addWidget(lbl_ref)

        xls_layout = QHBoxLayout()
        self.lbl_xls = QLabel()  
        self.lbl_xls.setWordWrap(False)
        self.lbl_xls.setToolTip(excel_path)
        self.lbl_xls.setText(f'<a href="{excel_path}" style="color: #1F2937; text-decoration: underline;">엑셀파일: {excel_path}</a>')
        self.lbl_xls.setStyleSheet("font-weight: bold; font-size: 14px;")
        self.lbl_xls.setCursor(Qt.PointingHandCursor)
        self.lbl_xls.mouseDoubleClickEvent = lambda event: self._open_excel_file(excel_path)
        xls_layout.addWidget(self.lbl_xls, stretch=1)

        self.btn_reload = QPushButton("change Excel")
        self.btn_reload.setMinimumSize(100, 36)
        self.btn_reload.setStyleSheet("font-weight: bold; background-color: #64748B; color: white; border-radius: 6px;")
        self.btn_reload.clicked.connect(self.change_excel)
        xls_layout.addWidget(self.btn_reload)

        self.btn_reload = QPushButton("load Excel")
        self.btn_reload.setMinimumSize(100, 36)
        self.btn_reload.setStyleSheet("font-weight: bold; background-color: #64748B; color: white; border-radius: 6px;")
        self.btn_reload.clicked.connect(lambda: self.reload_excel(self.excel_path_local, keep_selection=True))
        xls_layout.addWidget(self.btn_reload)

        self.btn_save = QPushButton("save to Excel")
        self.btn_save.setMinimumSize(100, 36)
        self.btn_save.setStyleSheet("font-weight: bold; background-color: #059669; color: white; border-radius: 6px;")
        self.btn_save.clicked.connect(self.save_to_excel)
        xls_layout.addWidget(self.btn_save)

        layout.addLayout(xls_layout)

        sheet_layout = QHBoxLayout()
        lbl_sheet = QLabel("시트:")
        lbl_sheet.setStyleSheet("font-weight: bold; font-size: 13px;")
        self.combo_sheet = QComboBox()
        self.combo_sheet.setMinimumWidth(200)
        self.combo_sheet.currentTextChanged.connect(self.load_sheet)
        sheet_layout.addWidget(lbl_sheet)
        sheet_layout.addWidget(self.combo_sheet)
        sheet_layout.addStretch()
        layout.addLayout(sheet_layout)

        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        layout.addWidget(separator)
        
        toolbar = self._create_toolbar()
        layout.addWidget(toolbar)

        self.table = QTableWidget()
        self.table.setEditTriggers(QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.setSelectionBehavior(QAbstractItemView.SelectItems)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)
        layout.addWidget(self.table, stretch=1)

        self._setup_shortcuts()

        btn_layout = QHBoxLayout()
        self.btn_run = QPushButton("Make file multi case run")
        self.btn_run.setMinimumSize(180, 36)
        self.btn_run.setStyleSheet("font-weight: bold; background-color: #1E40AF; color: white; border-radius: 6px;")
        self.btn_run.clicked.connect(self.on_make_run)
        btn_layout.addWidget(self.btn_run)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        self.reload_excel(self.excel_path, keep_selection=False)


    @staticmethod
    def show_window(parent, file_path):
        """기존 files_tab.py의 우클릭 호출 방식을 그대로 수용하는 브릿지 함수"""
       
        # 1. parent(files_tab) 내부에 숨겨진 다양한 형태의 엑셀 경로 변수명을 추적합니다.
        excel_path = ""
        for attr_name in ["excel_path", "excel_file_path", "excel_filepath", "current_excel_path"]:
            if hasattr(parent, attr_name):
                excel_path = getattr(parent, attr_name)
                if excel_path and os.path.exists(str(excel_path)):
                    break
        
        # 2. 만약 메인 창에서 경로를 여전히 못 찾았다면 파일 열기 창(QFileDialog)을 강제로 띄워 사용자가 직접 선택하게 구원합니다.
        if not excel_path or not os.path.exists(str(excel_path)):
            excel_path, _ = QFileDialog.getOpenFileName(
                parent, "연동할 Excel 파일 선택", os.path.dirname(file_path), "Excel Files (*.xlsx *.xls)"
)
            
        # 레퍼런스 이름 추적 및 자동 보완
        ref_name = ref_name = os.path.basename(file_path) if file_path else ""

        # 3. 클래스 인스턴스(객체) 생성 및 출력
        dialog = MultiCaseRunWindow(parent, file_path, ref_name, excel_path)
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        
        if not hasattr(parent, '_multi_case_dialogs'):
            parent._multi_case_dialogs = []
        parent._multi_case_dialogs.append(dialog)
        
        dialog.show()
        return dialog

    def open_excel_file(self, excel_path):
        """라벨 더블클릭 시 윈도우 시스템 명령을 통해 실제 엑셀 프로그램을 실행하는 함수"""

        if not excel_path or not os.path.exists(excel_path):
            QMessageBox.warning(self, "파일 오류", f"열고자 하는 엑셀 파일이 존재하지 않습니다.\n경로: {excel_path}")
            return

        try:
            # 윈도우 환경(Windows)에서 기본 연결된 프로그램(Excel)으로 파일 가동
            if platform.system() == "Windows":
                os.startfile(excel_path)
            # macOS 환경 대응
            elif platform.system() == "Darwin":
                subprocess.Popen(["open", excel_path])
            # Linux 환경 대응
            else:
                subprocess.Popen(["xdg-open", excel_path])
                
            print(f"[MultiCase] 외부 엑셀 실행 성공: {excel_path}")
        except Exception as e:
            QMessageBox.critical(self, "실행 실패", f"엑셀 파일을 여는 중 오류가 발생했습니다:\n{str(e)}")

    def _create_toolbar(self):
        toolbar = QToolBar()
        toolbar.setMovable(False)
        toolbar.setStyleSheet("QToolBar { border: none; spacing: 8px; }")

        btn_copy = QPushButton("복사")
        btn_copy.clicked.connect(self._copy_selected)
        toolbar.addWidget(btn_copy)

        btn_cut = QPushButton("잘라내기")
        btn_cut.clicked.connect(self._cut_selected)
        toolbar.addWidget(btn_cut)

        btn_paste = QPushButton("붙여넣기")
        btn_paste.clicked.connect(self._paste_selected)
        toolbar.addWidget(btn_paste)

        toolbar.addSeparator()

        btn_add_row = QPushButton("행 +")
        btn_add_row.clicked.connect(self._add_row)
        toolbar.addWidget(btn_add_row)

        btn_del_row = QPushButton("행 -")
        btn_del_row.clicked.connect(self._delete_selected_rows)
        toolbar.addWidget(btn_del_row)

        btn_add_col = QPushButton("열 +")
        btn_add_col.clicked.connect(self._add_column)
        toolbar.addWidget(btn_add_col)

        btn_del_col = QPushButton("열 -")
        btn_del_col.clicked.connect(self._delete_selected_columns)
        toolbar.addWidget(btn_del_col)

        toolbar.addSeparator()

        btn_hide_row = QPushButton("행 숨기기")
        btn_hide_row.clicked.connect(self._hide_selected_rows)
        toolbar.addWidget(btn_hide_row)

        btn_show_row = QPushButton("행 보이기")
        btn_show_row.clicked.connect(self._show_all_rows)
        toolbar.addWidget(btn_show_row)

        btn_hide_col = QPushButton("열 숨기기")
        btn_hide_col.clicked.connect(self._hide_selected_columns)
        toolbar.addWidget(btn_hide_col)

        btn_show_col = QPushButton("열 보이기")
        btn_show_col.clicked.connect(self._show_all_columns)
        toolbar.addWidget(btn_show_col)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        toolbar.addWidget(spacer)

        return toolbar

    def _setup_shortcuts(self):
        QShortcut(QKeySequence(Qt.CTRL | Qt.Key_C), self, self._copy_selected)
        QShortcut(QKeySequence(Qt.CTRL | Qt.Key_V), self, self._paste_selected)
        QShortcut(QKeySequence(Qt.CTRL | Qt.Key_X), self, self._cut_selected)
        QShortcut(QKeySequence(Qt.CTRL | Qt.Key_A), self, self._select_all)
        QShortcut(QKeySequence(Qt.Key_Delete), self, self._delete_selected_rows)
        QShortcut(QKeySequence(Qt.CTRL | Qt.Key_Z), self, self._undo)
        QShortcut(QKeySequence(Qt.CTRL | Qt.Key_Y), self, self._redo)

    def _get_selected_ranges(self):
        selected = self.table.selectedItems()
        if not selected:
            return None
        rows = {item.row() for item in selected}
        cols = {item.column() for item in selected}
        return min(rows), max(rows), min(cols), max(cols)

    def _get_range_data(self, r1, r2, c1, c2):
        data = []
        for r in range(r1, r2 + 1):
            row = []
            for c in range(c1, c2 + 1):
                item = self.table.item(r, c)
                row.append(item.text() if item else "")
            data.append(row)
        return data

    def _set_range_data(self, r1, c1, data):
        for dr, row in enumerate(data):
            for dc, val in enumerate(row):
                r, c = r1 + dr, c1 + dc
                if r < self.table.rowCount() and c < self.table.columnCount():
                    item = self.table.item(r, c)
                    if item is None:
                        item = QTableWidgetItem(str(val))
                        self.table.setItem(r, c, item)
                    else:
                        item.setText(str(val))

    def _copy_selected(self):
        rng = self._get_selected_ranges()
        if not rng:
            return
        r1, r2, c1, c2 = rng
        data = self._get_range_data(r1, r2, c1, c2)
        tsv = "\n".join("\t".join(row) for row in data)
        self._clipboard = tsv
        mime = QMimeData()
        mime.setText(tsv)
        QGuiApplication.clipboard().setMimeData(mime)
        print(f"[MultiCase] 복사: {len(data)}행 x {len(data[0]) if data else 0}열")

    def _cut_selected(self):
        self._copy_selected()
        rng = self._get_selected_ranges()
        if rng:
            r1, r2, c1, c2 = rng
            for r in range(r1, r2 + 1):
                for c in range(c1, c2 + 1):
                    item = self.table.item(r, c)
                    if item:
                        item.setText("")

    def _paste_selected(self):
        self._save_state()
        if not self._clipboard:
            clipboard_content = QGuiApplication.clipboard().text()  
            if not clipboard_content:
                return
            self._clipboard = clipboard_content

        rows = self._clipboard.strip().split("\n")
        data = [row.split("\t") for row in rows]
        if not data or not data[0]:
            return

        rng = self._get_selected_ranges()
        if rng:
            r1, _, c1, _ = rng
        else:
            r1, c1 = 0, 0

        self._set_range_data(r1, c1, data)
        print(f"[MultiCase] 붙여넣기: {len(data)}행 x {len(data[0]) if data else 0}열")

    def _select_all(self):
        self.table.selectAll()

    # ═══════════════════════════════════════════════════════════════
    # Undo / Redo (Ctrl+Z / Ctrl+Y)
    # ═══════════════════════════════════════════════════════════════
    def _save_state(self):
        """ 현재 테이블 상태를 히스토리에 저장 """
        # 히스토리 인덱스 뒤의 오래된 기록 제거
        if self._history_index < len(self._history) - 1:
            self._history = self._history[:self._history_index + 1]

        state = {
            "rows": self.table.rowCount(),
            "cols": self.table.columnCount(),
            "data": self._get_range_data(0, self.table.rowCount() - 1, 0, self.table.columnCount() - 1),
            "hidden_rows": set(self._hidden_rows),
            "hidden_cols": set(self._hidden_cols),
        }
        self._history.append(state)
        self._history_index = len(self._history) - 1

        # 최대 히스토리 제한
        if len(self._history) > self._max_history:
            self._history.pop(0)
            self._history_index -= 1

    def _restore_state(self, state):
        """ 히스토리 상태를 복원 """
        self.table.setRowCount(0)
        self.table.setColumnCount(0)
        self._hidden_rows.clear()
        self._hidden_cols.clear()

        rows = state["rows"]
        cols = state["cols"]
        data = state["data"]

        self.table.setColumnCount(cols)
        self.table.setRowCount(rows)

        for r in range(rows):
            for c in range(cols):
                val = data[r][c] if r < len(data) and c < len(data[r]) else ""
                self.table.setItem(r, c, QTableWidgetItem(str(val)))

        self._hidden_rows = set(state["hidden_rows"])
        self._hidden_cols = set(state["hidden_cols"])

        for r in self._hidden_rows:
            if r < rows:
                self.table.hideRow(r)
        for c in self._hidden_cols:
            if c < cols:
                self.table.hideColumn(c)

        self.table.resizeRowsToContents()

    def _undo(self):
        """ Ctrl+Z: 이전 상태로 복구 """
        if self._history_index <= 0:
            print("[MultiCase] 더 이상 되돌릴 수 없습니다.")
            return

        self._history_index -= 1
        self._restore_state(self._history[self._history_index])
        print(f"[MultiCase] 되돌리기: {self._history_index + 1}번째 상태로 복구")

    def _redo(self):
        """ Ctrl+Y: 다음 상태로 재실행 """
        if self._history_index >= len(self._history) - 1:
            print("[MultiCase] 더 이상 재실행할 수 없습니다.")
            return

        self._history_index += 1
        self._restore_state(self._history[self._history_index])
        print(f"[MultiCase] 재실행: {self._history_index + 1}번째 상태로 복구")

    def _add_row(self):
        self._save_state()
        row_count = self.table.rowCount()
        current_row = self.table.currentRow()
        if current_row < 0:
            current_row = row_count - 1

        self.table.setRowCount(row_count + 1)
        new_row = current_row + 1
        self.table.insertRow(new_row)
        for c in range(self.table.columnCount()):
            self.table.setItem(new_row, c, QTableWidgetItem(""))
        self.table.resizeRowsToContents()
        print(f"[MultiCase] 행 추가: {new_row}번째 행")

    def _delete_selected_rows(self):
        self._save_state()
        selected = sorted({item.row() for item in self.table.selectedItems()}, reverse=True)
        if not selected:
            return
        for r in selected:
            self.table.removeRow(r)
            self._hidden_rows.discard(r)
        print(f"[MultiCase] 행 삭제: {len(selected)}개 행")

    def _add_column(self):
        self._save_state()
        col_count = self.table.columnCount()
        current_col = self.table.currentColumn()
        if current_col < 0:
            current_col = col_count - 1

        self.table.setColumnCount(col_count + 1)
        new_col = current_col + 1
        self.table.insertColumn(new_col)
        item = self.table.horizontalHeaderItem(new_col)
        if not item:
            self.table.setHorizontalHeaderItem(new_col, QTableWidgetItem(f"Col_{new_col}"))
        for r in range(self.table.rowCount()):
            self.table.setItem(r, new_col, QTableWidgetItem(""))
        print(f"[MultiCase] 열 추가: {new_col}번째 열")

    def _delete_selected_columns(self):
        self._save_state()
        selected = sorted({item.column() for item in self.table.selectedItems()}, reverse=True)
        if not selected:
            return
        for c in selected:
            self.table.removeColumn(c)
            self._hidden_cols.discard(c)
        print(f"[MultiCase] 열 삭제: {len(selected)}개 열")

    def _hide_selected_rows(self):
        selected = sorted({item.row() for item in self.table.selectedItems()})
        for r in selected:
            self.table.hideRow(r)
            self._hidden_rows.add(r)
        print(f"[MultiCase] 행 숨기기: {len(selected)}개 행")

    def _show_all_rows(self):
        for r in list(self._hidden_rows):
            self.table.showRow(r)
        self._hidden_rows.clear()
        print("[MultiCase] 모든 행 보이기")

    def _hide_selected_columns(self):
        selected = sorted({item.column() for item in self.table.selectedItems()})
        for c in selected:
            self.table.hideColumn(c)
            self._hidden_cols.add(c)
        print(f"[MultiCase] 열 숨기기: {len(selected)}개 열")

    def _show_all_columns(self):
        for c in list(self._hidden_cols):
            self.table.showColumn(c)
        self._hidden_cols.clear()
        print("[MultiCase] 모든 열 보이기")

    def save_to_excel(self):
        if not self.excel_read[0]:
            QMessageBox.warning(self, "SAVE_ERROR", "로드된 엑셀 파일이 없습니다.")
            return

        path, _ = QFileDialog.getSaveFileName(
            self, "Excel 저장", self.excel_path_local,
            "Excel Files (*.xlsx *.xlsm *.xls);;All Files (*)"
        )
        if not path:
            return

        try:
            wb = openpyxl.load_workbook(self.excel_read[0])
            sheet_name = self.combo_sheet.currentText()
            if sheet_name in wb.sheetnames:
                ws = wb[sheet_name]
            else:
                ws = wb.active

            for r in range(self.table.rowCount()):
                for c in range(self.table.columnCount()):
                    item = self.table.item(r, c)
                    ws.cell(row=r + 1, column=c + 1, value=item.text() if item else "")

            wb.save(path)
            wb.close()
            QMessageBox.information(self, "SAVE_SUCCESS", f"Excel 저장 완료:\n{path}")
            print(f"[MultiCase] Excel 저장: {path}")
        except Exception as e:
            QMessageBox.critical(self, "SAVE_ERROR", f"Excel 저장 중 오류:\n{e}")

    @staticmethod
    def _col_letter_to_index(letter):
        letter = letter.upper()
        result = 0
        for char in letter:
            result = result * 26 + (ord(char) - ord('A') + 1)
        return result - 1
    
    def load_sheet(self, sheet_name):
        if not sheet_name or not self.excel_read[0]:
            return
        print(f"[MultiCase] load_sheet 호출: {sheet_name} / excel_read={self.excel_read[0]}")
        try:
            wb = openpyxl.load_workbook(self.excel_read[0], data_only=True)
            ws = wb[sheet_name]
            rows = list(ws.iter_rows(values_only=True))

            self.current_wb = wb
            self.current_ws = ws

            hidden_rows = set()
            for r in ws.row_dimensions:
                if ws.row_dimensions[r].hidden:
                    hidden_rows.add(r)

            hidden_cols = set()
            for c in ws.column_dimensions:
                if ws.column_dimensions[c].hidden:
                    hidden_cols.add(c)

            wb.close()
        except Exception as e:
            print(f"[MultiCase] 시트 읽기 예외: {e}")
            rows = [["액셀 읽기 실패:", str(e)]]
            hidden_rows = set()
            hidden_cols = set()
            ws = None
        if not rows:
            rows = [["(빈 시트)"]]

        data_cols = max((len(r) for r in rows if r), default=0)
        sheet_cols = ws.max_column if ws is not None else data_cols
        n_cols = max(data_cols, sheet_cols)

        self.table.setColumnCount(n_cols)
        self.table.setRowCount(len(rows))

        for r in range(len(rows)):
            self.table.showRow(r)
        for c in range(n_cols):
            self.table.showColumn(c)

        for r, row in enumerate(rows):
            for c in range(n_cols):
                val = row[c] if c < len(row) and row[c] is not None else ""
                self.table.setItem(r, c, QTableWidgetItem(str(val)))

        for excel_row in hidden_rows:
            table_row = excel_row - 1
            if 0 <= table_row < len(rows):
                self.table.hideRow(table_row)

        for col_letter in hidden_cols:
            col_idx = self._col_letter_to_index(col_letter)
            if 0 <= col_idx < n_cols:
                self.table.hideColumn(col_idx)

        self.table.resizeRowsToContents()
        print(f"[MultiCase] 테이블 세팅 완료: 데이터 {len(rows)}행")

    def _make_temp_copy(self, src_path):
        try:
            tmpf = tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx")
            shutil.copyfile(src_path, tmpf.name)
            tmpf.close()
            return tmpf.name
        except Exception as e:
            QMessageBox.critical(self, "액셀 복사 실패", str(e))
            return ""
        
    def reload_excel(self, src_path, keep_selection=False):
        if not src_path or not os.path.exists(src_path):
            QMessageBox.warning(self, "액셀 없음", "선택한 엑셀 파일을 찾을 수 없습니다.")
            return
        prev_sheet = self.combo_sheet.currentText() if keep_selection else ""
        tmp = self._make_temp_copy(src_path)
        if not tmp:
            return
        self.excel_read[0] = tmp
        self.excel_path_local = src_path
        try:
            wb = openpyxl.load_workbook(tmp)
            sheet_names = wb.sheetnames
            wb.close()
            self.combo_sheet.blockSignals(True)
            self.combo_sheet.clear()
            self.combo_sheet.addItems(sheet_names)
            if keep_selection and prev_sheet in sheet_names:
                self.combo_sheet.setCurrentText(prev_sheet)
                target = prev_sheet
            elif sheet_names:
                target = sheet_names[0]
            else:
                target = ""
            self.combo_sheet.blockSignals(False)
            if target:
                self.load_sheet(target)
        except Exception as e:
            print(f"[MultiCase] 시트목록 읽기 예외: {e}")
            QMessageBox.critical(self, "액셀 읽기 실패", str(e))

    def change_excel(self):
        """ [복사 없이 다이렉트 연동] 대상 Excel 파일만 재지정하여 화면에 즉시 재로드 """
        from PySide6.QtWidgets import QFileDialog, QMessageBox
        import os

        # 1. 새로 연결할 대상 Excel 파일 선택 (탐색기 팝업)
        picked, _ = QFileDialog.getOpenFileName(
            self, "연동할 Excel 파일 선택", os.path.dirname(self.excel_path_local),
            "Excel Files (*.xlsx *.xlsm *.xls);;All Files (*)"
        )
        
        # 취소 버튼을 누르면 아무 작업도 하지 않고 탈출
        if not picked:
            return

        try:
            # 2. 기존 워크북 스트림 세션이 열려있다면 안전하게 닫아줍니다.
            if hasattr(self, 'current_wb') and self.current_wb:
                try:
                    self.current_wb.close()
                except Exception:
                    pass

            print(f"[MultiCase] 대상 Excel 파일 변경 연동: {picked}")
            
            self.excel_path_local = picked
            self.excel_path = picked

            self.reload_excel(picked, keep_selection=False)
            
            self.lbl_xls.setText(f'<a href="{picked}" style="color: #1F2937; text-decoration: underline;">엑셀파일: {picked}</a>')
            self.lbl_xls.setToolTip(picked)
            
            self.lbl_xls.mouseDoubleClickEvent = lambda event: self._open_excel_file(picked)
            
        except Exception as e:
            QMessageBox.critical(self, "Excel 파일 전환 실패", f"파일을 불러오는 과정에서 오류가 발생했습니다:\n{str(e)}")


    def on_make_run(self):
        selected_rows = sorted({item.row() for item in self.table.selectedItems()})

        if self.table.rowCount() <= 1:
            print("[MultiCase] 처리할 데이터 행이 없습니다.")
            return

        if not selected_rows:
            print("[MultiCase] 선택된 행 없음 -> 화면에 보이는 행 내용을 기준으로 처리합니다.")
            selected_rows = [
                r for r in range(1, self.table.rowCount())
                if not self.table.isRowHidden(r)
                and any(
                    self.table.item(r, c) is not None and self.table.item(r, c).text().strip()
                    for c in range(self.table.columnCount())
                )
            ]

        headers = []
        for c in range(self.table.columnCount()):
            item = self.table.item(0, c)
            header_text = item.text().strip() if item is not None and item.text().strip() else f"Col_{c}"
            headers.append(header_text)

        display_to_param_key = {
            info.get("Description", ""): key
            for key, info in self.parameter_map.items()
            if info.get("Description")
        }
        print(f" display_to_param_key: {display_to_param_key}")

        changed_map = []
        of_run_list = {}

        for r in selected_rows:
            if r <= 0:
                continue

            row_values = []
            for c in range(self.table.columnCount()):
                item = self.table.item(r, c)
                value = item.text() if item is not None else ""
                row_values.append(value)

            row_data = {}
            for c, header in enumerate(headers):
                row_data[header] = row_values[c] if c < len(row_values) else ""

            of_word = str(row_data.get("OF_Word", "")).strip()
            file_symbol = str(row_data.get("File_Symbol", "")).strip()

            if of_word and file_symbol and of_word in self.parameter_map:
                old_symbol = self.parameter_map[of_word].get("File_Symbol", "")
                if old_symbol != file_symbol:
                    reply = QMessageBox.question(
                        self,
                        "parameter_map 변경 확인",
                        f"'{of_word}'의 File_Symbol을\n'{old_symbol}' -> '{file_symbol}'로 변경할까요?",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                        QMessageBox.StandardButton.No,
                    )
                    if reply == QMessageBox.StandardButton.Yes:
                        self.parameter_map[of_word]["File_Symbol"] = file_symbol
                        changed_map.append(f"{of_word}: {old_symbol} -> {file_symbol}")
                    else:
                        print(f"[MultiCase] 변경 취소: {of_word} ({old_symbol} -> {file_symbol})")

            row_output = {}
            for header, value in row_data.items():
                if not value:
                    continue
                if header in {"Description", "OF_Word", "File_Symbol"}:
                    continue

                param_key = display_to_param_key.get(header)
                if not param_key:
                    continue

                row_output[param_key] = value

            first_value = str(row_values[0]).strip() if row_values else ""
            if first_value.isdigit():
                of_run_list[f"N{first_value}"] = row_output

        if changed_map:
            print("[MultiCase] parameter_map 변경사항:")
            for msg in changed_map:
                print(f"  - {msg}")

        print("\n" + "=" * 60 + "OF_RunList JSON Output:")
        print(json.dumps(of_run_list, ensure_ascii=False, indent=2))

        print("\n" + "=" * 60 + "Generated Filenames:")
        max_num = max((int(k[1:]) for k in of_run_list.keys()), default=0)
        num_width = len(str(max_num))

        param_max_length = {}
        for run_key, row_output in of_run_list.items():
            for param_key, value in row_output.items():
                if param_key in self.parameter_map:
                    value_str = str(value).strip()
                    if param_key not in param_max_length:
                        param_max_length[param_key] = 0
                    param_max_length[param_key] = max(param_max_length[param_key], len(value_str))

        for run_key, row_output in of_run_list.items():
            num_part = run_key[1:]
            padded_num = num_part.zfill(num_width)
            filename_parts = [f"N{padded_num}"]

            for param_key in row_output.keys():
                if param_key in self.parameter_map:
                    file_symbol = self.parameter_map[param_key].get("File_Symbol", "")
                    truncated_symbol = file_symbol[:5] if file_symbol else ""
                    value = str(row_output[param_key]).strip().replace(" ", "")
                    if not value:
                        continue

                    numeric_check = value.replace('.', '').replace('-', '')
                    if numeric_check.isdigit():
                        padded_value = value.zfill(param_max_length.get(param_key, 0)) if param_max_length.get(param_key, 0) > 0 else value
                    else:
                        padded_value = value

                    if truncated_symbol:
                        filename_parts.append(f"{truncated_symbol}{padded_value}")

            filename = "_".join(filename_parts)
            of_run_list[run_key]["FST_File"] = filename
            print(f"  {filename}")

        print("\n" + "=" * 60 + "파일 생성 및 저장 시작")

        main_fst_path = self.file_path
        main_fst_dir = os.path.dirname(main_fst_path)
        main_fst_basename = os.path.basename(main_fst_path)
        main_fst_base = os.path.splitext(main_fst_basename)[0]

        from src.core.openfast_io import OpenFastIO
        files_to_copy = []

        soft_copy_targets = [
            "EDFile", "AeroFile", "ServoFile", "SeaStFile", "HydroFile", "MooringFile", "SubFile", "IceFile", "SoilFile", "InflowFile"
        ]

        for key, info in OpenFastIO.current_config.items():
            if key not in soft_copy_targets or not isinstance(info, dict):
                continue

            raw_value = info.get("current") or info.get("default")
            if not raw_value:
                continue

            paths_to_check = []
            if isinstance(raw_value, list):
                paths_to_check.extend(raw_value)
            elif isinstance(raw_value, str):
                paths_to_check.append(raw_value)

            for path_item in paths_to_check:
                if not isinstance(path_item, str) or not path_item.strip():
                    continue
                if path_item.strip() in ["0", "1", "2", "3"] or path_item.replace('.', '', 1).isdigit():
                    continue
                if '.' not in os.path.basename(path_item):
                    continue

                if not os.path.isabs(path_item):
                    resolved_path = os.path.normpath(os.path.join(os.path.dirname(main_fst_path), path_item))
                else:
                    resolved_path = os.path.normpath(path_item)

                if os.path.exists(resolved_path) and os.path.isfile(resolved_path):
                    if (key, resolved_path) not in files_to_copy:
                        files_to_copy.append((key, resolved_path))

        ext_rules = {
            "edfile": ".ela",
            "aerofile": ".aer",
            "servofile": ".ser",
            "seastfile": ".sea",
            "hydrofile": ".hyd",
            "mooringfile": ".moo",
            "subfile": ".sub",
            "icefile": ".ice",
            "soilfile": ".sol",
            "inflowfile": ".inf"
        }

        self.apply_all_policy = None

        for run_key, run_data in of_run_list.items():
            fst_filename = run_data.get("FST_File", "")
            if not fst_filename:
                continue

            main_replace_map = {}
            sub_replace_map = {}
            copied_files = []
            skip_this_run = False

            new_fst_path = os.path.join(main_fst_dir, f"{fst_filename}.fst")
            confirm = self.confirm_overwrite_with_policy(new_fst_path)
            if confirm is None:
                print("[MultiCase] 사용자가 작업을 취소했습니다.")
                return
            if not confirm:
                print(f"  [건너 skipped] {fst_filename}.fst 이미 존재")
                skip_this_run = True

            if not skip_this_run:
                try:
                    shutil.copy2(main_fst_path, new_fst_path)
                    print(f"  [생성] {fst_filename}.fst")
                    of_run_list[run_key]["NewFST_Path"] = new_fst_path
                except Exception as e:
                    print(f"  [오류] {fst_filename}.fst 생성 실패: {e}")
                    continue

                for key, src_path in files_to_copy:
                    src_basename = os.path.basename(src_path)
                    src_base = os.path.splitext(src_basename)[0]
                    src_ext = os.path.splitext(src_basename)[1]

                    target_ext = ext_rules.get(key.lower(), src_ext)
                    new_sub_basename = f"{fst_filename}{target_ext}"
                    dst_path = os.path.join(main_fst_dir, new_sub_basename)

                    confirm = self.confirm_overwrite_with_policy(dst_path)
                    if confirm is None:
                        print("[MultiCase] 사용자가 작업을 취소했습니다.")
                        return
                    if not confirm:
                        print(f"  [건너 skipped] {new_sub_basename} 이미 존재")
                        continue

                    try:
                        shutil.copy2(src_path, dst_path)
                        print(f"    -> {new_sub_basename}")
                        copied_files.append(dst_path)

                        main_replace_map[src_basename] = new_sub_basename
                        main_replace_map[src_base] = fst_filename
                        sub_replace_map[src_basename] = new_sub_basename
                    except Exception as e:
                        print(f"    X {new_sub_basename} 생성 실패: {e}")

                target_files = [new_fst_path] + copied_files
                sorted_main_names = sorted(main_replace_map.keys(), key=len, reverse=True)
                sorted_sub_names = sorted(sub_replace_map.keys(), key=len, reverse=True)

                for file_path in target_files:
                    if not os.path.exists(file_path):
                        continue

                    is_main_fst = os.path.abspath(file_path) == os.path.abspath(new_fst_path)
                    try:
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()

                        modified = False
                        if is_main_fst:
                            loop_names = sorted_main_names
                        else:
                            current_base = os.path.splitext(os.path.basename(file_path))[0]
                            loop_names = [
                                name for name in sorted_sub_names
                                if not name.startswith(current_base)
                            ]

                        for old_name in loop_names:
                            if not old_name.strip():
                                continue
                            if old_name not in content:
                                continue

                            new_name = (
                                main_replace_map[old_name]
                                if is_main_fst
                                else sub_replace_map[old_name]
                            )
                            content = content.replace(old_name, new_name)
                            modified = True

                        if modified:
                            with open(file_path, 'w', encoding='utf-8') as f:
                                f.write(content)
                    except Exception as e:
                        print(f"    X {os.path.basename(file_path)} 내용 업데이트 실패: {e}")

                print(f"\n[Processing] {run_key} 세트 내부 KEY 데이터 변환 작업 시작")
                print(f"  -> 대상 파일명: {fst_filename}.fst")

                new_data = {}
                new_data_specified = {}

                for param_key, param_value in run_data.items():
                    if param_key in ["FST_File", "NewFST_Path"]:
                        continue

                    clean_val = str(param_value).strip()
                    if not clean_val:
                        continue

                    if param_key in self.parameter_map:
                        target_ext = self.parameter_map[param_key].get("Target_File", "").lower()
                        if not target_ext:
                            continue

                        if clean_val.startswith("+"):
                            clean_val = clean_val[1:]
                        elif clean_val.startswith("-"):
                            pass

                        if clean_val.replace('.', '', 1).replace('-', '', 1).isdigit():
                            formatted_val = clean_val
                        else:
                            formatted_val = f'"{clean_val}"'

                        if target_ext not in new_data_specified:
                            new_data_specified[target_ext] = {}
                        new_data_specified[target_ext][param_key] = formatted_val

                if ".fst" not in new_data_specified:
                    new_data_specified[".fst"] = {}

                for key, src_path in files_to_copy:
                    src_basename = os.path.basename(src_path)
                    new_sub_basename = main_replace_map.get(src_basename)
                    if new_sub_basename:
                        new_data_specified[".fst"][key] = f'"{new_sub_basename}"'

                print(f"  -> new_data_specified = {new_data_specified}")

                for target_ext, new_data in new_data_specified.items():
                    if not new_data:
                        continue

                    actual_file_path = os.path.join(main_fst_dir, fst_filename + target_ext)

                    print(f"  fst_filename = {fst_filename} \n  target_ext = {target_ext}\n  actual_file_path={actual_file_path}\n")

                    if target_ext == ".inf" and "FileName_BTS" in new_data_specified[".inf"]:
                        original_bts = new_data_specified[".inf"]["FileName_BTS"]
                        clean_bts = original_bts.replace('"', '').strip()

                        if not self.current_ws:
                            print("X [오류] 참조할 활성화된 엑셀 시트(self.current_ws)가 없습니다.")
                            return

                        new_data_specified[".inf"]["FileName_BTS"] = f'"../../3_Wind/DLC{self.current_ws.title}/{clean_bts}.bts"'

                    if actual_file_path and os.path.exists(actual_file_path):
                        try:
                            OpenFastIO.save_module_data(actual_file_path, new_data)
                            print(f"------ {target_ext} 파일 내부 변수 치환 동기화 완료\n")
                        except Exception as e:
                            print(f"X {target_ext} 파일 대상 데이터 주입 중 에러 발생: {e}")
                    else:
                        print(f"[경로 누락] {target_ext} 타입에 해당하는 생성된 물리 파일 경로를 찾을 수 없어 치환을 스킵합니다.")

                QCoreApplication.processEvents()

        print("=" * 60 + "\n")

    def confirm_overwrite_with_policy(self, path):
        if not os.path.exists(path):
            return True

        if self.apply_all_policy == "YES_ALL":
            return True
        if self.apply_all_policy == "NO_ALL":
            return False

        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("파일 덮어쓰기 확인")
        msg_box.setText(f"이미 존재하는 파일입니다:\n{os.path.basename(path)}\n\n 덮어쓰시겠습니까?")

        yes_btn = msg_box.addButton("예 (&Y)", QMessageBox.ButtonRole.YesRole)
        yes_all_btn = msg_box.addButton("모두 예 (&A)", QMessageBox.ButtonRole.YesRole)
        no_btn = msg_box.addButton("아니오 (&N)", QMessageBox.ButtonRole.NoRole)
        no_all_btn = msg_box.addButton("모두 아니오 (&L)", QMessageBox.ButtonRole.NoRole)
        cancel_btn = msg_box.addButton(QMessageBox.StandardButton.Cancel)

        msg_box.setDefaultButton(no_btn)
        msg_box.exec_()

        clicked_btn = msg_box.clickedButton()

        if clicked_btn == yes_btn:
            return True
        elif clicked_btn == yes_all_btn:
            self.apply_all_policy = "YES_ALL"
            return True
        elif clicked_btn == no_btn:
            return False
        elif clicked_btn == no_all_btn:
            self.apply_all_policy = "NO_ALL"
            return False
        else:
            return None


    def closeEvent(self, event):
        if self.excel_read[0] and os.path.exists(self.excel_read[0]):
            try:
                os.remove(self.excel_read[0])
            except Exception:
                pass
        super().closeEvent(event)
