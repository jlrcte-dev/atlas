# ATLAS — Referência Rápida

**Stack atual**: Python 3.11 + FastAPI + SQLite + Claude API + Google APIs

---

## Arquitetura (Fase 1)

```text
Telegram / API
      ↓
┌─────────────────────────┐
│ FastAPI (routes.py)     │
└──────────┬──────────────┘
           ↓
┌─────────────────────────┐
│ Orchestrator            │
│ ├─ Intent Classifier    │  ← Claude classifica
│ └─ Handler dispatch     │  ← Roteia para service
└──────────┬──────────────┘
           ↓
┌─────────────────────────┐
│ Services                │
│ ├─ CalendarService      │  ← Google Calendar API
│ ├─ DriveService         │  ← Google Drive API
│ ├─ InboxService         │  ← Gmail API
│ ├─ NewsService          │  ← RSS feeds
│ ├─ BriefingService      │  ← Consolida tudo
│ └─ ApprovalService      │  ← Human-in-the-loop
└──────────┬──────────────┘
           ↓
┌─────────────────────────┐
│ SQLite                  │
│ ├─ users                │
│ ├─ document_catalog     │  ← NOVO (Fase 1)
│ ├─ draft_actions        │
│ ├─ audit_logs           │
│ └─ daily_briefings      │
└─────────────────────────┘
```

---

## Estrutura de pastas

```text
atlas-ai-assistant/
├── app/
│   ├── main.py                  ← Entry point FastAPI
│   ├── api/
│   │   ├── routes.py            ← Todas as rotas
│   │   └── schemas.py           ← Pydantic models
│   ├── agent/
│   │   ├── orchestrator.py      ← Roteamento central
│   │   ├── intent_classifier.py ← Classificação (Claude)
│   │   └── policies.py          ← Regras de segurança
│   ├── core/
│   │   ├── config.py            ← Settings (.env)
│   │   ├── exceptions.py        ← Erros customizados
│   │   ├── logging.py           ← Log estruturado
│   │   ├── permissions.py       ← Controle de acesso
│   │   └── security.py          ← Segurança
│   ├── db/
│   │   ├── models.py            ← Modelos SQLAlchemy
│   │   ├── repositories.py      ← Queries
│   │   └── session.py           ← Engine + get_db
│   ├── integrations/
│   │   ├── calendar_client.py   ← Google Calendar API
│   │   ├── drive_client.py      ← Google Drive API (NOVO)
│   │   ├── gmail_client.py      ← Gmail API
│   │   ├── claude_client.py     ← Claude API (NOVO)
│   │   ├── google_auth.py       ← Auth compartilhada (NOVO)
│   │   ├── rss_reader.py        ← RSS feeds
│   │   └── telegram_bot.py      ← Telegram Bot
│   ├── services/
│   │   ├── calendar_service.py  ← Agenda, free slots
│   │   ├── drive_service.py     ← Arquivos, categorias (NOVO)
│   │   ├── inbox_service.py     ← Emails, prioridades
│   │   ├── news_service.py      ← Notícias RSS
│   │   ├── briefing_service.py  ← Resumo diário
│   │   └── approval_service.py  ← Aprovações
│   └── scheduler/
│       └── jobs.py              ← Tarefas agendadas
├── tests/
├── docs/
├── scripts/
├── .env
├── requirements.txt
├── docker-compose.yml
└── Dockerfile
```

---

## Comandos essenciais

```bash
# Instalar dependências
pip install -r requirements.txt

# Rodar API
uvicorn app.main:app --reload

# Rodar testes
pytest -q

# API docs
# http://127.0.0.1:8000/docs

# Docker
docker compose up --build
```

---

## Endpoints da API

### Core

```text
GET  /health                              → Status do sistema
POST /chat                                → Conversa natural (via Orchestrator)
```

### Calendar

```text
GET  /calendar/today                      → Agenda de hoje
GET  /calendar/free-slots?duration=60     → Horários livres
POST /calendar/propose-event              → Propor evento (requer aprovação)
```

### Drive (NOVO — Fase 1)

```text
GET  /drive/files                         → Listar arquivos
GET  /drive/files/search?q=contrato       → Buscar arquivos
GET  /drive/files/{file_id}               → Detalhes do arquivo
POST /drive/files/{file_id}/categorize    → Categorizar arquivo
POST /drive/sync                          → Sincronizar catálogo
```

### Email / News / Briefing

```text
GET  /inbox/summary                       → Resumo da inbox
GET  /news                                → Notícias
GET  /briefing                            → Briefing diário completo
```

### Aprovações

```text
POST /approvals/{id}/approve              → Aprovar ação
POST /approvals/{id}/reject               → Rejeitar ação
```

---

## Variáveis de ambiente (.env)

```env
# App
APP_NAME=Atlas AI Assistant
APP_ENV=development
DATABASE_URL=sqlite:///./atlas_assistant.db
TIMEZONE=America/Sao_Paulo
LOG_LEVEL=INFO

# Claude
ANTHROPIC_API_KEY=sk-ant-...

# Google
GOOGLE_CREDENTIALS_PATH=./credentials.json
GOOGLE_TOKEN_PATH=./token.json
GOOGLE_CALENDAR_ID=primary
GOOGLE_DRIVE_ROOT_FOLDER=

# Telegram
TELEGRAM_BOT_TOKEN=
TELEGRAM_ALLOWED_USER_ID=

# RSS
RSS_DEFAULT_FEEDS=https://feeds.reuters.com/reuters/businessNews
```

---

## Troubleshooting

**"API retorna dados fake"**

- Integration ainda é stub. Verifique se `calendar_client.py` usa Google API real
- Cheque se `credentials.json` existe e tem scopes corretos

**"Google Auth falha"**

- Rode o fluxo OAuth manualmente uma vez para gerar `token.json`
- Verifique scopes: `calendar.readonly`, `drive.readonly`, `gmail.readonly`

**"Claude não responde"**

- Verifique `ANTHROPIC_API_KEY` no `.env`
- Cheque quota na dashboard da Anthropic
- Fallback: intent classifier funciona com regex se Claude falhar

**"SQLite locked"**

- Apenas 1 processo de escrita por vez
- Para Fase 1 (single-user), isso não é problema
- Se virar problema: migrar para PostgreSQL (Fase 4)

---

## Decisões por fase

### Fase 1 (atual)

| Necessidade | Solução | NÃO usar |
| ----------- | ------- | -------- |
| Database | SQLite | PostgreSQL |
| Cache | `lru_cache` | Redis |
| Busca | SQL LIKE + filtros | Elasticsearch |
| AI | Claude API direto | LangChain |
| Deploy | Docker Compose | Kubernetes |
| Infra | Local | AWS/GCP |

### Fase 2

| Necessidade | Solução | NÃO usar |
| ----------- | ------- | -------- |
| Vector search | ChromaDB local | Pinecone |
| Embeddings | OpenAI text-embedding-3-small | Modelos locais |
| RAG | Retriever + Claude simples | LangChain |

### Fase 3+

Reavaliar todas as decisões com base em dados reais de uso.

---

## Checklist de progresso — Fase 1

```text
Semana 1:
  □ Google Calendar API real funcionando
  □ Claude conectado ao Orchestrator
  □ GET /calendar/today retorna dados reais

Semana 2:
  □ Google Drive API funcionando
  □ DriveService + rotas
  □ DocumentCatalog no SQLite
  □ Busca e categorização

Semana 3:
  □ Gmail API real
  □ RSS real (feedparser)
  □ Briefing diário com dados 100% reais
  □ Zero stubs restantes

Semana 4:
  □ Error handling robusto
  □ Deploy estável
  □ Uso real por 2+ dias
  □ Lista de ajustes para Fase 2
```
