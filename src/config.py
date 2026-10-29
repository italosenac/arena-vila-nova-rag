"""Configuração por ambiente; sem credenciais ou ID de modelo embutidos."""

from dataclasses import dataclass
import math
import os


@dataclass(frozen=True)
class Settings:
    region: str = "sa-east-1"
    model_id: str = ""
    top_k: int = 3
    threshold: float = 0.12
    max_tokens: int = 250
    connect_timeout: float = 3
    read_timeout: float = 12

    def __post_init__(self) -> None:
        if (not 1 <= self.top_k <= 5 or not math.isfinite(self.threshold) or not 0 <= self.threshold <= 1
                or not 1 <= self.max_tokens <= 250
                or not math.isfinite(self.connect_timeout) or not 0 < self.connect_timeout <= 5
                or not math.isfinite(self.read_timeout) or not 0 < self.read_timeout <= 20
                or not self.region.strip()):
            raise ValueError("Limites de configuração inválidos")

    @classmethod
    def from_env(cls) -> "Settings":
        try:
            return cls(region=os.getenv("AWS_REGION", "sa-east-1").strip(),
                       model_id=os.getenv("BEDROCK_MODEL_ID", "").strip(),
                       top_k=int(os.getenv("RAG_TOP_K", "3")),
                       threshold=float(os.getenv("RAG_THRESHOLD", "0.12")),
                       max_tokens=int(os.getenv("BEDROCK_MAX_TOKENS", "250")),
                       connect_timeout=float(os.getenv("BEDROCK_CONNECT_TIMEOUT", "3")),
                       read_timeout=float(os.getenv("BEDROCK_READ_TIMEOUT", "12")))
        except ValueError:
            raise ValueError("Configuração de ambiente inválida") from None
