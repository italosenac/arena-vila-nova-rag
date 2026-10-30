"""Único serviço de resposta compartilhado entre CLI e Telegram."""

from dataclasses import dataclass
import re
from .config import Settings
from .knowledge import load_base, normalize
from .llm import BedrockGenerator, Generation, Generator
from .policies import ERROR, Status, supported_answer, triage, forwarding
from .retriever import Retriever
from .conversation import clarify
from .language import question_parts


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
        decision = triage(question)
        parts = question_parts(question)
        # Entrada inteira passa primeiro pelas defesas, inclusive nas perguntas mistas.
        if len(parts) > 1 and (decision is None or decision[0] != 'BLOQUEADO'):
            supported_parts = [part for part in parts if triage(part) is None]
            if supported_parts and len(supported_parts) < len(parts):
                result = self.responder('; '.join(supported_parts))
                if result.status == 'RESPONDER' and result.source_ids:
                    return Answer(result.text + ' Sobre a outra parte da pergunta, '
                                  'a recepção pode orientar pelo (99) 9999-0100.',
                                  result.status, result.source_ids, result.sources, 'parcial')
                return result
        if decision:
            return Answer(decision[1], decision[0], stage="triagem")
        guidance = clarify(question)
        if guidance:
            return Answer(guidance.text, "RESPONDER", stage="esclarecimento")
        try:
            hits = self.retriever.search(question)
        except Exception:
            return Answer(ERROR, "ERRO", stage="busca")
        if not hits:
            return Answer(forwarding(question), "NAO_CONSTA", stage="busca")
        context = tuple(hit.unit for hit in hits)
        return self._generate(question,context)

    def _generate(self, question: str, context: tuple, *, check_coverage: bool = True) -> Answer:
        try:
            result = self.generator.generate(question=question, context=context)
        except Exception:
            # Limite da aplicação: fallback acionável, sem detalhes ou payloads.
            return Answer(ERROR, "ERRO", stage="geracao")
        if not isinstance(result, Generation) or result.status != "RESPONDER" or not isinstance(result.answer,str):
            return Answer(forwarding(question), "NAO_CONSTA", stage="validacao")
        available = {unit["id"]: unit for unit in context}
        if (any(source_id in result.answer for source_id in available)
                or re.search(r'base de conhecimento|documentos? brutos?|ids? internos?', normalize(result.answer))):
            return Answer(forwarding(question), 'NAO_CONSTA', stage='apresentacao')
        ids = result.source_ids
        if (not isinstance(ids, tuple) or not ids or not all(isinstance(value, str) for value in ids)
                or len(ids) != len(set(ids)) or any(value not in available for value in ids)):
            return Answer(forwarding(question), "NAO_CONSTA", stage="validacao")
        cited = tuple(available[value] for value in ids)
        if check_coverage and len(question_parts(question))>1:
            for part in question_parts(question):
                hits=self.retriever.search(part)
                relevant={h.unit['id'] for h in hits if h.score>=hits[0].score*0.8
                          and h.unit['id'] in available} if hits else set()
                if not relevant or not relevant.intersection(ids):
                    return Answer(forwarding(question),'NAO_CONSTA',stage='cobertura')
        if not supported_answer(result.answer, cited, question=question):
            return Answer(forwarding(question), "NAO_CONSTA", stage="validacao")
        return Answer(result.answer, "RESPONDER", ids,
                      tuple(dict.fromkeys(unit["fonte"] for unit in cited)))


def build_service(settings: Settings | None = None, generator: Generator | None = None) -> Assistant:
    settings = settings or Settings.from_env()
    return Assistant(Retriever(load_base(), top_k=settings.top_k, threshold=settings.threshold),
                     generator if generator is not None else BedrockGenerator(settings))
