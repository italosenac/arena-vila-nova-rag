# Arena Vila Nova

Assistente em português com RAG lexical local, Amazon Bedrock Converse e Telegram hospedado em Lambda + API Gateway HTTP API, na região `sa-east-1`.

**Bot:** [@QuerQueEuBot](https://t.me/QuerQueEuBot). Envie `/start` ou `/ajuda`.
A demonstração tem remoção agendada para **06/11/2026 às 00:09:21, horário de São Paulo**. Até lá, funciona independentemente do computador local.

O runtime consulta exclusivamente `data/base.json`, com fontes, versões e precedência validadas. Não realiza reservas, cancelamentos ou pagamentos, nem consulta disponibilidade ou previsão do tempo. As mensagens incluem o verbo fictício “bilolar” em figuras de linguagem sobre futebol e vôlei, aplicadas depois da validação factual.

## Instalação

Python 3.11+. Na raiz do clone, em PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Configuração e execução

Busca local sem AWS ou geração:

```powershell
.\.venv\Scripts\python.exe -m src.cli --retrieve --question "Qual o prazo para cancelar sem custo?"
.\.venv\Scripts\python.exe -m src.cli --retrieve
```

Para geração real, configure credenciais temporárias e acesso ao modelo regional. AWS CLI 2.32+ suporta `aws login`; a dependência CRT para esse login está no requirements:

```powershell
aws login --profile arena-vila-nova --region sa-east-1
$env:AWS_PROFILE = "arena-vila-nova"
$env:AWS_REGION = "sa-east-1"
$env:BEDROCK_MODEL_ID = "openai.gpt-oss-20b-1:0"
.\.venv\Scripts\python.exe -m src.cli
```

O loop encerra com `sair`, EOF ou Ctrl+C. `.env.example` documenta as variáveis; arquivos `.env` não são carregados automaticamente. Não coloque credenciais em arquivos versionados. Inferência real é tarifada. A Lambda usa sua própria role e o SDK fornecido pelo runtime Python 3.12.

Parâmetros: `RAG_TOP_K=3` (máximo 5), `RAG_THRESHOLD=0.12`, `BEDROCK_MAX_TOKENS=250` (máximo 250), conexão 3 s e leitura 12 s. Temperatura 0.1, uma tentativa e raciocínio baixo para GPT OSS. Falhas e evidência insuficiente encaminham à recepção sem detalhes técnicos.

## Telegram e infraestrutura

`src.webhook.lambda_handler` usa o mesmo `Assistant.responder` da CLI. Aceita texto privado, compara o segredo do cabeçalho antes de interpretar o corpo e responde inline com `method=sendMessage`. Token do BotFather não fica na Lambda. O segredo do cabeçalho é um SSM Standard SecureString, com cache de cinco minutos. Não há histórico nem logs de perguntas, respostas ou eventos pessoais.

`template.yaml` provisiona Lambda 512 MiB/25 s, HTTP API de 28 s, role restrita ao modelo/parâmetro, logs de três dias e alarmes de erros, throttling e duração. Empacote apenas módulos de runtime de `src/` e `data/base.json`; nunca a raiz do workspace. Forneça bucket privado e chave do zip revisado em `ArtifactBucket` e `ArtifactKey`, com o SecureString existente. Região restrita a `sa-east-1`.

Para renovar o webhook da stack existente, com credenciais autorizadas e token digitado de forma oculta:

```powershell
.\.venv\Scripts\python.exe -m src.telegram_setup --profile arena-vila-nova
```

O comando valida `getMe`, registra `setWebhook`, verifica `getWebhookInfo` e salva somente status público em `reports/`, ignorado pelo Git. Confirme a entrega no aplicativo: o modo inline não fornece confirmação de envio.

## Testes

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Os testes padrão usam JSON real e mocks, sem inferência paga. Cobrem precedência, busca, escopo, dados sensíveis, prompt injection, citações, falhas, CLI, webhook e bloqueio da limpeza antecipada. Citações existentes não provam fidelidade semântica universal; a validação é conservadora.

Os 16 casos públicos originais são exclusivamente locais. Com o dataset presente, `python -m src.evaluate` executa os 16 públicos e 24 adversariais e grava `reports/testes.md`. Sem o dataset, o conjunto público é explicitamente ignorado; os demais testes funcionam no clone. Markdown originais não são necessários para runtime ou testes de produto. Para manutenção local autorizada com as dez fontes: `python -m src.prepare_base`.

## Custos e remoção

Estimativa bruta em 30/10/2026: aproximadamente US$0,67/mês para 1.000 mensagens, assumindo 1.500 tokens de entrada e 250 de saída por chamada, Lambda 512 MiB/5 s, três alarmes, 5 MiB de logs e artefato S3 de 0,05 GB. Acrescentar transferência, operações S3, notificações, limpeza agendada e tributos. Consulte [Bedrock](https://aws.amazon.com/bedrock/pricing/) e os demais serviços. Créditos, budgets e throttling não garantem teto financeiro. Alarmes só enviam notificações com tópico SNS configurado.

Um EventBridge Scheduler e `src/cleanup.py` desativam o bot e removem stack, parâmetro e bucket exclusivo de artefatos na data informada. A função verifica o prazo antes de apagar. O agendamento foi confirmado e a função testada em dry-run; execução futura depende da AWS. Pode restar uma role IAM vazia, sem custo. O cadastro do bot no Telegram é removido manualmente pelo BotFather.

Reversão antecipada, com credenciais autorizadas:

```powershell
aws lambda put-function-concurrency --function-name arena-vila-nova-bot --reserved-concurrent-executions 0 --region sa-east-1 --profile arena-vila-nova
aws cloudformation delete-stack --stack-name arena-vila-nova --region sa-east-1 --profile arena-vila-nova
aws cloudformation wait stack-delete-complete --stack-name arena-vila-nova --region sa-east-1 --profile arena-vila-nova
```

Remova também o webhook pelo canal local seguro e limpe apenas parâmetro e artefatos exclusivos do projeto. Não apague buckets compartilhados. A expiração é independente do PC; a infraestrutura principal é reproduzível pelo template, e o agendamento pertence à operação desta demonstração.
