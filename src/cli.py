"""CLI sem histórico: python -m src.cli; --retrieve não chama modelo."""

import argparse
from collections.abc import Callable

from .policies import triage
from .service import Assistant, build_service
from .concierge import QUESTIONS, recommendation_question, wants_advice


def main(argv: list[str] | None = None, *, factory: Callable[[], Assistant] = build_service) -> int:
    parser = argparse.ArgumentParser(description="Assistente da Arena Vila Nova")
    parser.add_argument("--question", help="Pergunta única")
    parser.add_argument("--retrieve", action="store_true", help="Somente IDs, fontes e scores; sem AWS")
    args = parser.parse_args(argv)
    service = None

    def respond(question: str) -> int:
        nonlocal service
        try:
            if service is None:
                service = factory()
            if args.retrieve:
                decision = triage(question)
                if decision:
                    print(decision[1])
                    return 0
                hits = service.retriever.search(question)
                print("Busca local, sem geração nem chamada AWS.")
                for hit in hits:
                    print(f"{hit.score:.3f} | {hit.unit['id']} | {hit.unit['fonte']}")
                if not hits:
                    print("Nenhuma evidência relevante.")
                return 0
            result = service.responder(question)
            print(result.text)
            if result.status == "ERRO":
                print("Geração indisponível: verifique configuração AWS, credenciais e acesso ao modelo. Use --retrieve para busca local.")
                return 1
            return 0
        except Exception:
            print("Atendimento indisponível. Verifique a configuração e a base local.")
            return 1

    if args.question is not None:
        return respond(args.question)
    print("Arena Vila Nova — digite sair para encerrar. Não envie dados pessoais.")
    try:
        while True:
            question = input("> ").strip()
            if question.casefold() == "sair":
                return 0
            if question:
                if wants_advice(question):
                    choices = []
                    for prompt,options in QUESTIONS:
                        print(prompt)
                        for index, option in enumerate(options,1):
                            print(f'{index}. {option}')
                        value = input('Opção (1–5; sair encerra): ').strip()
                        if value.casefold() == 'sair':
                            return 0
                        while value not in {'1','2','3','4','5'}:
                            value = input('Escolha 1, 2, 3, 4 ou 5: ').strip()
                            if value.casefold() == 'sair':
                                return 0
                        choices.append(int(value)-1)
                    question = recommendation_question(tuple(choices))
                respond(question)
    except (EOFError, KeyboardInterrupt):
        print()
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
