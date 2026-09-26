with open(r'C:\TEST\WB\src\ui\tabs_input\files_tab.py', 'rb') as f:
    content = f.read()
lines = content.split(b'\n')

# Fix process_tree_add_to_pending method and move class-level variables to __init__
output_lines = []
i = 0
while i < len(lines):
    line = lines[i]
    
    # Fix process_tree_add_to_pending - add method body
    if b'def process_tree_add_to_pending(self, file_path):' in line:
        output_lines.append(line)
        output_lines.append(b'        """DEPRECATED: queue_mgr.add_file() use"""')
        output_lines.append(b'        self.queue_mgr.add_file(file_path)')
        # Skip the empty line and class-level variables
        i += 3  # skip line 1054 (empty), 1055 (running_processes), 1056 (process_logs)
        continue
    
    # Skip class-level variables that should be in __init__
    if b'self.running_processes = []' in line and i >= 1050:
        i += 1
        continue
    if b'self.process_logs = {}' in line and i >= 1050:
        i += 1
        continue
        
    output_lines.append(line)
    i += 1

with open(r'C:\TEST\WB\src\ui\tabs_input\files_tab.py', 'wb') as f:
    f.write(b'\n'.join(output_lines))

print('Fixed process_tree_add_to_pending and removed class-level variables')