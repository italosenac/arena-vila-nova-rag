"""Empacotamento explícito: python -m src.package --output .local-tools/arena.zip."""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import tempfile
import subprocess
import sys
import zipfile
from .knowledge import load_base

ROOT = Path(__file__).resolve().parents[1]
MODULES = ('__init__', 'config', 'knowledge', 'language', 'retriever', 'policies',
           'llm', 'service', 'conversation', 'webhook')
FILES = tuple(f'src/{name}.py' for name in MODULES) + ('data/base.json',)

def build_archive(output: Path, root: Path = ROOT) -> dict:
    if len(load_base(root/'data/base.json')) != 39:
        raise ValueError('Corpus incompleto ou ampliado')
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as archive:
        for name in FILES:
            content=(root/name).read_bytes()
            if name.endswith('.py'):
                compile(content,name,'exec')
            archive.writestr(name,content)
    with zipfile.ZipFile(output) as archive:
        if archive.testzip() is not None or set(archive.namelist()) != set(FILES):
            raise ValueError('ZIP inválido')
        with tempfile.TemporaryDirectory() as directory:
            archive.extractall(directory)
            subprocess.run([sys.executable,'-I','-c',
                'import sys; sys.path.insert(0, sys.argv[1]); '
                'from src.webhook import lambda_handler; '
                'from src.knowledge import load_base; assert len(load_base()) == 39',directory],
                check=True,capture_output=True,timeout=15,cwd=directory)
    digest=hashlib.sha256(output.read_bytes()).digest()
    return {'sha256':digest.hex(),'code_sha256':base64.b64encode(digest).decode(),
            'files':list(FILES),'bytes':output.stat().st_size}

def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=Path('.local-tools/arena.zip'))
    args=parser.parse_args()
    print(json.dumps(build_archive(args.output),ensure_ascii=False))
    return 0

if __name__=='__main__':
    raise SystemExit(main())
