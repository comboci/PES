#!/usr/bin/env python3
"""Generate SHA-256 file manifest for a PES-15 release tree (manifest excluded)."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SKIP_DIRS={'__pycache__','.pytest_cache','.git','.venv','build','dist'}

def build():
    items=[]
    for p in ROOT.rglob('*'):
        if not p.is_file() or any(s in SKIP_DIRS for s in p.relative_to(ROOT).parts):continue
        if p.name=='PES-15.package-manifest.json' or p.suffix in ('.pyc','.pyo'):continue
        b=p.read_bytes()
        items.append({'path':p.relative_to(ROOT).as_posix(),'size_bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()})
    items.sort(key=lambda x:x['path'])
    manifest={'standard':'PES-15','schema_revision':'15.1.0','package_role':'standalone_reference_implementation',
        'build_date':'2026-11-20',
        'legacy_PES14_original_zip_sha256':'1a25c34d07c3548c70078a050a4ded130d25e7f252536fe0c6159fca3118732e',
        'legacy_PES14_mutated':False,
        'manifest_self_excluded':True,
        'files':items}
    (ROOT/'PES-15.package-manifest.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print('manifest created with',len(items),'files')

if __name__=='__main__':build()
