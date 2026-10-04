""" 선형화(.lin) MBC 처리 및 VTK 가시화 출력용 모달리스 창 (LinearizationWindow) """

import io
import os
import sys
import subprocess

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTextEdit, QMessageBox, QApplication, QLineEdit, QLabel, QTextEdit,
                               QPushButton, QHBoxLayout, QVBoxLayout, QSplitter, QComboBox, QCheckBox, QScrollArea, QFrame, )
from PySide6.QtCore import Qt, QSettings, QProcess

# openfast_toolbox 패키지가 src 하위에 있으므로 경로 보강
_PROJECT_SRC = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_SRC not in sys.path:
    sys.path.append(_PROJECT_SRC)

sys.path.append(r"C:\TEST\WB")
sys.path.append(r"C:\TEST\WB\src")


class LinearizationWindow(QDialog):
    """ .lin → MBC → .bin/.viz 생성 → OpenFAST -VTKLin 구동 """

    def __init__(self, parent, lin_file):
        super().__init__(parent, Qt.Window)

        self._proc = None

        self.lin_file = os.path.normpath(os.path.abspath(lin_file))
        dir           = os.path.dirname(lin_file)
        name          = os.path.basename(lin_file)

        prefix     = name.rsplit('.', 1)[0] + '.'
        prefix_chp = name.split('.', 1)[0] + '.' 

        self.chkp_out = os.path.join(dir, f"{prefix_chp}ModeShapeVTK.chkp")
        self.bin_out  = os.path.join(dir, f"{prefix}ModeShapeVTK.bin")
        self.viz_out  = os.path.join(dir, f"{prefix}ModeShapeVTK.viz")

        self.setWindowTitle("Linearization (MBC -> VTK)")
        self.resize(860, 520)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        self.lbl_path = QLabel(f"Target : {self.lin_file}")
        layout.addWidget(self.lbl_path)

        self.btn_resonance = QPushButton("Calculate resonance Frequency")
        self.btn_resonance.clicked.connect(self.run_resonance)

        self.btn_vtk = QPushButton("Generate VTK")
        self.btn_vtk.clicked.connect(self.gen_vtk)

        btns = QHBoxLayout()
        btns.addWidget(self.btn_resonance, stretch=1)
        btns.addWidget(self.btn_vtk, stretch=1)
        layout.addLayout(btns)

        input = QHBoxLayout()
        lbl_modes = QLabel("📍Mode number to visualize : 1, 2, [3:5], 6 ....")
        self.txt_modes = QLineEdit("[1:6]")
        input.addWidget(lbl_modes, stretch=1)
        input.addWidget(self.txt_modes, stretch=2)
        layout.addLayout(input)

        input = QHBoxLayout()
        lbl_scale = QLabel("📍Scale to visualize : 10 ")
        self.txt_scale = QLineEdit("10")
        input.addWidget(lbl_scale, stretch=1)
        input.addWidget(self.txt_scale, stretch=2)
        layout.addLayout(input)    
         
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        layout.addWidget(self.log, stretch=1)

        if os.path.exists(self.lin_file):
            self.log.append(f".lin : {self.lin_file}")
        if os.path.exists(self.bin_out):            
            self.log.append(f".bin : {self.bin_out}")
        if os.path.exists(self.chkp_out):
            self.log.append(f".chkp : {self.chkp_out}")
        if os.path.exists(self.viz_out):
            self.log.append(f".viz : {self.viz_out}")

    @staticmethod
    def show_window(parent, lin_file):
        """ .lin 절대 경로를 받아 창을 띄웁니다. """
        if not lin_file or not os.path.isabs(str(lin_file)) or not os.path.exists(lin_file) \
                or not lin_file.lower().endswith(".lin"):
            QMessageBox.warning(parent, "파일 오류", "유효한 .lin 파일이 아닙니다.\n\n경로: " + str(lin_file))
            return

        LinearizationWindow(parent, lin_file).show()

    def run_resonance(self):
        """ .lin → 고유진동수 계산 """
        if not os.path.exists(self.lin_file):
            QMessageBox.critical(self, "파일 오류", f".lin 파일이 없습니다.\n{self.lin_file}")
            return

        # 고유진동수 해석 ----------------------------------------------------------
        self.btn_resonance.setEnabled(False)
        QApplication.processEvents()

        try:
            from src.core import mode_linearization

            import io
            self.log.append("\n...Calculating the resonance frequency...\n")
            QApplication.processEvents()

            captured = io.StringIO()
            old_stdout = sys.stdout
            sys.stdout = captured
            try:
                mode_linearization.mode_from_lin(self.lin_file)
            finally:
                sys.stdout = old_stdout

            # 캡처한 내용을 로그창에 반영
            self.log.append(captured.getvalue())

        except Exception as e:
            self.log.append(f"ERROR: {e}\n")

        self.btn_resonance.setEnabled(True)
        #--------------------------------------------------------------------------

        # .bin 생성 ----------------------------------------------------------------
        MBC, matData = mode_linearization.fx_mbc3([self.lin_file], self.bin_out)
        nModes = len(MBC['eigSol']['NaturalFreqs_Hz'])
        modes_str = ','.join(str(i) for i in range(1, nModes + 1))
        #--------------------------------------------------------------------------

    def gen_vtk(self):
        """ .viz 생성 후 OpenFAST -VTKLin 구동 """
        if not os.path.exists(self.lin_file):
            QMessageBox.critical(self, "파일 오류", f".lin 파일이 없습니다.\n{self.lin_file}")
            return

        self.btn_vtk.setEnabled(False)
        self.btn_resonance.setEnabled(False)
        QApplication.processEvents()

        # bin / chkp 존재 확인 -----------------------------------------------------
        if not os.path.exists(self.bin_out):
            QMessageBox.critical(self, "파일 오류", f".bin 파일이 없습니다.\n{self.bin_out}")
            self.btn_vtk.setEnabled(True)
            self.btn_resonance.setEnabled(True)
            return
        if not os.path.exists(self.chkp_out):
            QMessageBox.critical(self, "파일 오류", f"chkp 파일이 없습니다.\n{self.chkp_out}")
            self.btn_vtk.setEnabled(True)
            self.btn_resonance.setEnabled(True)
            return

        modes = []
        for token in self.txt_modes.text().replace(" ", "").split(","):
            if not token:
                continue
            if token.startswith("[") and token.endswith("]"):
                rng = token[1:-1].split(":")
                if len(rng) == 2 and rng[0].isdigit() and rng[1].isdigit():
                    modes.extend(range(int(rng[0]), int(rng[1]) + 1))
            elif token.isdigit():
                modes.append(int(token))

        if not modes:
            QMessageBox.warning(self, "입력 오류",
                                "Mode 입력을 해석할 수 없습니다.\n")
            self.btn_vtk.setEnabled(True)
            self.btn_resonance.setEnabled(True)
            return

        nModes = len(modes)
        modes_str = ', '.join(str(m) for m in modes)

        scale = self.txt_scale.text().strip() or "1"

        # Generating .viz file
        viz_content = (
            "------- OpenFAST MODE-SHAPE INPUT FILE -------------------------------------------\n"
            "# Options for visualizing mode shapes\n"
            "---------------------- FILE NAMES ----------------------------------------------\n"
            f'"{os.path.splitext(os.path.basename(self.chkp_out))[0]}"   CheckpointRoot - Rootname of the checkpoint file\n'
            f'"{os.path.basename(self.bin_out)}"                         ModesFileName - Name of the mode-shape file\n'
            "---------------------- VISUALIZATION OPTIONS -----------------------------------\n"
            f"{nModes}        VTKLinModes   - Number of modes to visualize\n"
            f"{modes_str}     VTKModes      - List of modes\n"
            f"{scale}         VTKLinScale   - Mode shape visualization scaling factor\n"
            "2          VTKLinTim     - Switch to make one animation for all LinTimes together\n"
            "true       VTKLinTimes1  - Visualize modes at LinTimes(1) only\n"
            "0.0        VTKLinPhase   - Phase\n"
        )

        with open(self.viz_out, 'w', encoding='utf-8') as f:
            f.write(viz_content)

        self.log.append(f"\n... {self.viz_out} was generated!\n  - Mode number : {nModes} ({modes_str})\n  - Scale: {scale}\n")

        # Run openFAST and generating VTKs 
        self.log.append(f"\n... Generating VTK files with OpenFAST!\n")
        self.run_openfast()

    def run_openfast(self):
        """ 생성된 .viz 로 OpenFAST -VTKLin 구동 """

        openfast_exe = self._find_openfast()
        if not openfast_exe or not os.path.exists(openfast_exe):
            self.log.append("WARNING: OpenFAST.exe 경로가 없어 -VTKLin 구동을 건너뜁니다.\n")
            self.btn_vtk.setEnabled(True)
            self.btn_resonance.setEnabled(True)
            return

        self.log.append(f"\nOpenFAST -VTKLin 구동 중...\n")


        proc = QProcess(self)
        self._proc = proc                                  # 종료 시 kill 용으로 보관

        proc.readyReadStandardOutput.connect(
            lambda: self.log.append(bytes(proc.readAllStandardOutput()).decode('utf-8', 'ignore'))
        )
        proc.finished.connect(self._on_openfast_finished)

        proc.setProgram(openfast_exe)
        proc.setArguments(["-VTKLin", self.viz_out])
        proc.setWorkingDirectory(os.path.dirname(self.viz_out))

        # [개선]] 표준 에러(Stderr)를 표준 출력(Stdout)과 합쳐서 하나의 채널로 읽어옵니다.
        proc.setProcessChannelMode(QProcess.MergedChannels)

        proc.start()

    def _on_openfast_finished(self, exit_code, exit_status):
        self.log.append(f"\nOpenFAST 종료 (code={exit_code})\n")
        self._proc = None
        self.btn_vtk.setEnabled(True)
        self.btn_resonance.setEnabled(True)

    def _find_openfast(self):
        """ QSettings에 저장된 OpenFAST.exe 경로를 읽어옵니다. """
        openfast_exe = QSettings("JHLEE", "OFA").value("OpenFastExe", "")

        if not openfast_exe or not os.path.exists(openfast_exe):
            default_paths = [
                r"C:\OpenFAST\openfast.exe",
                r"C:\Program Files\OpenFAST\openfast.exe",
                r"C:\Users\jeong\Downloads\BU_openFAST\OpenFAST.exe",  # 사용자 환경 경로 포용
            ]
            for p in default_paths:
                if os.path.exists(p):
                    openfast_exe = p
                    break

        if not openfast_exe or not os.path.exists(openfast_exe):
            QMessageBox.critical(self, "OpenFAST 없음", "OpenFAST 실행 파일을 찾을 수 없습니다.")
            return

        return openfast_exe if openfast_exe and os.path.exists(openfast_exe) else ""
    

    def closeEvent(self, event):
        proc = getattr(self, '_proc', None)
        if proc is not None:
            if proc.state() != QProcess.NotRunning:
                proc.kill()
                proc.waitForFinished(1000)
            self._proc = None
            try:
                proc.readyReadStandardOutput.disconnect()
                proc.finished.disconnect()
            except RuntimeError:
                pass
        super().closeEvent(event)
