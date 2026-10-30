"""Configura Telegram localmente. Token digitado de forma oculta, nunca persistido."""
import argparse
import getpass
import json
from pathlib import Path
import re
import urllib.error
import urllib.request


class TelegramFailure(Exception):
    pass


def telegram_call(token: str, method: str, payload: dict) -> object:
    request = urllib.request.Request("https://api.telegram.org/bot" + token + "/" + method,
        data=json.dumps(payload).encode(), headers={"Content-Type":"application/json"}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            data=json.loads(response.read(65536))
    except (OSError, ValueError, urllib.error.URLError):
        # Exceções HTTP contêm a URL com token: nunca imprimir a exceção original.
        raise TelegramFailure("Falha na conexão Telegram; confira token e rede.") from None
    if not isinstance(data,dict) or data.get("ok") is not True:
        raise TelegramFailure("Telegram não confirmou a operação.")
    return data["result"]


def configure(*, token: str, url: str, secret: str, call=telegram_call) -> dict:
    if not re.fullmatch(r"\d{6,12}:[A-Za-z0-9_-]{30,}", token):
        raise ValueError("Formato de token inválido")
    if not re.fullmatch(r"https://[a-z0-9]+\.execute-api\.sa-east-1\.amazonaws\.com/telegram",url):
        raise ValueError("Endpoint inválido")
    if not re.fullmatch(r"[A-Za-z0-9_-]{32,256}",secret):
        raise ValueError("Segredo inválido")
    me=call(token,"getMe",{})
    if not isinstance(me,dict) or not me.get("is_bot") or not re.fullmatch(r"[A-Za-z0-9_]+",me.get("username","")):
        raise TelegramFailure("Identidade do bot não confirmada")
    if call(token,"setWebhook",{"url":url,"secret_token":secret,"allowed_updates":["message","callback_query"],
                                  "max_connections":1,"drop_pending_updates":False}) is not True:
        raise TelegramFailure("Registro do webhook não confirmado")
    info=call(token,"getWebhookInfo",{})
    if info.get("url") != url:
        raise TelegramFailure("Endpoint do webhook não corresponde ao implantado")
    call(token,"setMyCommands",{"commands":[{"command":"start","description":"Iniciar atendimento"},
                                           {"command":"ajuda","description":"Orientações e privacidade"},
                                           {"command":"informe","description":"Panorama da Arena Vila Nova"},
                                           {"command":"aconselhe","description":"Questionário e sugestão de pelada"}]})
    return {"username":me["username"],"url":"https://t.me/"+me["username"],"webhook_url":info["url"],
            "pending_update_count":info.get("pending_update_count"),"last_error_date":info.get("last_error_date"),
            "verified":True}


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile",default="arena-vila-nova")
    parser.add_argument("--deployment",type=Path,default=Path("reports/deployment.json"))
    args=parser.parse_args()
    try:
        import boto3
        from botocore.config import Config
        session=boto3.Session(profile_name=args.profile,region_name="sa-east-1")
        if args.deployment.is_file():
            deployment=json.loads(args.deployment.read_text(encoding="utf-8"))
        else:
            stack=session.client("cloudformation").describe_stacks(StackName="arena-vila-nova")["Stacks"][0]
            deployment={"webhook_url":next(o["OutputValue"] for o in stack["Outputs"] if o["OutputKey"]=="WebhookUrl"),
                        "secret_parameter":"/arena-vila-nova/webhook-secret"}
        client=session.client("ssm",
            config=Config(connect_timeout=3,read_timeout=5,retries={"total_max_attempts":1,"mode":"standard"}))
        secret=client.get_parameter(Name=deployment["secret_parameter"],WithDecryption=True)["Parameter"]["Value"]
        print("Digite o token do BotFather apenas aqui. A entrada fica oculta e não será salva.")
        token=getpass.getpass("Token Telegram (oculto): ").strip()
        result=configure(token=token,url=deployment["webhook_url"],secret=secret)
        target=args.deployment.parent/"telegram-status.json"
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
        print("Bot confirmado: "+result["url"])
        print("Webhook confirmado pelo Telegram. Abra o bot e envie /start e uma pergunta.")
        return 0
    except (KeyboardInterrupt,EOFError):
        print("Configuração interrompida; token não armazenado.")
        return 1
    except Exception as exc:
        reason=type(exc).__name__
        if isinstance(exc,(TelegramFailure,ValueError)):
            print(str(exc))
        target=args.deployment.parent/"telegram-setup-error.json"
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(json.dumps({"error_type":reason}),encoding="utf-8")
        print("Não foi possível concluir. Confira sessão AWS, rede e token; nenhum segredo foi exibido.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
