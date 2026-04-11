# Atlas AI Assistant Starter Kit

Starter kit do MVP lean do assistente operacional pessoal com Claude.

## Stack
- Python 3.11+
- FastAPI
- SQLAlchemy
- SQLite
- Docker / Docker Compose
- Telegram Bot API
- MCP adapters (stubs para Google Workspace e RSS)

## Módulos do MVP
- Inbox Copilot
- Calendar Copilot
- News Briefing
- Daily Briefing
- Approval System

## Segurança
- Read-only por padrão
- Ações sensíveis exigem aprovação explícita
- Logs de auditoria
- Segredos via variáveis de ambiente

## Como rodar localmente

### 1. Criar ambiente
```bash
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\\Scripts\\activate  # Windows
pip install -r requirements.txt
```

### 2. Configurar ambiente
```bash
cp .env.example .env
```

### 3. Subir a API
```bash
uvicorn app.main:app --reload
```

API em `http://127.0.0.1:8000`

Docs em `http://127.0.0.1:8000/docs`

### 4. Rodar testes
```bash
pytest -q
```

## Docker
```bash
docker compose up --build
```

## Estrutura
```text
app/
  api/
  agent/
  integrations/
  services/
  db/
  scheduler/
  core/
tests/
```

## Observações
- As integrações MCP estão abstraídas em clientes stub para você conectar depois ao Claude/MCP real.
- O banco inicial é SQLite para reduzir custo e complexidade.
- O projeto já vem com fluxo de aprovação para ações sensíveis.
