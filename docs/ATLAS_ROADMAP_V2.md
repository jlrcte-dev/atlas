# ATLAS — Roadmap Pragmático de Execução

**Versão**: 2.0 | **Data**: Abril 2026 | **Realidade**: Equipe pequena, execução real

---

## DIAGNÓSTICO HONESTO

### O que já existe

O starter kit **já tem** uma base sólida:

```
✅ FastAPI funcionando com rotas definidas
✅ Orchestrator com classificação de intents
✅ Services: Inbox, Calendar, News, Briefing, Approval
✅ SQLAlchemy + SQLite (simples e funcional)
✅ Logging estruturado
✅ Audit log
✅ Sistema de aprovação (human-in-the-loop)
✅ Webhook do Telegram
✅ Docker + docker-compose
✅ Testes unitários
```

### O que NÃO funciona

Tudo que toca o mundo real é **stub** (dados fake):

```
❌ GoogleCalendarClient → retorna 3 eventos hardcoded
❌ GmailClient → retorna 2 emails hardcoded
❌ GoogleWorkspaceMCPClient → mock
❌ RSSClient → mock
❌ Claude → configurado mas NÃO conectado
❌ Google Drive → não existe
❌ Gerenciamento de documentos → não existe
❌ Base de conhecimento → não existe
```

### O problema da arquitetura anterior (v1)

A arquitetura enterprise que desenhei antes é **correta como visão de 2 anos**, mas como plano de execução ela causa paralisia:

- Propõe PostgreSQL, Pinecone, Redis, Kafka, Kubernetes, Terraform
- Propõe 6 camadas separadas com 50+ arquivos novos
- Propõe 3 agentes de domínio, RAG completo, event-driven
- Timeline de 12-16 semanas para o primeiro valor real
- Ignora que já existe um starter kit funcional

**Resultado**: você não constrói nada porque o "certo" parece grande demais.

### A verdade

O caminho mais rápido para valor real é:

1. **Manter** a estrutura do starter kit (ela é boa)
2. **Substituir** os stubs por integrações reais
3. **Adicionar** Google Drive + gestão documental
4. **Conectar** Claude para inteligência real
5. **Depois** — e só depois — pensar em enterprise

---

## MODELO DE EVOLUÇÃO EM 4 FASES

```
FASE 1: Operacional     → "Atlas funciona no dia a dia"
FASE 2: Inteligente      → "Atlas entende e busca"
FASE 3: Automatizado     → "Atlas age e orquestra"
FASE 4: Avançado         → "Atlas decide e escala"

Cada fase entrega valor REAL e UTILIZÁVEL.
Nenhuma fase depende de tecnologia que ainda não foi validada.
```

---

## FASE 1 — ATLAS OPERACIONAL (Semanas 1-4)

### Objetivo

**Atlas funciona como assistente real no dia a dia.**

Você abre o Telegram (ou a API), e ele:
- Mostra sua agenda REAL do Google Calendar
- Lista e organiza arquivos REAIS do Google Drive
- Categoriza documentos por domínio
- Responde perguntas simples usando Claude
- Mantém log de tudo

### O que ENTRA

| Funcionalidade | Detalhe |
|----------------|---------|
| Google Calendar real | Substituir stub por Google Calendar API |
| Google Drive real | Nova integração — listar, buscar, categorizar arquivos |
| Claude conectado | Intent classifier e respostas usando Claude API |
| Catálogo de documentos | Modelo simples no SQLite para organizar arquivos do Drive |
| API de busca | Buscar documentos por nome, tipo, domínio |
| Logs operacionais | Toda ação logada no audit_log |

### O que NÃO ENTRA

```
✗ Embeddings / busca semântica
✗ RAG
✗ Vector database
✗ Kafka / event-driven
✗ PostgreSQL (SQLite é suficiente)
✗ Redis
✗ Kubernetes / Terraform
✗ Agentes de domínio
✗ Integração com TradeArena / Derivativos / Cartório
✗ Multi-user
```

### Entregas práticas

1. **Posso perguntar "qual minha agenda de hoje?"** → resposta real
2. **Posso perguntar "quais documentos tenho sobre contratos?"** → lista real do Drive
3. **Posso pedir "organize meus arquivos por categoria"** → categorização funcional
4. **Posso pedir "crie um evento às 15h"** → proposta com aprovação → evento criado
5. **Tudo é logado** → audit trail funcional

### Critérios de validação (Definition of Done)

```
□ GET /calendar/today retorna eventos reais do Google Calendar
□ GET /drive/files retorna arquivos reais do Google Drive
□ GET /drive/files?category=legal retorna arquivos filtrados
□ POST /chat com "minha agenda" retorna agenda real via Claude
□ POST /chat com "documentos de contratos" busca no Drive real
□ POST /calendar/propose-event cria evento real após aprovação
□ Audit log registra todas as operações
□ Testes passam com integração real (ou mock controlado)
□ Funciona via Telegram OU via API diretamente
```

---

## FASE 2 — INTELIGÊNCIA INCREMENTAL (Semanas 5-8)

### Objetivo

**Atlas entende contexto e encontra informações de forma inteligente.**

### O que ENTRA

| Funcionalidade | Detalhe |
|----------------|---------|
| Busca semântica | Embeddings dos documentos do Drive |
| RAG simples | Perguntar sobre seus documentos e receber resposta contextual |
| Sugestões | Atlas sugere ações baseadas na agenda + docs |
| RSS real | Substituir stub por feeds reais |
| Resumo diário real | Briefing que consolida agenda + docs + news reais |
| Início de domínios | Tags: "financeiro", "legal", "operacional" nos documentos |

### O que NÃO ENTRA

```
✗ Agentes autônomos
✗ Decisões automáticas
✗ Integração com TradeArena / Derivativos (apenas tags)
✗ Orquestração entre domínios
✗ Event-driven distribuído
✗ Multi-user / RBAC
```

### Entregas práticas

1. **"O que dizem meus contratos sobre prazo de renovação?"** → RAG busca nos docs e responde
2. **"Resumo do dia"** → agenda real + notícias reais + docs relevantes
3. **"Buscar documentos sobre LGPD"** → busca semântica (não apenas por nome)
4. **Sugestão automática**: "Você tem uma reunião sobre contratos às 15h. Encontrei 3 documentos relacionados."

### Critérios de validação

```
□ Busca semântica retorna documentos relevantes (não apenas match de texto)
□ RAG responde perguntas sobre conteúdo dos documentos
□ Briefing diário usa dados reais de todas as fontes
□ Sugestões aparecem quando há correlação agenda ↔ documentos
□ RSS funciona com feeds reais configuráveis
□ Performance: busca semântica < 2 segundos
```

### Tecnologia adicionada nesta fase

```
+ OpenAI Embeddings API (text-embedding-3-small é suficiente)
+ ChromaDB local (vector store — roda no SQLite, zero infra)
+ Não precisa de Pinecone. Não precisa de servidor separado.
```

**Por que ChromaDB e não Pinecone?**

ChromaDB roda localmente, persiste em disco, zero custo, zero configuração. Para centenas/milhares de documentos, é mais que suficiente. Migrar para Pinecone depois é trivial (mesma interface).

---

## FASE 3 — AUTOMAÇÃO E ORQUESTRAÇÃO (Semanas 9-14)

### Objetivo

**Atlas executa tarefas e conecta domínios.**

### O que ENTRA

| Funcionalidade | Detalhe |
|----------------|---------|
| Automações reais | Criar eventos, mover arquivos, enviar alertas |
| Alertas proativos | "Contrato X vence em 30 dias" |
| Pipeline de documentos | Upload → categorização → embedding → disponível para busca |
| Início TradeArena | Dados de mercado fluem para o Atlas |
| Início Derivativos | Trades e posições visíveis no Atlas |
| Scheduler | Tarefas recorrentes (briefing matinal, check de prazos) |
| KIP conectado | Dados do KIP entram no pipeline de documentos |

### O que NÃO ENTRA

```
✗ Agentes autônomos com decisão própria
✗ SaaS / multi-tenant
✗ Blockchain
✗ Kubernetes em produção
✗ Arquitetura distribuída
```

### Entregas práticas

1. **Briefing matinal automático** às 7h no Telegram
2. **Alerta**: "COAF filing vence em 10 dias" → notificação proativa
3. **Pipeline**: Upload doc no Drive → automaticamente categorizado e indexado
4. **Consulta**: "Como está meu portfolio?" → dados reais do sistema de derivativos
5. **Consulta**: "Quais mercados estão abertos?" → dados do TradeArena

### Critérios de validação

```
□ Scheduler roda briefing matinal automaticamente
□ Alertas de prazo funcionam para documentos com data de vencimento
□ Pipeline de ingestão processa novos documentos em < 5 minutos
□ Dados de pelo menos 1 sistema externo (TradeArena ou Derivativos) fluem
□ KIP adapter funciona com dados reais
□ Automações respeitam sistema de aprovação (human-in-the-loop)
```

---

## FASE 4 — INTELIGÊNCIA AVANÇADA (Semanas 15+)

### Objetivo

**Atlas raciocina, decide (com aprovação) e serve como plataforma.**

### O que ENTRA

| Funcionalidade | Detalhe |
|----------------|---------|
| Agentes de domínio | Market Agent, Trading Agent, Compliance Agent |
| Decisões assistidas | "Recomendo reduzir exposição em 10%. Aprovar?" |
| Cross-domain | Atlas correlaciona dados entre TradeArena + Derivativos + Cartório |
| RAG avançado | Multi-source, com citações e confiança |
| Dashboard | Visão consolidada de todos os domínios |
| Preparação SaaS | Multi-user, RBAC, API keys |

### O que pode entrar se validado

```
? PostgreSQL (se SQLite virar gargalo)
? Redis (se cache for necessário)
? Kafka (se event-driven for necessário)
? Pinecone (se ChromaDB não escalar)
? Kubernetes (se deploy justificar)
```

### Entregas práticas

1. **"Analise meu portfolio e sugira hedge"** → análise real com recomendação
2. **"Estamos compliance com LGPD?"** → audit baseado em documentos reais
3. **Dashboard**: portfolio + mercados + compliance em uma tela
4. **Multi-user**: outros membros da equipe podem usar com permissões diferentes

### Critérios de validação

```
□ Pelo menos 1 agente de domínio funciona end-to-end
□ Decisões assistidas geram valor mensurável
□ Cross-domain: pelo menos 1 insight que cruza 2 domínios
□ API suporta autenticação com API keys
□ Sistema roda por 1 semana sem intervenção manual
```

---

## ROADMAP SEMANAL — FASE 1 (DETALHADO)

### Semana 1: Google Calendar Real + Claude Conectado

**Objetivo**: Substituir os 2 stubs mais importantes

#### Dia 1-2: Google Calendar API

**O que fazer**:

1. Criar projeto no Google Cloud Console
2. Ativar Google Calendar API
3. Criar credenciais OAuth2 (ou Service Account)
4. Baixar `credentials.json`
5. Substituir o stub em `app/integrations/calendar_client.py`

**Dependências**: `google-api-python-client`, `google-auth-httplib2`, `google-auth-oauthlib`

**Código-alvo**: Substituir `GoogleCalendarClient` para chamar a API real.

Métodos a implementar:
- `get_today_events()` → chama Calendar API com `timeMin`/`timeMax` de hoje
- `get_events_range(start, end)` → chama Calendar API com range
- `create_event(...)` → cria evento real (mantém sistema de aprovação)

**Validação**:
```
□ GET /calendar/today retorna eventos reais da sua agenda
□ Eventos mostram título, horário, localização, participantes reais
□ find_free_slots() calcula com base em eventos reais
```

#### Dia 3-4: Claude Conectado ao Orchestrator

**O que fazer**:

1. Adicionar `anthropic` ao requirements.txt
2. Criar `app/integrations/claude_client.py` — wrapper simples para Claude API
3. Modificar `IntentClassifier.classify()` para usar Claude (tool_use) em vez de regex
4. Modificar `Orchestrator.handle_request()` para gerar respostas com Claude

**Escopo**: Claude classifica intents E gera respostas naturais. Nada mais.

Não é RAG. Não é agente. É apenas:
- Input: mensagem do usuário
- Claude decide: qual intent? quais parâmetros?
- Sistema executa: chama o service correto
- Claude formata: resposta natural para o usuário

**Validação**:
```
□ POST /chat com "qual minha agenda?" → Claude identifica intent GET_CALENDAR
□ POST /chat com "crie reunião às 15h com João" → Claude extrai título, hora, participante
□ Respostas são naturais (não mais templates hardcoded)
□ Fallback para classifier regex se Claude falhar (resiliência)
```

#### Dia 5: Testes + Ajustes

```
□ Todos os testes existentes passam
□ Novos testes para Calendar real (com mock da API para CI)
□ Novos testes para Claude classifier
□ Teste manual via Telegram: conversa natural funciona
□ .env atualizado com novas variáveis
```

---

### Semana 2: Google Drive

**Objetivo**: Atlas enxerga e organiza seus arquivos

#### Dia 1-2: Google Drive API — Leitura

**O que fazer**:

1. Ativar Google Drive API no mesmo projeto GCP
2. Criar `app/integrations/drive_client.py`
3. Implementar:
   - `list_files(folder_id=None, query=None)` → lista arquivos
   - `search_files(query)` → busca por nome/conteúdo
   - `get_file_metadata(file_id)` → metadados
   - `download_file_content(file_id)` → conteúdo (texto)
   - `list_folders()` → estrutura de pastas

**Validação**:
```
□ list_files() retorna arquivos reais do seu Drive
□ search_files("contrato") encontra documentos com "contrato" no nome
□ get_file_metadata() retorna nome, tipo, tamanho, data de modificação
□ download_file_content() retorna texto de Google Docs / PDFs
```

#### Dia 3: Drive Service + Rotas

**O que fazer**:

1. Criar `app/services/drive_service.py`
   - `list_files(folder=None, category=None)`
   - `search_files(query)`
   - `categorize_file(file_id, category)` → tag manual
   - `get_file_summary(file_id)` → metadados formatados
   
2. Criar rotas em `app/api/routes.py`:
   - `GET /drive/files` → lista arquivos (filtro por pasta, categoria)
   - `GET /drive/files/search?q=contrato` → busca
   - `GET /drive/files/{file_id}` → detalhes
   - `POST /drive/files/{file_id}/categorize` → categorizar

3. Adicionar intents no classifier:
   - `GET_DRIVE_FILES` → "meus arquivos", "documentos", "drive"
   - `SEARCH_DRIVE` → "buscar documento", "encontrar arquivo"

**Validação**:
```
□ GET /drive/files retorna lista de arquivos reais
□ GET /drive/files/search?q=contrato filtra corretamente
□ POST /chat "quais documentos tenho?" → lista via Claude
□ POST /chat "buscar contrato de aluguel" → busca no Drive
```

#### Dia 4: Catálogo de Documentos (SQLite)

**O que fazer**:

1. Novo modelo em `app/db/models.py`:

```python
class DocumentCatalog(Base):
    __tablename__ = "document_catalog"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    drive_file_id: Mapped[str] = mapped_column(String(200), unique=True)
    title: Mapped[str] = mapped_column(String(500))
    file_type: Mapped[str] = mapped_column(String(50))  # pdf, doc, sheet
    category: Mapped[str] = mapped_column(String(100), default="geral")
    # "financeiro", "legal", "operacional", "pessoal", "geral"
    domain: Mapped[str] = mapped_column(String(100), default="")
    # "tradearena", "derivativos", "cartorio", ""
    summary: Mapped[str] = mapped_column(Text, default="")
    drive_folder: Mapped[str] = mapped_column(String(500), default="")
    last_synced: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
```

2. Sync service: sincroniza metadados do Drive → SQLite
3. Categorização básica: por pasta do Drive ou manual

**Validação**:
```
□ Sync popula catálogo com arquivos do Drive
□ GET /drive/files?category=legal filtra pelo catálogo
□ Categorização persiste entre reinicializações
```

#### Dia 5: Testes + Integração com Chat

```
□ POST /chat "organize meus documentos" → mostra categorias
□ POST /chat "documentos legais" → filtra por categoria
□ POST /chat "sincronizar drive" → atualiza catálogo
□ Testes para Drive integration (mock para CI)
□ Testes para DocumentCatalog model
```

---

### Semana 3: Polimento + Gmail Real + RSS Real

**Objetivo**: Todos os stubs substituídos. Sistema 100% real.

#### Dia 1-2: Gmail API Real

1. Ativar Gmail API no projeto GCP
2. Substituir stub em `app/integrations/gmail_client.py`
3. Implementar leitura de emails reais
4. Manter classificação de prioridade (Claude pode ajudar aqui)

#### Dia 3: RSS Real

1. Substituir stub em `app/integrations/rss_client.py`
2. Usar `feedparser` para parse de feeds reais
3. Configurar feeds padrão (Reuters, etc.)

#### Dia 4: Briefing Diário Completo

1. `BriefingService.run_daily_briefing()` consolida dados REAIS:
   - Agenda do dia (Calendar real)
   - Emails prioritários (Gmail real)
   - Notícias relevantes (RSS real)
   - Documentos recentes (Drive real)
2. Claude gera resumo executivo
3. Entrega via Telegram ou API

#### Dia 5: Testes End-to-End

```
□ Briefing diário funciona com dados 100% reais
□ Todos os endpoints retornam dados reais
□ Telegram bot funciona em conversa natural
□ Zero stubs restantes no código
□ Audit log registra todas as operações
```

---

### Semana 4: Estabilização + Deploy

**Objetivo**: Sistema rodando de forma estável, usável no dia a dia

#### Dia 1-2: Robustez

1. Error handling para falhas de API (Google offline, rate limit)
2. Retry com backoff exponencial
3. Fallback gracioso (se Calendar falha, mostra "indisponível" em vez de crash)
4. Rate limiting no Claude API (controlar custo)
5. Cache simples em memória (não precisa de Redis — `functools.lru_cache` basta)

#### Dia 3: Configuração e Deploy

1. Docker Compose atualizado com todas as dependências
2. Script de setup: `scripts/setup.sh` (cria .env, instala deps, roda migrations)
3. Documentação: README atualizado com instruções reais
4. Health check: `/health` verifica todas as integrações

#### Dia 4-5: Uso Real + Ajustes

```
□ Usar o Atlas durante 2 dias como ferramenta real
□ Anotar o que funciona e o que não funciona
□ Corrigir problemas encontrados no uso real
□ Ajustar prompts do Claude com base na experiência
□ Documentar decisões e próximos passos
```

---

## AJUSTE DA ARQUITETURA PARA MVP

### Estrutura de pastas: O QUE MANTER

```
atlas-ai-assistant/                ← Estrutura atual (raiz do repo)
│
├── app/
│   ├── __init__.py
│   ├── main.py                    ← MANTER (já funciona)
│   │
│   ├── api/
│   │   ├── routes.py              ← EXPANDIR (adicionar rotas de Drive)
│   │   └── schemas.py             ← EXPANDIR (adicionar schemas de Drive)
│   │
│   ├── agent/
│   │   ├── orchestrator.py        ← MANTER (expandir handlers)
│   │   ├── intent_classifier.py   ← MODIFICAR (conectar Claude)
│   │   └── policies.py            ← MANTER
│   │
│   ├── core/
│   │   ├── config.py              ← EXPANDIR (novas env vars)
│   │   ├── exceptions.py          ← MANTER
│   │   ├── logging.py             ← MANTER
│   │   ├── permissions.py         ← MANTER
│   │   └── security.py            ← MANTER
│   │
│   ├── db/
│   │   ├── models.py              ← EXPANDIR (DocumentCatalog)
│   │   ├── repositories.py        ← EXPANDIR
│   │   └── session.py             ← MANTER
│   │
│   ├── integrations/
│   │   ├── calendar_client.py     ← REESCREVER (Google Calendar API real)
│   │   ├── gmail_client.py        ← REESCREVER (Gmail API real)
│   │   ├── drive_client.py        ← NOVO
│   │   ├── claude_client.py       ← NOVO
│   │   ├── google_auth.py         ← NOVO (auth compartilhada)
│   │   ├── rss_reader.py          ← REESCREVER (feedparser real)
│   │   ├── telegram_bot.py        ← MANTER
│   │   └── google_mcp.py          ← REMOVER (substituído por clients reais)
│   │
│   ├── services/
│   │   ├── calendar_service.py    ← MANTER (já funciona com novo client)
│   │   ├── inbox_service.py       ← MANTER
│   │   ├── drive_service.py       ← NOVO
│   │   ├── news_service.py        ← MANTER
│   │   ├── briefing_service.py    ← EXPANDIR (incluir Drive)
│   │   └── approval_service.py    ← MANTER
│   │
│   └── scheduler/
│       └── jobs.py                ← MANTER (expandir depois)
│
├── tests/                         ← EXPANDIR
├── scripts/
│   └── setup.sh                   ← NOVO
├── .env.example                   ← ATUALIZAR
├── requirements.txt               ← ATUALIZAR
├── docker-compose.yml             ← ATUALIZAR
├── Dockerfile                     ← MANTER
└── README.md                      ← ATUALIZAR
```

### O que REMOVER ou ADIAR

| Item | Decisão | Motivo |
|------|---------|--------|
| `google_mcp.py` | REMOVER | Substituído por clients reais |
| PostgreSQL | ADIAR (Fase 4) | SQLite é suficiente para single-user |
| Redis | ADIAR (Fase 4) | `lru_cache` basta |
| Pinecone | ADIAR (Fase 4) | ChromaDB local na Fase 2 |
| Kafka | ADIAR (Fase 4) | Não precisa de event bus |
| Kubernetes | ADIAR (Fase 4) | Docker Compose basta |
| Terraform | ADIAR (Fase 4) | Não há infra cloud no MVP |
| `/intelligence` dir | ADIAR (Fase 2) | Não existe ainda |
| `/domains` dir | ADIAR (Fase 3) | Domínios não estão conectados |
| `/events` dir | ADIAR (Fase 4) | Não há event-driven |
| `/knowledge` dir | ADIAR (Fase 2) | ChromaDB na Fase 2 |
| Agentes de domínio | ADIAR (Fase 4) | Overkill para MVP |
| RAG completo | ADIAR (Fase 2) | Sem embeddings no MVP |
| RBAC / Multi-user | ADIAR (Fase 4) | Single-user agora |

### Novas dependências (APENAS o necessário)

```txt
# requirements.txt — Fase 1

# Já existentes
fastapi>=0.135.0
uvicorn[standard]>=0.44.0
sqlalchemy>=2.0.49
pydantic>=2.12.0
pydantic-settings>=2.13.0
httpx>=0.28.0
python-dotenv>=1.2.0

# NOVAS — Fase 1
anthropic>=0.40.0                  # Claude API
google-api-python-client>=2.150.0  # Google APIs
google-auth-httplib2>=0.2.0        # Google Auth
google-auth-oauthlib>=1.2.0        # Google OAuth
feedparser>=6.0.0                  # RSS real

# Fase 2 (adicionar quando chegar lá)
# chromadb>=0.5.0                  # Vector DB local
# openai>=1.50.0                   # Embeddings
```

### Novas variáveis de ambiente

```env
# .env — Fase 1

# Já existentes
APP_NAME=Atlas AI Assistant
DATABASE_URL=sqlite:///./atlas_assistant.db
TELEGRAM_BOT_TOKEN=
TELEGRAM_ALLOWED_USER_ID=
TIMEZONE=America/Sao_Paulo

# NOVAS — Fase 1
ANTHROPIC_API_KEY=               # Claude API key
GOOGLE_CREDENTIALS_PATH=./credentials.json  # OAuth credentials
GOOGLE_TOKEN_PATH=./token.json   # OAuth token (gerado automaticamente)
GOOGLE_CALENDAR_ID=primary       # Calendar ID (default: primary)
GOOGLE_DRIVE_ROOT_FOLDER=        # Pasta raiz no Drive (opcional)

# REMOVER
# GOOGLE_MCP_BASE_URL=           # Não precisa mais
# GOOGLE_MCP_API_KEY=            # Não precisa mais
# CLAUDE_PROVIDER=               # Simplificar
# CLAUDE_MODEL=                  # Mover para config.py
```

---

## ERROS CRÍTICOS A EVITAR

### 1. Construir infraestrutura antes de ter produto

```
❌ ERRADO: "Primeiro vou configurar Kafka, Redis, PostgreSQL, Kubernetes..."
✅ CERTO:  "Primeiro vou fazer o Calendar funcionar. O resto vem depois."

Por quê? Infraestrutura sem produto é custo sem valor.
SQLite + FastAPI + Docker Compose suporta MILHARES de requests/dia
para um usuário. Você não precisa de mais.
```

### 2. Criar abstrações antes de ter repetição

```
❌ ERRADO: "Vou criar um BaseAdapter genérico para todas as integrações"
✅ CERTO:  "Vou criar GoogleCalendarClient que faz exatamente o que preciso"

Por quê? Abstrações prematuras engessam. Quando você tiver 3 integrações
similares, ENTÃO refatore. Não antes.
```

### 3. Separar em muitos pacotes/diretórios cedo demais

```
❌ ERRADO: /ingestion/sources/adapters/google/calendar/v1/client.py
✅ CERTO:  /integrations/calendar_client.py

Por quê? Cada nível de diretório é fricção cognitiva. Um arquivo de
200 linhas é melhor que 10 arquivos de 20 linhas quando há 1 desenvolvedor.
```

### 4. Implementar multi-user antes de ter single-user funcionando

```
❌ ERRADO: "Preciso de JWT, RBAC, API keys, tenant isolation..."
✅ CERTO:  "Preciso que FUNCIONE para mim. Depois abro para outros."

Por quê? Cada feature de segurança multiplica complexidade por 3.
Se você não tem usuários, não tem problema de multi-user.
```

### 5. Escolher tecnologia pela "melhor prática" e não pela necessidade

```
❌ ERRADO: "Kafka é industry standard para events" (com 10 events/dia)
✅ CERTO:  "Um cron job que roda a cada hora resolve" (com 10 events/dia)

❌ ERRADO: "Preciso de PostgreSQL para ACID" (com 1 usuário)
✅ CERTO:  "SQLite é ACID e suporta milhões de rows"

❌ ERRADO: "Pinecone para vector search é o padrão" (com 500 docs)
✅ CERTO:  "ChromaDB roda local, zero custo, mesma qualidade"
```

### 6. Documentar mais do que implementar

```
❌ ERRADO: Semana 1 → 200 páginas de docs, 0 linhas de código
✅ CERTO:  Semana 1 → Calendar funcionando, Claude conectado, docs mínimos

Por quê? Documentação é importante, mas código funcionando é mais.
Documente o que você construiu, não o que planeja construir.
```

### 7. Planejar a Fase 4 enquanto está na Fase 1

```
❌ ERRADO: "Preciso garantir que a Fase 1 é compatível com blockchain"
✅ CERTO:  "Preciso garantir que o Calendar funciona"

Por quê? Requisitos da Fase 4 vão mudar. O que você sabe agora sobre
blockchain pode estar errado daqui 6 meses. Foque no que é real hoje.
```

---

## PRINCÍPIOS DE EVOLUÇÃO DO ATLAS

### Regra 1: Adicione tecnologia apenas quando a atual DÓER

```
Trigger: "SQLite está lento" (medido, não sentido)
Action: Migre para PostgreSQL

Trigger: "Busca por texto não encontra o que preciso"
Action: Adicione embeddings + ChromaDB

Trigger: "Preciso processar 1000 eventos por minuto"
Action: Adicione Kafka

Se não dói, não mexa.
```

### Regra 2: Valide antes de expandir

```
Antes de começar a Fase 2, responda:
□ Estou usando o Atlas todo dia?
□ O Calendar real funciona sem problemas?
□ O Drive está organizado e útil?
□ O briefing diário me ajuda de verdade?
□ Claude responde de forma útil?

Se algum "não" → corrija na Fase 1, não avance para Fase 2.
```

### Regra 3: Um serviço novo = um problema resolvido

```
Não adicione um serviço "porque pode ser útil".
Adicione porque resolve um problema que você TEM.

✅ "Não consigo encontrar documentos por conteúdo" → adicione embeddings
✅ "Preciso de alertas de prazo" → adicione scheduler
✅ "Quero ver dados do TradeArena" → adicione integração

❌ "Talvez um dia precise de..." → NÃO adicione
```

### Regra 4: Escale arquitetura apenas com evidência

```
Escalar de SQLite → PostgreSQL:
  Evidência: queries > 1 segundo, ou > 100K rows, ou precisa de concurrent writes

Escalar de ChromaDB → Pinecone:
  Evidência: > 100K documentos, ou latência > 2 segundos

Escalar de Docker Compose → Kubernetes:
  Evidência: > 3 serviços independentes, ou precisa de auto-scaling

Escalar de single-user → multi-user:
  Evidência: alguém pediu acesso
```

### Regra 5: A melhor abstração é nenhuma (até que doa)

```
Fase 1: Código direto, sem camadas extras
Fase 2: Refatore se houver repetição clara
Fase 3: Abstraia se padrões emergirem
Fase 4: Arquitete se for virar plataforma

Nessa ordem. Nunca ao contrário.
```

### Regra 6: Cada deploy deve ser testável em 5 minutos

```
Se leva mais de 5 minutos para rodar o sistema localmente, algo está errado.

Alvo:
  git clone → pip install → python -m app.main → funcionando

Se precisar de Docker:
  docker compose up → funcionando

Se precisar de mais que isso → simplifique.
```

---

## RESUMO VISUAL: O QUE MUDA EM CADA FASE

```
FASE 1 (Semanas 1-4)
─────────────────────
Stack: Python + FastAPI + SQLite + Claude + Google APIs
Infra: Docker Compose (local)
Dados: SQLite
AI:    Claude para classificação e respostas
Busca: SQL (LIKE) + filtros por categoria
Users: 1 (você)

FASE 2 (Semanas 5-8)
─────────────────────
Stack: + ChromaDB + OpenAI Embeddings
Infra: Docker Compose (local)
Dados: SQLite + ChromaDB (local)
AI:    Claude + RAG simples
Busca: SQL + busca semântica
Users: 1

FASE 3 (Semanas 9-14)
──────────────────────
Stack: + Scheduler + KIP adapter
Infra: Docker Compose (pode subir em VPS)
Dados: SQLite → avaliar PostgreSQL
AI:    Claude + RAG + sugestões proativas
Busca: Semântica + cross-domain
Users: 1-3

FASE 4 (Semanas 15+)
─────────────────────
Stack: + PostgreSQL + Redis + API auth
Infra: Docker Compose → avaliar Kubernetes
Dados: PostgreSQL + ChromaDB (ou Pinecone)
AI:    Claude + agentes de domínio + decisões assistidas
Busca: Semântica avançada + RAG multi-source
Users: 5+
```

---

## CUSTO POR FASE

```
FASE 1:
  Claude API: ~$10-30/mês (uso pessoal, Haiku para classificação)
  Google APIs: $0 (quota gratuita)
  Infra: $0 (local)
  Total: ~$10-30/mês

FASE 2:
  + OpenAI Embeddings: ~$5/mês (poucos docs)
  Total: ~$15-35/mês

FASE 3:
  + VPS (se deploy remoto): ~$10-20/mês
  Total: ~$25-55/mês

FASE 4:
  + PostgreSQL managed: ~$15/mês
  + Redis managed: ~$10/mês
  Total: ~$50-100/mês
```

---

## CHECKLIST FINAL: PRIORIDADE DE EXECUÇÃO

### Esta semana (prioridade máxima)

```
□ Criar projeto no Google Cloud Console
□ Ativar Calendar API + Drive API + Gmail API
□ Gerar credentials.json (OAuth2)
□ Obter ANTHROPIC_API_KEY
□ Instalar novas dependências
□ Reescrever calendar_client.py com API real
□ Testar: GET /calendar/today → dados reais
```

### Próxima semana

```
□ Criar drive_client.py
□ Criar drive_service.py
□ Adicionar DocumentCatalog ao models.py
□ Adicionar rotas de Drive
□ Conectar Claude ao Orchestrator
□ Testar: conversa natural sobre agenda e documentos
```

### Semana 3

```
□ Gmail real
□ RSS real
□ Briefing completo com dados reais
□ Todos os stubs eliminados
```

### Semana 4

```
□ Robustez (error handling, retries)
□ Deploy estável
□ Uso real por 2+ dias
□ Lista de ajustes para Fase 2
```

---

## CONCLUSÃO

A arquitetura enterprise está **certa como visão**.
Mas o roadmap precisa ser **sobre execução, não sobre visão**.

O Atlas não precisa de Kafka para organizar sua agenda.
O Atlas não precisa de Pinecone para listar seus documentos.
O Atlas não precisa de Kubernetes para rodar no seu computador.

**O Atlas precisa funcionar.**

Comece substituindo stubs por realidade.
Depois adicione inteligência.
Depois automatize.
Depois escale.

Nessa ordem. Sem pular etapas.

---

**Documento**: ATLAS Roadmap Pragmático v2  
**Criado**: Abril 11, 2026  
**Status**: Pronto para execução imediata  
**Próximo passo**: Criar projeto no Google Cloud Console
