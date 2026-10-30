"""Relatório local opt-in gerado dos resultados reais do pytest."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
import platform
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
ROWS = {}


def pytest_addoption(parser):
    parser.addoption("--arena-report", default=None, help="Gravar relatório local de avaliação")


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    if report.when != "call":
        return
    row = getattr(item, "arena_record", None)
    if row is not None:
        row["result"] = "PASSOU" if report.passed else "FALHOU" if report.failed else "NÃO EXECUTADO"
        ROWS[row["id"]] = row


def pytest_sessionfinish(session, exitstatus):
    target = session.config.getoption("--arena-report")
    if not target:
        return
    now = datetime.now(timezone(timedelta(hours=-3))).isoformat(timespec="seconds")
    passed = sum(row["result"] == "PASSOU" for row in ROWS.values())
    failed = sum(row["result"] == "FALHOU" for row in ROWS.values())
    path = Path(target)
    previous = path.read_text(encoding="utf-8") if path.is_file() else ""
    history = previous.partition("## Histórico das correções desta etapa")[2].strip()
    lines = ["# Testes — Arena Vila Nova", "", f"Execução: {now} · Python {platform.python_version()} · pytest {pytest.__version__}.",
             "", "Ambiente: MOCK. Recuperação real em data/base.json; gerador e cliente Bedrock falsos. Nenhuma inferência AWS real.",
             "As respostas factuais do mock são oráculos de teste e só são devolvidas após conferir evidência recuperada. Não medem qualidade de um LLM.",
             "", f"Resultado da avaliação: {passed} passaram; {failed} falharam; {len(ROWS)} casos registrados. Código de saída pytest: {exitstatus}.",
             "", "manter_regras corresponde a BLOQUEADO; responder_* a RESPONDER; nao_consta a NAO_CONSTA; recusar a FORA_ESCOPO.",
             "", "| ID | Pergunta sintética | Esperado | Obtido | Fonte recuperada | Resposta resumida | Resultado | Etapa da falha | Ambiente |",
             "|---|---|---|---|---|---|---|---|---|"]

    def clean(value):
        return str(value).replace("|", "\\|").replace("\n", " ")

    for row in sorted(ROWS.values(), key=lambda r: (not r["id"].startswith("P"), r["id"])):
        lines.append("| " + " | ".join(clean(value) for value in (
            row["id"], row["question"], row["expectation"],
            row["obtained"], "; ".join(row["sources"]) or "nenhuma",
            row["answer"][:450], row["result"], row["stage"], "mock")) + " |")
    lines += ["", "## IDs e diagnóstico", ""]
    for row in sorted(ROWS.values(), key=lambda r: r["id"]):
        lines.append(f"- {row['id']}: {', '.join(row['ids']) or 'nenhum ID'}; {row['detail']}")
    lines += ["", "## Limites deste relatório", "",
              "- Esta execução mede somente os testes com mocks e recuperação local.",
              "- Bedrock real, implantação, clone e entrega no aplicativo exigem evidências separadas; este relatório não determina seu estado.",
              "- Relatório e dataset original são exclusivamente locais.", ""]
    if history:
        lines += ["## Histórico das correções desta etapa", "", history, ""]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")
