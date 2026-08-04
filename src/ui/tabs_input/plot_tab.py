import os
import io

import pandas as pd
from PySide6.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QTreeView, QComboBox,
                             QLabel, QSplitter, QCheckBox, QRadioButton, QButtonGroup,
                             QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView, QGridLayout)
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMenu, QDialog  # QMenu, QDialog 추가
from PySide6.QtGui import QStandardItemModel, QStandardItem, QGuiApplication
from PySide6.QtWidgets import QMessageBox, QFileDialog, QTextEdit, QPushButton


from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.widgets import RectangleSelector

import matplotlib.pyplot as plt

from src.core.openfast_io import OpenFastIO  # 💡 코어 엔진 임포트

class PlotTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        # 구조: { file_title: (dataframe, columns_list) }
        self.data_dict = {} 

        # Drag & Drop 활성화
        self.setAcceptDrops(True)
        self.init_ui()

        self.check_and_load_default_data()

    def init_ui(self):
        # 메인 레이아웃 (좌우 분할)
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)
        
        splitter_main = QSplitter(Qt.Horizontal)

        # ================= [좌측 영역] 컨트롤 패널 =================
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)

        # 1. 상단 X축 선택 콤보박스
        x_layout = QHBoxLayout()
        x_layout.addWidget(QLabel("X-Axis:"))
        self.combo_x = QComboBox()
        self.combo_x.addItem("Time_[s]") # 초기 디폴트 값 표시
        self.combo_x.currentIndexChanged.connect(self.update_plot)
        x_layout.addWidget(self.combo_x)
        left_layout.addLayout(x_layout)

        # 2. Y축 변수 리스트 (향후 카테고라이징을 위해 QTreeView 사용)
        self.var_tree = QTreeView()
        self.var_tree.setHeaderHidden(True)
        self.var_tree.setIndentation(10)

        self.var_tree.setSelectionMode(QAbstractItemView.ExtendedSelection) 
        self.var_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.var_tree.customContextMenuRequested.connect(self.var_tree_context_menu)

        self.var_tree.setStyleSheet("""
            QTreeView::item {
                padding-left: 0px;
                margin-left: -4px;
            }
            QTreeView::branch {
                width: 12px; /* 화살표 영역 너비 제한 */
            }
        """)
        self.tree_model = QStandardItemModel()
        self.var_tree.setModel(self.tree_model)
        self.var_tree.setSelectionMode(QAbstractItemView.ExtendedSelection) # 다중 선택(Ctrl/Shift)
        self.var_tree.selectionModel().selectionChanged.connect(self.update_plot)
        
        # 초기 안내 문구 표시
        placeholder = QStandardItem("💡여기에 .out 파일을 드래그하세요")
        placeholder.setSelectable(False)
        self.tree_model.appendRow(placeholder)
        left_layout.addWidget(self.var_tree)

        splitter_main.addWidget(left_panel)

        # ================= [우측 영역] 그래프 & 하단 메뉴 패널 =================
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel) # 이미 레이아웃 생성됨
        right_layout.setContentsMargins(0, 0, 0, 0)

        splitter_right = QSplitter(Qt.Vertical)

        # 1. 상단 그래프 영역 (Matplotlib)
        self.fig, self.ax = plt.subplots()
        self.canvas = FigureCanvas(self.fig)

        self.canvas.setMouseTracking(True) 
        self.canvas.setContextMenuPolicy(Qt.CustomContextMenu)
        self.canvas.customContextMenuRequested.connect(self.mouseRclick_menu)
        self.canvas.mpl_connect('motion_notify_event', self.on_mouse_move)

        # 드래그 줌인을 위한 셀렉터 정의 (드래그 시 사각형 상자가 그려짐)
        self.selector = RectangleSelector(
            self.ax, self.on_draw_zoom,
            useblit=True,
            button=[1],  # 1번 버튼 = 마우스 왼쪽 클릭 드래그만 허용
            minspanx=5, minspany=5,  # 너무 미세한 드래그는 무시 (실수 방지)
            props=dict(facecolor='blue', edgecolor='blue', alpha=0.15, fill=True), # 선택 영역 색상
        )
              
        splitter_right.addWidget(self.canvas)
        
        # 초기 빈 화면 텍스트 안내
        self.ax.clear()
        self.ax.text(0.5, 0.5, "Plot the data", 
                     ha='center', va='center', fontsize=12, color='gray')
        self.ax.set_xticks([])
        self.ax.set_yticks([])
        
        splitter_right.addWidget(self.canvas)

        # 2. 하단 메뉴부 인터페이스 (입력 공간 준비)
        bottom_menu_widget = QWidget()
        bottom_layout = QVBoxLayout(bottom_menu_widget)
        bottom_layout.setContentsMargins(0, 5, 0, 0)

        # 2-A. 체크박스 및 옵션 컨트롤 레이아웃 (이미지 중간의 조작부 매칭)
        options_layout = QHBoxLayout()
        
        # 라디오 버튼 그룹 (Regular, PDF, FFT 등)
        radio_layout = QVBoxLayout()
        radio_layout.setSpacing(0)
        radio_layout.setContentsMargins(15, 0, 0, 0) 
        self.bg_mode = QButtonGroup(self)
        modes = ["Regular", "PDF", "FFT", "MinMax", "Compare", "Polar (beta)"]
        for i, mode in enumerate(modes):
            rb = QRadioButton(mode)
            if i == 0: rb.setChecked(True)
            rb.setStyleSheet("QRadioButton { padding-top: 1px; padding-bottom: 1px; margin: 0px; }")
            self.bg_mode.addButton(rb, i)
            radio_layout.addWidget(rb)
        radio_layout.addStretch()  
        options_layout.addLayout(radio_layout)

        # 중간 체크박스 구역 (Log-x, Log-y, Grid, CrossHair 등)
        chk_grid = QGridLayout()
        self.chk_logx = QCheckBox("Log-x")
        self.chk_logy = QCheckBox("Log-y")
        self.chk_grid = QCheckBox("Grid")
        self.chk_grid.setChecked(True)
        self.chk_cross = QCheckBox("CrossHair")
        self.chk_autoscale = QCheckBox("AutoScale")
        self.chk_autoscale.setChecked(True)
        self.chk_stepplot = QCheckBox("StepPlot")

        self.chk_grid.stateChanged.connect(self.update_plot)
        self.chk_logx.stateChanged.connect(self.update_plot)
        self.chk_logy.stateChanged.connect(self.update_plot)        
        self.chk_autoscale.stateChanged.connect(self.update_plot) 

        chk_grid.addWidget(self.chk_logx, 0, 0)
        chk_grid.addWidget(self.chk_logy, 0, 1)
        chk_grid.addWidget(self.chk_grid, 1, 0)
        chk_grid.addWidget(self.chk_cross, 1, 1)
        chk_grid.addWidget(self.chk_autoscale, 0, 2)
        chk_grid.addWidget(self.chk_stepplot, 1, 2)
        options_layout.addLayout(chk_grid)
        
        # 우측 좌표 출력용 레이블 공간 정보
        self.lbl_coords = QLabel("x = ---\ny = ---")
        self.lbl_coords.setStyleSheet("border: 1px solid lightgray; padding: 5px; background: #f9f9f9;")
        self.lbl_coords.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        options_layout.addWidget(self.lbl_coords)
        
        # 마우스가 그래프 위에서 움직일 때 좌표를 계산하는 함수 연결
        self.canvas.mpl_connect('motion_notify_event', self.on_mouse_move)

        bottom_layout.addLayout(options_layout)

        # 2-B. 최하단 통계 테이블 (Min, Max, Range 등)
        self.stats_table = QTableWidget(1, 6)
        self.stats_table.setHorizontalHeaderLabels(["Min", "Max", "Range", "dx", "xRange", "n"])
        self.stats_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.stats_table.setMaximumHeight(50)
        bottom_layout.addWidget(self.stats_table)

        splitter_right.addWidget(bottom_menu_widget)
        
        # 우측 스플리터 비율 조정 (그래프 대 메뉴 비율 7:3)
        splitter_right.setSizes([550, 120])

        right_layout.addWidget(splitter_right)
        splitter_main.addWidget(right_panel)

        # 좌측 25%, 우측 75% 비율 설정
        splitter_main.setSizes([250, 850])
        main_layout.addWidget(splitter_main)

    def on_tab_enter(self):
        """ Plot Data 탭 진입 시 최신 결과 파일 자동 로드 """
        self.check_and_load_default_data()

    def check_and_load_default_data(self):
        """ OpenFastIO의 current_config 정보를 기반으로 자동 로딩을 수행합니다. """
        try:
            # 1. OpenFastIO에 현재 설정된 MainFST 파일 경로가 있는지 확인
            fst_config = OpenFastIO.current_config.get("MainFST", {})
            fst_path = fst_config.get("current", "").strip()
            
            if not fst_path or not os.path.exists(fst_path):
                return  # .fst 파일 경로가 비어있거나 실제 존재하지 않으면 통과
                
            # 2. .fst 파일 이름의 확장자를 떼고 .out 또는 .txt 경로 조합
            base_path, _ = os.path.splitext(fst_path)
            out_candidate = base_path + ".out"
            txt_candidate = base_path + ".txt"
            
            # 3. .out 파일이 먼저 있는지 보고, 없으면 .txt 파일 확인 후 자동 로드
            if os.path.exists(out_candidate):
                print(f"[AutoLoad] 시뮬레이션 결과 자동 로드: {out_candidate}")
                self.load_output_data(out_candidate)
            elif os.path.exists(txt_candidate):
                print(f"[AutoLoad] 시뮬레이션 결과 자동 로드: {txt_candidate}")
                self.load_output_data(txt_candidate)
                
        except Exception as e:
            print(f"Error during auto-loading simulation data: {e}")


    def update_plot(self, *args):
        """ 변수 선택 시 우측 캔버스에 그래프를 실시간으로 그리는 함수 """
        if not self.data_dict:
            return

        # QTreeView에서 유저가 선택한 모든 행 인덱스 리스트 추출
        selected_indexes = self.var_tree.selectionModel().selectedRows()

        # 아무것도 선택되지 않았을 때 안내창 클리어
        if not selected_indexes:
            self.ax.clear()
            self.ax.text(0.5, 0.5, "Drop files or select variable(s) from the tree",
                         ha='center', va='center', fontsize=12, color='gray')
            self.ax.set_xticks([])
            self.ax.set_yticks([])
            self.canvas.draw()
            return

        self.ax.clear()
        x_col_text = self.combo_x.currentText()
        plotted_count = 0

        # 다중 선택된 인덱스들을 순회하며 멀티 파일 플롯 렌더링 시작
        for index in selected_indexes:
            col_name = index.data(Qt.UserRole)         # 변수명
            file_title = index.data(Qt.UserRole + 1)   # 메타데이터에서 추출한 파일 식별자

            # 추출된 파일 식별자를 통해 data_dict에서 각 파일 고유의 DataFrame 탐색 매핑
            if file_title in self.data_dict:
                df, columns = self.data_dict[file_title]
                
                # 유효성 검사: 선택한 X축 이름이 해당 파일 데이터프레임 내에 존재하는지 체크
                target_x = x_col_text
                if target_x not in df.columns:
                    # 파일 간 열 규격이 깨질 경우 대비용 Time 자동 타협 보정 코드
                    time_cols = [c for c in columns if 'Time' in c]
                    target_x = time_cols[0] if time_cols else columns[0]

                if col_name in df.columns and col_name != target_x:
                    x_data = df[target_x]
                    y_data = df[col_name]
                    
                    # 💡 다중 파일 그래프 겹쳐 그릴 때 구분이 쉽도록 라벨 앞에 파일명 태그 추가
                    label_name = f"[{file_title}] {col_name}"
                    self.ax.plot(x_data, y_data, label=label_name, linewidth=1.5)
                    plotted_count += 1

        if plotted_count == 0:
            self.canvas.draw()
            return

        # UI 옵션 상태(Grid, Log 스케일) 동적 제어 반영
        self.ax.grid(self.chk_grid.isChecked())
        if self.chk_logx.isChecked(): self.ax.set_xscale('log')
        if self.chk_logy.isChecked(): self.ax.set_yscale('log')

        # 레이블 및 범례(Legend) 갱신 연동
        self.ax.set_xlabel(x_col_text)
        self.ax.set_ylabel("Values")
        self.ax.legend(loc="upper right")

        # 여백 조절 및 Qt 도화지 리렌더링
        self.fig.subplots_adjust(left=0.15, right=0.95, top=0.95, bottom=0.15)
        self.canvas.draw()


    def dragEnterEvent(self, event):
        "Drag & Drop 핸들러"
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            file_path = url.toLocalFile()
            if file_path.endswith('.out') or file_path.endswith('.txt'):
                self.load_output_data(file_path)

    def load_output_data(self, file_path):
        "데이터 파싱 및 로드"
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()

            # OpenFAST .out 형식의 헤더 줄 찾기
            header_idx = -1
            for i, line in enumerate(lines[:10]):
                if line.strip().startswith('Time'):
                    header_idx = i
                    break

            if header_idx == -1:
                return

            # 컬럼명과 단위 결합해서 pyDatView 형태로 제작
            raw_cols = lines[header_idx].strip().split()
            raw_units = lines[header_idx + 1].strip().split()
            
            columns = []
            for col, unit in zip(raw_cols, raw_units):
                columns.append(f"{col}_{unit}")

            # 데이터프레임 빌드
            df = pd.read_csv(file_path, skiprows=header_idx+2, sep=r'\s+', names=columns, header=None)

            base_name = os.path.basename(file_path)
            file_title = os.path.splitext(base_name)[0]

            # 💡 [변경] 기존 단일 변수 오버라이트 대신 딕셔너리에 파일별 테이블 누적 저장
            self.data_dict[file_title] = (df, columns)

            # 컴포넌트 전체 화면 동기화
            self.update_ui_components()

        except Exception as e:
            print(f"Error parsing out file: {e}")

    def update_ui_components(self, file_path=None):
        """ 다중 파일 적재 상태를 기반으로 트리구조와 X축 콤보박스를 갱신 """
        if not self.data_dict:
            return

       # X축 콤보박스는 가장 최근에 드롭/추가된 파일의 컬럼 리스트 기준으로 갱신
        latest_file_title = list(self.data_dict.keys())[-1]
        _, latest_columns = self.data_dict[latest_file_title]

        self.combo_x.blockSignals(True)
        current_x = self.combo_x.currentText()
        self.combo_x.clear()
        self.combo_x.addItems(latest_columns)
        
        # 기존에 사용자가 선택 중이던 X축이 있으면 유지 처리
        if current_x in latest_columns:
            self.combo_x.setCurrentText(current_x)
        else:
            time_col = [c for c in latest_columns if 'Time' in c]
            if time_col:
                self.combo_x.setCurrentText(time_col[0])
            else:
                self.combo_x.setCurrentIndex(0)
        self.combo_x.blockSignals(False)

        # 좌측 트리뷰 리셋 후 적재된 모든 파일을 그룹화하여 계층형 트리 빌드
        self.tree_model.clear()
        
        for file_title, (df, columns) in self.data_dict.items():
            # 부모 폴더 노드 생성: 확장자 제외 파일 이름 주입
            root_item = QStandardItem(f"📁 {file_title} ({len(columns)})")
            root_item.setSelectable(True)
            root_item.setData(file_title, Qt.UserRole + 1)
            self.tree_model.appendRow(root_item)

            for col in columns:
                var_item = QStandardItem(col)
                # 변수를 클릭할 때 부모가 누구인지 추적할 수 있도록 파일명을 데이터 롤(+1)
                var_item.setData(col, Qt.UserRole)              # 역할 1: 고유 컬럼명
                var_item.setData(file_title, Qt.UserRole + 1)   # 역할 2: 소속 부모 파일명
                root_item.appendRow(var_item)
            
        self.var_tree.expandAll()


    def on_draw_zoom(self, eclick, erelease):
        """ 마우스 왼쪽 드래그로 줌인할 때 호출되는 함수 """
        x1, y1 = eclick.xdata, eclick.ydata
        x2, y2 = erelease.xdata, erelease.ydata
        
        # 실제 그래프 영역 밖을 드래그한 경우 무시
        if x1 is None or x2 is None or y1 is None or y2 is None:
            return
            
        # 미세하게 클릭만 한 경우(실수) 줌인 방지
        if abs(x1 - x2) < 0.01 or abs(y1 - y2) < 0.01:
            return

        # 1. 축 범위 강제 수동 설정 (줌인)
        self.ax.set_xlim(min(x1, x2), max(x1, x2))
        self.ax.set_ylim(min(y1, y2), max(y1, y2))
        
        # 2. 오토스케일 상태 끄기
        self.ax.set_autoscale_on(False)
        
        # 3. 신호 충돌 방지를 위해 잠시 차단 후 체크박스 해제
        self.chk_autoscale.blockSignals(True)
        self.chk_autoscale.setChecked(False)
        self.chk_autoscale.blockSignals(False)
        
        self.canvas.draw()

    # ================= ✨ [새로 추가] 마우스 커서 좌표 출력 =================
    def on_mouse_move(self, event):
        """ 마우스 커서가 그래프 위에 있을 때 실시간으로 X, Y 좌표를 레이블에 표시합니다. """
        # 마우스가 실제 그래프 좌표축(Axes) 안에 들어와 있는지 확인
        if event.inaxes == self.ax:
            x_val = event.xdata
            y_val = event.ydata
            
            # 값이 정상적으로 읽혔다면 소수점 4자리까지 포맷팅하여 출력
            if x_val is not None and y_val is not None:
                self.lbl_coords.setText(f"x = {x_val:.4f}\ny = {y_val:.4f}")
        else:
            # 마우스가 그래프 바깥으로 나가면 초기 상태 기호로 리셋
            self.lbl_coords.setText("x = ---\ny = ---")

    def mouseRclick_menu(self, pos):
        """ 마우스 우클릭 시 팝업 메뉴를 띄웁니다. """
        context_menu = QMenu(self)
        
        action_copy = context_menu.addAction("📋 그래프 클립보드 복사")
        action_popup = context_menu.addAction("🖥️ 새 창으로 띄우기")
        action_export = context_menu.addAction("📄 선택된 데이터 텍스트 출력")
        
        # 전역 좌표로 메뉴 실행 후 사용자가 선택한 액션 반환
        action = context_menu.exec(self.canvas.mapToGlobal(pos))
        
        if action == action_copy:
            self.mouseRclick_copy_to_clipboard()
        elif action == action_popup:
            self.mouseRclick_open_to_window()
        # 🌟 분기 처리문 추가
        elif action == action_export:
            self.mouseRclick_export_data()

    def mouseRclick_copy_to_clipboard(self):
        """ 현재 그래프를 이미지 파일로 굽어 클립보드에 복사합니다. """
        try:
            # 메모리 버퍼에 현재 Matplotlib 그림 저장
            buf = io.BytesIO()
            self.fig.savefig(buf, format='png', bbox_inches='tight', dpi=150)
            buf.seek(0)
            
            # 버퍼에서 바이트 데이터를 읽어 Qt 이미지 객체로 변환
            from PySide6.QtGui import QImage, QPixmap
            image = QImage.fromData(buf.getvalue())
            
            # 시스템 클립보드에 삽입
            clipboard = QGuiApplication.clipboard()
            clipboard.setImage(image)
            print("[Success] 그래프가 클립보드 이미지로 저장되었습니다. (Ctrl+V 가능)")
        except Exception as e:
            print(f"Clipboard copy error: {e}")


    def mouseRclick_open_to_window(self):
        """ 🖥️ 현재 다중 적재 상태 및 옵션과 100% 일치하는 새 팝업 창을 생성합니다. """
        try:
            # 1. 독립된 다이얼로그(새 창) 생성 및 크기 세팅
            pop_win = QDialog(self)
            pop_win.setWindowTitle("Advanced Graph Viewer")
            pop_win.resize(900, 700)
            
            # 새 레이아웃 구성
            pop_layout = QVBoxLayout(pop_win)
            pop_layout.setContentsMargins(5, 5, 5, 5)
            
            # 2. 새 PlotTab 인스턴스 가동 및 멀티 파일 데이터 사전 구조 동기화 (CRITICAL FIX)
            sub_tab = PlotTab(parent=pop_win)
            
            # 💡 [핵심 교정 1]: 더 이상 존재하지 않는 self.df 대신, 현재 적재된 멀티 딕셔너리 데이터를 통째로 이식합니다.
            sub_tab.data_dict = {
                file_title: (df.copy(), list(cols)) 
                for file_title, (df, cols) in self.data_dict.items()
            }
            
            # 적재된 전체 데이터를 기반으로 서브 팝업창의 좌측 트리 구조와 컴포넌트 렌더링 동기화
            sub_tab.update_ui_components()
            
            # 3. 현재 메인 탭에 지정된 X축 문자열 이식
            sub_tab.combo_x.setCurrentText(self.combo_x.currentText())
            
            # 4. 다중 선택된 계층형 트리뷰(Y축 항목) 구조 완벽 복제 (CRITICAL FIX)
            from PySide6.QtCore import QItemSelectionModel
            
            # 메인 창에서 파랗게 선택되어 있던 모든 행 인덱스 추출
            src_sel = self.var_tree.selectionModel().selectedRows()
            sub_tab_selection_model = sub_tab.var_tree.selectionModel()
            
            for idx in src_sel:
                # 우리가 앞서 심어둔 멀티 롤 메타데이터(변수명, 부모 파일명)를 정확하게 가로챕니다.
                col_name = idx.data(Qt.UserRole)
                file_title = idx.data(Qt.UserRole + 1)
                
                # 💡 다른 파일에 이름이 똑같은 변수가 있어도, 진짜 동일한 소속 파일의 자식 노드가 맞는지 검증하며 복제합니다.
                match_items = sub_tab.tree_model.findItems(col_name, Qt.MatchRecursive)
                for item in match_items:
                    if item.data(Qt.UserRole + 1) == file_title:
                        flags = QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows
                        sub_tab_selection_model.select(
                            sub_tab.tree_model.indexFromItem(item), flags
                        )
                        break
            
            # 5. 하단 체크박스 옵션 싱크 동기화
            sub_tab.chk_grid.setChecked(self.chk_grid.isChecked())
            sub_tab.chk_logx.setChecked(self.chk_logx.isChecked())
            sub_tab.chk_logy.setChecked(self.chk_logy.isChecked())
            sub_tab.chk_autoscale.setChecked(self.chk_autoscale.isChecked())
            
            # 6. 라디오 버튼 활성 모드 싱크 맞추기
            active_id = self.bg_mode.checkedId()
            if active_id != -1:
                sub_tab.bg_mode.button(active_id).setChecked(True)
            
            # 7. 데이터 뷰 매핑 완수 후 새 창의 도화지 실시간 차트 렌더링 강제 실행
            sub_tab.update_plot()
            
            # 💡 [요구사항]: 왼쪽 변수 리스트 제어창을 숨겨 깔끔하게 그래프와 옵션만 팝업에 나오게 처리
            if sub_tab.var_tree.parentWidget():
                sub_tab.var_tree.parentWidget().hide()
            
            # 8. 최종 레이아웃 조립 및 비모달(Modeless) 화면 표출
            pop_layout.addWidget(sub_tab)
            pop_win.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)    
            pop_win.show() 
            
            print("[Success] 변수 트리 제어창을 숨긴 독립 그래프 패널 새 창 가동 완료.")
            
        except Exception as e:
            import traceback
            print(f"Error opening new window: {e}")
            traceback.print_exc() # 짚고 넘어갈 수 있도록 상세 에러 스택 디버그 출력 추가

    def mouseRclick_export_data(self):
        """ 📄 현재 선택된 트리뷰 항목들의 데이터를 추출하여 텍스트로 출력 및 저장합니다. """
        try:
            # 1. 현재 선택된 X축 변수명 가져오기
            x_col = self.combo_x.currentText()
            if not x_col:
                QMessageBox.warning(self, "경고", "선택된 X축 변수가 없습니다.")
                return

            # 2. 트리뷰에서 선택된 Y축 변수 및 소속 파일 정보 취합 (UserRole 메타데이터 가로채기)
            src_sel = self.var_tree.selectionModel().selectedRows()
            if not src_sel:
                QMessageBox.warning(self, "경고", "트리뷰에서 출력할 Y축 변수를 선택해주세요.")
                return

            # 파일 그룹별로 선택된 Y축 변수 목록 정리 {file_title: [y_col1, y_col2, ...]}
            selected_targets = {}
            for idx in src_sel:
                y_col = idx.data(Qt.UserRole)
                file_title = idx.data(Qt.UserRole + 1)
                
                if file_title not in selected_targets:
                    selected_targets[file_title] = []
                selected_targets[file_title].append(y_col)

            # 3. 데이터 추출 및 텍스트 빌드
            text_lines = []
            text_lines.append("==================================================")
            text_lines.append("       OpenFAST Selected Data Text Export        ")
            text_lines.append("==================================================")

            # 마지막으로 처리된 파일 이름을 저장해두었다가 기본 저장 파일명 힌트로 사용
            last_file_title = "OpenFAST" 

            for file_title, y_cols in selected_targets.items():
                if file_title not in self.data_dict:
                    continue
                
                last_file_title = os.path.splitext(file_title)[0] # 확장자 제거한 이름 추출
                df, _ = self.data_dict[file_title]
                
                text_lines.append(f"\n📁 Source File: {file_title}")
                
                # 헤더 라인 작성 (예: Time \t WindVxi \t RotSpeed)
                headers = [x_col] + y_cols
                text_lines.append("\t".join(headers))
                
                # 시계열 데이터 행 루프 수행
                for row_idx in range(len(df)):
                    # X축 변수가 해당 DataFrame에 누락된 경우 예외 처리
                    if x_col not in df.columns:
                        text_lines.append(f"❌ Error: X-axis [{x_col}] not found in this file.")
                        break
                        
                    # 공학용 표기법(:.6e)으로 데이터 정밀도 유지 및 정렬 안정화
                    row_vals = [f"{df[x_col].iloc[row_idx]:.6e}"]
                    for y_col in y_cols:
                        if y_col in df.columns:
                            row_vals.append(f"{df[y_col].iloc[row_idx]:.6e}")
                        else:
                            row_vals.append("NaN")
                    
                    text_lines.append("\t".join(row_vals))
                
                text_lines.append("-" * 50)

            final_text_content = "\n".join(text_lines)

            # 4. 텍스트 표출 전용 다이얼로그(QDialog) 레이아웃 빌드
            export_win = QDialog(self)
            export_win.setWindowTitle("Exported Text Viewer")
            export_win.resize(750, 550)
            
            pop_layout = QVBoxLayout(export_win)
            pop_layout.setContentsMargins(10, 10, 10, 10)
            
            # 안내 메시지 추가
            info_lbl = QLabel("선택된 변수의 데이터가 탭(\t) 구분자 형식으로 추출되었습니다.\n컨텐츠를 복사하거나 파일로 내보낼 수 있습니다.", export_win)
            pop_layout.addWidget(info_lbl)
            
            # 상단에 선언된 QTextEdit 인스턴스 가동
            text_edit = QTextEdit(export_win)
            text_edit.setPlainText(final_text_content)
            text_edit.setReadOnly(True)  # 편집 방지 및 드래그 복사 허용
            pop_layout.addWidget(text_edit)
            
            # 하단 제어 버튼 배치
            btn_layout = QHBoxLayout()
            
            # [기능 1]: 파일 저장 버튼 (QFileDialog 활용)
            btn_save = QPushButton("💾 텍스트 파일로 저장", export_win)
            def save_to_file():
                file_path, _ = QFileDialog.getSaveFileName(
                    self, "데이터 텍스트 저장", f"{last_file_title}_exported.txt", "Text Files (*.txt);;CSV Files (*.csv);;All Files (*)"
                )
                if file_path:
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(text_edit.toPlainText())
                    QMessageBox.information(self, "완료", "성공적으로 파일이 저장되었습니다.")
            btn_save.clicked.connect(save_to_file)
            
            # [기능 2]: 창 닫기 버튼
            btn_close = QPushButton("닫기", export_win)
            btn_close.clicked.connect(export_win.accept)
            
            btn_layout.addWidget(btn_save)
            btn_layout.addWidget(btn_close)
            pop_layout.addLayout(btn_layout)
            
            # 창이 닫힐 때 메모리 해제 설정 및 모달(Modal) 실행
            export_win.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
            export_win.exec()
            
            print(f"[Success] '{last_file_title}' 외 선택 데이터 텍스트 변환 및 팝업 완료.")

        except Exception as e:
            QMessageBox.critical(self, "에러 발생", f"데이터를 텍스트로 처리하는 중 오류가 발생했습니다:\n{str(e)}")
            print(f"[System Error] {str(e)}")



    def var_tree_context_menu(self, pos):
        """ 📁 [최종 완성형] 단일 선택 및 다중 선택(Ctrl/Shift)된 모든 파일 세션을 완벽히 수집하여 지우는 함수 """
        
        # 1️⃣ 메뉴창을 띄우기 '전'에, 현재 마우스가 위치한 인덱스를 확보합니다.
        clicked_index = self.var_tree.indexAt(pos)
        selection_model = self.var_tree.selectionModel()
        
        # 💡 [다중 선택 해결책] selectedRows() 대신 selectedIndexes()를 호출하여 파랗게 선택된 모든 마디를 낱개로 긁어모읍니다.
        raw_selected_indexes = selection_model.selectedIndexes()
        
        # 0번째 열(Column 0)에 해당하는 순수 데이터 인덱스들만 중복 없이 정돈하여 백업합니다.
        backup_indexes = list(set([idx for idx in raw_selected_indexes if idx.column() == 0]))
        
        # 만약 Ctrl이나 Shift로 다중 선택을 안 하고, 그냥 특정 파일 위에서 곧바로 우클릭만 딸깍 누른 경우라면
        # 마우스 커서 바로 밑에 있는 그 인덱스 하나를 백업 리스트에 강제로 채워 넣어 구동시킵니다.
        if not backup_indexes and clicked_index.isValid():
            backup_indexes = [clicked_index]

        # ------------------------------------------------------------------
        # 데이터 사전 확보 완수 후 우클릭 컨텍스트 메뉴 가동
        # ------------------------------------------------------------------
        context_menu = QMenu(self)
        remove_action = context_menu.addAction("❌ 선택한 파일/변수 리스트에서 제거")
        
        # 마우스 커서 전역 좌표 기준으로 메뉴 열기
        action = context_menu.exec(self.var_tree.mapToGlobal(pos))
        
        if action == remove_action:
            from PySide6.QtWidgets import QMessageBox
            
            # 사전에 복사해둔 백업 인덱스가 전혀 없다면 에러 리턴
            if not backup_indexes:
                QMessageBox.information(self, "안내", "리스트에서 제거할 파일이나 변수를 먼저 마우스로 선택해 주세요.")
                return

            files_to_remove = set()
            
            for index in backup_indexes:
                item = self.tree_model.itemFromIndex(index)
                if not item:
                    continue
                
                # 사용자가 최상위 부모(파일 폴더) 노드를 선택한 경우 순수 파일명 발려내기
                if item.parent() is None:
                    full_text = item.text().strip()
                    
                    # 앞쪽 아이콘/이모지 제거 필터 가동
                    pure_text = full_text
                    for char in full_text:
                        if char.isalnum() or char in ['_', '=', '-', '.']:
                            pure_text = full_text[full_text.index(char):]
                            break
                    
                    # 뒤쪽 변수 개수 괄호 " (135)" 패턴 완벽 절단 (배열 원소 인덱스 고정)
                    if " (" in pure_text:
                        file_title = pure_text.rsplit(" (", 1)[0].strip()
                    else:
                        file_title = pure_text.strip()
                        
                    files_to_remove.add(file_title)
                
                # 사용자가 폴더 내부의 하위 변수 자식 노드들을 마우스 드래그로 선택한 경우
                else:
                    file_title = item.data(Qt.UserRole + 1)
                    if file_title:
                        files_to_remove.add(str(file_title).strip())

            if not files_to_remove:
                return

            # 사용자 최종 삭제 여부 더블 체크 대화상자 팝업
            target_list = ", ".join(list(files_to_remove))
            reply = QMessageBox.question(
                self, "파일 제거 확인",
                f"선택한 {len(files_to_remove)}개의 파일 세션을 리스트와 백엔드 메모리에서 완전히 삭제하시겠습니까?\n\n"
                f"삭제 대상 키: [ {target_list} ]",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                # 1. 백엔드 메모리 딕셔너리 데이터 소스에서 타겟 키 일괄 완전 삭제
                for f_title in files_to_remove:
                    if f_title in self.data_dict:
                        del self.data_dict[f_title]
                        print(f"[🗑️ 삭제 완료] {f_title}")
                    else:
                        # 2차 방어선: 대소문자 및 미세 공백 불일치 유연 매칭 청소
                        matched_key = None
                        for key in self.data_dict.keys():
                            if key.lower().strip() == f_title.lower().strip():
                                matched_key = key
                                break
                        if matched_key:
                            del self.data_dict[matched_key]
                            print(f"[🗑️ 삭제 완료(유연)] {matched_key}")
                
                # 2. 남은 데이터들을 기반으로 좌측 트리뷰 및 X축 컴포넌트 자동 동기화 리셋
                if self.data_dict:
                    self.update_ui_components()
                else:
                    # 데이터 소스가 텅 비었을 때 초기 상태 플레이스홀더 화면 복구
                    self.tree_model.clear()
                    self.combo_x.clear()
                    self.combo_x.addItem("Time_[s]")
                    
                    placeholder = QStandardItem("💡여기에 .out 파일을 드래그하세요")
                    placeholder.setSelectable(False)
                    self.tree_model.appendRow(placeholder)
                
                # 3. 우측 Matplotlib 차트 화면도 지워진 데이터를 즉시 반영하여 새로고침
                self.update_plot()



