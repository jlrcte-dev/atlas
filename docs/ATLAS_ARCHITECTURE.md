# ATLAS ARCHITECTURE — Central Intelligence Hub

**Versao**: 2.0 | **Abril 2026** | **Status**: Visao de longo prazo (horizonte 2 anos)

> **IMPORTANTE**: Este documento descreve a arquitetura TARGET (onde queremos chegar).
> O plano de execucao atual esta em [ATLAS_ROADMAP_V2.md](ATLAS_ROADMAP_V2.md).
> A implementacao segue uma abordagem incremental em 4 fases.

---

## Indice

1. [Estado Atual vs Visao](#estado-atual-vs-visao)
2. [Ecossistema](#ecossistema)
3. [Arquitetura Global](#arquitetura-global)
4. [Camadas do Sistema](#camadas-do-sistema)
5. [Fluxo de Dados](#fluxo-de-dados)
6. [Estrutura de Pastas](#estrutura-de-pastas)
7. [Separacao de Dominios](#separacao-de-dominios)
8. [Arquitetura de IA](#arquitetura-de-ia)
9. [Estrategia de Integracao](#estrategia-de-integracao)
10. [Governanca e Seguranca](#governanca-e-seguranca)
11. [Escalabilidade](#escalabilidade)

---

## Estado Atual vs Visao

### O que existe HOJE (Fase 1)

```text
Telegram / API
      |
  FastAPI + SQLite
      |
  +---------+---------+---------+
  |         |         |         |
Calendar  Drive     Gmail     RSS
(Google)  (Google)  (Google)  (feeds)
      |
    Claude API (classificacao + respostas)
```

Stack: Python + FastAPI + SQLite + Claude + Google APIs
Infra: Docker Compose local
Users: 1

### Para onde vamos (Fase 4 — horizonte 2 anos)

```text
                  Integrações Externas
                  (Google, APIs financeiras, legal)
                         |
              +----------+----------+
              |   ATLAS CORE (Hub)  |
              |                     |
              |  Knowledge Layer    |
              |  Intelligence Layer |
              |  Integration Layer  |
              +----+--------+------+
                   |        |
         +---------+--------+---------+
         |         |        |         |
    TradeArena  Derivativos Cartorio  KIP
```

Stack: Python + FastAPI + PostgreSQL + ChromaDB/Pinecone + Redis + Claude + Google APIs
Infra: Docker Compose ou Kubernetes
Users: Multiplos com RBAC

### Como chegamos la

```text
Fase 1 → Stubs viram APIs reais (SQLite, local)
Fase 2 → Embeddings + RAG simples (+ ChromaDB)
Fase 3 → Scheduler + dominios conectados (+ KIP, TradeArena)
Fase 4 → Agentes + multi-user (+ PostgreSQL, Redis, RBAC)
```

Cada transicao e feita APENAS quando a fase anterior esta validada e funcionando.

---

## Ecossistema

### KIP (Knowledge Intake Pipeline)

- Pipeline de ingestao de dados (HTML, documentos, web)
- Deduplicacao, catalogacao, validacao
- Estado: estavel e validado
- Conexao com Atlas: Fase 3

### TradeArena

- Mercados de previsao + gamificacao + blockchain
- Depende de dados estruturados de alta qualidade
- Conexao com Atlas: Fase 3 (dados de mercado fluem para o Atlas)

### Derivativos

- Trading profissional, portfolio, risco
- Depende de analise e alertas
- Conexao com Atlas: Fase 3 (trades e posicoes visiveis no Atlas)

### Cartorio

- Sistema legal/registral, compliance (COAF, DOI)
- Depende de organizacao documental e audit trail
- Conexao com Atlas: Fase 3 (documentos e compliance)

### Google Workspace

- Drive: documentos, contratos, arquivos
- Calendar: agenda, reunioes, prazos
- Gmail: emails, comunicacao
- Conexao com Atlas: **Fase 1 (prioridade maxima)**

---

## Arquitetura Global

### Padrao Hub-and-Spoke

ATLAS e o hub central. Todos os sistemas se conectam a ele, nao entre si.

```text
     Google Drive ----+
     Google Calendar --+---- ATLAS ----+---- TradeArena
     Gmail ------------+    (Hub)     +---- Derivativos
     KIP --------------+              +---- Cartorio
     APIs externas ----+
```

Principios:

1. **Single source of truth**: Atlas e o repositorio canonico de inteligencia
2. **Hub-first**: Toda comunicacao passa pelo Atlas
3. **Domain isolation**: Cada dominio e independente
4. **API-first**: Tudo e exposto via API, nada e hardcoded
5. **Human-in-the-loop**: Acoes sensiveis requerem aprovacao

---

## Camadas do Sistema

### Camada 1: Ingestao

Traz dados para dentro do sistema.

| Fonte | Fase | Metodo |
| ----- | ---- | ------ |
| Google Drive | 1 | Google Drive API |
| Google Calendar | 1 | Google Calendar API |
| Gmail | 1 | Gmail API |
| RSS | 1 | feedparser |
| KIP | 3 | Adapter HTTP |
| APIs financeiras | 3 | REST adapters |
| APIs legais | 4 | REST adapters |

Saida: dados normalizados para a camada de processamento.

### Camada 2: Processamento

Transforma dados brutos em informacao utilizavel.

Fase 1:
- Categorizacao simples (por pasta, por tipo, manual)
- Filtragem e busca por texto

Fase 2:
- Embeddings (text-embedding-3-small)
- Extracao de entidades basica
- Enriquecimento com contexto

Fase 4:
- NER avancado (pessoas, empresas, contratos)
- Mapeamento de relacionamentos
- Metricas derivadas

### Camada 3: Conhecimento

Armazena e torna dados consultaveis.

| Fase | Storage | Uso |
| ---- | ------- | --- |
| 1 | SQLite | Catalogo de documentos, audit log, usuarios |
| 2 | + ChromaDB | Embeddings, busca semantica |
| 4 | + PostgreSQL | Dados relacionais complexos, concurrent writes |
| 4 | + Redis | Cache de consultas frequentes |

### Camada 4: Inteligencia

Gera insights e apoia decisoes.

| Fase | Capacidade |
| ---- | ---------- |
| 1 | Claude para classificacao e respostas naturais |
| 2 | RAG simples (busca semantica + Claude) |
| 3 | Sugestoes proativas, alertas de prazo |
| 4 | Agentes de dominio, decisoes assistidas |

### Camada 5: Integracao

Expoe inteligencia do Atlas para sistemas externos.

| Fase | Interface |
| ---- | --------- |
| 1 | REST API (FastAPI) + Telegram bot |
| 3 | + Webhooks para sistemas externos |
| 4 | + API autenticada com API keys + RBAC |

### Camada 6: Aplicacao

Sistemas de dominio que consomem inteligencia do Atlas.

| Dominio | Consome | Fase |
| ------- | ------- | ---- |
| TradeArena | Sinais de mercado, inteligencia de predicao | 3 |
| Derivativos | Alertas de risco, analise de portfolio | 3 |
| Cartorio | Alertas de compliance, organizacao documental | 3 |

---

## Fluxo de Dados

### Fluxo 1: Consulta de agenda (Fase 1 — funciona hoje)

```text
Usuario: "Qual minha agenda de hoje?"
     |
Orchestrator → Claude classifica intent: GET_CALENDAR
     |
CalendarService → Google Calendar API
     |
Claude formata resposta natural
     |
Usuario recebe: "Voce tem 3 compromissos hoje: ..."
```

### Fluxo 2: Busca de documentos (Fase 1)

```text
Usuario: "Documentos sobre contratos"
     |
Orchestrator → Claude classifica intent: SEARCH_DRIVE
     |
DriveService → Google Drive API + DocumentCatalog (SQLite)
     |
Claude formata resposta
     |
Usuario recebe: "Encontrei 5 documentos: ..."
```

### Fluxo 3: Pergunta sobre conteudo (Fase 2 — RAG)

```text
Usuario: "O que dizem meus contratos sobre prazo de renovacao?"
     |
Orchestrator → Claude classifica intent: RAG_QUERY
     |
RAG Retriever → ChromaDB (busca semantica)
     |
Retorna: 3 documentos mais relevantes
     |
RAG Generator → Claude (resposta com contexto + citacoes)
     |
Usuario recebe: "Segundo o contrato X (pag 3), o prazo..."
```

### Fluxo 4: Alerta proativo (Fase 3)

```text
Scheduler (cron, 07:00):
     |
ComplianceCheck → DocumentCatalog
     |
Detecta: "Contrato X vence em 30 dias"
     |
Telegram Bot → notificacao para usuario
```

### Fluxo 5: Decisao assistida (Fase 4)

```text
TradingAgent analisa portfolio
     |
Detecta: "Delta exposure excede limite em 5%"
     |
Gera recomendacao: "Reduzir posicao SPY em 10%"
     |
Envia para ApprovalService → aguarda aprovacao
     |
Aprovado → executa acao
Rejeitado → loga e descarta
```

---

## Estrutura de Pastas

### Fase 1 (atual)

```text
atlas-ai-assistant/
├── app/
│   ├── main.py
│   ├── api/          (routes, schemas)
│   ├── agent/        (orchestrator, intent classifier, policies)
│   ├── core/         (config, logging, security, exceptions)
│   ├── db/           (models, repositories, session)
│   ├── integrations/ (calendar, drive, gmail, claude, rss, telegram)
│   ├── services/     (calendar, drive, inbox, news, briefing, approval)
│   └── scheduler/    (jobs)
├── tests/
├── .env
├── requirements.txt
└── docker-compose.yml
```

### Fase 2 (adicoes)

```text
app/
├── integrations/
│   └── embeddings_client.py    (NOVO — OpenAI embeddings)
├── services/
│   ├── knowledge_service.py    (NOVO — busca semantica)
│   └── rag_service.py          (NOVO — retrieval + generation)
└── db/
    └── vector_store.py         (NOVO — ChromaDB wrapper)
```

### Fase 3 (adicoes)

```text
app/
├── integrations/
│   ├── kip_adapter.py          (NOVO — dados do KIP)
│   ├── tradearena_client.py    (NOVO — dados de mercado)
│   └── derivatives_client.py   (NOVO — dados de trading)
├── services/
│   ├── alert_service.py        (NOVO — alertas proativos)
│   └── pipeline_service.py     (NOVO — processamento de docs)
└── scheduler/
    └── jobs.py                 (EXPANDIR — briefing matinal, checks de prazo)
```

### Fase 4 (adicoes)

```text
app/
├── agents/                     (NOVO — diretorio)
│   ├── base_agent.py
│   ├── market_agent.py
│   ├── trading_agent.py
│   └── compliance_agent.py
├── auth/                       (NOVO — multi-user)
│   ├── jwt_manager.py
│   └── rbac.py
└── domains/                    (NOVO — logica de dominio)
    ├── tradearena/
    ├── derivatives/
    └── cartorio/
```

A estrutura cresce organicamente. Nenhum diretorio e criado antes de ser necessario.

---

## Separacao de Dominios

### Principio

Cada dominio (TradeArena, Derivativos, Cartorio) sera:

1. **Independente**: pode evoluir sem afetar outros
2. **Loosely coupled**: comunica via API do Atlas, nao acessa DB de outros
3. **Domain-driven**: usa linguagem do dominio

### TradeArena (Fase 3+)

Atlas fornece:
- Sinais de mercado agregados
- Inteligencia de predicao
- Dados de acuracia

TradeArena fornece ao Atlas:
- Eventos de predicao
- Resultados de mercado

### Derivativos (Fase 3+)

Atlas fornece:
- Alertas de risco
- Analise de performance
- Sugestoes de rebalanceamento

Derivativos fornece ao Atlas:
- Trades executados
- Estado do portfolio

### Cartorio (Fase 3+)

Atlas fornece:
- Organizacao documental
- Alertas de compliance (COAF, DOI, LGPD)
- Audit trail

Cartorio fornece ao Atlas:
- Documentos legais
- Status de filings

---

## Arquitetura de IA

### Fase 1: Claude como classificador e gerador

```text
Mensagem do usuario
     |
Claude (Haiku) → classifica intent + extrai parametros
     |
Service executa acao
     |
Claude (Sonnet) → formata resposta natural
```

Sem RAG. Sem agentes. Sem embeddings.

### Fase 2: RAG simples

```text
Pergunta do usuario
     |
Embedder → converte pergunta em vetor
     |
ChromaDB → busca documentos similares (top 3)
     |
Context Builder → monta prompt com docs relevantes
     |
Claude (Sonnet) → responde citando fontes
```

Implementacao: ~100 linhas de codigo, sem framework.

### Fase 4: Agentes de dominio

```text
Agente recebe tarefa
     |
1. Retrieve: busca contexto via RAG
2. Reason: analisa com Claude
3. Recommend: gera recomendacao
4. Approve: submete para aprovacao humana
5. Execute: age (se aprovado)
```

Cada agente e especializado:

- **Market Agent**: analisa sinais, detecta anomalias
- **Trading Agent**: avalia risco, sugere hedge
- **Compliance Agent**: monitora prazos, valida LGPD

---

## Estrategia de Integracao

### Fase 1: APIs diretas

```text
Atlas → Google Calendar API (REST)
Atlas → Google Drive API (REST)
Atlas → Gmail API (REST)
Atlas → Claude API (REST)
Atlas → RSS feeds (HTTP)
```

Autenticacao: OAuth2 para Google, API key para Claude.

### Fase 3: APIs bidirecionais

```text
Atlas ← → TradeArena (REST)
Atlas ← → Derivativos (REST)
Atlas ← → Cartorio (REST)
Atlas ← → KIP (REST)
```

### Fase 4: Eventos (se necessario)

Avaliar se event-driven e necessario. Triggers para adocao:

- Mais de 1000 eventos/minuto
- Necessidade de replay de eventos
- Multiplos consumidores independentes

Se sim: Kafka ou AWS SQS.
Se nao: REST + webhooks e suficiente.

---

## Governanca e Seguranca

### Human-in-the-loop (todas as fases)

O sistema de aprovacao ja existe no starter kit:

- Acoes de escrita (criar evento, enviar email) requerem aprovacao
- Draft actions ficam pendentes ate confirmacao
- Audit log registra tudo

### LGPD (Fase 3+)

Quando dados pessoais entrarem no sistema:

- Consentimento explicito para processamento
- Direito de acesso: usuario pode ver seus dados
- Direito de delecao: usuario pode pedir remocao
- Retencao: dados expiram conforme politica

### Audit Trail (todas as fases)

Ja implementado no starter kit (`AuditLog` model):

```text
- Quem fez (actor)
- O que fez (action_type)
- Resultado (status)
- Quando (timestamp)
- Contexto (metadata_json)
```

### Encriptacao (Fase 4)

- Em transito: HTTPS/TLS (obrigatorio quando acessivel pela internet)
- Em repouso: encriptacao do disco (quando em cloud)
- Secrets: variaveis de ambiente, nunca no codigo

---

## Escalabilidade

### Fase 1-2: Escala zero

- 1 usuario, 1 processo, 1 arquivo SQLite
- Docker Compose local
- Sem preocupacao com escala

### Fase 3: Escala minima

- 1-3 usuarios
- Avaliar VPS para acesso remoto
- SQLite ainda suficiente (WAL mode para reads concorrentes)

### Fase 4: Escala moderada

- 5+ usuarios
- PostgreSQL para concurrent writes
- Redis para cache
- Multiplos workers (uvicorn --workers 4)
- Docker Compose em VPS

### Futuro: Escala enterprise

- Kubernetes se houver 3+ servicos
- Pinecone se houver 100K+ documentos
- Kafka se houver 1000+ eventos/minuto
- Multi-region se houver requisito de latencia

Cada nivel de escala e ativado por evidencia, nao por antecipacao.

---

## Resumo

Este documento descreve **para onde o ATLAS vai** em 2 anos.

A execucao segue o [ATLAS_ROADMAP_V2.md](ATLAS_ROADMAP_V2.md):

- Fase 1: fazer funcionar (stubs → APIs reais)
- Fase 2: fazer pensar (embeddings + RAG)
- Fase 3: fazer agir (automacoes + dominios)
- Fase 4: fazer escalar (agentes + multi-user)

A arquitetura enterprise e o destino. O roadmap pragmatico e o caminho.
