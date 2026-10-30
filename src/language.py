"""Normalização de intenções linguísticas; contém vocabulário, nunca respostas."""
import re
from .knowledge import normalize

CONCEPTS = (
    (r'\bonde fica\b','endereço'),
    (r'\babatimento\b','desconto'),
    (r'\b(?:refrigerante|garrafa|plastica|plastico)\b','bebidas'),
    (r'(?:trocar|mudar).{0,20}(?:data|dia)|outra data','reagendamento'),
    (r'\b(?:que horas|ate que horas|feriado|natal|ano novo)\b','horário funcionamento'),
    (r'\batras|cheg.{0,20}depois|tempo perdido','atrasos tolerância'),
    (r'\b(?:agendo|agendar|agendamento|marcar|canal)\b','reservar site recepção'),
    (r'\b(?:entrada|adiantar|adiantamento|segurar)\b','sinal'),
    (r'\b(?:especie|numerario)\b','dinheiro pagamento'),
    (r'\b(?:tenis|chuteira|calcado|calcados|solado)\b','calçados'),
    (r'\b(?:cachorro|pet|churrasqueira|fumar|vape|vidro|som alto)\b','proibições'),
    (r'\b(?:mochila|cadeado|armario|pertences)\b|guardar (?:coisas|bolsa)','pertences armários'),
    (r'\b(?:cadastro|informacoes pessoais|documento pessoal)\b','dados coletamos privacidade'),
    (r'para que.{0,50}dados|usam.{0,30}dados|dados.{0,20}utiliz','finalidade'),
    (r'(?:documento pessoal|cpf|cartao|senha).{0,40}(?:chat|telegram)|(?:chat|telegram).{0,40}(?:documento|cpf|cartao|senha)','atendimento Telegram'),
    (r'\b(?:excluir|exclusao|corrigir|correcao|acessar)\b.{0,30}dados','direitos titular'),
    (r'\b(?:parcelar|parcelamento|credito|debito)\b','meios aceitos pagamento'),
    (r'\bprimeiros socorros\b','saúde socorros'),
    (r'\b(?:aniversario|corporativo|orcamento)\b','eventos orçamento'),
)


def expand_question(question: str) -> str:
    value=normalize(question)
    extra=[terms for pattern,terms in CONCEPTS if re.search(pattern,value)]
    return question+' '+' '.join(extra)


def has_arena_concept(question: str) -> bool:
    value=normalize(question)
    return any(re.search(pattern,value) for pattern,_ in CONCEPTS)


def question_parts(question: str) -> tuple[str,...]:
    """Só decompor cláusulas com conteúdo, sem separar 'Pix e cartão'."""
    if normalize(question).startswith('aconselhe um encontro esportivo'):
        return (question,)
    parts=re.split(r'[?;]|\be (?=(?:posso |jogar |usar |levar |como |quanto |qual |preciso |se |o que |tem |vocês ))',question,flags=re.I)
    substantive=tuple(p.strip() for p in parts if len(re.findall(r'\w+',p))>=3)
    if len(substantive)<=1:
        return (question,)
    explicit=r'sinal|pagamento|pix|dinheiro|cartao|chuteira|calca|tenis|menor|plano|mensal|evento|anivers|campeon|dados|reserva|volei|futebol|futsal|areia|chuva|armario|cadeado|bebida|vidro'
    return tuple(part if i==0 or has_arena_concept(part) or re.search(explicit,normalize(part))
                 else substantive[0]+' '+part for i,part in enumerate(substantive[:5]))
