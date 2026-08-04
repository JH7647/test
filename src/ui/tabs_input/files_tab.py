import os
import copy
import sys
import subprocess 
import json
import shutil
import tempfile
import openpyxl
import re

from datetime import datetime
from logging import config

from PySide6.QtWidgets import QMessageBox, QFileDialog, QDialog
from PySide6.QtCore import QPoint, Qt,QSettings, Qt, QPoint, QSettings, QProcess
from PySide6.QtGui import QStandardItemModel, QStandardItem
from PySide6.QtWidgets import QTextEdit, QPushButton, QHBoxLayout, QFormLayout, QSpinBox, QLineEdit, QComboBox, QTableWidget, QTableWidgetItem, QAbstractItemView
from PySide6.QtGui import QColor, QBrush, QFont, QCursor
from PySide6.QtCore import QProcess, QSettings, Qt
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QTabWidget, QLabel, QTreeView, QSplitter

from PySide6.QtWidgets import QFileDialog, QInputDialog, QMessageBox, QWidget, QVBoxLayout, QTreeView

from src.core.openfast_io import OpenFastIO  # 코어 엔진 임포트

PROGRESS_RE = re.compile(r"Time:\s*(\d+)\s+of\s+(\d+)\s+seconds[^\r\n]*")

class FilesTab(QWidget):
    """ 오직 파일 디렉토리 탐색과 드래그앤드롭 모션, 트리 배지만 책임지는 정석 UI 위젯 """
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window  # 상위 컨트롤러 메인 창 정보 저장 (탭 라우팅 신호용)
        self._drag_start_position = QPoint()
        self.init_ui()

        self.running_processes = []
        self.process_logs = {}

    def init_ui(self):

        self.setAcceptDrops(True)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(2, 2, 2, 2)
        main_layout.setSpacing(2)
        main_layout.addWidget(splitter)

# region : [LEFT SIDE] 대기열 및 상태 관리 영역 
# =================================================================

        # === [LEFT SIDE] 세로 Splitter로 분할 ===
        left_vsplitter = QSplitter(Qt.Vertical)
        left_vsplitter.setChildrenCollapsible(False)

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
        # ========================================
        
        # 1. Path 정보 (버튼 -> 디렉토리 변경)
        # 레지스트리에서 마지막 세션 복구 자동 가동
        settings = QSettings("JHLEE", "OFA")
        last_fst_path = settings.value("LastFstPath_fst", "")

        current_dir = "" 
        display_dir = ""
        
        if last_fst_path and os.path.exists(last_fst_path):
            current_dir = os.path.dirname(last_fst_path)
            display_dir = self.shrink_directory_path(current_dir, max_len=150)

        # 경로 데이터 유무에 따른 최종 텍스트 마킹
        btn_text = f"📂 {display_dir}" if display_dir else "📂 디렉토리 선택"

        self.btn_change_dir = QPushButton(btn_text)
        self.btn_change_dir.setMinimumHeight(30)
        
        # 마우스를 올렸을 때 뜨는 툴팁에는 '원본(긴) 경로'를 온전히 보여줍니다.
        if current_dir:
            self.btn_change_dir.setToolTip(current_dir)
            
        self.btn_change_dir.setStyleSheet("""
            QPushButton {
                background-color: #F3F4F6;
                color: #1F2937;
                font-weight: bold;
                font-size: 12px;
                border: 1px solid #D1D5DB;
                border-radius: 4px;
                text-align: left;
                padding-left: 8px;
            }
            QPushButton:hover { background-color: #D1D5DB; }
        """)
        # 버튼을 클릭했을 때 작동할 이벤트 연결 
        self.btn_change_dir.clicked.connect(self.btn_change_dir_clicked)

        left_top_layout.addWidget(self.btn_change_dir)
        
        # 2. .fst 파일 list 트리뷰         
        self.dir_tree_list = QTreeView()  
        self.dir_tree_list.setHeaderHidden(True)
        self.dir_tree_list.setRootIsDecorated(False)    
        self.dir_tree_list.setIndentation(2)           
        self.dir_tree_list.setExpandsOnDoubleClick(False)
        self.dir_tree_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.dir_tree_list.setSelectionBehavior(QAbstractItemView.SelectRows)

        self.dir_tree_model = QStandardItemModel()   # 새 모델 바인딩
        self.dir_tree_list.setModel(self.dir_tree_model) # 새 모델 바인딩       
        self.dir_tree_list.setStyleSheet("""
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
            QTreeView::item:hover { 
                background-color: #F0F9FF; 
                color: #0369A1;            
            }
            /* 💡 [배경색 변경 핵심 와꾸] 
               마우스로 선택(selected)되는 순간, 스타일시트가 기본 파란색을 가로채어 
               통일된 연회색(#E5E7EB) 배경과 진한 회색(#374151) 글자색을 100% 촥 채우도록 강제합니다. */
            QTreeView::item:selected {
                background-color: #D1D5DB !important; 
                color: #374151 !important;            
                font-weight: bold;         
            }
        """)

        # 마우스 물리 피지컬 이벤트 격리 바인딩
        self.dir_tree_list.mousePressEvent = self.on_dir_tree_clicked
        self.dir_tree_list.doubleClicked.connect(self.on_dir_tree_item_double_clicked)
        self.dir_tree_list.setContextMenuPolicy(Qt.CustomContextMenu)
        # self.dir_tree_list.customContextMenuRequested.connect(self.on_dir_tree_item_right_clicked)

        left_top_layout.addWidget(self.dir_tree_list, stretch=4)

        if last_fst_path and os.path.exists(last_fst_path):
            self.update_dir_tree_list(last_fst_path)

        # 3. Process list 표시 영역 (라벨 및 Run, Stop 버튼 한 행 구성)
        process_header_layout = QHBoxLayout()
        process_header_layout.setContentsMargins(4, 10, 0, 2) # 좌, 상, 우, 하
        process_header_layout.setSpacing(0) # 레이아웃 기본 스페이싱은 0으로 격리
        
        # ⚙️ Process list 표시 라벨
        lbl_process = QLabel(" ⚙️ Process list 표시")
        lbl_process.setStyleSheet("font-weight: bold; color: #374151; font-size: 14px;")
        process_header_layout.addWidget(lbl_process)
        
        # 여기에 Stretch를 넣어 왼쪽 라벨을 고정하고 모든 버튼을 오른쪽 끝으로 밀어냅니다.
        process_header_layout.addStretch() 
        
        # 🚀 Run 버튼 (너비 및 디자인 유지)
        self.btn_left_run = QPushButton("🚀 Run")
        self.btn_left_run.setFixedWidth(130)     
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
        
        # 💡 두 버튼 사이의 간격을 10px 만큼 확실하게 띄워줌
        process_header_layout.addSpacing(25)
        
        # 🛑 Stop 버튼 (너비 및 디자인 유지)
        self.btn_left_stop = QPushButton("🛑 Stop")
        self.btn_left_stop.setFixedWidth(130)     
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
        self.btn_left_stop.clicked.connect(self.btn_left_stop_clicked)
        process_header_layout.addWidget(self.btn_left_stop)
        
        # 레이아웃을 패널에 추가
        left_bottom_layout.addLayout(process_header_layout)
        
        # 프로세스 상태 리스트를 표현할 트리뷰 (또는 리스트뷰)
        self.process_tree_view = QTreeView()
        self.process_tree_view.setHeaderHidden(True)
        self.process_tree_list = QStandardItemModel()
        self.process_tree_view.setModel(self.process_tree_list)
        self.process_tree_view.setRootIsDecorated(False)
        self.process_tree_view.setIndentation(0)
        self.process_tree_view.setStyleSheet("""
            QTreeView { border: 1px solid #E5E7EB; background-color: #FFFFFF; font-size: 13px; }
            QTreeView::viewport {
                background-color: #FFFFFF;
            }
            QTreeView::item { padding: 6px 0px; font-weight: bold; }
            QTreeView::item:selected {
                background-color: #D1D5DB;
                color: #374151;
            }
        """)
        left_bottom_layout.addWidget(self.process_tree_view, stretch=2)

        self.process_logs = {}       # {파일경로: "누적 로그 문자열"} 형태로 로그를 보관할 장부
        self.current_viewing_path = "" # 현재 사용자가 클릭해서 보고 있는 파일 경로 Track
        self.process_tree_view.clicked.connect(self.on_process_item_clicked)

        # 세로 Splitter에 위젯 추가
        left_top_widget.setMinimumWidth(300)
        left_vsplitter.addWidget(left_top_widget)
        left_vsplitter.addWidget(left_bottom_widget)
        left_vsplitter.setSizes([400, 180])  # 초기 비율

        splitter.addWidget(left_vsplitter)

# endregion : =====================================================



# region : [RIGHT SIDE] 파일 경로 상세 정보 및 실행 로그 제어 영역
# =================================================================
        # === [RIGHT SIDE] ===
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

        # 1. 상단: .fst 파일 path 정보 및 세부 연동 파일 표시 트리뷰
        current_fst_path = ""
        display_fst_path = ""

        if last_fst_path and os.path.exists(last_fst_path):
            current_fst_path = last_fst_path
            display_fst_path = self.shrink_directory_path(current_fst_path, max_len=100)

        # # 경로 데이터 유무에 따른 최종 버튼 마킹 텍스트 분기 처리
        # btn_fst_path_text = f"🚀 {display_fst_path}   -> Run Batch" if display_fst_path else "📂 Drag & Drop, or Select '.fst' File"

        # self.btn_fst_path = QPushButton(btn_fst_path_text)
        # self.btn_fst_path.setMinimumHeight(30) 
        
        # # 실제 유효한 파일 경로가 존재할 때만 툴팁에 원본(긴) 전체 경로를 온전히 뿌려줍니다.
        # if current_fst_path:
        #     self.btn_fst_path.setToolTip(current_fst_path)
            
        # self.btn_fst_path.setStyleSheet("""
        #     QPushButton {
        #         background-color: #F8FAFC;
        #         color: #334155;
        #         font-weight: bold;
        #         font-size: 12px;
        #         border: 1px solid #E2E8F0;
        #         border-radius: 6px;
        #         text-align: left;
        #         padding-left: 12px;
        #     }
        #     QPushButton:hover { 
        #         background-color: #F1F5F9; 
        #         border: 1px solid #CBD5E1;
        #     }
        # """)
        # # 버튼을 클릭했을 때 작동할 이벤트 연결 
        # self.btn_fst_path.clicked.connect(self.btn_fst_path_clicked)

        # right_panel.addWidget(self.btn_fst_path)

        # 2. OpenFAST 모델 구성 정보 표시 트리뷰   
        self.model_tree_view = QTreeView()
        self.model_tree_view.setHeaderHidden(True)
        self.model_tree_view.setRootIsDecorated(True)   
        self.model_tree_view.setIndentation(20)
        self.model_tree_view.setExpandsOnDoubleClick(False)

        self.model_tree_model = QStandardItemModel()
        self.model_tree_view.setModel(self.model_tree_model)

        self.model_tree_view.setStyleSheet("""
            QTreeView { 
                border: 1px solid #E5E7EB; 
                background-color: #FFFFFF; 
                font-size: 12px; 
            }
            QTreeView::viewport {
                background-color: #FFFFFF;
            }
            QTreeView::item { 
                padding: 5px 0px; 
            }
            QTreeView::item:selected {
                background-color: #D1D5DB !important; 
                color: #374151 !important;            
                font-weight: bold;         
            }
        """)

        # 마우스 물리 피지컬 이벤트 격리 바인딩
        self.model_tree_view.mousePressEvent = self.on_model_tree_press_event
        self.model_tree_view.mouseMoveEvent = self.on_model_tree_move_event
        self.model_tree_view.doubleClicked.connect(self.on_model_tree_item_double_clicked)
        self.model_tree_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.model_tree_view.customContextMenuRequested.connect(self.on_model_tree_item_right_clicked)

        right_top_layout.addWidget(self.model_tree_view, stretch=402)

        if current_fst_path and os.path.exists(current_fst_path):
            self.update_model_tree_view(current_fst_path)

        # 3. CMD Result 표시 영역
        process_result_header_layout = QHBoxLayout() # 좌측 process_header_layout의 (4, 10, 0, 2)와 똑같이 상단 여백(10px)을 주어 완벽하게 수평을 맞춥니다.
        process_result_header_layout.setContentsMargins(4, 16, 0, 6)
        process_result_header_layout.setSpacing(0)

        lbl_process_result = QLabel(" 🔍 Process Result")
        lbl_process_result.setStyleSheet("font-weight: bold; color: #374151; font-size: 14px;")
        process_result_header_layout.addWidget(lbl_process_result)
        
        right_bottom_layout.addLayout(process_result_header_layout)

        # cmd 로그 출력 창 (`QTextEdit`)
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
        right_vsplitter.setSizes([500, 300])
        splitter.addWidget(right_vsplitter)
# endregion : =====================================================


    def on_dir_tree_item_double_clicked(self, index):
        """ 📝 좌측 트리 항목을 더블 클릭했을 때 Notepad++로 파일을 즉시 연는 슬롯 """
        if not index.isValid():
            return

        print("📂 [FilesTab] Double-click detected on directory tree item.")
        
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

    def on_dir_tree_clicked(self, event):
        """ 좌측 디렉토리 트리뷰에서 마우스 물리 누름(Press) 이벤트를 가로채어 처리 """
        
        # 1. 마우스가 누른 좌표로부터 트리의 인덱스 추출
        index = self.dir_tree_list.indexAt(event.pos())
        
        # 2. QTreeView 본연의 선택 및 하이라이트 모션을 유지하기 위해 부모 이벤트 호출
        from PySide6.QtWidgets import QTreeView
        QTreeView.mousePressEvent(self.dir_tree_list, event)

        # 빈 여백이 아닌 실제 파일 항목을 정확히 찍었을 때만 진입
        if not index.isValid():
            return
            
        item = self.dir_tree_model.itemFromIndex(index)
        if item:
            clicked_file_path = item.data(Qt.UserRole)
            
            if clicked_file_path and os.path.exists(clicked_file_path):
                print(f"⚡ [Single Click] 활성화 -> {clicked_file_path}")
                
                # 💡 [더블클릭 먹통 및 잔상 버그 동시 해결 완수 핵심 와꾸]
                # self.update_dir_tree_list() 호출을 과감히 제거합니다! (장부 폭파 차단)
                # 대신 장부에 이미 생성되어 있는 파일들을 돌면서 '스마트 색상 토글'만 집행합니다.
                from PySide6.QtGui import QBrush, QColor, QFont
                
                for row in range(self.dir_tree_model.rowCount()):
                    loop_item = self.dir_tree_model.item(row)
                    if not loop_item:
                        continue
                        
                    loop_path = loop_item.data(Qt.UserRole)
                    
                    # 새로 클릭한 타겟 파일인 경우 -> 연회색 강조 적용
                    if loop_path and loop_path.lower() == clicked_file_path.lower():
                        loop_item.setBackground(QBrush(QColor("#D1D5DB")))
                        loop_item.setForeground(QBrush(QColor("#374151")))
                        font = QFont()
                        font.setBold(True)
                        loop_item.setFont(font)
                    # 이전에 강조되었던 과거의 파일인 경우 -> 깨끗하게 하얀색 원상 복구!
                    else:
                        loop_item.setBackground(QBrush(Qt.GlobalColor.transparent))
                        loop_item.setForeground(QBrush(Qt.GlobalColor.black))
                        font = QFont()
                        font.setBold(False)
                        loop_item.setFont(font)

                # 3. 최신 세션 경로 변수 동기화
                self.last_fst_path = clicked_file_path
                
                # 🎯 [우측 화면 동기화] 우측 상세 구성 정보 트리 실시간 파싱 및 동기화
                if hasattr(self, 'update_model_tree_view'):
                    self.update_model_tree_view(clicked_file_path)
                
                # 🎯 [화면 즉시 리프레시] 윈도우 OS 그래픽 엔진 즉시 렌더링 강제 집행
                from PySide6.QtWidgets import QApplication
                QApplication.processEvents()

    def update_dir_tree_list(self, last_fst_path):
        """ 📁 지정된 폴더 내부의 모든 .fst 파일만 순수하게 추출하여 좌측 리스트에 바인딩합니다. """
        # 좌측 트리 리스트를 깨끗하게 비웁니다.
        self.dir_tree_model.clear()
        
        directory_path = ""
        if last_fst_path and os.path.exists(last_fst_path):
            directory_path = os.path.dirname(last_fst_path)

        if not os.path.exists(directory_path):
            return
            
        try:
            files = os.listdir(directory_path)
            fst_files = [f for f in files if f.lower().endswith('.fst')]
        except Exception as e:
            if hasattr(self, 'cmd_output'):
                self.cmd_output.append(f"❌ 폴더 읽기 실패: {str(e)}\n")
            return

        # 만약 폴더 내에 .fst 파일이 하나도 없다면 안내 문구를 띄웁니다.
        if not fst_files:
            item = QStandardItem("🚫 .fst 파일이 없습니다.")
            item.setEnabled(False)
            item.setEditable(False)

            self.dir_tree_model.appendRow(item)
            return

        for file_name in sorted(fst_files):
            # 파일 각각의 온전한 절대 경로는 내부 데이터 영역(UserRole)에만 보관합니다.
            full_path = os.path.join(directory_path, file_name).replace('\\', '/')
            
            item = QStandardItem(f"📄 {file_name}")
            item.setData(full_path, Qt.UserRole)  # 향후 클릭 이벤트 처리용 경로 저장
            item.setEditable(False) 
    
            item.setBackground(QBrush(Qt.GlobalColor.transparent))
            item.setForeground(QBrush(Qt.GlobalColor.black))
            # 현재 등록하려는 파일의 절대경로(full_path)가 마지막 세션 파일(last_fst_path)과 완벽히 일치한다면?
            if last_fst_path and full_path.lower() == last_fst_path.replace('\\', '/').lower():
                # 🎨 마우스 클릭 스타일시트와 완전히 일치하는 연회색/진한회색 주입
                item.setBackground(QBrush(QColor("#D1D5DB")))      
                item.setForeground(QBrush(QColor("#374151")))      
                font = QFont()
                font.setBold(True)
                item.setFont(font)

            self.dir_tree_model.appendRow(item)

    def btn_change_dir_clicked(self):
        """ 📂 'Path 정보' 버튼을 눌러 새 디렉토리를 물리적으로 선택하는 함수 """
        # 기존 툴팁에서 기존 경로가 있다면 시작 위치로 재활용
        old_path = self.btn_change_dir.toolTip()
        initial_dir = old_path if old_path and os.path.exists(old_path) else ""

        # 사용자에게 폴더 선택 다이얼로그 출력
        selected_dir = QFileDialog.getExistingDirectory(self, "작업 디렉토리 선택", initial_dir)
        
        if selected_dir:
            # 1. 시스템 슬래시 스타일 통일
            selected_dir = selected_dir.replace('\\', '/')
            
            # 2. 버튼 텍스트 축소본으로 업데이트 및 툴팁 원본 저장
            shrunk_text = self.shrink_directory_path(selected_dir, max_len=100)
            self.btn_change_dir.setText(f"📂 {shrunk_text}")
            self.btn_change_dir.setToolTip(selected_dir)
            
            # 3. 해당 폴더 안의 모든 .fst 파일 리스트를 좌측 트리뷰에 업데이트
            self.update_dir_tree_list(selected_dir)

    @staticmethod
    def shrink_directory_path(path, max_len=50):
        """ 경로가 max_len을 넘으면 중간을 '...'으로 생략하는 함수 """
        if not path or len(path) <= max_len:
            return path
        
        # OS 구분자 기준 분할 (오픈패스트 특성상 슬래시 사용)
        parts = path.replace('\\', '/').split('/')
        
        # 드라이브명(앞)과 현재 폴더명(뒤) 결합
        head = parts[0] + "/" + parts[1] if len(parts) > 1 else parts[0]
        tail = parts[-1]
        
        # 글자수가 제한을 넘을 경우 중간 조합
        shrunk = f"{head}/.../{tail}"
        
        # 만약 생략한 결과도 너무 길다면 단순 글자수 자르기
        if len(shrunk) > max_len:
            return path[:max_len-3] + "..."
        return shrunk

    def __btn_fst_path_clicked(self, checked=False):
        """ 우측 디렉토리 트리뷰에서 마우스 클릭 이벤트를 안전하게 격리 및 OpenFAST 실행 """
        # QPushButton.clicked 시그널은 마우스 왼쪽 클릭일 때만 기본 트리거됩니다.
        if hasattr(self, 'dir_tree_list') and self.dir_tree_list is not None:
            # QCursor를 PySide6 환경에서 정상적으로 작동하도록 좌표 기록
            self._drag_start_position = self.dir_tree_list.mapFromGlobal(QCursor.pos())

        # 코어 엔진(OpenFastIO) 연동을 고려한 안전한 실행 처리
        try:
            # UI 동결(Freeze) 현상을 방지하기 위해 run_openfast_process가 내부적으로 QProcess나 비동기 쓰레드를 사용하는지 확인하는 것이 좋습니다.
            if hasattr(self, 'run_openfast_process'):
                self.run_openfast_process()
            else:
                # 혹시 함수명이 다르거나 없을 경우를 대비한 예외 처리 예시
                print("[경고] run_openfast_process 메서드를 찾을 수 없습니다.")
                
        except Exception as e:
            # 에러 발생 시 사용자에게 메시지 박스로 안내 (상단 PySide6 임포트 활용)
            QMessageBox.critical(self, "오류", f"OpenFAST 연산 실행 중 에러가 발생했습니다:\n{str(e)}")

    def btn_left_stop_clicked(self, checked=False):
        """ 우측 디렉토리 트리뷰에서 마우스 클릭 이벤트를 안전하게 격리 및 OpenFAST 실행 """
        print("Hellow ")




    def btn_left_run_clicked(self, checked=False):
        """ dir_tree_list에서 선택된 .fst 파일을 OpenFAST로 실행 """
        selected = self.dir_tree_list.selectedIndexes()
        if not selected:
            print("[Stop] 선택된 항목이 없습니다.")
            return

        item = self.dir_tree_model.itemFromIndex(selected[0])
        if not item:
            return

        fst_path = item.data(Qt.UserRole)
        if not fst_path or not os.path.exists(fst_path):
            print(f"[Stop] 파일이 존재하지 않습니다: {fst_path}")
            return

        # OpenFAST 실행 경로 (레지스트리 또는 환경변수에서 가져올 수 있음)
        settings = QSettings("JHLEE", "OFA")
        openfast_exe = settings.value("OpenFastExe", "")

        if not openfast_exe or not os.path.exists(openfast_exe):
            # 기본 경로 시도
            default_paths = [
                r"C:\OpenFAST\openfast.exe",
                r"C:\Program Files\OpenFAST\openfast.exe",
            ]
            for p in default_paths:
                if os.path.exists(p):
                    openfast_exe = p
                    break

        if not openfast_exe or not os.path.exists(openfast_exe):
            QMessageBox.critical(self, "OpenFAST 없음", "OpenFAST 실행 파일을 찾을 수 없습니다.")
            return

        try:
            self.process = subprocess.Popen([openfast_exe, fst_path], cwd=os.path.dirname(fst_path))
            print(f"[Stop] OpenFAST 실행: {fst_path}")
        except Exception as e:
            QMessageBox.critical(self, "실행 오류", f"OpenFAST 실행 실패:\n{str(e)}")
    

    def update_model_tree_view(self, fst_file_path):
        """ 우측 트리뷰 채우는 최종 연동 함수 """
        # 1. 우측 트리뷰 장부 깔끔하게 비우기
        self.model_tree_model.clear()
        
        if not fst_file_path or not os.path.exists(fst_file_path):
            return

        # 2. 레지스트리 세션 복구 및 메인 타이틀 업데이트
        settings = QSettings("JHLEE", "OFA")
        settings.setValue("LastFstPath_fst", fst_file_path)

        if hasattr(self, 'main_window') and self.main_window:
            file_name = os.path.basename(fst_file_path)
            self.main_window.setWindowTitle(f"OFA : [{file_name}]")

        try:
            # 제공해주신 클래스 메서드를 직통 호출하여 파싱 완료된 전체 최신 데이터 장부 획득
            config = OpenFastIO.update_config_from_fst(fst_file_path)
        except Exception as e:
            self.cmd_output.append(f"❌ 설정 파일 연쇄 파싱 실패: {str(e)}\n")
            return

        # Main .fst 파일을 트리 내부의 유일한 최상위 루트 노드로 지정합니다.
        main_root_item = QStandardItem(f"📁 Main \t: {fst_file_path}")
        main_root_item.setEditable(False)
        self.model_tree_model.appendRow(main_root_item)
        
        # 모듈 노드를 최상위가 아닌 'main_root_item'의 자식으로 등록하는 헬퍼 함수
        def add_module_item(display_name, file_name, base_path):
            abs_path = OpenFastIO.get_absolute_path(base_path, file_name)
            item = QStandardItem(f"📁 {display_name:<8} : {abs_path}")
            item.setEditable(False)
            main_root_item.appendRow(item) # 최상위 장부가 아닌 main_root_item 산하 자식으로 등록
            return item, abs_path

        def get_val(key):
            return config.get(key, {}).get("current") or config.get(key, {}).get("default", "")

        # =================================================================
        # [1] ElastoDyn & BeamDyn 구역 (다단 계층 완벽 교정)
        # =================================================================
        comp_elast = int(get_val("CompElast") or 0)
        
        if comp_elast == 1 or comp_elast == 2:
            ed_file = get_val("EDFile")
            # Main 산하에 Elasto 모듈 노드 등록
            ed_item, ed_abs_path = add_module_item("Elasto", ed_file, fst_file_path)
            
            # ElastoDyn 모드: Elasto 노드 바로 아래에 3개의 Blade 배치
            if comp_elast == 1:
                for num in range(1, 4):
                    bld_file = get_val(f"BldFile({num})")
                    if bld_file:
                        bld_path = OpenFastIO.get_absolute_path(ed_abs_path, bld_file)
                        child = QStandardItem(f"📁 BldFile({num}) \t: {bld_path}")
                        child.setEditable(False)
                        ed_item.appendRow(child)

            # BeamDyn 모드: Main -> Elasto -> Beam(num) -> BldFile 형태로 깊이 확장
            elif comp_elast == 2:
                for num in range(1, 4):
                    bdbld_file = get_val(f"BDBldFile({num})")
                    if bdbld_file:
                        bd_path = OpenFastIO.get_absolute_path(ed_abs_path, bdbld_file)
                        bd_item = QStandardItem(f"📁 Beam({num})  \t: {bd_path}")
                        bd_item.setEditable(False)
                        ed_item.appendRow(bd_item)  # Elasto 노드의 자식으로 안착

                        # Beam 하위의 개별 BldFile 추적 (각 Beam 파일 경로 기준 해석)
                        bld_file = get_val("BldFile")
                        if bld_file:
                            bld_path = OpenFastIO.get_absolute_path(bd_path, bld_file)
                            child = QStandardItem(f"📁 BldFile   \t: {bld_path}")
                            child.setEditable(False)
                            bd_item.appendRow(child) # Beam 노드의 자식으로 안착

        # =================================================================
        # [2] AeroDyn 구역
        # =================================================================
        comp_aero = int(get_val("CompAero") or 0)
        if comp_aero > 0:
            ae_file = get_val("AeroFile")
            ae_item, ae_abs_path = add_module_item("Aero", ae_file, fst_file_path)
            
            for num in range(1, 4):
                adbl_file = get_val(f"ADBlFile({num})")
                if adbl_file:
                    al_path = OpenFastIO.get_absolute_path(ae_abs_path, adbl_file)
                    child = QStandardItem(f"📁 ADBlFile({num}) \t: {al_path}")
                    child.setEditable(False)
                    ae_item.appendRow(child)

            af_lists = config.get("AFFileList", {}).get("current", [])
            if isinstance(af_lists, list):
                for num, af_list in enumerate(af_lists, start=1):
                    child = QStandardItem(f"📁 Air Foil({num}) \t: {af_list}")
                    child.setEditable(False)
                    ae_item.appendRow(child)

        # =================================================================
        # [3] ServoDyn 구역
        # =================================================================
        comp_servo = int(get_val("CompServo") or 0)
        if comp_servo > 0:
            servo_file = get_val("ServoFile")
            sv_item, sv_abs_path = add_module_item("Servo", servo_file, fst_file_path)
            
            dll_file = get_val("DLL_FileName")
            if dll_file:
                dll_path = OpenFastIO.get_absolute_path(sv_abs_path, dll_file)
                child = QStandardItem(f"📁 DLL_File   \t: {dll_path}")
                child.setEditable(False)
                sv_item.appendRow(child)

        # =================================================================
        # [4] 나머지 독립형 단일 모듈 라인업 (Main의 바로 아래 자식들)
        # =================================================================
        independent_modules = [
            ("CompInflow", "InflowFile", "Inflow"),
            ("CompSeaSt", "SeaStFile", "SeaSt"),
            ("CompHydro", "HydroFile", "Hydro"),
            ("CompSub", "SubFile", "Sub"),
            ("CompMooring", "MooringFile", "Mooring"),
            ("CompIce", "IceFile", "Ice"),
            ("CompSoil", "SoilFile", "Soil")
        ]

        for comp_key, file_key, display_name in independent_modules:
            comp_val = int(get_val(comp_key) or 0)
            if comp_val > 0:
                f_name = get_val(file_key)
                if f_name:
                    add_module_item(display_name, f_name, fst_file_path)

        # =================================================================
        # ⚡ [트리 화살표 및 초기 접힘 상태 제어 교정]
        # =================================================================
        self.model_tree_view.setRootIsDecorated(True)
        self.model_tree_view.setIndentation(20) 
        
        # 💡 최상위 Main 노드 하위만 처음에 깔끔하게 노출되도록 전체 대기 정렬
        self.model_tree_view.collapseAll()
        
        # 💡 첫 실행 시 유저가 Main의 존재를 바로 볼 수 있게 Main 루트만 한 단계 확장해 둡니다.
        first_index = self.model_tree_model.index(0, 0)
        self.model_tree_view.expand(first_index)

    def __load_fst_file_(self, file_path):
        self.model_tree_model.clear()
        
        # 주소를 Computer Registry에 저장
        settings = QSettings("JHLEE", "OFA")
        settings.setValue("LastFstPath_fst", file_path)

        # [추가] 파일명 추출 후 메인 윈도우 타이틀 업데이트
        if hasattr(self, 'main_window') and self.main_window:
            file_name = os.path.basename(file_path)
            self.main_window.setWindowTitle(f"OFA : [{file_name}]")
           
        root_item = QStandardItem(f"📁 Main \t: {file_path}")
        self.model_tree_model.appendRow(root_item)
        
        config = OpenFastIO.update_config_from_fst(file_path)

        module = "CompElast"                
        comp_elast = int( config[module]["current"] or config[module]["default"] )
        if comp_elast == 1 or comp_elast == 2:
            ed_file = config["EDFile"]["current"] or config["EDFile"]["default"]
            ed_path = OpenFastIO.get_absolute_path(file_path, ed_file)     
            ed_item = QStandardItem(f"📁 Elasto  \t: {ed_path}")
            
            for num in range(1, 4):
                bl_file = config[f"BldFile({num})"]["current"] or config[f"BldFile({num})"]["default"]
                bl_path = OpenFastIO.get_absolute_path(ed_path, bl_file)
                ed_item.appendRow(QStandardItem(f"📁 BldFile({num}) \t: {bl_path}"))

            root_item.appendRow(ed_item)

        if comp_elast == 2:
            bd_file = config["BDBldFile(1)"]["current"] or config["BDBldFile(1)"]["default"]
            bd_path = OpenFastIO.get_absolute_path(file_path, bd_file)         
            bd_item = QStandardItem(f"📁 Beam    \t: {bd_path}")
            
            for num in range(1, 2):
                bl_file = config["BldFile"]["current"] or config["BldFile"]["default"]
                bl_path = OpenFastIO.get_absolute_path(bd_path, bl_file)
                bd_item.appendRow(QStandardItem(f"📁 BldFile \t\t: {bl_path}"))

            root_item.appendRow(bd_item)

        module = "CompAero"  
        comp_aero = int( config[module]["current"] or config[module]["default"] )
        if comp_aero > 0:
            ae_file = config["AeroFile"]["current"] or config["AeroFile"]["default"]
            ae_path = OpenFastIO.get_absolute_path(file_path, ae_file)            
            ae_item = QStandardItem(f"📁 Aero   \t: {ae_path}")
            
            for num in range(1, 4):
                ad_file = config[f"ADBlFile({num})"]["current"] or config[f"ADBlFile({num})"]["default"]
                al_path = OpenFastIO.get_absolute_path(ae_path, ad_file)
                ae_item.appendRow(QStandardItem(f"📁 ADBlFile({num}) \t: {al_path}"))

            af_lists = config["AFFileList"]["current"]
            if isinstance(af_lists, list):
                for num, af_list in enumerate(af_lists, start=1):
                    ae_item.appendRow(QStandardItem(f"📁 Air Foil({num}) \t: {af_list}"))          

            root_item.appendRow(ae_item)

        module = "CompServo"  
        comp_servo = int( config[module]["current"] or config[module]["default"] )
        if comp_servo > 0:
            servo_file = config["ServoFile"]["current"] or config["ServoFile"]["default"]
            servo_path = OpenFastIO.get_absolute_path(file_path, servo_file)            
            servo_item = QStandardItem(f"📁 Servo   \t: {servo_path}")
            
            for num in range(1, 2):
                file = config[f"DLL_FileName"]["current"] 
                path = OpenFastIO.get_absolute_path(servo_path, file)
                servo_item.appendRow(QStandardItem(f"📁 DLL_FileName   \t: {path}"))    

            root_item.appendRow(servo_item)

        module = "CompSeaSt"  
        comp_seast = int( config[module]["current"] or config[module]["default"] )
        if comp_seast > 0:
            seast_file = config["SeaStFile"]["current"] or config["SeaStFile"]["default"]
            seast_path = OpenFastIO.get_absolute_path(file_path, seast_file)            
            seast_item = QStandardItem(f"📁 SeaSt    \t: {seast_path}")  

            root_item.appendRow(seast_item)

        module = "CompHydro"  
        comp_hydro = int( config[module]["current"] or config[module]["default"] )
        if comp_hydro > 0:
            hydro_file = config["HydroFile"]["current"] or config["HydroFile"]["default"]
            hydro_path = OpenFastIO.get_absolute_path(file_path, hydro_file)            
            hydro_item = QStandardItem(f"📁 Hydro   \t: {hydro_path}")  

            root_item.appendRow(hydro_item)

        module = "CompSub"  
        comp_sub = int( config[module]["current"] or config[module]["default"] )
        if comp_sub > 0:
            sub_file = config["SubFile"]["current"] or config["SubFile"]["default"]
            sub_path = OpenFastIO.get_absolute_path(file_path, sub_file)            
            sub_item = QStandardItem(f"📁 Sub \t: {sub_path}")  

            root_item.appendRow(sub_item)

        module = "CompMooring"  
        comp_moor = int( config[module]["current"] or config[module]["default"] )
        if comp_moor > 0:
            moor_file = config["MooringFile"]["current"] or config["MooringFile"]["default"]
            moor_path = OpenFastIO.get_absolute_path(file_path, moor_file)            
            moor_item = QStandardItem(f"📁 Mooring\t: {moor_path}")  

            root_item.appendRow(moor_item)

        module = "CompIce"  
        comp_ice = int( config[module]["current"] or config[module]["default"] )
        if comp_ice > 0:
            ice_file = config["IceFile"]["current"] or config["IceFile"]["default"]
            ice_path = OpenFastIO.get_absolute_path(file_path, ice_file)            
            ice_item = QStandardItem(f"📁 Ice \t: {ice_path}")  

            root_item.appendRow(ice_item)

        module = "CompSoil"  
        comp_soil = int( config[module]["current"] or config[module]["default"] )
        if comp_soil > 0:
            soil_file = config["SoilFile"]["current"] or config["SoilFile"]["default"]
            soil_path = OpenFastIO.get_absolute_path(file_path, soil_file)            
            soil_item = QStandardItem(f"📁 Soil \t: {soil_path}")  

            root_item.appendRow(soil_item)

        self.model_tree_view.collapseAll()
        self.model_tree_view.expandToDepth(0)

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
                    self.update_model_tree_view(drop_file_path)

            if not current_main or current_main == drop_file_path:
                self.update_model_tree_view(drop_file_path)

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
                self.update_model_tree_view(current_main)

    def on_model_tree_press_event(self, event):
        """ 마우스 클릭 시 클릭한 위치와 항목을 기억하는 함수 """
        if event.button() == Qt.LeftButton:
            self._drag_start_position = event.position().toPoint()
        # 원래 QTreeView의 기본 마우스 클릭 동작도 함께 수행합니다.
        QTreeView.mousePressEvent(self.model_tree_view, event)

    def on_model_tree_move_event(self, event):
        """ 마우스를 누른 채 일정 거리 이상 움직이면 외부로 드래그를 시작하는 함수 """
        if not (event.buttons() & Qt.LeftButton):
            return
        current_pos = event.position().toPoint()
        if (current_pos - self._drag_start_position).manhattanLength() < QApplication.startDragDistance():
            return

        # 현재 마우스로 붙잡은 트리 아이템 가져오기
        index = self.tree_view.indexAt(current_pos)
        if not index.isValid():
            return

        item = self.tree_model.itemFromIndex(index)
        text = item.text()

        # 실제 파일 경로만 분리해냅니다.
        if "\t:" in text:
            file_path = text.split("\t:")[1].strip()
            
            # 실제 컴퓨터에 존재하는 파일인 경우에만 드래그를 시작합니다.
            if os.path.exists(file_path):
                from PySide6.QtCore import QMimeData, QUrl
                from PySide6.QtGui import QDrag
                
                # 윈도우 OS 시스템에 파일 경로 데이터 등록 (가장 중요)
                mime_data = QMimeData()
                mime_data.setUrls([QUrl.fromLocalFile(file_path)])
                
                drag = QDrag(self.tree_view)
                drag.setMimeData(mime_data)

                from PySide6.QtWidgets import QStyle
                # 시스템 표준 파일 아이콘을 큼직한 크기(48x48)로 가져와 마우스에 붙임
                pixmap = self.tree_view.style().standardIcon(QStyle.SP_FileIcon).pixmap(48, 48)
                drag.setPixmap(pixmap)                

                # 드래그 시 마우스 커서 모양을 복사(Copy) 형태로 지정하여 수행
                drag.exec(Qt.CopyAction)

    def on_model_tree_item_double_clicked(self, index):
    # """ 트리 항목을 더블 클릭했을 때 Notepad++로 파일을 여는 함수 """
        item = self.model_tree_model.itemFromIndex(index)
        if not item:
            return
            
        text = item.text()

        if " :" in text:
            file_path = text.split(" :")[1].strip()
        elif "\t:" in text:
            file_path = text.split("\t:")[1].strip()
        elif ":" in text:
            # 혹시나 예외 상황인 경우, 첫 번째 콜론 기준 오른쪽을 다 가져온 뒤 양끝 공백을 지웁니다.
            file_path = text.split(":", 1)[1].strip()
        else:
            return
            
        npp_path = r"C:\Program Files\Notepad++\notepad++.exe"
        
        if os.path.exists(file_path):
            try:
                subprocess.Popen([npp_path, file_path])
            except FileNotFoundError:
                subprocess.Popen(["notepad.exe", file_path])

    def on_model_tree_item_right_clicked(self, pos):
   # 트리 뷰 마우스 우클릭 팝업 메뉴 화면 처리 
        from PySide6.QtWidgets import QMenu
        from PySide6.QtGui import QAction

        # 현재 마우스 우클릭을 한 주소의 트리 아이템 인덱스 가져오기
        if not hasattr(self, 'model_tree_view') or self.model_tree_view is None:
            return

        index = self.model_tree_view.indexAt(pos)
        if not index.isValid():
            return # 빈 바탕을 눌렀다면 메뉴를 띄우지 않고 취소

        item = self.model_tree_model.itemFromIndex(index)
        full_text = item.text()

        # "📁 모듈명    : C:/path/file.dat" 형태에서 실제 파일 절대 경로만 깔끔하게 추출
        if " : " in full_text:
            text = full_text.split(" : ", 1)[1].strip()
        else:
            text = full_text.strip()

        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #FFFFFF;
                border: 1px solid #CCCCCC;
                padding: 5px;
                font-size: 13px;
            }
            QMenu::item {
                padding: 5px 20px;
                background-color: transparent;
            }
            QMenu::item:selected {
                background-color: #1E40AF;
                color: #FFFFFF;
            }
            QMenu::separator {
                height: 1px;               /* 구분선 두께 */
                background-color: #D1D5DB; /* 구분선 색상 (연한 회색) */
                margin-top: 4px;           /* 위쪽 여백 */
                margin-bottom: 4px;        /* 아래쪽 여백 */
            }                         
        """)

        # 마우스 우클릭 시 띄워줄 저장 옵션 액션(메뉴 아이템) 선언
        open_directory_action = QAction("📁 Open Directory", self)
        export_text_action = QAction("📋 파일 절대 경로 텍스트 복사", self)

        save_project_action = QAction("💾 Project Files Deep 복사/저장하기", self)
        save_runfile_action = QAction("💾 Project Files Soft 복사/저장하기", self)
        save_as_action = QAction("📝 다른 이름으로 저장하기...", self)

        run_openfast_action = QAction("▶️ OpenFAST 실행하기", self)
        run_multi_case_action = QAction("▶️ Multi-Case 실행하기", self)

        menu.addAction(open_directory_action)
        menu.addAction(export_text_action)
        menu.addSeparator() # Separator line     
        menu.addAction(save_project_action)
        menu.addAction(save_runfile_action)
        menu.addAction(save_as_action)
        menu.addSeparator() # Separator line 
        menu.addAction(run_openfast_action)
        menu.addAction(run_multi_case_action)

        open_directory_action.triggered.connect(lambda:  self.mouse_Rclick_open_directory(text))
        save_project_action.triggered.connect(lambda:    self.mouse_Rclick_save_project_hard(text))
        save_runfile_action.triggered.connect(lambda:    self.mouse_Rclick_save_project_soft(text))       
        save_as_action.triggered.connect(lambda:         self.mouse_Rclick_save_file(text))
        export_text_action.triggered.connect(lambda:     print(f"[선택] 절대 경로 복사 target: {text}"))
        run_openfast_action.triggered.connect(lambda:    self.mouse_Rclick_run_openfast(text))
        run_multi_case_action.triggered.connect(lambda: self.mouse_Rclick_run_multi_case(text))
        

        menu.exec(self.model_tree_view.mapToGlobal(pos))  # 마우스가 클릭된 전역 좌표(화면 기준 주소)에 메뉴판 오픈



    def run_openfast_process(self, func_name=""):
        """ 함수명을 건네받아 해당 함수에 따라 하나 또는 여러 개의 OpenFAST를 실행합니다."""
  
        # 1. OpenFAST 실행 파일 경로 확인
        settings = QSettings("JHLEE", "OFA")
        openfast_exe = settings.value("LastOpenFastPath", "")

        if not openfast_exe or not os.path.exists(openfast_exe):
            QMessageBox.critical(self, "OpenFAST 없음", "OpenFAST 실행 파일을 찾을 수 없습니다.")
            return

        # 2. 함수명에 따라 실행할 .fst 파일 목록(list) 결정
        fst_paths = []
        
        if func_name == "main_tab" and hasattr(self.main_window, 'pane_main'):
            path = OpenFastIO.current_config.get("MainFST", {}).get("current", "")
            if path:
                fst_paths.append(path)
                
        elif func_name == "wind_tab" and hasattr(self.main_window, 'pane_wind'):
            # wind_tab에서 .fst 경로를 가져오는 로직 (필요시 구현)
            pass
            
        else:
            # 기본: dir_tree_list에서 선택된 '모든' 파일 가져오기
            selected_indexes = self.dir_tree_list.selectedIndexes()
            # QTreeView의 경우 컬럼 수만큼 인덱스가 중복될 수 있으므로 행(row) 기준으로 고유값 필터링
            unique_rows = set()
            for index in selected_indexes:
                # 0번 컬럼 기준으로 고유 행 식별
                row_key = (index.row(), index.parent())
                if row_key not in unique_rows:
                    unique_rows.add(row_key)
                    item = self.dir_tree_model.itemFromIndex(index)
                    if item:
                        path = item.data(Qt.UserRole)
                        if path:
                            fst_paths.append(path)

        # 유효한 파일 필터링 및 존재 여부 검증
        valid_fst_paths = [p for p in fst_paths if p and os.path.exists(p)]

        if not valid_fst_paths:
            QMessageBox.warning(self, "파일 없음", "실행할 유효한 .fst 파일을 하나 이상 선택하거나 설정하세요.")
            return

        # 3. 파일 목록을 순회하며 비동기 프로세스 개별 실행
        last_started_path = None
        
        for fst_path in valid_fst_paths:
            working_dir = os.path.dirname(fst_path)
            file_name = os.path.basename(fst_path)

            print(f"[실행] OpenFAST 비동기 구동 시도: {fst_path} ")

            try:
                process = QProcess(self)
                process.setWorkingDirectory(working_dir)
                
                self.process_logs[fst_path] = f"⏳ [Start] Simulation Started for: {file_name}\n"
                
                # 람다식 매핑 연결 (각 fst_path가 고유하게 캡처됨)
                process.readyReadStandardOutput.connect(lambda p=process, path=fst_path: self.handle_ready_read(p, path))
                process.readyReadStandardError.connect(lambda p=process, path=fst_path: self.handle_ready_read(p, path))
                process.finished.connect(lambda exit_code, exit_status, path=fst_path: self.handle_process_finished(path))

                # 상대경로 유지 구동
                process.start(openfast_exe, [file_name])

                if hasattr(self, 'process_tree_list') and self.process_tree_list is not None:
                    status_item = QStandardItem(f"🟢 {file_name} (실행중...)")
                    status_item.setEditable(False)
                    status_item.setData(fst_path, Qt.ItemDataRole.UserRole)
                    self.process_tree_list.appendRow(status_item)
                    self.running_processes.append((process, fst_path, status_item))
                
                last_started_path = fst_path
                print(f"✅ 프로세스 백그라운드 러닝 진입 성공: {file_name}")

            except Exception as e:
                QMessageBox.critical(self, "실행 실패", f"OpenFAST 구동 중 시스템 예외가 발생했습니다.\n파일: {file_name}\n사유: {e}")

        # 4. 공통 UI 제어 (최소 하나 이상 실행 성공 시)
        if last_started_path:
            if hasattr(self, 'btn_stop_fast') and self.btn_stop_fast:
                self.btn_stop_fast.setEnabled(True)
                
            # UI 로그 뷰어에는 가장 마지막으로 실행 시작된 파일의 로그를 우선 표시
            self.current_viewing_path = last_started_path
            self.cmd_output.setText(self.process_logs[last_started_path])


    def stop_openfast_process(self):
        """ 🛑 'Stop' 버튼 클릭 시, 에러로 멈춘 유령 CMD 창까지 포함하여 강제 파괴하는 철벽 대응 함수 """
        if not hasattr(self, 'running_processes') or not self.running_processes:
            QMessageBox.information(self, "안내", "현재 실행 중인 CMD 시뮬레이션 창이 없습니다.")
            return

        # 💡 [핵심 변경] poll()이 None인 것뿐만 아니라, 리스트에 등록된 모든 프로세스 시도를 검사 대상에 포함합니다.
        # 이미지처럼 FATAL ERROR로 멈춘 창은 poll() 결과가 꼬일 수 있으므로 등록된 전체 개수를 기준 잡습니다.
        total_count = len(self.running_processes)

        reply = QMessageBox.question(
            self, "전체 작업 중단", 
            f"현재 구동 및 에러로 인해 화면에 남아있는 모든 OpenFAST CMD 창({total_count}개)과\n"
            "내부 연산 엔진을 강제로 완전히 청소하시겠습니까?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                # 리스트에 기록된 모든 Popen 프로세스를 예외 없이 순회합니다.
                for process, path in self.running_processes:
                    pid = process.pid  # 프로세스 고유 ID 추출
                    
                    # 💡 .poll() 상태와 관계없이 윈도우 커널 레벨에서 taskkill을 강제 집행합니다.
                    # 이미 죽은 프로세스라면 무시되고, 에러로 멈춰있는 유령 프로세스는 이 명령어로 확실히 사살됩니다.
                    subprocess.run(
                        ["taskkill", "/F", "/T", "/PID", str(pid)], 
                        stdout=subprocess.DEVNULL, 
                        stderr=subprocess.DEVNULL,
                        creationflags=subprocess.CREATE_NO_WINDOW
                    )
                
                self.cmd_output.append(f"\n❌ [Stop] {total_count} OpenFAST Process was Terminated.")
                
            except Exception as e:
                self.cmd_output.append(f"\n⚠️ [오류] 프로세스 완전 강제 종료 중 예외 발생: {e}")

            # 💡 [중요] 연산 창들을 커널 레벨에서 밀어버렸으므로, 파이썬 내부 관리 백업 리스트를 깨끗하게 비웁니다.
            self.running_processes.clear()
            self.btn_stop_fast.setEnabled(False)

    def btn_left_run_clicked(self, checked=False):
        """ Run 버튼: dir_tree_list 선택 파일로 OpenFAST 실행 """
        self.run_openfast_process("")

    def btn_left_stop_clicked(self, checked=False):
        """ Stop 버튼: 실행 중인 OpenFAST 프로세스 종료 """
        self.stop_openfast_process("")


    @staticmethod
    def _render_log(raw):
        """ OpenFAST 진행률 출력(\\r)을 터미널처럼 같은 줄 덮어쓰기로 정리 """
        out = []
        for line in raw.replace('\\r\\n', '\\n').split('\\n'):
            segs = line.split('\\r')
            out.append(segs[-1] if segs else '')
        text = '\\n'.join(out)
        if text.endswith('\\n'):
            text = text[:-1]
        return text

    def _append_log(self, text):
        """ cmd 출력창에 추가하되, \\r 진행률은 같은 줄을 덮어쓰고 끝의 빈 줄은 제거 """
        from PySide6.QtGui import QTextCursor
        text = text.replace('\\r\\n', '\\n')
        cursor = self.cmd_output.textCursor()
        cursor.movePosition(QTextCursor.End)

        # 이전 청크가 \\r로 끝났으면 이번 첫 삽입은 현재 줄 맨 앞에서 덮어쓰기
        at_line_start = getattr(self, '_log_cr_pending', False)
        self._log_cr_pending = False

        for i, seg in enumerate(text.split('\\r')):
            if not seg:
                continue
            if i == 0 and at_line_start:
                cursor.movePosition(QTextCursor.StartOfLine)
                cursor.movePosition(QTextCursor.EndOfLine, QTextCursor.KeepAnchor)
                cursor.removeSelectedText()
            cursor.insertText(seg)

        # 이 청크가 \\r로 끝났으면 다음 청크 첫 삽입은 줄 맨 앞에서
        if text.endswith('\\r'):
            self._log_cr_pending = True

    def handle_ready_read(self, process, file_path):
        """ 📥 [실시간 로그 가로채기] 백그라운드 프로세스가 텍스트를 출력할 때마다 메모리에 누적 저장 """
        from PySide6.QtCore import QByteArray

        # 표준 출력(Stdout)과 에러 출력(Stderr) 버퍼에 쌓인 데이터를 유실 없이 각각 모두 수거
        stdout_bytes = process.readAllStandardOutput()
        stderr_bytes = process.readAllStandardError()

        # 두 버퍼의 데이터를 결합 (PySide6 QByteArray는 서로 더할 수 있습니다)
        combined_bytes = stdout_bytes + stderr_bytes
        if combined_bytes.isEmpty():
            return

        # 수집된 바이트 데이터를 문자열로 안전하게 디코딩
        raw_data = combined_bytes.data()
        try:
            text = raw_data.decode('utf-8')
        except UnicodeDecodeError:
            text = raw_data.decode('cp949', errors='ignore') # 윈도우 인코딩 예외 처리 안전망

        if not text:
            return

        # 진행률 파싱 -> 좌측 리스트 항목 갱신 (우측 출력은 원본 그대로 유지)
        m = PROGRESS_RE.search(text)
        if m:
            cur, total = int(m.group(1)), int(m.group(2))
            pct = (cur / total * 100) if total else 0
            file_name = os.path.basename(file_path)
            for _, fpath, item in getattr(self, 'running_processes', []):
                if fpath == file_path and item is not None:
                    item.setText(f"🟢 {file_name} ({pct:.0f} %)")
                    break

        # 전역 로그 장부에 실시간 텍스트 추가
        if file_path in self.process_logs:
            self.process_logs[file_path] += text
        else:
            self.process_logs[file_path] = text

        # 만약 사용자가 현재 '클릭해서 보고 있는' 프로세스의 로그라면 화면에도 실시간 중계
        if getattr(self, 'current_viewing_path', None) == file_path:
            self._append_log(text)

            # 로그가 추가되면 자동으로 스크롤바를 가장 최하단(최신 로그 위치)으로 밀어내기
            scrollbar = self.cmd_output.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())

    def handle_process_finished(self, file_path):
        """ ⚪ [프로세스 종료 리스너] 연산이 끝난 프로세스의 UI 상태를 변경 """
        from PySide6.QtCore import QProcess, Qt
        import os
        
        file_name = os.path.basename(file_path)
        
        # 로그 장부에 종료 라인 추가
        if file_path in self.process_logs:
            self.process_logs[file_path] += f"\n✅ [Finished] Process End : {file_name}\n"
            
        # 현재 화면에 떠있는 로그가 종료된 로그라면 완료 문구 표시
        if getattr(self, 'current_viewing_path', None) == file_path:
            self.cmd_output.setText(self._render_log(self.process_logs[file_path]))
            scrollbar = self.cmd_output.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())

        # 좌측 리스트 뷰에서 해당 파일을 찾아 상태를 (연산 완료)로 갱신
        if hasattr(self, 'process_tree_list') and self.process_tree_list is not None:
            for i in range(self.process_tree_list.rowCount()):
                item = self.process_tree_list.item(i)
                if item and item.data(Qt.ItemDataRole.UserRole) == file_path:
                    item.setText(f"⚪ {file_name} (연산 완료)")
                    break

        # 활성 프로세스 관리 리스트 동기화
        if hasattr(self, 'running_processes'):
            self.running_processes = [item for item in self.running_processes if item[0].state() == QProcess.ProcessState.Running]
            if not self.running_processes and hasattr(self, 'btn_stop_fast') and self.btn_stop_fast:
                self.btn_stop_fast.setEnabled(False)

    def on_process_item_clicked(self, index):
        """ 🎯 [Process List 클릭 이벤트] 리스트에서 항목을 선택하면 보관 중이던 전역 로그를 QTextEdit에 표출 """
        from PySide6.QtCore import Qt
        
        # 클릭한 아이템 객체 획득
        if not hasattr(self, 'process_tree_list') or self.process_tree_list is not None:
            item = self.process_tree_list.itemFromIndex(index)
        else:
            return
            
        if not item:
            return

        # 내부 메타데이터에서 고유 열쇠인 파일 절대경로 추출
        file_path = item.data(Qt.ItemDataRole.UserRole)
        if not file_path:
            return

        # 1. 현재 보고 있는 대상 경로를 변경
        self.current_viewing_path = file_path

        # 2. 로그 장부(process_logs)에서 해당 파일의 로그를 찾아 화면에 통째로 갱신
        if file_path in self.process_logs:
            self.cmd_output.setText(self._render_log(self.process_logs[file_path]))
        else:
            self.cmd_output.setText("💡 선택된 프로세스의 기록된 로그가 존재하지 않습니다.\n")

        # 3. 스크롤바를 가장 최신 로그 위치(맨 아래)로 자동 정렬
        scrollbar = self.cmd_output.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

            
    def mouse_Rclick_open_directory(self, text):
        """ 우클릭 메뉴에서 'Open Directory'를 선택했을 때 실제 폴더를 열어주는 함수 """
        # 💡 [교정] 이전 단계에서 text를 순수 경로로 정제해 보냈으므로, 문자열 검증 및 스플릿 로직이 필요 없습니다.
        if not text:
            return

        # 이미 순수 절대 경로 상태이므로 바로 디렉터리 경로만 추출합니다.
        dir_path = os.path.dirname(text)
        
        # 실제 존재하는 경로인지 체크 후 윈도우 파일 탐색기 열기
        if os.path.exists(dir_path):
            try:
                os.startfile(dir_path)
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Can't open directory! \n\n Reason: {e}")
        else:
            QMessageBox.warning(self, "Warning", f"No directory path was found! \n\n경로: {dir_path}")

    def mouse_Rclick_save_project_hard(self, text):
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
 
    def mouse_Rclick_save_project_soft(self, text):
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
            if hasattr(self, 'update_model_tree_view'):
                self.update_model_tree_view(final_new_fst_path)
                
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

    def mouse_Rclick_save_file(self, text):
        """ Save File with new name & update the tree path"""

        file_path_preset = text.split(":", 1)[1].strip()
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

    def mouse_Rclick_run_multi_case(self, text):
        """ [우클릭] '다중 케이스 실행' 선택 시 모달리스 설정 창을 띄웁니다. (로직은 multi_tab.py) """
        from src.ui.tabs_input.multi_tab import open_multi_case_window
        open_multi_case_window(self, text)
