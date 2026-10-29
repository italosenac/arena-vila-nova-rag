"""Contrato do SDK e CLI com clientes falsos; nenhuma inferência real."""

import json
from pathlib import Path
import sys
from unittest.mock import Mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def context():
    from src.knowledge import load_base
    return tuple(u for u in load_base() if u["secao"] == "Sinal")


def sdk_response(text, stop="end_turn"):
    return {"stopReason": stop, "output": {"message": {"content": [{"text": text}]}}}


def test_converse_contract():
    from src.config import Settings
    from src.llm import BedrockGenerator
    units = context()
    client = Mock()
    client.converse.return_value = sdk_response(json.dumps({
        "answer": "O sinal é de 30%.", "source_ids": [units[0]["id"]], "status": "RESPONDER"}))
    result = BedrockGenerator(Settings(model_id="modelo-ficticio"), client=client).generate(
        question="Qual o sinal?", context=units)
    assert result.answer == "O sinal é de 30%."
    client.converse.assert_called_once()
    kwargs = client.converse.call_args.kwargs
    assert kwargs["modelId"] == "modelo-ficticio"
    assert 0 < kwargs["inferenceConfig"]["maxTokens"] <= 250
    assert kwargs["inferenceConfig"]["temperature"] <= 0.2
    assert "toolConfig" not in kwargs
    assert units[0]["texto"] not in kwargs["system"][0]["text"]
    prompt = json.loads(kwargs["messages"][0]["content"][0]["text"])
    assert len(prompt["trechos_nao_confiaveis"]) == len(units)
    assert prompt["trechos_nao_confiaveis"][0]["id"] == units[0]["id"]


@pytest.mark.parametrize("raw", ["texto sem JSON", '{"answer":"x"}',
                                 '{"answer":"x","source_ids":[12],"status":"RESPONDER"}'])
def test_malformed_generation(raw):
    from src.config import Settings
    from src.llm import BedrockGenerator
    client = Mock()
    client.converse.return_value = sdk_response(raw)
    with pytest.raises(ValueError):
        BedrockGenerator(Settings(model_id="ficticio"), client=client).generate(question="Qual o sinal?", context=context())


def test_truncation_is_not_accepted():
    from src.config import Settings
    from src.llm import BedrockGenerator
    client = Mock()
    client.converse.return_value = sdk_response('{}', stop="max_tokens")
    with pytest.raises(ValueError):
        BedrockGenerator(Settings(model_id="ficticio"), client=client).generate(question="Qual o sinal?", context=context())


def test_missing_model_never_creates_client(monkeypatch):
    from src.config import Settings
    from src.llm import BedrockGenerator, ModelUnavailable
    import boto3
    session = Mock()
    monkeypatch.setattr(boto3, "Session", session)
    with pytest.raises(ModelUnavailable):
        BedrockGenerator(Settings()).generate(question="Qual o sinal?", context=context())
    session.assert_not_called()


def test_missing_credentials_never_invokes(monkeypatch):
    from src.config import Settings
    from src.llm import BedrockGenerator, ModelUnavailable
    import boto3
    session = Mock()
    session.get_credentials.return_value = None
    monkeypatch.setattr(boto3, "Session", Mock(return_value=session))
    with pytest.raises(ModelUnavailable):
        BedrockGenerator(Settings(model_id="ficticio")).generate(question="Qual o sinal?", context=context())
    session.client.assert_not_called()


def test_sdk_region_timeouts_and_no_retry(monkeypatch):
    from src.config import Settings
    from src.llm import BedrockGenerator
    import boto3
    session = Mock()
    factory = Mock(return_value=session)
    monkeypatch.setattr(boto3, "Session", factory)
    generator = BedrockGenerator(Settings(model_id="ficticio"))
    assert generator._get_client() is generator._get_client()
    factory.assert_called_once_with(region_name="sa-east-1")
    session.client.assert_called_once()
    config = session.client.call_args.kwargs["config"]
    assert config.connect_timeout == 3 and config.read_timeout == 12
    assert config.retries["total_max_attempts"] == 1


@pytest.mark.parametrize("kwargs", [
    {"max_tokens": 251}, {"max_tokens": 0}, {"threshold": float("nan")},
    {"top_k": 10}, {"read_timeout": 100},
])
def test_invalid_settings(kwargs):
    from src.config import Settings
    with pytest.raises(ValueError):
        Settings(**kwargs)


def test_cli_mocked_response(monkeypatch, capsys):
    from src.cli import main
    from src.service import Answer
    service = Mock()
    service.responder.return_value = Answer("Resposta mockada explicitamente.", "RESPONDER")
    entries = iter(["", "Qual o sinal?", "sair"])
    monkeypatch.setattr("builtins.input", lambda _: next(entries))
    assert main([], factory=lambda: service) == 0
    assert "Resposta mockada" in capsys.readouterr().out
    service.responder.assert_called_once_with("Qual o sinal?")


def test_cli_missing_model_is_honest(capsys):
    from src.cli import main
    from src.config import Settings
    from src.service import build_service
    assert main(["--question", "Qual o sinal?"], factory=lambda: build_service(Settings())) == 1
    output = capsys.readouterr().out
    assert "indisponível" in output and "--retrieve" in output
    assert "30%" not in output


def test_cli_local_retrieval_does_not_generate(capsys):
    from src.cli import main
    from src.config import Settings
    from src.service import build_service
    generator = Mock()
    assert main(["--retrieve", "--question", "Qual o sinal?"],
                factory=lambda: build_service(Settings(), generator)) == 0
    assert "sem geração" in capsys.readouterr().out
    generator.generate.assert_not_called()


@pytest.mark.parametrize("exception", [EOFError, KeyboardInterrupt])
def test_cli_exit(monkeypatch, exception):
    from src.cli import main
    def end(_):
        raise exception
    monkeypatch.setattr("builtins.input", end)
    assert main([], factory=Mock()) == 0
