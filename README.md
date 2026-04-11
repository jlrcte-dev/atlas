# ATLAS — Comece Aqui

**Versão**: 2.0 | **Abril 2026** | **Abordagem**: Execução pragmática

---

## O que é ATLAS?

ATLAS é o **cérebro operacional do negócio** — um assistente inteligente que organiza dados, automatiza tarefas, integra sistemas e auxilia na tomada de decisão.

**Não é um produto para vender (ainda).** É uma ferramenta interna que precisa funcionar no dia a dia.

---

## Estado atual

O projeto já tem:

```
✅ FastAPI funcionando
✅ Orchestrator com intent classification
✅ Services: Inbox, Calendar, News, Briefing, Approval
✅ SQLAlchemy + SQLite
✅ Telegram bot
✅ Docker
✅ Testes

❌ Todas as integrações são STUBS (dados fake)
❌ Google Drive não existe
❌ Claude não está conectado
❌ Nenhum dado real flui pelo sistema
```

**O trabalho da Fase 1 é substituir stubs por realidade.**

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

```
1. Criar projeto no Google Cloud Console
2. Ativar Calendar API + Drive API + Gmail API
3. Gerar credentials.json (OAuth2)
4. Obter ANTHROPIC_API_KEY
5. Reescrever calendar_client.py com API real
6. Testar: GET /calendar/today → dados reais
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
