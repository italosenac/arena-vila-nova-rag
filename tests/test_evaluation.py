"""SPEC-04: dataset local, recuperação real, mock estrito e diagnóstico por caso."""

from pathlib import Path
from unittest.mock import Mock

import pytest

from evaluation_cases import ADVERSARIAL, load_public_cases
from src.knowledge import load_base, normalize
from src.llm import Generation
from src.policies import contains_sensitive
from src.retriever import Retriever
from src.service import Assistant


ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "perguntas-publicas.json"
PUBLIC = load_public_cases(DATASET) if DATASET.is_file() else []


class ObservedRetriever:
    def __init__(self, retriever):
        self.retriever = retriever
        self.hits = []

    def search(self, question):
        self.hits = self.retriever.search(question)
        return self.hits


@pytest.fixture(scope="module")
def retriever():
    return Retriever(load_base())


def exercise(case, retriever, request):
    safe_question = "[entrada sintética sensível omitida]" if contains_sensitive(case.question) else case.question
    row = {"id": case.id, "question": safe_question, "category": case.category,
           "expected": case.expected, "obtained": "não executado", "sources": [], "ids": [],
           "answer": "", "stage": "base", "detail": "teste interrompido antes da resposta"}
    row["expectation"] = case.category + " → " + case.expected
    if case.sources:
        row["expectation"] += "; fonte: " + ", ".join(case.sources) + " / " + case.section
    if case.facts:
        row["expectation"] += "; evidência: " + ", ".join(case.facts)
    if case.mode != "normal":
        row["expectation"] += "; rejeitar saída mockada " + case.mode
    request.node.arena_record = row
    base = load_base()
    if case.section:
        candidates = [u for u in base if Path(u["fonte"]).stem in case.sources and u["secao"] == case.section]
        row["detail"] = "seção ou fatos esperados ausentes da base"
        if not candidates and any(Path(u["fonte"]).stem in case.sources for u in base):
            row["stage"] = "chunk"
        assert candidates
        assert all(normalize(fact) in normalize(" ".join(u["texto"] for u in candidates)) for fact in case.facts)
    observed = ObservedRetriever(retriever)
    generator = Mock()
    mock_issue = {}

    def generate(*, question, context):
        if len(context) > retriever.top_k or any(u["status"] != "vigente" for u in context):
            mock_issue["stage"] = "prompt"
            raise AssertionError("Contexto não segue o contrato")
        selected = [u for u in context if Path(u["fonte"]).stem in case.sources and u["secao"] == case.section]
        if not selected or not all(normalize(f) in normalize(" ".join(u["texto"] for u in selected)) for f in case.facts):
            mock_issue["stage"] = "busca"
            raise AssertionError("A busca não entregou a evidência necessária")
        ids = tuple(u["id"] for u in selected)
        return Generation(case.reply, ("ID_FORJADO" if case.mode == "forged" else ids[0],), "RESPONDER")

    generator.generate.side_effect = generate
    result = Assistant(observed, generator).responder(case.question)
    row.update(obtained=result.status, answer=result.text,
               sources=[h.unit["fonte"] + " / " + h.unit["secao"] for h in observed.hits],
               ids=[h.unit["id"] for h in observed.hits])
    row["stage"] = mock_issue.get("stage", "geração" if generator.generate.called else "recusa")
    row["detail"] = f"estado esperado {case.expected}; obtido {result.status}"
    assert result.status == case.expected
    if case.section:
        row["stage"] = "busca"
        assert any(Path(h.unit["fonte"]).stem in case.sources and h.unit["secao"] == case.section for h in observed.hits)
        generator.generate.assert_called_once()
    else:
        row["stage"] = "recusa"
        generator.generate.assert_not_called()
    if case.expected == "RESPONDER":
        row["stage"] = "geração"
        assert all(normalize(f) in normalize(result.text) for f in case.facts)
        assert set(result.source_ids) <= {h.unit["id"] for h in observed.hits}
        assert {Path(source).stem for source in result.sources}.intersection(case.sources)
    if case.mode in {"unsafe", "forged"}:
        assert result.stage == "validacao"
        assert result.text != case.reply
    assert 0 < len(result.text) <= 900
    assert "ARENA50" not in result.text
    if case.id in {"A06", "A07"}:
        assert "DADO SINTÉTICO" not in result.text
    detail = ("saída mockada adversarial rejeitada apesar de evidência recuperada" if case.mode != "normal"
              else "contrato de comportamento, fonte e segurança verificado com mock")
    row.update(stage="nenhuma", detail=detail)


@pytest.mark.parametrize("case", PUBLIC or [pytest.param(None, marks=pytest.mark.skip(reason="Dataset público original disponível somente no ambiente local"))],
                         ids=[c.id for c in PUBLIC] if PUBLIC else ["dataset-local-ausente"])
def test_public(case, retriever, request, caplog):
    exercise(case, retriever, request)
    assert not caplog.records


@pytest.mark.parametrize("case", ADVERSARIAL, ids=[c.id for c in ADVERSARIAL])
def test_adversarial(case, retriever, request, caplog):
    exercise(case, retriever, request)
    assert not caplog.records
