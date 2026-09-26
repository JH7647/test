import os

class OpenFastIO:
    _config_template = {}
    _MODULE_MAP = []
    current_config = {}
    
    @classmethod
    def update_config_from_fst(cls, fst_path):
        return {}
    
    @staticmethod
    def get_absolute_path(base, rel):
        return rel
    
    @classmethod
    def _build_single_tree_data(cls, fst_path: str) -> dict:
        config = cls.update_config_from_fst(fst_path)
        root = {"name": os.path.basename(fst_path), "path": fst_path, "children": [], "is_root": True}
        
        gv = lambda k: config.get(k, {}).get("current") or config.get(k, {}).get("default", "")
        iv = lambda k: int(gv(k) or 0)
        ap = lambda base, rel: cls.get_absolute_path(base, rel) if rel else ""
        
        # ElastoDyn / BeamDyn
        comp_elast = iv("CompElast")
        if comp_elast in (1, 2):
            ed_file = gv("EDFile")
            ed_path = ap(fst_path, ed_file)
            ed_node = cls._make_node("Elasto", ed_path)
            
            if comp_elast == 1:
                for n in range(1, 4):
                    bld = gv(f"BldFile({n})")
                    if bld: ed_node["children"].append(cls._make_node(f"BldFile({n})", ap(ed_path, bld)))
            else:
                for n in range(1, 4):
                    bd = gv(f"BDBldFile({n})")
                    if bd:
                        bd_path = ap(ed_path, bd)
                        bd_node = cls._make_node(f"Beam({n})", bd_path)
                        bld = gv("BldFile")
                        if bld: bd_node["children"].append(cls._make_node("BldFile", ap(bd_path, bld)))
                        ed_node["children"].append(bd_node)
            
            twr = gv("TwrFile")
            if twr: ed_node["children"].append(cls._make_node("TwrFile", ap(ed_path, twr)))
            root["children"].append(ed_node)
        
        # 독립 모듈 (데이터 기반)
        for comp_key, file_key, display in cls._MODULE_MAP:
            if iv(comp_key) > 0:
                mod_path = ap(fst_path, gv(file_key))
                root["children"].append(cls._make_node(display, mod_path))
        
        return root
    
    @staticmethod
    def _make_node(name: str, path: str) -> dict:
        return {"name": name, "path": path, "children": []}

# Test
result = OpenFastIO._build_single_tree_data("test.fst")
print("Success:", result)