"""修复 EMRViewer.vue 中 \\r\\r\\n 双换行问题"""

path = r'd:\大模型项目\lx0222\health-qc-monorepo\apps\medqc-web\src\components\qc\EMRViewer.vue'

with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# 把 \r\r\n 全部换成 \r\n
fixed = content.replace('\r\r\n', '\r\n')

with open(path, 'w', encoding='utf-8', newline='') as f:
    f.write(fixed)

print("Fixed double CRLF")

# 验证
with open(path, 'r', encoding='utf-8') as f:
    check = f.read()
if '\r\r\n' in check:
    print("WARNING: still contains \\r\\r\\n")
else:
    print("OK: no double CRLF found")
print(f"File size: {len(check)} bytes")
