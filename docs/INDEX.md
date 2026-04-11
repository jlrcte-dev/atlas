# ATLAS — Índice de Documentação

**Atualizado**: Abril 2026 | **Abordagem ativa**: Roadmap Pragmático v2

---

## Documentos Ativos (usar agora)

| Documento | O que contém | Quando ler |
| --------- | ------------ | ---------- |
| [ATLAS_ROADMAP_V2.md](ATLAS_ROADMAP_V2.md) | Plano de execução em 4 fases, roadmap semanal, erros a evitar, princípios de evolução | **Primeiro documento a ler. Plano ativo.** |
| [QUICK_REFERENCE.md](QUICK_REFERENCE.md) | Stack atual, estrutura de pastas, comandos, troubleshooting | Enquanto programa |
| [TECHNICAL_DECISIONS.md](TECHNICAL_DECISIONS.md) | Por que SQLite (não PostgreSQL), por que ChromaDB (não Pinecone), trade-offs | Quando precisar justificar uma escolha |
| [EXECUTIVE_SUMMARY.md](EXECUTIVE_SUMMARY.md) | Visão estratégica, ecossistema, fases de evolução, custos | Para apresentar a stakeholders |
| [README.md](../README.md) | Ponto de entrada, estado atual, próximo passo concreto | Se é a primeira vez abrindo o projeto |

## Documentos de Referência (visão de longo prazo)

| Documento | O que contém | Quando ler |
| --------- | ------------ | ---------- |
| [ATLAS_ARCHITECTURE.md](ATLAS_ARCHITECTURE.md) | Arquitetura enterprise completa (hub-and-spoke, 6 camadas, domínios, AI) | Quando planejar Fase 3-4 |
| [IMPLEMENTATION_ROADMAP.md](IMPLEMENTATION_ROADMAP.md) | Roadmap original v1 (enterprise, 12-16 semanas) | Arquivo — substituído pelo v2 |

---

## Guia rápido por papel

**Estou implementando a Fase 1:**

1. [ATLAS_ROADMAP_V2.md](ATLAS_ROADMAP_V2.md) — Seção "Roadmap Semanal — Fase 1"
2. [QUICK_REFERENCE.md](QUICK_REFERENCE.md) — Stack, comandos, estrutura

**Preciso tomar uma decisão técnica:**

1. [TECHNICAL_DECISIONS.md](TECHNICAL_DECISIONS.md) — Trade-offs documentados
2. [ATLAS_ROADMAP_V2.md](ATLAS_ROADMAP_V2.md) — Seção "Princípios de Evolução"

**Estou apresentando o projeto:**

1. [EXECUTIVE_SUMMARY.md](EXECUTIVE_SUMMARY.md) — Visão completa
2. [ATLAS_ROADMAP_V2.md](ATLAS_ROADMAP_V2.md) — Seção "Modelo de Evolução em 4 Fases"

**Estou planejando o futuro (Fase 3+):**

1. [ATLAS_ARCHITECTURE.md](ATLAS_ARCHITECTURE.md) — Visão enterprise
2. [TECHNICAL_DECISIONS.md](TECHNICAL_DECISIONS.md) — Seção "Alternativas e Futuro"

---

## Evolução da documentação

A documentação seguiu o mesmo princípio do código: começou ambiciosa, depois foi corrigida para ser pragmática.

- **v1** (Abril 2026): Arquitetura enterprise com PostgreSQL, Kafka, Kubernetes, 200+ páginas
- **v2** (Abril 2026): Roadmap pragmático — substituir stubs, usar o que existe, entregar valor na Semana 1

A v1 permanece como referência para o horizonte de 2 anos. A v2 é o plano ativo.
