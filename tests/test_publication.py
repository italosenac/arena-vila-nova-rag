"""Confere regras de Git sem inicializar ou commitar o workspace."""

from pathlib import Path
import shutil
import subprocess


def test_report_and_original_dataset_are_git_ignored(tmp_path):
    root = Path(__file__).resolve().parents[1]
    shutil.copy2(root / ".gitignore", tmp_path / ".gitignore")
    subprocess.run(["git", "init", "--quiet", str(tmp_path)], check=True, capture_output=True, timeout=15)
    forbidden = ["reports/testes.md", "reports/plano-aws.md", "perguntas-publicas.json",
                 "perguntas-publicas.md", "base-completa.md", "base-de-conhecimento/fonte.md",
                 "base-de-conhecimento-adicional/aula.md", "diretrizes-do-assistente.md",
                 "AGENTS.md", "docs/06-AWS-E-CUSTOS.md", "slides.pptx", ".env",
                 "src/.env.production", "src/runtime.log", "tests/chave.pem",
                 "src/credentials.json", ".aws/credentials", ".venv/pyvenv.cfg",
                 "src/__pycache__/cli.pyc", "data/rascunho.json"]
    result = subprocess.run(["git", "-C", str(tmp_path), "check-ignore", "--no-index", *forbidden],
                            capture_output=True, text=True, timeout=15)
    assert result.returncode == 0
    assert set(result.stdout.splitlines()) == set(forbidden)
    allowed = ["src/cli.py", "tests/test_base.py", "data/base.json", "requirements.txt",
               "template.yaml", "README.md", ".env.example", ".gitignore"]
    result = subprocess.run(["git", "-C", str(tmp_path), "check-ignore", "--no-index", *allowed],
                            capture_output=True, text=True, timeout=15)
    assert result.returncode == 1
    assert not result.stdout
