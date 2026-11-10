"""Dependency-free verification, usable before installing any AI libraries."""
from pathlib import Path
import hashlib
import json

def digest(path):
    value=hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):value.update(chunk)
    return value.hexdigest()

def verify(root):
    root=Path(root).resolve()
    manifest=json.loads((root/'manifest.json').read_text(encoding='utf-8'))
    for name,expected in manifest['files_sha256'].items():
        path=(root/name).resolve()
        if not path.is_relative_to(root) or not path.is_file() or digest(path)!=expected:
            raise RuntimeError('Package integrity failure: '+name)
    return manifest
