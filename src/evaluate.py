"""Executa a avaliação pytest local; nunca importa ou chama o adaptador real."""

from pathlib import Path
import subprocess
import sys


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    if not (root / "perguntas-publicas.json").is_file():
        print("Avaliação pública indisponível: dataset original somente local. Execute pytest para os testes de produto.")
        return 1
    result = subprocess.run([sys.executable, "-m", "pytest", "tests/test_evaluation.py", "-q", "--tb=short",
                             "--arena-report", "reports/testes.md"], cwd=root, check=False)
    print("Relatório local: reports/testes.md. Ambiente MOCK, sem Bedrock real.")
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
