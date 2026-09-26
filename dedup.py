with open(r'C:\TEST\WB\src\ui\tabs_input\files_tab.py', 'rb') as f:
    content = f.read()
lines = content.split(b'\n')

# Deduplicate: keep only first occurrence of each method definition
seen_methods = set()
output_lines = []
i = 0
while i < len(lines):
    line = lines[i]
    stripped = line.strip()
    
    # Check if this is a method definition at class level (4-space indent)
    if stripped.startswith(b'def ') and len(line) - len(line.lstrip()) == 4:
        method_name = stripped.split(b'(')[0].replace(b'def ', b'').strip()
        if method_name in seen_methods:
            # Skip this method entirely - find next method or class-level def
            i += 1
            while i < len(lines):
                next_line = lines[i]
                next_stripped = next_line.strip()
                if next_stripped.startswith(b'def ') and len(next_line) - len(next_line.lstrip()) == 4:
                    break
                i += 1
            continue
        else:
            seen_methods.add(method_name)
    
    output_lines.append(line)
    i += 1

with open(r'C:\TEST\WB\src\ui\tabs_input\files_tab.py', 'wb') as f:
    f.write(b'\n'.join(output_lines))

print(f'Deduplicated: kept {len(seen_methods)} unique methods')
print('Methods:', sorted([m.decode() for m in seen_methods]))