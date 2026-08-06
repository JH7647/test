import os
import copy
import re

class OpenFastIO:
    """ OpenFAST 파일들의 실제 데이터를 가상으로 읽고 쓰는 엔진 """

    _config_template = {
        "MainFST":      {"default": "", "current": ""},

        "CompElast":    {"default": "0", "current": ""},
        "EDFile":       {"default": "ElastoDyn.dat", "current": ""},
        "BldFile(1)":   {"default": "blade_ElastoDyn.dat", "current": ""},
        "BldFile(2)":   {"default": "blade_ElastoDyn.dat", "current": ""},
        "BldFile(3)":   {"default": "blade_ElastoDyn.dat", "current": ""},

        "BDBldFile(1)": {"default": "BeamDyn.dat", "current": ""},
        "BDBldFile(2)": {"default": "BeamDyn.dat", "current": ""},
        "BDBldFile(3)": {"default": "BeamDyn.dat", "current": ""},
        "BldFile":      {"default": "blade_BeamDyn.dat", "current": ""},

        "CompInflow":   {"default": "0", "current": ""},
        "InflowFile":   {"default": "InflowWind.dat", "current": ""},

        "CompAero":     {"default": "0", "current": ""},
        "AeroFile":     {"default": "AeroDyn.dat", "current": ""},
        "ADBlFile(1)":  {"default": "blade_AeroDyn.dat", "current": ""},
        "ADBlFile(2)":  {"default": "blade_AeroDyn.dat", "current": ""},
        "ADBlFile(3)":  {"default": "blade_AeroDyn.dat", "current": ""},
        "NumAFfiles":   {"default": "0", "current": ""},
        "AFFileList":   {"default": [], "current": []},

        "CompServo":    {"default": "0", "current": ""},
        "ServoFile":    {"default": "ServoDyn.dat", "current": ""},
        "DLL_FileName": {"default": "", "current": ""},

        "CompSeaSt":    {"default": "0", "current": ""},
        "SeaStFile":    {"default": "SeaState.dat", "current": ""},
        "CompHydro":    {"default": "0", "current": ""},
        "HydroFile":    {"default": "HydroDyn.dat", "current": ""},
        "CompSub":      {"default": "0", "current": ""},
        "SubFile":      {"default": "SubDyn.dat", "current": ""},
        "CompMooring":  {"default": "0", "current": ""},
        "MooringFile":  {"default": "MoorDyn.dat", "current": ""},
        "CompIce":      {"default": "0", "current": ""},
        "IceFile":      {"default": "Ice.dat", "current": ""},
        "CompSoil":     {"default": "0", "current": ""},
        "SoilFile":     {"default": "Soil.dat", "current": ""},

        "TMax":         {"default": "600.0", "current": ""},
        "DT":           {"default": "0.0125", "current": ""},
        "WakeMod":      {"default": "1", "current": ""}
    }

    _MODULE_MAP = [
        ("CompInflow", "InflowFile", "Inflow"),
        ("CompSeaSt", "SeaStFile", "SeaSt"),
        ("CompHydro", "HydroFile", "Hydro"),
        ("CompSub", "SubFile", "Sub"),
        ("CompMooring", "MooringFile", "Mooring"),
        ("CompIce", "IceFile", "Ice"),
        ("CompSoil", "SoilFile", "Soil"),
    ]

    current_config = {}

    @classmethod
    def reset_config_to_defaults(cls):
        """ 새 파일을 오픈할 때 메모리(current_config)를 완전히 청소하고 기본 플랜으로 초기화 """
        cls.current_config = {}
        for key, val in cls._config_template.items():
            if isinstance(val["default"], list):
                cls.current_config[key] = {"default": list(val["default"]), "current": list(val["default"])}
            else:
                cls.current_config[key] = {"default": val["default"], "current": val["default"]}

    @staticmethod
    def get_absolute_path(base_file_path, target_file_name):
        """ 상대 경로로 기록된 파일 이름을 완벽한 절대 경로(주소)로 연산 """
        target_file_name = target_file_name.strip()

        if os.path.isabs(target_file_name):
            return target_file_name.replace(os.sep, '/')

        raw_path = os.path.join(os.path.dirname(base_file_path), target_file_name)
        return os.path.abspath(raw_path).replace(os.sep, '/')

    @classmethod
    def read_file(cls, file_path, config_dict):
        """ 단순화한 통합 리더기 (O(줄) 집합 조회로 최적화) """
        if not os.path.exists(file_path):
            return config_dict

        scalar_keys = {k for k, v in config_dict.items() if not isinstance(v["default"], list)}
        has_af = "AFFileList" in config_dict and "NumAFfiles" in config_dict

        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()

            af_start_line = -1

            for idx, line in enumerate(lines):
                clean_line = line.strip()
                if not clean_line:
                    continue

                parts = clean_line.split()
                if len(parts) < 2:
                    continue

                key = parts[1]
                if key in scalar_keys:
                    if key == "NumAFfiles" and "AFNames" in line:
                        continue
                    config_dict[key]["current"] = parts[0].strip('"').strip("'")

                if has_af and "AFNames" in line:
                    af_start_line = idx - 1

            if af_start_line != -1:
                num_af = int(config_dict["NumAFfiles"]["current"] or config_dict["NumAFfiles"]["default"])
                result_list = []

                for i in range(1, num_af + 1):
                    target_idx = af_start_line + i
                    if target_idx < len(lines):
                        next_parts = lines[target_idx].strip().split() # AFFileList는 파일 경로만 있으므로 parts[0]만 사용
                        if next_parts:
                            result_list.append(cls.get_absolute_path(file_path, next_parts[0].strip('"').strip("'")))

                config_dict["AFFileList"]["current"] = result_list

        except Exception as e:
            print(f"간단 리더기 가동 중 예외 발생: {e}")

        return config_dict

    @classmethod
    def _int_val(cls, key):
        """ 현재/기본값을 정수로 안전하게 변환 (비활성=0) """
        val = cls.current_config[key].get("current") or cls.current_config[key]["default"]
        try:
            return int(val)
        except (TypeError, ValueError):
            return 0

    @classmethod
    def _resolve_path(cls, file_key, base_path):
        """ file_key 의 파일명을 base_path 기준 절대경로로 해석 """
        name = cls.current_config[file_key].get("current") or cls.current_config[file_key]["default"]
        return cls.get_absolute_path(base_path, name)

    @classmethod
    def update_config_from_fst(cls, root_path):
        """ .fst를 시작으로 연쇄 파싱을 수행하여 중앙 config만 완벽히 업데이트 """

        cls.reset_config_to_defaults()
        cls.current_config["MainFST"]["current"] = root_path
        cls.current_config = cls.read_file(root_path, cls.current_config)

        # ElastoDyn
        comp_elast = cls._int_val("CompElast")
        if comp_elast in (1, 2):
            ed_path = cls._resolve_path("EDFile", root_path)
            cls.current_config = cls.read_file(ed_path, cls.current_config)

        # BeamDyn (+ 하위 BldFile)
        if comp_elast == 2:
            for num in range(1, 4):
                bd_path = cls._resolve_path(f"BDBldFile({num})", ed_path)
                cls.current_config = cls.read_file(bd_path, cls.current_config)
                bld_path = cls._resolve_path("BldFile", bd_path)
                cls.current_config = cls.read_file(bld_path, cls.current_config)

        # AeroDyn
        if cls._int_val("CompAero") > 0:
            ae_path = cls._resolve_path("AeroFile", root_path)
            cls.current_config = cls.read_file(ae_path, cls.current_config)

        # ServoDyn (+ DLL)
        if cls._int_val("CompServo") > 0:
            sv_path = cls._resolve_path("ServoFile", root_path)
            cls.current_config = cls.read_file(sv_path, cls.current_config)
            dll_path = cls._resolve_path("DLL_FileName", sv_path)
            cls.current_config = cls.read_file(dll_path, cls.current_config)

        # 나머지 독립 모듈 (데이터 기반 루프)
        for comp_key, file_key, _ in cls._MODULE_MAP:
            if cls._int_val(comp_key) > 0:
                mod_path = cls._resolve_path(file_key, root_path)
                cls.current_config = cls.read_file(mod_path, cls.current_config)

        return cls.current_config

    @staticmethod
    def read_module_data(file_path):
        """ 파일을 읽어 UI 입력창에 뿌려줄 데이터를 평탄화된 딕셔너리로 변환 """
        if not file_path or not os.path.exists(file_path):
            return {}

        config = copy.deepcopy(OpenFastIO._config_template)
        config = OpenFastIO.read_file(file_path, config)

        return {
            k: (v["current"] if v["current"] else v["default"])
            for k, v in config.items()
            if not isinstance(v["default"], list)
        }

    @staticmethod
    def save_module_data(file_path, updated_data, description=None):
        """ UI에서 수정한 딕셔너리 데이터를 받아 실제 텍스트 파일로 저장 """
        if not file_path or not os.path.exists(file_path):
            print(f"❌ [저장 실패] 파일이 존재하지 않습니다: {file_path}")
            return False

        if not isinstance(updated_data, dict):
            print("❌ [저장 실패] 변경 데이터가 딕셔너리 형식이 아닙니다.")
            return False

        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()

            new_lines = list(lines) # 원본 라인의 복사본을 만듭니다.

            # Description은 두 번째 줄에 위치하므로 특별 처리
            if description is not None and len(lines) > 1:
                new_lines[1] = description + "\n"

            for key, new_val in updated_data.items():
                for i, line in enumerate(new_lines):
                    # Description은 이미 처리되었으므로 건너뜁니다.
                    if i == 1 and description is not None:
                        continue

                    stripped = line.strip()
                    if not stripped:
                        continue

                    # 키가 라인에 포함되어 있고, 주석 라인이 아닌 경우 (-------)
                    if key in line and "-------" not in line:
                        # 키워드 앞의 값 부분을 찾기 위한 정규식 (숫자 또는 따옴표로 묶인 문자열)
                        # 예: "   5   SttsTime" -> "   5"
                        # 예: '"ES10.3E2"   OutFmt' -> '"ES10.3E2"'
                        match = re.match(r'^\s*(".*?"|\'.*?\'|\S+)\s+' + re.escape(key), stripped)
                        if match:
                            old_value_str = match.group(1)
                            leading_whitespace = line[:len(line) - len(line.lstrip())]
                            # 새 값으로 교체하고 줄의 나머지 부분 유지
                            # 값을 10자리로 맞추고, 나머지 부분은 그대로 유지합니다.
                            remainder = line.split(key, 1)[1]
                            new_lines[i] = f"{str(new_val):<12}{key}{remainder}"
                            break # 키를 찾아서 업데이트했으면 다음 키로 넘어감

            with open(file_path, 'w', encoding='utf-8') as f:
                f.writelines(new_lines)

            print(f"💾 [저장 완료] 파일: {file_path}")
            print(f"📝 [변경 내용]: {updated_data}")
            return True

        except Exception as e:
            print(f"❌ [저장 실패] 파일: {file_path}, 오류: {e}")
            return False
