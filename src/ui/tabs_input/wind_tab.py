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
from PySide6.QtWidgets import QTextEdit, QPushButton, QHBoxLayout

from PySide6.QtWidgets import QFileDialog, QInputDialog, QMessageBox, QWidget, QVBoxLayout, QTreeView

from src.core.openfast_io import OpenFastIO  # 코어 엔진 임포트

class WindTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        self.setAcceptDrops(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        layout.setAlignment(Qt.AlignTop)

        # 타이틀 라벨
        title_label = QLabel("💨 Wind / InflowWind Status")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #1E3A8A;")
        layout.addWidget(title_label)

        # 상태 표시 라벨
        self.lbl_status = QLabel("...")
        self.lbl_status.setStyleSheet("font-size: 14px; padding: 10px; background-color: #F1F5F9; border-radius: 5px;")
        self.lbl_status.setWordWrap(True)
        layout.addWidget(self.lbl_status)

        # UI 업데이트
        self.refresh_ui()

    def on_tab_enter(self):
        """ Wind 탭에 진입할 때마다 UI를 새로고침합니다. """
        self.refresh_ui()

    def refresh_ui(self):
        """ OpenFastIO.current_config를 기반으로 화면 내용을 업데이트합니다. """
        # CompInflow 값에 따른 상태 메시지 맵
        status_map = {
            "0": "0: Still air - 바람이 없는 정적 상태로 시뮬레이션합니다.",
            "1": "1: InflowWind - InflowWind 모듈을 사용하여 바람 데이터를 읽어옵니다.",
            "2": "2: External from ExtInflow - 외부 프로그램(예: TurbSim)으로부터 바람 데이터를 받습니다."
        }

        # OpenFastIO에서 현재 설정된 CompInflow 값을 가져옵니다.
        config = OpenFastIO.current_config.get("CompInflow", {})
        current_value = config.get("current") or config.get("default", "0")
        
        # 값에 해당하는 메시지를 라벨에 표시합니다.
        self.lbl_status.setText(status_map.get(current_value, "알 수 없는 상태입니다."))
