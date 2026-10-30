"""Novos contratos de estrutura, esportes e orientação, independentes de rede."""
from src.knowledge import load_base
from src.retriever import Retriever


def test_five_hundred_reviewed_conversation_scenarios():
    rows=[u for u in load_base() if u['fonte']=='11-guia-de-convivencia.md' and u['secao'].startswith('Cenário ')]
    assert len(rows)==2560 and len({u['texto'] for u in rows})==len(rows)
    assert all(u['area']=='conversa' and u['status']=='vigente' for u in rows)


def test_reception_updates_do_not_replace_cancellation():
    base=load_base()
    owner=[u for u in base if u['fonte']=='10-atualizacao-da-recepcao.md']
    assert any('30 minutos de antecedência' in u['texto'] for u in owner)
    assert any('grama sintética' in u['texto'] for u in owner)
    assert any('geladeira' in u['texto'] for u in owner)
    cancel=next(u for u in base if u['fonte']=='03-reservas-e-cancelamento.md' and u['secao']=='Cancelamento')
    assert '24 horas' in cancel['texto'] and '30 minutos' not in cancel['texto']
    booking=next(u for u in base if u['fonte']=='03-reservas-e-cancelamento.md' and u['secao']=='Como reservar')
    assert 'no mínimo 2 horas' not in booking['texto']


def test_sports_evidence_never_answers_arena_prices():
    r=Retriever(load_base())
    sport=r.search('Quantos jogadores tem uma dupla no vôlei de praia oficial?')
    assert sport and any(h.unit['area']=='esporte' for h in sport)
    prices=r.search('Quanto custa futsal quarta às 19h?')
    assert prices and all(h.unit['area']!='esporte' for h in prices)
    assert any(h.unit['secao']=='Tabela de preços por hora' for h in prices)
