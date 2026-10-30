"""Perguntas de descoberta derivadas das seções do JSON vigente; navegação assinada."""
from functools import lru_cache
import hmac
import re
import time

from .concierge import _signature
from .knowledge import SOURCES, OWNER_SOURCE, load_base, normalize

TOPIC_SOURCES = (*SOURCES, OWNER_SOURCE)
LABELS = ('Estrutura, horários e contato','Quadras, preços e capacidade','Reservas, cancelamento e chuva',
          'Pagamentos e comprovantes','Regras de uso e menores','Planos mensalistas',
          'Eventos e campeonatos','Bebidas e dúvidas frequentes','Privacidade e LGPD',
          'Novidades da estrutura e reservas')
PROMPTS = (
    'Você quer conhecer a estrutura, os horários ou o contato?',
    'Sua dúvida é sobre preço, duração, capacidade ou equipamentos?',
    'Você precisa de nova reserva, cancelamento, reagendamento ou orientação sobre chuva?',
    'Você quer entender o sinal, o saldo, os meios de pagamento ou comprovantes?',
    'A dúvida é sobre calçados, itens permitidos, menores, pertences ou primeiros socorros?',
    'Você busca horário fixo, condições do plano, reposição de faltas ou cancelamento?',
    'Você está organizando um evento, aniversário ou inscrição no campeonato?',
    'Você quer saber sobre sinal, bebidas ou vestiário?',
    'Você quer entender finalidade, retenção dos dados ou exercer seus direitos?',
    'Você quer saber sobre a nova reserva, os pisos, banheiros, refrescos ou cessão de horário?',
)


@lru_cache(maxsize=1)
def catalogue() -> tuple[dict,...]:
    return tuple({'unit':dict(u),'question':f"Sobre {u['titulo']}: o que preciso saber sobre {u['secao']}?"}
                 for u in load_base() if u['fonte'] in TOPIC_SOURCES and u['secao']!='Panorama da arena')


def sections(topic: int) -> tuple[dict,...]:
    if type(topic) is not int or not 0 <= topic < len(TOPIC_SOURCES):
        raise ValueError('Assunto inválido')
    return tuple(q for q in catalogue() if q['unit']['fonte']==TOPIC_SOURCES[topic])


def wants_topics(text: str) -> bool:
    return normalize(text).strip(' .!?') in {'/assuntos','me ajude','quero ajuda','quero saber',
        'quero informacoes','quais assuntos','o que posso perguntar','quero conhecer a arena'}


def topic_prompt(topic: int | None) -> str:
    return ('Vamos bilolar com informação: o que você precisa entender para organizar seu jogo?'
            if topic is None else 'Vamos bilolar por partes! '+PROMPTS[topic])


def topic_buttons(topic: int | None, chat_id: int, secret: str, *, now=None) -> dict:
    deadline=int(time.time() if now is None else now)+1800
    choices=((i,0,label) for i,label in enumerate(LABELS)) if topic is None else (
        (topic,i,q['unit']['secao']) for i,q in enumerate(sections(topic),1))
    rows=[]
    for source,section,label in choices:
        payload=f'n:{deadline}:{source}:{section}'
        rows.append([{'text':label[:60],'callback_data':payload+':'+_signature(payload,chat_id,secret)}])
    return {'inline_keyboard':rows}


def decode_topic(data: str, chat_id: int, secret: str, *, now=None) -> tuple[int,int]:
    if not isinstance(data,str) or not re.fullmatch(r'n:\d{1,12}:\d:\d{1,2}:[a-f0-9]{16}',data):
        raise ValueError('Assunto inválido')
    payload,signature=data.rsplit(':',1)
    _,expires,topic,section=payload.split(':')
    current=int(time.time() if now is None else now)
    if not current <= int(expires) <= current+1800 or not hmac.compare_digest(signature,_signature(payload,chat_id,secret)):
        raise ValueError('Assunto expirado ou inválido')
    topic,section=int(topic),int(section)
    if not 0 <= section <= len(sections(topic)):
        raise ValueError('Seção inválida')
    return topic,section
