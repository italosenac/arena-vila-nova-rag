"""Relógio injetável e encaminhamento útil, sem inventar fatos comerciais."""
from datetime import datetime, timezone
import pytest

@pytest.mark.parametrize('hour,expected',[(3,'madrugada'),(8,'manhã'),(15,'tarde'),(23,'noite')])
def test_greeting_uses_sao_paulo_instead_of_server_clock(hour,expected):
    from src.tone import time_band
    assert time_band(datetime(2026,10,30,hour,0,tzinfo=timezone.utc))==expected

def test_greeting_boundaries_and_unchanged_factual_body():
    from src.webhook import present_answer
    for hour,expected in [(7,'madrugada'),(8,'manhã'),(14,'manhã'),(15,'tarde'),(20,'tarde'),(21,'noite')]:
        now=datetime(2026,10,30,hour,0,tzinfo=timezone.utc)
        from src.tone import time_band
        assert time_band(now)==expected
        answer=present_answer('O sinal é de 30%.',now=now)
        assert answer.endswith('O sinal é de 30%.') and 'bilola' in answer
    with pytest.raises(ValueError):
        time_band(datetime(2026,10,30,12))

def test_time_prefix_is_applied_once_to_questionnaires():
    from src.webhook import response
    import json
    text='Vamos bilolar! Qual modalidade você prefere?'
    first=json.loads(response(200,{'method':'sendMessage','text':text})['body'])['text']
    second=json.loads(response(200,{'method':'editMessageText','text':first})['body'])['text']
    assert first==second and first.endswith(text)

@pytest.mark.parametrize('question',['Tem estacionamento?','Tem vaga para amanhã?', 'Qual a marca dos refletores?'])
def test_unknown_details_offer_next_steps_without_exposing_internal_base(question):
    from src.service import build_service
    from src.llm import Generation
    class Generator:
        def generate(self,**kwargs):
            return Generation('',(),'NAO_CONSTA')
    answer=build_service(generator=Generator()).responder(question)
    assert 'não tenho' not in answer.text.lower()
    assert 'na base' not in answer.text.lower() and 'evidência' not in answer.text.lower()
    assert 'recepção' in answer.text.lower() or '/aconselhe' in answer.text

def test_parking_forward_does_not_assert_parking_exists():
    from src.policies import forwarding
    assert 'se há estacionamento' in forwarding('Tem estacionamento?')

def test_model_internal_language_is_replaced_with_actionable_guidance():
    from src.service import build_service
    from src.llm import Generation
    class Generator:
        def generate(self,*,question,context):
            return Generation('Não tenho essa informação na base. O sinal é de 30%.',
                (next(u['id'] for u in context if u['secao']=='Sinal'),),'RESPONDER')
    answer=build_service(generator=Generator()).responder('Qual o sinal para reservar?')
    assert answer.stage=='apresentacao' and 'na base' not in answer.text
    assert 'recepção' in answer.text
