# Atlas AI Assistant - Project Scope

## Objective
Assistente operacional pessoal com foco em inbox, agenda, notícias e aprovações.

## Principles
- Low cost
- Security first
- Local-first architecture
- Human-in-the-loop
- Modular growth

## MVP Modules
1. Inbox Copilot
2. Calendar Copilot
3. News Briefing
4. Daily Briefing
5. Approval System

## Core Rules
- Default mode is read-only
- Sensitive actions require approval
- Audit logs are mandatory
- Secrets must stay out of code
- Only trusted integrations are allowed

## Suggested Next Steps
- Conectar Claude real no orquestrador
- Integrar MCP real do Google Workspace
- Substituir RSS stub por parser real
- Adicionar autenticação do Telegram
- Evoluir SQLite para PostgreSQL quando necessário
