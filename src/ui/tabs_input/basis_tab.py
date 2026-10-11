# -*- coding: utf-8 -*-
"""
🗼Basis  —  SubDyn.dat 구조(Basis) 3D 뷰어 탭

- .fst 의 SubFile(SubDyn.dat) 을 파싱해 Joint / Member / 집중질량(CM) 을 읽는다- 좌측: 회전·줌·패닝 가능한 3D 그래프
- 우측: Node / Element 표시 제어 패널 (Show All / Show 편집창 / Disappear 편집창)
"""
import os
import math

from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtGui import QColor, QPainter, QPen, QFont
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QCheckBox,
    QGroupBox, QSplitter, QMessageBox, QDialog, QDialogButtonBox,
    QListWidget, QListWidgetItem, QAbstractItemView,
)

from src.core.openfast_io import OpenFastIO

# =====================================================================================
# 0. 탭
# =====================================================================================
class BasisTab(QWidget):
    def __init__(self, main_window=None, parent=None):
        super().__init__(parent)
        self.main_window = main_window

        self.subdyn_path = ""
        self.joints = {}
        self.members = []
        self.cm_points = []

        self.init_ui()

    # ---------------------------------------------------------------- UI
    def init_ui(self):
        self.count_labels = {}

        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 10, 10, 10)

        # ---- 상단 바 ----
        top = QHBoxLayout()
        top.setSpacing(12)

        lbl_name = QLabel("📝 SubDyn File:")
        lbl_name.setStyleSheet("font-weight: bold; font-size: 14px;")
        self.lbl_file_path = QLabel("N/A")
        self.lbl_file_path.setStyleSheet("font-weight: bold; font-size: 14px;")
        self.lbl_file_path.mouseDoubleClickEvent = self.open_file_in_editor
        top.addWidget(lbl_name)
        top.addWidget(self.lbl_file_path, 1)

        self.chk_node_label = QCheckBox("노드 라벨")
        self.chk_elem_label = QCheckBox("멤버 라벨")
        self.chk_declutter = QCheckBox("겹치는 라벨 숨김")
        self.chk_node_label.setChecked(True)
        self.chk_elem_label.setChecked(True)
        self.chk_declutter.setChecked(False)
        self.chk_node_label.toggled.connect(self._on_label_toggle)
        self.chk_elem_label.toggled.connect(self._on_label_toggle)
        self.chk_declutter.toggled.connect(self._on_label_toggle)
        top.addWidget(self.chk_node_label)
        top.addWidget(self.chk_elem_label)
        top.addWidget(self.chk_declutter)

        self.btn_reset_view = QPushButton("🎥 시점 초기화")
        self.btn_reset_view.clicked.connect(self.on_reset_view)
        self.btn_reload = QPushButton("🔄 Reload")
        self.btn_reload.clicked.connect(self.reload_model)
        top.addWidget(self.btn_reset_view)
        top.addWidget(self.btn_reload)

        lay.addLayout(top)

        # ---- 좌: 3D 뷰 / 우: 제어 패널 ----
        splitter = QSplitter(Qt.Horizontal)
        self.view3d = Basis3DView()
        splitter.addWidget(self.view3d)

        right = QWidget()
        rv = QVBoxLayout(right)
        rv.setContentsMargins(10, 10, 10, 10)
        rv.addWidget(self._build_group("📦 Node", "node"))
        rv.addWidget(self._build_group("🔗 Element", "elem"))
        rv.addStretch()

        self.lbl_status = QLabel("")
        self.lbl_status.setWordWrap(True)
        self.lbl_status.setStyleSheet("color: #4B5563; font-size: 12px;")
        rv.addWidget(self.lbl_status)

        splitter.addWidget(right)
        splitter.setSizes([720, 380])
        lay.addWidget(splitter)

        self.reload_model()

    def _build_group(self, title, kind):
        gb = QGroupBox(title)
        gb.setStyleSheet("font-weight: bold;")
        v = QVBoxLayout(gb)

        b_all = QPushButton("Show All")
        b_all.clicked.connect(lambda k=kind: self.on_show_all(k))
        v.addWidget(b_all)

        row = QHBoxLayout()
        b_show = QPushButton("Show 선택…")
        b_show.clicked.connect(lambda k=kind: self.on_select(kind, "show"))
        b_hide = QPushButton("Disappear 선택…")
        b_hide.clicked.connect(lambda k=kind: self.on_select(kind, "hide"))
        row.addWidget(b_show)
        row.addWidget(b_hide)
        v.addLayout(row)

        lbl = QLabel("")
        lbl.setStyleSheet("font-size: 12px; color: #4B5563;")
        v.addWidget(lbl)
        self.count_labels[kind] = lbl

        return gb

    # ---------------------------------------------------------------- 표시 제어
    def _ids_of(self, kind):
        if kind == "node":
            return list(self.joints.keys()), set(self.view3d.node_visible)
        return [m[0] for m in self.members], set(self.view3d.elem_visible)

    def on_show_all(self, kind):
        all_ids, _ = self._ids_of(kind)
        self._apply(kind, set(all_ids))

    def on_select(self, kind, mode):
        all_ids, current = self._ids_of(kind)
        if not all_ids:
            QMessageBox.information(self, "알림", "표시할 데이터가 없습니다.")
            return

        name = "Node" if kind == "node" else "Element"
        if mode == "show":
            dlg = IdSelectDialog(f"{name} - Show", all_ids, all_ids, self)
        else:
            dlg = IdSelectDialog(f"{name} - Disappear", all_ids, current, self)

        if dlg.exec() != QDialog.Accepted:
            return

        picked = set(dlg.checked_ids())
        self._apply(kind, (current | picked) if mode == "show" else (current - picked))

    def _apply(self, kind, ids):
        if kind == "node":
            self.view3d.set_node_visible(ids)
        else:
            self.view3d.set_elem_visible(ids)
        self._update_count_labels()

    def _update_count_labels(self):
        self.count_labels["node"].setText(f"표시 중: {len(self.view3d.node_visible)} / {len(self.joints)}")
        self.count_labels["elem"].setText(f"표시 중: {len(self.view3d.elem_visible)} / {len(self.members)}")

    def _on_label_toggle(self):
        self.view3d.show_node_label = self.chk_node_label.isChecked()
        self.view3d.show_elem_label = self.chk_elem_label.isChecked()
        self.view3d.declutter = self.chk_declutter.isChecked()
        self.view3d.update()

    def on_reset_view(self):
        self.view3d.reset_view()

    # ---------------------------------------------------------------- 데이터 로드
    def get_subdyn_path(self):
        main_fst = OpenFastIO.current_config.get("MainFST", {}).get("current", "")
        if not main_fst or not os.path.isfile(main_fst):
            return ""

        sub = OpenFastIO.current_config.get("SubFile", {})
        sub_name = sub.get("current") or sub.get("default") or ""
        if not sub_name:
            return ""

        return OpenFastIO.get_absolute_path(main_fst, sub_name)

    def reload_model(self):
        path = self.get_subdyn_path()
        self.subdyn_path = path

        if not path or not os.path.exists(path):
            self.joints, self.members, self.cm_points = {}, [], []
            self.lbl_file_path.setText("N/A")
            self.lbl_status.setText("⚠️ SubDyn 파일을 찾을 수 없습니다. (.fst 의 CompSub / SubFile 을 확인하세요)")
            self.view3d.set_model({}, [], [])
            self._update_count_labels()
            return

        self.joints, self.members, self.cm_points = parse_subdyn(path)
        self.lbl_file_path.setText(path)
        self.view3d.set_model(self.joints, self.members, self.cm_points)
        self._update_count_labels()
        self.lbl_status.setText(
            f"Joint {len(self.joints)} 개 · Member {len(self.members)} 개 · CM {len(self.cm_points)} 개\n"
            "드래그: 회전 / 휠: 줌 / 가운데·우클릭 드래그: 이동 / 더블클릭: 시점 초기화"
        )

    # ---------------------------------------------------------------- 탭 훅
    def on_tab_enter(self):
        """ Basis 탭에 진입할 때마다 SubDyn 데이터를 다시 읽습니다. """
        self.reload_model()

    def on_tab_leave(self):
        """ 읽기 전용 탭이므로 처리 없음 """

    def open_file_in_editor(self, event):
        """ lbl_file_path 더블클릭 → Notepad++ 로 SubDyn 파일 열기 """
        path = self.lbl_file_path.text()
        if not path or not os.path.exists(path):
            QMessageBox.warning(self, "파일 오류", "유효한 파일 경로가 아닙니다.")
            return

        npp = r"C:\Program Files\Notepad++\notepad++.exe"
        try:
            if os.path.exists(npp):
                import subprocess
                subprocess.Popen([npp, path])
            else:
                import subprocess
                subprocess.Popen(["notepad.exe", path])
        except Exception as e:
            QMessageBox.critical(self, "실행 오류", f"파일을 여는 중 오류가 발생했습니다:\n{e}")


# =====================================================================================
# 1. parse_subdyn
# =====================================================================================
def parse_subdyn(subdyn_path):
    """
    SubDyn.dat → (joints, members, cm_points)
        joints   : { JointID: (x, y, z) }
        members  : [ (MemberID, MJointID1, MJointID2), ... ]
        cm_points: [ (CMJointID, (x, y, z), JMass), ... ]
    """
    joints, members, cm_points = {}, [], []

    if not subdyn_path or not os.path.isfile(subdyn_path):
        return joints, members, cm_points

    try:
        with open(subdyn_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.read().splitlines()
    except Exception as e:
        print(f"❌ SubDyn.dat 읽기 실패: {e}")
        return joints, members, cm_points

    def toks(s):
        return s.replace(",", " ").replace("!", " ").split()

    def to_int(s):
        return int(float(s))          # "1.0" 같은 경우도 허용

    def read_table(start, count, ncols, conv):
        """ 헤더 다음(단위행)2행 skip → count 개만 읽는다.
            개수를 선언한 개수로 제한하므로 뒤쪽의 'MemberID'(MEMBER OUTPUT LIST) 표를 절대 건드리지 않는다.
            그래도 넘치면 숫자가 아닌 줄에서 즉시 중단한다. """
        out, i, limit = [], start + 2, (count if count > 0 else None)
        while i < len(lines):
            if limit is not None and len(out) >= limit:
                break
            p = toks(lines[i])
            if not p:
                i += 1
                continue
            if len(p) < ncols:
                break
            try:
                out.append(conv(p))
            except (ValueError, IndexError):
                break
            i += 1
        return out, i

    def declared_count(key):
        """ '163 NJoints  - Number of joints (-)' → 163 """
        for ln in lines:
            p = toks(ln)
            if len(p) >= 2 and p[1] == key:
                try:
                    return int(float(p[0]))
                except ValueError:
                    return 0
        return 0

    n_joints  = declared_count("NJoints")
    n_members = declared_count("NMembers")
    n_cmass   = declared_count("NCmass")

    # 같은 헤더(MemberID 등)가 파일에 2번 나올 수 있으므로 1회만 파싱
    seen = set()

    i, n = 0, len(lines)
    while i < n:
        parts = toks(lines[i])
        key = parts[0] if parts else ""

        # ---- JointID JointXss JointYss JointZss JointType ... ----
        if key == "JointID" and "joint" not in seen:
            seen.add("joint")
            rows, i = read_table(i, n_joints, 4,
                                 lambda p: (to_int(p[0]), (float(p[1]), float(p[2]), float(p[3]))))
            for jid, xyz in rows:
                joints[jid] = xyz
            continue

        # ---- MemberID  MJointID1 MJointID2 MPropSetID1 MPropSetID2 MType MSpin/COSMID ----
        if key == "MemberID" and "member" not in seen:
            seen.add("member")
            rows, i = read_table(i, n_members, 3,
                                 lambda p: (to_int(p[0]), to_int(p[1]), to_int(p[2])))
            members.extend(rows)
            continue

        # ---- CMJointID  JMass JMXX ... MCGX MCGY MCGZ ----
        if key == "CMJointID" and "cm" not in seen:
            seen.add("cm")
            rows, i = read_table(i, n_cmass, 4, lambda p: (to_int(p[0]), float(p[1]), p))
            for cid, mass, p in rows:
                # CM 표는 전역좌표지만 구조 위치를 보기 위해 Joint 좌표를 우선 사용
                g = (float(p[8]), float(p[9]), float(p[10])) if len(p) >= 11 else (0.0, 0.0, 0.0)
                cm_points.append((cid, joints.get(cid, g), mass))
            continue

        i += 1

    return joints, members, cm_points

# =====================================================================================
# 2. 3D 그래프 뷰 (직교투영 + QPainter : 회전 / 줌 / 패닝 / 라벨)
# =====================================================================================
class Basis3DView(QWidget):
    COLOR_MEMBER = QColor("#4B5563")
    COLOR_NODE_DOT = QColor("#111827")
    COLOR_NODE_TXT = QColor("#6B7280")   # 노드 숫자: 회색
    COLOR_ELEM_TXT = QColor("#2563EB")   # 멤버 숫자: 파랑
    COLOR_CM_DOT = QColor("#DC2626")
    COLOR_AXIS = QColor("#E5E7EB")

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(520, 420)
        self.setMouseTracking(True)

        self.joints = {}
        self.members = []
        self.cm_points = []

        self.node_visible = set()
        self.elem_visible = set()
        self.show_node_label = True
        self.show_elem_label = True
        self.declutter = False        # True 면 겹치는 라벨을 숨김 (기본 OFF: 전부 표시)

        self.yaw = -55.0
        self.pitch = 18.0
        self.zoom = 1.0
        self._pan = QPointF(0.0, 0.0)
        self._drag_mode = None
        self._last_pos = QPointF()

        self._base_scale = 1.0
        self._center = (0.0, 0.0, 0.0)
        self._recompute_frame()

    # ---------------------------------------------------------------- 데이터
    def set_model(self, joints, members, cm_points):
        self.joints = dict(joints or {})
        self.members = list(members or [])
        self.cm_points = list(cm_points or [])
        self.node_visible = set(self.joints.keys())
        self.elem_visible = set(m[0] for m in self.members)
        self.reset_view()

    def set_node_visible(self, ids):
        self.node_visible = set(ids)
        self._recompute_frame()
        self.update()

    def set_elem_visible(self, ids):
        self.elem_visible = set(ids)
        self.update()

    def reset_view(self):
        self.yaw, self.pitch, self.zoom = -55.0, 18.0, 1.0
        self._pan = QPointF(0.0, 0.0)
        self._recompute_frame()
        self.update()

    # ---------------------------------------------------------------- 좌표계
    def _recompute_frame(self):
        pts = [self.joints[j] for j in self.node_visible if j in self.joints]
        if pts:
            xs = [p[0] for p in pts]; ys = [p[1] for p in pts]; zs = [p[2] for p in pts]
            self._center = ((min(xs) + max(xs)) / 2.0,
                            (min(ys) + max(ys)) / 2.0,
                            (min(zs) + max(zs)) / 2.0)
            ext = max(max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs), 1e-6)
        else:
            self._center = (0.0, 0.0, 0.0)
            ext = 1.0
        self._base_scale = 0.80 * max(self.width(), self.height()) / ext

    def _to2d(self, p):
        """ 월드 좌표 → 화면 좌표 (중심기준 회전 후 직교투영) """
        x, y, z = p[0] - self._center[0], p[1] - self._center[1], p[2] - self._center[2]
        cy, sy = math.cos(math.radians(self.yaw)), math.sin(math.radians(self.yaw))
        cp, sp = math.cos(math.radians(self.pitch)), math.sin(math.radians(self.pitch))
        x1 = x * cy - y * sy
        y1 = x * sy + y * cy
        y2 = y1 * cp - z * sp
        s = self._base_scale * self.zoom
        return (self.width() / 2.0 + x1 * s + self._pan.x(),
                self.height() / 2.0 - y2 * s + self._pan.y())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._recompute_frame()

    # ---------------------------------------------------------------- 그리기
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.fillRect(self.rect(), QColor("#FFFFFF"))

        if not self.joints:
            p.setPen(QColor("#9CA3AF"))
            p.drawText(self.rect(), Qt.AlignCenter,
                       "표시할 데이터가 없습니다.\n(.fst 의 CompSub / SubFile 을 확인하세요)")
            return

        label_boxes = []
        font = QFont("Consolas")
        font.setPointSize(8)
        p.setFont(font)

        # 1) Member 선
        pen = QPen(self.COLOR_MEMBER)
        pen.setWidthF(1.4)
        p.setPen(pen)
        drawn = {}
        for mid, j1, j2 in self.members:
            if mid not in self.elem_visible:
                continue
            if j1 not in self.joints or j2 not in self.joints:
                continue
            a, b = self._to2d(self.joints[j1]), self._to2d(self.joints[j2])
            p.drawLine(QPointF(*a), QPointF(*b))
            drawn[mid] = ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)

        # 2) CM 점
        p.setPen(QPen(self.COLOR_CM_DOT))
        p.setBrush(self.COLOR_CM_DOT)
        for _cid, xyz, _m in self.cm_points:
            cx, cy = self._to2d(xyz)
            p.drawEllipse(QPointF(cx, cy), 3.2, 3.2)
        p.setBrush(Qt.NoBrush)

        # 3) Node 점
        p.setPen(QPen(self.COLOR_NODE_DOT))
        p.setBrush(self.COLOR_NODE_DOT)
        for jid in self.node_visible:
            if jid not in self.joints:
                continue
            x, y = self._to2d(self.joints[jid])
            p.drawEllipse(QPointF(x, y), 2.6, 2.6)
        p.setBrush(Qt.NoBrush)

        # 4) 라벨 (Member 파랑 → Node 회색) : 겹치면 건너뛰어 가독성 확보
        if self.show_elem_label:
            p.setPen(self.COLOR_ELEM_TXT)
            for mid, (mx, my) in drawn.items():
                self._draw_label(p, label_boxes, f"{mid}", mx + 4, my - 10)

        if self.show_node_label:
            p.setPen(self.COLOR_NODE_TXT)
            for jid in self.node_visible:
                if jid not in self.joints:
                    continue
                jx, jy, jz = self.joints[jid]
                x, y = self._to2d((jx, jy, jz))
                self._draw_label(p, label_boxes, f"{jid} ({jx:.2f}, {jy:.2f}, {jz:.2f})", x + 5, y + 2)

        p.end()

    def _draw_label(self, painter, boxes, text, x, y):
        # PySide6 의 QPainter.boundingRect 는 (QPointF, str) 오버로드가 없으므로
        # 기준점만 넣은 빈 QRectF 를 넘긴다. 반환 rect 는 텍스트를 포함하는 영역이 된다.
        rect = painter.boundingRect(QRectF(x, y, 0.0, 0.0), text)

        # 겹침 제거 ON 이면 이미 그려진 라벨과 부딪히는 것을 건너뛴다.
        # OFF 면 전부 그린다 (확대해서 보면 모든 번호를 확인할 수 있다)
        if self.declutter:
            for b in boxes:
                if b.intersects(rect.adjusted(-1, -1, 1, 1)):
                    return

        boxes.append(rect)
        painter.drawText(QPointF(x, y), text)

    # ---------------------------------------------------------------- 마우스
    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        if delta == 0:
            return
        factor = 1.15 if delta > 0 else (1.0 / 1.15)
        self.zoom = max(0.05, min(60.0, self.zoom * factor))
        self.update()
        event.accept()

    def mousePressEvent(self, event):
        self._last_pos = event.position()
        if event.button() == Qt.LeftButton:
            self._drag_mode = "rot"
        elif event.button() in (Qt.MiddleButton, Qt.RightButton):
            self._drag_mode = "pan"
        else:
            self._drag_mode = None

    def mouseMoveEvent(self, event):
        if self._drag_mode is None:
            return
        pos = event.position()
        d = pos - self._last_pos
        if self._drag_mode == "rot":
            self.yaw += d.x() * 0.5
            self.pitch = max(-89.0, min(89.0, self.pitch - d.y() * 0.5))
        else:
            self._pan += d
        self._last_pos = pos
        self.update()

    def mouseReleaseEvent(self, event):
        self._drag_mode = None

    def mouseDoubleClickEvent(self, event):
        self.reset_view()


# =====================================================================================
# 3. 표시 항목 편집 다이얼로그 (Show / Disappear 공용)
# =====================================================================================
class IdSelectDialog(QDialog):
    """ Node / Element 표시 항목을 체크박스로 고르는 편집 창 """

    def __init__(self, title, all_ids, checked_ids, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(300, 420)

        lay = QVBoxLayout(self)
        self.list = QListWidget()
        self.list.setSelectionMode(QAbstractItemView.NoSelection)
        checked = set(checked_ids)
        for i in sorted(all_ids, key=lambda v: (len(str(v)), str(v))):
            it = QListWidgetItem(str(i))
            it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
            it.setCheckState(Qt.Checked if i in checked else Qt.Unchecked)
            self.list.addItem(it)
        lay.addWidget(self.list)

        row = QHBoxLayout()
        b_all = QPushButton("전체 선택")
        b_none = QPushButton("전체 해제")
        b_all.clicked.connect(lambda: self._set_all(Qt.Checked))
        b_none.clicked.connect(lambda: self._set_all(Qt.Unchecked))
        row.addWidget(b_all)
        row.addWidget(b_none)
        lay.addLayout(row)

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Ok).setText("적용")
        bb.button(QDialogButtonBox.Cancel).setText("취소")
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def _set_all(self, state):
        for i in range(self.list.count()):
            self.list.item(i).setCheckState(state)

    def checked_ids(self):
        out = []
        for i in range(self.list.count()):
            it = self.list.item(i)
            if it.checkState() == Qt.Checked:
                try:
                    out.append(int(it.text()))
                except ValueError:
                    out.append(it.text())
        return out


