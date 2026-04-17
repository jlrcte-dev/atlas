# ATLAS — Visão Estratégica

**Versão**: 2.1 | **Abril 2026** | **Status**: Fase 1 concluída nas frentes principais — em refinamento

---

## O que é ATLAS

ATLAS é um **assistente inteligente operacional** que:

- Organiza dados (documentos, agenda, emails)
- Automatiza tarefas (alertas, briefings, categorização)
- Integra sistemas (Google Drive, Calendar, TradeArena, Derivativos, Cartório)
- Auxilia decisões (sugestões baseadas em dados reais)

Não é um produto para vender. É a **infraestrutura cognitiva do negócio**.

---

## Ecossistema

```text
ATLAS (cérebro central)
  ├── Google Drive     — documentos, contratos, arquivos
  ├── Google Calendar  — agenda, reuniões, prazos
  ├── Gmail            — emails, comunicação
  ├── KIP              — pipeline de ingestão de dados
  ├── TradeArena       — mercados de previsão, gamificação
  ├── Derivativos      — trading, portfolio, risco
  └── Cartório         — operações legais, compliance
```

ATLAS conecta tudo isso. Mas **não implementa tudo de uma vez**.

---

## Modelo de evolução

### Fase 1 — Operacional (Semanas 1-4)

Atlas funciona como ferramenta real no dia a dia.

- Google Calendar com dados reais
- Google Drive com busca e categorização
- Claude conectado para respostas inteligentes
- Gmail e RSS reais
- Briefing diário completo

**Stack**: Python + FastAPI + SQLite + Claude API + Google APIs
**Custo**: ~$10-30/mês

### Fase 2 — Inteligente (Semanas 5-8)

Atlas entende contexto e busca informações semanticamente.

- Embeddings + busca semântica (ChromaDB local)
- RAG simples (perguntar sobre documentos)
- Sugestões automáticas
- RSS real configurável

**Stack adicional**: ChromaDB + OpenAI Embeddings
**Custo**: ~$15-35/mês

### Fase 3 — Automatizado (Semanas 9-14)

Atlas executa tarefas e conecta domínios.

- Alertas proativos (prazos, compliance)
- Pipeline de documentos automatizado
- Dados do TradeArena e Derivativos fluindo
- KIP conectado
- Scheduler para tarefas recorrentes

**Custo**: ~$25-55/mês

### Fase 4 — Avançado (Semanas 15+)

Atlas raciocina, decide com aprovação e serve como plataforma.

- Agentes de domínio (Market, Trading, Compliance)
- Decisões assistidas
- Multi-user com RBAC
- Dashboard consolidado
- Preparação para SaaS

**Custo**: ~$50-100/mês

---

## Estado atual

A Fase 1 foi concluída nas integrações principais. O Atlas opera com dados reais no dia a dia:

```text
✅ FastAPI + SQLAlchemy + SQLite
✅ Orchestrator + Intent Classifier
✅ Google Calendar real (eventos + free slots)
✅ Google Drive real (listagem + busca)
✅ Gmail real (leitura + priorização)
✅ RSS / News real (feedparser)
✅ Briefing diário consolidando dados reais
✅ Módulo de email multi-provider (Gmail + Outlook/Microsoft 365)
✅ Autenticação Google (OAuth) e Microsoft (MSAL + PKCE)
✅ Telegram bot + Docker + Testes
```

**Próximo foco**: refinar a inteligência e a qualidade dos módulos já integrados (começando por email/inbox), não adicionar novas fontes.

---

## Investimento

| Fase | Infra/mês | Descrição |
| ---- | --------- | --------- |
| Fase 1 | $10-30 | Claude API + Google APIs (gratuitas) |
| Fase 2 | $15-35 | + OpenAI Embeddings |
| Fase 3 | $25-55 | + VPS para deploy remoto |
| Fase 4 | $50-100 | + PostgreSQL + Redis managed |

Sem investimento em infraestrutura pesada até que haja necessidade comprovada.

---

## Princípios

1. **Funcionar primeiro** — Substituir stubs por realidade antes de adicionar features
2. **Simplicidade** — Usar a tecnologia mais simples que resolve o problema
3. **Validação contínua** — Usar o Atlas diariamente antes de expandir
4. **Escalar com evidência** — Só trocar SQLite por PostgreSQL quando SQLite doer
5. **Construir sobre o existente** — O starter kit é bom, melhorar e não recomeçar

---

## Visão de longo prazo

O ATLAS pode evoluir para:

- **Plataforma interna** — equipe usando para decisões de negócio
- **AI OS** — agentes autônomos (com aprovação humana) para cada domínio
- **SaaS** — oferecer para outras empresas do mesmo segmento

Mas isso só acontece **depois** que a Fase 1 funcionar no dia a dia.

---

## Próximo passo

Criar projeto no Google Cloud Console, ativar APIs, e começar a Semana 1 da Fase 1.

Detalhes em [ATLAS_ROADMAP_V2.md](ATLAS_ROADMAP_V2.md).
