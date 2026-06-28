import os
import io

import pandas as pd
from PySide6.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QTreeView, QComboBox,
                             QLabel, QSplitter, QCheckBox, QRadioButton, QButtonGroup,
                             QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView, QGridLayout)
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMenu, QDialog  # QMenu, QDialog 추가

from PySide6.QtGui import QStandardItemModel, QStandardItem
from PySide6.QtGui import QClipboard, QGuiApplication

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.widgets import RectangleSelector

import matplotlib.pyplot as plt

from src.core.openfast_io import OpenFastIO  # 💡 코어 엔진 임포트

class PlotTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.df = None  # 파싱된 데이터 저장
        self.columns = [] # 컬럼 이름 리스트
        
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
        if self.df is None or len(self.columns) == 0:
            return

        # 1. 현재 콤보박스에서 선택된 X축 컬럼 확인
        x_col = self.combo_x.currentText()
        if x_col not in self.df.columns:
            return

        # 2. QTreeView에서 다중 선택된 Y축 컬럼 리스트 추출
        selected_indexes = self.var_tree.selectionModel().selectedRows()
        y_cols = []
        for index in selected_indexes:
            col_name = index.data(Qt.UserRole)  # 노드에 심어둔 오리지널 컬럼명 추출
            if col_name and col_name in self.df.columns and col_name != x_col:
                y_cols.append(col_name)

        # 3. Y축 변수가 선택되지 않았다면 안내 텍스트 출력 후 종료
        if not y_cols:
            self.ax.clear()
            self.ax.text(0.5, 0.5, "Drop an OpenFAST .out file here to plot", 
                         ha='center', va='center', fontsize=12, color='gray')
            self.ax.set_xticks([])
            self.ax.set_yticks([])
            self.canvas.draw()
            return

        # 4. Matplotlib 축 리셋 후 데이터 플롯 생성
        self.ax.clear()
        x_data = self.df[x_col]

        for y_col in y_cols:
            y_data = self.df[y_col]
            self.ax.plot(x_data, y_data, label=y_col, linewidth=1.5)

        # 5. UI 옵션 상태(Grid, Log 스케일) 반영
        self.ax.grid(self.chk_grid.isChecked())
        if self.chk_logx.isChecked(): self.ax.set_xscale('log')
        if self.chk_logy.isChecked(): self.ax.set_yscale('log')

        # 6. 레이블 및 범례(Legend) 추가
        self.ax.set_xlabel(x_col)
        self.ax.set_ylabel(y_cols[0] if len(y_cols) == 1 else "Values")
        self.ax.legend(loc="upper right")

        # 7. Qt 도화지(Canvas) 새로고침 갱신
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
                break

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
            
            self.columns = []
            for col, unit in zip(raw_cols, raw_units):
                self.columns.append(f"{col}_{unit}")

            # 데이터프레임 로드
            self.df = pd.read_csv(file_path, skiprows=header_idx+2, sep=r'\s+', names=self.columns, header=None)

            # UI 컴포넌트 업데이트
            self.update_ui_components()

        except Exception as e:
            print(f"Error parsing out file: {e}")

    def update_ui_components(self):
        if self.df is None:
            return

        # 1. X축 콤보박스 리스트 채우기 및 기본값 세팅
        self.combo_x.blockSignals(True)
        self.combo_x.clear()
        self.combo_x.addItems(self.columns)
        
        # 'Time_[s]' 또는 첫 번째 열을 기본값으로 설정
        time_col = [c for c in self.columns if 'Time' in c]
        if time_col:
            self.combo_x.setCurrentText(time_col[0])
        else:
            self.combo_x.setCurrentIndex(0)
        self.combo_x.blockSignals(False)

        # 2. 좌측 변수 트리 구조 채우기 (나중 카테고리 확장을 위해 계층구조 설계)
        self.tree_model.clear()
        
        # 현재는 루트 폴더 하위에 바로 변수 리스트를 넣는 구조 (나중에 조건 분기하여 카테고리화 가능)
        root_item = QStandardItem(f"📁 Variables ({len(self.columns)})")
        root_item.setSelectable(False)
        self.tree_model.appendRow(root_item)

        for col in self.columns:
            var_item = QStandardItem(col)
            # 데이터를 아이템 내부에 심어두어 나중 조회에 편리하게 함
            var_item.setData(col, Qt.UserRole) 
            root_item.appendRow(var_item)
            
        # 끊겼던 마지막 코드를 완성합니다.
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

    # ================= ✨ [새로 추가] 우클릭 팝업 메뉴 및 기능 =================
    def mouseRclick_menu(self, pos):
        """ 마우스 우클릭 시 팝업 메뉴를 띄웁니다. """
        context_menu = QMenu(self)
        
        action_copy = context_menu.addAction("📋 그래프 클립보드 복사")
        action_popup = context_menu.addAction("🖥️ 새 창으로 띄우기")
        
        # 전역 좌표로 메뉴 실행 후 사용자가 선택한 액션 반환
        action = context_menu.exec(self.canvas.mapToGlobal(pos))
        
        if action == action_copy:
            self.mouseRclick_copy_to_clipboard()
        elif action == action_popup:
            self.mouseRclick_open_to_window()

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
        """ 현재 우측 패널(그래프+컨트롤러)과 완벽히 일치하는 새 팝업 창을 생성합니다. """
        try:
            # 독립된 다이얼로그(새 창) 생성
            pop_win = QDialog(self)
            pop_win.setWindowTitle("Graph Viewer")
            pop_win.resize(900, 700) # 시원한 크기로 초기 세팅
            
            # 새 레이아웃 구성
            pop_layout = QVBoxLayout(pop_win)
            pop_layout.setContentsMargins(5, 5, 5, 5)
            
            # 기존 우측 스플리터와 완전히 동일한 구성의 축소형 PlotTab 복제본 위젯 생성
            # 단, 파일 데이터(df)와 선택된 컬럼 정보를 새 인스턴스에 똑같이 이식합니다.
            sub_tab = PlotTab(parent=pop_win)
            sub_tab.df = self.df.copy() if self.df is not None else None
            sub_tab.columns = self.columns.copy()
            sub_tab.update_ui_components() # 변수 리스트 복사
            
            # 현재 선택되어 있는 X축과 Y축 체크 상태 그대로 복사
            sub_tab.combo_x.setCurrentText(self.combo_x.currentText())
            
            from PySide6.QtCore import QItemSelectionModel # 안전하게 함수 내에서 바로 불러옵니다.
            
            src_sel = self.var_tree.selectionModel().selectedRows()
            for idx in src_sel:
                col_name = idx.data(Qt.UserRole)
                match_items = sub_tab.tree_model.findItems(col_name, Qt.MatchRecursive)
                if match_items:
                    # PySide6 표준 플래그 규격(SelectionFlag)을 적용하여 변수 선택 상태를 완전 복제합니다.
                    flags = QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows
                    sub_tab.var_tree.selectionModel().select(
                        sub_tab.var_tree.model().indexFromItem(match_items[0]), flags
                    )
            
            # 하단 체크박스 및 라디오 버튼 상태 싱크 맞추기
            sub_tab.chk_grid.setChecked(self.chk_grid.isChecked())
            sub_tab.chk_logx.setChecked(self.chk_logx.isChecked())
            sub_tab.chk_logy.setChecked(self.chk_logy.isChecked())
            sub_tab.chk_autoscale.setChecked(self.chk_autoscale.isChecked())
            
            # 현재 선택된 라디오 버튼 ID 싱크
            active_id = self.bg_mode.checkedId()
            if active_id != -1:
                sub_tab.bg_mode.button(active_id).setChecked(True)
            
            # 뷰 동기화 후 새 도화지 렌더링 강제 실행
            sub_tab.update_plot()
            
            # 💡 요구사항: 새로운 그래프 창은 현재 창의 "오른쪽과 동일한 형태"로 레이아웃
            sub_tab.var_tree.parentWidget().hide() 
            
            # pop_layout.addWidget(sub_tab)
            # pop_win.exec() # 모달 형태로 창 열기

            pop_layout.addWidget(sub_tab)
            # 부모 창(기존 창)이 소멸할 때 새 창도 함께 안전하게 닫히도록 속성 지정
            pop_win.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)    
            # ✨ [핵심 변경] exec() 대신 show()를 쓰면 두 창을 동시에 활성화하여 조작할 수 있습니다.
            pop_win.show() 
            
        except Exception as e:
            print(f"Error opening new window: {e}")
