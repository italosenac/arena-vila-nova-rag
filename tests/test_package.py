"""Evita enviar artefato inválido ou arquivos de desenvolvimento à Lambda."""
import base64
import hashlib
import zipfile
from src.package import build_archive, FILES

def test_binary_zip_is_complete_and_importable_without_markdown(tmp_path):
    path=tmp_path/'runtime.zip'
    info=build_archive(path)
    with zipfile.ZipFile(path) as archive:
        assert archive.testzip() is None and set(archive.namelist())==set(FILES)
        assert all(name.endswith('.py') or name=='data/base.json' for name in archive.namelist())
    assert info['code_sha256']==base64.b64encode(hashlib.sha256(path.read_bytes()).digest()).decode()
