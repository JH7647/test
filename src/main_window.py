import os
import sys
import subprocess 
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QTabWidget, QLabel, QTreeView
from PySide6.QtWidgets import QMessageBox, QFileDialog
from PySide6.QtCore import Qt,QSettings 
from PySide6.QtGui import QStandardItemModel, QStandardItem
from PySide6.QtCore import QProcess

# 모듈별 분리된 컴포넌트 탭 임포트
from src.ui.tabs_input.main_tab import MainTab
from src.ui.tabs_input.files_tab import FilesTab
from src.ui.tabs_input.aero_tab import AeroTab
from src.ui.tabs_input.plot_tab import PlotTab
from src.core.openfast_io import OpenFastIO

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("OFA - OpenFAST Automation")
        self.resize(1100, 650)

        self.setAcceptDrops(True)   # 마우스 파일 드롭 허용

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # 마스터 탭 위젯 정의
        self.tab_widget = QTabWidget()
        
        # 탐색용 디렉토리 트리 구조 탭
        self.tab_files = QWidget()
        files_layout = QVBoxLayout(self.tab_files)
        self.tree_view = QTreeView()

        self.tree_view.setHeaderHidden(True)
        self.tree_model = QStandardItemModel()                              # 데이터를 담아줄 트리 모델 생성 및 연결
        self.tree_view.setModel(self.tree_model)

        files_layout.addWidget(self.tree_view)
        
        # 각 입력 제어부 독립 인스턴스 할당
        self.pane_files = FilesTab(main_window=self) 
        self.pane_main = MainTab(main_window=self)
        self.pane_aero = AeroTab()
        self.pane_plot = PlotTab()
        
        # 메인 프레임 레이아웃에 탭 순차 바인딩
        self.tab_widget.addTab(self.pane_files, "📁 Files")
        self.tab_widget.addTab(self.pane_main, "⚙️ Main")
        self.tab_widget.addTab(self.pane_plot, "📊 Plot Data")    
        self.tab_widget.addTab(self.pane_aero, "🦅 AeroDyn")    
        # self.tab_widget.addTab(self.tab_inflow, "💨 InFlow")
        # self.tab_widget.addTab(self.tab_elasto, "💪 Elasto")
        # self.tab_widget.addTab(self.tab_servo, "🔌 Servo")
        # self.tab_widget.addTab(self.tab_seast, "🌊 SeaSt")
        # self.tab_widget.addTab(self.tab_hydro, "⚓ Hydro")
        # self.tab_widget.addTab(self.tab_sub, "🏗️ Sub")
        # self.tab_widget.addTab(self.tab_mooring, "⛓️ Mooring")
        # self.tab_widget.addTab(self.tab_ice, "❄️ Ice")
        # self.tab_widget.addTab(self.tab_soil, "🌱 Soil")

        self.tab_widget.currentChanged.connect(self.on_tab_changed)

        placeholder_item = QStandardItem("💡여기에 .fst 파일을 마우스로 끌어다 놓으세요 (Drag & Drop)")
        self.tree_model.appendRow(placeholder_item)
        
        main_layout.addWidget(self.tab_widget)

        # Register the information : openFAST.exe path, last Main.fst file path 등등
        settings = QSettings("JHLEE", "OFA")
        last_fst_path = settings.value("LastFstPath_fst", "")
        if last_fst_path and os.path.exists(last_fst_path):
            self.pane_files.load_fst_file(last_fst_path)

    def is_simulation_running(self):
        """ 현재 프로그램 전체에서 OpenFAST가 실행 중인지 체크 """

        if hasattr(self, 'pane_main') and hasattr(self.pane_main, 'process'):
            if self.pane_main.process and self.pane_main.process.state() == QProcess.Running:
                return True
            
        return False
    
    def on_tab_changed(self, index):
        """ 사용자가 탭을 전환했을 때 자동으로 최신 .out 데이터를 로드하는 함수 """
        
        # 사용자가 클릭한 탭의 이름이 "📊 Plot Data" 인지 확인
        if self.tab_widget.tabText(index) == "📊 Plot Data":
            # 1. 현재 로드되어 시뮬레이션에 쓰인 .fst 파일 경로 가져오기
            fst_path = OpenFastIO.current_config.get("MainFST", {}).get("current", "").strip()
            
            if fst_path and os.path.exists(fst_path):
                # 2. .fst 확장자를 .out 확장자로 자동 변경하여 결과 파일 경로 예측
                # 예: C:/Test/Main.fst -> C:/Test/Main.out
                base_path, _ = os.path.splitext(fst_path)
                out_file_path = base_path + ".out"
                
                # 3. 만약 예측한 결과 파일(.out)이 실제로 물리적인 폴더 내에 존재한다면
                if os.path.exists(out_file_path):
                    # 4. 안전 검증 후 PlotTab의 파싱 함수를 다이렉트로 강제 호출 및 새로고침
                    if hasattr(self, 'pane_plot') and hasattr(self.pane_plot, 'load_output_data'):
                        self.pane_plot.load_output_data(out_file_path)
                else:
                    print(f"⚠️ [OFA 경고] 결과 파일이 존재하지 않아 로드할 수 없습니다")