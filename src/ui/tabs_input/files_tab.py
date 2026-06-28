import os
import copy
import sys
import subprocess 
import json
import shutil

from datetime import datetime
from logging import config

from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QTabWidget, QLabel, QTreeView
from PySide6.QtWidgets import QMessageBox, QFileDialog
from PySide6.QtCore import QPoint, Qt,QSettings, Qt, QPoint, QSettings, QProcess
from PySide6.QtGui import QStandardItemModel, QStandardItem

from PySide6.QtWidgets import QFileDialog, QInputDialog, QMessageBox, QWidget, QVBoxLayout, QTreeView

from src.core.openfast_io import OpenFastIO  # 💡 코어 엔진 임포트

class FilesTab(QWidget):
    """ 💡 오직 파일 디렉토리 탐색과 드래그앤드롭 모션, 트리 배지만 책임지는 정석 UI 위젯 """
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window  # 상위 컨트롤러 메인 창 정보 저장 (탭 라우팅 신호용)
        self._drag_start_position = QPoint()
        self.init_ui()

    def init_ui(self):
        """ 🎨 트리뷰 레이아웃 배치 및 이벤트 바인딩 """
        self.setAcceptDrops(True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)

        # 트리뷰 위젯 정의
        self.tree_view = QTreeView()
        self.tree_view.setDragEnabled(True)
        
        # 🖱️ 마우스 피지컬 이벤트를 이 탭 영역 내부로 안전하게 격리
        self.tree_view.mousePressEvent = self.tree_press_event
        self.tree_view.mouseMoveEvent = self.tree_move_event
        self.tree_view.doubleClicked.connect(self.on_item_double_clicked)
        
        self.tree_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree_view.customContextMenuRequested.connect(self.on_item_right_clicked)
        self.tree_view.setHeaderHidden(True)

        # 데이터 모델 생성 및 스타일 적용
        self.tree_model = QStandardItemModel()
        self.tree_view.setModel(self.tree_model)
        
        self.tree_view.setStyleSheet("""
            QTreeView { border: none; background-color: #FFFFFF; font-size: 14px; }
            QTreeView::item { padding: 5px 0px; }
        """)

        layout.addWidget(self.tree_view)
        
        # 레지스트리에서 마지막 세션 복구 자동 가동
        settings = QSettings("JHLEE", "OFA")
        last_fst_path = settings.value("LastFstPath_fst", "")
        if last_fst_path and os.path.exists(last_fst_path):
            self.load_fst_file(last_fst_path)
        else:
            self.clear_and_show_placeholder()

    def clear_and_show_placeholder(self):
        self.tree_model.clear()
        self.tree_model.appendRow(QStandardItem("💡여기에 .fst 파일을 마우스로 끌어다 놓으세요 (Drag & Drop)"))

    def load_fst_file(self, file_path):
        self.tree_model.clear()
        
        # 주소를 Computer Registry에 저장
        settings = QSettings("JHLEE", "OFA")
        settings.setValue("LastFstPath_fst", file_path)
           
        root_item = QStandardItem(f"📁 Main \t: {file_path}")
        self.tree_model.appendRow(root_item)
        
        config = OpenFastIO.update_config_from_fst(file_path)
        # print(json.dumps(config, indent=4, ensure_ascii=False))

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

        self.tree_view.collapseAll()
        self.tree_view.expandToDepth(0)

    # ================= [ 🖱️ 마우스 드래그 앤 드롭 및 클릭 핸들러 ] =================

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
                    self.load_fst_file(drop_file_path)
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
                self.load_fst_file(current_main)




    def tree_press_event(self, event):
        """ 마우스 클릭 시 클릭한 위치와 항목을 기억하는 함수 """
        if event.button() == Qt.LeftButton:
            self._drag_start_position = event.position().toPoint()
        # 원래 QTreeView의 기본 마우스 클릭 동작도 함께 수행합니다.
        QTreeView.mousePressEvent(self.tree_view, event)

    def tree_move_event(self, event):
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

    def on_item_double_clicked(self, index):
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


    def on_item_right_clicked(self, pos):
   # 트리 뷰 마우스 우클릭 팝업 메뉴 화면 처리 
        from PySide6.QtWidgets import QMenu
        from PySide6.QtGui import QAction

        # 현재 마우스 우클릭을 한 주소의 트리 아이템 인덱스 가져오기
        index = self.tree_view.indexAt(pos)
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
        save_project_action = QAction("💾 Project Files 복사/저장하기", self)
        save_runfile_action = QAction("💾 Run Files 복사/저장하기", self)
        save_as_action = QAction("📝 다른 이름으로 저장하기...", self)
        export_text_action = QAction("📋 파일 절대 경로 텍스트 복사", self)
        run_openfast_action = QAction("▶️ OpenFAST 실행하기", self)

        menu.addAction(open_directory_action)
        menu.addAction(export_text_action)
        menu.addSeparator() # Separator line     
        menu.addAction(save_project_action)
        menu.addAction(save_runfile_action)
        menu.addAction(save_as_action)
        menu.addSeparator() # Separator line 
        menu.addAction(run_openfast_action)

        open_directory_action.triggered.connect(lambda:  self.mouse_Rclick_open_directory(text))
        save_project_action.triggered.connect(lambda:    self.mouse_Rclick_save_project(text))
        save_runfile_action.triggered.connect(lambda:    self.mouse_Rclick_save_runfile(text))       
        save_as_action.triggered.connect(lambda:         print(f"[선택] 다른 이름으로 저장하기 target: {text}"))
        export_text_action.triggered.connect(lambda:     print(f"[선택] 절대 경로 복사 target: {text}"))
        run_openfast_action.triggered.connect(lambda:    self.mouse_Rclick_run_openfast(text))

        menu.exec(self.tree_view.mapToGlobal(pos))  # 마우스가 클릭된 전역 좌표(화면 기준 주소)에 메뉴판 오픈

    def mouse_Rclick_run_openfast(self, text):
        """ 우클릭 메뉴에서 'OpenFAST 실행하기'를 선택했을 때 OpenFAST를 실행하는 함수 """
        if hasattr(self, 'main_window') and self.main_window:
            if self.main_window.is_simulation_running():
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.warning(
                    self, 
                    "실행 불가", 
                    "현재 이미 OpenFAST 시뮬레이션이 구동 중입니다.\n기존 작업이 끝난 후 다시 시도해 주세요."
                )
                return False
            
        run_in_background = False
        if "|BACKGROUND" in text:
            run_in_background = True
            text = text.replace("|BACKGROUND", "")

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
            if run_in_background:
                process = QProcess()
                process.setProcessChannelMode(QProcess.MergedChannels)
                process.setWorkingDirectory(working_dir)
                process.start("cmd.exe", ["/c", openfast_path, file_path])
                return process  # 💡 만들어진 프로세스 엔진을 MainTab에 토스!
    
            cmd_list = f'cmd /c "{openfast_path}" "{file_path}" || pause'
            cmd_list = ["cmd.exe", "/k", openfast_path, file_path]
            
            subprocess.Popen(
                cmd_list, 
                cwd=working_dir,
                creationflags=subprocess.CREATE_NEW_CONSOLE )

            return "NEW_CONSOLE"
            
        except Exception as e:
            QMessageBox.critical(self, "실행 실패", f"OpenFAST 구동 중 오류가 발생했습니다.\n\n사유: {e}")
            return False
    
    
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


   
    def mouse_Rclick_save_project(self, text):
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

    def mouse_Rclick_save_runfile(self, text):
        """ Soft copy """
        main_fst_path = OpenFastIO.current_config.get("MainFST", {}).get("current")
        if not main_fst_path:
            QMessageBox.critical(self, "Error", "로드된 OpenFAST 설정 파일이 없습니다.")
            return

        # 1. 기존 경로 분석
        # current_fst_dir = "A0/A1"
        current_fst_dir = os.path.dirname(os.path.abspath(main_fst_path))
        # parent_dir = "A0"
        parent_dir = os.path.dirname(current_fst_dir) 
        # original_version_name = "A1"
        original_version_name = os.path.basename(current_fst_dir)

        # 2. 유저에게 새 폴더 이름('신규이름') 입력 받기
        today_str = datetime.now().strftime("%Y%m%d")
        default_new_name = f"{original_version_name}_{today_str}"
        
        new_folder_name, ok = QInputDialog.getText(
            self, 
            "📁 새 프로젝트 생성", 
            f"현재 버전 [{original_version_name}]을 대체할\n새로운 폴더 이름을 입력하세요:",
            text=default_new_name
        )
        
        if not ok or not new_folder_name.strip():
            return

        new_folder_name = new_folder_name.strip()
        # target_dir = "A0/신규이름"
        target_dir = os.path.join(parent_dir, new_folder_name)

        # 3. 복사 대상 파일 수집 (기존 로직 활용)
        files_to_copy = []
        files_to_copy.append(("MainFST", main_fst_path))
        
        for key, info in OpenFastIO.current_config.items():
            if key == "MainFST" or not isinstance(info, dict):
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
                    resolved_path = os.path.normpath(os.path.join(current_fst_dir, path_item))
                else:
                    resolved_path = os.path.normpath(path_item)

                if os.path.exists(resolved_path) and os.path.isfile(resolved_path):
                    if (key, resolved_path) not in files_to_copy:
                        files_to_copy.append((key, resolved_path))

        # 4. 경로 치환 및 실제 복사 실행
        copied_files_count = 0
        failed_files = []

        for key, origin_path in files_to_copy:
            try:
                # 핵심: 기존 "A0/A1"로 시작하는 경로를 "A0/신규이름" 경로로 강제 치환합니다.
                # 예: "A0/A1/main.fst" -> "A0/신규이름/main.fst"
                # 예: "A0/A1/HydroData/HydroDyn.dat" -> "A0/신규이름/HydroData/HydroDyn.dat"
                if origin_path.startswith(current_fst_dir):
                    relative_to_v1 = os.path.relpath(origin_path, current_fst_dir)
                    destination_path = os.path.join(target_dir, relative_to_v1)
                else:
                    # 만약 A0/A1 내부가 아니라 아예 외부 파일이라면 원래 이름 구조를 유지하여 새 폴더 하위에 복사
                    destination_path = os.path.join(target_dir, os.path.basename(origin_path))

                # 복사할 하위 디렉토리가 새 폴더 내에 없다면 생성 (예: HydroData 폴더 생성)
                dest_subdir = os.path.dirname(destination_path)
                if not os.path.exists(dest_subdir):
                    os.makedirs(dest_subdir)

                # 파일 물리 복사
                shutil.copy2(origin_path, destination_path)
                copied_files_count += 1

            except Exception as e:
                failed_files.append(f"{os.path.basename(origin_path)} ({e})")

        # 5. 결과 알림 팝업 및 폴더 열기
        if failed_files:
            summary = "\n".join(failed_files)
            QMessageBox.warning(
                self, 
                "Warning", 
                f"{copied_files_count}개 파일 복사 완료.\n\n⚠️ 일부 파일 복사 실패:\n{summary}"
            )
        else:
            # 성공 안내 메시지 박스
            QMessageBox.information(
                self, 
                "Success", 
                f"성공적으로 원래 버전 [{original_version_name}] 구조를 복제하여\n"
                f"[{target_dir}] 폴더로 안전하게 저장했습니다!"
            )
            
            # [신규 추가] 저장 완료된 신규 디렉토리 자동 오픈 로직
            import platform
            import subprocess
            
            try:
                target_dir = os.path.normpath(target_dir) # 경로 포맷 청소
                system_os = platform.system()
                
                if system_os == "Windows":
                    os.startfile(target_dir)
                elif system_os == "Darwin":  # macOS
                    subprocess.run(["open", target_dir], check=True)
                else:  # Linux
                    subprocess.run(["xdg-open", target_dir], check=True)
                    
                print(f"📂 신규 프로젝트 디렉토리 오픈 완료: {target_dir}")
                
            except Exception as e:
                print(f"⚠️ 디렉토리를 열 수 없습니다: {e}")
