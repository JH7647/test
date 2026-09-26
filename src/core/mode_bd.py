#%% Linearization Analysis using openfast_toolbox
#   Date: 2026.02.13

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.special import roots_legendre
from openfast_toolbox.io.fast_linearization_file import FASTLinearizationFile
#from IPython.core.debugger import set_trace

#----------------------------------------------------------------------------------------
def plot_mode_shape(modes, nth_mode, total_node_number, zNode):
    # 인덱스 범위 확인 및 해당 모드 추출
    if nth_mode > len(modes): print(f"Error: {nth_mode}번 모드가 존재하지 않습니다. (최대 {len(modes)}개)"); return
    
    mode   = modes[nth_mode - 1]  # 사용자는 1번부터 입력, 인덱스는 0부터 시작
    desc   = mode['desc']
    vector = mode['eigen_vector']

    # 6개 자유도별 인덱스 생성 (x, y, z, rx, ry, rz)
    dof_indices = [[6 * i + dof for i in range(total_node_number)] for dof in range(6)]
    dof_labels = ['X', 'Y', 'Z', 'RX', 'RY', 'RZ']

    # 6개 성분(idx 0~5)을 반복하며 그래프 그리기 
    plt.figure(figsize=(12, 6))
    file = open('output_result.txt', 'a', encoding='utf-8')
    file.write(f"Mode {mode['no']} - Frequency: {mode['freq']:.4f} Hz, Damping: {mode['damp']:.4f}, Dominant State: {mode['desc']}\n")
    np.set_printoptions(linewidth=np.inf)

    dof_energies = []
    for idx in range(6):
        # 복소수 벡터에서 해당 성분의 절대값(진폭) 추출
        current_idx_list = dof_indices[idx]
        disp_mag  = np.abs(vector[current_idx_list])
        disp_plot = disp_mag * np.sign(np.real(vector[current_idx_list]))  

        # 그래프 그리기
        plt.plot(zNode, disp_plot, label=dof_labels[idx], marker='o', markersize=4)    
        file.write(f" {dof_labels[idx]} DOF \n")
        file.write(f" {disp_plot}\n")

        # 지배적 성분 판단 기준: 해당 성분의 진폭 평균(또는 합계)
        dof_energies.append(np.mean(disp_mag))

        # # 최대값으로 정규화 (값이 0일 경우 제외)
        # max_val = np.max(disp_mag)
        # if max_val > 1e-12:
        #     disp_norm = disp_mag / max_val
        # else:
        #     disp_norm = disp_mag
            
    plt.xlabel('Node Index (Root to Tip)')
    plt.ylabel('Amplitude')
    plt.title(f"Mode {mode['no']} Shape ({mode['freq']:.4f} Hz)\n{mode['desc']}")
    plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left') # 범례를 밖으로 빼서 가독성 확보
    plt.grid(True, alpha=0.3)
    plt.tight_layout()

    # 가장 에너지가 큰 인덱스 찾기
    dominant_idx   = np.argmax(dof_energies)
    dominant_label = dof_labels[dominant_idx]
    dominant_data  = np.abs(vector[dof_indices[dominant_idx]]) * np.sign(np.real(vector[dof_indices[dominant_idx]]))  
    print(f"\n")
    print(f"이 모드의 지배적 성분은 [{dominant_label}] 입니다. (평균 진폭: {dof_energies[dominant_idx]:.4e})")

    powers = [2, 3, 4, 5, 6]
    # 커브 피팅용 데이터 준비 (지배적 성분의 부호 포함 데이터)
    y_data = dominant_data / np.max(np.abs(dominant_data))
    x_data = np.array(zNode) / max(zNode)

    # Curve Fitting (x^2, x^3, x^4, x^5 항만 포함) 특정 차수만 강제하려면 np.linalg.lstsq를 사용하는 것이 정확합니다.
    coeffs = get_ModeFitPars(x_data, y_data, powers=[2, 3, 4, 5, 6])

    # 결과 출력
    print(f"ElastoDyn.dat Input : Mode [{mode['no']}] Fitted Normalized Coefficients :")
    for p, c in zip(powers, coeffs):
        print(f" {c:.4f}   BldFl1Sh({p}) - {'Flap' if dominant_label == 'X' else 'Edge'} mode {mode['no']}, coeff of x^{p} ")


    # (옵션) 피팅된 값 계산
    # y_fit = sum(c * x_data**p for p, c in zip(powers, coeffs))
    # plt.plot(zNode, (y_fit * np.max(np.abs(dominant_data))), 'r-.', lw = 7, label='Fitted')

    # plt.show()
    file.close()

#----------------------------------------------------------------------------------------
def get_ModeFitPars(x, y, powers=[2, 3, 4, 5, 6]):
    # 설계 행렬(Design Matrix) 생성: [[x1^2, x1^3, ...], [x2^2, x2^3, ...]]
    A = np.column_stack([x**p for p in powers])
    
    # 최소자승법(Least Squares)으로 계수 계산
    coeffs, residuals, rank, s = np.linalg.lstsq(A, y, rcond=None)
    return coeffs

#----------------------------------------------------------------------------------------
def get_zNode(n_elem, order_elem, blade_length):

    import yaml
    file_path = 'Main_BD.BD1.sum.yaml'

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        print(f"\n✅ '{file_path}' 파일 로드 성공!")
        print(f"Get span data of blade node")

        order_elem    = data.get('Number_of_nodes') - 1
        blade_length  = data.get('Length')
        Init_nodes_E1 = data.get('Init_Nodes_E1')

        zNode = [col[2] for col in Init_nodes_E1]   
        print(f"해석용 노드 개수: {len(zNode)}")
        print(f"실제 Span 위치(m):\n   {zNode}")

    except FileNotFoundError:
        print(f"❌ 오류: '{file_path}' 파일이 없습니다.")
        data = None
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        data = None
            
    if data == None:
        zNode = cal_beamdyn_actual_nodes(n_elem, order_elem=order_elem, blade_length=blade_length)
        print(f"해석용 노드 개수: {len(zNode)}")
        print(f"실제 Span 위치(m):\n   {zNode}")

    return zNode

#----------------------------------------------------------------------------------------
def cal_beamdyn_actual_nodes(n_elem, order_elem, blade_length):
    # 1. 단일 엘리먼트 내 LGL 상대 위치 (-1 ~ 1 사이 n+1개 점)
    # n차 Lobatto 노드는 (n-1)차 Legendre 다항식의 뿌리에 양 끝점(-1, 1)을 추가한 것
    internal_nodes, _ = roots_legendre(order_elem - 1)
    lgl_coords        = np.concatenate(([-1.0], internal_nodes, [1.0]))
    
    # 2. 전체 길이를 n_elem만큼 등분
    elem_boundaries   = np.linspace(0, blade_length, n_elem + 1)
    final_nodes = []
    
    for i in range(n_elem):
        start, end    = elem_boundaries[i], elem_boundaries[i+1]
        width         = (end - start) / 2.0
        center        = (start + end) / 2.0
        # LGL 좌표를 실제 구간(m)으로 사상 (Mapping)
        actual_points = center + width * lgl_coords
        
        if i == 0:
            final_nodes.extend(actual_points)
        else:
            final_nodes.extend(actual_points[1:]) # 중복되는 경계 노드 제거

    return np.array(final_nodes)           

#----------------------------------------------------------------------------------------
def eig_A(lin_file_path = 'Main_ED_SD_3mwPrototypeTower_Lin.1.lin'):
    lin = FASTLinearizationFile(lin_file_path)
    w, v = np.linalg.eig(lin['A'])
    total_node_number = int(lin.nx/6/2)  # 1st node position = 0

    freqs = np.abs(np.imag(w)) / (2 * np.pi)
    dampings = -np.real(w) / np.abs(w)
    state_desc = np.array(lin['x_info']['Description'])

    print(f"total_node_number = {total_node_number}")

    # 주파수 오름차순 정렬
    sort_idx = np.argsort(freqs)

    print(f"\n[OpenFAST 전체 행렬 추출 결과 - 필터 없음]")
    print(f"{'No':<3} | {'Freq [Hz]':<10} | {'Damping':<10} | {'Dominant State'}\n{'-'*100}")

    count = 0
    for idx in sort_idx:
        f = freqs[idx]
        
        # 강체 모드(0Hz) 무시
        if f < 0.01: continue
        
        # 고유값 켤레쌍 중 양의 주파수 성분만 출력 (음수 주파수 파트 무시)
        if w[idx].imag < 0: continue

        # 가장 크게 움직이는 상태 변수 찾기
        mag = np.abs(v[:, idx])
        max_idx = np.argmax(mag)
        max_desc = state_desc[max_idx]
        
        count += 1
        print(f"{count:03d} | {f:10.4f} | {dampings[idx]:10.4f} | {max_desc}")
        
        # 너무 길어지는 것을 방지하기 위해 상위 60개만 출력 (필요시 조절)
        if count >= 60: break

# eig_A()