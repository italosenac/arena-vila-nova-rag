# Arena Vila Nova

Assistente informativo em Python 3.11+, com recuperação lexical TF-IDF local e geração pelo Amazon Bedrock. O runtime usa somente `data/base.json`, com versões e precedência revisadas. Não realiza reservas, cancelamentos ou pagamentos, nem consulta disponibilidade ou clima.

## Instalação

Na raiz do projeto, em PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Configuração

`.env.example` documenta as variáveis; arquivos `.env` **não são carregados automaticamente**. Configure o ambiente da sessão:

```powershell
$env:AWS_REGION = "sa-east-1"
$env:BEDROCK_MODEL_ID = "ID_CONFIRMADO_PARA_SUA_CONTA"
```

Use credenciais temporárias pelo mecanismo padrão da AWS, por exemplo um perfil autenticado via AWS CLI/SSO; em Lambda, use a role de execução. Não coloque chaves ou tokens no código. Não há modelo padrão: catálogo, permissões, compatibilidade Converse e custo devem ser conferidos antes de escolher um ID.

Parâmetros: `RAG_TOP_K=3` (máximo 5), `RAG_THRESHOLD=0.12`, `BEDROCK_MAX_TOKENS=250` (máximo 250), `BEDROCK_CONNECT_TIMEOUT=3` e `BEDROCK_READ_TIMEOUT=12` segundos. Geração usa temperatura 0.1 e uma tentativa total, sem repetição automática.

## Execução

Busca local, sem chamar AWS ou gerar respostas artificiais:

```powershell
.\.venv\Scripts\python.exe -m src.cli --retrieve --question "Qual o prazo para desmarcar sem custo?"
.\.venv\Scripts\python.exe -m src.cli --retrieve
```

Geração real, **somente após autorização de custos**, com modelo e credenciais configurados:

```powershell
.\.venv\Scripts\python.exe -m src.cli
```

O loop encerra com `sair`, EOF ou Ctrl+C. Falta de configuração, credencial ou indisponibilidade produz aviso de erro, sem fingir geração real. O serviço compartilhado é `Assistant.responder(pergunta)`; o webhook Telegram será implementado em etapa posterior.

## Testes

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Os testes usam o JSON real e geradores/clientes falsos, sem credenciais nem inferência paga. Cobrem base, precedência, busca com paráfrases, escopo, ataques, dados sensíveis, citações, falhas do SDK e CLI. São distintos da avaliação real do Bedrock.

Para executar os 16 casos públicos e 24 casos novos, com o dataset original disponível **somente localmente**:

```powershell
.\.venv\Scripts\python.exe -m src.evaluate
```

O comando executa os testes de avaliação e grava `reports/testes.md`, ignorado pelo Git, incluindo falhas e sua etapa. As respostas factuais são mocks que exigem contexto recuperado compatível; aprovação não atesta geração real. Sem o dataset no clone, apenas o conjunto público é explicitamente não executado; os testes de produto e adversariais continuam independentes dos originais. A avaliação pública retorna erro se o arquivo local estiver ausente.

Não há histórico persistido nem logging de perguntas, respostas ou eventos. IDs citados precisam pertencer aos trechos recuperados, e a saída passa por checagens de conteúdo. Isso reduz riscos, mas não garante equivalência semântica universal; incerteza leva à recepção.

## Manutenção

Um clone funciona com o JSON publicado e não precisa dos Markdown originais. Para manutenção local com os dez arquivos em `base-de-conhecimento/`: `python -m src.prepare_base` atualiza a base após validação. Originais, SPECs, perguntas públicas e relatórios permanecem locais e fora do GitHub.

O adaptador segue o contrato oficial de [Bedrock Converse](https://docs.aws.amazon.com/boto3/latest/reference/services/bedrock-runtime/client/converse.html). Nenhum recurso AWS é criado por estes comandos; a execução com modelo configurado realiza inferência tarifada.

`template.yaml` é um plano CloudFormation para `sa-east-1`: HTTP API, Lambda, role restrita, logs de três dias e alarmes. Propõe `mistral.ministral-3-3b-instruct`; geração real ainda exige validação autorizada. O handler `src.webhook.lambda_handler` ainda não existe: **o template ainda não deve ser implantado**. Exige zip revisado em bucket privado e parâmetro SecureString existentes; não empacote a raiz do workspace. A integração Telegram está pendente: o token do BotFather deve permanecer local, fora do Git, e o segredo do cabeçalho ficará no Parameter Store. Alarmes só notificam se receberem um tópico SNS existente configurado.

Estimativa bruta em 29/10/2026: aproximadamente US$0,67/mês para 1.000 mensagens (1.500 tokens de entrada e 250 de saída por mensagem; Lambda 512 MiB por 5 segundos; três alarmes, 5 MiB de logs e artefato S3 de 0,05 GB). Acrescentar transferência, operações S3, notificações e tributos. Crédito não garante gratuidade; budgets e throttling não são bloqueios rígidos. Consulte os preços de [Bedrock](https://aws.amazon.com/bedrock/pricing/) e dos demais serviços antes de implantar.

Validação local opcional da infraestrutura: `python -m pip install cfn-lint` e `cfn-lint template.yaml`; os testes verificam as restrições principais sem AWS. Nenhum deploy, inferência real ou registro de webhook foi executado. Para reversão futura da stack planejada: `aws cloudformation delete-stack --stack-name arena-vila-nova --region sa-east-1` e `aws cloudformation wait stack-delete-complete --stack-name arena-vila-nova --region sa-east-1`. Desative o webhook antes; parâmetro e artefato externos exigem limpeza separada e restrita ao projeto.
