"""Único serviço de resposta compartilhável entre CLI e futuro Telegram."""

from dataclasses import dataclass
import re
from .config import Settings
from .knowledge import load_base, normalize
from .llm import BedrockGenerator, Generation, Generator
from .policies import ERROR, Status, supported_answer, triage, forwarding
from .retriever import Retriever
from .concierge import wants_overview, wants_advice, question_text
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
            return Answer(forwarding(question), "NAO_CONSTA", stage="busca")
        context = tuple(hit.unit for hit in hits)
        return self._generate(question,context)

    def explicar(self, source_id: str) -> Answer:
        """Seleção estruturada pelo menu: evidência validada, mesmo gerador e validador."""
        from .knowledge import SOURCES, OWNER_SOURCE
        unit = next((u for u in self.retriever.units if u['id']==source_id
                     and u['fonte'] in {*SOURCES,OWNER_SOURCE}),None)
        if unit is None:
            return Answer(forwarding(''),'NAO_CONSTA',stage='busca')
        if unit['secao']=='Panorama da arena':
            return self.responder('/informe')
        context=[unit]
        if unit['fonte']=='03-reservas-e-cancelamento.md' and unit['secao']=='Como reservar':
            context.extend(u for u in self.retriever.units if u['fonte']==OWNER_SOURCE
                           and u['secao']=='Nova reserva com antecedência mínima')
        question=(f"Na Arena Vila Nova, o que está confirmado sobre {unit['secao']} do assunto {unit['titulo']}? "
                  "Apresente os fatos do trecho, incluindo as opções por modalidade quando existirem. "
                  "Se algum detalhe não está confirmado, diferencie-o dos fatos conhecidos; não invente esse detalhe.")
        if unit['secao']=='Nova reserva com antecedência mínima':
            question='Qual é a antecedência mínima atual para pedir uma nova reserva e por quais canais? Resuma em palavras próprias.'
        return self._generate(question,tuple(context),check_coverage=False)

    def _generate(self, question: str, context: tuple, *, check_coverage: bool = True) -> Answer:
        try:
            result = self.generator.generate(question=question, context=context)
        except Exception:
            # Limite da aplicação: fallback acionável, sem detalhes ou payloads.
            return Answer(ERROR, "ERRO", stage="geracao")
        if not isinstance(result, Generation) or result.status != "RESPONDER" or not isinstance(result.answer,str):
            return Answer(forwarding(question), "NAO_CONSTA", stage="validacao")
        if re.search(r'base de (?:conhecimento|dados)|\b(?:na|nossa|minha) base\b|nao (?:tenho|temos|encontrei|localizei).{0,60}(?:inform|base)',
                     normalize(result.answer)):
            return Answer(forwarding(question),'NAO_CONSTA',stage='apresentacao')
        available = {unit["id"]: unit for unit in context}
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
