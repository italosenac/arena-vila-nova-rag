"""Saudações por horário, sem associar o relógio a disponibilidade da arena."""
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

try:
    LOCAL_TIME = ZoneInfo('America/Sao_Paulo')
except ZoneInfoNotFoundError:
    # Hosts Windows sem tzdata: offset de São Paulo para a demonstração em 2026.
    LOCAL_TIME = timezone(timedelta(hours=-3))

GREETINGS = {
    'madrugada': ('Boa madrugada! ', 'Boa madrugada, turma da pelada! ', 'Boa madrugada, pessoal da resenha! '),
    'manhã': ('Bom dia! ', 'Bom dia, turma da pelada! ', 'Bom dia, pessoal do saque e do gol! '),
    'tarde': ('Boa tarde! ', 'Boa tarde, turma da resenha! ', 'Boa tarde, pessoal do saque e do gol! '),
    'noite': ('Boa noite! ', 'Boa noite, turma da pelada! ', 'Boa noite, pessoal da resenha! '),
}


def local_now(now: datetime | None = None) -> datetime:
    value = datetime.now(timezone.utc) if now is None else now
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError('O relógio injetado deve informar o fuso')
    return value.astimezone(LOCAL_TIME)


def time_band(now: datetime | None = None) -> str:
    hour = local_now(now).hour
    return 'madrugada' if hour < 5 else 'manhã' if hour < 12 else 'tarde' if hour < 18 else 'noite'


def greet(text: str, *, now: datetime | None = None) -> str:
    if any(text.startswith(prefix) for choices in GREETINGS.values() for prefix in choices):
        return text
    value = local_now(now)
    choices = GREETINGS[time_band(value)]
    index = sha256((value.date().isoformat()+text).encode()).digest()[0] % len(choices)
    return choices[index] + text
