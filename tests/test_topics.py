"""Perguntas guiadas sobre todas as seções vigentes, sem depender dos Markdown."""
import pytest
from src.knowledge import SOURCES, load_base
from src.topics import catalogue, topic_buttons, decode_topic, topic_prompt


def test_questions_cover_every_valid_original_section():
    questions=catalogue()
    original={u['id'] for u in load_base() if u['fonte'] in SOURCES}
    assert original <= {q['unit']['id'] for q in questions}
    assert len(questions)==47
    assert all(q['question'].endswith('?') for q in questions)
    assert len({q['question'] for q in questions})==len(questions)
    assert not any('ARENA50' in q['question'] or '03b-' in q['unit']['fonte'] for q in questions)


def test_signed_topic_navigation_binds_chat_and_expires():
    buttons=topic_buttons(None,1,'s'*40,now=100)
    assert len(buttons['inline_keyboard'])==10
    choice=buttons['inline_keyboard'][0][0]['callback_data']
    assert decode_topic(choice,1,'s'*40,now=101)==(0,0)
    assert len(choice.encode())<=64
    with pytest.raises(ValueError):
        decode_topic(choice,2,'s'*40,now=101)
    with pytest.raises(ValueError):
        decode_topic(choice,1,'s'*40,now=2000)
    assert '?' in topic_prompt(0)


def test_selected_evidence_uses_same_model_validation():
    from src.service import build_service
    from src.llm import Generation
    class Generator:
        def generate(self, *, question,context):
            assert len(context)<=3
            return Generation('Use tênis ou calçado de solado liso no futsal. Chuteiras de trava são proibidas.',
                              (context[0]['id'],),'RESPONDER')
    service=build_service(generator=Generator())
    unit=next(u for u in load_base() if u['secao']=='Calçados')
    result=service.explicar(unit['id'])
    assert result.status=='RESPONDER' and unit['id'] in result.source_ids
    assert service.explicar('ID_FORJADO').status=='NAO_CONSTA'


def test_webhook_topic_navigation_selects_exact_evidence():
    import json
    from unittest.mock import Mock
    from src.webhook import handle_event
    from src.service import Answer
    secret='s'*40
    service=Mock()
    service.explicar.return_value=Answer('Use calçado de solado liso no futsal.','RESPONDER')
    event={'rawPath':'/telegram','requestContext':{'http':{'method':'POST'}},
           'headers':{'content-type':'application/json','x-telegram-bot-api-secret-token':secret}}
    event['body']=json.dumps({'update_id':1,'message':{'chat':{'id':1,'type':'private'},'text':'Me ajude'}})
    def call():
        result=handle_event(event,secret_provider=lambda:secret,service_factory=lambda:service)
        assert result['statusCode']==200
        return json.loads(result['body'])
    body=call()
    for index in (4,0):
        data=body['reply_markup']['inline_keyboard'][index][0]['callback_data']
        event['body']=json.dumps({'update_id':2,'callback_query':{'id':'q','data':data,
            'from':{'id':1},'message':{'message_id':10,'chat':{'id':1,'type':'private'}}}})
        body=call()
    assert 'solado liso' in body['text'] and 'bilola' in body['text']
    assert len(body['reply_markup']['inline_keyboard'])==10
    service.explicar.assert_called_once_with('05-regras-de-uso:calcados')


def test_all_questions_deliver_their_selected_evidence_to_generator():
    from src.service import build_service
    from src.llm import Generation
    from unittest.mock import Mock
    generator=Mock()
    generator.generate.return_value=Generation('',(),'NAO_CONSTA')
    service=build_service(generator=generator)
    for question in catalogue():
        unit=question['unit']
        service.explicar(unit['id'])
        context=generator.generate.call_args.kwargs['context']
        assert context[0]['id']==unit['id']
        assert all(u['status']=='vigente' for u in context)
        assert len(context)<=2
    assert generator.generate.call_count==47


def test_factual_validation_accepts_version_metadata_and_privacy_warnings():
    from src.policies import supported_answer
    base=load_base()
    intro=next(u for u in base if u['secao']=='Introdução')
    assert supported_answer('A versão 2.0 substitui a versão 1.0 a partir de 1º de agosto de 2026.',(intro,))
    privacy=next(u for u in base if u['secao']=='Atendimento pelo Telegram')
    assert supported_answer('Não envie CPF, dados de cartão nem senhas pelo Telegram.',(privacy,))
    assert not supported_answer('Envie CPF, dados de cartão e senhas pelo Telegram.',(privacy,))
