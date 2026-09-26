# import os
# # 이미지와 소스코드 구조에 맞춰 campbell.py 파일에서 직접 올인원 함수를 가져옵니다.
# from openfast_toolbox.linearization.campbell import postproCampbell

# # 선형화 실행 타겟 메인 fst 파일 이름 지정
# # (작업 폴더 내에 존재하는 실제 .fst 파일명과 완벽히 일치해야 합니다.)
# fst_file = "Main_ED_SD_3mwPrototypeTower.fst" 
# fst_files_list = [fst_file]

# print(">> [NREL Campbell System] MBC3 구속 변환 및 구조 주파수 복원 연산 가동...")

# # 2. 올인원 후처리 함수 실행 -> 디스크에 'Campbell_Summary.txt' 자동 저장
# OP, Freq, Damp, UnMapped, ModeData, modeID_file = postproCampbell(fst_files_list)

# print("\n🎉 [연산 및 파일 출력 완료] 작업 디렉토리에 후처리 리포트가 저장되었습니다!")
# print(f"생성된 엑셀 가이드 파일: {modeID_file}")

# # 3. 생성된 요약본 텍스트 파일 바로 읽어서 화면에 0.287Hz 복원 결과 요약 출력
# summary_file = "Campbell_Summary.txt"
# if os.path.exists(summary_file):
#     print(f"\n>> '{summary_file}' 내부의 복원된 구조 고유진동수 상단 스캔:")
#     print("-" * 75)
#     with open(summary_file, 'r', encoding='utf-8', errors='ignore') as f:
#         lines = f.readlines()
#         # 텍스트 파일의 상단 핵심 수치 정보 25줄을 가독성 있게 화면에 뿌려줍니다.
#         for line in lines[:25]:
#             print(line.strip())
#     print("-" * 75)
# else:
#     print(f"\n⚠️ 연산은 끝났으나 '{summary_file}' 파일을 찾을 수 없습니다. 출력 파일명을 확인하세요.")


import os
import matplotlib.pyplot as plt
from openfast_toolbox.linearization.campbell import postproCampbell

# 1. 이미지에 완벽히 확인된 실제 .fst 파일 이름을 그대로 지정합니다.
# 엔진이 이 이름을 바탕으로 같은 폴더 내의 .1.lin, .2.lin 파일을 정확히 스캔합니다.
fst_files_list = ["Main_ED_SD_3mwPrototypeTower_Lin.fst"]

print(">> [NREL Campbell System] MBC3 구속 변환 및 구조 주파수(0.287Hz) 복원 연산 가동...")

# 2. 올인원 후처리 함수 정석 실행 (디스크에 'Campbell_Summary.txt' 자동 저장)
OP, Freq, Damp, UnMapped, ModeData, modeID_file = postproCampbell(fst_files_list)

print("\n🎉 [연산 대성공] 후처리 리포트가 작업 폴더에 정상 저장되었습니다!")
print(f"생성된 엑셀 가이드 파일: {modeID_file}")

# 3. 생성된 요약본 텍스트 파일 바로 읽어서 화면에 0.287Hz 복원 결과 요약 출력
summary_file = "Campbell_Summary.txt"
if os.path.exists(summary_file):
    print(f"\n>> '{summary_file}' 내부의 복원된 구조 고유진동수 상단 스캔:")
    print("-" * 75)
    with open(summary_file, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
        # 텍스트 파일의 상단 핵심 수치 정보 25줄을 가독성 있게 화면에 뿌려줍니다.
        for line in lines[:25]:
            print(line.strip())
    print("-" * 75)
