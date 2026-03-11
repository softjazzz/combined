"""检查 Zhang San 的文书 API 返回"""
import urllib.request, json

resp = urllib.request.urlopen('http://localhost:3000/api/medical-records/documents/V-ZS-001')
d = json.loads(resp.read())

print(f"总文书数: {len(d['documents'])}")
for doc in d['documents']:
    content_preview = repr(doc['content'][:80]) if doc['content'] else 'None'
    print(f"  {doc['type']:30s} | has_content={doc['has_content']} | len={doc['length']} | content={content_preview}")
