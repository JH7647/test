# -*- coding: utf-8 -*-
"""Comprehensive cleanup of files_tab.py - remove duplicates, fix indentation"""

with open(r'C:\TEST\WB\src\ui\tabs_input\files_tab.py', 'rb') as f:
    content = f.read()

# Split into lines
lines = content.split(b'\n')

# Track seen methods (by name)
seen_methods = set()
output_lines = []
i = 0

while i < len(lines):
    line = lines[i]
    stripped = line.strip()
    
    # Check if this is a method definition we care about
    is_method_def = False
    method_name = None
    
    for name in [b'btn_left_run_clicked', b'btn_left_stop_clicked', b'process_tree_add_to_pending']:
        if stripped.startswith(b'def ') and name in stripped:
            is_method_def = True
            method_name = name
            break
    
    if is_method_def:
        # Check indentation - only keep if at 4 spaces (class method level)
        indent = len(line) - len(line.lstrip())
        if indent == 4:
            if method_name not in seen_methods:
                seen_methods.add(method_name)
                output_lines.append(line)
                # Continue adding body lines until next method or class-level item
                i += 1
                while i < len(lines):
                    next_line = lines[i]
                    next_stripped = next_line.strip()
                    next_indent = len(next_line) - len(next_line.lstrip())
                    
                    # Stop at next class method (4 spaces + def) or class definition
                    if next_stripped.startswith(b'def ') and next_indent <= 4:
                        # Don't consume this line, let outer loop handle it
                        i -= 1
                        break
                    if next_stripped.startswith(b'class ') and next_indent == 0:
                        i -= 1
                        break
                    output_lines.append(next_line)
                    i += 1
                continue
            else:
                # Skip duplicate or wrongly indented method
                # Skip until next method or class-level item
                i += 1
                while i < len(lines):
                    next_line = lines[i]
                    next_stripped = next_line.strip()
                    next_indent = len(next_line) - len(next_line.lstrip())
                    
                    if next_stripped.startswith(b'def ') and next_indent <= 4:
                        i -= 1
                        break
                    if next_stripped.startswith(b'class ') and next_indent == 0:
                        i -= 1
                        break
                    i += 1
                continue
    
    output_lines.append(line)
    i += 1

# Also fix merged lines (lines with two statements on one line)
cleaned_lines = []
for line in output_lines:
    # Fix common merged patterns
    # Pattern: "statement1    def method_name"
    if b'def ' in line and not line.strip().startswith(b'def '):
        # Split at '    def '
        parts = line.split(b'    def ', 1)
        if len(parts) == 2:
            cleaned_lines.append(parts[0].rstrip())
            cleaned_lines.append(b'    def ' + parts[1])
            continue
    cleaned_lines.append(line)

# Write back
new_content = b'\n'.join(cleaned_lines)
with open(r'C:\TEST\WB\src\ui\tabs_input\files_tab.py', 'wb') as f:
    f.write(new_content)

print('Cleanup done!')
print(f'Kept methods: {seen_methods}')