with open(r'C:\TEST\WB\src\ui\tabs_input\files_tab.py', 'rb') as f:
    content = f.read()
print(f'File size: {len(content)} bytes')
print(f'Line count: {len(content.split(b"\n"))}')