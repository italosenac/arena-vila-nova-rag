"""Contrato HTTP/Telegram sem rede, segredos reais ou dados pessoais."""
import base64
import json
from unittest.mock import Mock

import pytest

from src.service import Answer


def event(text="Qual o sinal?", secret="segredo-ficticio-para-testes-123456"):
    return {"version":"2.0", "rawPath":"/telegram", "requestContext":{"http":{"method":"POST"}},
            "headers":{"content-type":"application/json", "x-telegram-bot-api-secret-token":secret},
            "body":json.dumps({"update_id":1,"message":{"chat":{"id":1,"type":"private"},"text":text}})}


def invoke(data, service=None, provider=None):
    from src.webhook import handle_event
    service = service or Mock()
    provider = provider or Mock(return_value="segredo-ficticio-para-testes-123456")
    return handle_event(data, secret_provider=provider, service_factory=lambda: service)


def test_auth_precedes_body_parse_and_model(caplog):
    service=Mock()
    data=event(secret="segredo-errado-para-testes-12345678")
    data["body"]="não é JSON"
    assert invoke(data, service)["statusCode"]==403
    service.responder.assert_not_called()
    assert not caplog.records


@pytest.mark.parametrize("command", ["/start", "/ajuda", "/start@ArenaFicticiaBot"])
def test_commands_inline_without_model(command):
    service=Mock()
    result=invoke(event(command),service)
    body=json.loads(result["body"])
    assert result["statusCode"]==200 and body["method"]=="sendMessage" and body["chat_id"]==1
    assert "Arena Vila Nova" in body["text"] and "dados" in body["text"]
    service.responder.assert_not_called()


def test_same_service_and_no_history(caplog):
    service=Mock()
    service.responder.return_value=Answer("O sinal é de 30%.","RESPONDER")
    result=invoke(event(),service)
    service.responder.assert_called_once_with("Qual o sinal?")
    text=json.loads(result["body"])["text"]
    assert "bilola" in text and text.endswith("O sinal é de 30%.")
    assert not caplog.records


@pytest.mark.parametrize("text",["/start","/ajuda","/outro",None,"Qual o sinal?"])
def test_every_telegram_message_has_requested_style(text):
    service=Mock()
    service.responder.return_value=Answer("Resposta de teste.","RESPONDER")
    data=event(text)
    body=json.loads(invoke(data,service)["body"])
    assert "bilola" in body["text"]


@pytest.mark.parametrize("mutation,code", [("method",405),("path",404),("headers",403),
    ("large",413),("json",400),("content",415),("array",400),("duplicate",400),
    ("group",200),("bot",200),("chat_id",400),("text_type",400)])
def test_unexpected_inputs_never_reach_model(mutation,code):
    data=event()
    body=json.loads(data["body"])
    if mutation=="method": data["requestContext"]["http"]["method"]="GET"
    elif mutation=="path": data["rawPath"]="/other"
    elif mutation=="headers": data["headers"]={}
    elif mutation=="large": data["body"]="x"*20000
    elif mutation=="json": data["body"]="{"
    elif mutation=="content": data["headers"]["content-type"]="text/plain"
    elif mutation=="array": data["body"]="[]"
    elif mutation=="duplicate": data["body"]='{"update_id":1,"update_id":2}'
    elif mutation=="group": body["message"]["chat"]["type"]="group"
    elif mutation=="bot": body["message"]["from"]={"is_bot":True}
    elif mutation=="chat_id": body["message"]["chat"]["id"]=True
    elif mutation=="text_type": body["message"]["text"]={"unsafe":"value"}
    if mutation in {"group","bot","chat_id","text_type"}: data["body"]=json.dumps(body)
    service=Mock()
    assert invoke(data,service)["statusCode"]==code
    service.responder.assert_not_called()


def test_base64_and_attachment():
    data=event("/ajuda")
    data["body"]=base64.b64encode(data["body"].encode()).decode()
    data["isBase64Encoded"]=True
    assert json.loads(invoke(data)["body"])["method"]=="sendMessage"
    data=event()
    body=json.loads(data["body"])
    del body["message"]["text"]
    data["body"]=json.dumps(body)
    assert "texto" in json.loads(invoke(data)["body"])["text"]


def test_secret_and_service_fail_closed_without_details(caplog):
    provider=Mock(side_effect=RuntimeError("DETALHE_FICTICIO"))
    assert invoke(event(),provider=provider)["statusCode"]==503
    service=Mock()
    service.responder.side_effect=RuntimeError("DETALHE_FICTICIO")
    result=invoke(event(),service)
    assert result["statusCode"]==200 and "DETALHE" not in result["body"]
    assert not caplog.records


def test_ssm_secure_string_cached(monkeypatch):
    from src import webhook
    monkeypatch.setenv("WEBHOOK_SECRET_PARAMETER","/arena-vila-nova/test-ficticio")
    client=Mock()
    client.get_parameter.return_value={"Parameter":{"Type":"SecureString","Value":"segredo-ficticio-para-testes-123456"}}
    provider=webhook.ParameterSecret(client=client)
    assert provider()==provider()
    client.get_parameter.assert_called_once_with(Name="/arena-vila-nova/test-ficticio",WithDecryption=True)
    client.get_parameter.return_value={"Parameter":{"Type":"String","Value":"invalido"}}
    with pytest.raises(ValueError): webhook.ParameterSecret(client=client)()
