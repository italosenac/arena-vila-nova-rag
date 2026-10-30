"""O cliente escolhe reserva ou consulta antes das opções gerais."""
import json
from unittest.mock import Mock
from src.webhook import handle_event

SECRET='s'*40

def call(update, service):
    event={'rawPath':'/telegram','requestContext':{'http':{'method':'POST'}},
        'headers':{'content-type':'application/json','x-telegram-bot-api-secret-token':SECRET},
        'body':json.dumps({'update_id':1,**update})}
    result=handle_event(event,secret_provider=lambda:SECRET,service_factory=lambda:service)
    assert result['statusCode']==200
    return json.loads(result['body'])

def message(text,service):
    return call({'message':{'chat':{'id':1,'type':'private'},'text':text}},service)

def click(body,index,service):
    return call({'callback_query':{'id':'f','data':body['reply_markup']['inline_keyboard'][index][0]['callback_data'],
        'from':{'id':1},'message':{'message_id':10,'chat':{'id':1,'type':'private'}}}},service)

def test_start_and_help_prioritize_two_primary_paths():
    service=Mock()
    for text in ('/start','Me ajude'):
        body=message(text,service)
        assert len(body['reply_markup']['inline_keyboard'])==2
        assert 'reservar' in body['text'].lower()
        assert 'dados' in body['text'] and 'bilola' in body['text']
    service.responder.assert_not_called()

def test_reservation_intent_never_dumps_general_topics():
    service=Mock()
    body=message('Quero reservar uma quadra',service)
    assert 'Menu de reservas' in body['text']
    labels=[r[0]['text'] for r in body['reply_markup']['inline_keyboard']]
    assert 'Nova reserva' in labels and 'Consultar horários' in labels
    assert not any('LGPD' in label for label in labels)
    service.responder.assert_not_called()

def test_declining_reservation_enters_availability_questions():
    body=message('Não quero reservar',Mock())
    assert 'modalidade' in body['text'].lower()
    assert len(body['reply_markup']['inline_keyboard'])==5

def test_availability_collects_preferences_and_requests_confirmation_without_inventing_slots():
    service=Mock()
    body=message('Quero consultar horários disponíveis',service)
    for index in (2,1,2):
        body=click(body,index,service)
    assert 'vôlei de praia' in body['text'] and 'amanhã' in body['text'] and 'noite' in body['text']
    assert 'confirmar' in body['text'].lower() and 'arenavilanova.example/reservas' in body['text']
    assert 'disponível às' not in body['text'] and 'na base' not in body['text']
    service.responder.assert_not_called()

def test_other_options_only_appear_when_requested():
    body=message('Não é isso que eu quero',Mock())
    assert len(body['reply_markup']['inline_keyboard'])==10

def test_declining_availability_offers_other_topics():
    body=message('Não quero consultar horários',Mock())
    assert len(body['reply_markup']['inline_keyboard'])==10

def test_reservation_errors_are_friendly_and_do_not_expose_details():
    service=Mock()
    service.explicar.side_effect=RuntimeError('DETALHE_INTERNO_FICTICIO')
    body=click(message('Quero reservar',service),0,service)
    assert 'DETALHE_INTERNO' not in body['text'] and 'recepção' in body['text']

def test_flow_button_is_bound_to_chat_and_short_enough():
    from src.flows import decode_flow
    import pytest
    body=message('/start',Mock())
    data=body['reply_markup']['inline_keyboard'][0][0]['callback_data']
    assert len(data.encode())<=64 and decode_flow(data,1,SECRET)=='r'
    with pytest.raises(ValueError):
        decode_flow(data,2,SECRET)

def test_specific_question_after_declining_is_answered_without_forcing_other_menus():
    from src.service import Answer
    service=Mock()
    service.responder.return_value=Answer('Futsal custa R$ 120 até 17h em dias úteis.','RESPONDER')
    question='Não quero reservar, só saber o preço por hora'
    body=message(question,service)
    service.responder.assert_called_once_with(question)
    assert 'R$ 120' in body['text'] and 'Menu de reservas' not in body['text']
