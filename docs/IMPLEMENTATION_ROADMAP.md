# ATLAS — Roadmap de Implementação

**Versão**: 2.0 | **Abril 2026**

> **NOTA**: Este documento foi atualizado para refletir a abordagem pragmática.
> O plano detalhado de execução está em [ATLAS_ROADMAP_V2.md](ATLAS_ROADMAP_V2.md).
> A arquitetura enterprise de longo prazo está em [ATLAS_ARCHITECTURE.md](ATLAS_ARCHITECTURE.md).

---

## Visão geral das fases

```text
Fase 1 (Sem 1-4)   → Operacional     → Stubs viram APIs reais
Fase 2 (Sem 5-8)   → Inteligente     → Embeddings + RAG simples
Fase 3 (Sem 9-14)  → Automatizado    → Scheduler + domínios conectados
Fase 4 (Sem 15+)   → Avançado        → Agentes + multi-user + SaaS
```

---

## Fase 1 — Operacional (Semanas 1-4)

### Objetivo

Substituir todos os stubs por integrações reais. Atlas funciona no dia a dia.

### Semana 1: Google Calendar + Claude

| Dia | Tarefa | Validação |
| --- | ------ | --------- |
| 1-2 | Criar projeto GCP, ativar Calendar API, OAuth2 | `credentials.json` gerado |
| 1-2 | Reescrever `calendar_client.py` com API real | `GET /calendar/today` retorna dados reais |
| 3-4 | Criar `claude_client.py`, conectar ao Orchestrator | `POST /chat "minha agenda"` responde via Claude |
| 5 | Testes, ajustes, fallback se Claude falhar | Testes passam, Telegram funciona |

### Semana 2: Google Drive

| Dia | Tarefa | Validação |
| --- | ------ | --------- |
| 1-2 | Ativar Drive API, criar `drive_client.py` | `list_files()` retorna arquivos reais |
| 3 | Criar `drive_service.py` + rotas na API | `GET /drive/files` funciona |
| 4 | Criar modelo `DocumentCatalog` no SQLite | Sync Drive → catálogo persiste |
| 5 | Integrar com chat: "meus documentos" funciona | `POST /chat` busca no Drive |

### Semana 3: Gmail + RSS + Briefing

| Dia | Tarefa | Validação |
| --- | ------ | --------- |
| 1-2 | Gmail API real (substituir stub) | `GET /inbox/summary` dados reais |
| 3 | RSS real com feedparser | `GET /news` feeds reais |
| 4 | Briefing diário consolida tudo (real) | `GET /briefing` completo e útil |
| 5 | Testes end-to-end, zero stubs | Nenhum mock em produção |

### Semana 4: Estabilização

| Dia | Tarefa | Validação |
| --- | ------ | --------- |
| 1-2 | Error handling, retries, fallbacks | Sistema não crasha com API offline |
| 3 | Docker Compose atualizado, health check | `docker compose up` funciona |
| 4-5 | Uso real por 2 dias, anotar ajustes | Lista de melhorias para Fase 2 |

### Definition of Done — Fase 1

```text
□ GET /calendar/today → eventos reais
□ GET /drive/files → arquivos reais
□ GET /inbox/summary → emails reais
□ GET /news → notícias reais
□ GET /briefing → briefing completo com dados reais
□ POST /chat → conversa natural via Claude
□ Zero stubs em produção
□ Audit log registra todas as operações
□ Funciona via Telegram
□ Testes passam
```

---

## Fase 2 — Inteligente (Semanas 5-8)

### Objetivo

Atlas entende contexto e busca informações semanticamente.

### Entregas

- ChromaDB local para vector search
- Embeddings dos documentos do Drive
- RAG simples: perguntar sobre documentos e receber resposta contextual
- Sugestões: "Você tem reunião sobre X, encontrei docs relacionados"
- Tags de domínio nos documentos

### Tecnologia adicionada

```text
+ chromadb
+ openai (embeddings)
```

### Definition of Done — Fase 2

```text
□ Busca semântica retorna docs relevantes (não apenas match de texto)
□ "O que dizem meus contratos sobre prazo?" → RAG responde
□ Sugestões correlacionam agenda com documentos
□ Performance: busca < 2 segundos
□ Briefing inclui insights baseados em contexto
```

---

## Fase 3 — Automatizado (Semanas 9-14)

### Objetivo

Atlas executa tarefas e conecta domínios.

### Entregas

- Scheduler: briefing matinal automático, check de prazos
- Alertas proativos: "Contrato X vence em 30 dias"
- Pipeline: novo doc no Drive → categorizado → embeddado → buscável
- Dados do TradeArena e/ou Derivativos fluindo para o Atlas
- KIP adapter conectado

### Definition of Done — Fase 3

```text
□ Briefing matinal automático no Telegram
□ Alertas de prazo funcionam
□ Pipeline de ingestão processa novos docs em < 5 min
□ Dados de pelo menos 1 sistema externo (TradeArena ou Derivativos) fluem
□ KIP adapter funciona com dados reais
```

---

## Fase 4 — Avançado (Semanas 15+)

### Objetivo

Atlas raciocina, decide com aprovação e serve como plataforma.

### Entregas

- Agentes de domínio (Market, Trading, Compliance)
- Decisões assistidas com approval
- Multi-user com RBAC
- Dashboard consolidado
- Avaliar migração: SQLite → PostgreSQL, ChromaDB → Pinecone, lru_cache → Redis

### Definition of Done — Fase 4

```text
□ Pelo menos 1 agente funciona end-to-end
□ Decisões assistidas geram valor mensurável
□ API suporta autenticação multi-user
□ Sistema roda por 1 semana sem intervenção
```

---

## Regra entre fases

Não avançar para a próxima fase até que a atual esteja:

1. **Funcionando** — sem bugs críticos
2. **Sendo usada** — no dia a dia, não apenas em testes
3. **Validada** — gera valor real e mensurável
4. **Estável** — roda sem crashes por pelo menos 1 semana

---

## Referências

- Plano detalhado com código: [ATLAS_ROADMAP_V2.md](ATLAS_ROADMAP_V2.md)
- Decisões técnicas: [TECHNICAL_DECISIONS.md](TECHNICAL_DECISIONS.md)
- Arquitetura de longo prazo: [ATLAS_ARCHITECTURE.md](ATLAS_ARCHITECTURE.md)
