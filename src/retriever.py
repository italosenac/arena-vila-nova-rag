"""TF-IDF esparso de palavras e n-gramas, somente biblioteca padrão."""

from collections import Counter
from dataclasses import dataclass
import math
import re

from .knowledge import Unit, normalize, validate_base


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


class Retriever:
    def __init__(self, base: list[Unit], *, top_k: int = 3, threshold: float = 0.12):
        if type(top_k) is not int or not 1 <= top_k <= 5 or not math.isfinite(threshold) or not 0 <= threshold <= 1:
            raise ValueError("Configuração de recuperação inválida")
        # Cópias próprias impedem que o chamador altere os dados já validados.
        self.units = tuple(dict(unit) for unit in validate_base(base))
        self.top_k, self.threshold = top_k, threshold
        documents = [tokens(f"{u['secao']} {u['secao']} {u['titulo']} {u['texto']}") for u in self.units]
        counts = [features(words) for words in documents]
        frequency = Counter(feature for count in counts for feature in count)
        self.idf = {feature: 1 + math.log((1 + len(counts)) / (1 + count))
                    for feature, count in frequency.items()}
        self.vectors = [self._vector(count) for count in counts]
        self.word_vocabulary = {word for words in documents for word in words}

    def _vector(self, count: Counter) -> dict[str, float]:
        weighted = {key: (1 + math.log(value)) * self.idf[key] * (0.2 if key.startswith("c:") else 1)
                    for key, value in count.items() if key in self.idf}
        norm = math.sqrt(sum(value * value for value in weighted.values()))
        return {key: value / norm for key, value in weighted.items()} if norm else {}

    def search(self, question: str) -> list[Hit]:
        words = tokens(question)
        if not set(words) & self.word_vocabulary:
            return []
        query = self._vector(features(words))
        hits = []
        monthly = bool(re.search(r"mensal|plano|horario fixo", normalize(question)))
        cancellation = "cancelamento" in words
        for unit, vector in zip(self.units, self.vectors):
            # Elegibilidade por assunto antecede score e evita misturar plano/avulso.
            if cancellation and ((not monthly and unit["fonte"] == "06-planos-mensalistas.md") or
                                 (monthly and unit["fonte"] == "03-reservas-e-cancelamento.md")):
                continue
            score = sum(value * vector.get(key, 0) for key, value in query.items())
            if unit["prioridade"] == 100:
                score *= 0.65  # FAQ complementar, não autoridade por correspondência literal.
            if score > 0 and score >= self.threshold:
                hits.append(Hit(dict(unit), min(score, 1.0)))
        return sorted(hits, key=lambda hit: (-hit.score, hit.unit["id"]))[:self.top_k]
