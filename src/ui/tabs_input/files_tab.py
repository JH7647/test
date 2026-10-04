import os
import copy
import sys
import subprocess 
import json
import shutil
import tempfile
from PySide6 import QtGui
import openpyxl
import re

from datetime import datetime
# from logging import config

from PySide6.QtWidgets import QMessageBox, QFileDialog, QDialog, QCheckBox
from PySide6.QtCore import QDir, QPoint, Qt, QSettings, QProcess
from PySide6.QtGui import QStandardItemModel, QStandardItem
from PySide6.QtWidgets import QTextEdit, QPushButton, QHBoxLayout, QFormLayout, QSpinBox, QLineEdit, QComboBox, QTableWidget, QTableWidgetItem, QAbstractItemView, QFileSystemModel
from PySide6.QtGui import QColor, QBrush, QFont, QCursor,QTextCursor, QAction
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QTabWidget, QLabel, QTreeView, QSplitter, QTreeWidget, QTreeWidgetItem 
from PySide6.QtWidgets import QFileDialog, QInputDialog, QMessageBox, QWidget, QVBoxLayout, QTreeView, QMenu

from src.core.openfast_io import OpenFastIO  
from src.core.process_queue import ProcessQueueManager
from src.core.process_queue import ProcessQueueManager, PROCESS_TREE_STATUS_PENDING, PROCESS_TREE_STATUS_RUNNING, PROCESS_TREE_STATUS_COMPLETED, PROCESS_TREE_STATUS_STOP, PROCESS_TREE_STATUS_ERROR



PROGRESS_RE = re.compile(r"Time:\s*(\d+)\s+of\s+(\d+)\s+seconds[^\r\n]*")


class FilesTab(QWidget):
    """ 오직 파일 디렉토리 탐색과 드래그앤드롭 모션, 트리 배지만 책임지는 정석 UI 위젯 """
    
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window  # 상위 컨트롤러 메인 창 정보 저장 (탭 라우팅 신호용)
        self._drag_start_position = QPoint()

        # ProcessQueueManager initialized BEFORE init_ui()
        self.queue_mgr = ProcessQueueManager(self)
        self.queue_mgr.item_added.connect(self._on_queue_item_added)
        self.queue_mgr.item_updated.connect(self._on_queue_item_updated)
        self.queue_mgr.item_removed.connect(self._on_queue_item_removed)
        self.queue_mgr.log_received.connect(self._on_queue_log_received)
        self.queue_mgr.progress_updated.connect(self._on_queue_progress_updated)
        self.queue_mgr.buttons_update_needed.connect(self._on_queue_buttons_update)
        
        self.init_ui()  # <-- Called AFTER queue_mgr exists

    def init_ui(self):

        self.setAcceptDrops(True)

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(2, 2, 2, 2)
        main_layout.setSpacing(2)

        self.main_splitter = QSplitter(Qt.Horizontal)
        self.main_splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: #D1D5DB;
            }
            QSplitter::handle:horizontal {
                width: 1px;
            }
        """)

        main_layout.addWidget(self.main_splitter)

# region : [LEFT SIDE] 세로 Splitter로 분할 ==============================================================================================================================================================
        left_vsplitter = QSplitter(Qt.Vertical)

        # 상단: 디렉토리 버튼 + 파일 트리
        left_top_widget = QWidget()
        left_top_layout = QVBoxLayout(left_top_widget)
        left_top_layout.setContentsMargins(0, 0, 0, 0)
        left_top_layout.setSpacing(5)

        # 하단: 프로세스 헤더 + 프로세스 트리
        left_bottom_widget = QWidget()
        left_bottom_layout = QVBoxLayout(left_bottom_widget)
        left_bottom_layout.setContentsMargins(0, 0, 0, 0)
        left_bottom_layout.setSpacing(5)
        
        # --- 좌측 상단 패널을 다시 좌우로 분할 ---
        left_top_splitter = QSplitter(Qt.Horizontal)

        # 1. 디렉토리 탐색기 트리
        dir_explorer_widget = QWidget()
        dir_explorer_layout = QVBoxLayout(dir_explorer_widget)
        dir_explorer_layout.setContentsMargins(0,0,0,0)
        
        self.dir_model = QFileSystemModel()
        self.dir_model.setRootPath('')
        self.dir_model.setFilter(QDir.AllDirs | QDir.NoDotAndDotDot)

        self.dir_explorer_tree = QTreeView()
        self.dir_explorer_tree.setModel(self.dir_model)
        self.dir_explorer_tree.setHeaderHidden(True)
        self.dir_explorer_tree.setIndentation(10) 
        for i in range(1, self.dir_model.columnCount()):
            self.dir_explorer_tree.hideColumn(i)
        
        self.dir_explorer_tree.selectionModel().selectionChanged.connect(self.on_dir_explorer_selected)
        dir_explorer_layout.addWidget(self.dir_explorer_tree)

        left_top_splitter.addWidget(dir_explorer_widget)

        # 2. .fst 파일 리스트
        fst_list_widget = QWidget()
        fst_list_layout = QVBoxLayout(fst_list_widget)
        fst_list_layout.setContentsMargins(0,0,0,0)
        # fst_list_layout.setSpacing(5)

        # --- 파일 타입 필터 체크박스 (한 줄에 배치) ---
        filter_layout = QHBoxLayout()
        # filter_layout.setContentsMargins(0, 0, 0, 0)
        # filter_layout.setSpacing(2)

        self.chk_fst = QCheckBox("📜  ")
        self.chk_out = QCheckBox("📊  ")
        self.chk_lin = QCheckBox("∿  ")
        
        self.chk_fst.setChecked(True)
        self.chk_out.setChecked(False)
        self.chk_lin.setChecked(False)

        for chk in (self.chk_fst, self.chk_out, self.chk_lin):
            chk.setStyleSheet("font-size: 12px; font-weight: bold; color: #374151;")
            chk.stateChanged.connect(self.on_file_filter_changed)
            filter_layout.addWidget(chk)
        
        filter_layout.addStretch()
        fst_list_layout.addLayout(filter_layout)
        
        self.dir_tree = QTreeView()  
        self.dir_tree.setHeaderHidden(True)
        self.dir_tree.setRootIsDecorated(False)    
        self.dir_tree.setIndentation(2)           
        self.dir_tree.setExpandsOnDoubleClick(False)
        self.dir_tree.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.dir_tree.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.dir_tree_model = QStandardItemModel()   
        self.dir_tree.setModel(self.dir_tree_model)        
        self.dir_tree.setStyleSheet("""
            QTreeView { 
                border: 1px solid #E5E7EB; 
                background-color: #FFFFFF; 
                font-size: 12px; 
            }
            QTreeView::viewport {
                background-color: #FFFFFF;
            }
            QTreeView::item { 
                padding: 4px 0px; 
            }
            QTreeView::item:selected {
                background-color: #D1D5DB !important; 
                color: #374151 !important;            
                font-weight: bold;         
            }
            QTreeView::item:hover:!selected {
                background-color: rgba(230, 242, 255, 50);   
            }
        """)
        self.dir_tree.mousePressEvent = self.dir_tree_clicked
        self.dir_tree.doubleClicked.connect(self.dir_tree_item_double_clicked)
        self.dir_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.dir_tree.setAcceptDrops(True)
        self.dir_tree.dragEnterEvent = self.dir_tree_drag_enter_event
        self.dir_tree.dropEvent = self.dir_tree_drop_event
        fst_list_layout.addWidget(self.dir_tree)
        left_top_splitter.addWidget(fst_list_widget)

        left_top_splitter.setSizes([250, 300])
        left_top_layout.addWidget(left_top_splitter)

        # 3. Process list 표시 영역 (라벨 및 Run, Stop 버튼 한 행 구성)
        process_header_layout = QHBoxLayout()
        process_header_layout.setContentsMargins(4, 10, 0, 2) # 좌, 상, 우, 하
        process_header_layout.setSpacing(0) # 레이아웃 기본 스페이싱은 0으로 격리
        
        # ⚙️ Process list 표시 라벨
        self.lbl_process = QLabel(" ⚙️ OpenFAST Process list")
        self.lbl_process.setStyleSheet("font-weight: bold; color: #374151; font-size: 14px;")
        process_header_layout.addWidget(self.lbl_process)
        self.lbl_process.mouseDoubleClickEvent = self.process_tree_adjust_run_count
        
        # 여기에 Stretch를 넣어 왼쪽 라벨을 고정하고 모든 버튼을 오른쪽 끝으로 밀어냅니다.
        process_header_layout.addStretch() 
        
        # 🚀 Run 버튼 (너비 및 디자인 유지)
        self.btn_left_run = QPushButton(" 🚀 Run ")
        # self.btn_left_run.setFixedWidth(120)     
        self.btn_left_run.setMinimumHeight(30)   
        self.btn_left_run.setStyleSheet("""
            QPushButton {
                font-weight: bold;
                color: #2563EB;
                background-color: #EFF6FF; 
                border: 1px solid #BFDBFE;  
                border-radius: 4px;
                font-size: 14px;
            }
            QPushButton:hover {
                color: #1D4ED8;
                background-color: #DBEAFE; 
                border-color: #93C5FD;
            }
        """)
        self.btn_left_run.clicked.connect(self.btn_left_run_clicked)
        process_header_layout.addWidget(self.btn_left_run)
        process_header_layout.addSpacing(20)
        
        # 🛑 Stop 버튼 (너비 및 디자인 유지)
        self.btn_left_stop = QPushButton(" 🛑 Stop ")
        # self.btn_left_stop.setFixedWidth(120)     
        self.btn_left_stop.setMinimumHeight(30)   
        self.btn_left_stop.setStyleSheet("""
            QPushButton {
                font-weight: bold;
                color: #DC2626;
                background-color: #FEF2F2; 
                border: 1px solid #FEE2E2;  
                border-radius: 4px;
                font-size: 14px;
            }
            QPushButton:hover {
                color: #B91C1C;
                background-color: #FEE2E2; 
                border-color: #FCA5A5;
            }
        """)
        self.btn_left_stop.setEnabled(False)  
        process_header_layout.addWidget(self.btn_left_stop)
        left_bottom_layout.addLayout(process_header_layout)

        # === process_tree 실행 큐 데이터 구조 ===
        self.process_tree_run_queue = {
            "pending": [],       # 런예정 파일 경로 리스트
            "running": [],       # 런중 파일 경로 리스트
            "completed": [],     # 런완료 리스트
        }
        self.process_tree_max_concurrent = 3       # 최대 동시 실행 수
        self.process_tree_process_map = {}         # {file_path: QProcess} 실행 프로세스 추적

        # 프로세스 상태 트리 (평면 리스트 형태)
        self.process_tree = QTreeWidget()
        self.process_tree.setHeaderLabels(["File", "Status", "Start", "Finish"])
        self.process_tree.setColumnWidth(0, 320)   # File    ← 2배 길이 (기본 160px × 2)
        self.process_tree.setColumnWidth(1, 100)   # Status
        self.process_tree.setColumnWidth(2, 100)   # Start
        self.process_tree.setColumnWidth(3, 100)   # Finish    
        self.process_tree.setRootIsDecorated(False)   # 그룹 화살표 제거
        self.process_tree.setIndentation(0)
        self.process_tree.setExpandsOnDoubleClick(False)

        self.process_tree_model = self.process_tree  
        self.process_tree_list = self.process_tree    

        self.process_tree.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.process_tree.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.process_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.process_tree.setStyleSheet("""
            QTreeView {
                border: 1px solid #E5E7EB;
                background-color: #FFFFFF;
                font-size: 12px;
            }
            QTreeView::viewport {
                background-color: #FFFFFF;
            }
            QTreeView::item {
                padding: 4px 0px;
            }
            QTreeView::item:selected {
                /* background-color: #D1D5DB;  ← 배경 유지 */
            }
            QTreeView::item:hover:!selected {
                background-color: rgba(230, 242, 255, 50);
            }
        """)
        self.process_tree.clicked.connect(self.process_tree_on_item_clicked)
        self.process_tree.clicked.connect(self.process_tree_on_item_selection_changed)
    
        left_bottom_layout.addWidget(self.process_tree, stretch=2)

        self.process_logs = {}       
        self.current_viewing_path = "" 

        # 세로 Splitter에 위젯 추가
        left_top_widget.setMinimumWidth(300)
        left_vsplitter.addWidget(left_top_widget)
        left_vsplitter.addWidget(left_bottom_widget)
        left_vsplitter.setSizes([400, 200])  

        self.main_splitter.addWidget(left_vsplitter)

# endregion : ==========================================================================================================================================================================================

# region : [RIGHT SIDE] 파일 경로 상세 정보 및 실행 로그 제어 영역 ===========================================================================================================================================
        right_vsplitter = QSplitter(Qt.Vertical)
        right_vsplitter.setChildrenCollapsible(False)

        right_top_widget = QWidget()
        right_top_layout = QVBoxLayout(right_top_widget)
        right_top_layout.setContentsMargins(0, 0, 0, 0)
        right_top_layout.setSpacing(5)

        right_bottom_widget = QWidget()
        right_bottom_layout = QVBoxLayout(right_bottom_widget)
        right_bottom_layout.setContentsMargins(0, 0, 0, 0)
        right_bottom_layout.setSpacing(5)

        # OpenFAST 모델 구성 정보 표시 트리뷰   
        self.model_tree = QTreeView()
        self.model_tree.setHeaderHidden(True)
        self.model_tree.setRootIsDecorated(True)   
        self.model_tree.setIndentation(20)
        self.model_tree.setExpandsOnDoubleClick(False)
        self.model_tree_model = QStandardItemModel()
        self.model_tree.setModel(self.model_tree_model)
        self.model_tree.setStyleSheet("""
            QTreeView { 
                border: 1px solid #E5E7EB; 
                background-color: #FFFFFF; 
                font-size: 12px; 
            }
            QTreeView::viewport {
                background-color: #FFFFFF;
            }
            QTreeView::item { 
                padding: 3px 0px; 
            }
            QTreeView::item:selected {
                background-color: #D1D5DB !important; 
                color: #374151 !important;            
                font-weight: bold;         
            }
        """)

        # 마우스 물리 피지컬 이벤트 격리 바인딩
        self.model_tree.mousePressEvent = self.model_tree_press_event
        self.model_tree.mouseMoveEvent = self.model_tree_move_event
        self.model_tree.clicked.connect(self.model_tree_clicked)
        self.model_tree.doubleClicked.connect(self.model_tree_item_double_clicked)
        self.model_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.model_tree.customContextMenuRequested.connect(self.model_tree_item_right_clicked)

        right_top_layout.addWidget(self.model_tree, stretch=402)

        # CMD Result 표시 영역
        process_result_header_layout = QHBoxLayout() # 좌측 process_header_layout의 (4, 10, 0, 2)와 똑같이 상단 여백(10px)을 주어 완벽하게 수평을 맞춥니다.
        process_result_header_layout.setContentsMargins(4, 16, 0, 6)
        process_result_header_layout.setSpacing(0)

        lbl_process_result = QLabel(" 🔍 Process Log from OpenFAST")
        lbl_process_result.setStyleSheet("font-weight: bold; color: #374151; font-size: 14px;")
        process_result_header_layout.addWidget(lbl_process_result)
        
        right_bottom_layout.addLayout(process_result_header_layout)

        self.cmd_output = QTextEdit()
        self.cmd_output.setReadOnly(True)
        self.cmd_output.setStyleSheet("""
            QTextEdit {
                background-color: #FFFFFF; 
                color: #2D3748;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 12px;
                border: 1px solid #E5E7EB; /* 좌측 트리뷰 선 색상인 #E5E7EB와 일치 */
                border-radius: 0px;        /* 테두리 각 지게 통일 */
                padding: 6px;              /* 좌측 QTreeView::item padding 비율과 매칭 */
            }
        """)
        self.cmd_output.append("Simulation logs will be displayed.\n")
        right_bottom_layout.addWidget(self.cmd_output, stretch=186)

        right_top_widget.setMinimumWidth(300)
        right_vsplitter.addWidget(right_top_widget)
        right_vsplitter.addWidget(right_bottom_widget)
        right_vsplitter.setSizes([500, 500])
        
        self.main_splitter.addWidget(right_vsplitter)
        self.main_splitter.setSizes([400, 600])
# endregion : =====================================================================================================================================================================================

        self.on_tab_enter()  # 탭 진입 시 UI 초기화

    def on_tab_enter(self):
        """ Files 탭에 진입할 때마다 UI를 새로고침합니다. """
        settings = QSettings("JHLEE", "OFA")
        last_fst_path = settings.value("LastFstPath_fst", "")

        if last_fst_path and os.path.exists(last_fst_path):
            self.displayed_files = [last_fst_path]  
            self.dir_tree_update(last_fst_path)
            self.model_tree_update(self.displayed_files)  

            dir_path = os.path.dirname(last_fst_path)
            if dir_path:
                index = self.dir_model.index(dir_path)
                if index.isValid():
                    self.dir_explorer_tree.setCurrentIndex(index)
                    self.dir_explorer_tree.scrollTo(index, QAbstractItemView.PositionAtTop)

            # print(f"[DEBUG] on_tab_enter: last_fst_path={last_fst_path}, displayed_files={self.displayed_files}")

    def on_dir_explorer_selected(self, selected, deselected):
        """디렉토리 탐색기에서 디렉토리 선택 시 .fst 목록 업데이트"""
        indexes = selected.indexes()
        if not indexes:
            return
        
        index = indexes[0]
        dir_path = self.dir_model.filePath(index)
        print(f"[DEBUG] Explorer selected: dir_path={dir_path}")  # ← 이 줄 추가
        
        if dir_path:
            self.dir_tree_update(dir_path)

    def dir_tree_drag_enter_event(self, event):
        """ dir_tree에 드래그가 들어왔을 때 허용합니다. """
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dir_tree_drop_event(self, event):
        """ dir_tree에 파일이 드롭되었을 때 해당 파일의 디렉토리로 갱신합니다. """
        urls = event.mimeData().urls()
        if not urls:
            return

        file_path = urls[0].toLocalFile()
        self.dir_tree_update(os.path.dirname(file_path))

        self.splitter.setSizes([550, 450])

    def dir_tree_item_double_clicked(self, index):
        """ 좌측 트리 항목을 더블 클릭했을 때 Notepad++로 파일을 즉시 연는 슬롯 """
        if not index.isValid():
            return

        print("📜 [FilesTab] Double-click detected on directory tree item.")
        
        # 인덱스로부터 데이터 모델 아이템 호출
        item = self.dir_tree_model.itemFromIndex(index)
        if not item:
            return
            
        file_path = item.data(Qt.UserRole)
        
        npp_path = r"C:\Program Files\Notepad++\notepad++.exe"
        
        # 하드디스크에 실제 파일이 존재하는지 검증 (안전핀)
        if file_path and os.path.exists(file_path):
            try:
                # 1. 시스템에 Notepad++ 가 설치되어 있다면 우선적으로 점화
                if os.path.exists(npp_path):
                    subprocess.Popen([npp_path, file_path])
                    print(f"🚀 Notepad++ 오픈 완수: {os.path.basename(file_path)}")
                else:
                    # Notepad++ 주소가 없거나 유실 시 Windows 순정 메모장으로 2차 우회 방어
                    subprocess.Popen(["notepad.exe", file_path])
                    print(f"📝 Notepad++ 미설치로 기본 메모장 우회 구동: {os.path.basename(file_path)}")
            except Exception as e:
                # 예상치 못한 시스템 I/O 에러 발생 시 최종 순정 메모장 강제 복구 가동
                subprocess.Popen(["notepad.exe", file_path])
                print(f"⚠️ 에러 발생으로 기본 메모장 강제 우회: {str(e)}")
        else:
            print(f"⚠️ 파일 경로 유효성 검증 실패 또는 실재하지 않음: {file_path}")

    def dir_tree_clicked(self, event):
        """ 좌측 디렉토리 트리뷰에서 마우스 물리 누름(Press) 이벤트를 가로채어 처리 """
          
        # 어떤 특수키(Modifier)가 함께 눌렸는지 확인
        modifiers = QApplication.keyboardModifiers()

        # 마우스가 누른 좌표로부터 트리의 인덱스 추출
        index = self.dir_tree.indexAt(event.pos())

        # QTreeView 본연의 선택 및 하이라이트 모션을 유지하기 위해 부모 이벤트 호출
        QTreeView.mousePressEvent(self.dir_tree, event)

        # 빈 여백이 아닌 실제 파일 항목을 정확히 찍었을 때만 진입
        if not index.isValid():
            return

        self._apply_dir_tree_selection(index, modifiers)

    def _apply_dir_tree_selection(self, index, modifiers=None):
        """ dir_tree 인덱스의 선택 결과를 displayed_files / model_tree / QSettings 에 반영한다.
            마우스 클릭(dir_tree_clicked)과 자동 선택(_dir_tree_auto_select)이 공유하는 단일 진입점. """
        if modifiers is None:
            modifiers = QApplication.keyboardModifiers()

        item = self.dir_tree_model.itemFromIndex(index)
        if item:
            clicked_file_path = item.data(Qt.UserRole)
            
            if clicked_file_path and os.path.exists(clicked_file_path):
                
                if not hasattr(self, 'displayed_files'):
                    self.displayed_files = []

                # Ctrl 키를 누른 상태에서 클릭한 경우
                if bool(modifiers & Qt.ControlModifier):
                    # 조건 : 처음에 아무것도 표시되지 않은 상태였다면 -> 그냥 클릭한 파일만 표시
                    if not self.displayed_files:
                        self.displayed_files = [clicked_file_path]
                        print(f"⚡ [Ctrl + Click] 처음 상태 -> {clicked_file_path} 단독 추가")
                    
                    # 조건 : 이미 2개의 파일이 표시되어 있는 상태라면 -> 두번째 파일을 새 파일로 교체
                    elif len(self.displayed_files) >= 2:
                        print(f"⚡ [Ctrl + Click] 2개 포화 상태 -> 두번째 파일({self.displayed_files[1]})을 {clicked_file_path}로 교체")
                        self.displayed_files[1] = clicked_file_path
                    
                    # 그 외 (이미 1개만 표시되어 있던 상태) -> 뒤에 추가하여 2개로 만듦
                    else:
                        if clicked_file_path not in self.displayed_files:
                            self.displayed_files.append(clicked_file_path)
                            print(f"⚡ [Ctrl + Click] 두번째 파일 추가 -> {clicked_file_path}")
                
                # Ctrl 키를 누르지 않고 일반 클릭
                else:
                    self.displayed_files = [clicked_file_path]

                   # OpenFastIO 저장, Settings 레지스트리에도 동기화
                    OpenFastIO.current_config.setdefault("MainFST", {})["current"] = clicked_file_path
                    settings = QSettings("JHLEE", "OFA")
                    settings.setValue("LastFstPath_fst", clicked_file_path)

                    print(f" OpenFastIO.current_config.set = {OpenFastIO.current_config.get('MainFST', {}).get('current')}")

                # 리스트(self.displayed_files)에 포함된 파일들 하이라이트
                for row in range(self.dir_tree_model.rowCount()):
                    loop_item = self.dir_tree_model.item(row)
                    if not loop_item:
                        continue
                        
                    loop_path = loop_item.data(Qt.UserRole)
                    
                    # 현재 표시 대상 리스트에 들어있는 파일인 경우 -> 연회색 강조 적용
                    if loop_path and any(loop_path.lower() == df.lower() for df in self.displayed_files):
                        loop_item.setBackground(QBrush(QColor("#D1D5DB")))
                        loop_item.setForeground(QBrush(QColor("#374151")))
                        font = self._safe_font(loop_item, True)
                        loop_item.setFont(font)
                        
                    # 대상이 아닌 과거의 파일인 경우 -> 깨끗하게 원상 복구!
                    else:
                        loop_item.setBackground(QBrush(Qt.GlobalColor.transparent))
                        loop_item.setForeground(QBrush(Qt.GlobalColor.black))
                        font = self._safe_font(loop_item, False)
                        loop_item.setFont(font)
                
                # 🎯 [우측 화면 동기화] model_tree에 최종 결정된 리스트 전달하여 업데이트 실행
                if hasattr(self, 'model_tree_update'):
                    self.model_tree_update(self.displayed_files)
                

    def dir_tree_update(self, last_fst_path):
        """ 지정된 폴더 내부의 파일들을 필터에 맞춰 추출하여 좌측 리스트에 바인딩합니다. """
        self.dir_tree_model.clear()

        if os.path.isfile(last_fst_path):
            directory_path = os.path.dirname(last_fst_path)
            self.last_fst_path = last_fst_path  # 파일 경로인 경우 보존
        else:
            directory_path = last_fst_path
            # 디렉토리 경로가 들어온 경우 기존에 선택되어 있던 last_fst_path가 있다면 유지
            if not hasattr(self, 'last_fst_path'):
                settings = QSettings("JHLEE", "OFA")
                self.last_fst_path = settings.value("LastFstPath_fst", "")
    
        extensions = []
        if self.chk_fst.isChecked():
            extensions.append('.fst')
        if self.chk_out.isChecked():
            extensions.append('.out')
        if self.chk_lin.isChecked():
            extensions.append('.lin')

        if not extensions:
            extensions = ['.fst']

        try:
            files = os.listdir(directory_path)
            filtered_files = [f for f in files if any(f.lower().endswith(ext) for ext in extensions)]
        except Exception as e:
            if hasattr(self, 'cmd_output'):
                self.cmd_output.append(f"❌ 폴더 읽기 실패: {str(e)}\n")
            return
        
        # 빈 메시지도 동적으로 변경
        if not filtered_files:
            ext_str = ", ".join(extensions)
            item = QStandardItem(f"🚫 {ext_str} 파일이 없습니다.")
            item.setEnabled(False)
            item.setEditable(False)
            self.dir_tree_model.appendRow(item)
            return
        
        for file_name in sorted(filtered_files):
            full_path = os.path.join(directory_path, file_name).replace('\\', '/')
            
            # 아이콘도 확장자별로 다르게
            if file_name.lower().endswith('.fst'):
                icon = "📜"
            elif file_name.lower().endswith('.out'):
                icon = "📊"
            elif file_name.lower().endswith('.lin'):
                icon = "∿"
            else:
                icon = "📄"
            
            item = QStandardItem(f"{icon} {file_name}")
            item.setData(full_path, Qt.UserRole)
            item.setEditable(False) 
    
            item.setBackground(QBrush(Qt.GlobalColor.transparent))
            item.setForeground(QBrush(Qt.GlobalColor.black))
            
            # 🔍 수정 포인트: 전달받은 인자 대신 self.last_fst_path 및 self.displayed_files와 비교
            target_match_paths = [self.last_fst_path] if hasattr(self, 'last_fst_path') else []
            if hasattr(self, 'displayed_files') and self.displayed_files:
                target_match_paths = self.displayed_files

            if any(target_path and full_path.lower() == target_path.replace('\\', '/').lower() for target_path in target_match_paths):
                # 🎨 마우스 클릭 스타일시트와 완전히 일치하는 연회색/진한회색 주입
                item.setBackground(QBrush(QColor("#D1D5DB")))      
                item.setForeground(QBrush(QColor("#374151")))      
                font = self._safe_font(item, True)
                item.setFont(font)

            self.dir_tree_model.appendRow(item)

        # 목록 갱신 직후 아무것도 선택되어 있지 않으면 .fst 항목을 자동 선택한다.
        # (btn_left_run_clicked 가 self.dir_tree.selectedIndexes() 를 읽으므로 선택이 없으면
        #  '[Run] 선택된 항목이 없습니다.' 로 종료된다. .fst 만 후보로 제한해 MainFST 오염 방지)
        self._dir_tree_auto_select(getattr(self, 'last_fst_path', ''))

    def _dir_tree_auto_select(self, prefer_path='', force=False):
        """ dir_tree 에 자동 선택을 적용한다.
            - 이미 사용자가 선택해 둔 항목이 있으면 건드리지 않는다 (force=False 일 때)
            - prefer_path 와 일치하는 .fst 항목을 우선, 없으면 첫 번째 활성 .fst 항목 선택 """
        if not force and self.dir_tree.selectionModel().selectedIndexes():
            return False

        want = (prefer_path or '').replace('\\', '/').lower()

        target_row = -1
        for r in range(self.dir_tree_model.rowCount()):
            it = self.dir_tree_model.item(r)
            if not it or not it.isEnabled():
                continue

            path = (it.data(Qt.UserRole) or '').replace('\\', '/')
            if not path.lower().endswith('.fst'):
                continue

            if target_row < 0:
                target_row = r

            if want and path.lower() == want:
                target_row = r
                break

        if target_row < 0:
            return False

        index = self.dir_tree_model.index(target_row, 0)
        if not index.isValid():
            return False

        self.dir_tree.setCurrentIndex(index)
        self.dir_tree.scrollTo(index)
        self._apply_dir_tree_selection(index, Qt.NoModifier)
        return True

    def on_file_filter_changed(self, state):
        """파일 필터 체크박스 변경 시 파일 리스트 즉시 갱신"""
        indexes = self.dir_explorer_tree.selectionModel().selectedIndexes()
        if indexes:
            dir_path = self.dir_model.filePath(indexes[0])
            if dir_path:
                self.dir_tree_update(dir_path)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        import os
        urls = event.mimeData().urls()
        if not urls:
            return

        drop_file_path = os.path.normpath(urls[0].toLocalFile())
        current_main = OpenFastIO.current_config.get("MainFST", {}).get("current")

        # --- Case 1: 메인 설정 파일(.fst)이 드롭된 경우 ---
        if drop_file_path.endswith('.fst'):
            if not current_main or current_main != drop_file_path:
                msg_box = QMessageBox(self)
                msg_box.setIcon(QMessageBox.Question)
                # 오타 수정: Chage -> Change
                msg_box.setWindowTitle("🔄 Change File Warning")
                msg_box.setInformativeText(f"프로젝트 메인 파일을\n[{drop_file_path}]로 변경하시겠습니까?")
                msg_box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
                msg_box.setDefaultButton(QMessageBox.No)   

                if msg_box.exec() == QMessageBox.Yes:
                    self.model_tree_update(drop_file_path)

            if not current_main or current_main == drop_file_path:
                self.model_tree_update(drop_file_path)

            return
        
        # --- Case 2: 하위 모듈 파일들(.dat 등)이 드롭된 경우 ---
        else:
            # 안전장치: 주 설정 파일(.fst)이 먼저 로드되어 있어야 비교 및 쓰기가 가능
            if not current_main:
                QMessageBox.critical(self, "Error", ".fst 파일을 먼저 로드하세요.")
                return
                    
            # 파일 첫 줄 읽어서 모듈 식별
            first_line = ""
            try:
                with open(drop_file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    first_line = f.readline().strip()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"파일을 읽는 중 오류가 발생했습니다:\n{e}")
                return

            # 헤더에 포함된 단어를 기준으로 변경할 항목(target_key) 추정
            target_key = None

            if "ELASTODYN v5.x INPUT FILE" in first_line:
                target_key = "EDFile"                
            elif "AERODYN INPUT FILE" in first_line:
                target_key = "AeroFile"
            elif "InflowWind" in first_line:
                target_key = "InflowFile"
            elif "SERVODYN INPUT FILE" in first_line:
                target_key = "ServoFile"
            elif "HydroDyn" in first_line:
                target_key = "HydroFile"
            elif "SubDyn" in first_line:
                target_key = "SubFile"
            elif "MoorDyn" in first_line:
                target_key = "MooringFile"
            elif "BeamDyn" in first_line:
                target_key = "BDBldFile(1)"
            else:
                QMessageBox.warning(
                    self, 
                    "Warning", 
                    f"파일 헤더에서 유효한 모듈 키워드를 찾지 못했습니다.\n"
                    f"첫 줄 내용: {first_line[:40]}..."
                )
                return

            # 동일한 파일이 이미 세팅되어 있다면 스킵
            current_sub_path = OpenFastIO.current_config.get(target_key, {}).get("current", "")
            if os.path.normpath(current_sub_path) == drop_file_path:
                return

            # 사용자 확인 팝업창 (통합 실행)
            msg_box = QMessageBox(self)
            msg_box.setIcon(QMessageBox.Question)
            msg_box.setWindowTitle("🔄 Change File Warning")
            msg_box.setInformativeText(f"메인 파일 내의 [{target_key}] 경로를\n[{drop_file_path}]로 수정할까요?")
            msg_box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            msg_box.setDefaultButton(QMessageBox.No)   

            if msg_box.exec() == QMessageBox.Yes:
                # MainFST의 텍스트 내용을 찾아 새 주소로 물리 치환 및 저장
                try:
                    with open(current_main, 'r', encoding='utf-8', errors='ignore') as f:
                        lines = f.readlines()
                    
                    with open(current_main, 'w', encoding='utf-8') as f:
                        for line in lines:
                            # 동적 키 키워드(EDFile, AeroFile 등) 검사 및 치환
                            if target_key in line:
                                parts = line.split(target_key, 1)
                                # 윈도우 스타일 역슬래시 경로 탈출 문자 처리 방지를 위해 슬래시 변환 권장
                                safe_path = drop_file_path.replace("\\", "/")
                                line = f'"{safe_path}"   {target_key}{parts[1]}'
                            f.write(line)

                except Exception as e:
                    QMessageBox.critical(self, "Error", f"메인 설정을 수정하는 중 오류가 발생했습니다:\n{e}")
                    return
                
                # 변경사항을 메모리(current_config)에 동적 반영하고 새로고침
                if target_key in OpenFastIO.current_config:
                    OpenFastIO.current_config[target_key]["current"] = drop_file_path                    
                
                OpenFastIO.current_config = OpenFastIO.read_file(current_main, OpenFastIO.current_config)
                self.model_tree_update(current_main)

#=================================================================================================================================================================================================


    def model_tree_update(self, fst_file_paths):
        """ 우측 model_tree 창에 1개 또는 2개의 OpenFAST 파일 구조 정보를 표시 """
        self.model_tree_model.clear()

        # 만약 문자열(단일 경로)이 들어왔다면 리스트로 감싸서 통일성 유지
        if isinstance(fst_file_paths, str):
            fst_file_paths = [fst_file_paths] if fst_file_paths else []
            
        if not fst_file_paths:
            self.model_tree_displayed_files = []
            self.model_tree_displayed_nodes = []
            return

        try:
            # OpenFastIO에서 계층 데이터 구조 가져오기
            tree_data_list = OpenFastIO.get_model_tree_data(fst_file_paths)
        except Exception as e:
            self.cmd_output.append(f"❌ 모델 트리 데이터 생성 실패: {str(e)}\n")
            return

        # 데이터 구조를 QStandardItemModel로 렌더링 (루트별 고유 ID 부여)
        for i, tree_data in enumerate(tree_data_list):
            self._render_tree_node(tree_data, self.model_tree_model, str(i))

        # 트리 펼치기
        self.model_tree.setRootIsDecorated(True)
        self.model_tree.setIndentation(20)
        for i in range(self.model_tree_model.rowCount()):
            root_index = self.model_tree_model.index(i, 0)
            if root_index.isValid():
                self.model_tree.setExpanded(root_index, True)

        # # 🔄 [개선] 파일 미설정 시 자동 클릭 효과 발생 → btn_run 사용 가능한 상태로 전환
        # self._model_tree_auto_select()

        # 🔄 [개선] 표시 기준을 dir_tree 의 displayed_files 로 통일
        #    (이전 model_tree_displayed_files 가 남아 있으면 새 트리에 옛 파일이 계속 하이라이트된다)
        self.model_tree_displayed_files = [p for p in fst_file_paths if p]
        self.model_tree_displayed_nodes = []      # 트리가 새로 그려졌으므로 노드 ID 선택은 초기화

        # 선택된 파일들 하이라이트 재적용
        self._update_model_tree_highlight()

    def _render_tree_node(self, node_data: dict, parent_item, uid_prefix="0"):
        """ 재귀적으로 트리 노드 렌더링
            uid_prefix : 노드 고유 ID(부모 경로 + 자식 인덱스).
                         같은 파일을 가리키는 여러 노드(BldFile(1..3) 가 한 파일 등)를 구분하는 키. """

        # 노드 생성
        is_root = node_data.get("is_root", False)
        if is_root:
            display_text = f"📜 {node_data['name']}"
        else:
            display_text = f"📝 {node_data['name']} : {node_data['path']}"

        item = QStandardItem(display_text)
        item.setEditable(False)
        item.setData(node_data['path'], Qt.UserRole)
        item.setData(bool(is_root), Qt.UserRole + 1)   # 루트 표시용 (하이라이트 리셋 시 굵게 유지)
        item.setData(uid_prefix, Qt.UserRole + 2)      # 노드 고유 ID (선택 판정용)

        if is_root:
            item.setFont(self._safe_font(item, True))

        parent_item.appendRow(item)

        # 자식 노드들 재귀 처리
        for i, child in enumerate(node_data.get("children", [])):
            self._render_tree_node(child, item, f"{uid_prefix}.{i}")

    @staticmethod
    def _get_node_uid(index):
        """ 인덱스에 해당하는 model_tree 노드의 고유 ID 추출 """
        if not index or not index.isValid():
            return ""
        it = index.model().itemFromIndex(index) if hasattr(index, 'model') else None
        return (it.data(Qt.UserRole + 2) or "") if it else ""

    def _get_clicked_file_path(self, index):
        """트리 아이템 인덱스로부터 유효한 파일 경로를 추출하는 공통 함수"""
        if not index or not index.isValid():
            return None
            
        item = self.model_tree_model.itemFromIndex(index)
        if not item:
            return None
            
        # 데이터를 안전하게 문자열로 반환 (없으면 None)
        return item.data(Qt.UserRole)

    @staticmethod
    def _safe_font(base, bold=False):
        """ pointSize() <= 0 인 폰트를 그대로 setFont() 에 넘기지 않도록 보정해 반환한다.
            QSS(px 단위)로 폰트를 지정한 위젯/아이템은 pointSize() 가 -1 이고,
            QStandardItem.font() 은 폰트 데이터가 없으면 기본 QFont(=pointSize -1) 를 돌려준다.
            이 값을 item.setFont() 에 넣으면 Qt 내부 폴리시 중
            'QFont::setPointSize: Point size <= 0 (-1)' 경고가 발생한다.
            pixelSize 가 있으면 96dpi 기준 등가 point 로 환산하므로 실제 표시 크기는 변하지 않는다.

            base : QFont / QWidget(QStandardItem 포함) 아무 것이나 전달 가능 """
        # QStandardItem/QTreeWidgetItem 은 font() 를 통해, QFont/위젯 은 그대로 복사
        font = QFont(base.font()) if hasattr(base, 'font') else QFont(base)
        font.setBold(bold)

        if font.pointSize() <= 0:
            pixel = font.pixelSize()
            if pixel > 0:
                # QSS(px)로 지정된 폰트 → 96dpi 기준 등가 point 로 환산해 표시 크기를 그대로 유지
                font.setPointSizeF(pixel * 72.0 / 96.0)
            else:
                fallback = QApplication.font().pointSize()
                font.setPointSizeF(fallback if fallback > 0 else 9)

        return font

    def model_tree_press_event(self, event):
        """ 마우스 클릭 시 클릭한 위치와 항목을 기억하는 함수 """
        if event.button() == Qt.LeftButton:
            self._drag_start_position = event.position().toPoint()
        # 원래 QTreeView의 기본 마우스 클릭 동작도 함께 수행합니다.
        QTreeView.mousePressEvent(self.model_tree, event)

    def model_tree_move_event(self, event):
        """ 마우스를 누른 채 일정 거리 이상 움직이면 외부로 드래그를 시작하는 함수 """
        if not (event.buttons() & Qt.LeftButton):
            return
        current_pos = event.position().toPoint()
        if (current_pos - self._drag_start_position).manhattanLength() < QApplication.startDragDistance():
            return

        # 현재 마우스로 붙잡은 트리 아이템 가져오기
        index = self.model_tree.indexAt(current_pos)
        if not index.isValid():
            return

        item = self.model_tree_model.itemFromIndex(index)

        # 실제 파일 경로만 분리해냅니다. (렌더링 시 Qt.UserRole에 저장됨)
        file_path = item.data(Qt.UserRole) or ""

        # 실제 컴퓨터에 존재하는 파일인 경우에만 드래그를 시작합니다.
        if file_path and os.path.exists(file_path):
            from PySide6.QtCore import QMimeData, QUrl
            from PySide6.QtGui import QDrag

            # 윈도우 OS 시스템에 파일 경로 데이터 등록 (가장 중요)
            mime_data = QMimeData()
            mime_data.setUrls([QUrl.fromLocalFile(file_path)])

            drag = QDrag(self.model_tree)
            drag.setMimeData(mime_data)

            from PySide6.QtWidgets import QStyle
            # 시스템 표준 파일 아이콘을 큼직한 크기 (48x48)로 가져와 마우스에 붙임
            pixmap = self.model_tree.style().standardIcon(QStyle.SP_FileIcon).pixmap(48, 48)
            drag.setPixmap(pixmap)

            # 드래그 시 마우스 커서 모양을 복사(Copy) 형태로 지정하여 수행
            drag.exec(Qt.CopyAction)

    def model_tree_item_double_clicked(self, index):
        """ 트리 항목을 더블 클릭했을 때 Notepad++로 파일을 여는 함수 """
        clicked_file_path = self._get_clicked_file_path(index)

        print(f"double click item = {clicked_file_path}")

        npp_path = r"C:\Program Files\Notepad++\notepad++.exe"

        if os.path.exists(clicked_file_path):
            try:
                subprocess.Popen([npp_path, clicked_file_path])
            except FileNotFoundError:
                subprocess.Popen(["notepad.exe", clicked_file_path])
        else:
            QMessageBox.warning(self, "Error", "Files is not found & Please check whether the file exist.")

    def _select_file(self, file_path, ctrl=False, uid=""):
        """ 노드를 선택 상태로 만드는 단일 진입점 (마우스 클릭 / 자동 선택 공용)
            uid : 노드 고유 ID. 같은 파일을 가리키는 다른 노드(BldFile(1..3) 가 한 파일 등)와
                  경로만으로 구분되지 않게 해 클릭한 노드 하나만 하이라이트되게 한다. """
        if not file_path:
            return False

        # 궤적 추적용 리스트가 클래스에 없다면 안전하게 생성
        if not hasattr(self, 'model_tree_displayed_files'):
            self.model_tree_displayed_files = []
        if not hasattr(self, 'model_tree_displayed_nodes'):
            self.model_tree_displayed_nodes = []

        pairs = list(self.model_tree_displayed_nodes)      # [(uid, path), ...]
        pair = (uid, file_path)

        if ctrl:
            # 조건 : 처음에 아무것도 표시되지 않은 상태였다면 -> 그냥 클릭한 노드만 표시
            if not pairs:
                pairs = [pair]
                print(f"[ACTION] [ModelTree Ctrl + Click] 처음 상태 -> {file_path} 단독 추가")

            # 조건 : 이미 2개의 노드가 표시되어 있는 상태라면 -> 두번째 노드를 새 노드로 교체
            elif len(pairs) >= 2:
                print(f"[ACTION] [ModelTree Ctrl + Click] 2개 포화 상태 -> 두번째 노드({pairs[1][1]})을 {file_path}로 교체")
                pairs[1] = pair

            # 그 외 (이미 1개만 표시되어 있던 상태) -> 뒤에 추가하여 2개로 만듦
            elif pair not in pairs:
                pairs.append(pair)
                print(f"[ACTION] [ModelTree Ctrl + Click] 두번째 노드 추가 -> {file_path}")

        # 그냥 클릭한 경우 (Ctrl 없이 일반 클릭)
        else:
            print(f"model_tree_selected with {file_path} (uid={uid})")
            pairs = [pair]

        self.model_tree_displayed_nodes = pairs

        # 실행/병합 비교가 참조하는 경로 리스트 (같은 파일은 1개로 유지)
        ordered, seen = [], set()
        for _, p in pairs:
            key = p.lower()
            if key not in seen:
                seen.add(key)
                ordered.append(p)
        self.model_tree_displayed_files = ordered

        # UI 하이라이트 업데이트
        self._update_model_tree_highlight()
        return True

    def model_tree_clicked(self, index):
        """ 우측 model_tree에서 마우스 클릭 시 파일 선택 추적 (Ctrl+클릭으로 다중 선택 지원) """
        clicked_file_path = self._get_clicked_file_path(index)
        if not clicked_file_path:
            return          # 경로가 없는 그룹 노드(Linearization/bins/vizs) 등은 선택 무시

        ctrl = bool(QApplication.keyboardModifiers() & Qt.ControlModifier)
        self._select_file(clicked_file_path, ctrl=ctrl, uid=self._get_node_uid(index))

    # def _model_tree_auto_select(self, row=0, force=False):
    #     """
    #     model_tree 갱신 시 자동으로 '클릭된 효과'를 발생시킨다.
    #     → model_tree_displayed_files 등록 + 하이라이트 + btn_run 사용 가능 상태

    #     force=False 이면 이미 선택된 파일이 있을 때 건드리지 않아
    #     드래그&드롭 / 리로드로 트리가 갱신되어도 사용자 선택이 초기화되지 않는다.
    #     """
    #     if not force and getattr(self, 'model_tree_displayed_files', None):
    #         return False

    #     idx = self.model_tree_model.index(row, 0)
    #     if not idx.isValid():
    #         return False

    #     self.model_tree.setCurrentIndex(idx)     # 네이티브 선택 표시(파란색)
    #     self.model_tree.scrollTo(idx)            # 스크롤 자동 이동
    #     self.model_tree_clicked(idx)             # 클릭과 동일한 효과
    #     return True

    def _update_model_tree_highlight(self):
        """ model_tree 표시 대상 파일들 하이라이트 업데이트 """
        displayed = getattr(self, 'model_tree_displayed_files', None)
        if not displayed:
            displayed = []
        self.model_tree_displayed_files = displayed

        for row in range(self.model_tree_model.rowCount()):
            root_item = self.model_tree_model.item(row)
            if not root_item:
                continue
            self._update_item_highlight_recursive(root_item)

    def _update_item_highlight_recursive(self, item):
        """ 재귀적으로 트리 아이템 하이라이트 업데이트 """
        if not item:
            return

        item_path = item.data(Qt.UserRole) or ""
        is_root = bool(item.data(Qt.UserRole + 1))
        uid = item.data(Qt.UserRole + 2) or ""

        pairs = getattr(self, 'model_tree_displayed_nodes', []) or []

        if pairs:
            # 노드 ID 로 판정 → 같은 파일을 가리키는 다른 노드가 함께 칠해지지 않는다
            is_selected = any(u == uid for u, _ in pairs)
        else:
            # ID 선택이 없으면(좌측 dir_tree 로 트리가 갱신된 경우) 경로로 판정
            is_selected = bool(item_path) and any(
                df and item_path.lower() == df.lower() for df in self.model_tree_displayed_files
            )

        if is_selected:
            item.setBackground(QBrush(QColor("#D1D5DB")))
            item.setForeground(QBrush(QColor("#374151")))
            item.setFont(self._safe_font(item, True))
        else:
            # QBrush() = 역할 자체 해제 → QSS/기본 렌더링으로 복귀한다.
            # QBrush(Qt.transparent) 를 심으면 selection 색과 합성되어 클릭한 줄과 구분되지 않는다.
            item.setBackground(QBrush())
            item.setForeground(QBrush())
            item.setFont(self._safe_font(item, is_root))   # 루트 굵게는 유지

        # 자식 아이템들도 재귀적으로 처리
        for row in range(item.rowCount()):
            child = item.child(row)
            if child:
                self._update_item_highlight_recursive(child)

    def model_tree_item_right_clicked(self, pos):
        # 현재 마우스 우클릭을 한 주소의 트리 아이템 인덱스 가져오기
        if not hasattr(self, 'model_tree') or self.model_tree is None:
            return

        index = self.model_tree.indexAt(pos)
        if not index.isValid():
            return # 빈 바탕을 눌렀다면 메뉴를 띄우지 않고 취소

        menu = QMenu(self)
 
        # 마우스 우클릭 시 띄워줄 저장 옵션 액션(메뉴 아이템) 선언
        reload_model_tree        = QAction("📜🔄 relead .fst file", self)
        open_directory_action    = QAction("📁 Open Directory", self)
        export_text_action       = QAction("📋 파일 절대 경로 텍스트 복사", self)
        save_project_action      = QAction("💾 Project Files Deep 복사/저장하기", self)
        save_runfile_action      = QAction("💾 Project Files Soft 복사/저장하기", self)
        save_as_action           = QAction("📝 다른 이름으로 저장하기...", self)
        compare_action           = QAction("🔀 Compare Two Files (Merger)", self)
        run_openfast_action      = QAction("▶️ OpenFAST 실행하기", self)
        run_linearization_action = QAction("▶️ Linearization 실행하기", self)
        run_multi_case_action    = QAction("▶️ Multi-Case 실행하기", self)

        menu.addAction(reload_model_tree)
        menu.addAction(open_directory_action)
        menu.addAction(export_text_action)
        menu.addSeparator() # Separator line     
        menu.addAction(save_project_action)
        menu.addAction(save_runfile_action)
        menu.addAction(save_as_action)
        menu.addSeparator() # Separator line 
        menu.addAction(compare_action)
        menu.addSeparator() # Separator line
        menu.addAction(run_openfast_action)
        menu.addAction(run_linearization_action)
        menu.addAction(run_multi_case_action)

        reload_model_tree.triggered.connect(       lambda: self.mouse_Rclick_reload_model_tree(index))
        open_directory_action.triggered.connect(   lambda: self.mouse_Rclick_open_directory(index))
        save_project_action.triggered.connect(     lambda: self.mouse_Rclick_save_project_hard(index))
        save_runfile_action.triggered.connect(     lambda: self.mouse_Rclick_save_project_soft(index))       
        save_as_action.triggered.connect(          lambda: self.mouse_Rclick_save_file(index))
        export_text_action.triggered.connect(      lambda: print(f"[선택] 절대 경로 복사 target: {self._get_clicked_file_path(index)}"))
        compare_action.triggered.connect(          lambda: self.mouse_Rclick_compare_files())
        run_openfast_action.triggered.connect(     lambda: self.mouse_Rclick_run_openfast(index))
        run_linearization_action.triggered.connect(lambda: self.mouse_Rclick_run_linearization(index))
        run_multi_case_action.triggered.connect(   lambda: self.mouse_Rclick_run_multi_case(index))
        
        menu.exec(self.model_tree.mapToGlobal(pos))  # 마우스가 클릭된 전역 좌표(화면 기준 주소)에 메뉴판 오픈

    def mouse_Rclick_open_directory(self, index):
        """ 우클릭 메뉴에서 'Open Directory'를 선택했을 때 실제 폴더를 열어주는 함수 """
        clicked_file_path = self._get_clicked_file_path(index)
        if not clicked_file_path or not os.path.isabs(str(clicked_file_path)):
            return      # 경로가 없는 그룹 노드(Linearization/bins/vizs)는 조용히 무시

        dir_path = clicked_file_path if os.path.isdir(clicked_file_path) else os.path.dirname(clicked_file_path)

        self.cmd_output.append(f"📂 폴더 열기: {dir_path}\n")
        print(f"mouse_Rclick_open_directory dir_path = {dir_path}")

        if not os.path.isdir(dir_path):
            QMessageBox.warning(self, "Warning", f"No directory path was found!\n\n경로: {dir_path}")
            return

        try:
            os.startfile(dir_path, "explore")     # 폴더 → 탐색기로 열기
        except OSError as e:
            QMessageBox.critical(self, "Error", f"Can't open directory!\n\nReason: {e}")

    def mouse_Rclick_save_project_hard(self, index):
        "Save project files to new folder"
         
        main_fst_path = OpenFastIO.current_config.get("MainFST", {}).get("current")
        if not main_fst_path:
            QMessageBox.critical(self, "Error", "로드된 OpenFAST 설정 파일이 없습니다.")
            return

       # 제안할 폴더 명칭 및 부모 디렉토리 추출
        today_str = datetime.now().strftime("%Y%m%d")
        default_folder_name = f"New_OpenFAST_Project_{today_str}"
        base_dir = os.path.dirname(main_fst_path)

        # dialog = QFileDialog(self)
        # dialog.setWindowTitle("📁 새 프로젝트 폴더 위치 선택 or 생성")
        # dialog.setDirectory(base_dir) 
        
        # # [핵심 수정] Directory 대신 AnyFile을 써야 존재하지 않는 새 폴더명을 타이핑해도 버튼이 활성화됩니다.
        # dialog.setFileMode(QFileDialog.AnyFile) 
        # dialog.setAcceptMode(QFileDialog.AcceptSave)       
        
        # dialog.setOption(QFileDialog.DontUseNativeDialog, True) 
        # dialog.setLabelText(QFileDialog.Accept, "Choose")
        # dialog.selectFile(default_folder_name)

        dialog = QFileDialog(self)
        dialog.setWindowTitle("📁 새 프로젝트 폴더 위치 선택")
        dialog.setDirectory(base_dir) 
        dialog.setFileMode(QFileDialog.Directory) #(QFileDialog.AnyFile) 
        dialog.setOption(QFileDialog.DontUseNativeDialog, True) 
        dialog.setLabelText(QFileDialog.Accept, "Choose")
        dialog.selectFile(default_folder_name)

        # 유저가 글자를 입력창에 두고 Choose를 누르면 즉시 수락(accept) 처리되도록 이벤트를 바인딩
        from PySide6.QtWidgets import QDialogButtonBox, QLineEdit
        
        # 대화상자 내부의 입력창(QLineEdit)과 버튼 그룹을 찾아옵니다.
        line_edit = dialog.findChild(QLineEdit)
        button_box = dialog.findChild(QDialogButtonBox)

        if button_box:
            # 기존 Qt의 내부 연결을 끊고, 버튼 클릭 시 즉시 대화상자를 수락(Accept)하고 닫도록 강제합니다.
            try:
                button_box.accepted.disconnect()
            except:
                pass
            button_box.accepted.connect(dialog.accept)

        if line_edit:
            # 입력창에서 엔터를 쳤을 때도 내부로 들어가지 않고 즉시 창이 닫히도록 바인딩합니다.
            try:
                line_edit.returnPressed.disconnect()
            except:
                pass
            line_edit.returnPressed.connect(dialog.accept)

        # 대화상자 실행 (이제 Choose나 엔터를 누르면 무조건 즉시 닫힙니다)
        if not dialog.exec():
            return
            
        selected_files = dialog.selectedFiles()
        if not selected_files:
            return
            
        raw_target = selected_files[0]
        if raw_target == base_dir or not os.path.basename(raw_target).strip():
            target_dir = os.path.join(base_dir, default_folder_name)
        else:
            target_dir = raw_target

        print(f"👉 대화상자 즉시 탈출 완료! 생성 경로: {target_dir}")


        # [실제 디렉토리 생성 및 다음 파일 복사 프로세스로 즉시 진행]
        try:
            if not os.path.exists(target_dir):
                os.makedirs(target_dir)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"디렉토리를 생성할 수 없습니다:\n{e}")
            return
            

        # current_config를 순회하며 파일 복사 수행
        copied_files_count = 0
        failed_files = []

        # 복사 대상 목록 수집 (MainFST와 하위 모듈 파일들)
        files_to_copy = []
        
        # 메인 fst 파일 추가
        files_to_copy.append(("MainFST", main_fst_path))
        
        # 메인 파일이 위치한 절대 경로 기준점 (상대 경로 복원용)
        base_dir = os.path.dirname(main_fst_path)
        
        # 하위 모듈 파일들 수집
        for key, info in OpenFastIO.current_config.items():
            if key == "MainFST" or not isinstance(info, dict):
                continue
            
            # 값 추출 (current 우선, 없으면 default)
            raw_value = info.get("current") or info.get("default")
            if not raw_value:
                continue

            # 값의 타입에 따라 처리 분기 (리스트 vs 문자열)
            paths_to_check = []
            if isinstance(raw_value, list):
                # AFFileList 같은 가변 리스트 대응
                paths_to_check.extend(raw_value)
            elif isinstance(raw_value, str):
                # 일반 문자열 경로 대응
                paths_to_check.append(raw_value)
            else:
                continue

            # 수집된 경로 검증 및 절대 경로 변환
            for path_item in paths_to_check:
                if not isinstance(path_item, str) or not path_item.strip():
                    continue
                
                # "0", "600.0", "1" 등 단순 수치나 설정값은 파일 경로에서 제외
                if path_item.strip() in ["0", "1", "2", "3"] or path_item.replace('.', '', 1).isdigit():
                    continue
                
                # 확장자가 없는 순수 옵션 값 필터링 (.dat, .txt, .dll, .fst 등 파일 형태만 인정)
                if '.' not in os.path.basename(path_item):
                    continue

                # 절대 경로로 변환 (상대 경로 파일명일 경우 base_dir와 결합)
                if not os.path.isabs(path_item):
                    resolved_path = os.path.normpath(os.path.join(base_dir, path_item))
                else:
                    resolved_path = os.path.normpath(path_item)

                # 실제 디스크에 존재하는 파일만 수집
                if os.path.exists(resolved_path) and os.path.isfile(resolved_path):
                    if (key, resolved_path) not in files_to_copy:
                        files_to_copy.append((key, resolved_path))

         # 실제 파일 복사 가동 (상위 디렉토리가 다를 경우 공통 조상 구조 유지 버전)
        if files_to_copy:
            # 1. 수집된 모든 파일들의 원본 경로 목록 추출
            all_paths = [origin_path for _, origin_path in files_to_copy]
            
            # 2. 모든 파일이 공유하는 가장 공통된 부모 디렉토리(상위 경로)를 찾습니다.
            # 예: "C:/Project/A/Main.fst"와 "C:/Project/B/HydroData/HydroDyn.dat"가 있으면
            # 공통 분모인 "C:/Project"를 자동으로 찾아냅니다.
            common_root = os.path.commonpath(all_paths)
            
            # 만약 공통 경로가 드라이브 루트(C:\)이거나 비어있다면 메인 파일 폴더를 기준으로 설정 (안전 장치)
            if common_root == os.path.abspath(os.path.splitdrive(main_fst_path)[0] + os.sep):
                common_root = base_dir

            print(f"🔍 계산된 공통 상위 경로(Common Root): {common_root}")

            for key, origin_path in files_to_copy:
                try:
                    # 3. 공통 상위 경로를 기준으로 한 상대 경로를 계산합니다.
                    # 예: "C:/Project/A/Main.fst" -> "A/Main.fst"
                    # 예: "C:/Project/B/HydroData/HydroDyn.dat" -> "B/HydroData/HydroDyn.dat"
                    try:
                        relative_path = os.path.relpath(origin_path, common_root)
                    except ValueError:
                        # 드라이브가 아예 다른 경우(C드라이브 vs D드라이브)에는 경로 분리가 안 되므로 파일명만 사용
                        relative_path = os.path.basename(origin_path)
                    
                    # 4. 사용자가 지정한 새 저장 위치(target_dir)와 상대 경로를 결합합니다.
                    # 예: "C:/Project/C/" + "A/Main.fst" -> "C:/Project/C/A/Main.fst"
                    # 예: "C:/Project/C/" + "B/HydroData/HydroDyn.dat" -> "C:/Project/C/B/HydroData/HydroDyn.dat"
                    destination_path = os.path.join(target_dir, relative_path)
                    
                    # 5. 복사할 하위 디렉토리가 새 폴더 내에 없다면 자동으로 트리 생성
                    dest_subdir = os.path.dirname(destination_path)
                    if not os.path.exists(dest_subdir):
                        os.makedirs(dest_subdir)
                    
                    # 6. 파일 원본 메타데이터(수정일 등)를 포함하여 물리 복사
                    shutil.copy2(origin_path, destination_path)
                    copied_files_count += 1
                    
                except Exception as e:
                    failed_files.append(f"{os.path.basename(origin_path)} ({e})")

        # 결과 알림 팝업
        if failed_files:
            summary = "\n".join(failed_files)
            QMessageBox.warning(
                self, 
                "Warning", 
                f"{copied_files_count}개 파일 복사 완료.\n\n⚠️ 일부 파일 복사 실패:\n{summary}"
            )
        else:
            QMessageBox.information(
                self, 
                "Success", 
                f"총 {copied_files_count}개의 프로젝트 파일이\n[{target_dir}] 폴더로 안전하게 저장되었습니다!"
            )

    def mouse_Rclick_save_project_soft(self, index):
        """ 소프트 카피: 새로운 .fst 파일을 입력받고, 연결된 모든 하위 파일들을 동일 디렉토리에 복사 및 치환 후 리로드 """
        # 0. 현재 로드된 메인 fst 경로 확보
        main_fst_path = OpenFastIO.current_config.get("MainFST", {}).get("current")
        if not main_fst_path or not os.path.exists(main_fst_path):
            QMessageBox.critical(self, "Error", "로드된 OpenFAST 설정 파일이 없습니다.")
            return

        current_fst_dir = os.path.dirname(os.path.abspath(main_fst_path))
        old_fst_name = os.path.basename(main_fst_path)
        old_fst_base, _ = os.path.splitext(old_fst_name)

        # 1. 유저에게 새 .fst 파일 저장 경로 및 파일명 입력 받기 (디렉토리 선택 가능)
        today_str = datetime.now().strftime("%Y%m%d")
        default_new_fst = f"{old_fst_base}_{today_str}.fst"
        default_full_path = os.path.join(current_fst_dir, default_new_fst)
        
        file_path_selected, _ = QFileDialog.getSaveFileName(
            self,
            "📄 새 메인 파일 저장 위치 및 이름 선택",
            default_full_path,                # 초기 탐색 디렉토리 및 기본 파일명 지정
            "OpenFAST 설정 파일 (*.fst)"        # 파일 포맷 필터
        )
        
        # 취소 버튼을 누르거나 창을 닫은 경우 종료
        if not file_path_selected.strip():
            return

        # 선택된 전체 경로를 기반으로 변수들 재정의
        final_new_fst_path = os.path.normpath(file_path_selected)
        new_fst_name = os.path.basename(final_new_fst_path)
        new_fst_base, _ = os.path.splitext(new_fst_name)
        
        # 사용자가 메인 .fst 파일을 다른 디렉토리로 선택했을 수 있으므로 하위 파일들이 복사될 타겟 디렉토리를 사용자가 선택한 새 폴더 경로로 업데이트합니다.
        current_fst_dir = os.path.dirname(final_new_fst_path)

        # 기존 파일과 경로/이름이 완벽히 같으면 덮어쓰기 방지를 위해 종료
        if os.path.abspath(final_new_fst_path).lower() == os.path.abspath(main_fst_path).lower():
            QMessageBox.warning(self, "이름 중복", "기존 메인 파일과 완전히 동일한 경로 및 이름입니다. 다른 이름이나 경로를 선택해주세요.")
            return

        # 2. 복사 대상 하위 파일 수집 (기존 current_config 활용)
        files_to_copy = [] # (key, 원래절대경로) 저장

        # 소프트 카피 시 고유 확장자(.ela, .aer 등)를 부여하고 물리 이사할 핵심 1차 파일 목록 정의
        soft_copy_targets = [
            "EDFile", "AeroFile", "ServoFile", "SeaStFile", "HydroFile", "MooringFile", "SubFile", "IceFile", "SoilFile", "InflowFile"
        ]        

        for key, info in OpenFastIO.current_config.items():
            # [수정] 수집 대상 Key가 소프트 카피 대상 1차 모듈 리스트에 포함되어 있는지 엄격히 체크
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
                # 숫자 파라미터 제외 가드코드
                if path_item.strip() in ["0", "1", "2", "3"] or path_item.replace('.', '', 1).isdigit():
                    continue
                if '.' not in os.path.basename(path_item):
                    continue

                if not os.path.isabs(path_item):
                    # 메인 .fst 파일이 위치한 원본 디렉토리를 기준으로 절대 경로화
                    resolved_path = os.path.normpath(os.path.join(os.path.dirname(main_fst_path), path_item))
                else:
                    resolved_path = os.path.normpath(path_item)

                if os.path.exists(resolved_path) and os.path.isfile(resolved_path):
                    if (key, resolved_path) not in files_to_copy:
                        files_to_copy.append((key, resolved_path))

        # config 템플릿의 정확한 Key 풀네임을 기준으로 고정 확장자 매핑 정의
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

        # 사용자 승인(Accept)을 위한 변경 내용 요약 및 알림창 팝업
        summary_text = (
            f"📄 새 메인 파일 경로:\n{final_new_fst_path}\n\n"
            f"📂 하위 파일 이사 및 확장자 변경 요약:\n"
        )
        for key, origin_path in files_to_copy:
            orig_name = os.path.basename(origin_path)
            key_lower = str(key).strip().lower()
            target_ext = ext_rules.get(key_lower, os.path.splitext(orig_name)[1])
            new_name = f"{new_fst_base}{target_ext}"
            summary_text += f"• [{key}] {orig_name} ──> {new_name}\n"
            
        summary_text += f"\n위 내용대로 물리 복사 및 내부 경로 치환을 진행하시겠습니까?"

        reply = QMessageBox.question(
            self,
            "프로젝트 소프트 복사 승인",
            summary_text,
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes
        )

        if reply == QMessageBox.No:
            if hasattr(self, 'cmd_output'):
                self.cmd_output.append("❌ 사용자가 프로젝트 복사 요청을 취소했습니다.\n")
            return
  

        # 3. 하위 파일들을 유저가 지정한 새 디렉토리에 새로운 이름 구조로 물리 복사 실행
        main_replace_map = {}   # 메인 fst 파일 내부 치환용 매핑 테이블
        sub_replace_map = {}    # 복사된 하위 파일 내부 치환용 매핑 테이블
        file_copy_pairs = []    # [(원래절대경로, 생성될새절대경로)] -> 물리 복사 실행용
        failed_files = []
        
        total_attempted = 0     # 총 복사 시도 횟수
        copied_count = 0        # 복사 성공 횟수

        # 1) 이름 및 '새 디렉토리 기준 절대 경로' 조립 단계
        for key, origin_path in files_to_copy:
            try:
                orig_basename = os.path.basename(origin_path)
                orig_base, orig_ext = os.path.splitext(orig_basename)
                
                key_lower = str(key).strip().lower()
                target_ext = ext_rules.get(key_lower, orig_ext)

                # 유저가 새로 지정한 폴더(current_fst_dir) 내부에 고유 파일명 결합, 예: HD_P1SS_Cd0_H20_20260711.ela 형태로 이름 빌드
                new_sub_basename = f"{new_fst_base}{target_ext}"
                destination_path = os.path.normpath(os.path.join(current_fst_dir, new_sub_basename))

                # 물리 복사 대기열 등록
                file_copy_pairs.append((origin_path, destination_path))
                total_attempted += 1

                # OpenFAST 설정 정보 추출 및 안전 다중 매핑 빌드
                raw_info = OpenFastIO.current_config.get(key, {})
                raw_text_path = raw_info.get("current") or raw_info.get("default")

                if isinstance(raw_text_path, str) and raw_text_path.strip():
                    cleaned_raw = raw_text_path.strip().strip("'\"")
                    
                    # [단순화] 원본 경로가 어떻게 적혀있든 간에 '새 순수 파일명'으로 교체하도록 등록
                    main_replace_map[cleaned_raw] = new_sub_basename
                    main_replace_map[cleaned_raw.replace("/", "\\")] = new_sub_basename
                    
                    sub_replace_map[cleaned_raw] = new_sub_basename
                    sub_replace_map[cleaned_raw.replace("/", "\\")] = new_sub_basename

                # 패턴 B 백업 가드: 오직 1차 핵심 모듈 파일일 때만 순수 파일명 단독 치환 허용
                if key_lower in ext_rules:
                    main_replace_map[orig_basename] = new_sub_basename
                    main_replace_map[orig_basename.replace("/", "\\")] = new_sub_basename

            except Exception as e:
                failed_files.append(f"{os.path.basename(origin_path)} (이름 조립 실패: {e})")

        # 2) [물리 복사 단계] 대기열에 있는 파일들을 유저가 지정한 새 디렉토리에 실제로 복사합니다. (유지)
        print("\n" + "📂"*5 + " [파일 물리 복사 진행 현황] " + "📂"*5)
        for src_path, dst_path in file_copy_pairs:
            src_name = os.path.basename(src_path)
            dst_name = os.path.basename(dst_path)
            try:
                shutil.copy2(src_path, dst_path)
                copied_count += 1
                print(f"  [성공] {src_name} ──> {os.path.dirname(dst_path)} 폴더 내 {dst_name}")
            except Exception as e:
                failed_files.append(f"{src_name} ──> {dst_name} (복사 실패: {e})")
        print("="*50 + "\n")



        # 4. 생성된 모든 파일(새 .fst 및 모든 새 하위 파일)의 내부 텍스트 전체 치환 연동
        target_files_to_modify = [final_new_fst_path] + [dst for _, dst in file_copy_pairs if os.path.exists(dst)]
        
        # 글자 수가 긴 원본 문자열 경로 패턴부터 정렬하여 변환 꼬임/치환 깨짐 방지
        sorted_main_names = sorted(main_replace_map.keys(), key=len, reverse=True)
        sorted_sub_names = sorted(sub_replace_map.keys(), key=len, reverse=True)

        # 원본 메인 fst의 내용을 복사하여 새 메인 fst 파일을 기초 생성
        try:
            with open(main_fst_path, 'r', encoding='utf-8', errors='ignore') as f:
                main_content = f.read()
            with open(final_new_fst_path, 'w', encoding='utf-8') as f:
                f.write(main_content)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"새 메인 파일 기초 생성 실패: {e}")
            return

        # 모든 대상 파일들을 순회하며 내부 텍스트 안의 모든 옛날 경로들을 새 폴더 경로로 정밀 치환
        for file_path in target_files_to_modify:
            try:
                # 현재 수정 중인 파일이 메인 .fst 인지 구분하는 가드 플래그
                is_main_fst = (os.path.abspath(file_path).lower() == os.path.abspath(final_new_fst_path).lower())

                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()

                modified = False
                
                # 파일 종류에 맞는 정밀 매핑 테이블 스위칭 체계 적용
                loop_names = sorted_main_names if is_main_fst else sorted_sub_names
                active_map = main_replace_map if is_main_fst else sub_replace_map

                if not is_main_fst:
                    current_sub_basename = os.path.basename(file_path) # 현재 수정 중인 파일명 (예: Main...aer)
                    filtered_loop_names = []
                    
                    # 현재 파일에 해당하는 원본 1차 모듈 파일명(예: AeroDyn.dat)을 추적합니다.
                    matched_orig_base = ""
                    for src, dst in file_copy_pairs:
                        if os.path.basename(dst) == current_sub_basename:
                            matched_orig_base = os.path.basename(src) # AeroDyn.dat 확보
                            break
                            
                    for name in loop_names:
                        # 검사 단어 장부에 자기 자신 모듈의 파일명이 포함되어 있다면 과감히 제외시킵니다.
                        if matched_orig_base and matched_orig_base in name:
                            continue
                        filtered_loop_names.append(name)
                    loop_names = filtered_loop_names


                for old_sub in loop_names:
                    # 빈 문자열 치환 방지 가드코드
                    if not old_sub.strip():
                        continue
                        
                    if old_sub in content:
                        new_sub = active_map[old_sub]
                        content = content.replace(old_sub, new_sub)
                        modified = True

                if modified:
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(content)

            except Exception as e:
                if hasattr(self, 'cmd_output'):
                    self.cmd_output.append(f"⚠️ 경고: {os.path.basename(file_path)} 파일 내부 치환 중 오류 발생: {e}\n")

        # 5. [핵심] 가상 엔진 데이터 동기화 및 트리뷰 자동 리로드
        try:
            if hasattr(self, 'model_tree_update') and hasattr(self, 'dir_tree_update'):
                self.model_tree_update(final_new_fst_path)
                self.dir_tree_update(final_new_fst_path) # 좌측 .fst 파일 목록 트리도 함께 새로고침
                
                # 수집된 총 개수 정의
                total_collected = len(files_to_copy)
                
                # [조건문] 수집된 개수와 실제 복사 성공한 개수가 완벽히 일치할 때 (전원 성공)
                if total_collected == copied_count:
                    QMessageBox.information(
                        self, 
                        "✨ Success", 
                        f"하이브리드 프로젝트 복사 완료!\n\n"
                        f"• 새 메인 파일: {new_fst_name}\n"
                        f"• 복사 성공: {copied_count} / {total_collected} 개\n\n"
                        f"현재 파일 트리가 새 프로젝트 세션으로 리로드되었습니다."
                    )
                # 하나라도 누락되거나 다를 때 (일부 실패 또는 예외 발생)
                else:
                    error_details = "\n".join(failed_files) if failed_files else "알 수 없는 전송 누락"
                    QMessageBox.warning(
                        self, 
                        "⚠️ Warning", 
                        f"프로젝트 복사 중 누락 발생!\n\n"
                        f"• 새 메인 파일: {new_fst_name}\n"
                        f"• 복사 성공: {copied_count} / {total_collected} 개\n\n"
                        f"일부 하위 파일 처리 중 오류가 발생했습니다:\n{error_details}"
                    )
            else:
                if hasattr(self, 'cmd_output'):
                    self.cmd_output.append("⚠️ 알림: load_fst_file 메서드를 찾을 수 없어 자동 리로드를 건너뜜.\n")
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"프로젝트 리로드 중 오류 발생: {e}")

    def mouse_Rclick_save_file(self, index):
        """ Save File with new name & update the tree path"""
        file_path_preset = self._get_clicked_file_path(index)
        if not file_path_preset:
            return

        default_dir = os.path.dirname(file_path_preset)
        default_name = os.path.basename(file_path_preset)  
        initial_path = os.path.join(default_dir, default_name)
        _, ext = os.path.splitext(default_name)

        filter_name = ext.strip('.').lower()

        # 새 파일 저장/생성 다이얼로그 띄우기 ([저장] 버튼으로 출력됨)
        final_file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Make New File with your input",
            initial_path,
            f"{filter_name} Files (*{ext});;All Files (*)",
            options=QFileDialog.Option.DontConfirmOverwrite  # 👈 시스템 경고창 팝업을 강제로 발생시키지 않는 플래그
        )

        # 유저가 취소 버튼을 누르면 프로세스 가동 없이 즉시 종료
        if not final_file_path:
            return  

        final_file_path = os.path.abspath(final_file_path) # 절대 경로 표준화
        preset_abs_path = os.path.abspath(file_path_preset)

        # 파일 변경(새로 만들기) 여부 체크 및 분기 처리
        if final_file_path == preset_abs_path:
            # 이름을 변경하지 않고 기존 파일명 그대로 저장을 눌렀을 때의 처리
            reply = QMessageBox.warning(self, "파일 이름 미변경", "기존 파일과 동일한 이름이므로 파일을 새로 만들지 않습니다." )
            return

        else:
            # 새로운 파일명이 입력되었을 때 -> 트리뷰 구조를 새 파일 이름으로 자동 갱신 및 저장
            try:
                if os.path.exists(preset_abs_path) and not os.path.exists(final_file_path):
                    import shutil
                    shutil.copy(preset_abs_path, final_file_path) # 기존 뼈대 파일 복사 생성
            except Exception as e:
                self.cmd_output.append(f"⚠️ 새 파일 물리 생성 중 알림: {e}\n")

            if final_file_path.lower().endswith('.fst'):
                if hasattr(self, 'load_fst_file'):
                    self.load_fst_file(final_file_path)
                    self.cmd_output.append(f"✨ 새로운 세션이 생성되고 파일트리 업데이트 되었습니다: {os.path.basename(final_file_path)}")
            else :
                # file layer -> Update .fst -> reload tree a.t. Upated .fst
                try:
                    # 현재 GUI에 로드된 메인 (.fst) 파일 경로 가져오기
                    fst_path = OpenFastIO.current_config.get("MainFST", {}).get("current")
                    if not fst_path:
                        QMessageBox.critical(self, "Error", "로드된 OpenFAST 설정 파일이 없습니다.")
                        return

                    if not fst_path or not os.path.exists(fst_path):
                        # 만약 변수가 없다면 이미지 구조에 따라 Main 노드의 텍스트 등에서 파싱하는 로직이 필요합니다.
                        self.cmd_output.append("⚠️ 오류: 업데이트할 메인 (.fst) 파일 경로를 찾을 수 없습니다.\n")
                        return

                    # 메인 (.fst) 파일 내부 텍스트 읽기
                    with open(fst_path, 'r', encoding='utf-8', errors='ignore') as f:
                        lines = f.readlines()

                    # .fst 내용 중 기존 하위 파일 경로(상대경로 또는 파일명)를 새 파일 경로로 교체
                    # OpenFAST 파일 특성상 상대 경로 처리를 위해 basename 위주로 매칭하거나 전체 경로 매칭을 시도합니다.
                    old_name = os.path.basename(file_path_preset)
                    new_name = os.path.basename(final_file_path)
                    
                    updated = False
                    new_lines = []
                    for line in lines:
                        # 기존 파일명이 포함된 라인이 있다면 새 파일명으로 교체 (따옴표 고려)
                        if old_name in line:
                            line = line.replace(old_name, new_name)
                            updated = True
                        new_lines.append(line)

                    # 변경된 내용을 메인 (.fst) 파일에 다시 저장
                    if updated:
                        with open(fst_path, 'w', encoding='utf-8') as f:
                            f.writelines(new_lines)
                        self.cmd_output.append(f"📝 메인 파일({os.path.basename(fst_path)}) 내부의 경로가 업데이트 되었습니다.")
                    else:
                        self.cmd_output.append("⚠️ 알림: 메인 파일 내부에서 기존 파일의 레퍼런스를 찾지 못했습니다.")

                    # 변경된 메인 (.fst) 파일을 다시 불러와 트리뷰 전체 리로드
                    if hasattr(self, 'load_fst_file'):
                        self.load_fst_file(fst_path)
                        self.cmd_output.append(f"🔄 하위 파일 변경에 따라 파일트리가 재동기화 되었습니다: {new_name}")
                        
                except Exception as e:
                    self.cmd_output.append(f"⚠️ 하위 파일 링크 업데이트 중 오류 발생: {e}\n")

    def mouse_Rclick_run_linearization(self, index):
        """ 우클릭 메뉴에서 'Linearization'를 선택 시 모달리스창 띄우기 (로직은 linearization_tab.py) """
        clicked_file_path = self._get_clicked_file_path(index)

        from src.ui.tabs_input.linearization_tab import LinearizationWindow
        LinearizationWindow.show_window(self, clicked_file_path)

    def mouse_Rclick_run_multi_case(self, index):
        """ [우클릭] '다중 케이스 실행' 선택 시 모달리스 설정 창을 띄웁니다. (로직은 multi_tab.py) """
        clicked_file_path = self._get_clicked_file_path(index)
        
        from src.ui.tabs_input.multi_tab import MultiCaseRunWindow

        # # main_window의 자식 위젯들을 순회하며 MultiCaseRunWindow 인스턴스를 찾습니다.
        # for widget in self.main_window.findChildren(QDialog):
        #     if isinstance(widget, MultiCaseRunWindow) and widget.isVisible():
        #         widget.activateWindow()
        #         widget.raise_()
        #         return

        MultiCaseRunWindow.show_window(self, clicked_file_path)

    def mouse_Rclick_run_openfast(self, index):
        """ model_tree에서 openfast 실행시키기 """
        clicked_file_path = self._get_clicked_file_path(index)
        if not clicked_file_path:
            return

        if not os.path.exists(clicked_file_path) or not clicked_file_path.lower().endswith('.fst'):
            QMessageBox.warning(self, "파일 오류", f"유효한 .fst 파일을 찾을 수 없습니다.\n경로: {clicked_file_path}")
            return

        for i in range(self.process_tree.topLevelItemCount()):
            item = self.process_tree.topLevelItem(i)
            if item and item.data(0, Qt.UserRole) == clicked_file_path:
                status = item.data(1, Qt.UserRole)
                if status in [PROCESS_TREE_STATUS_PENDING, PROCESS_TREE_STATUS_RUNNING]:
                    QMessageBox.information(self, "알림", "선택한 파일은 이미 실행 대기 중이거나 실행 중입니다.")
                    return

        self.process_tree_add_to_pending(clicked_file_path)
        print(f"✅ [Run Queue] '{os.path.basename(clicked_file_path)}' 파일이 실행 대기열에 추가되었습니다.")

    def mouse_Rclick_reload_model_tree(self, index):
        """ model_tree update when change the file in external fila like as notepad """
        clicked_file_path = self._get_clicked_file_path(index)

        main_fst_path = OpenFastIO.current_config.get("MainFST", {}).get("current")
        if not main_fst_path:
            QMessageBox.critical(self, "Error", "로드된 OpenFAST 설정 파일이 없습니다.")
            return

        self.model_tree_update(main_fst_path)

    def mouse_Rclick_compare_files(self):
        """ 선택된 두 파일을 Merger로 비교 """
        if not hasattr(self, 'model_tree_displayed_files') or len(self.model_tree_displayed_files) < 2:
            QMessageBox.warning(self, "비교 불가", "비교할 파일이 2개 선택되지 않았습니다.\nCtrl+클릭으로 두 파일을 선택하세요.")
            return

        file1 = self.model_tree_displayed_files[0]
        file2 = self.model_tree_displayed_files[1]

        if not os.path.exists(file1) or not os.path.exists(file2):
            QMessageBox.critical(self, "오류", "선택된 파일 중 하나가 존재하지 않습니다.")
            return

        # Merger 실행 파일 경로 가져오기 (기본값: C:\Program Files\Merger\Merger.exe)
        merger_path = r'C:\Program Files\WinMerge\WinMergeU.exe'

        if not os.path.exists(merger_path):
            QMessageBox.critical(self, "Merger 없음", f"Merger 실행 파일을 찾을 수 없습니다.\n기본 경로: {merger_path}\n\n설정에서 경로를 지정해주세요.")
            return

        try:
            # Merger 실행: merger.exe file1 file2
            subprocess.Popen([merger_path, file1, file2])
            print(f"[COMPARE] Merger 실행: {file1} <-> {file2}")
        except Exception as e:
            QMessageBox.critical(self, "실행 오류", f"Merger 실행 중 오류 발생:\n{e}")

#=================================================================================================================================================================================================


    def btn_left_run_clicked(self, checked=False):
        """선택된 .fst 파일 → process_tree_add_to_pending 호출 (Error 파일 재실행 가능)"""
        selected = self.dir_tree.selectedIndexes()
        if not selected:
            print("[Run] 선택된 항목이 없습니다.")
            return
        
        # 중복 방지: 이미 런예정/런중에 있는 파일은 추가 안 함, Error/완료 상태인 파일은 제거 후 재실행 가능
        existing_paths = set()
        error_items = {}  # {file_path: item} - 재실행 가능한 Error 상태 항목
        
        for i in range(self.process_tree.topLevelItemCount()):
            item = self.process_tree.topLevelItem(i)
            if item:
                file_path = item.data(0, Qt.UserRole)
                existing_paths.add(file_path)
                
                # Error 상태인 항목은 재실행을 위해 보관
                item_status = item.data(1, Qt.UserRole)
                if item_status in [PROCESS_TREE_STATUS_ERROR, PROCESS_TREE_STATUS_COMPLETED]:
                    error_items[file_path] = item
        
        for index in selected:
            item = self.dir_tree_model.itemFromIndex(index)
            if not item:
                continue
            file_path = item.data(Qt.UserRole)
            
            # 🔄 Error/Completed 상태면 기존 항목 제거 후 재실행
            if file_path in existing_paths and file_path in error_items:
                old_item = error_items[file_path]
                row = self.process_tree.indexOfTopLevelItem(old_item)
                if row != -1:
                    self.process_tree.takeTopLevelItem(row)  # 기존 Error 아이템 제거
                
                # 큐에서도 제거
                if file_path in self.process_tree_run_queue["completed"]:
                    self.process_tree_run_queue["completed"] = [
                        x for x in self.process_tree_run_queue["completed"] 
                        if x.get("path") != file_path
                    ]
                
                # 🟢 새로 pending 추가 → 자동 실행 시작
                self.process_tree_add_to_pending(file_path)
                continue
            
            # 일반 중복 방지
            if file_path in existing_paths:
                continue  # 런예정/런중 상태면 스킵
            
            # 런예정에 추가
            self.process_tree_add_to_pending(file_path)

    def process_tree_add_to_pending(self, file_path):
        """런예정 리스트에 항목 추가 → 즉시 실행 가능 여부 확인"""
        item = QTreeWidgetItem([os.path.basename(file_path), "pending", "", ""])
        item.setData(0, Qt.UserRole, file_path)
        item.setData(1, Qt.UserRole, PROCESS_TREE_STATUS_PENDING)
        self.process_tree_apply_status_style(item, PROCESS_TREE_STATUS_PENDING)
        
        self.process_tree.addTopLevelItem(item)
        self.process_tree_run_queue["pending"].append(file_path)
        
        # 실행 가능 여부 확인 후 즉시 시작
        self.process_tree_try_start_next()

    def process_tree_try_start_next(self):
        """running process 개수 확인 → 설정 이하이면 런예정에서 실행 시작"""
        running_count = len(self.process_tree_run_queue["running"])
        
        while running_count < self.process_tree_max_concurrent:
            if not self.process_tree_run_queue["pending"]:
                break
            
            file_path = self.process_tree_run_queue["pending"].pop(0)
            
            # QTreeWidgetItem 찾기
            item = self.process_tree_find_item_by_path(file_path)
            if item:
                self.process_tree_move_to_running(item, file_path)
                running_count += 1

    def process_tree_move_to_running(self, item, file_path):
        """런예정 → 런중으로 이동 및 OpenFAST 실행"""
        start_time = datetime.now().strftime("%H:%M:%S")
        item.setText(2, start_time)
        item.setData(1, Qt.UserRole, PROCESS_TREE_STATUS_RUNNING)
        self.process_tree_apply_status_style(item, PROCESS_TREE_STATUS_RUNNING)
        
        self.process_tree_run_queue["running"].append(file_path)
        
        # 자동으로 첫 번째 런중 파일의 로그 보기
        if not getattr(self, 'current_viewing_path', ''):
            self.current_viewing_path = file_path
            if hasattr(self, 'cmd_output'):
                self.cmd_output.clear()
                self.cmd_output.append(f"📡 [{os.path.basename(file_path)}] 실행 중...\n")
        
        self.process_tree_execute_openfast(item, file_path)

    def process_tree_move_to_completed(self, item, file_path, status, is_error=False):
        """running → completed 이동 """
        print(f"{item} file_path: {file_path} 상태 변경: {status} (에러 여부: {is_error})")

        end_time = datetime.now().strftime("%H:%M:%S")
        item.setText(3, end_time)       # 종료 시간
        item.setData(1, Qt.UserRole, status) 
        self.process_tree_apply_status_style(item, status) 
        
        self.process_tree_run_queue["completed"].append({
            "path": file_path,
            "success": not is_error,
            "end_time": end_time
        })

    def process_tree_apply_status_style(self, item, status):
        """평면 리스트 아이템 상태별 배경색 및 글자색 적용 (Stop 상태 추가)"""
        
        # === 상태별 색상 정의 ===
        colors = {
            PROCESS_TREE_STATUS_PENDING:   {"bg": "#FFFFFF", "fg": "#000000", "text": "Pending"},       #  (예정)
            PROCESS_TREE_STATUS_RUNNING:   {"bg": "#DCFCE7", "fg": "#000000", "text": "Running"},       #  (런중)
            PROCESS_TREE_STATUS_COMPLETED: {"bg": "#D1D5DB", "fg": "#000000", "text": "Completed"},     #  (완료)
            PROCESS_TREE_STATUS_STOP:      {"bg": "#D1D5DB", "fg": "#000000", "text": "Stopped"},       #  (중단)
            PROCESS_TREE_STATUS_ERROR:     {"bg": "#D1D5DB", "fg": "#EF4444", "text": "Error"},         #  빨간 글자 (에러)
        }
        
        if status not in colors:
            return
        
        style = colors[status]
        
        # 모든 컬럼에 동일한 스타일 적용
        for col in range(4):  # File, Status, Start, Finish
            item.setBackground(col, QBrush(QColor(style["bg"])))
            item.setForeground(col, QBrush(QColor(style["fg"])))
        
        item.setText(1, style["text"])

    def process_tree_find_item_by_path(self, file_path):
        """평면 리스트에서 파일 경로로 QTreeWidgetItem 찾기"""
        for i in range(self.process_tree.topLevelItemCount()):
            item = self.process_tree.topLevelItem(i)
            if item and item.data(0, Qt.UserRole) == file_path:
                return item
        return None

    def process_tree_execute_openfast(self, item, file_path):
        """OpenFAST 프로세스 실행 및 완료 콜백 (트리거링) 설정"""
        proc = QProcess(self)
        self.process_tree_process_map[file_path] = proc
        
        # 💡 기존 원본 코드의 OpenFAST 경로 탐색 방식 적용
        settings = QSettings("JHLEE", "OFA")
        openfast_exe = settings.value("OpenFastExe", "")

        if not openfast_exe or not os.path.exists(openfast_exe):
            default_paths = [
                r"C:\OpenFAST\openfast.exe",
                r"C:\Program Files\OpenFAST\openfast.exe",
                r"C:\Users\jeong\Downloads\BU_openFAST\OpenFAST.exe",  # 사용자 환경 경로 포용
            ]
            for p in default_paths:
                if os.path.exists(p):
                    openfast_exe = p
                    break

        if not openfast_exe or not os.path.exists(openfast_exe):
            QMessageBox.critical(self, "OpenFAST 없음", "OpenFAST 실행 파일을 찾을 수 없습니다.")
            self.process_tree_handle_process_finished(item, file_path, 1)
            return
        
        try:
            # QProcess 설정 및 실행
            proc.setProgram(openfast_exe)
            proc.setArguments([file_path])
            proc.setWorkingDirectory(os.path.dirname(file_path))

            # [개선] 표준 에러와 표준 출력을 완벽히 합쳐줍니다 (PySide6 스타일 네임스페이스)
            proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)

            # Openfast 실행중 콜백 연결 (실행에 따른 트리거링) 및 실행완료 시 트리거링
            proc.readyReadStandardOutput.connect(
                lambda: self.process_tree_stream_output(proc, file_path)
            )
            proc.finished.connect(
                lambda exit_code, exit_status, it=item, fp=file_path:
                self.process_tree_handle_process_finished(it, fp, exit_code)
            )
            
            proc.start()
            print(f"🚀 OpenFAST 프로세스 시작: {file_path}")
            
        except Exception as e:
            QMessageBox.critical(self, "실행 오류", f"OpenFAST 실행 실패:\n{str(e)}")
            self.process_tree_handle_process_finished(item, file_path, 1)

    def process_tree_handle_process_finished(self, item, file_path, exit_code):
        """OpenFAST 실행 완료 콜백"""
        # 💡 [수정] UI 객체가 이미 삭제되었다면 아무 작업도 하지 않고 즉시 종료
        if not self or not hasattr(self, 'process_tree') or not self.process_tree:
            print(f"⚠️ [Warning] UI has been destroyed. Skipping process finish handling for {os.path.basename(file_path)}.")
            return

        # 큐에서 런중 제거
        if file_path in self.process_tree_run_queue["running"]:
            self.process_tree_run_queue["running"].remove(file_path)

        # 해당 file_path에 대한 QProcess 객체를 process_tree_process_map에서 제거
        if file_path in self.process_tree_process_map:
            del self.process_tree_process_map[file_path]

        # 런중 → 런완료로 이동
        current_item_in_tree = self.process_tree_find_item_by_path(file_path)
        if current_item_in_tree: # 아이템이 아직 트리에 있다면 업데이트
            success = (exit_code == 0)
            self.process_tree_move_to_completed(current_item_in_tree, file_path, 
                                                PROCESS_TREE_STATUS_COMPLETED if success else PROCESS_TREE_STATUS_ERROR,
                                                is_error=not success)
        else: # 아이템이 이미 트리에 없다면 (사용자가 삭제했을 가능성) 로그만 업데이트
            print(f"⚠️ [Warning] Process finished for {os.path.basename(file_path)}, but its UI item was already removed.")
            if file_path in self.process_logs:
                self.process_logs[file_path] += f"\n✅ [Finished] Process End (UI item removed by user): {os.path.basename(file_path)}\n"
        
        # 실행 가능한 다음 항목 시작
        self.process_tree_try_start_next()

    def process_tree_stream_output(self, proc, file_path):
        """OpenFAST 로그 스트리밑 + 진행률 파싱 → Finish 컬럼에 % 표시"""
        # print(f"📡 [Streaming] OpenFAST 로그 수신 중: {file_path}")
        try:
            data = proc.readAllStandardOutput().data().decode('utf-8', errors='ignore')
            if data:
                # 1. 로그 누적
                if not hasattr(self, 'process_logs'):
                    self.process_logs = {}
                if file_path not in self.process_logs:
                    self.process_logs[file_path] = ""
                self.process_logs[file_path] += data

                # 2. 진행률 파싱 후 Finish 컬럼에 표시
                match = PROGRESS_RE.search(data)
                if match:
                    current_sec = int(match.group(1))
                    total_sec = int(match.group(2))
                    
                    
                    item = self.process_tree_find_item_by_path(file_path) # Check item existence
                    if item and total_sec > 0: # Only update if item exists and total_sec is valid
                        progress_pct = int((current_sec / total_sec) * 100)
                        # 아이템 찾아서 컬럼 3 (Finish) 에 진행률 표시
                        item = self.process_tree_find_item_by_path(file_path)
                        if item and item.data(1, Qt.UserRole) == PROCESS_TREE_STATUS_RUNNING:
                            item.setText(3, f"{progress_pct}%")  # 👈 진행률 표시

                # 3. 선택된 파일 로그만 cmd_output에 출력
                if (hasattr(self, 'cmd_output') and 
                    getattr(self, 'current_viewing_path', '') == file_path):
                    self.cmd_output.append(data)
                    self.cmd_output.moveCursor(QtGui.QTextCursor.End)

        except Exception as e:
            print(f"❌ 로그 스트리밍 중 예외 발생: {e}")

    def process_tree_on_item_clicked(self, index):
        """클릭 시 해당 파일의 누적 로그 표시 (자동 스크롤 맨 아래)"""
        print(f"process_tree_on_item_clicked(index) 호출됨: index={index.row()}")

        item = self.process_tree.itemFromIndex(index)
        if not item:
            return
            
        file_path = item.data(0, Qt.UserRole)
        if not file_path:
            return
            
        self.current_viewing_path = file_path
        
        if hasattr(self, 'cmd_output') and hasattr(self, 'process_logs'):
            self.cmd_output.clear()
            log_text = self.process_logs.get(file_path, "아직 생성된 로그가 없습니다.\n")
            self.cmd_output.setPlainText(log_text)
            self.cmd_output.moveCursor(QtGui.QTextCursor.End)  # 👈 맨 아래로 스크롤

    def process_tree_on_item_selection_changed(self):
        """평면 리스트에서 선택 변경 시 버튼 동작 전환 + Bold 처리"""
        print("process_tree_on_item_selection_changed() 호출됨")

        selected_items = self.process_tree.selectedItems()
        
        # 모든 아이템 폰트 일관 처리: 선택 = Bold / 비선택 = Normal
        font_bold = self._safe_font(self.process_tree.font(), True)
        font_normal = self._safe_font(self.process_tree.font(), False)
        
        # 모든 아이템 순회 → 선택된 것만 Bold
        for i in range(self.process_tree.topLevelItemCount()):
            item = self.process_tree.topLevelItem(i)
            if item:
                is_selected = item.isSelected()
                for col in range(item.columnCount()):
                    # 선택된 아이템 → Bold 폰트, 비선택 아이템 → Normal 폰트 (Bold 해제)
                    item.setFont(col, font_bold if is_selected else font_normal)

                item_status = item.data(1, Qt.UserRole)
                self.process_tree_apply_status_style(item, item_status)
        
        # 버튼 전환 로직
        if not selected_items:
            print("[Process Tree] 선택된 항목이 없습니다. 버튼 상태 초기화.")
            self.process_tree_reset_buttons()
            return
        
        first_item = selected_items[0]
        item_status = first_item.data(1, Qt.UserRole)
        
        # 상태가 다른 아이템이 섞여 있으면 선택 해제 (방지)
        for item in selected_items:
            if item.data(1, Qt.UserRole) != item_status:
                item.setSelected(False)
        
        # 버튼 전환
        if item_status == PROCESS_TREE_STATUS_RUNNING:
            self.process_tree_set_stop_button_active()
            print("process_tree_set_stop_button_active() 호출됨")
        else:
            self.process_tree_set_remove_button_active(item_status)
            print("process_tree_set_remove_button_active() 호출됨")

    def process_tree_set_stop_button_active(self):
        """Stop 버튼으로 전환 (런중 아이템 선택 시)"""
        self.btn_left_stop.setText("🛑 Stop")
        self.btn_left_stop.setEnabled(True)
        self.btn_left_stop.setEnabled(True) # Enable the button
        try:
            self.btn_left_stop.clicked.disconnect() # Disconnect any previous connections
        except RuntimeError: # Catch if no slot was connected
            pass
        self.btn_left_stop.clicked.connect(self.process_tree_handle_stop_clicked)

    def process_tree_set_remove_button_active(self, status):
        """Remove 버튼으로 전환 (running/completed/stop 아이템 선택 시)"""
        self.btn_left_stop.setText("🗑️ Remove")
        self.btn_left_stop.setEnabled(True)
        try:
            self.btn_left_stop.clicked.disconnect()
        except RuntimeError:
            pass
        self.btn_left_stop.clicked.connect(lambda: self.process_tree_handle_remove_clicked(status)) # noqa

    def process_tree_reset_buttons(self):
        """단추 원래 상태로 리셋"""
        self.btn_left_stop.setText("🛑 Stop")
        self.btn_left_stop.setEnabled(False)
        try:
            self.btn_left_stop.clicked.disconnect()
        except RuntimeError:
            pass

    def process_tree_handle_stop_clicked(self):
        """런중 아이템 선택 → Stop 버튼 → 3단계 강제 종료"""
        selected = [it for it in self.process_tree.selectedItems() 
                    if it.data(1, Qt.UserRole) == PROCESS_TREE_STATUS_RUNNING]
        
        if not selected:
            return
        
        reply = QMessageBox.question(
            self, "실행 중단",
            f"선택한 {len(selected)}개의 프로세스를 중단하시겠습니까?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.No:
            return
        
        for item in selected:
            file_path = item.data(0, Qt.UserRole)
            proc = self.process_tree_process_map.get(file_path)

            # Remove from running queue and process map immediately
            if file_path in self.process_tree_run_queue["running"]:
                self.process_tree_run_queue["running"].remove(file_path)
            if file_path in self.process_tree_process_map:
                del self.process_tree_process_map[file_path]

            # Disconnect signals immediately to prevent further updates from QProcess
            
            if proc and proc.state() == QProcess.Running:
                import subprocess as sp
                
                # 🛑 1단계: terminate (SIGTERM)
                proc.terminate()
                try:
                    proc.waitForFinished(2000)
                except:
                    pass
                
                # 🛑 2단계: kill (SIGKILL)
                if proc.state() == QProcess.Running:
                    proc.kill()
                    try:
                        proc.waitForFinished(3000)
                    except:
                        pass
                
                # 🛑 3단계: system-level taskkill (자식 프로세스 포함) — ★ 핵심!
                if proc.state() == QProcess.Running:
                    try:
                        pid = proc.pid()
                        # /T: 자식 프로세스 포함, /F: 강제 종료
                        result = sp.run(
                            f'taskkill /F /PID {pid} /T',
                            shell=True, capture_output=True, text=True, timeout=5
                        )
                        print(f"⚡ [System Kill] PID={pid}: {result.stdout.strip()}")
                        
                        proc.waitForFinished(1000)
                    except Exception as e:
                        print(f"⚠️ [System Kill 예외] {e}")
                
                # 🧹 4단계: 정리
                self.process_tree_process_map.pop(file_path, None)
                try:
                    proc.readyReadStandardOutput.disconnect()
                    proc.readyReadStandardError.disconnect()
                    proc.finished.disconnect()
                except RuntimeError:
                    pass


                # Update process_logs to reflect termination
                if file_path in self.process_logs:
                    self.process_logs[file_path] += f"\n❌ [Stopped by User] Process Terminated: {os.path.basename(file_path)}\n"
                
                # 상태 로그
                state = proc.state()
                if state == QProcess.Running:
                    # If it's still running after all attempts, mark as error
                    self.process_tree_move_to_completed(item, file_path, PROCESS_TREE_STATUS_ERROR, is_error=True)
                    if file_path in self.process_tree_run_queue["running"]:
                        self.process_tree_run_queue["running"].remove(file_path)
                    print(f"❌ [Stop] 종료 실패: {os.path.basename(file_path)} (PID: {proc.pid()})")
                else:
                    print(f"✅ [Stop] 종료 성공: {os.path.basename(file_path)}")
            
            # UI 상태 변경
            self.process_tree_move_to_completed(item, file_path, PROCESS_TREE_STATUS_STOP, True)
            self.process_tree_set_remove_button_active(PROCESS_TREE_STATUS_STOP)
            # Remove from running queue
            if file_path in self.process_tree_run_queue["running"]:
                self.process_tree_run_queue["running"].remove(file_path)
        
        # 다음 런예정 시작
        self.process_tree_try_start_next()

    def process_tree_handle_remove_clicked(self, status):
        """런예정/런완료/Stop 아이템 선택 → Remove 버튼 → 리스트에서 제거"""
        selected = [it for it in self.process_tree.selectedItems()
                    if it.data(1, Qt.UserRole) == status or (status in [PROCESS_TREE_STATUS_COMPLETED, PROCESS_TREE_STATUS_STOP, PROCESS_TREE_STATUS_ERROR] and it.data(1, Qt.UserRole) in [PROCESS_TREE_STATUS_COMPLETED, PROCESS_TREE_STATUS_STOP, PROCESS_TREE_STATUS_ERROR])]
        
        # Use a copy of the list to iterate over, as we'll be modifying the original
        items_to_remove = list(selected)

        for item in items_to_remove:
            file_path = item.data(0, Qt.UserRole)

            # If a running process is being removed, terminate it and disconnect signals
            if item.data(1, Qt.UserRole) == PROCESS_TREE_STATUS_RUNNING:
                proc = self.process_tree_process_map.get(file_path)
                if proc and proc.state() == QProcess.Running:
                    print(f"⚠️ [Warning] Removing running process {os.path.basename(file_path)}. Terminating it.")
                    try:
                        proc.readyReadStandardOutput.disconnect()
                        proc.readyReadStandardError.disconnect()
                        proc.finished.disconnect()
                    except RuntimeError:
                        pass
                    proc.terminate()
                    proc.waitForFinished(1000)
                    if proc.state() == QProcess.Running:
                        proc.kill()
                        proc.waitForFinished(1000)
                    if proc.state() == QProcess.Running:
                        try:
                            pid = proc.pid()
                            subprocess.run(
                                f'taskkill /F /PID {pid} /T',
                                shell=True, capture_output=True, text=True, timeout=5,
                                creationflags=subprocess.CREATE_NO_WINDOW
                            )
                            print(f"⚡ [System Kill] PID={pid} for removed item.")
                        except Exception as e:
                            print(f"⚠️ [System Kill Exception] for removed item: {e}")
                
                # Remove from process map and running queue
                if file_path in self.process_tree_process_map:
                    del self.process_tree_process_map[file_path]
                if file_path in self.process_tree_run_queue["running"]:
                    self.process_tree_run_queue["running"].remove(file_path)

            # 큐에서도 제거
            queue_key = {PROCESS_TREE_STATUS_PENDING: "pending", 
                         PROCESS_TREE_STATUS_COMPLETED: "completed",
                         PROCESS_TREE_STATUS_STOP: "completed",
                         PROCESS_TREE_STATUS_ERROR: "completed"}.get(item.data(1, Qt.UserRole))
            if queue_key and file_path in self.process_tree_run_queue[queue_key]:
                self.process_tree_run_queue[queue_key].remove(file_path)
            
            # 👇 flat view용: topLevelItem 직접 제거
            row = self.process_tree.indexOfTopLevelItem(item)
            if row != -1:
                self.process_tree.takeTopLevelItem(row) # This deletes the QTreeWidgetItem

        # After removal, update button states and try to start next pending process
        self.process_tree_on_item_selection_changed() # Re-evaluate button states
        self.process_tree_try_start_next()

        

    def get_current_working_dir(self):
        """현재 작업 디렉토리 반환 (마지막 .fst 경로 기반)"""
        if self.process_tree_run_queue["pending"]:
            return os.path.dirname(self.process_tree_run_queue["pending"][0])
        settings = QSettings("JHLEE", "OFA")
        last_fst = settings.value("LastFstPath_fst", "")
        return os.path.dirname(last_fst) if last_fst else os.getcwd()

    def process_tree_adjust_run_count(self, event=None):
        """최대 동시 실행 개수 조절 (ProcessQueueManager에 위임)"""
        new_count = self.queue_mgr.adjust_max_concurrent(self, self.queue_mgr.queue.max_concurrent)
        if new_count is not None and hasattr(self, 'cmd_output'):
            self.cmd_output.append(f"⚙️ 최대 동시 실행 개수: {new_count}로 설정됨\n")

    def cleanup_processes(self):
        """애플리케이션 종료 시 모든 실행 중인 QProcess를 정리합니다."""
        print("[Cleanup] 모든 실행 중인 프로세스를 종료합니다...")
        
        # process_tree_process_map의 복사본을 만들어 순회 (원본 딕셔너리 변경에 따른 문제 방지)
        for file_path, proc in list(self.process_tree_process_map.items()):
            if proc and proc.state() == QProcess.Running:
                try:
                    # 시그널 연결 해제 (메모리 누수 및 충돌 방지)
                    proc.readyReadStandardOutput.disconnect()
                    proc.finished.disconnect()
                except RuntimeError:
                    pass # 이미 연결이 끊어진 경우
                proc.kill()  # 프로세스 강제 종료
                proc.waitForFinished(1000) # 1초 대기
                print(f"  -> 🛑 종료: {os.path.basename(file_path)}")
        self.process_tree_process_map.clear()


    def process_tree_move_selected_up(self):
        """Shift + ↑ : 런예정 리스트 내 선택항목 위로 이동"""
        selected_items = self.process_tree.selectedItems()
        if not selected_items:
            return

        # PENDING 상태인 항목만 필터링
        pending_items = [it for it in selected_items if it.data(1, Qt.UserRole) == PROCESS_TREE_STATUS_PENDING]
        if not pending_items:
            return

        # 올바른 순서로 이동하기 위해 행 번호 기준으로 정렬
        pending_items.sort(key=lambda item: self.process_tree.indexOfTopLevelItem(item))

        for item in pending_items:
            row = self.process_tree.indexOfTopLevelItem(item)
            if row > 0:
                # 바로 위 아이템이 PENDING 상태가 아니면 이동하지 않음
                above_item = self.process_tree.topLevelItem(row - 1)
                if above_item and above_item.data(1, Qt.UserRole) == PROCESS_TREE_STATUS_PENDING:
                    self.process_tree.takeTopLevelItem(row)
                    self.process_tree.insertTopLevelItem(row - 1, item)
                    item.setSelected(True)

        # 큐 순서도 동기화
        self.process_tree_resync_pending_queue()

    def process_tree_move_selected_down(self):
        """Shift + ↓ : 런예정 리스트 내 선택항목 아래로 이동"""
        selected_items = self.process_tree.selectedItems()
        if not selected_items:
            return

        pending_items = [it for it in selected_items if it.data(1, Qt.UserRole) == PROCESS_TREE_STATUS_PENDING]
        if not pending_items:
            return

        # 아래에서 위로 순서로 정렬해야 인덱스가 꼬이지 않음
        pending_items.sort(key=lambda item: self.process_tree.indexOfTopLevelItem(item), reverse=True)

        for item in pending_items:
            row = self.process_tree.indexOfTopLevelItem(item)
            # 마지막 아이템이 아니어야 함
            if row < self.process_tree.topLevelItemCount() - 1:
                below_item = self.process_tree.topLevelItem(row + 1)
                if below_item and below_item.data(1, Qt.UserRole) == PROCESS_TREE_STATUS_PENDING:
                    self.process_tree.takeTopLevelItem(row)
                    self.process_tree.insertTopLevelItem(row + 1, item)
                    item.setSelected(True)

        self.process_tree_resync_pending_queue()

    def process_tree_resync_pending_queue(self):
        """UI 순서를 큐 데이터와 동기화"""
        self.process_tree_run_queue["pending"] = [
            self.process_tree.topLevelItem(i).data(0, Qt.UserRole)
            for i in range(self.process_tree.topLevelItemCount())
            if self.process_tree.topLevelItem(i).data(1, Qt.UserRole) == PROCESS_TREE_STATUS_PENDING
        ]

    def keyPressEvent(self, event):
        if event.modifiers() & Qt.ShiftModifier:
            if event.key() == Qt.Key_Up:
                self.process_tree_move_selected_up()
                return
            elif event.key() == Qt.Key_Down:
                self.process_tree_move_selected_down()
                return
        super().keyPressEvent(event)

    def process_tree_save_run_queue(self):
        """실행 큐 상태를 .ofa_run_queue.json으로 저장"""
        queue_data = {
            "pending": self.process_tree_run_queue["pending"],
            "running": self.process_tree_run_queue["running"],
            "completed": self.process_tree_run_queue["completed"],
            "max_concurrent": self.process_tree_max_concurrent,
            "timestamp": datetime.now().isoformat(),
        }
        
        save_path = os.path.join(self.get_current_working_dir(), ".ofa_run_queue.json")
        try:
            with open(save_path, 'w', encoding='utf-8') as f:
                json.dump(queue_data, f, indent=2)
            # cmd_output에 저장 완료 메시지
            if hasattr(self, 'cmd_output'):
                self.cmd_output.append(f"💾 실행 큐 상태 저장: {save_path}\n")
        except Exception as e:
            print(f"❌ 큐 저장 실패: {e}")

    def process_tree_load_run_queue(self):
        """저장된 실행 큐 상태 복구 (사용자 확인 후)"""
        save_path = os.path.join(self.get_current_working_dir(), ".ofa_run_queue.json")
        if not os.path.exists(save_path):
            return
        
        # 파일 수정 시간 확인
        mtime = datetime.fromtimestamp(os.path.getmtime(save_path))
        
        reply = QMessageBox.question(
            self, "실행 상태 복구",
            f"이전 실행 상태가 발견되었습니다.\n\n"
            f"저장 시간: {mtime.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"복구하시겠습니까?\n\n"
            f"(이미 완료된 작업은 런완료로, 진행 중이던 작업은 런예정으로 복구됩니다.)",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes
        )
        
        if reply == QMessageBox.No:
            return
        
        try:
            with open(save_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            self.process_tree_restore_queue(data)
            if hasattr(self, 'cmd_output'):
                self.cmd_output.append("🔄 실행 큐 상태 복구 완료\n")
        except Exception as e:
            QMessageBox.warning(self, "복구 실패", f"실행 상태 복구 중 오류:\n{e}")

    def process_tree_restore_queue(self, data):
        """복구된 데이터로 큐와 UI 재구성"""
        # 기존 트리 비우기
        self.process_tree.clear()
        
        # 큐 복원
        self.process_tree_run_queue = {
            "pending": data.get("pending", []),
            "running": data.get("running", []),   # 재시작 시에는 모두 런예정으로 처리
            "completed": data.get("completed", []),
        }
        self.process_tree_max_concurrent = data.get("max_concurrent", 3)
        
        # 런중 → 런예정으로 이동 (재시작 시)
        restored_running = self.process_tree_run_queue["running"]
        self.process_tree_run_queue["pending"] = restored_running + self.process_tree_run_queue["pending"]
        self.process_tree_run_queue["running"] = []
        
        # UI 재구성
        # 1. 런예정 항목 추가
        for fp in self.process_tree_run_queue["pending"]:
            self.process_tree_add_to_pending(fp)

        # 2. 런완료/에러/중단 항목 복원
        for completed_info in self.process_tree_run_queue.get("completed", []):
            path = completed_info.get("path")
            success = completed_info.get("success")
            status = PROCESS_TREE_STATUS_COMPLETED if success else PROCESS_TREE_STATUS_ERROR
            item = QTreeWidgetItem([os.path.basename(path), "", "", ""])
            item.setData(0, Qt.UserRole, path)
            self.process_tree_move_to_completed(item, path, status, is_error=not success)
            self.process_tree.addTopLevelItem(item)



    def _on_queue_item_added(self, item):
        """큐에 새 아이템 추가 시 UI 트리에 추가"""
        qt_item = QTreeWidgetItem([os.path.basename(item.path), "Pending", "", ""])
        qt_item.setData(0, Qt.UserRole, item.path)
        qt_item.setData(1, Qt.UserRole, item.status)
        self._apply_status_style(qt_item, item.status)
        self.process_tree.addTopLevelItem(qt_item)
        item.qt_item = qt_item

    def _on_queue_item_updated(self, item):
        """큐 아이템 상태 변경 시 UI 업데이트"""
        qt_item = getattr(item, 'qt_item', None)
        if qt_item:
            self._apply_status_style(qt_item, item.status)
            if item.start_time:
                qt_item.setText(2, item.start_time)
            if item.end_time:
                qt_item.setText(3, item.end_time)

    def _on_queue_item_removed(self, item):
        """큐에서 아이템 제거 시 UI에서 제거"""
        qt_item = getattr(item, 'qt_item', None)
        if qt_item:
            row = self.process_tree.indexOfTopLevelItem(qt_item)
            if row != -1:
                self.process_tree.takeTopLevelItem(row)

    def _on_queue_log_received(self, file_path: str, data: str):
        """로그 수신 시 process_logs 업데이트"""
        if not hasattr(self, 'process_logs'):
            self.process_logs = {}
        if file_path not in self.process_logs:
            self.process_logs[file_path] = ""
        self.process_logs[file_path] += data
        
        if getattr(self, 'current_viewing_path', '') == file_path:
            if hasattr(self, 'cmd_output'):
                self.cmd_output.append(data)
                self.cmd_output.moveCursor(QtGui.QTextCursor.End)

    def _on_queue_progress_updated(self, file_path: str, percent: int):
        """진행률 업데이트 시 Finish 컬럼에 표시"""
        item = self._find_qt_item_by_path(file_path)
        if item and item.data(1, Qt.UserRole) == PROCESS_TREE_STATUS_RUNNING:
            item.setText(3, f"{percent}%")

    def _on_queue_buttons_update(self):
        """버튼 상태 업데이트 요청"""
        if hasattr(self, 'process_tree_on_item_selection_changed'):
            self.process_tree_on_item_selection_changed()

    def _find_qt_item_by_path(self, file_path: str):
        """경로로 QTreeWidgetItem 찾기"""
        for i in range(self.process_tree.topLevelItemCount()):
            item = self.process_tree.topLevelItem(i)
            if item and item.data(0, Qt.UserRole) == file_path:
                return item
        return None

    def _apply_status_style(self, item, status):
        """아이템에 상태별 스타일 적용"""
        status_map = {
            0: {"bg": "#FFFFFF", "fg": "#000000", "text": "Pending"},
            1: {"bg": "#DCFCE7", "fg": "#000000", "text": "Running"},
            2: {"bg": "#D1D5DB", "fg": "#000000", "text": "Completed"},
            3: {"bg": "#D1D5DB", "fg": "#000000", "text": "Stopped"},
            4: {"bg": "#D1D5DB", "fg": "#EF4444", "text": "Error"},
        }
        style = status_map.get(status)
        if not style:
            return
        for col in range(4):
            item.setBackground(col, QBrush(QColor(style["bg"])))
            item.setForeground(col, QBrush(QColor(style["fg"])))
        item.setText(1, style["text"])

#=================================================================================================================================================================================================



    def closeEvent(self, event):
        """프로그램 종료 전 상태 저장"""
        self.process_tree_save_run_queue()
        
        event.accept()

#=================================================================================================================================================================================================