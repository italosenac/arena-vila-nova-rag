"""Regressões da correção definitiva e do adendo; sem rede."""
import json
from unittest.mock import Mock

from src.knowledge import load_base, SOURCES
from src.llm import Generation
from src.retriever import Retriever
from src.service import Assistant


def test_original_corpus_only():
    units = load_base()
    assert len(units) == 39
    assert {u['fonte'] for u in units} == set(SOURCES)
    booking = next(u for u in units if u['secao'] == 'Como reservar')
    assert 'no mínimo 2 horas' in booking['texto']


def test_runtime_has_no_removed_persona():
    from pathlib import Path
    stem = ''.join(map(chr, (98, 105, 108, 111, 108)))
    root = Path(__file__).resolve().parents[1]
    for path in [*root.joinpath('src').glob('*.py'), root/'data/base.json', root/'README.md']:
        assert stem not in path.read_text(encoding='utf-8').casefold(), path.name


def test_complete_question_uses_retrieval_and_model():
    retriever = Retriever(load_base())
    observed = Mock(wraps=retriever)
    unit = next(u for u in load_base() if u['secao'] == 'Sinal')
    model = Mock()
    model.generate.return_value = Generation('O sinal é de 30%.', (unit['id'],), 'RESPONDER')
    answer = Assistant(observed, model).responder('Qual é o percentual do sinal?')
    assert answer.status == 'RESPONDER'
    observed.search.assert_called_once()
    model.generate.assert_called_once()


def test_valid_citation_cannot_change_minimum_booking_notice():
    unit = next(u for u in load_base() if u['secao'] == 'Como reservar')
    from src.policies import supported_answer
    assert not supported_answer('É possível reservar com no mínimo 30 minutos de antecedência.', (unit,))

def test_internal_reference_never_appears_in_customer_reply():
    unit=next(u for u in load_base() if u['secao']=='Sinal')
    model=Mock()
    model.generate.return_value=Generation('O sinal é de 30%. '+unit['id'],(unit['id'],),'RESPONDER')
    result=Assistant(Retriever(load_base()),model).responder('Qual o sinal?')
    assert result.status=='NAO_CONSTA' and unit['id'] not in result.text

def test_rain_does_not_retrieve_monthly_replacement_for_single_booking():
    hits=Retriever(load_base()).search('E se chover no dia do meu jogo na areia?')
    assert hits and all(h.unit['fonte']!='06-planos-mensalistas.md' for h in hits)

def test_yes_cannot_confirm_wrong_cancellation_deadline():
    from src.policies import supported_answer
    unit=next(u for u in load_base() if u['secao']=='Cancelamento')
    assert not supported_answer('Sim, o cancelamento é gratuito até 24 horas antes.',
                                (unit,),question='Posso cancelar 12 horas antes sem custo?')

def test_distinct_clauses_can_explain_both_deadlines():
    from src.policies import supported_answer
    units=tuple(u for u in load_base() if u['secao'] in {'Cancelamento','Reagendamento'})
    text=('Não, o prazo de cancelamento gratuito é de até 24 horas antes do início. '
          'O prazo de 12 horas se aplica apenas ao reagendamento.')
    assert supported_answer(text,units)
