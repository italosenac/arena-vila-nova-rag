"""TF-IDF esparso de palavras e n-gramas, somente biblioteca padrão."""

from collections import Counter
from dataclasses import dataclass
import math
import re
from functools import lru_cache

from .knowledge import Unit, normalize, validate_base
from .language import expand_question, has_arena_concept, question_parts


STOP = set("a o as os de da do das dos e ou em no na nos nas para por com um uma que se ao ate qual quais como posso voces me eu meu minha tem quanto dia jogo partida fazer isso".split())
SYNONYMS = {
    "cancelar": "cancelamento", "cancele": "cancelamento", "desmarcar": "cancelamento",
    "desistir": "cancelamento", "desmarco": "cancelamento",
    "remarcar": "reagendamento", "reagendar": "reagendamento", "remarcacao": "reagendamento",
    "faltar": "comparecimento", "aparecer": "comparecimento", "comparecer": "comparecimento",
    "valor": "preco", "valores": "preco", "precos": "preco",
    "custa": "preco", "custam": "preco", "custo": "preco",
    "lotacao": "capacidade", "cabem": "capacidade", "pessoas": "pessoa",
    "chover": "chuva", "chovendo": "chuva", "beach": "areia",
    "pagar": "pagamento", "pago": "pagamento", "pagamentos": "pagamento",
    "abrem": "funcionamento", "abre": "funcionamento", "abertura": "funcionamento",
    "sabados": "sabado", "domingos": "domingo", "quadras": "quadra",
    "reservar": "reserva", "reservas": "reserva", "travas": "trava",
    "chuteiras": "chuteira", "proibidas": "proibido", "proibida": "proibido", "proibidos": "proibido",
}


def tokens(text: str) -> list[str]:
    value = normalize(text)
    value = re.sub(r"\bsem (?:custos?|pagar(?: nada)?)\b|\bgratis\b", "gratuito", value)
    if re.search(r"mudar (?:a |o )?(?:data|dia|horario)", value):
        value += " reagendamento"
    if (re.search(r"\b(aqui|chat|telegram)\b", value) and
            re.search(r"reserv|cancel", value)):
        value += " site recepcao telegram"
    return [SYNONYMS.get(word, word) for word in re.findall(r"[a-z0-9]+", value)
            if word not in STOP]


def features(words: list[str]) -> Counter:
    result = Counter("w:" + word for word in words)
    result.update("b:" + a + ":" + b for a, b in zip(words, words[1:]))
    for word in words:
        padded = " " + word + " "
        for size in (3, 4):
            result.update("c:" + padded[i:i + size] for i in range(len(padded) - size + 1))
    return result


@dataclass(frozen=True)
class Hit:
    unit: Unit
    score: float


def vectorize(count: Counter, idf: dict[str,float]) -> dict[str,float]:
    weighted = {key:(1+math.log(value))*idf[key]*(0.2 if key.startswith('c:') else 1)
                for key,value in count.items() if key in idf}
    norm = math.sqrt(sum(value*value for value in weighted.values()))
    return {key:value/norm for key,value in weighted.items()} if norm else {}


@lru_cache(maxsize=6)
def _index(documents: tuple[str,...]):
    """Cache apenas do corpus público; nunca recebe perguntas ou preferências."""
    words = [tokens(text) for text in documents]
    counts = [features(row) for row in words]
    frequency = Counter(feature for count in counts for feature in count)
    idf = {feature:1+math.log((1+len(counts))/(1+count)) for feature,count in frequency.items()}
    return idf,tuple(vectorize(count,idf) for count in counts),frozenset(w for row in words for w in row)


class Retriever:
    def __init__(self, base: list[Unit], *, top_k: int = 3, threshold: float = 0.12):
        if type(top_k) is not int or not 1 <= top_k <= 5 or not math.isfinite(threshold) or not 0 <= threshold <= 1:
            raise ValueError("Configuração de recuperação inválida")
        # Cópias próprias impedem que o chamador altere os dados já validados.
        self.units = tuple(dict(unit) for unit in validate_base(base))
        self.top_k, self.threshold = top_k, threshold
        self.indexes = {}
        self.word_vocabulary = set()
        for domain in ('arena','esporte','conversa'):
            units = tuple(u for u in self.units if (u['area'] if u['area'] in {'esporte','conversa'} else 'arena') == domain)
            idf,vectors,vocabulary = _index(tuple(f"{u['secao']} {u['secao']} {u['titulo']} {u['texto']}" for u in units))
            self.indexes[domain] = (units,idf,vectors)
            self.word_vocabulary.update(vocabulary)

    def search(self, question: str) -> list[Hit]:
        parts=question_parts(question)
        if len(parts)==1:
            return self._rank(question)
        ranked=[self._rank(part) for part in parts]
        selected={hits[0].unit['id']:hits[0] for hits in ranked if hits}
        for hit in sorted((h for hits in ranked for h in hits),key=lambda h:-h.score):
            if len(selected)>=self.top_k:
                break
            selected.setdefault(hit.unit['id'],hit)
        return list(selected.values())[:self.top_k]

    def _rank(self, question: str) -> list[Hit]:
        value = normalize(question)
        words = tokens(expand_question(question))
        if not set(words) & self.word_vocabulary:
            return []
        hits = []
        monthly = bool(re.search(r"mensal|plano|horario fixo", normalize(question)))
        cancellation = "cancelamento" in words
        advice = value.startswith('aconselhe um encontro esportivo') or (bool(re.search(r'aconselh|organiz|resenha|amig|night|conviv|iniciante|treino|preferencia', value)) and not has_arena_concept(question) and not bool(re.search(r'preco|pagamento|cancel|sinal|quanto custa|capacidade|lotacao|orcamento|evento|campeonato',value)))
        sport = bool(re.search(r'\b(?:jogadores?|pontos|sets?|toques|impedimento)\b|regra.{0,20}oficia|duracao.{0,20}(?:futebol|futsal)|medidas oficiais', value)) and not bool(re.search(r'arena|preco|custa|capacidade|lotacao|reserva',value))
        beach = bool(re.search(r'praia|areia|beach', value))
        domain = 'conversa' if advice else 'esporte' if sport else 'arena'
        units,idf,vectors = self.indexes[domain]
        query = vectorize(features(words),idf)
        for unit, vector in zip(units, vectors):
            if (unit['fonte'] == '03-reservas-e-cancelamento.md' and unit['secao'] == 'Como reservar'
                    and any(u['fonte'] == '10-atualizacao-da-recepcao.md' for u in units)
                    and re.search(r'anteced|minim|30 minuto|duas horas|2 horas',value)):
                continue  # A atualização substitui apenas a antecedência mínima da nova reserva.
            if advice:
                if unit['area'] != 'conversa':
                    continue
            elif sport:
                if unit['area'] != 'esporte':
                    continue
                subject = normalize(unit['titulo']+' '+unit['fonte'])
                if 'futsal' in value and 'futsal' not in subject:
                    continue
                if 'volei' in value and (('beach' in subject) != beach or 'futsal' in subject or 'theifab' in subject):
                    continue
                if 'futebol' in value and 'theifab' not in subject:
                    continue
            elif unit['area'] in {'esporte','conversa'} or unit['secao'] == 'Panorama da arena':
                continue
            # Elegibilidade por assunto antecede score e evita misturar plano/avulso.
            if cancellation and ((not monthly and unit["fonte"] == "06-planos-mensalistas.md") or
                                 (monthly and unit["fonte"] == "03-reservas-e-cancelamento.md")):
                continue
            score = sum(value * vector.get(key, 0) for key, value in query.items())
            section_words = set(tokens(unit['secao']))
            if score > 0 and domain == 'arena' and section_words:
                score += 0.12 * len(section_words & set(words)) / len(section_words)
            if unit["prioridade"] == 100:
                score *= 0.65  # FAQ complementar, não autoridade por correspondência literal.
            if score > 0 and score >= self.threshold:
                hits.append(Hit(dict(unit), min(score, 1.0)))
        return sorted(hits, key=lambda hit: (-hit.score, hit.unit["id"]))[:self.top_k]
