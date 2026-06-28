import os
from PySide6.QtWidgets import (QWidget, QFormLayout, QLineEdit, QLabel, QTextEdit, 
                               QPushButton, QHBoxLayout, QVBoxLayout, QSplitter)
from PySide6.QtCore import QProcess, Qt
from src.core.openfast_io import OpenFastIO

# 💡 BaseInputTab 대신 일반 QWidget을 상속받습니다.
class MainTab(QWidget):
    def __init__(self, main_window=None, parent=None):
        super().__init__(parent)
        self.main_window = main_window  # 부모 윈도우 인스턴스 저장
        
        # 가상의 데이터 저장소 역할 (기존 부모가 제공하던 data_store 대응용)
        self.data_store = {} 
        
        # 최초 1회 화면 구조를 완벽하게 조립합니다.
        self.init_ui()

    def init_ui(self):
        """ 좌측 변수 입력 패널과 우측 콘솔 패널을 완전히 독립적으로 배치 """
        # 메인 가로 레이아웃
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)

        # 좌우 조절용 가로형 스플리터 생성
        main_splitter = QSplitter(Qt.Horizontal)

        # ================= [좌측 영역] 시뮬레이션 변수 입력 패널 =================
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 10, 0)
        
        form_param = QFormLayout()
        
        # 입력 위젯 정의 및 기본값 셋팅
        self.txt_tmax = QLineEdit(self.data_store.get("TMax", "600.0"))
        self.txt_dt = QLineEdit(self.data_store.get("DT", "0.0125"))
        
        form_param.addRow(QLabel("<h3><b>⚙️ Simulation Variables</b></h3>"))
        form_param.addRow(QLabel("<font color='gray'>왼쪽에 추가 변수들을 계속 배치할 공간입니다.</font>"))
        form_param.addRow("", QLabel(""))  # 한 줄 띄우기
        form_param.addRow("⏱️ Total Time (TMax):", self.txt_tmax)
        form_param.addRow("⏱️ Time Step (DT):", self.txt_dt)
        
        left_layout.addLayout(form_param)
        left_layout.addStretch()  # 입력창들을 위로 밀착시킴
        
        main_splitter.addWidget(left_widget)

        # ================= [우측 영역] 시뮬레이션 진행 모니터링 패널 =================
        right_widget = QWidget()

        # 콘솔 작동 제어용 실행/중지 버튼 배치
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(10, 0, 0, 0)

        console_btn_layout = QHBoxLayout()

        self.btn_run_fast = QPushButton("🚀 Simulation Start")
        self.btn_run_fast.setMinimumHeight(35)
        self.btn_run_fast.setStyleSheet("""
            QPushButton {
                background-color: #E1F5FE; /* 연한 하늘색/파스텔 블루 배경 */
                color: #0277BD;             /* 신뢰감을 주는 짙은 파란색 글자 */
                font-weight: bold;
                font-size: 12px;
                border: 1px solid #B3E5FC;  /* 은은한 블루 톤 테두리 */
                border-radius: 4px;
            }
            QPushButton:disabled {
                background-color: #E5E7EB;
                color: #9CA3AF;
                border: 1px solid #D1D5DB;
            }
        """)
        self.btn_run_fast.clicked.connect(self.run_openfast_process)
        
        self.btn_stop_fast = QPushButton("🛑 Stop")
        self.btn_stop_fast.setMinimumHeight(35)
        self.btn_stop_fast.setStyleSheet("""
            QPushButton {
                background-color: #FDE8E8; 
                color: #03543F; 
                font-weight: bold;
                font-size: 12px;
                border: 1px solid #FBD5D5;
                border-radius: 4px;
            }
            QPushButton:disabled {
                background-color: #E5E7EB;
                color: #9CA3AF;
                border: 1px solid #D1D5DB;
            }
        """)
        self.btn_stop_fast.setEnabled(False)
        self.btn_stop_fast.clicked.connect(self.stop_openfast_process)
        
        console_btn_layout.addWidget(self.btn_run_fast)
        console_btn_layout.addWidget(self.btn_stop_fast)
        right_layout.addLayout(console_btn_layout)
        
        self.cmd_output = QTextEdit()
        self.cmd_output.setReadOnly(True)
        self.cmd_output.setStyleSheet("""
            QTextEdit {
                background-color: #F4F5F7;  /* 연한 그레이 배경 */
                color: #2D3748;             /* 부드러운 다크 차콜 글자색 */
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 13px;
                border: 1px solid #E2E8F0;  /* 은은한 외곽 테두리 */
                border-radius: 4px;
            }
        """)
        self.cmd_output.append("💡 OpenFAST를 가동하면 여기에 실시간 CMD 로그가 출력됩니다.\n")
        right_layout.addWidget(self.cmd_output)

        main_splitter.addWidget(right_widget)

        # 💡 보내주신 요구사항 비율(좌측 450px : 우측 650px) 고정 및 메인 장착
        main_splitter.setSizes([450, 650])
        main_layout.addWidget(main_splitter)



    def refresh_ui(self):
        """ 독립 위젯이 되면서 동적 레이아웃 재생성이 필요 없어졌습니다. 데이터 동기화가 필요하면 활용하세요. """
        pass

    def collect_inputs(self):
        """ 입력 데이터 취합 함수 """
        return {
            "TMax": self.txt_tmax.text(),
            "DT": self.txt_dt.text()
        }

    def run_openfast_process(self):
        """ 변수명 매핑 오류를 방지하기 위해 전체 위젯에서 FilesTab 인스턴스를 직접 탐색하여 호출하는 함수 """
        from PySide6.QtWidgets import QApplication
        from src.ui.tabs_input.files_tab import FilesTab # 정확한 타입 체크를 위해 임포트

        target_pane = None

        # 1. ✨ [핵심 수정] 프로그램 전체를 뒤져서 실시간으로 작동 중인 FilesTab 객체를 직접 찾아냅니다.
        for widget in QApplication.allWidgets():
            if isinstance(widget, FilesTab):
                target_pane = widget
                break

        # 만약 시스템 전체를 뒤졌는데도 찾지 못했다면 비상 대책 가동
        if not target_pane:
            main_win = self.window()
            if main_win and hasattr(main_win, 'pane_files'):
                target_pane = main_win.pane_files

        # 최종 검증 실패 시 예외 처리
        if not target_pane:
            self.cmd_output.setText("❌ 시스템 오류: 메모리에서 Files 탭 인스턴스(FilesTab)를 탐색하지 못했습니다.")
            return

        # 2. OpenFastIO.current_config에서 현재 로드된 .fst 파일의 전체 경로를 가져옵니다.
        fst_path = OpenFastIO.current_config.get("MainFST", {}).get("current", "").strip()

        if not fst_path or not os.path.exists(fst_path):
            self.cmd_output.setText("❌ 에러: 로드된 .fst 파일이 없습니다. Files 탭에서 먼저 .fst 파일을 로드해 주세요.")
            return

        # 3. FilesTab 함수 규격("키워드\t: 파일경로")에 맞게 가짜 텍스트(text)를 조합하여 가공
        fake_text = f"MainFST\t: {fst_path}|BACKGROUND"
        
        try:
            # 4. 안전하게 추출된 진짜 FilesTab 객체의 공용 실행 함수를 호출합니다.
            result = target_pane.mouse_Rclick_run_openfast(fake_text)
            
            # 💡 [보완 핵심] 만약 인터락에 걸려 False를 반환받았다면, 내장 콘솔에 기록을 남기고 즉시 종료
            if result is False:
                self.cmd_output.append("\n⚠️ [경고] 이미 백그라운드에서 OpenFAST 시뮬레이션이 구동 중입니다. 작업을 취소합니다.")
                return
                
            self.process = result
            
        except Exception as e:
            self.cmd_output.setText(f"❌ 실행 엔진 호출 실패: {e}")
            return

        # 5. 가로챈 실행 엔진이 정상 반환되었다면 내장 콘솔 창 스트림 및 시그널을 연결합니다.
        if self.process:
            self.cmd_output.clear()
            self.cmd_output.append(f"⏳ OpenFAST 구동 시작 (공용 실행 엔진 가동 중...)\n")
            self.cmd_output.append(f"📄 실행 대상: {os.path.basename(fst_path)}\n" + "-"*60 + "\n")
            
            # 실시간 로그 긁어오기 및 종료 콜백 시그널 바인딩
            self.process.readyReadStandardOutput.connect(self.read_console_output)
            self.process.finished.connect(self.on_process_finished)
            
            # 메인 버튼 인터랙션 권한 제어
            self.btn_run_fast.setEnabled(False)
            self.btn_stop_fast.setEnabled(True)


    def stop_openfast_process(self):
        """ 실행 중인 cmd.exe와 하위 openfast.exe 프로세스를 완전히 강제 종료 """
        # 프로세스 존재 및 실행 여부 검증
        if hasattr(self, 'process') and self.process and self.process.state() == QProcess.Running:
            
            # 1. 윈도우 환경에서 하위 자식 프로세스(openfast.exe)까지 싹 다 강제 종료하기
            pid = self.process.processId() # 현재 실행 중인 QProcess(cmd.exe)의 고유 번호(PID) 추출
            if pid > 0:
                import subprocess
                # /F: 강제종료, /T: 자식 프로세스까지 통째로 종료
                subprocess.run(f"taskkill /pid {pid} /f /t", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            # 2. 만약의 상황을 대비한 QProcess 자체 엔진 정지 및 메모리 해제 대기
            self.process.kill()
            self.process.waitForFinished(1000) # 최대 1초 대기
            
            self.cmd_output.append("\n🛑 사용자에 의해 시뮬레이션이 안전하게 강제 종료되었습니다.")
            
            # 3. UI 버튼 상태 정상화
            self.btn_run_fast.setEnabled(True)
            self.btn_stop_fast.setEnabled(False)


    def read_console_output(self):
        if self.process:
            data = self.process.readAllStandardOutput()
            try:
                output_text = data.data().decode('cp949', errors='ignore')
            except Exception:
                output_text = data.data().decode('utf-8', errors='ignore')
                
            self.cmd_output.insertPlainText(output_text)
            scrollbar = self.cmd_output.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())


    def on_process_finished(self, exit_code, exit_status):
        self.cmd_output.append(f"\n✨ 프로세스 종료됨 (Exit Code: {exit_code})")
        self.btn_run_fast.setEnabled(True)
        self.btn_stop_fast.setEnabled(False)

        if exit_code == 0:
            try:
                main_win = self.window()
                if main_win and hasattr(main_win, 'pane_plot'):
                    self.cmd_output.append("\n📊 [OFA 알림] 시뮬레이션 완료에 따라 'Plot Data' 탭의 그래프 데이터를 자동 갱신합니다.")
                    main_win.pane_plot.check_and_load_default_data()
            except Exception as e:
                self.cmd_output.append(f"\n⚠️ 그래프 자동 갱신 중 에러 발생: {e}")

