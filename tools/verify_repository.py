"""Verify package hashes, Python syntax and local documentation links offline."""
from pathlib import Path
import ast
import hashlib
import json
import re
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]

def main():
    count = 0
    for folder in ('03_Inference_Pi/runtime', '05_Dashboard/station'):
        base = ROOT / folder
        manifest = json.loads((base / 'manifest.json').read_text(encoding='utf-8'))
        for name, expected in manifest['files_sha256'].items():
            path = (base / name).resolve()
            if not path.is_relative_to(base) or not path.is_file():
                raise RuntimeError(f'Missing or unsafe manifest path: {path}')
            if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                raise RuntimeError(f'Hash mismatch: {path}')
            count += 1
    evidence = ROOT / 'docs/evidence'
    for line in (evidence / 'SHA256SUMS').read_text(encoding='utf-8').splitlines():
        expected, name = line.split('  ', 1)
        path = (evidence / name).resolve()
        if not path.is_relative_to(evidence):
            raise RuntimeError(f'Unsafe evidence path: {name}')
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise RuntimeError(f'Evidence hash mismatch: {name}')
        count += 1
    for path in ROOT.rglob('*.py'):
        if '__pycache__' not in path.parts:
            ast.parse(path.read_text(encoding='utf-8-sig'), filename=str(path))
    for path in ROOT.rglob('*.md'):
        for target in re.findall(r'\]\(([^)]+)\)', path.read_text(encoding='utf-8')):
            if '://' in target or target.startswith(('#', 'mailto:')):
                continue
            local = unquote(target.split('#')[0])
            if local and not (path.parent / local).exists():
                raise RuntimeError(f'Broken link in {path.relative_to(ROOT)}: {target}')
    print(f'PASS: {count} file hashes, Python syntax and local Markdown links')

if __name__ == '__main__':
    main()
