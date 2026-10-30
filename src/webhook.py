"""HTTP API v2 -> Telegram inline -> serviço compartilhado, sem histórico ou logs."""
import base64
import hmac
import hashlib
import json
import os
import re
import time
from typing import Callable

from .policies import ERROR
from .service import Assistant, build_service
from .concierge import (QUESTIONS, decode_choice, keyboard, question_text,
                        recommendation_question, wants_advice)

HELP = ("Sou o assistente da Arena Vila Nova. Pergunte sobre horários, preços e regras. "
        "Não faço reservas nem cancelamentos. Não envie dados pessoais, cartão ou senhas. "
        "Use /informe para um panorama da arena e /aconselhe para escolher uma pelada "
        "com cinco perguntas sobre suas preferências. Também converso sobre esportes e organização do grupo. "
        "Use /ajuda para ver esta orientação.")
MAX_BODY = 16384


def present_answer(text: str) -> str:
    """Tom solicitado para o Telegram, aplicado após a validação factual."""
    openings = (
        "Você bilola mais que bola em mil rachões: ",
        "Entre um saque e outro, a gente bilola: ",
        "Quando o chute visita a lua, a gente bilola sem drama: ",
        "Se a manchete saiu de férias, a gente bilola com calma: ",
        "Do primeiro saque à última resenha, você bilola com a gente: ",
        "Depois de correr por um time inteiro, você bilola por aqui: ",
        "Entre o gole d’água e o próximo set, a gente bilola: ",
        "Se a bola foi dar uma voltinha fora da linha, a gente bilola: ",
        "Estamos bilolando no ritmo da pelada: ",
        "No vôlei, bilolamos fortemente — e o recado é este: ",
        "Quando saímos para bilolar, até a resenha entra em quadra: ",
        "Entre a pelada e a night, a gente bilola com calma: ",
        "Depois da night, bilolamos no modo recuperação: ",
        "No aquecimento, bilolamos como se a final fosse hoje: ",
    )
    choice = hashlib.sha256(text.encode("utf-8")).digest()[0] % len(openings)
    return openings[choice] + text


class ParameterSecret:
    """Valor só em memória; nome no ambiente. Nunca emitir o parâmetro em logs."""
    def __init__(self, client=None):
        self.client = client
        self.value = ""
        self.expires = 0.0

    def __call__(self) -> str:
        if self.value and time.monotonic() < self.expires:
            return self.value
        name = os.environ.get("WEBHOOK_SECRET_PARAMETER", "")
        if not re.fullmatch(r"/arena-vila-nova/[A-Za-z0-9/_-]+", name):
            raise ValueError("Parâmetro não configurado")
        if self.client is None:
            import boto3
            from botocore.config import Config
            self.client = boto3.Session(region_name=os.getenv("AWS_REGION", "sa-east-1")).client(
                "ssm", config=Config(connect_timeout=1, read_timeout=2,
                retries={"total_max_attempts":1,"mode":"standard"}))
        parameter = self.client.get_parameter(Name=name, WithDecryption=True)["Parameter"]
        value = parameter.get("Value", "")
        if parameter.get("Type") != "SecureString" or not re.fullmatch(r"[A-Za-z0-9_-]{32,256}", value):
            raise ValueError("Segredo inválido")
        self.value, self.expires = value, time.monotonic() + 300
        return value


def response(code: int, body: dict | None = None) -> dict:
    return {"statusCode":code, "headers":{"content-type":"application/json; charset=utf-8", "cache-control":"no-store"},
            "body":json.dumps(body or {}, ensure_ascii=False)}


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Campo duplicado")
        result[key] = value
    return result


def handle_event(event: dict, *, secret_provider: Callable[[], str],
                 service_factory: Callable[[], Assistant]) -> dict:
    if not isinstance(event, dict):
        return response(400)
    try:
        if event.get("requestContext", {}).get("http", {}).get("method") != "POST":
            return response(405)
        if event.get("rawPath") != "/telegram":
            return response(404)
        raw_headers = event.get("headers")
        if not isinstance(raw_headers, dict):
            return response(403)
        headers = {str(k).lower():v for k,v in raw_headers.items()}
        received = headers.get("x-telegram-bot-api-secret-token", "")
        if not isinstance(received, str) or not re.fullmatch(r"[A-Za-z0-9_-]{32,256}", received):
            return response(403)
        try:
            expected = secret_provider()
            valid = isinstance(expected,str) and bool(expected) and hmac.compare_digest(received,expected)
        except Exception:
            return response(503)
        if not valid:
            return response(403)
        # Só após autenticar: interpretar conteúdo não confiável.
        if str(headers.get("content-type", "")).split(";",1)[0].strip().lower() != "application/json":
            return response(415)
        body = event.get("body", "")
        if not isinstance(body, str):
            return response(400)
        if len(body) > MAX_BODY:
            return response(413)
        if event.get("isBase64Encoded"):
            body = base64.b64decode(body, validate=True).decode("utf-8")
        if len(body.encode("utf-8")) > MAX_BODY:
            return response(413)
        update = json.loads(body, object_pairs_hook=unique_object)
        if not isinstance(update, dict) or type(update.get("update_id")) is not int:
            return response(400)
        if 'callback_query' in update:
            callback = update['callback_query']
            if not isinstance(callback,dict):
                return response(400)
            message = callback.get('message',{})
            chat = message.get('chat',{})
            chat_id, message_id = chat.get('id'),message.get('message_id')
            sender = callback.get('from',{})
            if chat.get('type') != 'private' or sender.get('is_bot'):
                return response(200)
            if (type(chat_id) is not int or chat_id <= 0 or type(message_id) is not int
                    or message_id <= 0 or type(sender.get('id')) is not int or sender['id'] != chat_id):
                return response(400)
            try:
                choices = decode_choice(callback.get('data'),chat_id,expected)
            except ValueError:
                return response(200,{'method':'sendMessage','chat_id':chat_id,
                    'text':'Vamos bilolar de novo: essa opção expirou ou é inválida. Use /aconselhe para recomeçar.'})
            if len(choices) < len(QUESTIONS):
                return response(200,{'method':'editMessageText','chat_id':chat_id,'message_id':message_id,
                    'text':question_text(choices),'reply_markup':keyboard(choices,chat_id,expected)})
            try:
                answer = service_factory().responder(recommendation_question(choices)).text
            except Exception:
                answer = ERROR
            profile = ' / '.join(options[c] for (_,options),c in zip(QUESTIONS,choices))
            return response(200,{'method':'editMessageText','chat_id':chat_id,'message_id':message_id,
                'text':present_answer('Seu perfil esportivo: '+profile+'.\n'+answer),
                'reply_markup':{'inline_keyboard':[]},'link_preview_options':{'is_disabled':True}})
        message = update.get("message")
        if message is None:
            return response(200)
        if not isinstance(message, dict) or not isinstance(message.get("chat"),dict):
            return response(400)
        chat = message["chat"]
        if chat.get("type") != "private" or message.get("from", {}).get("is_bot"):
            return response(200)
        chat_id = chat.get("id")
        if type(chat_id) is not int or chat_id <= 0:
            return response(400)
        text = message.get("text")
        if text is not None and not isinstance(text, str):
            return response(400)
        if text is None:
            answer = "Envie uma pergunta em texto, sem documentos ou dados pessoais."
        elif wants_advice(text):
            return response(200,{'method':'sendMessage','chat_id':chat_id,'text':question_text(()),
                                 'reply_markup':keyboard((),chat_id,expected)})
        elif text.strip().split(" ",1)[0].split("@",1)[0] in {"/start","/ajuda","/help"}:
            answer = HELP
        elif text.startswith("/") and text.strip() != '/informe':
            answer = "Use /ajuda ou envie uma pergunta sobre a Arena Vila Nova."
        else:
            try:
                answer = service_factory().responder(text).text
            except Exception:
                answer = ERROR
        return response(200,{"method":"sendMessage","chat_id":chat_id,"text":present_answer(answer),
                             "link_preview_options":{"is_disabled":True}})
    except (ValueError, TypeError, AttributeError, KeyError, UnicodeError, RecursionError):
        return response(400)


_secret = ParameterSecret()
_service = None


def cached_service() -> Assistant:
    global _service
    if _service is None:
        _service = build_service()
    return _service


def lambda_handler(event, context):
    return handle_event(event, secret_provider=_secret, service_factory=cached_service)
