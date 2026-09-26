import sys
import numpy as np

# 1. 로컬 MoorPy 패키지 경로 등록
src_path = r"C:\TEST\OFA\src"
if src_path not in sys.path:
    sys.path.append(src_path)

import moorpy as mp

moordyn_file_path = r"C:\TEST\oFAST\_3MW\3_sd_260904_Floater\Floater.moo"

# 2. 빈 MoorPy 시스템 생성 및 물속 깊이 설정
ms = mp.System()
ms.depth = 64.5  # 앵커가 -64.5m 에 위치

body_id = 1

# Body 생성 — HydroDyn PtfmVol0(3804.19 m³) 기반 부피와 질량 설정
# v=3804.19 (부피), m=3804.19*1025 (중립 유체량), AWP=500 (수면적), rCG/rM로 안정성 확보
ms.addBody(0, np.zeros(6),
           m=3804.19 * ms.rho,   # 질량 ≈ 3,899,295 kg
           v=3804.19,            # 부피 (m³)
           AWP=500,              # 수면적 (m²)
           rCG=[0, 0, -10],      # 중심 of gravity (몸통 중심 아래 10m)
           rM=[0, 0, 10])        # metacenter (몸통 중심 위 10m)

# 4. 라인 타입 이름을 수동 추적하기 위한 딕셔너리
line_types = {}

# 5. 파일 한 줄씩 직접 읽어서 MoorPy 객체로 조립하기
with open(moordyn_file_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

current_section = None
for line in lines:
    line_strip = line.strip()
    if not line_strip or line_strip.startswith("(-)") or line_strip.startswith("Name") or line_strip.startswith("ID"):
        continue
    if "LINE TYPES" in line:
        current_section = "TYPES"
        continue
    elif "POINTS" in line:
        current_section = "POINTS"
        continue
    elif "LINES" in line:
        current_section = "LINES"
        continue
    elif "SOLVER OPTIONS" in line or "OUTPUTS" in line:
        current_section = None
        break

    parts = line_strip.split()
    if not parts:
        continue

    # A. 라인 타입 등록
    if current_section == "TYPES":
        name = parts[0]
        d    = float(parts[1])   # 지름 (m)
        mass = float(parts[2])   # 선형 질량 (kg/m)
        ea   = float(parts[3])   # EA (N)

        ms.setLineType(dnommm=d*1000, d_vol=d, mass=mass, EA=ea, name=name)
        ms.lineTypes[name]['material'] = 'chain'  # plot()의 material 체크 회피
        line_types[name] = name

    # B. 포인트 등록 및 바디 연결
    elif current_section == "POINTS":
        pid = int(parts[0])
        attach = parts[1]
        x, y, z = float(parts[2]), float(parts[3]), float(parts[4])

        if attach.lower() == "vessel":
            ms.addPoint(1, [x, y, z], body=body_id)
        elif attach.lower() == "fixed":
            ms.addPoint(1, [x, y, z])

    # C. 라인 연결
    elif current_section == "LINES":
        lid = int(parts[0])
        ltype = parts[1]
        ptA = int(parts[2])
        ptB = int(parts[3])
        L_unstr = float(parts[4])
        nSegs = int(parts[5]) if len(parts) > 5 else 20

        ms.addLine(L_unstr, ltype, nSegs=nSegs, pointA=ptA, pointB=ptB)

# 5. 정적 평형 상태 계산 및 강성행렬 추출
ms.initialize()
ms.solveEquilibrium()  # findEquilibrium → solveEquilibrium

K_matrix = ms.getSystemStiffness()
print("\n[6x6 Mooring Stiffness Matrix]")
for row in K_matrix:
    print(" ".join(f"{val:14.2f}" for val in row))

K_matrix = ms.getSystemStiffness(lines_only=True)
print("\n[6x6 Mooring Stiffness Matrix]")
for row in K_matrix:
    print(" ".join(f"{val:14.2f}" for val in row))

# 6. 시각화
import matplotlib.pyplot as plt

fig, ax = ms.plot()
plt.show()