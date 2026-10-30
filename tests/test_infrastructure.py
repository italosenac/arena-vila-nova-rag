"""Inspeção offline das fronteiras de segurança do plano, sem chamadas AWS."""

import json
from pathlib import Path

import yaml


class TemplateLoader(yaml.SafeLoader):
    pass


def intrinsic(loader, tag, node):
    if isinstance(node, yaml.ScalarNode):
        value = loader.construct_scalar(node)
    elif isinstance(node, yaml.SequenceNode):
        value = loader.construct_sequence(node)
    else:
        value = loader.construct_mapping(node)
    return {tag: value}


TemplateLoader.add_multi_constructor("!", intrinsic)
TEMPLATE = yaml.load((Path(__file__).resolve().parents[1] / "template.yaml").read_text(encoding="utf-8"), Loader=TemplateLoader)
RESOURCES = TEMPLATE["Resources"]


def test_runtime_permissions_are_scoped_to_model_secret_and_logs():
    statements = RESOURCES["RuntimeRole"]["Properties"]["Policies"][0]["PolicyDocument"]["Statement"]
    actions = {action for statement in statements for action in statement["Action"]}
    assert actions == {"bedrock:InvokeModel", "ssm:GetParameter", "logs:CreateLogStream", "logs:PutLogEvents"}
    assert all(statement["Resource"] != "*" for statement in statements)
    assert "foundation-model/${BedrockModelId}" in json.dumps(statements)
    assert "parameter${WebhookSecretParameter}" in json.dumps(statements)
    permission = RESOURCES["ApiInvokePermission"]["Properties"]
    assert permission["SourceAccount"] == {"Ref": "AWS::AccountId"}
    assert permission["SourceArn"]["Sub"].endswith("${HttpApi}/$default/POST/telegram")


def test_no_secret_value_or_unbounded_log_payload_in_configuration():
    env = RESOURCES["BotFunction"]["Properties"]["Environment"]["Variables"]
    assert env["WEBHOOK_SECRET_PARAMETER"] == {"Ref": "WebhookSecretParameter"}
    assert not {"AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "TELEGRAM_BOT_TOKEN", "WEBHOOK_SECRET"} & env.keys()
    log_format = RESOURCES["HttpStage"]["Properties"]["AccessLogSettings"]["Format"]
    assert set(json.loads(log_format)) == {"requestId", "status", "latency"}
    for name in ("RuntimeLogs", "ApiLogs"):
        assert RESOURCES[name]["Properties"]["RetentionInDays"] == 3
        assert RESOURCES[name]["DeletionPolicy"] == "Delete"


def test_timeouts_rate_and_quota_do_not_assume_positive_reservation():
    function = RESOURCES["BotFunction"]["Properties"]
    env = function["Environment"]["Variables"]
    assert int(env["BEDROCK_MAX_TOKENS"]) <= 250
    assert float(env["BEDROCK_CONNECT_TIMEOUT"]) + float(env["BEDROCK_READ_TIMEOUT"]) < function["Timeout"]
    assert function["Timeout"] * 1000 < RESOURCES["WebhookIntegration"]["Properties"]["TimeoutInMillis"] <= 30000
    assert TEMPLATE["Parameters"]["ReservedConcurrency"]["Default"] == -1
    assert function["ReservedConcurrentExecutions"]["If"][2] == {"Ref": "AWS::NoValue"}
    limits = RESOURCES["HttpStage"]["Properties"]["DefaultRouteSettings"]
    assert limits["ThrottlingBurstLimit"] == 5 and limits["ThrottlingRateLimit"] == 1


def test_only_planned_services_no_implicit_artifact_or_secret_creation():
    assert {r["Type"] for r in RESOURCES.values()} == {
        "AWS::Lambda::Function", "AWS::Lambda::Permission", "AWS::IAM::Role",
        "AWS::Logs::LogGroup", "AWS::ApiGatewayV2::Api", "AWS::ApiGatewayV2::Integration",
        "AWS::ApiGatewayV2::Route", "AWS::ApiGatewayV2::Stage", "AWS::CloudWatch::Alarm",
    }
    assert RESOURCES["BotFunction"]["Properties"]["Code"] == {
        "S3Bucket": {"Ref": "ArtifactBucket"}, "S3Key": {"Ref": "ArtifactKey"},
    }
    assert TEMPLATE["Parameters"]["BedrockModelId"]["AllowedValues"] == ["openai.gpt-oss-20b-1:0"]
