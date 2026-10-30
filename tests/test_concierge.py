"""Questionário de preferências: sem cadastro ou histórico persistido."""
import pytest
from src.concierge import QUESTIONS, decode_choice, keyboard, recommendation_question
from src.service import build_service
from src.concierge import MATRIX_AXES, MATRIX_SHAPE


def test_five_questions_and_bound_signed_choices():
    assert len(QUESTIONS) == 5
    assert MATRIX_SHAPE == (5,5,5,5,5)
    assert len(MATRIX_AXES) == 5
    data = keyboard((), 123, 's'*40, now=100)['inline_keyboard'][0][0]['callback_data']
    assert len(data.encode()) <= 64
    assert decode_choice(data, 123, 's'*40, now=101) == (0,)
    for chat, secret, when in [(124,'s'*40,101),(123,'x'*40,101),(123,'s'*40,4000)]:
        with pytest.raises(ValueError):
            decode_choice(data, chat, secret, now=when)
    with pytest.raises(ValueError):
        decode_choice(data[:-1]+'z',123,'s'*40,now=101)


def test_questionnaire_contains_only_sport_preferences():
    text = recommendation_question((0,1,2,3,0))
    assert 'futsal' in text and 'quatro pessoas' in text
    assert not any(word in text.lower() for word in ('cpf','senha','cartão','nome completo'))
    assert len({recommendation_question((a,b,c,d,e)) for a in range(5) for b in range(5)
                for c in range(5) for d in range(5) for e in range(5)}) == 3125


def test_informe_is_complete_without_model():
    class NoModel:
        def generate(self, **kwargs):
            raise AssertionError('Panorama não precisa invocar modelo')
    answer = build_service(generator=NoModel()).responder('Me informe')
    assert answer.status == 'RESPONDER'
    assert all(f in answer.text for f in ('30%', '24 horas', '12 horas', '30 minutos'))
    assert answer.source_ids and '10-atualizacao-da-recepcao.md' in answer.sources
    assert len(answer.text) < 3950
    assert all(f in answer.text for f in ('mensalista','LGPD','campeonato','Pagamento'))


def test_webhook_questionnaire_entire_flow_without_history():
    import json
    from unittest.mock import Mock
    from src.webhook import handle_event
    from src.service import Answer
    secret='s'*40
    service=Mock()
    service.responder.return_value=Answer('Combine o grupo e consulte a recepção para reservar.','RESPONDER')
    event={'rawPath':'/telegram','requestContext':{'http':{'method':'POST'}},
           'headers':{'content-type':'application/json','x-telegram-bot-api-secret-token':secret}}
    event['body']=json.dumps({'update_id':1,'message':{'chat':{'id':1,'type':'private'},'text':'Me aconselhe'}})
    def call():
        result=handle_event(event,secret_provider=lambda:secret,service_factory=lambda:service)
        assert result['statusCode']==200
        return json.loads(result['body'])
    body=call()
    service.responder.assert_not_called()
    for step in range(5):
        assert f'Pergunta {step+1} de 5' in body['text']
        assert len(body['reply_markup']['inline_keyboard'])==5
        data=body['reply_markup']['inline_keyboard'][step][0]['callback_data']
        event['body']=json.dumps({'update_id':step+2,'callback_query':{'id':str(step),
            'from':{'id':1,'is_bot':False},'data':data,'message':{
                'message_id':10,'chat':{'id':1,'type':'private'}}}})
        body=call()
        assert body['method']=='editMessageText'
    assert 'Seu perfil esportivo' in body['text'] and 'bilola' in body['text']
    service.responder.assert_called_once_with(recommendation_question((0,1,2,3,4)))
    assert body['reply_markup']['inline_keyboard']==[]
