"""Único serviço de resposta compartilhável entre CLI e futuro Telegram."""

from dataclasses import dataclass
from .config import Settings
from .knowledge import load_base
from .llm import BedrockGenerator, Generation, Generator
from .policies import ERROR, NO_DATA, Status, supported_answer, triage
from .retriever import Retriever
from .concierge import wants_overview, wants_advice, question_text


@dataclass(frozen=True)
class Answer:
    text: str
    status: Status
    source_ids: tuple[str, ...] = ()
    sources: tuple[str, ...] = ()
    stage: str = "nenhuma"


class Assistant:
    def __init__(self, retriever: Retriever, generator: Generator):
        self.retriever, self.generator = retriever, generator

    def responder(self, question: str) -> Answer:
        if wants_overview(question):
            panorama = next((u for u in self.retriever.units if u['fonte'] == '10-atualizacao-da-recepcao.md'
                             and u['secao'] == 'Panorama da arena'), None)
            if panorama:
                return Answer(panorama['texto'], 'RESPONDER', (panorama['id'],), (panorama['fonte'],), 'panorama')
        if wants_advice(question):
            return Answer(question_text(())+' Na CLI, responda às opções numeradas do questionário interativo.',
                          'RESPONDER',stage='questionario')
        decision = triage(question)
        if decision:
            return Answer(decision[1], decision[0], stage="triagem")
        try:
            hits = self.retriever.search(question)
        except Exception:
            return Answer(ERROR, "ERRO", stage="busca")
        if not hits:
            return Answer(NO_DATA, "NAO_CONSTA", stage="busca")
        context = tuple(hit.unit for hit in hits)
        try:
            result = self.generator.generate(question=question, context=context)
        except Exception:
            # Limite da aplicação: fallback acionável, sem detalhes ou payloads.
            return Answer(ERROR, "ERRO", stage="geracao")
        if not isinstance(result, Generation) or result.status != "RESPONDER":
            return Answer(NO_DATA, "NAO_CONSTA", stage="validacao")
        available = {unit["id"]: unit for unit in context}
        ids = result.source_ids
        if (not isinstance(ids, tuple) or not ids or not all(isinstance(value, str) for value in ids)
                or len(ids) != len(set(ids)) or any(value not in available for value in ids)):
            return Answer(NO_DATA, "NAO_CONSTA", stage="validacao")
        cited = tuple(available[value] for value in ids)
        if not supported_answer(result.answer, cited, question=question):
            return Answer(NO_DATA, "NAO_CONSTA", stage="validacao")
        return Answer(result.answer, "RESPONDER", ids,
                      tuple(dict.fromkeys(unit["fonte"] for unit in cited)))


def build_service(settings: Settings | None = None, generator: Generator | None = None) -> Assistant:
    settings = settings or Settings.from_env()
    return Assistant(Retriever(load_base(), top_k=settings.top_k, threshold=settings.threshold),
                     generator if generator is not None else BedrockGenerator(settings))
