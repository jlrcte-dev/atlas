# Módulo Finance — v1.1

> **Status:** Implementado e encerrado. Audit técnico pré-commit executado em Abril 2026.
> **Testes:** 49/49 passando. Suite completa: 211/211.

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
│       └── service.py             # FinanceService — toda a lógica de negócio
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

## Audit Técnico

> Executado em Abril 2026, antes do commit de encerramento da fase.

| Item | Resultado | Detalhe |
|---|---|---|
| Precisão financeira | ✅ OK | `Numeric(14,2)` nos 3 modelos; `Decimal(str(v))` no service; zero `float` |
| Unicidade MonthlyClosing | ✅ OK | `UniqueConstraint` + `unique=True` + `IntegrityError` → rollback explícito |
| Unicidade Snapshot | ✅ OK | `UniqueConstraint(account_id, month_ref)` + `IntegrityError` → rollback |
| Fórmulas do resumo | ✅ OK | Aderentes à spec em `service.py:219-236` |
| Erros explícitos | ✅ OK | 5 exceções com código estruturado; handler global HTTP 400 |
| Naming | ✅ OK | Código inglês, mensagens português, consistente com o projeto |
| Estrutura do módulo | ✅ OK | models → repositories → schemas → service → routes |
| Inicialização do app | ✅ OK | 2 linhas em `main.py`; tabelas auto-criadas; zero impacto no lifespan |
| Cobertura de testes | ✅ OK | 49 testes; cenários críticos cobertos |
| Regressão | ✅ ZERO | 211/211 na suite completa |

**Conclusão:** módulo íntegro. Nenhuma correção estrutural necessária. Encerrado nesta fase.

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

## Known Limitations (riscos residuais identificados no audit)

Comportamentos existentes que não constituem bugs críticos, mas devem ser conhecidos:

**1. `month_ref` aceita meses semanticamente inválidos**

A validação atual usa a regex `^\d{4}-\d{2}$`, que garante o formato `YYYY-MM` mas não valida a semântica do mês. Valores como `2026-13` (mês 13) ou `2026-00` (mês 0) são aceitos sem erro. Não há impacto nos cálculos do resumo — o dado é agrupado normalmente. Correção possível em versão futura com validação de range `01-12`.

**2. `amount` não valida valor positivo**

O campo `amount` em `FinancialEntry` aceita valores negativos sem rejeição. Não há validação `amount > 0` na camada de schema nem no service. Para uso pessoal com dados inseridos manualmente, o comportamento é aceitável — o usuário controla o que insere. Se necessário, pode ser adicionado como `field_validator` em `FinancialEntryCreate` em versão futura.

**3. N+1 query no cálculo do resumo mensal**

Para cada `AccountBalanceSnapshot` retornado, `get_monthly_summary()` executa uma query separada para buscar a `Account` correspondente. O comportamento é correto; o custo é irrelevante para volume pessoal (≤ 10 contas por mês). Resolvível com `joinedload` se o volume crescer.
