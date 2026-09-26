with open(r'C:\TEST\WB\src\ui\tabs_input\files_tab.py', 'rb') as f:
    content = f.read()
lines = content.split(b'\n')

# Find context menu handlers that call old methods
output_count = 0
for i, l in enumerate(lines):
    if b'process_tree_' in l and b'def' not in l:
        # Find the method this call is in
        method_name = 'unknown'
        for j in range(i, -1, -1):
            if b'def ' in lines[j] and len(lines[j]) - len(lines[j].lstrip()) == 4:
                method_name = lines[j].strip()[:80].decode('utf-8', errors='ignore')
                break
        if 'process_tree' not in method_name and 'mouse_Rclick' not in method_name:
            spaces = len(l) - len(l.lstrip())
            print(f'Line {i+1} (in {method_name}): [{spaces} spaces] {l[:100]!r}')
            output_count += 1
            if output_count >= 30:
                break