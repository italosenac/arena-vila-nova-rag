"""Reserva -> consulta -> alternativas; estado mínimo em botões assinados."""
import hmac
import re
import time
from .concierge import _signature
from .knowledge import normalize
from .topics import catalogue, topic_buttons, topic_prompt

SPORTS=('futsal','futebol em grama sintética','vôlei de praia','futevôlei')
DAYS=('hoje','amanhã','outro dia')
PERIODS=('manhã','tarde','noite')
SECTIONS={'b':'03-reservas-e-cancelamento:como-reservar',
          's':'03-reservas-e-cancelamento:sinal',
          'm':'03-reservas-e-cancelamento:reagendamento',
          'c':'03-reservas-e-cancelamento:cancelamento'}


def route_intent(text: str) -> str | None:
    from .policies import contains_sensitive,is_attack
    if contains_sensitive(text) or is_attack(text) or len(text)>2000:
        return None
    value=normalize(text).strip(' .!?')
    command=value.split(' ',1)[0].split('@',1)[0]
    if (re.search(r'nao (?:quero|desejo)|nao e isso',value)
            and re.search(r'preco|valor|pagamento|sinal|regra|calcad|contato|endereco|privacidade|mensal|cancel|reagend',value)):
        return None  # Uma dúvida específica prevalece sobre a recusa de outro caminho.
    if re.search(r'nao e isso|outra coisa|outro assunto|outras opcoes|nenhuma dessas|nao (?:quero|desejo).{0,15}consultar',value):
        return 'o'
    if value=='nao':
        return 'd'
    if re.search(r'nao (?:quero|desejo).{0,15}reserv',value):
        return 'h'
    if command=='/horarios' or re.search(r'horarios? disponive|consultar (?:os )?horarios?|tem vaga|consultar vaga',value):
        return 'h'
    if command=='/reservar' or value in {'reserva','reservar','quero jogar'} or re.search(r'\b(?:quero|preciso|desejo) (?:fazer (?:uma )?)?(?:reservar|agendar|marcar|uma reserva)\b',value):
        return 'r'
    if command in {'/start','/ajuda','/help'} or value in {'me ajude','quero ajuda','/menu'}:
        return 'e'
    return None


def _buttons(choices,chat_id: int,secret: str) -> dict:
    expiry=int(time.time())+1800
    rows=[]
    for label,action in choices:
        payload=f'f:{expiry}:{action}'
        rows.append([{'text':label,'callback_data':payload+':'+_signature(payload,chat_id,secret)}])
    return {'inline_keyboard':rows}


def decode_flow(data: str,chat_id: int,secret: str) -> str:
    if not isinstance(data,str) or not re.fullmatch(r'f:\d{1,12}:(?:[edrhobsmc]|a[0-3]{1,3}):[a-f0-9]{16}',data):
        raise ValueError('Opção inválida')
    payload,signature=data.rsplit(':',1)
    _,expiry,action=payload.split(':')
    if not time.time()<=int(expiry)<=time.time()+1801 or not hmac.compare_digest(signature,_signature(payload,chat_id,secret)):
        raise ValueError('Opção inválida ou expirada')
    if action.startswith('a') and any(int(d)>=len(options) for d,options in zip(action[1:],(SPORTS,DAYS,PERIODS))):
        raise ValueError('Preferência inválida')
    return action


def flow_view(action: str,chat_id: int,secret: str,*,service_factory) -> dict:
    if action=='e':
        text=('Sou o assistente da Arena Vila Nova. Vamos bilolar com planejamento! '
              'Você quer reservar um horário ou consultar horários? Não envie dados pessoais.')
        choices=(('Quero reservar','r'),('Consultar horários','h'))
    elif action=='d':
        text='Vamos bilolar pelo caminho certo: você prefere consultar horários ou tratar de outro assunto?'
        choices=(('Consultar horários','h'),('Outra necessidade','o'))
    elif action=='r':
        text='Vamos bilolar por etapas. Menu de reservas: o que você precisa fazer? O chat orienta; a confirmação é pelo site ou recepção.'
        choices=(('Nova reserva','b'),('Consultar horários','h'),('Pagamento do sinal','s'),
                 ('Reagendamento','m'),('Cancelamento','c'),('Outra necessidade','o'))
    elif action=='o':
        return {'text':topic_prompt(None),'reply_markup':topic_buttons(None,chat_id,secret)}
    elif action in SECTIONS:
        from .policies import ERROR
        try:
            answer=service_factory().explicar(SECTIONS[action]).text
        except Exception:
            answer=ERROR
        text='Vamos bilolar com o próximo passo: '+answer
        choices={
            'b':(('Consultar horários','h'),('Entender o sinal','s')),
            's':(('Como solicitar a reserva','b'),),
            'm':(('Consultar outro horário','h'),('Entender cancelamento','c')),
            'c':(('Consultar reagendamento','m'),),
        }[action]
    elif action=='h' or action.startswith('a'):
        digits='' if action=='h' else action[1:]
        steps=(('Qual modalidade você quer consultar?',SPORTS),('Para qual dia?',DAYS),('Em qual período?',PERIODS))
        if len(digits)<3:
            prompt,options=steps[len(digits)]
            text='Vamos bilolar e organizar sua consulta. '+prompt
            choices=tuple((label,'a'+digits+str(i)) for i,label in enumerate(options))
            if not digits:
                choices+= (('Não quero consultar horários','o'),)
        else:
            sport,day,period=(options[int(d)] for d,options in zip(digits,(SPORTS,DAYS,PERIODS)))
            contact=next(q['unit']['texto'] for q in catalogue() if q['unit']['id']=='01-sobre-a-arena:contato')
            site=re.search(r'[A-Za-z0-9.-]+\.example/reservas',contact).group()
            phone=re.search(r'\(\d{2}\) \d{4}-\d{4}',contact).group()
            text=(f'Vamos bilolar com um pedido definido: {sport}, {day}, no período da {period}. '
                  f'Consulte {site} ou a recepção {phone} para confirmar vagas nessas condições. '
                  'Informe a data exata ao canal oficial; a escolha aqui organiza a consulta e não confirma uma reserva. '
                  'Quer seguir para a reserva, consultar outro horário ou tratar de outra necessidade?')
            choices=(('Como fazer a reserva','b'),('Consultar outro horário','h'),('Outra necessidade','o'))
    else:
        raise ValueError('Fluxo inválido')
    return {'text':text,'reply_markup':_buttons(choices,chat_id,secret)}
