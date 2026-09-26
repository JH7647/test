"""Process Queue Management — 큐 상태 + QProcess 실행/종료 통합 관리"""
import os
import json
import subprocess
from datetime import datetime
from typing import Optional, Callable, List, Dict, Any
from dataclasses import dataclass, field

from PySide6.QtCore import QProcess, QObject, Signal, QTimer
from PySide6.QtWidgets import QMessageBox


# ─── 상태 상수 ───
PROCESS_TREE_STATUS_PENDING = 0
PROCESS_TREE_STATUS_RUNNING = 1
PROCESS_TREE_STATUS_COMPLETED = 2
PROCESS_TREE_STATUS_STOP = 3
PROCESS_TREE_STATUS_ERROR = 4


@dataclass
class QueueItem:
    """큐 내 단일 항목 데이터"""
    path: str
    status: int = PROCESS_TREE_STATUS_PENDING
    start_time: str = ""
    end_time: str = ""
    success: Optional[bool] = None
    pid: Optional[int] = None
    log: str = ""


class ProcessQueue:
    """큐 상태 관리 (UI 독립적, 순수 데이터)"""
    
    def __init__(self, max_concurrent: int = 3):
        self.max_concurrent = max_concurrent
        self.pending: List[QueueItem] = []
        self.running: List[QueueItem] = []
        self.completed: List[QueueItem] = []
    
    def add_pending(self, file_path: str) -> QueueItem:
        item = QueueItem(path=file_path)
        self.pending.append(item)
        return item
    
    def move_to_running(self, item: QueueItem) -> None:
        if item in self.pending:
            self.pending.remove(item)
        item.status = PROCESS_TREE_STATUS_RUNNING
        item.start_time = datetime.now().strftime("%H:%M:%S")
        self.running.append(item)
    
    def move_to_completed(self, item: QueueItem, success: bool) -> None:
        if item in self.running:
            self.running.remove(item)
        item.status = PROCESS_TREE_STATUS_COMPLETED if success else PROCESS_TREE_STATUS_ERROR
        item.success = success
        item.end_time = datetime.now().strftime("%H:%M:%S")
        self.completed.append(item)
    
    def move_to_stopped(self, item: QueueItem) -> None:
        if item in self.running:
            self.running.remove(item)
        elif item in self.pending:
            self.pending.remove(item)
        item.status = PROCESS_TREE_STATUS_STOP
        item.end_time = datetime.now().strftime("%H:%M:%S")
        self.completed.append(item)
    
    def remove_item(self, item: QueueItem) -> None:
        for lst in (self.pending, self.running, self.completed):
            if item in lst:
                lst.remove(item)
                break
    
    def can_start_next(self) -> bool:
        return len(self.running) < self.max_concurrent and len(self.pending) > 0
    
    def get_next_pending(self) -> Optional[QueueItem]:
        if self.pending:
            return self.pending[0]
        return None
    
    def to_dict(self) -> Dict[str, Any]:
        def item_to_dict(item: QueueItem) -> Dict[str, Any]:
            return {
                "path": item.path,
                "status": item.status,
                "start_time": item.start_time,
                "end_time": item.end_time,
                "success": item.success,
            }
        return {
            "pending": [item_to_dict(i) for i in self.pending],
            "running": [item_to_dict(i) for i in self.running],
            "completed": [item_to_dict(i) for i in self.completed],
            "max_concurrent": self.max_concurrent,
            "timestamp": datetime.now().isoformat(),
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ProcessQueue':
        def dict_to_item(d: Dict[str, Any]) -> QueueItem:
            item = QueueItem(path=d["path"])
            item.status = d.get("status", 0)
            item.start_time = d.get("start_time", "")
            item.end_time = d.get("end_time", "")
            item.success = d.get("success")
            return item
        
        q = cls(max_concurrent=data.get("max_concurrent", 3))
        q.pending = [dict_to_item(i) for i in data.get("pending", [])]
        q.running = [dict_to_item(i) for i in data.get("running", [])]
        q.completed = [dict_to_item(i) for i in data.get("completed", [])]
        return q
    
    def save(self, filepath: str) -> bool:
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(self.to_dict(), f, indent=2)
            return True
        except Exception as e:
            print(f"❌ 큐 저장 실패: {e}")
            return False
    
    @classmethod
    def load(cls, filepath: str) -> Optional['ProcessQueue']:
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return cls.from_dict(data)
        except Exception as e:
            print(f"❌ 큐 로드 실패: {e}")
            return None


class ProcessRunner(QObject):
    """QProcess 래퍼 — 실행, 스트리밍, 강제 종료 처리"""
    
    output_received = Signal(str, str)      # file_path, data
    process_finished = Signal(str, int)     # file_path, exit_code
    progress_updated = Signal(str, int)     # file_path, percent
    
    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.processes: Dict[str, QProcess] = {}
        self.openfast_exe: str = ""
    
    def set_openfast_exe(self, exe_path: str) -> None:
        self.openfast_exe = exe_path
    
    def find_openfast_exe(self, settings_prefix: str = "JHLEE/OFA") -> str:
        """설정/기본 경로에서 OpenFAST 실행파일 찾기"""
        from PySide6.QtCore import QSettings
        settings = QSettings(*settings_prefix.split('/'))
        exe = settings.value("OpenFastExe", "")
        if exe and os.path.exists(exe):
            self.openfast_exe = exe
            return exe
        
        defaults = [
            r"C:\OpenFAST\openfast.exe",
            r"C:\Program Files\OpenFAST\openfast.exe",
        ]
        for p in defaults:
            if os.path.exists(p):
                self.openfast_exe = p
                return p
        return ""
    
    def start(self, file_path: str) -> bool:
        """OpenFAST 프로세스 시작"""
        if file_path in self.processes:
            return False
        
        if not self.openfast_exe:
            self.find_openfast_exe()
        
        if not self.openfast_exe or not os.path.exists(self.openfast_exe):
            self.process_finished.emit(file_path, 1)
            return False
        
        proc = QProcess(self)
        self.processes[file_path] = proc
        
        proc.setProgram(self.openfast_exe)
        proc.setArguments([file_path])
        proc.setWorkingDirectory(os.path.dirname(file_path))
        
        proc.readyReadStandardOutput.connect(
            lambda fp=file_path, p=proc: self._on_ready_read(fp, p)
        )
        proc.finished.connect(
            lambda exit_code, exit_status, fp=file_path: self._on_finished(fp, exit_code)
        )
        
        proc.start()
        return True
    
    def _on_ready_read(self, file_path: str, proc: QProcess) -> None:
        try:
            data = proc.readAllStandardOutput().data().decode('utf-8', errors='ignore')
            if data:
                self.output_received.emit(file_path, data)
                
                # 진행률 파싱 (Time: X of Y seconds)
                import re
                PROGRESS_RE = re.compile(r"Time:\s*(\d+)\s+of\s+(\d+)\s+seconds")
                match = PROGRESS_RE.search(data)
                if match:
                    current = int(match.group(1))
                    total = int(match.group(2))
                    if total > 0:
                        percent = int((current / total) * 100)
                        self.progress_updated.emit(file_path, percent)
        except Exception as e:
            print(f"❌ 스트리밍 예외: {e}")
    
    def _on_finished(self, file_path: str, exit_code: int) -> None:
        if file_path in self.processes:
            del self.processes[file_path]
        self.process_finished.emit(file_path, exit_code)
    
    def terminate(self, file_path: str) -> bool:
        """3단계 강제 종료 (terminate → kill → taskkill)"""
        proc = self.processes.get(file_path)
        if not proc:
            return False
        
        # 1단계: terminate
        proc.terminate()
        if proc.waitForFinished(2000):
            return True
        
        # 2단계: kill
        proc.kill()
        if proc.waitForFinished(3000):
            return True
        
        # 3단계: system taskkill (자식 프로세스 포함)
        try:
            pid = proc.pid()
            result = subprocess.run(
                f'taskkill /F /PID {pid} /T',
                shell=True, capture_output=True, text=True, timeout=5
            )
            print(f"⚡ [System Kill] PID={pid}: {result.stdout.strip()}")
            proc.waitForFinished(1000)
            return True
        except Exception as e:
            print(f"⚠️ System Kill 예외: {e}")
            return False
    
    def cleanup_all(self) -> None:
        """모든 프로세스 정리"""
        for file_path, proc in list(self.processes.items()):
            if proc.state() == QProcess.Running:
                try:
                    proc.readyReadStandardOutput.disconnect()
                    proc.finished.disconnect()
                except RuntimeError:
                    pass
                proc.kill()
                proc.waitForFinished(1000)
        self.processes.clear()


class ProcessQueueManager(QObject):
    """큐 + 러너 통합 관리자 — FilesTab에서 사용하는 메인 인터페이스"""
    
    # UI 업데이트용 시그널
    item_added = Signal(object)           # QueueItem
    item_updated = Signal(object)         # QueueItem
    item_removed = Signal(object)         # QueueItem
    log_received = Signal(str, str)       # file_path, data
    progress_updated = Signal(str, int)   # file_path, percent
    buttons_update_needed = Signal()      # 버튼 상태 갱신 요청
    
    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.queue = ProcessQueue()
        self.runner = ProcessRunner(self)
        
        # 러너 시그널 연결
        self.runner.output_received.connect(self._on_output)
        self.runner.process_finished.connect(self._on_process_finished)
        self.runner.progress_updated.connect(self._on_progress)
    
    def set_openfast_exe(self, exe_path: str) -> None:
        self.runner.set_openfast_exe(exe_path)
    
    def add_file(self, file_path: str) -> QueueItem:
        """파일 추가 → pending → 즉시 시작 시도"""
        item = self.queue.add_pending(file_path)
        self.item_added.emit(item)
        self._try_start_next()
        return item
    
    def _try_start_next(self) -> None:
        while self.queue.can_start_next():
            item = self.queue.get_next_pending()
            if not item:
                break
            self.queue.move_to_running(item)
            self.item_updated.emit(item)
            self.runner.start(item.path)
    
    def _on_process_finished(self, file_path: str, exit_code: int) -> None:
        item = self._find_item(file_path)
        if item:
            success = (exit_code == 0)
            self.queue.move_to_completed(item, success)
            self.item_updated.emit(item)
        self._try_start_next()
    
    def _on_output(self, file_path: str, data: str) -> None:
        item = self._find_item(file_path)
        if item:
            item.log += data
        self.log_received.emit(file_path, data)
    
    def _on_progress(self, file_path: str, percent: int) -> None:
        self.progress_updated.emit(file_path, percent)
    
    def _find_item(self, file_path: str) -> Optional[QueueItem]:
        for lst in (self.queue.pending, self.queue.running, self.queue.completed):
            for item in lst:
                if item.path == file_path:
                    return item
        return None
    
    def stop_item(self, item: QueueItem) -> bool:
        """실행 중인 항목 강제 중단"""
        if item.status != PROCESS_TREE_STATUS_RUNNING:
            return False
        
        if self.runner.terminate(item.path):
            self.queue.move_to_stopped(item)
            self.item_updated.emit(item)
            return True
        return False
    
    def remove_item(self, item: QueueItem) -> None:
        """항목 제거 (실행 중이면 먼저 중단)"""
        if item.status == PROCESS_TREE_STATUS_RUNNING:
            self.stop_item(item)
        self.queue.remove_item(item)
        self.item_removed.emit(item)
        self._try_start_next()
    
    def move_pending_up(self, item: QueueItem) -> bool:
        """pending 항목 위로 이동"""
        idx = self.queue.pending.index(item)
        if idx > 0:
            self.queue.pending[idx], self.queue.pending[idx-1] = self.queue.pending[idx-1], self.queue.pending[idx]
            return True
        return False
    
    def move_pending_down(self, item: QueueItem) -> bool:
        """pending 항목 아래로 이동"""
        idx = self.queue.pending.index(item)
        if idx < len(self.queue.pending) - 1:
            self.queue.pending[idx], self.queue.pending[idx+1] = self.queue.pending[idx+1], self.queue.pending[idx]
            return True
        return False
    
    def save_queue(self, work_dir: str) -> bool:
        return self.queue.save(os.path.join(work_dir, ".ofa_run_queue.json"))
    
    def load_queue(self, work_dir: str) -> bool:
        path = os.path.join(work_dir, ".ofa_run_queue.json")
        loaded = ProcessQueue.load(path)
        if loaded:
            self.queue = loaded
            return True
        return False
    
    def cleanup(self) -> None:
        self.runner.cleanup_all()
    
    def get_all_items(self) -> List[QueueItem]:
        return self.queue.pending + self.queue.running + self.queue.completed

    def adjust_max_concurrent(self, parent_widget, current_value: int) -> Optional[int]:
        """최대 동시 실행 개수 조절 다이얼로그 표시 및 설정 변경"""
        from PySide6.QtWidgets import QInputDialog
        count, ok = QInputDialog.getInt(
            parent_widget, "런 개수 설정",
            "최대 동시 실행 개수를 입력하세요:",
            current_value, 1, 20, 1
        )
        if ok:
            self.queue.max_concurrent = count
            self._try_start_next()
            return count
        return None