with open(r'C:\TEST\WB\src\ui\tabs_input\files_tab.py', 'rb') as f:
    content = f.read()
lines = content.split(b'\n')

# Fix the broken if block
output_lines = []
i = 0
while i < len(lines):
    line = lines[i]
    
    # Fix the broken if block at line 1298-1299
    if b"if not hasattr(self, 'process_logs'):" in line:
        # Remove this line
        i += 1
        continue
        
    output_lines.append(line)
    i += 1

with open(r'C:\TEST\WB\src\ui\tabs_input\files_tab.py', 'wb') as f:
    f.write(b'\n'.join(output_lines))

print('Fixed broken if block')