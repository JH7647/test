import os
import sys
import subprocess 
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QTabWidget, QLabel, QTreeView
from PySide6.QtWidgets import QMessageBox, QFileDialog
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
        self.tree_view.doubleClicked.connect(self.mouseDoubleClick_open) # 트리 항목 더블 클릭 시 파일 열기 함수 연결
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
        
        # last_openfast_path = settings.value("LastOpenFastPath", "")
        # if last_openfast_path and os.path.exists(last_openfast_path):
        #     print(f"Last OpenFAST.exe path: {last_openfast_path}")

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

    def read_file(self, file_path, config_dict):
        """ 순수하게 .fst 파일을 읽어서 config 딕셔너리에 데이터를 채워주는 전용 함수 """
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    for line in f:
                        clean_line = line.split('-')[0].strip()
                        if not clean_line:
                            continue
                        for key in config_dict:
                            if key in line:
                                # 예외 처리: NumAFfiles를 찾았는데 해당 줄이 AFNames 줄이라면 건너뜁니다.
                                if key == "NumAFfiles" and "AFNames" in line:
                                    continue

                                parts = clean_line.split()
                                if parts:
                                    raw_val = parts[0]
                                    # 인덱스 1번(빈 공간)에 추출한 설정 값을 저장합니다.
                                    config_dict[key][1] = raw_val.strip('"').strip("'")
            except Exception as e:
                print(f"파일 읽기 오류: {e}")

        return config_dict
    
    def read_file_variable(self, file_path, start_key, num_lines):
    #""" [추가] AFNames 처럼 키워드 아래로 연속된 가변 파일 목록을 읽어 리스트로 반환하는 함수 """
        result_list = []
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = f.readlines()
                    
                    idx = 0
                    while idx < len(lines):
                        line = lines[idx]
                        line_clean = line.split('-')[0].strip()
                        
                        # 지정한 시작 키워드(예: "AFNames")를 만나면 작동 시작
                        if start_key in line and line_clean:
                            parts = line_clean.split()
                            if parts:
                                # 첫 번째 줄 파일명 저장하지 않고 건너뜀
                                #result_list.append(parts[0].strip('"').strip("'"))
                                
                                # 사용자가 지정한 개수(NumAFfiles)만큼 아래 줄들을 연속 강제 수집
                                if num_lines > 0:
                                    for _ in range(num_lines):
                                        if idx + 1 < len(lines):
                                            idx += 1  # 다음 줄로 이동
                                            next_clean = lines[idx].split('-')[0].strip()
                                            next_parts = next_clean.split()
                                            
                                            if next_parts:
                                                result_list.append(next_parts[0].strip('"').strip("'"))
                                            else:
                                                result_list.append("****.dat")
                                        else:
                                            break
                                # 갯수만큼 다 읽었으므로 즉시 탈출(break)하여 파싱 종료
                                break
                        idx += 1
            except Exception as e:
                print(f"가변 파일 읽기 오류 ({start_key}): {e}")
                
        return result_list

    def build_tree(self, root_path):
        # 기존 문구 청소
        self.tree_model.clear()

        # 최상위 루트 노드 (.fst : File Path)
        root_item = QStandardItem(f"📁 Main \t: {root_path}")
        self.tree_model.appendRow(root_item)
        
        # ----------------------------------------------------
        # .fst 파일 텍스트 데이터 파싱 (CompElast, EDFile 추출)
        config = {
            "CompElast"   : ["0", ""],  "EDFile"      : ["ElastoDyn.dat", ""], 
                                        "BldFile(1)"  : ["blade_ElastoDyn.dat",""], "BldFile(2)" : ["blade_ElastoDyn.dat",""], "BldFile(3)": ["blade_ElastoDyn.dat",""],         
                                        "BDBldFile(1)": ["BeamDyn.dat",""], "BDBldFile(2)": ["BeamDyn.dat",""], "BDBldFile(3)": ["BeamDyn.dat",""], 
                                        "BldFile"     : ["blade_BeamDyn.dat",""],
            "CompInflow"  : ["0", ""],  "InflowFile"  : ["InflowWind.dat", ""],
            "CompAero"    : ["0", ""],  "AeroFile"    : ["AeroDyn.dat", ""],
                                        "ADBlFile(1)" : ["blade_AeroDyn.dat",""], "ADBlFile(2)": ["blade_AeroDyn.dat",""], "ADBlFile(3)": ["blade_AeroDyn.dat",""],
                                        "NumAFfiles"  : ["0",""], "AFFileList" : [[], []], # NumAFfiles 개수만큼 AFNames 아래 줄들을 리스트로 수집할 예정  
            "CompServo"   : ["0", ""],  "ServoFile"   : ["ServoDyn.dat", ""],
                                        "DLL_FileName": ["", ""],
            "CompSeaSt"   : ["0", ""],  "SeaStFile"   : ["SeaState.dat", ""],
            "CompHydro"   : ["0", ""],  "HydroFile"   : ["HydroDyn.dat", ""],
            "CompSub"     : ["0", ""],  "SubFile"     : ["SubDyn.dat", ""],
            "CompMooring" : ["0", ""],  "MooringFile" : ["MoorDyn.dat", ""],
            "CompIce"     : ["0", ""],  "IceFile"     : ["Ice.dat", ""],
            "CompSoil"    : ["0", ""],  "SoilFile"    : ["Soil.dat", ""]
        }

        # fst 파일 파싱 전용 함수 정의
        if os.path.exists(root_path):
            # Register the last opened .fst file path in QSettings for future reference
            settings = QSettings("JHLEE", "OFA")
            settings.setValue("LastFstPath_fst", root_path)

        config = self.read_file(root_path, config)

       # ----------------------------------------------------
       # Elasto 모듈 처리
        comp_elast = int(config["CompElast"][1] if config["CompElast"][1] else config["CompElast"][0])
        if comp_elast == 1 or comp_elast == 2:
            file_name = config["EDFile"][1] if config["EDFile"][1] else config["EDFile"][0]
            ed_path = self.get_absolute_path(root_path, file_name)
            ed_item = QStandardItem(f"📁 Elasto \t: {ed_path}")
            root_item.appendRow(ed_item)

            config = self.read_file(ed_path, config)
            for num in range(1, 4):
                bl_file_name = config[f"BldFile({num})"][1] if config[f"BldFile({num})"][1] else config[f"BldFile({num})"][0]
                bl_path = self.get_absolute_path(ed_path, bl_file_name)
                bl_item = QStandardItem(f"📁 BldFile({num}) \t: {bl_path}")
                ed_item.appendRow(bl_item)

       # ----------------------------------------------------
       # Beam 모듈 처리
        if comp_elast == 2:
            bd_file1_name = config["BDBldFile(1)"][1] if config["BDBldFile(1)"][1] else config["BDBldFile(1)"][0]
            bd_path1 = self.get_absolute_path(root_path, bd_file1_name)            
            bd_item = QStandardItem(f"📁 Beam   \t: {bd_path1}")
            root_item.appendRow(bd_item)

            config = self.read_file(bd_path1, config)
            for num in range(1, 2):
                bl_file_name = config[f"BldFile"][1] if config[f"BldFile"][1] else config[f"BldFile"][0]
                bl_path = self.get_absolute_path(bd_path1, bl_file_name)
                bl_item = QStandardItem(f"📁 BldFile \t\t: {bl_path}")
                bd_item.appendRow(bl_item)

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
            config = self.read_file(ae_path, config)
            for num in range(1, 4):
                ae_file_name = config[f"ADBlFile({num})"][1] if config[f"ADBlFile({num})"][1] else config[f"ADBlFile({num})"][0]
                al_path = self.get_absolute_path(ae_path, ae_file_name)
                al_item = QStandardItem(f"📁 ADBlFile({num}) \t: {al_path}")
                ae_item.appendRow(al_item)

            # 에어포일 파일명 List
            config = self.read_file(ae_path, config)
            num_AFfiles = int(config["NumAFfiles"][1] if config["NumAFfiles"][1] else config["NumAFfiles"][0])
            config["AFFileList"][1] = self.read_file_variable(ae_path, "NumAFfiles", num_AFfiles)

            for num, af_file in enumerate(config["AFFileList"][1], start=1):
                raw_path = self.get_absolute_path(ae_path, af_file)
                af_path = os.path.abspath(raw_path).replace(os.sep, '/')
                af_item = QStandardItem(f"📁 Air Foil({num}) \t: {af_path}")
                ae_item.appendRow(af_item)

        # ----------------------------------------------------
        # Servo 모듈 처리
        comp_servo = int(config["CompServo"][1] if config["CompServo"][1] else config["CompServo"][0])
        if comp_servo > 0:
            sv_file_name = config["ServoFile"][1] if config["ServoFile"][1] else config["ServoFile"][0]
            sv_path = self.get_absolute_path(root_path, sv_file_name)
            sv_item = QStandardItem(f"📁 Servo \t: {sv_path}")
            root_item.appendRow(sv_item)

            config = self.read_file(sv_path, config)
            for num in range(1, 2):
                file_name = config[f"DLL_FileName"][1] if config[f"DLL_FileName"][1] else config[f"DLL_FileName"][0]
                path = self.get_absolute_path(sv_path, file_name)
                item = QStandardItem(f"📁 DLL_FileName \t: {path}")
                sv_item.appendRow(item)


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

    def mouseDoubleClick_open(self, index):
    # """ 트리 항목을 더블 클릭했을 때 Notepad++로 파일을 여는 함수 """
        item = self.tree_model.itemFromIndex(index)
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
            QMenu::separator {
                height: 1px;               /* 구분선 두께 */
                background-color: #D1D5DB; /* 구분선 색상 (연한 회색) */
                margin-top: 4px;           /* 위쪽 여백 */
                margin-bottom: 4px;        /* 아래쪽 여백 */
            }                         
        """)

        # 마우스 우클릭 시 띄워줄 저장 옵션 액션(메뉴 아이템) 선언
        open_directory_action = QAction("📁 Open Directory", self)
        save_action = QAction("💾 현재 파일 복사/저장하기", self)
        save_as_action = QAction("📝 다른 이름으로 저장하기...", self)
        export_text_action = QAction("📋 파일 절대 경로 텍스트 복사", self)
        run_openfast_action = QAction("▶️ OpenFAST 실행하기", self)

        menu.addAction(open_directory_action)
        menu.addAction(export_text_action)
        menu.addSeparator() # Separator line     
        menu.addAction(save_action)
        menu.addAction(save_as_action)
        menu.addSeparator() # Separator line 
        menu.addAction(run_openfast_action)

        open_directory_action.triggered.connect(lambda:  self.mouse_Rclick_open_directory(text))
        save_action.triggered.connect(lambda: print(f"[선택] 현재 파일 저장하기 target: {text}"))
        save_as_action.triggered.connect(lambda: print(f"[선택] 다른 이름으로 저장하기 target: {text}"))
        export_text_action.triggered.connect(lambda: print(f"[선택] 절대 경로 복사 target: {text}"))
        run_openfast_action.triggered.connect(lambda: self.mouse_Rclick_run_openfast(text))

        menu.exec(self.tree_view.mapToGlobal(position))  # 마우스가 클릭된 전역 좌표(화면 기준 주소)에 메뉴판 오픈

    def mouse_Rclick_run_openfast(self, text):
    # """ 우클릭 메뉴에서 'OpenFAST 실행하기'를 선택했을 때 OpenFAST를 실행하는 함수 """
        settings = QSettings("JHLEE", "OFA")
        openfast_path = settings.value("LastOpenFastPath", "")

        # 📌 만약 저장된 경로가 없거나 파일이 물리적으로 존재하지 않는다면 최초 등록 프로세스 시작
        if not openfast_path or not os.path.exists(openfast_path):
            reply = QMessageBox.information(
                self,
                "Register OpenFAST.exe Path!",
                "최초 1회 openFAST.exe 파일의 위치 등록이 필요합니다.\n확인 버튼을 눌러 실행 파일을 선택해 주세요.",
                QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel )
            
            if reply == QMessageBox.StandardButton.Ok:
                # 윈도우 파일 탐색기 창 열기 (파일 필터를 .exe로 제한)
                selected_file, _ = QFileDialog.getOpenFileName(
                    self,
                    "openFAST.exe 파일 선택",
                    "C:/",
                    "Executable Files (openFAST.exe);;All Files (*)" )
                
                if selected_file:
                    # QSettings에 선택한 경로를 즉시 저장 
                    settings.setValue("LastOpenFastPath", selected_file)
                    openfast_path = selected_file

                else:
                    return # 파일 선택 취소 시 함수 종료
            else:
                return # 안내창에서 취소 시 함수 종료
        
        # Main.fst 파일 경로가 포함된 텍스트에서 실제 파일 경로만 분리
        if "\t:" not in text:
            return

        file_path = text.split(":", 1)[1].strip()
        if not os.path.exists(file_path):
            QMessageBox.warning(self, "입력 파일 오류", f"시뮬레이션을 실행할 파일이 경로에 존재하지 않습니다.\n\n경로: {file_path}")
            return

        # 실행 및 작업 디렉터리(CWD) 설정
        working_dir = os.path.dirname(file_path)
        try:
            cmd_list = f'cmd /c "{openfast_path}" "{file_path}" || pause'
            cmd_list = ["cmd.exe", "/k", openfast_path, file_path]
            
            subprocess.Popen(
                cmd_list, 
                cwd=working_dir,
                creationflags=subprocess.CREATE_NEW_CONSOLE )
            
        except Exception as e:
            QMessageBox.critical(self, "실행 실패", f"OpenFAST 구동 중 오류가 발생했습니다.\n\n사유: {e}")

    def mouse_Rclick_open_directory(self, text):
        """ 우클릭 메뉴에서 'Open Directory'를 선택했을 때 실제 폴더를 열어주는 함수 """
        if "\t:" not in text:
            return

        file_path = text.split(":", 1)[1].strip()

        # 파일 이름 부분만 떼어내고 상위 디렉터리 경로만 추출
        dir_path = os.path.dirname(file_path)
        
        # 실제 존재하는 경로인지 체크 후 윈도우 파일 탐색기 열기
        if os.path.exists(dir_path):
            try:
                os.startfile(dir_path)
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Can't open directory! \n\n Reason: {e}")
        else:
            QMessageBox.warning(self, "Warning", f"No directory path was found! \n\n경로: {dir_path}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
