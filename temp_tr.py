import numpy as np
import matplotlib.pyplot as plt

# ==============================================================================
# 1. 파일 이름 및 경로 지정 (필요시 경로 수정)
# ==============================================================================
file_name = "Main_P0Cd4_Default_exported.txt"

# ==============================================================================
# 2. 파일 오픈 및 데이터 로드 (텍스트 헤더 건너뛰기 기능 포함)
# ==============================================================================
time_data = []
input_data = []
output_data = []

print(f"[알림] '{file_name}' 파일을 읽어오는 중입니다...")

with open(file_name, 'r', encoding='utf-8') as f:
    for line in f:
        # 공백 제거 및 탭/띄어쓰기 단위 분할
        tokens = line.strip().split()
        
        # 행이 비어있거나 헤더 문자열(영어, 기호)인 경우 건너뜀
        if not tokens or not tokens[0][0].isdigit():
            continue
            
        try:
            # 문자열 데이터를 부동 소수점(Float)으로 변환하여 저장
            time_data.append(float(tokens[0]))
            input_data.append(float(tokens[1]))
            output_data.append(float(tokens[2]))
        except (ValueError, IndexError):
            # 숫자로 바꿀 수 없는 예외 행 필터링
            continue

# 리스트를 수치 해석용 넘파이 배열(Numpy Array)로 변환
t = np.array(time_data)
x = np.array(input_data)  # 입력 (PtfmPitch)
y = np.array(output_data) # 출력 (Wave1Elev)

print(f"[성공] 데이터 로드 완료. 총 {len(t)}개의 시계열 행을 추출했습니다.")

# ==============================================================================
# 3. 주파수 영역 변환 및 전달함수(TR) 수치 연산
# ==============================================================================
# 샘플링 타임스텝(DT) 및 총 데이터 개수(N) 계산
dt = t[1] - t[0]
n = len(t)

# 실수 공간 신호에 최적화된 Fast Fourier Transform (FFT) 가동
freq = np.fft.rfftfreq(n, d=dt)
fft_x = np.fft.rfft(x)
fft_y = np.fft.rfft(y)

# 전달함수 H(f) = Y(f) / X(f) 계산 (분모가 0이 되는 에러 방지)
H = np.zeros_like(fft_y, dtype=complex)
valid_idx = np.abs(fft_x) > 1e-12
H[valid_idx] = fft_y[valid_idx] / fft_x[valid_idx]

# 전달함수의 물리적 성분 추출 (Magnitude Gain 및 Phase Degree)
tr_magnitude = np.abs(H)              # 크기 비율 (Gain)
tr_phase = np.angle(H, deg=True)      # 위상차 (Degree)

# 정밀 분석을 위해 DC 성분(0 Hz) 제거 후 데이터 정렬
freq = freq[1:]
tr_magnitude = tr_magnitude[1:]
tr_phase = tr_phase[1:]

# ==============================================================================
# 4. 보드 선도(Bode Plot) 형태의 그래프 시각화
# ==============================================================================
print("[알림] 전달함수 크기/위상 그래프를 렌더링합니다...")

# 해상도 및 도화지 크기 설정 (전달함수 분석 전용 2단 분할 구조)
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8), sharex=True)
fig.suptitle(f"Transfer Function (TR) Result\nFile: {file_name}", fontsize=14, fontweight='bold')

# [상단 그래프] 주파수별 크기 이득 (Magnitude Gain)
ax1.plot(freq, tr_magnitude, color='blue', marker='o', linestyle='-', linewidth=1.5, label='TR Magnitude')
ax1.set_ylabel("Magnitude Gain\n(Output / Input)", fontsize=11)
ax1.grid(True, which="both", linestyle="--", alpha=0.6)
ax1.legend(loc="upper right")

# [하단 그래프] 주파수별 위상 변화량 (Phase Delay)
ax2.plot(freq, tr_phase, color='red', marker='s', linestyle='-', linewidth=1.5, label='TR Phase')
ax2.set_xlabel("Frequency [Hz]", fontsize=11)
ax2.set_ylabel("Phase Angle [deg]", fontsize=11)
# 위상 가독성을 위해 Y축 범위를 -180도 ~ +180도 수준으로 제어 (필요시 활성화)
ax2.set_ylim(-190, 190) 
ax2.grid(True, which="both", linestyle="--", alpha=0.6)
ax2.legend(loc="upper right")

# 여백 자동 조절 및 화면에 표출
plt.tight_layout()
plt.show()

print("[완료] 그래프 표출이 성공적으로 끝났습니다.")