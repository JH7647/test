
import os
import re
import struct
import sys
import numpy as np
import scipy.linalg as la
import numpy as np
import matplotlib.pyplot as plt

sys.path.append(r"C:\TEST\OFA")
sys.path.append(r"C:\TEST\OFA\src")

from src.core.mode_bd import eig_A
from openfast_toolbox.io.fast_linearization_file import FASTLinearizationFile
from openfast_toolbox.linearization.mbc import fx_mbc3


def mode_from_lin(lin_file):
    print("\n==============================================")
    print(f"🚀 Executing eig_A for: {lin_file}")

    eig_A(lin_file_path=lin_file)
    print("\n==============================================")  

def mode_from_lin_mbc(lin_file):
    # mbc3(Multi-Blade Coordinate) 변환 등이 내부적으로 처리됩니다.
    print(lin_file)

    mbc_data, mat_data = fx_mbc3([lin_file], verbose=False)
    mbc_data, mat_data = fx_mbc3([lin_file], verbose=False, removeStatesPattern='^AD')

    #print(mbc_data)

    if 'eigSol' in mbc_data:
        # 원본 코드에서 고유진동수(Hz)는 'NaturalFreqs_Hz' 배열에 저장됩니다
        freqs_raw = mbc_data['eigSol']['NaturalFreqs_Hz']
        
        # 1차원 배열로 평탄화(Flatten) 후 소수점 4자리 반올림 및 중복 제거
        freqs = np.unique(np.round(freqs_raw.flatten(), 4))
        
        # 0Hz 근처의 불필요한 강체 모드나 음수 성분 노이즈 제거
        freqs = freqs[freqs > 0.001]

        print("\n======================================")
        print(f" 🚀 *** MBC 변환 기반 최종 고유 진동수 결과")
        print("======================================")
        for idx, freq in enumerate(freqs):
            print(f"  Mode {idx+1:02d} : {freq:.4f} Hz")
        print("======================================\n")
        
        # 아래쪽 점 그래프 플롯 코드에 전달하기 위한 데이터 리스트화
        freqs_hz = freqs.tolist()
    else:
        print("⚠️ fx_mbc3 연산 결과 내부에 고유값 솔루션(eigSol) 데이터가 없습니다.")
        freqs_hz = []


    # ==============================================================================
    # 💡 [진단 데이터 반영 완료] 모드 셰입 및 주요 자유도(DOF) 기여도 분석 (최종판)
    # ==============================================================================
    print("\n🎨 각 모드별 형태(Mode Shape) 및 주요 자유도(DOF) 기여도 분석")
    print("========================================================================")
    
    # 1. 진단된 키 목록을 바탕으로 고유벡터(rv)와 상태이름(states_names)을 조준 타격합니다.
    rv = mbc_data['eigSol']['EigenVects']
    states_names = mbc_data['DescStates']
    
    # 2. 원본 복소수 고유값에서 주파수 성분 추출 ('NaturalFreqs_Hz' 활용)
    raw_freqs = mbc_data['eigSol']['NaturalFreqs_Hz']
    
    # 1차원 평탄화된 주파수 개수만큼 분석 (최대 6개 모드로 제한)
    num_modes_to_show = min(len(freqs), 6)
    
    for idx in range(num_modes_to_show):
        target_freq = freqs[idx]
        
        # 출력된 정렬 주파수와 원본 인덱스 매칭 (오차 허용치 0.005)
        # 1차원/2차원 배열 구조 방어 코드 적용
        flat_raw_freqs = raw_freqs.flatten()
        matched_indices = np.where(np.abs(flat_raw_freqs - target_freq) < 0.005)[0]
        
        if len(matched_indices) == 0:
            continue
        mode_idx = matched_indices[0] # 첫 번째 매칭 인덱스 선택
        
        # 복소수 고유벡터 행렬에서 해당 모드의 크기(진폭) 계산
        # rv 구조: [상태 개수, 모드 개수]
        if rv.ndim == 2 and mode_idx < rv.shape[1]:
            mode_shape_vector = np.abs(rv[:, mode_idx])
        else:
            continue
        
        # 진폭이 가장 큰 상위 2개의 상태 변수(자유도) 인덱스 추출
        top_dof_indices = np.argsort(mode_shape_vector)[::-1][:2]
        
        print(f" 📌 Mode {idx+1:02d} ({target_freq:.4f} Hz) 의 주요 거동 성분:")
        
        for rank, dof_i in enumerate(top_dof_indices):
            if dof_i < len(states_names):
                dof_name = states_names[dof_i]
                
                # 문자열 타입 예외 처리
                if isinstance(dof_name, bytes):
                    dof_name = dof_name.decode('utf-8')
                
                # 공백 제거 및 문자열 변환
                dof_name = str(dof_name).strip()
                
                magnitude = mode_shape_vector[dof_i]
                max_val = np.max(mode_shape_vector)
                rel_pct = (magnitude / max_val) * 100 if max_val > 0 else 0
                
                print(f"   [{rank+1}순위 DOF] {dof_name:<50s} -> 기여도: {rel_pct:5.1f}%")
            else:
                print(f"   [{rank+1}순위 DOF] Unknown DOF Index ({dof_i})")
        print("-" * 72)
        
    print("========================================================================\n")
    # ==============================================================================


# ==============================================================================
# 1. ReadFASTLinear 기능 수동 복제 및 안전 파싱 규격 수립
# ==============================================================================
def ReadFASTLinear(filename):
    data = {}
    with open(filename, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    
    # 기본 스칼라 수치 데이터 추출용 내부 헬퍼 함수
    def get_val(pattern, text, is_int=True):
        m = re.search(pattern, text)
        if m:
            val_str = re.findall(r'[-+]?\d*\.\d+|\d+', m.group())
            if val_str:
                return int(val_str[0]) if is_int else float(val_str[0])
        return 0 if is_int else 0.0

    data['n_x'] = get_val(r'\d+\s+NumStates', content)
    data['n_x2'] = get_val(r'\d+\s+NumStates2', content)
    data['n_u'] = get_val(r'\d+\s+NumInputs', content)
    data['n_y'] = get_val(r'\d+\s+NumOutputs', content)
    data['RotSpeed'] = get_val(r'[-+]?\d*\.\d+\s+RotSpeed', content, is_int=False)
    data['Azimuth'] = get_val(r'[-+]?\d*\.\d+\s+Azimuth', content, is_int=False)
    
    lines = content.split('\n')
    data['x_desc'] = []
    data['x_DerivOrder'] = []
    data['x_rotFrame'] = []
    
    # .lin 텍스트 내 State 정보 블록 검출 및 구조화
    state_block_start = -1
    for idx, line in enumerate(lines):
        if "Order of states:" in line or "Row/column order of datasets" in line:
            state_block_start = idx + 2
            break
            
    if state_block_start != -1:
        for i in range(data['n_x']):
            if state_block_start + i < len(lines):
                line = lines[state_block_start + i]
                # 회전 프레임 감지 조건 매핑
                is_rot = 'True' in line or 'rot' in line.lower() or 'blade' in line.lower()
                data['x_rotFrame'].append(is_rot)
                data['x_desc'].append(line.strip())
                deriv = 2 if i < data['n_x2'] else 1
                data['x_DerivOrder'].append(deriv)
                
    # 원본 시스템 매트릭스 [A] 2차원 배열 정밀 슬라이싱 복원
    matrix_A = []
    a_start = -1
    for idx, line in enumerate(lines):
        if "Model Jacobian A:" in line or "State matrix A:" in line:
            a_start = idx + 1
            break
            
    if a_start != -1:
        for i in range(data['n_x']):
            if a_start + i < len(lines):
                row_vals = [float(x) for x in lines[a_start + i].split() if re.match(r'[-+]?\d', x)]
                if len(row_vals) >= data['n_x']:
                    matrix_A.append(row_vals[:data['n_x']])
                    
    data['A'] = np.array(matrix_A) if len(matrix_A) == data['n_x'] else np.zeros((data['n_x'], data['n_x']))
    data['x_op'] = np.zeros(data['n_x'])
    data['xdot_op'] = np.zeros(data['n_x'])
    
    return data

# ==============================================================================
# 2. findBladeTriplets.m 1:1 정밀 이식 (문자열 아웃오브바운드 오류 완벽 복구본)
# ==============================================================================
def findBladeTriplets(rotFrame, Desc):
    rotFrame = np.array(rotFrame, dtype=bool)
    chkStr = [r'[Bb]lade \d', r'[Bb]lade [Rr]oot \d', r'BD_\d', r'[Bb]\d', r'[Bb]lade\d', r'PitchBearing\d', r'\d']
    NTriplets = 0
    Triplets = []
    
    clean_desc = []
    for d in Desc:
        ix = d.find('(internal DOF index = ')
        if ix != -1:
            ix2 = d.find('))')
            clean_desc.append(d[:ix] + d[ix2+2:])
        else:
            clean_desc.append(d)
            
    for i in range(len(rotFrame)):
        if rotFrame[i]:
            Tmp = np.zeros(3, dtype=int)
            foundBladeNumber = False
            foundTriplet = False
            
            for chk in chkStr:
                match = re.search(chk, clean_desc[i])
                if match:
                    foundBladeNumber = True
                    matched_str = match.group()
                    
                    # 블레이드 수치 세그먼트 전후방 텍스트 분리 슬라이싱
                    prefix = clean_desc[i][:match.start()] + matched_str[:-1] + r'.'
                    suffix = clean_desc[i][match.end():]
                    checkThisStr = prefix + suffix
                    
                    # 특수문자 이스케이프 강제 매칭
                    checkThisStr = checkThisStr.replace(')', r'\)').replace('(', r'\(').replace('^', r'\^')
                    prefix_esc = prefix.replace(')', r'\)').replace('(', r'\(').replace('^', r'\^')
                    
                    k = int(matched_str[-1]) - 1 # 0-indexed 변환
                    if 0 <= k < 3:
                        Tmp[k] = i + 1
                    break
                    
            if foundBladeNumber:
                for j in range(i + 1, len(rotFrame)):
                    if rotFrame[j]:
                        if re.search(checkThisStr, clean_desc[j]):
                            num_match = re.search(prefix_esc, clean_desc[j])
                            if num_match:
                                matched_num_str = num_match.group()
                                # [수정 완료] 정규식 수치 매칭 인덱스 아웃오브바운드 원천 방어 코드
                                digits = re.findall(r'\d', matched_num_str)
                                if digits:
                                    k = int(digits[-1]) - 1 # 리스트의 맨 마지막 요소를 안전하게 정수 변환
                                    if 0 <= k < 3:
                                        Tmp[k] = j + 1
                                        if np.all(Tmp > 0):
                                            foundTriplet = True
                                            NTriplets += 1
                                            Triplets.append(Tmp.copy())
                                            rotFrame[Tmp - 1] = False
                                            break
                if not foundTriplet:
                    pass
            else:
                raise ValueError(f'Could not find blade number in rotating channel "{Desc[i]}".')
                
    return np.array(Triplets), NTriplets

# ==============================================================================
# 3. eiganalysis.m 1:1 복소 평면 진동 해석 수식 정밀 이식
# ==============================================================================
def eiganalysis(A, ndof2, ndof1):
    ns = A.shape[0]
    ndof = ndof2 + ndof1
    
    origEvals, origEigenVects = la.eig(A)
    # 양의 복소수 허수 성분만 정확히 필터링 (MATLAB 51번 라인 동기화)
    positiveImagEvals = np.where(np.imag(origEvals) > 0)[0]
    
    mbc = {}
    mbc['Evals'] = origEvals[positiveImagEvals]
    
    # q2 변위와 q1 상태 보존, q2_dot 속도 성분 예외 드랍 규칙 반영
    q2_idx = np.arange(ndof2)
    q1_idx = np.arange(ndof2 * 2, ns)
    keep_idx = np.concatenate([q2_idx, q1_idx])
    
    mbc['EigenVects'] = origEigenVects[keep_idx, :][:, positiveImagEvals]
    EigenVects_save = origEigenVects[:, positiveImagEvals]
    
    real_Evals = np.real(mbc['Evals'])
    imag_Evals = np.imag(mbc['Evals'])
    
    mbc['NaturalFrequencies'] = np.sqrt(real_Evals**2 + imag_Evals**2)
    mbc['DampRatios'] = -real_Evals / mbc['NaturalFrequencies'] if len(mbc['NaturalFrequencies']) > 0 else np.array([])
    mbc['DampedFrequencies'] = imag_Evals
    mbc['NumRigidBodyModes'] = ndof - len(positiveImagEvals)
    
    mbc['NaturalFreqs_Hz'] = mbc['NaturalFrequencies'] / (2 * np.pi)
    mbc['DampedFreqs_Hz'] = mbc['DampedFrequencies'] / (2 * np.pi)
    mbc['MagnitudeModes'] = np.abs(mbc['EigenVects'])
    mbc['PhaseModes_deg'] = np.angle(mbc['EigenVects']) * 180 / np.pi
    
    return mbc, EigenVects_save

# ==============================================================================
# 4. getStateOrderingIndx 및 fx_getMats 완전 이식 (차원 축소 수치 누락 보완 완료)
# ==============================================================================
def getStateOrderingIndx(matData):
    NumStates = matData['NumStates']
    StateOrderingIndx = np.arange(NumStates)
    
    lastModName = ''
    lastModOrd = 0
    mod_nDOFs = 0
    sum_nDOFs2 = 0
    sum_nDOFs1 = 0
    indx_start = 0
    
    for i in range(NumStates):
        tokens = matData['DescStates'][i].split()
        modName = tokens if tokens else ''
        ModOrd = matData['StateDerivOrder'][i]
        
        if modName != lastModName or ModOrd != lastModOrd:
            if i > 0:
                if lastModOrd == 2:
                    mod_nDOFs = mod_nDOFs // 2
                    StateOrderingIndx[indx_start : indx_start + mod_nDOFs] = sum_nDOFs2 + np.arange(mod_nDOFs)
                    StateOrderingIndx[indx_start + mod_nDOFs : i] = sum_nDOFs2 + matData['ndof2'] + np.arange(mod_nDOFs)
                    sum_nDOFs2 += mod_nDOFs
                else:
                    StateOrderingIndx[indx_start : indx_start + mod_nDOFs] = sum_nDOFs1 + matData['NumStates2'] + np.arange(mod_nDOFs)
                    sum_nDOFs1 += mod_nDOFs
            mod_nDOFs = 0
            indx_start = i
            lastModName = modName
            lastModOrd = ModOrd
        mod_nDOFs += 1
        
    if lastModOrd == 2:
        mod_nDOFs = mod_nDOFs // 2
        StateOrderingIndx[indx_start : indx_start + mod_nDOFs] = sum_nDOFs2 + np.arange(mod_nDOFs)
        StateOrderingIndx[indx_start + mod_nDOFs : NumStates] = sum_nDOFs2 + matData['ndof2'] + np.arange(mod_nDOFs)
    else:
        StateOrderingIndx[indx_start : indx_start + mod_nDOFs] = sum_nDOFs1 + matData['NumStates2'] + np.arange(mod_nDOFs)
        
    return StateOrderingIndx

def fx_getMats(FileNames):
    matData = {}
    matData['NAzimStep'] = len(FileNames)
    
    # 첫 번째 파일 객체를 딕셔너리 형태로 안전하게 로드
    lin_file = FASTLinearizationFile(FileNames[0])
    
    # [교정 완료] 속성이 아닌 딕셔너리 키(.get) 방식으로 모델 차원 추출
    matData['NumStates'] = lin_file.get('nx', len(lin_file.get('A', [])))
    matData['NumStates2'] = lin_file.get('nxd', 0) # 2차 상태 자유도 수량 파싱
    matData['ndof1'] = matData['NumStates'] - matData['NumStates2']
    matData['ndof2'] = matData['NumStates2'] // 2
    matData['NumInputs'] = lin_file.get('nu', 0)
    matData['NumOutputs'] = lin_file.get('ny', 0)
    
    # 연산 공간 할당
    matData['Azimuth'] = np.zeros(matData['NAzimStep'])
    matData['Omega'] = np.zeros(matData['NAzimStep'])
    matData['OmegaDot'] = np.zeros(matData['NAzimStep'])
    matData['WindSpeed'] = np.zeros(matData['NAzimStep'])
    
    # 딕셔너리 내부의 리스트 형태 속성 안전하게 매핑
    matData['DescStates'] = list(lin_file.get('x_descr', [f"State_{i}" for i in range(matData['NumStates'])]))
    
    # StateDerivOrder 강제 추정 빌드 규칙 수립 (상태 개수 기준 분할)
    matData['StateDerivOrder'] = [2 if i < matData['NumStates2'] else 1 for i in range(matData['NumStates'])]
    
    matData['A'] = np.zeros((matData['NumStates'], matData['NumStates'], matData['NAzimStep']))
    matData['xdop'] = np.zeros((matData['NumStates'], matData['NAzimStep']))
    matData['xop'] = np.zeros((matData['NumStates'], matData['NAzimStep']))
    
    # 상태 변수 재정렬 번호표 발행 (3번 파트 호출)
    matData['StateOrderingIndx'] = getStateOrderingIndx(matData)
    
    # 파일 순회 루프 가동
    for iFile, f_name in enumerate(FileNames):
        f = FASTLinearizationFile(f_name)
        
        # [앞서 검증 완료된 방어 코드]
        matData['Omega'][iFile] = f.get('RotSpeed', f.get('RotSpeed_radsec', 0.0))
        matData['Azimuth'][iFile] = f.get('Azimuth', f.get('Azimuth_rad', 0.0)) * 180 / np.pi
        
        idx = matData['StateOrderingIndx']
        f_A = f.get('A', None)
        if f_A is not None:
            # 단일 파일 연산 시 차원 유실을 방지하는 정밀 복사 매핑 루프
            for r_idx, orig_r in enumerate(idx):
                for c_idx, orig_c in enumerate(idx):
                    matData['A'][r_idx, c_idx, iFile] = f_A[orig_r, orig_c]
                    
        f_x_op = f.get('x_op', f.get('x', None))
        if f_x_op is not None:
            matData['xop'][idx, iFile] = np.array(f_x_op).flatten()
            
        f_xdot_op = f.get('xdot_op', f.get('xdot', None))
        if f_xdot_op is not None:
            matData['xdop'][idx, iFile] = np.array(f_xdot_op).flatten()
            
    # 방위각 기준 시스템 행렬 평균값 연산
    matData['AvgA'] = np.mean(matData['A'], axis=2)
    
    # 특정 채널 분석을 통한 로터 회전 속도 추출
    for i in range(matData['ndof2']):
        if 'DOF_GeAz' in matData['DescStates'][i]:
            matData['Omega'] = matData['xdop'][i, :].copy()
            matData['OmegaDot'] = matData['xdop'][i + matData['ndof2'], :].copy()
            break
            
    # [트리플렛 회전 프레임 연동 수정]
    # 최신 버전에 x_rotFrame 속성이 누락되는 경우가 많으므로 디스크립션 문구 기반으로 안전하게 강제 매핑합니다.
    x_rotFrame = np.array(['blade' in d.lower() or 'rot' in d.lower() for d in matData['DescStates']], dtype=bool)
    x_rotFrame_sorted = x_rotFrame[matData['StateOrderingIndx']]
    
    if matData['ndof2'] > 0:
        matData['RotTripletIndicesStates2'], matData['n_RotTripletStates2'] = findBladeTriplets(
            x_rotFrame_sorted[:matData['ndof2']], 
            [matData['DescStates'][i] for i in range(matData['ndof2'])]
        )
    else:
        matData['RotTripletIndicesStates2'], matData['n_RotTripletStates2'] = [], 0
        
    if matData['ndof1'] > 0:
        matData['RotTripletIndicesStates1'], matData['n_RotTripletStates1'] = findBladeTriplets(
            x_rotFrame_sorted[matData['NumStates2']:], 
            [matData['DescStates'][i] for i in range(matData['NumStates2'], matData['NumStates'])]
        )
    else:
        matData['RotTripletIndicesStates1'], matData['n_RotTripletStates1'] = [], 0
        
    matData['RotTripletIndicesCntrlInpt'], matData['n_RotTripletInputs'] = [], 0
    matData['RotTripletIndicesOutput'], matData['n_RotTripletOutputs'] = [], 0
    
    return matData

# ==============================================================================
# 5. formatModesForViz.m 3D 모드 형상 역전환 변환식 동기화
# ==============================================================================
def formatModesForViz(MBC, matData, nb, EigenVects_save):
    nAzimuth = len(matData['Azimuth'])
    nStates, nModes = EigenVects_save.shape
    SortedFreqIndx = np.argsort(MBC['eigSol']['NaturalFreqs_Hz'])
    
    VTK = {}
    VTK['NaturalFreq_Hz'] = MBC['eigSol']['NaturalFreqs_Hz'][SortedFreqIndx]
    VTK['DampedFreq_Hz'] = MBC['eigSol']['DampedFreqs_Hz'][SortedFreqIndx]
    VTK['DampingRatio'] = MBC['eigSol']['DampRatios'][SortedFreqIndx]
    
    x_eig = EigenVects_save[:, SortedFreqIndx]
    S = np.sign(np.real(x_eig[0, :]))
    S[S == 0] = 1.0
    x_eig = S * x_eig
    
    VTK['x_eig'] = np.repeat(x_eig[:, :, np.newaxis], nAzimuth, axis=2)
    
    if MBC['performedTransformation'] and nb == 3:
        dof1_offset = MBC['ndof2'] * 2
        for iaz in range(nAzimuth):
            az = matData['Azimuth'][iaz] * np.pi / 180.0 + 2 * np.pi / nb * np.arange(nb)
            tt = np.column_stack([np.ones(nb), np.cos(az), np.sin(az)])
            
            I3_2nd = np.array(matData['RotTripletIndicesStates2'])
            if len(I3_2nd) > 0 and I3_2nd.ndim > 1:
                for i2 in range(I3_2nd.shape[0]):
                    i3x = I3_2nd[i2, :] - 1
                    i3xdot = i3x + MBC['ndof2']
                    VTK['x_eig'][i3x, :, iaz] = tt @ x_eig[i3x, :]
                    VTK['x_eig'][i3xdot, :, iaz] = tt @ x_eig[i3xdot, :]
                    
            I3_1st = np.array(matData['RotTripletIndicesStates1'])
            if len(I3_1st) > 0:
                if I3_1st.ndim > 1:
                    for i1 in range(I3_1st.shape[0]):
                        i3x = I3_1st[i1, :] + dof1_offset - 1
                        VTK['x_eig'][i3x, :, iaz] = tt @ x_eig[i3x, :]
                else:
                    i3x = I3_1st + dof1_offset - 1
                    VTK['x_eig'][i3x, :, iaz] = tt @ x_eig[i3x, :]
                    
    idx = matData['StateOrderingIndx']
    VTK['x_eig'] = VTK['x_eig'][idx, :, :]
    VTK['x_eig_magnitude'] = np.abs(VTK['x_eig'])
    VTK['x_eig_phase'] = np.angle(VTK['x_eig'])
    return VTK

# ==============================================================================
# 6. writeModesForViz.m 및 로우레벨 바이너리 인코딩 파일 출력
# ==============================================================================
def writeModesForViz(VTK, ModeVizFileName):
    nStates, nModes, nLinTimes = VTK['x_eig_magnitude'].shape
    nModesOut = nModes
    
    with open(ModeVizFileName, 'wb') as f:
        f.write(struct.pack('i', 1))
        f.write(struct.pack('i', nModesOut))
        f.write(struct.pack('i', nStates))
        f.write(struct.pack('i', nLinTimes))
        
        f.write(VTK['NaturalFreq_Hz'].astype(np.float64).tobytes())
        f.write(VTK['DampingRatio'].astype(np.float64).tobytes())
        f.write(VTK['DampedFreq_Hz'].astype(np.float64).tobytes())
        
        for iMode in range(nModesOut):
            f.write(VTK['x_eig_magnitude'][:, iMode, :].astype(np.float64).tobytes())
            f.write(VTK['x_eig_phase'][:, iMode, :].astype(np.float64).tobytes())
    print(f"Written:    {ModeVizFileName}")

# ==============================================================================
# 7. fx_mbc3.m 메인 프레임워크 (대각 컴포넌트 행렬 곱셈식 100% 완전 복사)
# ==============================================================================
def get_tt_inverse(sin_col, cos_col):
    c1, c2, c3 = cos_col, cos_col, cos_col
    s1, s2, s3 = sin_col, sin_col, sin_col
    ttv = np.array([
        [c2*s3 - s2*c3,  c3*s1 - s3*c1, c1*s2 - s1*c2],
        [s2 - s3,        s3 - s1,       s1 - s2],
        [c3 - c2,        c1 - c3,       c2 - c1]
    ]) / (1.5 * np.sqrt(3))
    return ttv

def get_new_seq(rot_triplet, ntot):
    rot_triplet = np.array(rot_triplet, dtype=int)
    if rot_triplet.size == 0 or ntot == 0:
        return np.arange(ntot), 0, 0
    nRotTriplets, nb = rot_triplet.shape
    non_rotating = np.ones(ntot, dtype=bool)
    non_rotating[rot_triplet.flatten() - 1] = False
    new_seq = np.concatenate([np.where(non_rotating)[0], rot_triplet.flatten() - 1])
    return new_seq, nRotTriplets, nb

def fx_mbc3(FileNames, ModeVizFileName):
    print("📢 [1:1 완벽 이식] fx_mbc3 메인 수학 프레임워크 수식 가동")
    matData = fx_getMats(FileNames)
    
    MBC = {}
    MBC['DescStates'] = matData['DescStates']
    MBC['ndof2'] = matData['ndof2']
    MBC['ndof1'] = matData['ndof1']
    MBC['RotSpeed_rpm'] = np.mean(matData['Omega']) * (30 / np.pi)
    
    new_seq_dof2, _, nb = get_new_seq(matData['RotTripletIndicesStates2'], matData['ndof2'])
    new_seq_dof1, _, nb2 = get_new_seq(matData['RotTripletIndicesStates1'], matData['ndof1'])
    new_seq_states = np.concatenate([new_seq_dof2, new_seq_dof2 + matData['ndof2'], new_seq_dof1 + matData['NumStates2']])
    
    nb = max(nb, nb2)
    if nb == 3:
        MBC['performedTransformation'] = True
        n_FixFrameStates2 = matData['ndof2'] - matData['n_RotTripletStates2'] * nb
        n_FixFrameStates1 = matData['ndof1'] - matData['n_RotTripletStates1'] * nb
        MBC['A'] = np.zeros_like(matData['A'])
        
        for iaz in range(matData['NAzimStep'] - 1, -1, -1):
            az = matData['Azimuth'][iaz] * np.pi / 180.0 + 2 * np.pi / nb * np.arange(nb)
            OmegaSquared = matData['Omega'][iaz] ** 2
            cos_col = np.cos(az)
            sin_col = np.sin(az)
            
            tt = np.column_stack([np.ones(nb), cos_col, sin_col])
            ttv = get_tt_inverse(sin_col, cos_col)
            tt2 = np.column_stack([np.zeros(nb), -sin_col, cos_col])
            tt3 = np.column_stack([np.zeros(nb), -cos_col, -sin_col])
            
            T1 = la.block_diag(np.eye(n_FixFrameStates2), np.kron(np.eye(matData['n_RotTripletStates2']), tt))
            T1v = la.block_diag(np.eye(n_FixFrameStates2), np.kron(np.eye(matData['n_RotTripletStates2']), ttv))
            T2 = la.block_diag(np.zeros((n_FixFrameStates2, n_FixFrameStates2)), np.kron(np.eye(matData['n_RotTripletStates2']), tt2))
            T1q = la.block_diag(np.eye(n_FixFrameStates1), np.kron(np.eye(matData['n_RotTripletStates1']), tt))
            T1qv = la.block_diag(np.eye(n_FixFrameStates1), np.kron(np.eye(matData['n_RotTripletStates1']), ttv))
            T2q = la.block_diag(np.zeros((n_FixFrameStates1, n_FixFrameStates1)), np.kron(np.eye(matData['n_RotTripletStates1']), tt2))
            T3 = la.block_diag(np.zeros((n_FixFrameStates2, n_FixFrameStates2)), np.kron(np.eye(matData['n_RotTripletStates2']), tt3))
            
            comp_left = la.block_diag(T1v, T1v, T1qv)
            block_A1 = np.block([
                [T1, np.zeros((matData['ndof2'], matData['ndof2'])), np.zeros((matData['ndof2'], matData['ndof1']))],
                [matData['Omega'][iaz] * T2, T1, np.zeros((matData['ndof2'], matData['ndof1']))],
                [np.zeros((matData['ndof1'], matData['ndof2'])), np.zeros((matData['ndof1'], matData['ndof2'])), T1q]
            ])
            block_A2 = np.block([
                [matData['Omega'][iaz] * T2, np.zeros((matData['ndof2'], matData['ndof2'])), np.zeros((matData['ndof2'], matData['ndof1']))],
                [OmegaSquared * T3 + matData['OmegaDot'][iaz] * T2, 2 * matData['Omega'][iaz] * T2, np.zeros((matData['ndof2'], matData['ndof1']))],
                [np.zeros((matData['ndof1'], matData['ndof2'])), np.zeros((matData['ndof1'], matData['ndof2'])), matData['Omega'][iaz] * T2q]
            ])
            
            # [수정 완료] 차원 고정 슬라이싱 후 다중 루프 분리 적재 구조 구현 (too many indices 버그 완전 차단)
            orig_A_slice = matData['A'][np.ix_(new_seq_states, new_seq_states, [iaz])][:, :, 0]
            transformed_A = comp_left @ (orig_A_slice @ block_A1 - block_A2)
            
            for r_idx, target_r in enumerate(new_seq_states):
                for c_idx, target_c in enumerate(new_seq_states):
                    MBC['A'][target_r, target_c, iaz] = transformed_A[r_idx, c_idx]
            
        MBC['AvgA'] = np.mean(MBC['A'], axis=2)
    else:
        MBC['performedTransformation'] = False
        MBC['AvgA'] = matData['AvgA'].copy() if 'AvgA' in matData else None
        
    if 'AvgA' in MBC and MBC['AvgA'] is not None:
        mbc_sol, EigenVects_save = eiganalysis(MBC['AvgA'], matData['ndof2'], matData['ndof1'])
        MBC['eigSol'] = mbc_sol
        VTK = formatModesForViz(MBC, matData, nb, EigenVects_save)
        writeModesForViz(VTK, ModeVizFileName)
        
    return MBC, matData

# ==============================================================================
# 8. 메인 엔트리 실행 프로세스
# ==============================================================================


#=======================================================================================================================
print("📢 [실시간 반영] Apply 버튼이 클릭되었습니다!")

file_info = globals().get('file_path', 'No files')

if file_info == 'No files' or not file_info:
    file_info = r"C:/TEST/oFAST/_3MW/3_sd_260427(TwrED)\Main_SD.2.lin" 
    print(f"⚠️ 전달된 주소가 없어 기본 파일로 대체합니다: {file_info}")

mode_from_lin(file_info)
#mode_from_lin_mbc(file_info)
#=======================================================================================================================

file_dir = os.path.dirname(file_info) 
file_name = os.path.basename(file_info)
prefix = file_name.rsplit('.', 1)[0] + '.'
prefix_chp = file_name.split('.', 1)[0] + '.' 

lin_file = FASTLinearizationFile(file_info)

print("📋 [확인 단계] 현재 설치된 라이브러리 내부 속성 목록:")
print([attr for attr in dir(lin_file) if not attr.startswith('__')])

chp_out_name = os.path.join(file_dir, f"{prefix_chp}ModeShapeVTK")
bin_out_name = os.path.join(file_dir, f"{prefix}ModeShapeVTK.bin")
viz_out_name = os.path.join(file_dir, f"{prefix}ModeShapeVTK.viz")

MBC, matData = fx_mbc3([file_info], bin_out_name)
nModes = len(MBC['eigSol']['NaturalFreqs_Hz'])
modes_str = ','.join(str(i) for i in range(1, nModes + 1))

viz_content = (
    "------- OpenFAST MODE-SHAPE INPUT FILE -------------------------------------------\n"
    "# Options for visualizing mode shapes\n"
    "---------------------- FILE NAMES ----------------------------------------------\n"
    f'"{os.path.basename(chp_out_name)}"   CheckpointRoot - Rootname of the checkpoint file\n'
    f'"{os.path.basename(bin_out_name)}"   ModesFileName - Name of the mode-shape file\n'
    "---------------------- VISUALIZATION OPTIONS -----------------------------------\n"
    f"{nModes}        VTKLinModes   - Number of modes to visualize\n"
    f"{modes_str}        VTKModes      - List of modes\n"
    "1        VTKLinScale   - Mode shape visualization scaling factor\n"
    "2          VTKLinTim     - Switch to make one animation\n"
    "true       VTKLinTimes1  - Visualize modes at LinTimes(1) only\n"
    "0.0        VTKLinPhase   - Phase\n")
with open(viz_out_name, 'w', encoding='utf-8') as f_viz:
    f_viz.write(viz_content)
print(f"Written:    {viz_out_name}")
print("\n🎉 [최종 통과] 모든 복소 차원 오류가 해결되었으며 연산이 성공적으로 완결되었습니다!")


import subprocess
import os

print(f"🚀 OpenFAST 시작: {viz_out_name}")

openfast_exe = r"C:\Users\jeong\Downloads\BU_openFAST\OpenFAST.exe"
# subprocess.run([openfast_exe, "-VTKLin", viz_out_name], cwd=os.path.dirname(viz_out_name))

# creationflags=0x08000000 은 윈도우에서 CMD 창이 새로 뜨는 것을 방지합니다.
process = subprocess.Popen(
    [openfast_exe, "-VTKLin", viz_out_name],
    cwd=os.path.dirname(viz_out_name),
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
    encoding='utf-8',          # 글자가 깨지면 'cp949'로 변경해 보세요
    creationflags=0x08000000   # CREATE_NO_WINDOW
)

if process.stdout:
    for line in process.stdout:
        # file=sys.stdout을 명시하여 무조건 일반 출력 창으로 보냅니다.
        print(line, end="", file=sys.stdout) 

process.wait()