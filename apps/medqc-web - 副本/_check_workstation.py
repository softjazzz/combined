import urllib.request
import json

resp = urllib.request.urlopen('http://localhost:8000/api/medical-records/workstation')
d = json.loads(resp.read())
print(f"总记录数: {d['total']}")
print(f"科室数: {len(d['departments'])}")
print("---")
for r in d['records']:
    name = r['name']
    rid = r['id']
    dept = r['department']
    status = r['status']
    print(f"  {name:6s} | {rid:20s} | {dept:8s} | 状态:{status}")
