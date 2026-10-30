# Arena Vila Nova

Assistente acadêmico em português sobre quadras, preços, reservas, pagamentos,
regras, planos, eventos e privacidade de uma arena fictícia.

Telegram: [@QuerQueEuBot](https://t.me/QuerQueEuBot).

Python 3.11+, RAG lexical TF-IDF por seção e Amazon Bedrock Converse.
O runtime consulta exclusivamente `data/base.json`: nove fontes vigentes,
39 seções com origem, versão, data e precedência. CLI e webhook compartilham
o mesmo serviço. API Gateway HTTP API e Lambda permitem acesso sem PC ligado.

## Instalação e configuração

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
aws login --profile arena-vila-nova --region sa-east-1
$env:AWS_PROFILE="arena-vila-nova"
$env:AWS_REGION="sa-east-1"
$env:BEDROCK_MODEL_ID="openai.gpt-oss-20b-1:0"
```

A inferência exige credenciais e permissão `bedrock:InvokeModel` para o modelo
na região. `.env.example` descreve as variáveis; `.env` não é carregado
automaticamente. Nunca coloque credenciais no repositório.

## Execução e testes

```powershell
python -m src.cli
python -m src.cli --retrieve --question "Qual o percentual do sinal?"
python -m pytest -q
```

`sair` encerra a CLI. `--retrieve` e os testes com mocks não chamam a AWS.
Os testes públicos originais são locais; o clone contém testes essenciais,
paráfrases e casos adversariais independentes desses arquivos.

No Telegram, use `/start`, `/ajuda` ou uma pergunta livre. A navegação é
opcional e solicita apenas esclarecimentos pertinentes. Perguntas completas
recebem resposta direta. Nenhuma conversa é persistida.

## Implantação

```powershell
python -m src.package --output .local-tools/arena.zip
aws s3 cp .local-tools/arena.zip s3://SEU_BUCKET/arena.zip --profile arena-vila-nova
aws cloudformation deploy --template-file template.yaml --stack-name arena-vila-nova --parameter-overrides ArtifactBucket=SEU_BUCKET ArtifactKey=arena.zip --capabilities CAPABILITY_IAM --region sa-east-1 --profile arena-vila-nova
```

O bucket privado e o parâmetro SecureString `/arena-vila-nova/webhook-secret`
devem existir. O pacote valida ZIP, imports e JSON. Após atualizar, confirme
`UPDATE_COMPLETE` e compare `CodeSha256` da Lambda com o checksum do pacote.
O runtime usa boto3/botocore fornecidos pelo Python da Lambda.

Para configurar um bot novo, execute `python -m src.telegram_setup`: o token
é solicitado localmente com entrada oculta. Ele não fica na Lambda.
Para atualizar código de um bot existente, preserve seu webhook.
Verifique a entrega pelo aplicativo; HTTP 200 não comprova envio ao Telegram.

## Limitações e custos

Não efetua reservas ou cancelamentos, não consulta vagas nem previsão do tempo.
O site e contatos `.example` são fictícios. Informação ausente é encaminhada
à recepção. Dados sensíveis e tentativas de alterar instruções são bloqueados.
IDs, números e regras críticas são validados; isso reduz alucinações sem
garantir equivalência factual universal.

Bedrock, Lambda, API Gateway, S3 e monitoramento podem gerar cobranças.
Créditos não são garantia de cobertura; alarmes não bloqueiam gastos.
A instalação de demonstração tem remoção agendada para 06/11/2026 às
00:09:21 de São Paulo; esse agendamento externo não é criado pelo template.
Para remover a stack manualmente: `aws cloudformation delete-stack --stack-name arena-vila-nova --region sa-east-1 --profile arena-vila-nova`.
Artefatos, parâmetro e agendamento externos também exigem limpeza.
