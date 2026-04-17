# ATLAS — Comece Aqui

**Versão**: 2.1 | **Abril 2026** | **Abordagem**: Execução pragmática | **Status**: Fase 1 concluída nas integrações principais

---

## O que é ATLAS?

ATLAS é o **cérebro operacional do negócio** — um assistente inteligente que organiza dados, automatiza tarefas, integra sistemas e auxilia na tomada de decisão.

**Não é um produto para vender (ainda).** É uma ferramenta interna que precisa funcionar no dia a dia.

---

## Estado atual

As integrações principais saíram da fase de stubs e operam com dados reais:

```
✅ FastAPI + Orchestrator + intent classification
✅ SQLAlchemy + SQLite + Telegram bot + Docker + Testes
✅ Google Calendar real (eventos + free slots)
✅ Google Drive real (listagem + busca)
✅ Gmail real (leitura + classificacao de prioridade)
✅ RSS / News real (feedparser)
✅ Briefing diario real (consolida Calendar + Inbox + News)
✅ Modulo de email multi-provider (Gmail + Outlook/Microsoft 365)
✅ Autenticacao Google (OAuth) e Microsoft (MSAL + PKCE) funcionais
✅ Troca de provider de email por configuracao (EMAIL_PROVIDER)
✅ InboxService e Briefing preservados sem regressao
```

**A Fase 1 foi concluida nas frentes principais.** O próximo foco natural é refinar a qualidade e inteligência dos módulos já integrados — começando por email/inbox.

---

## Leia nesta ordem

### Se você tem 10 minutos
1. **[ATLAS_ROADMAP_V2.md](docs/ATLAS_ROADMAP_V2.md)** — O plano real de execução

### Se vai implementar
1. **[ATLAS_ROADMAP_V2.md](docs/ATLAS_ROADMAP_V2.md)** — Roadmap semanal da Fase 1
2. **[QUICK_REFERENCE.md](docs/QUICK_REFERENCE.md)** — Cheat sheet para dev
3. **[TECHNICAL_DECISIONS.md](docs/TECHNICAL_DECISIONS.md)** — Por que cada escolha

### Se precisa da visão de longo prazo
1. **[EXECUTIVE_SUMMARY.md](docs/EXECUTIVE_SUMMARY.md)** — Visão estratégica atualizada
2. **[ATLAS_ARCHITECTURE.md](docs/ATLAS_ARCHITECTURE.md)** — Arquitetura enterprise (horizonte 2 anos)

---

## Próximo passo concreto

A Fase 1 de integração real foi essencialmente concluída. O Atlas entrou na fase de **refinamento dos módulos e aumento de inteligência**.

Próximo foco natural: melhorar a qualidade dos módulos já integrados, começando por **email/inbox** (classificação mais inteligente, priorização contextual, summarization).

Para ativar a integração Outlook (opcional):

```text
1. Registrar app no Azure AD (Mobile and desktop applications, Mail.Read)
2. Definir MICROSOFT_CLIENT_ID no .env
3. Rodar: python scripts/auth_microsoft.py
4. Definir EMAIL_PROVIDER=outlook no .env
```

---

## Documentação completa

| Documento | Propósito | Prioridade |
|-----------|-----------|------------|
| [ATLAS_ROADMAP_V2.md](docs/ATLAS_ROADMAP_V2.md) | Plano de execução pragmático (4 fases) | **PRINCIPAL** |
| [QUICK_REFERENCE.md](docs/QUICK_REFERENCE.md) | Referência rápida para devs | Alta |
| [TECHNICAL_DECISIONS.md](docs/TECHNICAL_DECISIONS.md) | Justificativa de cada escolha técnica | Alta |
| [EXECUTIVE_SUMMARY.md](docs/EXECUTIVE_SUMMARY.md) | Visão estratégica para stakeholders | Média |
| [ATLAS_ARCHITECTURE.md](docs/ATLAS_ARCHITECTURE.md) | Arquitetura enterprise (visão 2 anos) | Referência futura |
| [IMPLEMENTATION_ROADMAP.md](docs/IMPLEMENTATION_ROADMAP.md) | Roadmap original v1 (superseded by v2) | Arquivo |
| [INDEX.md](docs/INDEX.md) | Índice de todos os documentos | Navegação |

---

## Princípios que guiam o ATLAS

1. **Funcionar primeiro** — Código rodando > documentação sobre código futuro
2. **Simplicidade** — SQLite, não PostgreSQL. Cron, não Kafka. Local, não cloud.
3. **Valor imediato** — Cada semana entrega algo utilizável
4. **Escalar com evidência** — Adicionar tecnologia quando a atual doer (medido, não sentido)
5. **Construir sobre o que existe** — O starter kit é bom. Melhore, não recomece.

---

**Status**: Pronto para Semana 1 da Fase 1  
**Próximo**: Criar projeto Google Cloud + conectar APIs reais
