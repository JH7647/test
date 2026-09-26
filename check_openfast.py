with open(r'C:\TEST\WB\src\core\openfast_io.py', 'rb') as f:
    content = f.read()
lines = content.split(b'\n')
for i, l in enumerate(lines):
    if b'class ' in l and b':' in l:
        print(f'{i+1}: {l[:100].decode(errors="ignore")}')
    if b'def get_model_tree_data' in l:
        for j in range(max(0,i-5), i):
            print(f'  {j+1}: {lines[j][:100].decode(errors="ignore")}')
        break