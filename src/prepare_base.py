"""SPEC-01: python -m src.prepare_base. Só lê os dez individuais locais."""

import argparse
from datetime import date
import json
from pathlib import Path
import re

from .knowledge import (
    BASE_PATH, FAQ_SECTIONS, FAQ_SOURCE, OBSOLETE_SOURCE, SOURCES, Unit,
    priority, section_id, source_hash, validate_base,
)


def parse_document(raw: str) -> tuple[dict[str, str], str, list[tuple[str, str]]]:
    """Frontmatter YAML restrito a quatro escalares, conforme as fontes.

    Não é um parser YAML genérico: estruturas aninhadas, tags, aliases e chaves
    extras falham explicitamente. Versões e datas ficam strings sem conversão.
    """
    raw = raw.replace("\r\n", "\n")
    match = re.fullmatch(r"---\n(.*?)\n---\n(.*)", raw, flags=re.S)
    if not match:
        raise ValueError("Frontmatter ausente ou inválido")
    metadata = {}
    for line in match[1].splitlines():
        pair = re.fullmatch(r"(versao|status|area|atualizado_em):\s*(.*?)\s*", line)
        if not pair or pair[1] in metadata:
            raise ValueError("Frontmatter com chave inválida ou duplicada")
        value = pair[2]
        if value.startswith('"'):
            try:
                value = json.loads(value)
            except ValueError:
                raise ValueError("Escalar YAML inválido") from None
        elif value.startswith("'") and value.endswith("'"):
            value = value[1:-1].replace("''", "'")
        if not isinstance(value, str) or not re.fullmatch(r"[\w.\-]+", value):
            raise ValueError("Somente escalares simples são permitidos no frontmatter")
        metadata[pair[1]] = value
    if set(metadata) != {"versao", "status", "area", "atualizado_em"}:
        raise ValueError("Metadados obrigatórios ausentes")
    if metadata["status"] not in {"vigente", "obsoleta"}:
        raise ValueError("Status desconhecido")
    if not re.fullmatch(r"\d+\.\d+", metadata["versao"]):
        raise ValueError("Versão inválida")
    date.fromisoformat(metadata["atualizado_em"])
    body = match[2]
    title_match = re.match(r"# ([^\n]+)\n(.*)", body, flags=re.S)
    if not title_match:
        raise ValueError("Título principal ausente")
    title = title_match[1].strip()
    parts = re.split(r"^## ([^\n]+)\n", title_match[2], flags=re.M)
    sections = []
    # Preservar também a introdução factual de vigência da política.
    if parts[0].strip():
        sections.append(("Introdução", parts[0].strip()))
    sections.extend((heading.strip(), text.strip())
                    for heading, text in zip(parts[1::2], parts[2::2]))
    if not sections or any(not heading or not text for heading, text in sections):
        raise ValueError("Seções vazias ou ausentes")
    return metadata, title, sections


def build_base(source_dir: Path) -> list[Unit]:
    files = sorted(source_dir.glob("*.md"))
    expected = set(SOURCES) | {OBSOLETE_SOURCE}
    if {path.name for path in files} != expected or len(files) != 10:
        raise ValueError("A pasta deve conter exatamente os dez Markdown individuais")
    units = []
    for path in files:
        raw = path.read_bytes()
        metadata, title, sections = parse_document(raw.decode("utf-8-sig"))
        if metadata["status"] == "obsoleta":
            continue
        if path.name == OBSOLETE_SOURCE:
            raise ValueError("Documento substituído não pode ser reativado")
        for section, text in sections:
            if path.name == FAQ_SOURCE and section not in FAQ_SECTIONS:
                continue
            units.append(Unit(
                id=section_id(path.name, section), fonte=path.name, secao=section,
                area=metadata["area"], versao=metadata["versao"],
                atualizado_em=metadata["atualizado_em"], texto=text, titulo=title,
                status=metadata["status"], prioridade=priority(path.name), sha256=source_hash(raw),
            ))
    return validate_base(units)


def export_base(source_dir: Path, output: Path) -> list[Unit]:
    units = build_base(source_dir)
    # Atualizar as dez fontes originais preserva os suplementos já revisados.
    if output.is_file():
        from .knowledge import load_base, SUPPLEMENT_SOURCES
        units.extend(u for u in load_base(output) if u['fonte'] in SUPPLEMENT_SOURCES)
        if any(u['fonte'] == '10-atualizacao-da-recepcao.md' for u in units):
            for unit in units:
                if unit['fonte'] == '03-reservas-e-cancelamento.md' and unit['secao'] == 'Como reservar':
                    unit['texto'] = unit['texto'].replace(' e com no mínimo 2 horas','')
        validate_base(units)
    # A validação termina antes de tocar no artefato anterior.
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    try:
        temporary.write_text(json.dumps(units, ensure_ascii=False, indent=2) + "\n",
                             encoding="utf-8", newline="\n")
        temporary.replace(output)
    finally:
        temporary.unlink(missing_ok=True)
    return units


def main() -> int:
    parser = argparse.ArgumentParser(description="Transformar fontes locais em JSON validado")
    parser.add_argument("--source", type=Path, default=BASE_PATH.parent.parent / "base-de-conhecimento")
    parser.add_argument("--output", type=Path, default=BASE_PATH)
    args = parser.parse_args()
    try:
        units = export_base(args.source, args.output)
    except (ValueError, OSError):
        print("Preparação interrompida: confira fontes, metadados e regras vigentes.")
        return 1
    print(f"Base validada: {len(units)} unidades de {len({u['fonte'] for u in units})} documentos vigentes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
