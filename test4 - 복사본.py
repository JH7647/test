import sys
import os
import subprocess 
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QTabWidget, QLabel, QTreeView
from PySide6.QtCore import Qt,QSettings 
from PySide6.QtGui import QStandardItemModel, QStandardItem

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("OFA")
        self.resize(1050, 600) # 화면 크기 조절 (너비, 높이)

        # 전체 화면 배경 및 마우스 파일 드롭 허용
        self.setAcceptDrops(True)
        central_widget = QWidget()
        central_widget.setStyleSheet("background-color: #FFFFFF;")
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(15, 15, 15, 15)

        # 탭 위젯(Tab Control) 생성 및 서류철 스타일시트 적용
        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane { 
                border: 1px solid #000000; 
                background-color: #FFFFFF;
                position: absolute;
                top: -1px;
            }
            QTabBar {
                position: relative;
            }
            QTabBar::tab {
                background: #FFFFFF;
                border: 1px solid #000000;
                padding: 8px 25px;
                font-weight: bold;
                font-size: 13px;
                margin-right: -1px;
            }
            QTabBar::tab:last {
                margin-right: 0px; 
            }
            QTabBar::tab:selected {
                background: #FFFFFF;
                color: #1E40AF;
                border-bottom: 1px solid #FFFFFF;
            }
            QTabBar::tab:!selected {
                background: #F3F4F6;
                border-bottom: 1px solid #000000;
                margin-top: 2px;
            }
        """)

        # ----------------------------------------------------
        # Files 탭 화면 구성 
        self.tab_files = QWidget()
        files_layout   = QVBoxLayout(self.tab_files)
        files_layout.setContentsMargins(20, 20, 20, 20)

        # 트리뷰 선언 (윈도우 탐색기 형태)
        self.tree_view = QTreeView()
        self.tree_view.setDragEnabled(True)
        self.tree_view.mousePressEvent = self.tree_press_event
        self.tree_view.mouseMoveEvent  = self.tree_move_event
        self.tree_view.doubleClicked.connect(self.mouseDoubleClickEvent) # 트리 항목 더블 클릭 시 파일 열기 함수 연결
        self.tree_view.setContextMenuPolicy(Qt.CustomContextMenu) # 우클릭 커스텀 메뉴 허용
        self.tree_view.customContextMenuRequested.connect(self.mousePressRight) # 함수 연결

        self.tree_view.setHeaderHidden(True) 
        
        # 데이터를 담아줄 트리 모델 생성 및 연결
        self.tree_model = QStandardItemModel()
        self.tree_view.setModel(self.tree_model)
        
        # 트리뷰 테두리를 없애고 폰트를 단정하게 조율하는 스타일시트
        self.tree_view.setStyleSheet("""
            QTreeView {
                border: none;
                background-color: #FFFFFF;
                font-size: 14px;
            }
            QTreeView::item {
                padding: 5px 0px;
            }
        """)
        
        placeholder_item = QStandardItem("💡여기에 .fst 파일을 마우스로 끌어다 놓으세요 (Drag & Drop)")
        self.tree_model.appendRow(placeholder_item)
        
        files_layout.addWidget(self.tree_view)
        
        # ----------------------------------------------------
        # Main 탭 화면 구성
        self.tab_main = QWidget()
        main_page_layout = QVBoxLayout(self.tab_main)
        self.label_main = QLabel("⚙️ Main 제어 화면입니다.")
        self.label_main.setAlignment(Qt.AlignCenter)
        main_page_layout.addWidget(self.label_main)

        # ----------------------------------------------------
        # 2. InFlow 탭
        self.tab_inflow = QWidget()
        inflow_layout = QVBoxLayout(self.tab_inflow)
        self.label_inflow = QLabel("💨 InFlow 해석 화면입니다.")
        self.label_inflow.setAlignment(Qt.AlignCenter)
        inflow_layout.addWidget(self.label_inflow)

        # ----------------------------------------------------
        # 3. Aero 탭 (기존 유지)
        self.tab_aero = QWidget()
        aero_layout = QVBoxLayout(self.tab_aero)
        self.label_aero = QLabel("🦅 Aero 해석 화면입니다.")
        self.label_aero.setAlignment(Qt.AlignCenter)
        aero_layout.addWidget(self.label_aero)

        # ----------------------------------------------------
        # 4. Elasto 탭 (CompElast 대응)
        self.tab_elasto = QWidget()
        elasto_layout = QVBoxLayout(self.tab_elasto)
        self.label_elasto = QLabel("💪 Elasto 구조 해석 화면입니다.")
        self.label_elasto.setAlignment(Qt.AlignCenter)
        elasto_layout.addWidget(self.label_elasto)

        # ----------------------------------------------------
        # 5. Servo 탭
        self.tab_servo = QWidget()
        servo_layout = QVBoxLayout(self.tab_servo)
        self.label_servo = QLabel("🔌 Servo 제어/전기 해석 화면입니다.")
        self.label_servo.setAlignment(Qt.AlignCenter)
        servo_layout.addWidget(self.label_servo)

        # ----------------------------------------------------
        # 6. SeaSt 탭
        self.tab_seast = QWidget()
        seast_layout = QVBoxLayout(self.tab_seast)
        self.label_seast = QLabel("🌊 SeaSt 해상 상태 설정 화면입니다.")
        self.label_seast.setAlignment(Qt.AlignCenter)
        seast_layout.addWidget(self.label_seast)

        # ----------------------------------------------------
        # 7. Hydro 탭
        self.tab_hydro = QWidget()
        hydro_layout = QVBoxLayout(self.tab_hydro)
        self.label_hydro = QLabel("⚓ Hydro 수동력 해석 화면입니다.")
        self.label_hydro.setAlignment(Qt.AlignCenter)
        hydro_layout.addWidget(self.label_hydro)

        # ----------------------------------------------------
        # 8. Sub 탭
        self.tab_sub = QWidget()
        sub_layout = QVBoxLayout(self.tab_sub)
        self.label_sub = QLabel("🏗️ Sub 하부구조 해석 화면입니다.")
        self.label_sub.setAlignment(Qt.AlignCenter)
        sub_layout.addWidget(self.label_sub)

        # ----------------------------------------------------
        # 9. Mooring 탭
        self.tab_mooring = QWidget()
        mooring_layout = QVBoxLayout(self.tab_mooring)
        self.label_mooring = QLabel("⛓️ Mooring 계류선 해석 화면입니다.")
        self.label_mooring.setAlignment(Qt.AlignCenter)
        mooring_layout.addWidget(self.label_mooring)

        # ----------------------------------------------------
        # 10. Ice 탭
        self.tab_ice = QWidget()
        ice_layout = QVBoxLayout(self.tab_ice)
        self.label_ice = QLabel("❄️ Ice 빙하중 해석 화면입니다.")
        self.label_ice.setAlignment(Qt.AlignCenter)
        ice_layout.addWidget(self.label_ice)

        # ----------------------------------------------------
        # 11. Soil 탭
        self.tab_soil = QWidget()
        soil_layout = QVBoxLayout(self.tab_soil)
        self.label_soil = QLabel("🌱 Soil 지반 해석 화면입니다.")
        self.label_soil.setAlignment(Qt.AlignCenter)
        soil_layout.addWidget(self.label_soil)

        # ----------------------------------------------------
        # [순서 정렬] 상단 서류철 컨트롤러에 탭 노출 등록
        self.tab_widget.addTab(self.tab_files, "Files")
        self.tab_widget.addTab(self.tab_main, "Main")
        self.tab_widget.addTab(self.tab_inflow, "InFlow")
        self.tab_widget.addTab(self.tab_aero, "Aero")
        self.tab_widget.addTab(self.tab_elasto, "Elasto")
        self.tab_widget.addTab(self.tab_servo, "Servo")
        self.tab_widget.addTab(self.tab_seast, "SeaSt")
        self.tab_widget.addTab(self.tab_hydro, "Hydro")
        self.tab_widget.addTab(self.tab_sub, "Sub")
        self.tab_widget.addTab(self.tab_mooring, "Mooring")
        self.tab_widget.addTab(self.tab_ice, "Ice")
        self.tab_widget.addTab(self.tab_soil, "Soil")
       
        main_layout.addWidget(self.tab_widget)

        # Register the information : openFAST.exe path, last Main.fst file path 등등
        settings = QSettings("JHLEE", "OFA")
        last_fst_path = settings.value("LastFstPath_fst", "")
        if last_fst_path and os.path.exists(last_fst_path):
            self.build_tree(last_fst_path)

   # -----------------------------------------------------------
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if urls:
            file_path = urls[0].toLocalFile()
            
            # 파일이 .fst로 끝나는 마스터 파일일 때만 트리를 빌드합니다.
            if file_path.endswith('.fst'):
                self.build_tree(file_path)

    def get_absolute_path(self, base_file_path, target_file_name):
        if os.path.isabs(target_file_name):
            return target_file_name.replace(os.sep, '/')
        raw_path = os.path.join(os.path.dirname(base_file_path), target_file_name)
        return os.path.abspath(raw_path).replace(os.sep, '/')

    def build_tree(self, root_path):
        # 기존 문구 청소
        self.tree_model.clear()

        # 최상위 루트 노드 (.fst : File Path)
        root_item = QStandardItem(f"📁 Main \t: {root_path}")
        self.tree_model.appendRow(root_item)
        
        # ----------------------------------------------------
        # .fst 파일 텍스트 데이터 파싱 (CompElast, EDFile 추출)
        config = {
            "CompElast"   : ["0", ""],
            "EDFile"      : ["ElastoDyn.dat", ""],
            "BDBldFile(1)": ["****1.dat",""], "BDBldFile(2)": ["****2.dat",""], "BDBldFile(3)": ["****3.dat",""],
            "CompInflow"  : ["0", ""],        "InflowFile": ["InflowWind.dat", ""],
            "CompAero"    : ["0", ""],        "AeroFile": ["AeroDyn.dat", ""],
            "CompServo"   : ["0", ""],        "ServoFile": ["ServoDyn.dat", ""],
            "CompSeaSt"   : ["0", ""],        "SeaStFile": ["SeaState.dat", ""],
            "CompHydro"   : ["0", ""],        "HydroFile": ["HydroDyn.dat", ""],
            "CompSub"     : ["0", ""],        "SubFile": ["SubDyn.dat", ""],
            "CompMooring" : ["0", ""],        "MooringFile": ["MoorDyn.dat", ""],
            "CompIce"     : ["0", ""],        "IceFile": ["Ice.dat", ""],
            "CompSoil"    : ["0", ""],        "SoilFile": ["Soil.dat", ""]
        }

        # fst 파일 파싱 전용 함수 정의
        if os.path.exists(root_path):
            # Register the last opened .fst file path in QSettings for future reference
            settings = QSettings("JHLEE", "OFA")
            settings.setValue("LastFstPath_fst", root_path)

            try:
                with open(root_path, 'r', encoding='utf-8', errors='ignore') as f:
                    for line in f:
                        clean_line = line.split('-')[0].strip()
                        if not clean_line:
                            continue
                        for key in config:
                            if key in line:
                                parts = clean_line.split()
                                if parts:
                                    raw_val = parts[0]
                                    config[key][1] = raw_val.strip('"').strip("'")
            except Exception as e:
                print(f"파일 읽기 오류: {e}")

       # ----------------------------------------------------
       # Elasto 모듈 처리
        comp_elast   = int(config["CompElast"][1] if config["CompElast"][1] else config["CompElast"][0])
        if comp_elast == 1:
            ed_file_name = config["EDFile"][1] if config["EDFile"][1] else config["EDFile"][0]
            ed_path = self.get_absolute_path(root_path, ed_file_name)
            ed_item = QStandardItem(f"📁 Elasto \t: {ed_path}")
            root_item.appendRow(ed_item)

       # ----------------------------------------------------
       # Beam 모듈 처리
        elif comp_elast == 2:
            ed_file_name = config["EDFile"][1] if config["EDFile"][1] else config["EDFile"][0]
            ed_path = self.get_absolute_path(root_path, ed_file_name)
            ed_item = QStandardItem(f"📁 Elasto \t: {ed_path}")
            root_item.appendRow(ed_item)

            bd_file1_name = config["BDBldFile(1)"][1] if config["BDBldFile(1)"][1] else config["BDBldFile(1)"][0]
            bd_path1 = self.get_absolute_path(root_path, bd_file1_name)            
            bd_item = QStandardItem(f"📁 Beam   \t: {bd_path1}")
            root_item.appendRow(bd_item)


            

       # ----------------------------------------------------
       # InFlow 모듈 처리
        comp_inflow = int(config["CompInflow"][1] if config["CompInflow"][1] else config["CompInflow"][0])
        if comp_inflow > 0:
            if_file_name = config["InflowFile"][1] if config["InflowFile"][1] else config["InflowFile"][0]
            if_path = self.get_absolute_path(root_path, if_file_name)
            if_item = QStandardItem(f"📁 InFlow \t: {if_path}")
            root_item.appendRow(if_item)

        # ----------------------------------------------------
        # Aero 모듈 처리
        comp_aero = int(config["CompAero"][1] if config["CompAero"][1] else config["CompAero"][0])
        if comp_aero > 0:
            ae_file_name = config["AeroFile"][1] if config["AeroFile"][1] else config["AeroFile"][0]
            ae_path = self.get_absolute_path(root_path, ae_file_name)
            ae_item = QStandardItem(f"📁 Aero \t: {ae_path}")
            root_item.appendRow(ae_item)

            # ADBlFile of AeroDyn 파일 List
            adbl_file_list = []      # 블레이드 파일명들을 담을 가변 바구니
            num_adbl_file_list = 3   # 읽어올 블레이드 개수 (3개 고정)
            bd_key = "ADBlFile(1)"   # 기준이 될 시작 키워드

            if os.path.exists(ae_path):
                try:
                    with open(ae_path, 'r', encoding='utf-8', errors='ignore') as f:
                        lines = f.readlines()
                        
                        idx = 0
                        while idx < len(lines):
                            line = lines[idx]
                            line_clean = line.split('-')[0].strip()

                            if bd_key in line and line_clean:
                                parts = line_clean.split()
                                if parts:
                                    adbl_file_list.append(parts[0].strip('"').strip("'"))

                                    files_to_read = num_adbl_file_list - 1
                                    for _ in range(files_to_read):
                                        if idx + 1 < len(lines):
                                            idx += 1  # 곧바로 다음 줄(ADBlFile(2) 구역)로 연속 전진
                                            next_line_clean = lines[idx].split('-')[0].strip()
                                            next_parts = next_line_clean.split()
                                            
                                            if next_parts:
                                                adbl_file_list.append(next_parts[0].strip('"').strip("'"))
                                            else:
                                                adbl_file_list.append("****.dat")
                                        else:
                                            break # ADBlFile(1)부터 시작해서 3개 다 읽음
                                    break # while 종료
                            idx += 1

                except Exception as e:
                    print(f"AeroDyn 블레이드 파일 읽기 오류: {e}")

            for num, bl_file in enumerate(adbl_file_list, start=1):
                raw_bl_path = self.get_absolute_path(ae_path, bl_file)
                bl_path = os.path.abspath(raw_bl_path).replace(os.sep, '/')
                
                bl_item = QStandardItem(f"📁 ADBlFile({num}) \t: {bl_path}")
                ae_item.appendRow(bl_item) 

            # 에어포일 파일명 List
            air_foil_list = [] 
            num_air_foils_list = 0
           
            if os.path.exists(ae_path):
                try:
                    with open(ae_path, 'r', encoding='utf-8', errors='ignore') as f:
                        lines = f.readlines()
                        
                        idx = 0
                        while idx < len(lines):
                            line = lines[idx]
                            line_clean = line.split('-')[0].strip()
                            
                            if "NumAFfiles" in line and line_clean:
                                parts = line_clean.split()
                                if parts:
                                    try:
                                        num_air_foils_list = int(parts[0])
                                    except ValueError:
                                        num_air_foils_list = 0

                                    if num_air_foils_list > 0:
                                        for _ in range(num_air_foils_list):
                                            if idx + 1 < len(lines):
                                                idx += 1  # 곧바로 다음 줄(AF1.dat 구역)로 연속 전진
                                                next_line_clean = lines[idx].split('-')[0].strip()
                                                next_parts = next_line_clean.split()
                                                
                                                if next_parts:
                                                    air_foil_list.append(next_parts[0].strip('"').strip("'"))
                                                else:
                                                    air_foil_list.append("****.dat")
                                            else:
                                                break # NumAFfiles 만큼 다 읽음
                                    break  # while 종료
                                    
                            idx += 1
                except Exception as e:
                    print(f"AeroDyn 파일 읽기 오류: {e}")

            for num, af_file in enumerate(air_foil_list, start=1):
                raw_path = self.get_absolute_path(ae_path, af_file)
                af_path = os.path.abspath(raw_path).replace(os.sep, '/')
                
                af_item = QStandardItem(f"📁 Air Foil({num}) \t: {af_path}")
                ae_item.appendRow(af_item)  # Aero 노드 아래로 안착

        # ----------------------------------------------------
        # Servo 모듈 처리
        comp_servo = int(config["CompServo"][1] if config["CompServo"][1] else config["CompServo"][0])
        if comp_servo > 0:
            sv_file_name = config["ServoFile"][1] if config["ServoFile"][1] else config["ServoFile"][0]
            sv_path = self.get_absolute_path(root_path, sv_file_name)
            sv_item = QStandardItem(f"📁 Servo \t: {sv_path}")
            root_item.appendRow(sv_item)

        # ----------------------------------------------------
        # SeaSt 모듈 처리
        comp_seast = int(config["CompSeaSt"][1] if config["CompSeaSt"][1] else config["CompSeaSt"][0])
        if comp_seast > 0:
            ss_file_name = config["SeaStFile"][1] if config["SeaStFile"][1] else config["SeaStFile"][0]
            ss_path = self.get_absolute_path(root_path, ss_file_name)
            ss_item = QStandardItem(f"📁 SeaSt \t: {ss_path}")
            root_item.appendRow(ss_item)

        # ----------------------------------------------------
        # Hydro 모듈 처리
        comp_hydro = int(config["CompHydro"][1] if config["CompHydro"][1] else config["CompHydro"][0])
        if comp_hydro > 0:
            hd_file_name = config["HydroFile"][1] if config["HydroFile"][1] else config["HydroFile"][0]
            hd_path = self.get_absolute_path(root_path, hd_file_name)
            hd_item = QStandardItem(f"📁 Hydro \t: {hd_path}")
            root_item.appendRow(hd_item)

        # ----------------------------------------------------
        # Sub 모듈 처리
        comp_sub = int(config["CompSub"][1] if config["CompSub"][1] else config["CompSub"][0])
        if comp_sub > 0:
            sb_file_name = config["SubFile"][1] if config["SubFile"][1] else config["SubFile"][0]
            sb_path = self.get_absolute_path(root_path, sb_file_name)
            sb_item = QStandardItem(f"📁 Sub \t: {sb_path}")
            root_item.appendRow(sb_item)

        # ----------------------------------------------------
        # Mooring 모듈 처리
        comp_mooring = int(config["CompMooring"][1] if config["CompMooring"][1] else config["CompMooring"][0])
        if comp_mooring > 0:
            mr_file_name = config["MooringFile"][1] if config["MooringFile"][1] else config["MooringFile"][0]
            mr_path = self.get_absolute_path(root_path, mr_file_name)
            mr_item = QStandardItem(f"📁 Mooring\t: {mr_path}")
            root_item.appendRow(mr_item)

        # ----------------------------------------------------
        # Ice 모듈 처리
        comp_ice = int(config["CompIce"][1] if config["CompIce"][1] else config["CompIce"][0])
        if comp_ice > 0:
            ic_file_name = config["IceFile"][1] if config["IceFile"][1] else config["IceFile"][0]
            ic_path = self.get_absolute_path(root_path, ic_file_name)
            ic_item = QStandardItem(f"📁 Ice \t: {ic_path}")
            root_item.appendRow(ic_item)

        # ----------------------------------------------------
        # Soil 모듈 처리
        comp_soil = int(config["CompSoil"][1] if config["CompSoil"][1] else config["CompSoil"][0])
        if comp_soil > 0:
            sl_file_name = config["SoilFile"][1] if config["SoilFile"][1] else config["SoilFile"][0]
            sl_path = self.get_absolute_path(root_path, sl_file_name)
            sl_item = QStandardItem(f"📁 Soil \t: {sl_path}")
            root_item.appendRow(sl_item)

        self.tree_view.collapseAll()
        self.tree_view.expandToDepth(0)

    def tree_press_event(self, event):
    # """ 마우스 클릭 시 클릭한 위치와 항목을 기억하는 함수 """
        if event.button() == Qt.LeftButton:
            self._drag_start_position = event.position().toPoint()
        # 원래 QTreeView의 기본 마우스 클릭 동작도 함께 수행합니다.
        QTreeView.mousePressEvent(self.tree_view, event)

    def tree_move_event(self, event):
    # """ 마우스를 누른 채 일정 거리 이상 움직이면 외부로 드래그를 시작하는 함수 """
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

    def mouseDoubleClickEvent(self, index):
    # """ 트리 항목을 더블 클릭했을 때 Notepad++로 파일을 여는 함수 """
        item = self.tree_model.itemFromIndex(index)
        if not item:
            return
            
        text = item.text()

        if "\t:" in text:
            file_path = text.split("\t:")[1].strip()
            file_path = os.path.normpath(file_path)
            npp_path = r"C:\Program Files\Notepad++\notepad++.exe"
            
            if os.path.exists(file_path):
                try:
                    subprocess.Popen([npp_path, file_path])
                except FileNotFoundError:
                    subprocess.Popen(["notepad.exe", file_path])

    def mousePressRight(self, position):
    # 트리 뷰 마우스 우클릭 팝업 메뉴 화면 처리 
        from PySide6.QtWidgets import QMenu
        from PySide6.QtGui import QAction

        # 현재 마우스 우클릭을 한 주소의 트리 아이템 인덱스 가져오기
        index = self.tree_view.indexAt(position)
        if not index.isValid():
            return # 빈 바탕을 눌렀다면 메뉴를 띄우지 않고 취소

        item = self.tree_model.itemFromIndex(index)
        text = item.text()

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
        """)

        # 마우스 우클릭 시 띄워줄 저장 옵션 액션(메뉴 아이템) 선언
        save_action = QAction("💾 현재 파일 복사/저장하기", self)
        save_as_action = QAction("📝 다른 이름으로 저장하기...", self)
        export_text_action = QAction("📋 파일 절대 경로 텍스트 복사", self)

        menu.addAction(save_action)
        menu.addAction(save_as_action)
        menu.addSeparator() # 구분선 추가
        menu.addAction(export_text_action)

        save_action.triggered.connect(lambda: print(f"[선택] 현재 파일 저장하기 target: {text}"))
        save_as_action.triggered.connect(lambda: print(f"[선택] 다른 이름으로 저장하기 target: {text}"))
        export_text_action.triggered.connect(lambda: print(f"[선택] 절대 경로 복사 target: {text}"))

        menu.exec(self.tree_view.mapToGlobal(position))  # 마우스가 클릭된 전역 좌표(화면 기준 주소)에 메뉴판 오픈


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
