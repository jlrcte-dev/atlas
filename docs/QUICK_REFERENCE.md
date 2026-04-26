# ATLAS — Referência Rápida

**Stack atual**: Python 3.11 + FastAPI + SQLite + Claude API + Google APIs + Microsoft Graph (via MSAL)

**Status**: Fase 1 concluída nas integrações principais. Sistema opera com dados reais.

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
│ ├─ document_catalog     │  ← Fase 1
│ ├─ draft_actions        │
│ ├─ audit_logs           │
│ ├─ daily_briefings      │
│ ├─ finance_*            │  ← Fase 1 (Finance v1.1)
│ └─ memory_events        │  ← NOVO (Fase 2A — Memory + Feedback Loop)
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
│   │   ├── drive_client.py      ← Google Drive API
│   │   ├── gmail_client.py      ← Gmail API
│   │   ├── outlook_client.py    ← Microsoft Graph (Outlook)
│   │   ├── email_models.py      ← EmailMessage (provider-agnostic)
│   │   ├── base_email_client.py ← BaseEmailClient Protocol
│   │   ├── claude_client.py     ← Claude API
│   │   ├── google_auth.py       ← Google OAuth compartilhada
│   │   ├── microsoft_auth.py    ← Microsoft OAuth (MSAL + PKCE)
│   │   ├── rss_client.py        ← RSS feeds (feedparser)
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
GOOGLE_CREDENTIALS_PATH=credentials/google_oauth_credentials.json
GOOGLE_TOKEN_PATH=credentials/google_token.json
GOOGLE_CALENDAR_ID=primary
GOOGLE_DRIVE_ROOT_FOLDER=

# Microsoft Graph (Outlook) — PublicClientApplication + PKCE, sem client_secret
MICROSOFT_CLIENT_ID=
MICROSOFT_TENANT=common
MICROSOFT_TOKEN_CACHE_PATH=credentials/microsoft_token_cache.json

# Provider de email (gmail | outlook)
EMAIL_PROVIDER=gmail

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

## Checklist de progresso — Fase 1 ✅ CONCLUÍDA

```text
Integrações core:
  ☑ Google Calendar API real
  ☑ Google Drive API real
  ☑ Gmail API real
  ☑ RSS real (feedparser)
  ☑ Briefing diário consolidando dados reais
  ☑ Claude conectado (classificação de intents + respostas)

Módulo de email multi-provider:
  ☑ BaseEmailClient (Protocol estrutural)
  ☑ EmailMessage isolado em email_models.py
  ☑ InboxService com factory por EMAIL_PROVIDER
  ☑ OutlookClient (MS Graph, somente leitura)
  ☑ Autenticação Microsoft (MSAL + PKCE)
  ☑ Gmail preservado, briefing sem regressão

Próximo foco (refinamento, não expansão):
  □ Classificação de prioridade mais inteligente (Claude-based)
  □ Sumarização contextual de emails
  □ Priorização cross-source (agenda + inbox)
```

---

## Fase 2A — Inteligência Controlada (em curso)

### Memory Module v1

`app/modules/memory/` registra cada decisão do sistema como snapshot auditável.

```text
memory_events
  ├─ event_type     ("email_classified" | "news_ranked" | …)
  ├─ source         ("email" | "news" | …)
  ├─ reference_id   (normalizado via to_callback_ref, ≤ 32 chars)
  ├─ payload (JSON) (snapshot da decisão: categoria, tags, razões, ID original)
  ├─ score          (score do classificador no momento)
  └─ feedback       (preenchido pelo Telegram Feedback Loop)
```

- **Idempotência:** UniqueConstraint(`event_type`, `reference_id`)
- **Fail-safe:** falha no Memory nunca derruba Inbox/News/Briefing
- **Out-of-band:** `_log_email_classifications` e `_log_ranked_news` usam `SessionLocal` próprias

### Telegram Feedback Loop v1

Após `/inbox` ou `/news`, cada item top-5 é enviado como mensagem individual com 3 botões:

```text
👍 Relevante   → fb:<e|n>:<ref>:pos
👎 Irrelevante → fb:<e|n>:<ref>:neg
⭐ Prioridade  → fb:<e|n>:<ref>:imp

callback_data ≤ 41 bytes (limite Telegram = 64)
```

- **Lookup direto:** mesmo `to_callback_ref(raw)` aplicado no logging e no botão — sem tabela auxiliar
- **Webhook:** branch `fb:` curto-circuita antes do answer genérico para responder com toast específico
- **`MemoryService.add_feedback(ref, feedback, *, source=None, event_type=None) -> bool`** — backward compatible

### Adaptive Score Engine v1 + Integration v1 (Fase 2A · Etapas 3A e 3B)

`app/modules/memory/scoring.py` — motor isolado, read-only, determinístico.

```python
# Ajuste por feedback
positive  → +1.0  |  important → +2.0  |  negative → -2.0
# Neutro quando: sem evento, sem feedback, valor desconhecido, qualquer erro

MemoryAdjustment(adjustment: float, reason: Optional[str])
compute_memory_adjustment(source, reference_id, base_score, *, db_session) -> MemoryAdjustment
```

**Integração ativa em:**

- **Inbox** — `_compute_email_adjustments` (helper out-of-band) aplica `final_score = base + adj` nas ordenações de `action_items` e `top5`. `EmailClassification.score` (int) intacto.
- **News** — `_apply_memory_adjustments` (Layer 7.5) aplica ajuste antes do ranking, curadoria e diversificação. Recalcula `item["priority"]` quando score cruza threshold. Preserva `_base_score` no item e no payload de memória.

**Fail-safe:** três camadas em cada pipeline (imports → item → sessão DB). Nunca quebra o pipeline.

**Observabilidade:** `[AdaptiveScore] src= ref= base= adj= final=` (DEBUG, por item, apenas quando adj≠0) + `Applied adaptive scoring to X/Y items` (INFO, por batch).

### Backlog conhecido (Fase 2A)

```text
□ Mover _FB_SRC_MAP / _FB_SIG_MAP para camada compartilhada (hoje em routes.py)
□ Reduzir colisão hipotética em news sem link (incluir source no fallback do hash)
□ Extrair helper _format_inbox_item_text (deduplicar entre briefing e feedback)
□ Avaliar mover to_callback_ref para app/core (acoplamento integrations → modules)
□ Diferenciar "evento inexistente" de "erro interno" no retorno de add_feedback
□ Feedback no briefing consolidado (format_briefing_blocks)

[Backlog 3B — próximas iterações]
□ Extrair effective_score duplicado (closure summarize_emails + _build_top5) para função de módulo
□ Teste: fallback de title quando news item não tem link
□ Teste: URL longa (>32 chars) via hash path em integração adaptativa
□ Clarificar return type de _apply_memory_adjustments para None (mutação pura)

[Futuro — Adaptive Score v2]
□ Agregação de múltiplos feedbacks por item
□ Decaimento temporal (feedbacks antigos pesam menos)
□ Aprendizado por categoria/source (não por item individual)
□ Perfil de usuário (interesses persistentes)
```
