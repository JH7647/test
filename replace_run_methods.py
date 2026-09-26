# -*- coding: utf-8 -*-
with open(r'C:\TEST\WB\src\ui\tabs_input\files_tab.py', 'rb') as f:
    content = f.read()

# Positions found
start = 46482  # def btn_left_run_clicked (0 indent)
end = 48564    # def process_tree_add_to_pending (4 indent)

print(f"Replacing bytes {start} to {end} (length {end-start})")

# Read new code
with open(r'C:\TEST\WB\new_code.txt', 'rb') as f:
    new_code = f.read()

# Add 4 spaces to each non-empty line
new_lines = []
for line in new_code.split(b'\n'):
    if line.strip():
        new_lines.append(b'    ' + line)
    else:
        new_lines.append(line)
new_code = b'\n'.join(new_lines)

# Replace
new_content = content[:start] + new_code + content[end:]

with open(r'C:\TEST\WB\src\ui\tabs_input\files_tab.py', 'wb') as f:
    f.write(new_content)

print('Replaced successfully!')