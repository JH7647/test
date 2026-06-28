from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, QPushButton, QMessageBox
from PySide6.QtCore import Qt

class BaseInputTab(QWidget):
    """ 모든 모듈별 입력 탭이 상속받아 사용할 공통 스크롤 템플릿 틀 """
    def __init__(self, tab_name, parent=None):
        super().__init__(parent)
        self.tab_name = tab_name
        self.current_file_path = ""
        self.data_store = {}
        
        # 1. 메인 레이아웃
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(10, 10, 10, 10)
        
        # 2. 스크롤 영역 설정 (파라미터가 많아 아래로 길어질 때 필수)
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("QScrollArea { border: none; }")
        
        # 3. 입력 폼들이 실제로 배치될 내부 컨테이너
        self.container_widget = QWidget()
        self.form_layout = QVBoxLayout(self.container_widget)
        self.form_layout.setAlignment(Qt.AlignTop)
        
        scroll_area.setWidget(self.container_widget)
        self.main_layout.addWidget(scroll_area)
        
        # 4. 하단 고정 [저장] 버튼 구성
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.btn_save = QPushButton(f"💾 {self.tab_name} 파일 개별 저장")
        self.btn_save.setMinimumSize(180, 35)
        self.btn_save.setStyleSheet("font-weight: bold; background-color: #1E40AF; color: white; border-radius: 4px;")
        self.btn_save.clicked.connect(self.trigger_save)
        btn_layout.addWidget(self.btn_save)
        
        self.main_layout.addLayout(btn_layout)

    def load_data(self, file_path, data):
        """ 자식 탭들이 데이터를 전달받아 화면을 그리기 전 호출되는 함수 """
        self.current_file_path = file_path
        self.data_store = data
        self.refresh_ui()

    def refresh_ui(self):
        """ 자식 클래스들이 각자 오버라이딩하여 입력창을 채우는 함수 """
        pass

    def collect_inputs(self):
        """ 자식 클래스들이 각자 입력창의 최종 텍스트를 수집하는 함수 """
        return {}

    def trigger_save(self):
        """ 저장 버튼을 누를 때 코어 엔진을 호출하는 공통 로직 """
        if not self.current_file_path:
            QMessageBox.warning(self, "경고", "먼저 Files 탭에서 .fst 파일을 로드해 주세요.")
            return
            
        updated_data = self.collect_inputs()
        
        # 상위 디렉토리의 핵심 저장 모듈 호출
        from src.core.openfast_io import OpenFastIO
        success = OpenFastIO.save_module_data(self.current_file_path, updated_data)
        
        if success:
            QMessageBox.information(self, "저장 완료", f"[{self.tab_name}] 변경 내용이 파일에 성공적으로 기록되었습니다.")
