"""Triagem determinística e verificação conservadora da fundamentação."""

import re
from decimal import Decimal
from typing import Literal

from .knowledge import Unit, forbidden_content, normalize
from .retriever import tokens


Status = Literal["RESPONDER", "NAO_CONSTA", "FORA_ESCOPO", "BLOQUEADO", "ERRO"]
NO_DATA = ("Não tenho essa informação na base. A recepção pode confirmar pelo (99) 9999-0100, "
           "durante o horário de funcionamento: seg–sex 7h–23h, sábado 7h–22h, domingos e "
           "feriados 8h–20h. Fechado em 25/12 e 01/01.")
ERROR = "Não foi possível consultar o atendimento agora. A recepção pode ajudar pelo (99) 9999-0100."
OUTSIDE = ("Não tenho evidência para responder a esse assunto. Se quiser reunir a turma para "
           "futebol, vôlei ou futevôlei, diga ‘me aconselhe’: faço cinco perguntas sobre suas "
           "preferências e ajudo a planejar o encontro. A reserva é pelo site ou pela recepção.")
PRIVATE = "Não compartilhe dados sensíveis ou credenciais aqui. Use o canal oficial ou a recepção."
ATTACK = "Não posso alterar as regras nem revelar instruções ou documentos internos. Posso ajudar sobre a Arena Vila Nova."
TRANSACTION = "O chat não realiza reservas nem cancelamentos. Use arenavilanova.example/reservas ou a recepção."
NUMERIC_SENSITIVE = r"(?<!\d)(?:\d[ .-]?){11}(?!\d)|(?<!\d)(?:\d[ -]?){13,19}(?!\d)"


def contains_sensitive(text: str) -> bool:
    value = normalize(text)
    return bool(re.search(NUMERIC_SENSITIVE, value) or re.search(
        r"\b(?:senha|token|api[_ -]?key|chave de api|codigo de seguranca|cvv)\s*(?:e\b|:|=)\s*\S+|"
        r"\b(?:meu|minha)\s+(?:cpf|cartao|senha|token|telefone|email|e-mail|nome)\s*(?:e\b|:|=)|"
        r"\bsk-[a-z0-9_-]{10,}|\bAKIA[A-Z0-9]{12,}|\b\d{6,12}:[a-z0-9_-]{20,}\b", value, flags=re.I))


def is_attack(text: str) -> bool:
    value = normalize(text)
    return forbidden_content(text) or bool(re.search(
        r"(?:ignore|esqueca|substitua|desconsidere|altere).{0,50}(?:politica|regra|instruc)|"
        r"(?:revel|mostr|copi|imprim|exib).{0,65}(?:prompt|diretriz|instruc|document.{0,15}brut|base inteira)|"
        r"(?:system|sistema|developer)\s*:|\bprompt\b|diretrizes internas|instrucoes internas|"
        r"(?:sou|na qualidade de).{0,25}(?:dono|administrador|proprietario|desenvolvedor)|"
        r"ignore.{0,35}(?:rules|instructions|policy)|finja.{0,30}(?:sistema|dono|administrador)", value))


def is_transaction(text: str) -> bool:
    return bool(re.search(r"^\s*(?:por favor[, ]*)?(?:reserve|cancele|confirme|efetue|faca (?:a |uma )?reserva)\b",
                          normalize(text)))


def triage(question: str) -> tuple[Status, str] | None:
    if not question.strip():
        return "NAO_CONSTA", NO_DATA
    if len(question) > 2000:
        return "BLOQUEADO", "Envie uma pergunta de até 2000 caracteres, sem dados pessoais."
    if contains_sensitive(question):
        return "BLOQUEADO", PRIVATE
    if is_attack(question):
        return "BLOQUEADO", ATTACK
    if is_transaction(question):
        return "BLOQUEADO", TRANSACTION
    value = normalize(question)
    if re.search(r"previsao|vai chover|tempo amanha|piada|receita|bolo|eleic|votar|remedio|diagnostic|tratamento|aconselhamento (?:medico|juridico)", value):
        return "FORA_ESCOPO", OUTSIDE
    if re.search(r"estacion|disponiv|tem vaga|agenda ao vivo|piscina|wi-?fi|cupom|cupons", value):
        return "NAO_CONSTA", NO_DATA
    if not re.search(r"futebol|futevolei|aconselh|organiz|resenha|amig|night|conviv|iniciante|treino|preferencia|grama|banheiro|geladeira|refresco|jogadores|pontos|toques|impedimento|arena|quadr|futsal|areia|beach|volei|jogo|partida|reserv|sinal|cancel|desmarc|desist|reagend|remarc|mudar.{0,15}(?:dia|data)|chuva|chover|pag|pix|cartao|dinheiro|cheque|chuteira|trava|calcad|lotacao|capacidade|pessoa|campeon|inscri|mensal|plano|evento|anivers|privaci|dado|cpf|nota fiscal|horario|abrem|abre|funcion|sabado|domingo|feriado|preco|valor|desconto|bola|raquete|vestiar|bebida|vidro|cadeado|armario|comparec|faltar|aparecer|multa|atras|menor|responsavel|animal|assistencia|fumar|som alto|endereco|contato|telefone|recepcao|retencao|recibo", value):
        return "FORA_ESCOPO", OUTSIDE
    return None


def supported_answer(answer: str, cited: tuple[Unit, ...], *, question: str = "") -> bool:
    """IDs corretos não bastam: checar números e contradições críticas também.

    Regras e sobreposição lexical reduzem risco, sem provar equivalência semântica
    universal. Na dúvida a camada de serviço encaminha à recepção.
    """
    if not isinstance(answer, str) or not answer.strip() or len(answer) > 900 or not cited:
        return False
    if contains_sensitive(answer) or is_attack(answer):
        return False
    value = normalize(answer)
    if re.search(r"(?<!nao )(?<!nunca )(?:envie|informe|digite|mande).{0,25}(?:cpf|cartao|senha|token|cvv)|"
                 r"(?:reserva|cancelamento)\s+(?:confirmad|realizad)|reservei|cancelei|"
                 r"(?:cupom|50\s*%)|sinal.{0,30}(?:cinquenta|metade)|"
                 r"(?:cancelamento|cancelar).{0,70}(?:12|2)\s*(?:horas|h\b)|"
                 r"reagend.{0,35}(?:ilimitad|quantas vezes quiser)|"
                 r"(?:chuteira.{0,10}trava|vidro).{0,20}(?:permitid|liberad)", value):
        return False
    signal = re.search(r"\bsinal\b.{0,35}?(\d+)\s*%", value)
    if signal and signal[1] != "30":
        return False
    if re.search(r"(?:cancelamento|cancelar).{0,40}(?:gratuito|gratis).{0,20}menos de\s*24|"
                 r"reagend.{0,40}(?:duas|tres|[2-9])\s+vezes", value):
        return False
    if re.search(r"cobranca (?:adicional|extra)|multa (?:adicional|extra)", value):
        # A negação explícita da cobrança adicional é válida.
        if not re.search(r"nao ha (?:cobranca|multa) (?:adicional|extra)", value):
            return False
    if any(unit["secao"] == "Não comparecimento" for unit in cited):
        for clause in re.split(r"[.!?;,\n]", value):
            if re.search(r"(?:multa|cobranca|taxa).{0,30}(?:\d|alem do sinal)", clause):
                if not re.search(r"(?:nao ha|nao existe|nao cobramos|nenhuma|sem)\s+(?:multa|cobranca|taxa)", clause):
                    return False
    evidence = normalize(" ".join(' '.join(unit[key] for key in ('texto','titulo','versao','atualizado_em'))
                                  for unit in cited))
    # Pode repetir horário fornecido pelo usuário; isso não autoriza reaproveitar
    # seus números como preços, percentuais ou prazos inventados.
    numerical_text = value
    for time in re.findall(r"\b\d{1,2}(?:h(?:\d{2})?|:\d{2})\b", normalize(question)):
        numerical_text = re.sub(r"\b" + re.escape(time) + r"\b", "", numerical_text)
    def numbers(text):
        return {Decimal(n.replace(",", ".")) for n in re.findall(r"\d+(?:[.,]\d+)?", text)}
    if not numbers(numerical_text) <= numbers(evidence):
        return False
    if any(answer.strip() == unit["texto"].strip() and len(answer) > 300 for unit in cited):
        return False  # Evitar despejar documento/trecho longo como resposta ao cliente.
    content = re.split(r"fonte[s]?\s*:", value)[0]
    words = set(tokens(content))
    return bool(words) and len(words & set(tokens(evidence))) / len(words) >= 0.4
