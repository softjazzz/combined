import importlib.util as u
print('hnswlib', bool(u.find_spec('hnswlib')))
print('faiss', bool(u.find_spec('faiss')))
print('requests', bool(u.find_spec('requests')))
