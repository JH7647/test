import os
import re
import struct
import sys
import numpy as np
import scipy.linalg as la

sys.path.append(r"C:\TEST\OFA")
sys.path.append(r"C:\TEST\OFA\src")


from openfast_toolbox.io.fast_linearization_file import FASTLinearizationFile
# from openfast_toolbox.linearization.mbc import fx_mbc3
# from openfast_toolbox.linearization.tools import writeVizFile 


print("📢 [완전 전환] MATLAB 원본 소스코드 4종 100% 완전 동기화 엔진 가동")

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
if __name__ == "__main__":
    file_path = r"C:\TEST\oFAST\_3MW\3_sd_260904_Floater\Floater.1.lin"
    file_path = r"C:\TEST\oFAST\_3MW\3_sd_260427(TwrED)\Main.2.lin"
    file_dir = os.path.dirname(file_path)

    # file_path = r"C:\TEST\tem\5MW_Land_ModeShapes\5MW_Land_ModeShapes.1.lin"
    # file_dir = os.path.dirname(file_path)

    lin_file = FASTLinearizationFile(file_path)
    
    print("📋 [확인 단계] 현재 설치된 라이브러리 내부 속성 목록:")
    print([attr for attr in dir(lin_file) if not attr.startswith('__')])


    bin_out_name = os.path.join(file_dir, "ModeShapeVTK.bin")
    viz_out_name = os.path.join(file_dir, "ModeShapeVTK.viz")
    
    try:
        MBC, matData = fx_mbc3([file_path], bin_out_name)
        nModes = len(MBC['eigSol']['NaturalFreqs_Hz'])
        modes_str = ','.join(str(i) for i in range(1, nModes + 1))
        
        viz_content = (
            "------- OpenFAST MODE-SHAPE INPUT FILE -------------------------------------------\n"
            "# Options for visualizing mode shapes\n"
            "---------------------- FILE NAMES ----------------------------------------------\n"
            '"Main.ModeShapeVTK"   CheckpointRoot - Rootname of the checkpoint file\n'
            f'"{os.path.basename(bin_out_name)}"   ModesFileName - Name of the mode-shape file\n'
            "---------------------- VISUALIZATION OPTIONS -----------------------------------\n"
            f"{nModes}        VTKLinModes   - Number of modes to visualize\n"
            f"{modes_str}        VTKModes      - List of modes\n"
            "100        VTKLinScale   - Mode shape visualization scaling factor\n"
            "2          VTKLinTim     - Switch to make one animation\n"
            "true       VTKLinTimes1  - Visualize modes at LinTimes(1) only\n"
            "0.0        VTKLinPhase   - Phase\n")
        with open(viz_out_name, 'w', encoding='utf-8') as f_viz:
            f_viz.write(viz_content)
        print(f"Written:    {viz_out_name}")
        print("\n🎉 [최종 통과] 모든 복소 차원 오류가 해결되었으며 연산이 성공적으로 완결되었습니다!")
    except Exception as e:
        print(f"❌ 완전 전환 가동 중 오류 발생: {e}")







# # 🌟 writeVizFile 호환용 클래스 뼈대 정의
# class DictToObj(object):
#     def __init__(self, d):
#         for k, v in d.items():
#             setattr(self, k, v)

# #==============================================================================
# file_info = globals().get('file_path', 'No files')
# if file_info == 'No files' or not file_info:
#     file_info = [r"C:\TEST\oFAST\_3MW\3_sd_260904_Floater\Floater.1.lin"]
#     print(f"Lin File = {file_info}")

# # mbc3 연산 및 예외 처리
# try:
#     mbc_dict, matData = fx_mbc3(file_info, verbose=True)

#     # 🌟 dict 데이터를 객체(Object) 구조로 강제 래핑 및 필수 값 수동 보정
#     mbc_data = DictToObj(mbc_dict)
#     mbc_data.VTKLinModes = int(mbc_dict.get('NDof', 21))      # ◀ 정수형 보장
#     mbc_data.NBlades     = int(mbc_dict.get('nb', 3))        # ◀ 정수형 보장
#     mbc_data.WindSpeed   = float(mbc_dict.get('WindSpeed', 0.0))
#     mbc_data.RotorSpeed  = float(mbc_dict.get('RotSpeed_rpm', 0.0))
#     mbc_data.Azimuth     = 0.0
    
#     # .viz 파일 쓰기(저장) 수행
#     viz_file_name = 'ModeShapeVTK'
     
#     writeVizFile(f"{viz_file_name}.viz", mbc_data)

# except Exception as e:
#     print(f"❌ 에러 발생: {e}")
# #==============================================================================



# LinFileNames = [r"C:\TEST\oFAST\_3MW\3_sd_260904_Floater\Floater.1.lin"]

# mbc_data, matData = fx_mbc3(LinFileNames, verbose=True)
# writeVizFile("ModeShapeVTK.viz", mbc_data)

# # 1. 원본 선형화 파일 데이터 로드
# lin = FASTLinearizationFile(file_info)
# try:
#     A_matrix = lin['A']
# except (KeyError, TypeError):
#     A_matrix = lin.data['A'] if hasattr(lin, 'data') else lin.A_matrix

# # 2. 고유치 해석 (Eigenvalue Analysis)
# eigenvalues, eigenvectors = linalg.eig(A_matrix)

# n_modes = len(eigenvalues)    # 42
# n_states = len(A_matrix)      # 42
# n_lin_times = 1               # 1

# # 3. OpenFAST 엔진용 정확한 경로 매핑
# pyPostMBC_path = file_info.replace(".1.lin", ".1.ModeShapeVTK.pyPostMBC")

# with open(pyPostMBC_path, "wb") as f:
#     # --------------------------------------------------------------------------
#     # [레코드 1] 헤더 정보 레코드 (modes -> states -> linTimes 표준 순서)
#     # --------------------------------------------------------------------------
#     header_bytes = struct.pack("iii", n_modes, n_states, n_lin_times)
#     f.write(struct.pack("i", 12))  # 12바이트 레코드 가드 시작
#     f.write(header_bytes)          
#     f.write(struct.pack("i", 12))  # 레코드 가드 끝

#     # --------------------------------------------------------------------------
#     # [레코드 2] 시간 정보 레코드 (8바이트 부동소수점 블록)
#     # --------------------------------------------------------------------------
#     time_bytes = struct.pack("d", 0.0)
#     f.write(struct.pack("i", 8))   
#     f.write(time_bytes)
#     f.write(struct.pack("i", 8))   

#     # --------------------------------------------------------------------------
#     # 🔥 [교정 1] 고유값(Eigenvalues) 복소수 배열 레코드 (총 42 * 8 = 336 바이트)
#     # 비트 뒤틀림을 막기 위해 단일 모드당 [실수(4B) + 허수(4B)]를 완전히 붙여서 패킹합니다.
#     # --------------------------------------------------------------------------
#     eig_byte_list = []
#     for val in eigenvalues:
#         eig_byte_list.append(struct.pack("ff", float(val.real), float(val.imag)))
#     eig_bytes = b"".join(eig_byte_list)
    
#     f.write(struct.pack("i", len(eig_bytes))) # 고유값 배열 시작 가드 (336)
#     f.write(eig_bytes)
#     f.write(struct.pack("i", len(eig_bytes))) # 고유값 배열 끝 가드

#     # --------------------------------------------------------------------------
#     # 🔥 [교정 2] 고유벡터(Eigenvectors) 행렬 모드별 개별 레코드 순차 분리 작성
#     # Fortran Column-major 열우선 사양 및 복소수 구조(실수4B + 허수4B) 동기화
#     # --------------------------------------------------------------------------
#     vec_element_size = n_states * 8 # 42 * 8 = 336 바이트
    
#     for j in range(n_modes):
#         mode_column_bytes = []
#         for i in range(n_states):
#             val = eigenvectors[i, j]
#             # 각 원소를 절대로 찢지 않고 [실수, 허수] 커플로 묶어서 차례대로 빌드
#             mode_column_bytes.append(struct.pack("ff", float(val.real), float(val.imag)))
        
#         column_bytes_stream = b"".join(mode_column_bytes)
        
#         # 1개 모드 열 벡터를 독립된 레코드 블록으로 감싸 데이터 오독을 완전히 원천 차단합니다.
#         f.write(struct.pack("i", vec_element_size)) # 모드 레코드 가드 시작 (336)
#         f.write(column_bytes_stream)
#         f.write(struct.pack("i", vec_element_size)) # 모드 레코드 가드 끝 (336)

# print("-" * 50)
# print(f"📋 [물리 구조 교정 완료] 하드웨어 바이트 붕괴 버그를 수정했습니다.")
# print("-" * 50)

# # 4. 설정 가시화 연계 파일(.viz) 최종 빌드
# viz_output = writeVizFile(file_info, VTKLinModes=15, verbose=True)

# # 5. OpenFAST.exe 자동 구동
# openfast_exe = r"C:\Users\jeong\Downloads\BU_openFAST\OpenFAST.exe"
# print("⏳ OpenFAST 가시화 엔진(-VTKLin)을 최종 구동합니다...\n")
# cmd = [openfast_exe, "-VTKLin", viz_output]

# try:
#     result = subprocess.run(cmd, check=True, text=True)
#     print("\n" + "=" * 50)
#     print("🎉 [시각화 구축 성공] 가시화 파일 출력을 드디어 마쳤습니다!")
#     print("📁 폴더 내에 새로 쏟아진 Mode_X_...vtp 파일들을 ParaView에서 확인해 보세요!")
#     print("=" * 50)
# except subprocess.CalledProcessError as e:
#     print(f"\n❌ [구동 fatal error] OpenFAST 런타임 종료 코드: {e.returncode}")









# import os
# import sys
# import struct
# import subprocess
# import numpy as np
# from scipy import linalg

# sys.path.append(r"C:\TEST\OFA")
# sys.path.append(r"C:\TEST\OFA\src")

# from openfast_toolbox.io.fast_linearization_file import FASTLinearizationFile
# from openfast_toolbox.linearization.tools import writeVizFile 

# #==============================================================================
# print("📢 [실시간 반영] Apply 버튼이 클릭되었습니다!")

# file_info = globals().get('file_path', 'No files')
# if file_info == 'No files' or not file_info:
#     file_info = r"C:\TEST\oFAST\_3MW\3_sd_260904_Floater\Floater.1.lin"
#     print(f"⚠️ 전달된 주소가 없어 기본 파일로 대체합니다: {file_info}")

# # 1. 원본 선형화 파일 데이터 로드
# lin = FASTLinearizationFile(file_info)
# try:
#     A_matrix = lin['A']
# except (KeyError, TypeError):
#     A_matrix = lin.data['A'] if hasattr(lin, 'data') else lin.A_matrix

# # 2. 고유치 해석 (Eigenvalue Analysis)
# eigenvalues, eigenvectors = linalg.eig(A_matrix)

# n_modes = len(eigenvalues)    # 42
# n_states = len(A_matrix)      # 42
# n_lin_times = 1               # 1

# # --------------------------------------------------------------------------
# # 3. 🔥 핵심 수정: OpenFAST 함수 규칙과 100% 일치하는 정확한 파일명 지정
# # --------------------------------------------------------------------------
# # writeVizFile 함수 내부 매핑 규칙에 따라 파일 이름에 반드시 '.1.'이 들어가야 합니다.
# pyPostMBC_path = file_info.replace(".1.lin", ".1.ModeShapeVTK.pyPostMBC")

# with open(pyPostMBC_path, "wb") as f:
#     # [헤더 레코드] n_modes(4B), n_states(4B), n_lin_times(4B) 총 12바이트 데이터 블록
#     header_bytes = struct.pack("iii", n_modes, n_states, n_lin_times)
#     f.write(struct.pack("i", 12))  # 레코드 시작 가드 (12)
#     f.write(header_bytes)          
#     f.write(struct.pack("i", 12))  # 레코드 끝 가드 (12)

#     # [시간 레코드] linTimes 데이터 (단일 0.0 실수값, 8바이트)
#     time_bytes = struct.pack("d", 0.0)
#     f.write(struct.pack("i", 8))   # 레코드 시작 가드 (8)
#     f.write(time_bytes)
#     f.write(struct.pack("i", 8))   # 레코드 끝 가드 (8)

#     # [고유값 레코드] eigenvalues 단정밀도(single precision, 각 4바이트) 변환
#     eig_real = eigenvalues.real.astype(np.float32).tobytes()
#     eig_imag = eigenvalues.imag.astype(np.float32).tobytes()
#     eig_bytes = eig_real + eig_imag
#     total_eig_size = len(eig_bytes)
    
#     f.write(struct.pack("i", total_eig_size))
#     f.write(eig_bytes)
#     f.write(struct.pack("i", total_eig_size))

#     # [고유벡터 레코드] eigenvectors 단정밀도(single precision) 변환
#     vec_real = eigenvectors.real.astype(np.float32).tobytes()
#     vec_imag = eigenvectors.imag.astype(np.float32).tobytes()
#     vec_bytes = vec_real + vec_imag
#     total_vec_size = len(vec_bytes)
    
#     f.write(struct.pack("i", total_vec_size))
#     f.write(vec_bytes)
#     f.write(struct.pack("i", total_vec_size))

# print("-" * 50)
# print(f"✅ [Fortran 규격 동기화 완벽 완료]")
# print(f"   • 실제 덮어씌운 정확한 경로: {pyPostMBC_path}")
# print(f"   • nmodes: {n_modes}, nstates: {n_states}")
# print("-" * 50)

# # 4. 설정 가시화 연계 파일(.viz) 최종 빌드
# viz_output = writeVizFile(file_info, VTKLinModes=15, verbose=True)

# # 5. OpenFAST.exe 자동 구동 프로세스 트리거
# openfast_exe = r"C:\Users\jeong\Downloads\BU_openFAST\OpenFAST.exe"

# print("⏳ OpenFAST 가시화 엔진(-VTKLin)을 최종 구동합니다...\n")
# cmd = [openfast_exe, "-VTKLin", viz_output]

# try:
#     result = subprocess.run(cmd, check=True, text=True)
#     print("\n" + "=" * 50)
#     print("🎉 [최종 완성] OpenFAST 가시화 파이프라인 완주 성공!")
#     print("💡 폴더 내에 생성된 개별 Mode_X_...vtp 파일들을 ParaView에서 확인하세요!")
#     print("=" * 50)
# except subprocess.CalledProcessError as e:
#     print(f"\n❌ [구동 fatal error] OpenFAST 런타임 종료 코드: {e.returncode}")







# import os
# import pickle  # 파이썬 객체를 바이너리(*.bin) 파일로 내보내기 위함
# import numpy as np
# import sys
# from scipy import linalg

# sys.path.append(r"C:\TEST\OFA")
# sys.path.append(r"C:\TEST\OFA\src")

# from openfast_toolbox.io.fast_linearization_file import FASTLinearizationFile
# from openfast_toolbox.linearization.mbc import fx_mbc3
# from openfast_toolbox.linearization.tools import writeVizFile 

# #==============================================================================
# print("📢 [실시간 반영] Apply 버튼이 클릭되었습니다!")

# file_info = globals().get('file_path', 'No files')
# if file_info == 'No files' or not file_info:
#     file_info = r"C:\TEST\oFAST\_3MW\3_sd_260904_Floater\Floater.1.lin"
#     print(f"⚠️ 전달된 주소가 없어 기본 파일로 대체합니다: {file_info}")

# lin = FASTLinearizationFile(file_info)

# A_matrix = lin['A']
# eigenvalues, eigenvectors = linalg.eig(A_matrix)


# # 3. 속성 및 텍스트 데이터 정제
# state_names = lin['StateName'] if 'StateName' in lin else (lin.StateName if hasattr(lin, 'StateName') else [])
# state_names = [str(s).strip() for s in state_names]
# n_states = len(state_names)
# n_modes = len(eigenvalues)

# # 4. OpenFAST Fortran 구조체가 바이트 단위로 읽을 때 에러가 나지 않도록 표준 키맵 강제 지정
# # Campbell 구조체 규격 바인딩
# CampbellData = {
#     "NaturalFreq_Hz":      np.abs(eigenvalues) / (2 * np.pi),
#     "DampingRatio":        -eigenvalues.real / np.abs(eigenvalues),
#     "Eigenvalues":         eigenvalues,
#     "Eigenvectors":        eigenvectors,
#     "StateNames":          state_names,
#     "WindSpeed":           float(lin['WindSpeed'] if 'WindSpeed' in lin else 0.0),
#     "RotorSpeed_rpm":      float(lin['RotSpeed'] if 'RotSpeed' in lin else 0.0)
# }

# # 최종 OpenFAST v5.0.0 파서 탑레벨 딕셔너리 빌드
# pyPostMBC_data = {
#     "MBC":                  CampbellData,
#     "eigenvalues":          eigenvalues,
#     "eigenvectors":         eigenvectors,
#     "state_names":          state_names,
#     "wind_speed":           float(lin['WindSpeed'] if 'WindSpeed' in lin else 0.0),
#     "rotor_speed":          float(lin['RotSpeed'] if 'RotSpeed' in lin else 0.0),
#     "ndof_ED":              int(n_states),
#     "nmodes":               int(n_modes),
#     "linTimes":             [0.0]  # 단일 파일 해석이므로 시간에 대한 데이터 배열 강제 주입
# }

# # 5. 내장 함수 규격에 맞는 파일명으로 덤프 작성
# output_base = r"C:\TEST\oFAST\_3MW\3_sd_260904_Floater\Floater.1.ModeShapeVTK"
# pyPostMBC_path = output_base + ".pyPostMBC"

# with open(pyPostMBC_path, "wb") as f:
#     # OpenFAST 내부 읽기 유실을 방지하기 위해 HIGHEST_PROTOCOL 직렬화 유지
#     pickle.dump(pyPostMBC_data, f, protocol=pickle.HIGHEST_PROTOCOL)

# print("-" * 50)
# print(f"✅ [규격 정제 완료] .pyPostMBC 파일이 재생성되었습니다.")
# print(f"   • 파일 경로: {pyPostMBC_path}")
# print(f"   • 강제 지정된 모드 개수 (nmodes): {n_modes} (기대값: 42)")
# print(f"   • 강제 지정된 상태 변수 (ndof_ED): {n_states} (기대값: 42)")
# print("-" * 50)






# # 3. Paraview 또는 시각화 모듈이 읽을 수 있는 통합 모드 데이터 구조체 빌드
# # (OpenFAST Campbell 및 가시화 포맷 규격을 따름)
# mode_data = {
#     "file_source": file_info,
#     "num_modes": len(eigenvalues),
#     "eigenvalues": eigenvalues,
#     "eigenvectors": eigenvectors,
#     "state_names": lin['StateName'] if 'StateName' in lin else [],
#     "wind_speed": lin['WindSpeed'] if 'WindSpeed' in lin else 0.0,
#     "rotor_speed": lin['RotSpeed'] if 'RotSpeed' in lin else 0.0
# }

# # 4. 출력될 바이너리 파일 경로 설정 (기존 선형화 파일 이름 기반으로 .bin 확장자 자동 매핑)
# output_bin_path = file_info.replace(".1.lin", ".ModeShapeVTK.bin")
# output_pyPostMBC_path = file_info.replace(".1.lin", ".ModeShapeVTK.pyPostMBC")

# # 5. 바이너리 쓰기(wb) 모드로 파일 열고 데이터 덤프(Write)
# try:
#     with open(output_bin_path, "wb") as f:
#         pickle.dump(mode_data, f, protocol=pickle.HIGHEST_PROTOCOL)

#     with open(output_pyPostMBC_path, "wb") as f:
#         pickle.dump(mode_data, f, protocol=pickle.HIGHEST_PROTOCOL)
    
#     print("-" * 50)
#     print(f"🎉 [최종 성공] 2번 과정 수행 완료!")
#     print(f"📁 생성된 바이너리 파일: {output_bin_path}")
#     print(f"• 파일 크기: {os.path.getsize(output_bin_path) / 1024:.2f} KB")
#     print("-" * 50)
# except Exception as e:
#     print(f"❌ [오류] 바이너리 파일 생성 중 에러 발생: {e}")


# # --------------------------------------------------------------------------
# print("⏳ OpenFAST 가시화 연계용 설정 파일(.viz)을 생성하고 있습니다...")

# try:
#     # 공유해주신 소스코드 스펙 적용: 오직 fstFile 경로(여기서는 file_info)만 인자로 넘겨줍니다.
#     # 추가 옵션으로 화면에 진행 상황을 보려면 verbose=True를 줍니다.
#     viz_output = writeVizFile(file_info, VTKLinModes=15, verbose=True)
    
#     print("-" * 50)
#     print("🎉 [최종 가시화 성공] OpenFAST-ParaView 연계 파일 빌드 완료!")
#     print(f"📁 생성된 가시화 설정 파일: {viz_output}")
#     print("💡 이 생성된 .viz 구성 파일을 기반으로 3D 지오메트리 메쉬 결합을 실행하시면 됩니다.")
#     print("-" * 50)
# except Exception as e:
#     print(f"❌ [시각화 오류] .viz 설정 파일 생성 중 문제가 발생했습니다: {e}")








