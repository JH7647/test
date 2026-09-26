with open(r'C:\TEST\WB\src\ui\tabs_input\files_tab.py', 'rb') as f:
    content = f.read()
lines = content.split(b'\n')

# Replace all calls to process_tree_apply_status_style with _apply_status_style
# and remove the two method definitions
output_lines = []
i = 0
while i < len(lines):
    line = lines[i]
    
    # Replace method calls
    if b'self.process_tree_apply_status_style' in line and b'def' not in line:
        line = line.replace(b'self.process_tree_apply_status_style', b'self._apply_status_style')
        output_lines.append(line)
        i += 1
        continue
    
    # Skip the two method definitions
    if b'def process_tree_apply_status_style(self, item, status):' in line:
        # Skip until next method (4-space indent with def)
        i += 1
        while i < len(lines):
            next_line = lines[i]
            if next_line.strip() and len(next_line) - len(next_line.lstrip()) == 4 and next_line.strip().startswith(b'def '):
                break
            i += 1
        continue
        
    output_lines.append(line)
    i += 1

with open(r'C:\TEST\WB\src\ui\tabs_input\files_tab.py', 'wb') as f:
    f.write(b'\n'.join(output_lines))

print('Replaced calls and removed duplicate methods')