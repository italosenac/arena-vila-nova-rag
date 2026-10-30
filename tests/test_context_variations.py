"""Paráfrases novas cobrem todas as seções originais, com recuperação real."""
import pytest
from src.knowledge import load_base
from src.retriever import Retriever

CASES = [
 ('Onde fica esse espaço de lazer esportivo?', '01-sobre-a-arena:quem-somos'),
 ('Como é a estrutura das quadras e dos vestiários?', '01-sobre-a-arena:estrutura'),
 ('Até que horas posso jogar num feriado?', '01-sobre-a-arena:horario-de-funcionamento'),
 ('Como entro em contato com vocês?', '01-sobre-a-arena:contato'),
 ('Qual o valor por hora do futsal e da areia?', '02-quadras-e-precos:tabela-de-precos-por-hora'),
 ('Se eu fechar duas horas seguidas tem abatimento?', '02-quadras-e-precos:reservas-de-duas-horas'),
 ('Minha turma tem várias pessoas, qual é a lotação permitida na areia?', '02-quadras-e-precos:capacidade'),
 ('Vocês alugam bola e raquetes? Quanto fica?', '02-quadras-e-precos:itens-adicionais'),
 ('Qual versão da política de reservas está valendo?', '03-reservas-e-cancelamento:introducao'),
 ('Por qual canal agendo meu jogo?', '03-reservas-e-cancelamento:como-reservar'),
 ('Tenho que adiantar uma entrada para segurar a quadra?', '03-reservas-e-cancelamento:sinal'),
 ('Se desistir, em quanto tempo recebo meu dinheiro de volta?', '03-reservas-e-cancelamento:cancelamento'),
 ('Se ninguém da turma aparecer, vai ter outra cobrança?', '03-reservas-e-cancelamento:nao-comparecimento'),
 ('Quero trocar meu jogo para outra data, quais condições?', '03-reservas-e-cancelamento:reagendamento'),
 ('Chegar depois do horário dá direito a jogar mais no final?', '03-reservas-e-cancelamento:atrasos'),
 ('Choveu forte na areia e a partida parou, como resolver?', '03-reservas-e-cancelamento:chuva-apenas-quadras-de-areia'),
 ('Dá para parcelar no crédito ou pagar no débito?', '04-pagamento:meios-aceitos'),
 ('A entrada da reserva pode ser em espécie?', '04-pagamento:pagamento-do-sinal'),
 ('Preciso de recibo e nota fiscal, como funciona?', '04-pagamento:comprovantes'),
 ('O atendente pede senha ou código de verificação pelo Telegram?', '04-pagamento:seguranca'),
 ('Vou com meus amigos: pode jogar de tênis ou de chuteira?', '05-regras-de-uso:calcados'),
 ('Vou com amigos, posso levar cachorro, vidro e churrasqueira?', '05-regras-de-uso:proibicoes'),
 ('Meu filho pode ir desacompanhado para a quadra?', '05-regras-de-uso:menores-de-idade'),
 ('Tem onde guardar mochila? Preciso levar cadeado?', '05-regras-de-uso:pertences'),
 ('Se alguém passar mal no local, há primeiros socorros?', '05-regras-de-uso:saude'),
 ('Quero jogar toda semana num horário fixo, qual plano?', '06-planos-mensalistas:o-que-e'),
 ('Para ser mensalista tem fidelidade e desconto?', '06-planos-mensalistas:condicoes'),
 ('Sou mensalista: perdi um jogo e queria reposição, como funciona?', '06-planos-mensalistas:faltas-e-reposicao'),
 ('Quero sair do plano mensal, quanto tempo antes preciso avisar?', '06-planos-mensalistas:cancelamento-do-plano'),
 ('Quero comemorar meu aniversário com a turma, como peço orçamento?', '07-eventos-e-campeonatos:eventos-e-aniversarios'),
 ('Como inscrevo minha equipe na competição de futsal?', '07-eventos-e-campeonatos:campeonato-interno-de-futsal'),
 ('Posso pagar o sinal por Pix ou cartão?', '08-faq-atendimento:como-pago-o-sinal'),
 ('A turma quer levar refrigerante em garrafa plástica, pode?', '08-faq-atendimento:posso-levar-bebidas'),
 ('Existe vestiário para trocar de roupa e guardar coisas?', '08-faq-atendimento:ha-vestiario'),
 ('Quais informações pessoais a recepção usa para o cadastro?', '09-privacidade-e-lgpd:dados-que-coletamos'),
 ('Para que vocês usam os dados dos clientes?', '09-privacidade-e-lgpd:finalidade'),
 ('Por quanto tempo meus dados ficam guardados?', '09-privacidade-e-lgpd:retencao'),
 ('Como solicito exclusão ou correção dos meus dados?', '09-privacidade-e-lgpd:direitos-do-titular'),
 ('É necessário mandar documento pessoal neste chat?', '09-privacidade-e-lgpd:atendimento-pelo-telegram'),
]

@pytest.fixture(scope='module')
def retriever():
    return Retriever(load_base())

@pytest.mark.parametrize('question,expected',CASES)
def test_new_phrasings_retrieve_original_evidence(retriever,question,expected):
    from src.policies import triage
    assert triage(question) is None
    assert expected in {h.unit['id'] for h in retriever.search(question)}

def test_mixed_question_contains_evidence_for_each_subject(retriever):
    hits=retriever.search('Posso pagar o sinal em dinheiro e jogar usando chuteira de trava?')
    ids={h.unit['id'] for h in hits}
    assert '04-pagamento:pagamento-do-sinal' in ids
    assert '05-regras-de-uso:calcados' in ids

def test_mixed_question_never_certifies_unsupported_half():
    from src.service import build_service
    from src.llm import Generation
    class Generator:
        def generate(self, *,question,context):
            return Generation('O sinal só pode ser pago por Pix ou cartão no site de reservas.',
                tuple(u['id'] for u in context if u['id']=='04-pagamento:pagamento-do-sinal'),'RESPONDER')
    answer=build_service(generator=Generator()).responder('Posso pagar o sinal em dinheiro e jogar usando chuteira de trava?')
    assert answer.status=='NAO_CONSTA'

@pytest.mark.parametrize('text,valid',[
    ('Chuteiras de trava não são permitidas. Use tênis de solado liso no futsal.',True),
    ('Não é permitido usar chuteira de trava no futsal.',True),
    ('Chuteiras de trava são proibidas, mas tênis de solado liso são permitidos no futsal.',True),
    ('Chuteiras de trava não são permitidas e tênis de solado liso são permitidos no futsal.',True),
    ('É permitido usar chuteira de trava no futsal.',False),
    ('Chuteiras de trava são permitidas no futsal.',False),
    ('Não é permitido vidro; chuteiras de trava são permitidas.',False),
])
def test_prohibitions_preserve_negation(text,valid):
    from src.policies import supported_answer
    unit=next(u for u in load_base() if u['secao']=='Calçados')
    assert supported_answer(text,(unit,)) is valid
