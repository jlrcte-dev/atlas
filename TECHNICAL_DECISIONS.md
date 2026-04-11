# ATLAS — Decisões Técnicas

**Versão**: 2.0 | **Abril 2026** | **Princípio**: A tecnologia mais simples que resolve o problema

---

## Regra geral

Toda decisão técnica segue este filtro:

1. Resolve um problema que existe HOJE?
2. É a opção mais simples que funciona?
3. Pode ser trocada depois sem reescrever tudo?

Se sim para as 3, adote. Se não, adie.

---

## Decisões da Fase 1

### Python 3.11 + FastAPI

**Escolhido.** Sem discussão.

- Ecossistema de AI/ML é Python
- FastAPI é moderno, async, docs automáticas
- Starter kit já usa — não há motivo para trocar
- Time já conhece

Alternativas descartadas:

- Go/Rust: performance desnecessária, ecossistema AI fraco
- Node.js: inferior para data processing
- Django: pesado demais para o que precisamos

---

### SQLite (não PostgreSQL)

**Escolhido para Fase 1-3. PostgreSQL apenas na Fase 4.**

Por que SQLite agora:

- Zero configuração (arquivo único)
- ACID compliant (sim, SQLite é transacional)
- Suporta milhões de rows sem problemas
- Starter kit já usa
- Single-user não precisa de concurrent writes
- Backup = copiar 1 arquivo

Por que NÃO PostgreSQL agora:

- Requer servidor rodando (complexidade)
- Requer configuração de conexão, pool, migrations
- Não há necessidade de concurrent writes
- Não há necessidade de features avançadas (JSONB, full-text, etc.)

Quando migrar para PostgreSQL:

- Quando houver mais de 1 usuário escrevendo ao mesmo tempo
- Quando queries ficarem lentas (medido, não sentido)
- Quando precisar de full-text search nativo
- Migração é simples: trocar `DATABASE_URL` e rodar `alembic upgrade head`

---

### Claude API (Anthropic) para inteligência

**Escolhido.**

Uso na Fase 1:

- Intent classification (substituir regex por Claude)
- Geração de respostas naturais
- Resumos de emails e documentos
- NÃO usa RAG, NÃO usa agentes, NÃO usa tool_use complexo

Modelo recomendado:

- **Haiku** para classificação de intents (barato, rápido)
- **Sonnet** para respostas e resumos (quando qualidade importa)
- **Opus** apenas para análises complexas na Fase 4

Custo estimado: $10-30/mês para uso pessoal.

Alternativa:

- GPT-4 (OpenAI): funciona igual, API similar. Claude escolhido por qualidade de raciocínio e safety.
- A interface é agnóstica — trocar de provider requer mudar 1 arquivo (`claude_client.py`).

---

### Google APIs diretas (não MCP)

**Escolhido.** Substituir os stubs MCP por chamadas diretas.

O starter kit usava `GoogleWorkspaceMCPClient` (stub). Vamos trocar por:

- `google-api-python-client` para Calendar, Drive, Gmail
- OAuth2 para autenticação
- 1 arquivo de auth compartilhado (`google_auth.py`)
- Clients separados por serviço (`calendar_client.py`, `drive_client.py`, `gmail_client.py`)

Por que não MCP (Model Context Protocol):

- MCP adiciona uma camada de indireção desnecessária
- Google APIs são bem documentadas e estáveis
- Chamada direta = debug mais fácil
- Se MCP for necessário depois, pode wrappear os clients existentes

---

### feedparser para RSS

**Escolhido.** Substituir o stub RSS.

- `feedparser` é o padrão Python para RSS/Atom
- Zero configuração, zero dependências pesadas
- Parse feeds da Reuters, Bloomberg, etc.

---

### lru_cache para cache (não Redis)

**Escolhido para Fase 1-2.**

```python
from functools import lru_cache

@lru_cache(maxsize=128)
def get_cached_result(key):
    return expensive_computation(key)
```

Por que não Redis:

- Redis requer servidor separado
- Para single-user com poucos requests/minuto, in-memory basta
- Cache invalida no restart (aceitável para MVP)

Quando adicionar Redis:

- Quando houver múltiplos processos/workers
- Quando cache precisa sobreviver a restarts
- Quando houver dados compartilhados entre serviços

---

### Docker Compose para deploy (não Kubernetes)

**Escolhido para Fase 1-3.**

```yaml
services:
  atlas:
    build: .
    ports: ["8000:8000"]
    env_file: .env
    volumes:
      - ./data:/app/data
```

Por que não Kubernetes:

- 1 serviço, 1 usuário, 1 máquina
- Kubernetes é para orquestrar dezenas de containers
- Docker Compose faz o mesmo para escala pequena
- Custo cognitivo do K8s é enorme para 0 benefício neste momento

Quando migrar para Kubernetes:

- Quando houver 3+ serviços independentes
- Quando precisar de auto-scaling
- Quando deploy for em cloud com múltiplas instâncias

---

## Decisões da Fase 2

### ChromaDB local (não Pinecone)

**Planejado para Fase 2.**

ChromaDB:

- Roda localmente (zero custo, zero latência de rede)
- Persiste em disco (SQLite internamente)
- API simples para upsert/query
- Suficiente para milhares de documentos

Pinecone:

- Cloud-hosted (custo, latência)
- Serverless (escala infinita)
- Para centenas de milhares de documentos

Para Fase 2, ChromaDB é a escolha correta. Se escalar para 100K+ docs, migrar para Pinecone.

---

### OpenAI Embeddings (text-embedding-3-small)

**Planejado para Fase 2.**

- `text-embedding-3-small`: barato ($0.02/1M tokens), qualidade suficiente
- `text-embedding-3-large`: melhor qualidade, mais caro — usar se small não for suficiente
- Alternativa open-source: `sentence-transformers` (grátis, roda local, qualidade menor)

---

### RAG simples (não LangChain)

**Planejado para Fase 2.**

RAG será implementado com 3 funções simples:

1. `retrieve(query)` → busca documentos no ChromaDB
2. `build_context(docs)` → monta contexto para Claude
3. `generate(question, context)` → Claude responde

Sem LangChain. Sem frameworks. ~100 linhas de código.

Por que não LangChain:

- Adiciona complexidade sem valor proporcional
- Breaking changes frequentes
- Debug é difícil (camadas de abstração)
- 100 linhas de código próprio > 1 framework de 10K linhas

---

## Decisões adiadas

| Tecnologia | Fase | Trigger para adoção |
| ---------- | ---- | ------------------- |
| PostgreSQL | 4 | Concurrent writes necessários ou query lenta |
| Redis | 4 | Múltiplos workers ou cache persistente |
| Kafka | 4+ | Necessidade de processar 1000+ eventos/minuto |
| Kubernetes | 4+ | 3+ serviços independentes ou auto-scaling |
| Terraform | 4+ | Infra cloud que precisa ser reproduzível |
| Pinecone | 4+ | 100K+ documentos no vector store |
| LangChain | Nunca | Complexidade não justificada para nosso caso |
| GraphQL | Nunca | REST é suficiente, menos complexidade |

---

## Custo mensal por fase

| Fase | Componente | Custo |
| ---- | ---------- | ----- |
| 1 | Claude API (Haiku + Sonnet) | $10-30 |
| 1 | Google APIs | $0 (quota gratuita) |
| 1 | Infra | $0 (local) |
| 2 | + OpenAI Embeddings | $5 |
| 3 | + VPS (se deploy remoto) | $10-20 |
| 4 | + PostgreSQL managed | $15 |
| 4 | + Redis managed | $10 |

**Total Fase 1**: ~$10-30/mês
**Total Fase 4**: ~$50-100/mês

---

## Princípio de decisão

```text
"A melhor arquitetura é aquela que você consegue rodar,
debugar e explicar em 5 minutos."

Se precisa de um diagrama de 10 caixas para explicar
como seu sistema funciona, ele é complexo demais
para a fase em que está.
```

---

## Log de decisões

| Data | Decisão | Status |
| ---- | ------- | ------ |
| Abr 2026 | Python + FastAPI | Confirmado |
| Abr 2026 | SQLite (não PostgreSQL) | Fase 1-3 |
| Abr 2026 | Claude API | Confirmado |
| Abr 2026 | Google APIs diretas (não MCP) | Fase 1 |
| Abr 2026 | feedparser para RSS | Fase 1 |
| Abr 2026 | lru_cache (não Redis) | Fase 1-2 |
| Abr 2026 | Docker Compose (não K8s) | Fase 1-3 |
| Abr 2026 | ChromaDB (não Pinecone) | Fase 2 |
| Abr 2026 | RAG simples (não LangChain) | Fase 2 |
| Abr 2026 | Enterprise arch → visão de longo prazo | Referência |
