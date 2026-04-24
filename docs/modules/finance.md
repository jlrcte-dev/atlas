# Módulo Finance — v1.2

> **Status:** Implementado e encerrado. Audit técnico executado em Abril 2026.
> **Testes:** 71 Telegram + 49 REST + outros = 282 total. Suite completa: 282/282 passando.

---

## Objetivo

Reproduzir de forma simples e confiável a lógica de uma planilha de gerenciamento financeiro pessoal. Permite registrar receitas e despesas, conferir saldos por conta e gerar um resumo consolidado por mês.

---

## Estrutura do Módulo

```
app/
├── db/
│   ├── models.py                  # Account, MonthlyClosing, FinancialEntry, AccountBalanceSnapshot
│   └── repositories.py            # AccountRepository, MonthlyClosingRepository,
│                                  # FinancialEntryRepository, AccountBalanceSnapshotRepository
├── core/
│   └── exceptions.py              # FinanceError e subclasses (6 exceções)
├── modules/
│   └── finance/
│       ├── __init__.py
│       ├── schemas.py             # Pydantic v2 — Create/Update/Response por entidade
│       ├── service.py             # FinanceService — toda a lógica de negócio
│       └── telegram.py            # Parser + formatter Telegram (sem estado, sem I/O)
└── api/rest/
    └── finance_routes.py          # APIRouter(prefix="/finance") — 13 endpoints
```

---

## Entidades

### Account
Conta financeira usada para conferência manual de saldo.

| Campo | Tipo SQLite | Tipo Python | Descrição |
|---|---|---|---|
| id | INTEGER PK | int | Identificador único |
| name | VARCHAR(120) | str | Nome da conta (ex: Nubank) |
| institution | VARCHAR(120) | str | Instituição (ex: Nu Pagamentos) |
| is_active | BOOLEAN | bool | Se a conta está ativa |
| created_at | DATETIME | datetime | Criação (UTC) |
| updated_at | DATETIME | datetime | Última atualização (UTC) |

### MonthlyClosing
Registro do saldo inicial do mês. **Máximo de um por mês** — regra de integridade crítica.

| Campo | Tipo SQLite | Tipo Python | Descrição |
|---|---|---|---|
| id | INTEGER PK | int | Identificador único |
| month_ref | VARCHAR(7) UNIQUE | str | Mês no formato YYYY-MM |
| initial_balance | NUMERIC(14,2) | Decimal | Saldo no início do mês |
| notes | TEXT | str\|None | Observações |
| created_at | DATETIME | datetime | Criação (UTC) |
| updated_at | DATETIME | datetime | Última atualização (UTC) |

Unicidade garantida por `UniqueConstraint` na tabela e `unique=True` na coluna. Violação capturada via `IntegrityError` no repository → `FinanceDuplicateClosingError`.

### FinancialEntry
Lançamento de receita ou despesa.

| Campo | Tipo SQLite | Tipo Python | Descrição |
|---|---|---|---|
| id | INTEGER PK | int | Identificador único |
| description | VARCHAR(300) | str | Descrição do lançamento |
| amount | NUMERIC(14,2) | Decimal | Valor |
| type | VARCHAR(20) | str | `income` ou `expense` |
| status | VARCHAR(20) | str | `settled` ou `pending` |
| month_ref | VARCHAR(7) | str | Mês de referência YYYY-MM |
| category | VARCHAR(100) | str\|None | Categoria livre |
| due_date | VARCHAR(10) | str\|None | Vencimento (YYYY-MM-DD) |
| settlement_date | VARCHAR(10) | str\|None | Liquidação (YYYY-MM-DD) |
| is_investment | BOOLEAN | bool | Se é aporte/investimento |
| notes | TEXT | str\|None | Observações |
| created_at | DATETIME | datetime | Criação (UTC) |
| updated_at | DATETIME | datetime | Última atualização (UTC) |

### AccountBalanceSnapshot
Fotografia manual do saldo de uma conta em um mês. **Máximo de um snapshot por conta por mês.**

| Campo | Tipo SQLite | Tipo Python | Descrição |
|---|---|---|---|
| id | INTEGER PK | int | Identificador único |
| account_id | INTEGER FK | int | FK para `finance_accounts.id` |
| month_ref | VARCHAR(7) | str | Mês de referência YYYY-MM |
| balance | NUMERIC(14,2) | Decimal | Saldo fotografado manualmente |
| reference_date | VARCHAR(10) | str\|None | Data da fotografia (YYYY-MM-DD) |
| notes | TEXT | str\|None | Observações |
| created_at | DATETIME | datetime | Criação (UTC) |
| updated_at | DATETIME | datetime | Última atualização (UTC) |

Unicidade garantida por `UniqueConstraint("account_id", "month_ref")`. Violação → `FinanceDuplicateSnapshotError`.

---

## Regras de Negócio

### Totais do resumo
```
expenses_paid     = soma de lançamentos type=expense + status=settled
expenses_pending  = soma de lançamentos type=expense + status=pending
income_received   = soma de lançamentos type=income  + status=settled
income_pending    = soma de lançamentos type=income  + status=pending
```

### Saldo atual
```
current_balance = initial_balance + income_received - expenses_paid
```

### Saldo final projetado
```
projected_final_balance = current_balance + income_pending - expenses_pending
```

### Conferência
```
conference_total      = soma dos saldos dos snapshots do mês
conference_difference = conference_total - current_balance
```

`conference_difference = 0` → saldos reais batem com o calculado.

---

## Validações Aplicadas

| Campo | Validação | Onde |
|---|---|---|
| `month_ref` | Regex `^\d{4}-\d{2}$` | Schema Pydantic + `_validate_month_ref()` no service |
| `type` | Deve ser `income` ou `expense` | Schema Pydantic (`field_validator`) |
| `status` | Deve ser `settled` ou `pending` | Schema Pydantic (`field_validator`) |
| Unicidade MonthlyClosing | `IntegrityError` → `FinanceDuplicateClosingError` | Repository |
| Unicidade Snapshot | `IntegrityError` → `FinanceDuplicateSnapshotError` | Repository |
| Fechamento ausente | `FinanceMissingClosingError` antes do resumo | Service |
| Recurso não encontrado | `FinanceNotFoundError` em qualquer PATCH/DELETE | Service |
| Account válida no snapshot | Verificação explícita antes de criar snapshot | Service |

---

## Endpoints

### Contas
| Método | Rota | Status | Descrição |
|---|---|---|---|
| GET | /finance/accounts | 200 | Lista todas as contas |
| POST | /finance/accounts | 201 | Cria uma conta |
| PATCH | /finance/accounts/{id} | 200 | Atualiza nome/instituição/status |

### Fechamento Mensal
| Método | Rota | Status | Descrição |
|---|---|---|---|
| GET | /finance/monthly-closing?month=YYYY-MM | 200 | Busca o fechamento do mês |
| POST | /finance/monthly-closing | 201 | Registra saldo inicial |
| PATCH | /finance/monthly-closing/{id} | 200 | Atualiza saldo inicial ou notas |

### Lançamentos
| Método | Rota | Status | Descrição |
|---|---|---|---|
| GET | /finance/entries?month=YYYY-MM | 200 | Lista lançamentos do mês |
| POST | /finance/entries | 201 | Cria um lançamento |
| PATCH | /finance/entries/{id} | 200 | Atualiza um lançamento |
| DELETE | /finance/entries/{id} | 204 | Remove um lançamento |

### Saldos de Contas
| Método | Rota | Status | Descrição |
|---|---|---|---|
| GET | /finance/account-balances?month=YYYY-MM | 200 | Lista snapshots do mês |
| POST | /finance/account-balances | 201 | Registra snapshot manual |
| PATCH | /finance/account-balances/{id} | 200 | Atualiza saldo do snapshot |

### Resumo Mensal
| Método | Rota | Status | Descrição |
|---|---|---|---|
| GET | /finance/monthly-summary?month=YYYY-MM | 200 | Resumo consolidado |

---

## Exceções

Todas herdam de `FinanceError` → `AtlasError`. Capturadas pelo handler global de `main.py` → HTTP 400 com `{"error": "CÓDIGO", "message": "..."}`.

| Código | Classe | Situação |
|---|---|---|
| `FINANCE_NOT_FOUND` | `FinanceNotFoundError` | ID inexistente em PATCH/DELETE |
| `FINANCE_INVALID_MONTH_REF` | `FinanceInvalidMonthRefError` | `month_ref` fora do padrão YYYY-MM |
| `FINANCE_MISSING_CLOSING` | `FinanceMissingClosingError` | Resumo solicitado sem fechamento cadastrado |
| `FINANCE_DUPLICATE_CLOSING` | `FinanceDuplicateClosingError` | Segundo fechamento no mesmo mês |
| `FINANCE_DUPLICATE_SNAPSHOT` | `FinanceDuplicateSnapshotError` | Segundo snapshot da mesma conta no mesmo mês |

---

## Decisões Técnicas

### Decimal/Numeric para valores financeiros
Todos os campos de valor usam `Numeric(14, 2)` no SQLite e `Decimal` (Python) em toda a camada de aplicação. No `FinanceService.get_monthly_summary()`, os valores são normalizados via `Decimal(str(value))` antes da aritmética — proteção defensiva contra possível conversão `float` por variações do driver SQLite. Nenhum `float` é usado em nenhum cálculo financeiro.

### StaticPool no ambiente de testes
Adicionado `poolclass=StaticPool` ao `db_session` fixture em `tests/conftest.py`. SQLite in-memory com `QueuePool` (padrão SQLAlchemy) pode dar conexões distintas para `create_all()` e para a sessão do `TestClient` ASGI — resultando em tabelas ausentes em testes HTTP. `StaticPool` garante uma única conexão compartilhada. Não impacta os testes existentes.

### Router separado, registrado em main.py
O `finance_router` foi criado em `app/api/rest/finance_routes.py` em vez de adicionar endpoints ao `routes.py` existente. Isso mantém o módulo isolado sem poluir o arquivo de rotas existente. Impacto em `main.py`: +2 linhas.

### Unicidade dupla em MonthlyClosing
A coluna `month_ref` tem tanto `unique=True` (nível SQLAlchemy) quanto `UniqueConstraint` na `__table_args__` (nível DDL). O `unique=True` é suficiente funcionalmente; o `UniqueConstraint` nomeado torna a restrição explícita e auditável no schema. Ambos se traduzem para a mesma constraint no SQLite.

### `updated_at` setado manualmente nos repositories
A coluna `updated_at` usa `default=_utcnow` (valor de criação). Atualizações setam `obj.updated_at = datetime.now(UTC)` explicitamente nos métodos `update()` de cada repository. Isso é mais confiável e legível do que depender do `onupdate` do SQLAlchemy, que tem comportamento variável dependendo de como a sessão detecta mudanças.

---

## Integração Telegram (v1.2)

Quatro comandos disponíveis no bot do Telegram. Toda lógica financeira permanece no `FinanceService` — o Telegram é exclusivamente interface (parser + formatter).

### Arquitetura

```
Telegram message
    └─ webhook (POST /telegram/webhook)
        └─ Orchestrator.handle_request()
            └─ IntentClassifier          (identifica comando, preserva case dos args)
            └─ _handle_finance_*         (handler por intent)
                ├─ finance/telegram.py   (parse_* + format_* — sem estado, sem I/O)
                └─ FinanceService        (lógica de negócio — intacto)
```

**Separação de responsabilidades:**

| Camada | Arquivo | Responsabilidade |
|---|---|---|
| Entrada | `app/integrations/telegram_client.py` | Receber update, autorizar, despachar |
| Roteamento | `app/orchestrator/orchestrator.py` | Classificar intent, chamar handler |
| Parsing/Formatação | `app/modules/finance/telegram.py` | Interpretar args, formatar respostas |
| Negócio | `app/modules/finance/service.py` | Persistir, calcular, validar domínio |

### Comandos suportados

| Comando | Descrição | Exemplo |
|---|---|---|
| `/finance` | Resumo do mês atual | `/finance` |
| `/finance YYYY-MM` | Resumo de mês específico | `/finance 2026-04` |
| `/expense <valor> <descrição>` | Registrar despesa | `/expense 250 Mercado` |
| `/income <valor> <descrição>` | Registrar receita | `/income 5000 Salário` |
| `/balance <conta> <valor>` | Atualizar saldo da conta | `/balance XP 1850` |

### Formato de valores

> **v1.1** — `1.500` corrigido de silencioso para rejeitado explicitamente.
> **v1.2** — formato BR completo (`1.250,50`) aceito.

**Aceitos:**

| Entrada | Resultado |
|---|---|
| `1500` | `Decimal("1500")` |
| `1500.00` | `Decimal("1500.00")` |
| `1500,00` | `Decimal("1500.00")` |
| `250` | `Decimal("250")` |
| `250.00` | `Decimal("250.00")` |
| `250,00` | `Decimal("250.00")` |
| `1.500,00` | `Decimal("1500.00")` — BR milhar+decimal |
| `1.234,56` | `Decimal("1234.56")` — BR milhar+decimal |

**Rejeitados:**

- `1.500` — separador único com 3 dígitos: ambíguo (decimal US ou milhar BR?)
- `1,500` — separador único com 3 dígitos: ambíguo (decimal BR ou milhar US?)
- `1,250.50` — comma antes de ponto: formato US não suportado

**Mensagem para ambíguos:**

```
❌ Valor ambíguo. Use 1500, 1500.00 ou 1500,00.
```

**Lógica de detecção em `parse_amount` (v1.2):**

1. Se contém `.` **e** `,`: valida contra `^\d{1,3}(\.\d{3})*,\d{1,2}$` → aceita como BR ou rejeita
2. Se contém apenas `.` ou `,` e sufixo tem exatamente 3 dígitos → ambíguo → rejeita
3. Normaliza `,` → `.` e interpreta como `Decimal`

### Regras de parsing por comando

**`/expense` e `/income`:**

- Primeiro token = valor; restante = descrição
- Descrição é obrigatória; case preservado (`Atacadão`, `Salário CLT`)
- `month_ref` = mês atual; `due_date` e `settlement_date` = hoje
- Entrada criada com `status=settled`

**`/balance`:**

- Último token = valor; tudo antes = nome da conta (suporta nomes multi-palavra)
- Lookup por nome é case-insensitive (`nubank` encontra `Nubank`)
- Se já existe snapshot para `(conta, mês atual)`: **atualiza** o saldo (upsert)
- Se não existe: cria novo com `reference_date = hoje`

**`/finance`:**

- Sem argumento: mês atual (`datetime.now().strftime("%Y-%m")`)
- Com argumento: valida contra regex `^\d{4}-\d{2}$`

### Tratamento de erros

Nunca falham silenciosamente. Todas as mensagens começam com `❌`:

| Situação | Mensagem |
|---|---|
| Valor não numérico | `❌ Valor inválido. Use formato 250.00` |
| Valor ≤ 0 | `❌ Valor inválido. Use formato 250.00` |
| Valor ambíguo (`1.500`, `1,500`) | `❌ Valor ambíguo. Use 1500, 1500.00 ou 1500,00.` |
| Formato com ambos separadores | `❌ Valor ambíguo. Use 1500, 1500.00 ou 1500,00.` |
| Descrição ausente | `❌ Descrição obrigatória` |
| Conta inexistente no `/balance` | `❌ Conta não encontrada: <nome>` |
| Formato inválido no `/balance` | `❌ Formato inválido. Use: /balance <conta> <valor>` |
| `month_ref` fora do padrão YYYY-MM | `❌ Mês inválido. Use YYYY-MM` |
| Resumo sem fechamento cadastrado | `❌ Não existe fechamento para o mês informado` |

### Exemplos de resposta

**`/finance` (sucesso):**

```
📊 Financeiro — 2026-04

Saldo inicial: R$ 1.000,00
Recebido: R$ 3.000,00
A receber: R$ 500,00
Pago: R$ 800,00
A pagar: R$ 200,00

Saldo atual: R$ 3.200,00
Saldo final: R$ 3.500,00

Conferência: R$ 3.200,00
Diferença: R$ 0,00

Contas:
- Nubank: R$ 1.200,00
- XP: R$ 2.000,00
```

**`/expense` (sucesso):**

```
✅ Despesa registrada
R$ 250,00 — Atacadão
```

**`/income` (sucesso):**

```
✅ Receita registrada
R$ 8.000,00 — Salário
```

**`/balance` (sucesso):**

```
✅ Saldo registrado
XP — R$ 1.850,00
```

### Testes

`tests/test_finance_telegram.py` — 59 testes dedicados à integração Telegram.

| Grupo | Cobertura |
|---|---|
| `parse_amount` | Inteiro, ponto decimal, vírgula decimal, zeros, negativos, não numérico, ambíguos (`1.500`, `1,500`), milhar BR (`1.500,00`, `1.234,56`) |
| `parse_entry_args` | Descrição simples, multi-palavra, ausente, vazio, valor inválido |
| `parse_balance_args` | Conta simples, multi-palavra, valor ausente, vazio, valor inválido |
| `parse_month_ref` | None, vazio, espaços, válido, formato errado |
| `format_amount` | Pequeno, com milhar, zero, negativo |
| `IntentClassifier` | `/finance`, `/finance YYYY-MM`, `/expense`, `/income`, `/balance`, regressão `/approve` |
| Orchestrator `/finance` | Mês atual, mês específico, formato inválido, sem fechamento |
| Orchestrator `/expense` | Válido (persistência), sem descrição, valor inválido, sem args |
| Orchestrator `/income` | Válido (persistência, type=income) |
| Orchestrator `/balance` | Válido, case-insensitive, multi-palavra, conta inexistente, formato inválido, upsert |
| Integração E2E | Expense → summary, income → summary, balance → conferência |
| `format_summary` standalone | Exercício direto com `MonthlySummaryResponse` real |

### Menu Telegram (v1.2)

Menu principal inclui o módulo Finance como primeiro item:

```text
🏠 Atlas
[💰 Finanças]
[📥 Inbox] [📅 Agenda]
[📰 Noticias] [📑 Briefing]
[⏳ Pendencias]
```

Submenu Finance acessível via botão "💰 Finanças":

```text
💰 Finanças
[📊 Resumo do mês]
[➕ Como lançar despesa]
[➕ Como lançar receita]
[🏦 Como atualizar saldo]
[⬅️ Voltar]
```

**Callback data** (prefixos curtos, ≤ 64 bytes):

| Callback | Ação |
|---|---|
| `fin:menu` | Abre submenu Finance |
| `fin:sum` | Executa `/finance` (mês atual) |
| `fin:help_exp` | Mostra instruções do `/expense` |
| `fin:help_inc` | Mostra instruções do `/income` |
| `fin:help_bal` | Mostra instruções do `/balance` |
| `fin:back` | Volta ao menu principal |
| `main:menu` | Volta ao menu principal |

Callbacks `fin:menu`, `fin:help_*`, `fin:back`, `main:menu` são interceptados no webhook antes do orchestrator. `fin:sum` é traduzido para `/finance` pelo `_translate_callback()`.

### Limitações v1.2

Comportamentos deliberadamente fora do escopo desta versão:

- **Sem edição ou delete via Telegram** — operações destrutivas apenas via REST
- **Sem listagem de lançamentos** — apenas resumo agregado via `/finance`
- **Sem filtros** por categoria, tipo ou status
- **Sem fluxos multi-step ou inline keyboards**
- **Sem linguagem natural** — apenas slash commands estritamente tipados
- **Conta não criada automaticamente** — conta deve existir previamente (via REST)
- **Sem confirmação antes de registrar** — comandos executam imediatamente
- **Sem /undo** — desfazer requer uso da API REST
- **Single-user** — sem controle de acesso por usuário do Telegram

---

## Próximos passos (v2)

Funcionalidades identificadas para iteração futura:

- `/expenses` — listagem dos lançamentos do mês
- `/undo` — desfazer o último lançamento registrado
- Edição e deleção de lançamentos via Telegram
- NLP para entrada em linguagem natural ("gastei 250 no mercado")
- Inline keyboards para confirmação antes de registrar

---

## Audit Técnico

### Finance REST v1.1 (Abril 2026)

| Item | Resultado | Detalhe |
|---|---|---|
| Precisão financeira | ✅ OK | `Numeric(14,2)` nos 3 modelos; `Decimal(str(v))` no service; zero `float` |
| Unicidade MonthlyClosing | ✅ OK | `UniqueConstraint` + `unique=True` + `IntegrityError` → rollback explícito |
| Unicidade Snapshot | ✅ OK | `UniqueConstraint(account_id, month_ref)` + `IntegrityError` → rollback |
| Fórmulas do resumo | ✅ OK | Aderentes à spec em `service.py` |
| Erros explícitos | ✅ OK | 5 exceções com código estruturado; handler global HTTP 400 |
| Naming | ✅ OK | Código inglês, mensagens português, consistente com o projeto |
| Estrutura do módulo | ✅ OK | models → repositories → schemas → service → routes |
| Inicialização do app | ✅ OK | 2 linhas em `main.py`; tabelas auto-criadas; zero impacto no lifespan |
| Cobertura de testes | ✅ OK | 49 testes REST; cenários críticos cobertos |
| Regressão | ✅ ZERO | Suite completa passando |

### Finance + Telegram v1.1 (Abril 2026)

| Item | Resultado | Detalhe |
|---|---|---|
| Bug crítico `parse_amount("1.500")` | ✅ CORRIGIDO | Era aceito como `R$ 1,50`; agora rejeitado com mensagem explícita |
| Separação parser/service | ✅ OK | `telegram.py` sem estado, sem I/O; `FinanceService` intacto |
| Decimal end-to-end | ✅ OK | Parser → handler → service sem conversão float |
| Case preservation | ✅ OK | `/expense 250 Atacadão` preserva "Atacadão" |
| Upsert de snapshot | ✅ OK | `/balance` repetido atualiza em vez de duplicar |
| Erros em português | ✅ OK | Todas as mensagens `❌` claras e sem stack trace |
| Cobertura de testes | ✅ OK | 59 testes Telegram; parser, formatter, classifier, handlers, E2E |
| Regressão | ✅ ZERO | Nenhum teste pré-existente quebrado |

**Conclusão v1.1:** módulo íntegro. Bug crítico de parsing corrigido e validado. Encerrado nesta fase.

### Finance + Telegram v1.2 (Abril 2026)

| Item | Resultado | Detalhe |
| --- | --- | --- |
| Formato BR `1.250,50` | ✅ OK | Regex `^\d{1,3}(\.\d{3})*,\d{1,2}$` detecta e normaliza corretamente |
| Ambiguidade `1.500` rejeitada | ✅ OK | Um separador com 3 dígitos após → erro explícito |
| month_ref mês 00/13 rejeitado | ✅ OK | Regex `0[1-9]\|1[0-2]` em `telegram.py`, `service.py` e `schemas.py` |
| amount ≤ 0 rejeitado | ✅ OK | Validator Pydantic em `FinancialEntryCreate` + parser |
| Saldos negativos permitidos | ✅ OK | `parse_balance_args` aceita valores negativos via `parse_amount` sign-agnostic |
| Log sanitization | ✅ OK | `balance` e `conference_diff` removidos do log de `get_monthly_summary` |
| Menu principal com Finance | ✅ OK | Botão "💰 Finanças" como primeiro item no `build_main_menu()` |
| Submenu Finance | ✅ OK | `build_finance_menu()` com 5 botões; callback `fin:menu` abre o submenu |
| Interceptação fin:* no webhook | ✅ OK | Callbacks `fin:*` (exceto `fin:sum`) resolvidos sem passar pelo orchestrator |
| Autorização fin:* | ✅ OK | Verificação `is_authorized()` cobre todos os callbacks automaticamente |
| Cobertura de testes | ✅ OK | 71 testes Telegram; 282 total; cobertura v1.2 adicionada |
| Regressão | ✅ ZERO | Nenhum teste pré-existente quebrado |

**Conclusão v1.2:** hardening completo de validações, parsing de moeda BR, segurança de logs, e UX Telegram com menus interativos. Encerrado nesta fase.

---

## Limitações de Escopo (v1.1)

Comportamentos deliberadamente fora do escopo desta versão:

- **Multiusuário:** todos os dados são globais
- **Autenticação:** sem autenticação própria para o módulo
- **Vínculo lançamento-conta:** lançamentos não são vinculados a contas específicas
- **Conciliação automática:** saldos de contas são 100% manuais
- **Integração bancária:** sem importação de extratos ou open banking
- **Dashboard/visualizações:** sem endpoints de chart data ou relatórios
- **Paginação:** endpoints de listagem retornam todos os itens do mês sem limite

---

## Known Limitations (riscos residuais)

**1. `month_ref` aceita meses semanticamente inválidos**

A validação usa a regex `^\d{4}-\d{2}$`, que garante o formato `YYYY-MM` mas não valida a semântica. Valores como `2026-13` ou `2026-00` são aceitos. Não há impacto nos cálculos — o dado é agrupado normalmente. Correção possível com validação de range `01-12` em versão futura.

**2. `amount` não valida valor positivo na camada REST**

O campo `amount` em `FinancialEntryCreate` aceita valores negativos via REST sem rejeição. Via Telegram, `parse_amount` já rejeita valores ≤ 0. Para uso pessoal com dados manuais, o comportamento REST é aceitável.

**3. N+1 query no cálculo do resumo mensal**

Para cada `AccountBalanceSnapshot` retornado, `get_monthly_summary()` executa uma query separada para buscar a `Account` correspondente. Custo irrelevante para volume pessoal (≤ 10 contas/mês). Resolvível com `joinedload` se necessário.
