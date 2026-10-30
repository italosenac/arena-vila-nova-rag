"""Orientação opcional sem fatos, histórico ou dados pessoais."""
from dataclasses import dataclass
import hashlib
import hmac
import re

from .knowledge import normalize


@dataclass(frozen=True)
class Guidance:
    text: str
    choices: tuple[tuple[str, str], ...] = ()


PAGES = {
    'home': Guidance('Sobre o que você gostaria de saber?', (
        ('Quadras e preços', 'courts'), ('Reservas e cancelamentos', 'booking'),
        ('Horários e localização', 'location'), ('Outra dúvida', 'free'))),
    'courts': Guidance('Você quer saber o preço ou a estrutura das quadras?', (
        ('Preços', 'price'), ('Estrutura', 'structure'), ('Voltar', 'home'))),
    'price': Guidance('Você quer saber o preço do futsal ou da quadra de areia?', (
        ('Futsal', 'futsal'), ('Areia', 'sand'), ('Plano mensalista', 'monthly'), ('Voltar', 'home'))),
    'futsal': Guidance('Para qual período você quer consultar o preço do futsal?', (
        ('Dia útil até 17h', 'f_early'), ('Dia útil após 17h', 'f_late'),
        ('Fim de semana ou feriado', 'f_weekend'), ('Voltar', 'price'))),
    'sand': Guidance('Para qual período você quer consultar o preço da areia?', (
        ('Dia útil até 17h', 's_early'), ('Dia útil após 17h', 's_late'),
        ('Fim de semana ou feriado', 's_weekend'), ('Voltar', 'price'))),
    'booking': Guidance('Você quer entender como reservar, cancelar ou reagendar?', (
        ('Nova reserva', 'new'), ('Cancelamento', 'cancel'), ('Reagendamento', 'reschedule'), ('Voltar', 'home'))),
    'cancel': Guidance('É uma reserva avulsa ou um plano mensalista?', (
        ('Reserva avulsa', 'cancel_single'), ('Plano mensalista', 'cancel_monthly'), ('Voltar', 'booking'))),
    'location': Guidance('Você quer saber o horário de funcionamento ou a localização?', (
        ('Funcionamento', 'hours'), ('Localização', 'address'), ('Voltar', 'home'))),
    'free': Guidance('Pode enviar sua dúvida sobre a Arena Vila Nova, sem dados pessoais.'),
}

# Os botões expressam perguntas. Nenhuma resposta factual é armazenada aqui.
QUESTIONS = {
    'structure': 'Como é a estrutura das quadras da arena?',
    'structure_f': 'Como são as quadras de futsal da arena?',
    'structure_s': 'Como são as quadras de areia da arena?',
    'monthly': 'Quais são as condições do plano mensalista?',
    'f_early': 'Qual o preço por hora do futsal em dia útil até 17h?',
    'f_late': 'Qual o preço por hora do futsal em dia útil após 17h?',
    'f_weekend': 'Qual o preço por hora do futsal no fim de semana ou feriado?',
    's_early': 'Qual o preço por hora da areia em dia útil até 17h?',
    's_late': 'Qual o preço por hora da areia em dia útil após 17h?',
    's_weekend': 'Qual o preço por hora da areia no fim de semana ou feriado?',
    'new': 'Como reservar e qual a antecedência mínima e máxima?',
    'cancel_single': 'Como funciona o cancelamento de uma reserva avulsa?',
    'cancel_monthly': 'Como cancelar o plano mensalista?',
    'reschedule': 'Quais são as condições de reagendamento de uma reserva?',
    'hours': 'Qual o horário de funcionamento da arena?',
    'address': 'Onde fica a Arena Vila Nova?',
}


def clarify(question: str) -> Guidance | None:
    """Só intenções vagas: não interromper perguntas livres completas."""
    value = re.sub(r'[?!.,]+$', '', normalize(question).strip())
    if re.fullmatch(r'(?:oi|ola|bom dia|boa tarde|boa noite)', value):
        return Guidance('Olá! Como posso ajudar com a Arena Vila Nova?')
    if value in {'obrigado', 'obrigada', 'valeu', 'vlw'}:
        return Guidance('Disponha! Sempre que precisar, pode enviar outra dúvida sobre a arena.')
    if value in {'tchau', 'ate mais', 'ate logo'}:
        return Guidance('Até a próxima!')
    if value in {'entendi', 'certo', 'ok'}:
        return Guidance('Certo. Pode enviar outra dúvida sobre a arena quando quiser.')
    if value in {'quanto custa', 'qual o preco', 'precos', 'preco', 'valores'}:
        return PAGES['price']
    if value in {'quanto custa o futsal', 'qual o preco do futsal'}:
        return PAGES['futsal']
    if value in {'quanto custa a areia', 'qual o preco da areia'}:
        return PAGES['sand']
    if value in {'reserva', 'reservas', 'reservas e cancelamentos'}:
        return PAGES['booking']
    if value in {'cancelamento', 'quero cancelar', 'como cancelar'}:
        return PAGES['cancel']
    if value in {'modalidades', 'quadras', 'quais modalidades'}:
        return Guidance('Você quer informações sobre futsal ou quadras de areia?', (
            ('Futsal', 'structure_f'), ('Areia', 'structure_s'), ('Outra dúvida', 'free')))
    return None


def callback_data(action: str, chat_id: int, secret: str) -> str:
    if action not in PAGES and action not in QUESTIONS:
        raise ValueError('Opção inválida')
    message = f'{chat_id}:{action}'.encode()
    tag = hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()[:24]
    return f'q:{action}:{tag}'


def decode_callback(data: object, chat_id: int, secret: str) -> str:
    if not isinstance(data, str) or len(data) > 64:
        raise ValueError('Opção inválida')
    parts = data.split(':')
    if len(parts) != 3 or parts[0] != 'q':
        raise ValueError('Opção inválida')
    expected = callback_data(parts[1], chat_id, secret)
    if not hmac.compare_digest(data, expected):
        raise ValueError('Opção inválida')
    return parts[1]


def markup(view: Guidance, chat_id: int, secret: str) -> dict:
    return {'inline_keyboard': [[{'text': label, 'callback_data': callback_data(action, chat_id, secret)}]
                               for label, action in view.choices]}
