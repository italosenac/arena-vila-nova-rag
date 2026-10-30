"""A limpeza nunca executa antes da data nem aceita alvos do evento."""
import json
import pytest
from src.cleanup import lambda_handler


def test_cleanup_dry_run_and_not_due(monkeypatch):
    targets={"stack_name":"arena-vila-nova","bucket":"arena-vila-nova-artifacts-ficticio",
             "parameter":"/arena-vila-nova/webhook-secret","function":"arena-vila-nova-bot",
             "expires_at":"2999-01-01T00:00:00+00:00"}
    monkeypatch.setenv("ARENA_CLEANUP_TARGETS",json.dumps(targets))
    assert lambda_handler({"dry_run":True},None)["validated"]
    with pytest.raises(ValueError,match="ainda não"):
        lambda_handler({"stack_name":"outro"},None)


def test_cleanup_rejects_other_stack(monkeypatch):
    monkeypatch.setenv("ARENA_CLEANUP_TARGETS",json.dumps({"stack_name":"outro"}))
    with pytest.raises(AssertionError): lambda_handler({"dry_run":True},None)
