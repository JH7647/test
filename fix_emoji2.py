with open(r'C:\TEST\WB\src\ui\tabs_input\files_tab.py', 'r', encoding='utf-8') as f:
    text = f.read()

replacements = {
    '⚡': '[ACTION]',
    '🚀': '[RUN]',
    '📝': '[NOTE]',
    '❌': '[ERROR]',
    '📜': '[FILE]',
    '🛑': '[STOP]',
    '🗑️': '[REMOVE]',
    '🧹': '[CLEANUP]',
    '📁': '[DIR]',
    '📂': '[DIR]',
}

for emoji, replacement in replacements.items():
    text = text.replace('print("' + emoji, 'print("' + replacement)
    text = text.replace("print('" + emoji, "print('" + replacement)
    text = text.replace('self.cmd_output.append("' + emoji, 'self.cmd_output.append("' + replacement)
    text = text.replace("self.cmd_output.append('" + emoji, "self.cmd_output.append('" + replacement)
    text = text.replace('f"' + emoji, 'f"' + replacement)
    text = text.replace("f'" + emoji, "f'" + replacement)
    text = text.replace('f"\\n' + emoji, 'f"\\n' + replacement)
    text = text.replace("f'\\n" + emoji, "f'\\n" + replacement)
    text = text.replace('f"\\\\n' + emoji, 'f"\\\\n' + replacement)
    text = text.replace("f'\\\\n" + emoji, "f'\\\\n" + replacement)
    text = text.replace('f"📂"*5', 'f"[DIR]"*5')

with open(r'C:\TEST\WB\src\ui\tabs_input\files_tab.py', 'w', encoding='utf-8') as f:
    f.write(text)
print('Emoji replacements done!')