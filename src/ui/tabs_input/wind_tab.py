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
    def init_ui(self):
        """ 🎨 트리뷰 레이아웃 배치 및 이벤트 바인딩 """
        self.setAcceptDrops(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)

    def check_and_load_default_data(self):
        """ 📁 기본 데이터를 확인하고 로드하는 메서드 """
        # TODO: Implement default data loading logic here
        print("Checking and loading default wind data...")

        pass
