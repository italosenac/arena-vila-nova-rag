"""Configuração com chamadas falsas; nenhum token real em testes."""
import pytest
from src.telegram_setup import configure, TelegramFailure


def test_registration_checks_identity_and_getwebhookinfo():
    calls=[]
    def call(token,method,payload):
        calls.append((method,payload))
        if method=="getMe": return {"is_bot":True,"username":"ArenaFicticiaBot"}
        if method=="getWebhookInfo": return {"url":"https://ficticio.execute-api.sa-east-1.amazonaws.com/telegram","pending_update_count":0}
        return True
    # Formato sintético gerado em memória, nunca credencial de serviço.
    token="1"*8+":"+"x"*35
    result=configure(token=token,url="https://ficticio.execute-api.sa-east-1.amazonaws.com/telegram",secret="s"*40,call=call)
    assert result["verified"] and result["username"]=="ArenaFicticiaBot"
    assert [c[0] for c in calls]==["getMe","setWebhook","getWebhookInfo","setMyCommands"]
    assert calls[1][1]["max_connections"]==1
    assert not calls[1][1]["drop_pending_updates"]
    assert token not in str(result) and "s"*40 not in str(result)


def test_missing_confirmation_is_failure():
    def call(token,method,payload):
        return {"is_bot":True,"username":"ArenaFicticiaBot"} if method=="getMe" else False
    with pytest.raises(TelegramFailure):
        configure(token="1"*8+":"+"x"*35,url="https://ficticio.execute-api.sa-east-1.amazonaws.com/telegram",secret="s"*40,call=call)
