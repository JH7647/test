import os
import copy

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
        "AFFileList":   {"default": [], "current": []}, # 가변 리스트 대응
        
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
        
        # UI 연동 보완용 파라미터 백업 공간 추가
        "TMax":         {"default": "600.0", "current": ""},
        "DT":           {"default": "0.0125", "current": ""},
        "WakeMod":      {"default": "1", "current": ""}
    }

    current_config = {}

    @classmethod
    def reset_config_to_defaults(cls):
        """ 새 파일을 오픈할 때 메모리(current_config)를 완전히 청소하고 기본 플랜으로 초기화 """
        cls.current_config = {}
        cls.current_config = copy.deepcopy(cls._config_template)

        for key, val in cls._config_template.items():
            # 가변 리스트(예: AFFileList)가 들어오면 독립된 리스트로 안전하게 복제(copy)
            if isinstance(val["default"], list):
                cls.current_config[key] = {"default": list(val["default"]), "current": list(val["default"])}
            else:
                cls.current_config[key] = {"default": val["default"], "current": val["default"]}

    @staticmethod
    def get_absolute_path(base_file_path, target_file_name):
        """ 상대 경로로 기록된 파일 이름을 완벽한 절대 경로(주소)로 연산 """
        target_file_name = target_file_name.strip()
        
        # 이미 절대 경로(예: C:/...)라면 변환 없이 슬래시만 정리해서 즉시 반환
        if os.path.isabs(target_file_name):
            return target_file_name.replace(os.sep, '/')
            
        # 기준 파일(예: Servo.dat)의 부모 폴더와 타깃 파일명을 매끄럽게 결합
        raw_path = os.path.join(os.path.dirname(base_file_path), target_file_name)
        return os.path.abspath(raw_path).replace(os.sep, '/')

    @classmethod
    def read_file(cls, file_path, config_dict):
        """ 단순화한 통합 리더기 """
        if not os.path.exists(file_path):
            return config_dict
            
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
                
                af_start_line = -1

                for idx, line in enumerate(lines):
                    clean_line = line.strip()
                    if not clean_line:
                        continue

                    parts = clean_line.split()
                    if not parts:
                        continue

                    # 딕셔너리에 등록된 변수와 매칭
                    for key in config_dict:
                        # 🔹 [일반 단일 변수 매칭]: 줄 오른쪽 주석 구역에 변수명(key)이 적혀있다면!
                        if len(parts) > 1 and parts[1] == key:
                            # 예외 방어: 주석에 적힌 헷갈리는 문구는 그냥 패스!
                            if key == "NumAFfiles" and "AFNames" in line:
                                continue
                                
                            # 0번째 방에 든 수치/경로를 current에 저장하고 마무리!
                            config_dict[key]["current"] = parts[0].strip('"').strip("'")

                        # 🔹 [가변 목록 트리거 포착]: AFNames 라는 문장을 만나면 그 줄 번호를 기록해 둡니다.
                        if "AFNames" in line and key == "AFFileList":
                            af_start_line = idx - 1

                # 위에서 기록한 AFNames 줄 바로 다음 줄부터 개수만큼 연속 텍스트 수집!
                if af_start_line != -1:
                    num_af = int(config_dict["NumAFfiles"]["current"] or config_dict["NumAFfiles"]["default"])
                    result_list = []
                    
                    for i in range(1, num_af + 1):
                        target_idx = af_start_line + i
                        if target_idx < len(lines):
                            next_parts = lines[target_idx].strip().split()
                            if next_parts:
                                result_list.append(cls.get_absolute_path(file_path, next_parts[0].strip('"').strip("'")))

                    config_dict["AFFileList"]["current"] = result_list

        except Exception as e:
            print(f"간단 리더기 가동 중 예외 발생: {e}")
            
        return config_dict
    

    @classmethod
    def update_config_from_fst(cls, root_path):
        """ .fst를 시작으로 연쇄 파싱을 수행하여 중앙 config만 완벽히 업데이트 """

        cls.reset_config_to_defaults()    

        cls.current_config["MainFST"]["current"] = root_path  
        
        cls.current_config = cls.read_file(root_path, cls.current_config)

        module = "CompElast"
        comp_elast = int(cls.current_config[module].get("current") or cls.current_config[module]["default"])
        if comp_elast in [1, 2]:
            module = "EDFile"
            f_name = cls.current_config[module]["current"] or cls.current_config[module]["default"]
            f_path = cls.get_absolute_path(root_path, f_name)

            cls.current_config = cls.read_file(f_path, cls.current_config)

        if comp_elast == 2:
            for num in range(1, 4):
                module = f"BDBldFile({num})"
                f_name = cls.current_config[module]["current"] or cls.current_config[module]["default"]
                f_path = cls.get_absolute_path(f_path, f_name)

                cls.current_config = cls.read_file(f_path, cls.current_config)

                module = "BldFile"
                f_name = cls.current_config[module]["current"] or cls.current_config[module]["default"]
                f_path = cls.get_absolute_path(f_path, f_name)

                cls.current_config = cls.read_file(f_path, cls.current_config)

        module = "CompAero"
        comp_aero = int(cls.current_config[module].get("current") or cls.current_config[module]["default"])
        if comp_aero > 0:
            module = "AeroFile"
            ae_name = cls.current_config[module]["current"] or cls.current_config[module]["default"]
            ae_path = cls.get_absolute_path(root_path, ae_name)

            cls.current_config = cls.read_file(ae_path, cls.current_config)
         
        module = "CompServo"
        comp_servo = int(cls.current_config[module].get("current") or cls.current_config[module]["default"])
        if comp_servo > 0:
            module = "ServoFile"
            name = cls.current_config[module]["current"] or cls.current_config[module]["default"]
            path = cls.get_absolute_path(root_path, name)

            cls.current_config = cls.read_file(path, cls.current_config)
            
            for num in range(1, 2):
                module = f"DLL_FileName"
                name = cls.current_config[module]["current"] or cls.current_config[module]["default"]
                path = cls.get_absolute_path(path, name) 
                
                cls.current_config = cls.read_file(path, cls.current_config)

        module = "CompSeaSt"
        comp_seast = int(cls.current_config[module].get("current") or cls.current_config[module]["default"])
        if comp_seast > 0:
            module = "SeaStFile"
            name = cls.current_config[module]["current"] or cls.current_config[module]["default"]
            path = cls.get_absolute_path(root_path, name)

            cls.current_config = cls.read_file(path, cls.current_config)

        module = "CompHydro"
        comp_hydro = int(cls.current_config[module].get("current") or cls.current_config[module]["default"])
        if comp_hydro > 0:
            module = "HydroFile"
            name = cls.current_config[module]["current"] or cls.current_config[module]["default"]
            path = cls.get_absolute_path(root_path, name)

            cls.current_config = cls.read_file(path, cls.current_config)

        module = "CompSub"
        comp_sub = int(cls.current_config[module].get("current") or cls.current_config[module]["default"])
        if comp_sub > 0:
            module = "SubFile"
            name = cls.current_config[module]["current"] or cls.current_config[module]["default"]
            path = cls.get_absolute_path(root_path, name)

            cls.current_config = cls.read_file(path, cls.current_config)

        module = "CompMooring"
        comp_moor = int(cls.current_config[module].get("current") or cls.current_config[module]["default"])
        if comp_moor > 0:
            module = "MooringFile"
            name = cls.current_config[module]["current"] or cls.current_config[module]["default"]
            path = cls.get_absolute_path(root_path, name)

            cls.current_config = cls.read_file(path, cls.current_config)

        module = "CompIce"
        comp_ice = int(cls.current_config[module].get("current") or cls.current_config[module]["default"])
        if comp_ice > 0:
            module = "IceFile"
            name = cls.current_config[module]["current"] or cls.current_config[module]["default"]
            path = cls.get_absolute_path(root_path, name)

            cls.current_config = cls.read_file(path, cls.current_config)

        module = "CompSoil"
        comp_soil = int(cls.current_config[module].get("current") or cls.current_config[module]["default"])
        if comp_soil > 0:
            module = "SoilFile "
            name = cls.current_config[module]["current"] or cls.current_config[module]["default"]
            path = cls.get_absolute_path(root_path, name)

            cls.current_config = cls.read_file(path, cls.current_config)

        # UI 화면단으로 연산이 모두 끝난 최종 최신 데이터 구조 전달
        return cls.current_config

    # 외부 UI 입력 탭 전용 소통 채널 (Main, Aero 탭 전용)
    @classmethod
    def read_module_data(cls, file_path): ... # UI 입력창에 데이터를 전달하는 함수
    @classmethod
    def save_module_data(cls, file_path, updated_data): ... # UI에서 바꾼 데이터를 파일에 저장하는 함수


    @staticmethod
    def read_module_data(file_path):
        """ 파일을 읽어 UI 입력창에 뿌려줄 데이터를 딕셔너리로 변환 """
        # 실제 개발시에는 이곳에 텍스트 파싱 로직이 들어갑니다.
        # 동작 확인을 위한 가상 데이터를 반환합니다.
        filename = os.path.basename(file_path).lower()
        
        if "aero" in filename or ".dat" in filename:
            return {"WakeMod": "1", "AFAeroMod": "2", "TwindMod": "1"}
        else:
            return {"TMax": "600.0", "DT": "0.0125", "CompElast": "1"}

    @staticmethod
    def save_module_data(file_path, updated_data):
        """ UI에서 수정한 딕셔너리 데이터를 받아 실제 텍스트 파일로 저장 """
        print(f"\n💾 [저장 엔진 구동] 파일 경로: {file_path}")
        print(f"📝 [변경 내용]: {updated_data}")
        # 실제 개발시에는 여기서 파일 한 줄씩 읽으며 값을 치환하여 Write합니다.
        return True
