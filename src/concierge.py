"""Preferências esportivas em botões assinados; nenhum cadastro ou banco de dados."""
import hashlib
import hmac
import re
import time

from .knowledge import normalize

QUESTIONS = (
    ('Qual modalidade você prefere?', ('futsal','futebol em grama sintética','vôlei de praia','futevôlei','ainda quero escolher')),
    ('Qual é o tamanho do grupo?', ('dupla','quatro pessoas','cinco a oito pessoas','nove a quatorze pessoas','ainda vou reunir o grupo')),
    ('Qual é o objetivo do encontro?', ('lazer e resenha','treino de fundamentos','iniciação ao esporte','encontro com amigos','confraternização')),
    ('Como é a experiência do grupo?', ('iniciante','intermediário','grupo misto','praticante habitual','retomando a prática')),
    ('Qual período vocês preferem?', ('manhã','tarde','noite','fim de semana','a combinar')),
)
MATRIX_AXES = tuple(options for _,options in QUESTIONS)
MATRIX_SHAPE = tuple(len(axis) for axis in MATRIX_AXES)


def wants_advice(text: str) -> bool:
    return normalize(text).strip(' .!?') in {'me aconselhe','aconselhe','/aconselhe'}


def wants_overview(text: str) -> bool:
    return normalize(text).strip(' .!?') in {'me informe','informe','/informe','tudo sobre a arena','me informe sobre tudo da arena vila nova'}


def _signature(payload: str, chat_id: int, secret: str) -> str:
    return hmac.new(secret.encode(),f'{chat_id}:{payload}'.encode(),hashlib.sha256).hexdigest()[:16]


def keyboard(choices: tuple[int, ...], chat_id: int, secret: str, *, now=None) -> dict:
    if len(choices) >= len(QUESTIONS) or any(type(c) is not int or not 0 <= c < len(MATRIX_AXES[i]) for i,c in enumerate(choices)):
        raise ValueError('Etapa inválida')
    expires = int(time.time() if now is None else now) + 1800
    buttons = []
    for index, label in enumerate(QUESTIONS[len(choices)][1]):
        payload = f'q:{expires}:' + ''.join(str(c) for c in (*choices,index))
        buttons.append([{'text': label, 'callback_data': payload+':'+_signature(payload,chat_id,secret)}])
    return {'inline_keyboard': buttons}


def decode_choice(data: str, chat_id: int, secret: str, *, now=None) -> tuple[int, ...]:
    if not isinstance(data,str) or not re.fullmatch(r'q:\d{1,12}:[0-4]{1,5}:[a-f0-9]{16}', data):
        raise ValueError('Opção inválida')
    payload, signature = data.rsplit(':',1)
    _, deadline, digits = payload.split(':')
    current = int(time.time() if now is None else now)
    if not current <= int(deadline) <= current+1800 or not hmac.compare_digest(signature,_signature(payload,chat_id,secret)):
        raise ValueError('Opção expirada ou inválida')
    return tuple(int(c) for c in digits)


def recommendation_question(choices: tuple[int, ...]) -> str:
    if len(choices) != 5 or any(type(c) is not int or not 0 <= c < len(MATRIX_AXES[i]) for i,c in enumerate(choices)):
        raise ValueError('Perfil incompleto')
    preferences = '; '.join(f'{question} {options[choice]}' for (question,options),choice in zip(QUESTIONS,choices))
    return ('Aconselhe um encontro esportivo conforme estas preferências: '+preferences+
            '. Sugira organização do grupo, sem garantir preço, capacidade ou vaga. Oriente a consultar dia e horário na recepção para reservar.')


def question_text(choices: tuple[int, ...]) -> str:
    return (f'Vamos bilolar com planejamento! Pergunta {len(choices)+1} de 5: '+QUESTIONS[len(choices)][0]+
            '\nEscolha uma opção. São apenas preferências esportivas; não envie dados pessoais. Use /aconselhe para recomeçar.')
