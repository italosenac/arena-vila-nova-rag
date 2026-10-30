"""Contrato e carregamento da base publicável; somente biblioteca padrão."""

from datetime import date
import hashlib
import json
from pathlib import Path
import re
import unicodedata
from typing import TypedDict


BASE_PATH = Path(__file__).resolve().parents[1] / "data" / "base.json"
SOURCES = {
    "01-sobre-a-arena.md": "institucional", "02-quadras-e-precos.md": "comercial",
    "03-reservas-e-cancelamento.md": "politica", "04-pagamento.md": "comercial",
    "05-regras-de-uso.md": "regras", "06-planos-mensalistas.md": "comercial",
    "07-eventos-e-campeonatos.md": "comercial", "08-faq-atendimento.md": "atendimento",
    "09-privacidade-e-lgpd.md": "politica",
}
OBSOLETE_SOURCE = "03b-reservas-v1-obsoleta.md"
POLICY_SOURCE = "03-reservas-e-cancelamento.md"
FAQ_SOURCE = "08-faq-atendimento.md"
FAQ_SECTIONS = {"Como pago o sinal?", "Posso levar bebidas?", "Há vestiário?"}


class Unit(TypedDict):
    id: str
    fonte: str
    secao: str
    area: str
    versao: str
    atualizado_em: str
    texto: str
    titulo: str
    status: str
    prioridade: int
    sha256: str


def normalize(text: str) -> str:
    return "".join(char for char in unicodedata.normalize("NFD", text.casefold())
                   if unicodedata.category(char) != "Mn")


def section_id(source: str, section: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", normalize(section)).strip("-")
    return Path(source).stem + ":" + slug


def priority(source: str) -> int:
    """Autoridade explícita, independente do rótulo vigente do FAQ."""
    if source == FAQ_SOURCE:
        return 100
    return 300 if SOURCES[source] == "politica" else 200


def forbidden_content(text: str) -> bool:
    return bool(re.search(
        r"arena50|aviso interno|ignore.{0,40}(regra|instruc)|esqueca.{0,30}(regra|instruc)|"
        r"instrucao para assistentes|revele.{0,25}(prompt|segredo)|sou o dono", normalize(text)))


def validate_base(data: object) -> list[Unit]:
    """Rejeita artefato incompleto, ambíguo ou não revisado antes do runtime."""
    if not isinstance(data, list) or not data:
        raise ValueError("A base deve ser uma lista não vazia")
    keys = set(Unit.__annotations__)
    identifiers: set[str] = set()
    source_metadata: dict[str, tuple] = {}
    for unit in data:
        if not isinstance(unit, dict) or set(unit) != keys:
            raise ValueError("Esquema de unidade inválido")
        if any(not isinstance(unit[key], str) or not unit[key].strip()
               for key in keys - {"prioridade"}):
            raise ValueError("Campo textual ausente ou inválido")
        source = unit["fonte"]
        registry = SOURCES
        if source not in registry or unit["status"] != "vigente":
            raise ValueError("Fonte não autorizada ou obsoleta")
        if unit["area"] != registry[source] or type(unit["prioridade"]) is not int or unit["prioridade"] != priority(source):
            raise ValueError("Área ou autoridade inválida")
        if unit["id"] != section_id(source, unit["secao"]) or unit["id"] in identifiers:
            raise ValueError("ID inválido ou duplicado")
        identifiers.add(unit["id"])
        if not re.fullmatch(r"\d+\.\d+", unit["versao"]):
            raise ValueError("Versão inválida")
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", unit["atualizado_em"]):
            raise ValueError("Data inválida")
        date.fromisoformat(unit["atualizado_em"])
        if not re.fullmatch(r"[a-f0-9]{64}", unit["sha256"]):
            raise ValueError("Hash de origem inválido")
        metadata = tuple(unit[key] for key in ("versao", "atualizado_em", "sha256", "titulo", "area"))
        if source in source_metadata and source_metadata[source] != metadata:
            raise ValueError("Metadados conflitantes para a mesma fonte")
        source_metadata[source] = metadata
        if forbidden_content(" ".join(unit[key] for key in keys - {"prioridade"})):
            raise ValueError("Conteúdo instrucional proibido")
        if source == FAQ_SOURCE and (unit["secao"] not in FAQ_SECTIONS or
                                    "cancel" in normalize(unit["texto"])):
            raise ValueError("Seção ou conteúdo do FAQ não revisado")
        if source == POLICY_SOURCE:
            if unit["versao"] != "2.0" or unit["atualizado_em"] != "2026-08-01":
                raise ValueError("A política oficial deve ser v2 de 01/08/2026")
            text = normalize(unit["texto"])
            if unit["secao"] == "Como reservar" and not (
                    "no minimo 2 horas" in text and "30 dias" in text):
                raise ValueError("Antecedencia de reserva conflitante")
            if unit["secao"] == "Sinal" and ("30%" not in text or "50%" in text):
                raise ValueError("Regra do sinal conflitante")
            if unit["secao"] == "Cancelamento" and ("24 horas" not in text or "12 horas" in text):
                raise ValueError("Regra de cancelamento conflitante")
    if set(SOURCES) != set(source_metadata):
        raise ValueError("Base incompleta: falta fonte vigente")
    return data


def load_base(path: Path = BASE_PATH) -> list[Unit]:
    """Não lê Markdown nem precisa de acesso à AWS."""
    try:
        return validate_base(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError, TypeError) as exc:
        raise ValueError("Base JSON inválida ou indisponível") from None


def source_hash(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()
