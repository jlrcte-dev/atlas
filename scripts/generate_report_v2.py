"""Generate comprehensive PDF technical report for Atlas AI Assistant v0.2."""

from fpdf import FPDF


# ==============================================================================
# PDF CLASS
# ==============================================================================

class R(FPDF):
    """Atlas AI Assistant report renderer."""

    # -- Colors ----------------------------------------------------------------
    C_PRIMARY = (22, 54, 120)
    C_ACCENT = (41, 98, 182)
    C_TEXT = (35, 35, 35)
    C_MUTED = (110, 110, 110)
    C_LIGHT = (230, 235, 245)
    C_WHITE = (255, 255, 255)
    C_SUCCESS = (26, 120, 62)
    C_WARN = (180, 95, 6)
    C_DANGER = (180, 30, 30)
    C_TABLE_HDR = (30, 58, 138)
    C_TABLE_ALT = (241, 243, 250)

    def header(self):
        if self.page_no() == 1:
            return
        self.set_font("Helvetica", "B", 8)
        self.set_text_color(*self.C_MUTED)
        self.cell(95, 6, "Atlas AI Assistant -- Relatorio Tecnico v0.2", align="L")
        self.cell(95, 6, f"Pagina {self.page_no()}", align="R", new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(*self.C_ACCENT)
        self.set_line_width(0.4)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(5)

    def footer(self):
        self.set_y(-12)
        self.set_font("Helvetica", "I", 7)
        self.set_text_color(*self.C_MUTED)
        self.cell(0, 6, "Documento gerado automaticamente | Abril 2026 | Confidencial", align="C")

    # -- Section titles --------------------------------------------------------

    def cover_title(self, text):
        self.set_font("Helvetica", "B", 32)
        self.set_text_color(*self.C_PRIMARY)
        self.cell(0, 16, text, align="C", new_x="LMARGIN", new_y="NEXT")

    def cover_sub(self, text):
        self.set_font("Helvetica", "", 14)
        self.set_text_color(*self.C_MUTED)
        self.cell(0, 8, text, align="C", new_x="LMARGIN", new_y="NEXT")

    def h1(self, text):
        self.ln(3)
        self.set_font("Helvetica", "B", 16)
        self.set_text_color(*self.C_PRIMARY)
        self.cell(0, 10, text, new_x="LMARGIN", new_y="NEXT")
        y = self.get_y()
        self.set_draw_color(*self.C_ACCENT)
        self.set_line_width(0.6)
        self.line(10, y, 200, y)
        self.ln(5)

    def h2(self, text):
        self.ln(2)
        self.set_font("Helvetica", "B", 12)
        self.set_text_color(*self.C_ACCENT)
        self.cell(0, 8, text, new_x="LMARGIN", new_y="NEXT")
        self.ln(1)

    def h3(self, text):
        self.ln(1)
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(*self.C_TEXT)
        self.cell(0, 7, text, new_x="LMARGIN", new_y="NEXT")

    # -- Body elements ---------------------------------------------------------

    def p(self, text, size=10):
        self.set_font("Helvetica", "", size)
        self.set_text_color(*self.C_TEXT)
        self.multi_cell(0, 5.2, text)
        self.ln(1.5)

    def bullet(self, text):
        self.set_font("Helvetica", "", 10)
        self.set_text_color(*self.C_TEXT)
        x = self.l_margin + 8
        self.set_x(x)
        self.multi_cell(self.w - self.r_margin - x, 5.2, f"- {text}")

    def bullet_bold(self, label, text):
        self.set_font("Helvetica", "", 10)
        self.set_text_color(*self.C_TEXT)
        x = self.l_margin + 8
        self.set_x(x)
        self.multi_cell(self.w - self.r_margin - x, 5.2, f"- **{label}:** {text}", markdown=True)

    def spacer(self, h=3):
        self.ln(h)

    # -- Tables ----------------------------------------------------------------

    def table(self, headers, rows, widths, align=None):
        if align is None:
            align = ["L"] * len(headers)
        # Header
        self.set_font("Helvetica", "B", 8.5)
        self.set_fill_color(*self.C_TABLE_HDR)
        self.set_text_color(*self.C_WHITE)
        self.set_draw_color(200, 200, 200)
        for i, h in enumerate(headers):
            self.cell(widths[i], 7, h, border=1, fill=True, align="C")
        self.ln()
        # Rows
        self.set_font("Helvetica", "", 8.5)
        self.set_text_color(*self.C_TEXT)
        for ri, row in enumerate(rows):
            if self.get_y() > 268:
                self.add_page()
            if ri % 2 == 1:
                self.set_fill_color(*self.C_TABLE_ALT)
            else:
                self.set_fill_color(*self.C_WHITE)
            for i, cell in enumerate(row):
                self.cell(widths[i], 6.5, str(cell), border=1, fill=True, align=align[i])
            self.ln()
        self.ln(2)

    # -- Code blocks -----------------------------------------------------------

    def code(self, text):
        self.set_font("Courier", "", 7.5)
        self.set_text_color(30, 30, 30)
        self.set_fill_color(245, 245, 248)
        self.set_draw_color(210, 210, 215)
        x = self.get_x()
        lines = text.strip().split("\n")
        h = len(lines) * 4.2 + 5
        if self.get_y() + h > 272:
            self.add_page()
        y = self.get_y()
        self.rect(x, y, 190, h, style="D")
        self.rect(x + 0.3, y + 0.3, 189.4, h - 0.6, style="F")
        self.set_xy(x + 3, y + 2.5)
        for line in lines:
            self.cell(184, 4.2, line, new_x="LMARGIN", new_y="NEXT")
            self.set_x(x + 3)
        self.set_xy(x, y + h + 2)

    # -- KPI boxes -------------------------------------------------------------

    def kpi_row(self, items):
        """items: list of (label, value, color_tuple)"""
        n = len(items)
        w = 190 / n
        x0 = self.l_margin
        y0 = self.get_y()
        for i, (label, value, color) in enumerate(items):
            x = x0 + i * w
            self.set_fill_color(*color)
            self.rect(x, y0, w - 2, 22, style="F")
            # Value
            self.set_xy(x, y0 + 2)
            self.set_font("Helvetica", "B", 18)
            self.set_text_color(*self.C_WHITE)
            self.cell(w - 2, 10, str(value), align="C")
            # Label
            self.set_xy(x, y0 + 12)
            self.set_font("Helvetica", "", 8)
            self.cell(w - 2, 7, label, align="C")
        self.set_y(y0 + 26)

    # -- Status badge ----------------------------------------------------------

    def badge(self, text, color):
        self.set_font("Helvetica", "B", 8)
        self.set_fill_color(*color)
        self.set_text_color(*self.C_WHITE)
        tw = self.get_string_width(text) + 6
        self.cell(tw, 5.5, text, fill=True, align="C")
        self.set_text_color(*self.C_TEXT)


# ==============================================================================
# REPORT BUILDER
# ==============================================================================

def build():
    pdf = R()
    pdf.set_auto_page_break(auto=True, margin=18)

    # ==========================================================================
    # COVER PAGE
    # ==========================================================================
    pdf.add_page()
    pdf.ln(35)
    pdf.cover_title("Atlas AI Assistant")
    pdf.ln(2)
    pdf.cover_sub("Relatorio Tecnico Completo")
    pdf.ln(1)
    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(*R.C_MUTED)
    pdf.cell(0, 7, "Assistente Operacional Pessoal com Inteligencia Artificial", align="C",
             new_x="LMARGIN", new_y="NEXT")

    pdf.ln(15)
    pdf.set_draw_color(*R.C_ACCENT)
    pdf.set_line_width(1.0)
    pdf.line(65, pdf.get_y(), 145, pdf.get_y())
    pdf.ln(15)

    meta = [
        ("Versao", "0.2.0  (MVP Foundation + Quality Stack)"),
        ("Data", "10 de Abril de 2026"),
        ("Stack", "Python 3.14 | FastAPI | SQLAlchemy | SQLite | Docker"),
        ("Interface", "Telegram Bot API + REST API (14 endpoints)"),
        ("IA Engine", "Claude (Anthropic) -- tool_use ready"),
        ("Testes", "54 testes automatizados | 80.8% cobertura"),
        ("Quality Gate", "ruff + mypy + bandit + pip-audit | 0 issues"),
    ]
    for label, val in meta:
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(*R.C_TEXT)
        pdf.cell(42, 6.5, f"{label}:", align="R")
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(*R.C_MUTED)
        pdf.cell(0, 6.5, f"   {val}", new_x="LMARGIN", new_y="NEXT")

    # ==========================================================================
    # TABLE OF CONTENTS
    # ==========================================================================
    pdf.add_page()
    pdf.h1("Indice")
    toc = [
        "1. Resumo Executivo",
        "2. Metricas do Projeto",
        "3. Arquitetura do Sistema",
        "4. Modulos Implementados",
        "   4.1 Inbox Copilot",
        "   4.2 Calendar Copilot",
        "   4.3 News Briefing",
        "   4.4 Daily Briefing",
        "   4.5 Sistema de Aprovacao",
        "5. Orquestrador e Classificacao de Intent",
        "6. API REST -- 14 Endpoints",
        "7. Integracao Telegram",
        "8. Modelo de Dados",
        "9. Modelo de Seguranca",
        "10. Stack de Qualidade (Quality Gate)",
        "   10.1 Ferramentas Configuradas",
        "   10.2 Ruff -- Lint e Formatacao",
        "   10.3 Mypy -- Checagem de Tipos",
        "   10.4 Bandit -- Seguranca",
        "   10.5 pip-audit -- Vulnerabilidades",
        "   10.6 Pre-commit Hooks",
        "11. Cobertura de Testes",
        "12. Registro de Correcoes e Melhorias",
        "13. Estrutura de Arquivos",
        "14. Proximos Passos",
    ]
    for item in toc:
        indent = 8 if item.startswith("   ") else 0
        pdf.set_font("Helvetica", "" if indent else "B", 10)
        pdf.set_text_color(*R.C_TEXT)
        pdf.set_x(pdf.l_margin + indent)
        pdf.cell(0, 5.8, item.strip(), new_x="LMARGIN", new_y="NEXT")

    # ==========================================================================
    # 1. RESUMO EXECUTIVO
    # ==========================================================================
    pdf.add_page()
    pdf.h1("1. Resumo Executivo")
    pdf.p(
        "O Atlas AI Assistant e um assistente operacional pessoal alimentado por Claude, "
        "projetado para centralizar fluxos de informacao diarios (email, calendario, noticias) "
        "em inteligencia acionavel entregue via Telegram. O sistema opera sob o principio "
        "'assistir primeiro, executar nunca sem aprovacao' -- le, analisa, resume e propoe acoes, "
        "mas jamais executa operacoes sensiveis de forma autonoma."
    )
    pdf.p(
        "Esta versao (0.2.0) consolida a fundacao tecnica completa do MVP: todos os 5 modulos "
        "de negocio estao implementados, o orquestrador com classificacao de intent funciona, "
        "a API REST expoe 14 endpoints, o webhook do Telegram esta pronto, e uma stack completa "
        "de qualidade de codigo foi configurada e executada com zero issues pendentes."
    )

    pdf.h2("Principios de Design")
    for p in [
        "Read-only por padrao -- nenhuma escrita sem aprovacao humana explicita",
        "Arquitetura local-first -- dados e processamento rodam localmente",
        "Baixo custo operacional -- SQLite, sem infra paga alem da API Claude",
        "Composicao modular -- cada modulo e independente, adicionavel/removivel",
        "Seguranca como restricao -- politicas na camada de orquestracao, nao nos servicos",
        "Single-user (MVP) -- multi-tenancy e expansao futura planejada",
    ]:
        pdf.bullet(p)

    # ==========================================================================
    # 2. METRICAS
    # ==========================================================================
    pdf.add_page()
    pdf.h1("2. Metricas do Projeto")

    pdf.kpi_row([
        ("Arquivos Python", "33", R.C_PRIMARY),
        ("Linhas de Codigo", "1933", R.C_ACCENT),
        ("Linhas de Teste", "452", R.C_SUCCESS),
        ("Testes", "54", R.C_SUCCESS),
    ])
    pdf.spacer(2)
    pdf.kpi_row([
        ("Cobertura", "80.8%", (41, 98, 182)),
        ("Endpoints API", "14", R.C_PRIMARY),
        ("Modelos DB", "6", R.C_ACCENT),
        ("Intents", "9", R.C_SUCCESS),
    ])
    pdf.spacer(2)
    pdf.kpi_row([
        ("Ruff Issues", "0", R.C_SUCCESS),
        ("Mypy Errors", "0", R.C_SUCCESS),
        ("Bandit Findings", "0", R.C_SUCCESS),
        ("CVEs (pip-audit)", "0", R.C_SUCCESS),
    ])

    pdf.spacer(5)
    pdf.table(
        ["Categoria", "Quantidade", "Detalhe"],
        [
            ["Modulos de negocio", "5", "Inbox, Calendar, News, Briefing, Approval"],
            ["Services", "5", "inbox, calendar, news, briefing, approval"],
            ["Integration stubs", "4", "Gmail, Calendar, RSS, Telegram"],
            ["Repositorios DB", "4", "User, DraftAction, AuditLog, DailyBriefing"],
            ["Arquivos de config", "6", "pyproject.toml, pre-commit, req x3, .env"],
            ["Ferramentas de qualidade", "6", "ruff, mypy, bandit, pip-audit, pre-commit, dotenv-linter"],
        ],
        [48, 30, 112],
    )

    # ==========================================================================
    # 3. ARQUITETURA
    # ==========================================================================
    pdf.add_page()
    pdf.h1("3. Arquitetura do Sistema")

    pdf.h2("3.1 Fluxo de Dados")
    pdf.code(
        "Usuario --> Telegram Bot --> FastAPI Backend --> Orchestrator\n"
        "                                                    |\n"
        "                            +-----------------------+----------+\n"
        "                            |           |           |          |\n"
        "                       InboxSvc    CalendarSvc  NewsSvc  ApprovalSvc\n"
        "                            |           |           |          |\n"
        "                       GmailClient CalendarCli RSSClient  DB Repos\n"
        "                            |           |           |          |\n"
        "                       Google MCP  Google MCP  RSS Feeds   SQLite"
    )

    pdf.h2("3.2 Camadas da Aplicacao")
    layers = [
        ("API (app/api/)", "Fronteira HTTP -- validacao, serializacao, injecao de dependencias"),
        ("Agent (app/agent/)", "Decisao IA -- classificacao de intent, politicas, orquestracao"),
        ("Services (app/services/)", "Logica de negocio -- um servico por dominio, sem I/O direto"),
        ("Integrations (app/integrations/)", "Adaptadores externos -- Gmail, Calendar, RSS, Telegram"),
        ("DB (app/db/)", "Persistencia -- modelos ORM, repositorios, sessao"),
        ("Core (app/core/)", "Infraestrutura transversal -- config, logging, seguranca, excecoes"),
        ("Scheduler (app/scheduler/)", "Jobs agendados -- trigger de briefing diario"),
    ]
    for label, desc in layers:
        pdf.bullet_bold(label, desc)

    pdf.spacer(3)
    pdf.h2("3.3 Fluxo Read (sem aprovacao)")
    pdf.code(
        "User --> Telegram --> /chat --> Orchestrator --> Service --> Integration --> Response"
    )
    pdf.h2("3.4 Fluxo Write (com aprovacao)")
    pdf.code(
        "User --> /drafts/email --> ApprovalService.create_email_draft()\n"
        "  --> DraftAction(status=pending) + AuditLog(pending)\n"
        "  --> Response {id, status: pending}\n"
        "\n"
        "User --> /approvals/{id}/approve --> ApprovalService.confirm()\n"
        "  --> DraftAction(status=approved) + AuditLog(approved)\n"
        "  --> (Future) Integration executa a acao real"
    )

    # ==========================================================================
    # 4. MODULOS
    # ==========================================================================
    pdf.add_page()
    pdf.h1("4. Modulos Implementados")

    # 4.1 Inbox
    pdf.h2("4.1 Inbox Copilot")
    pdf.p(
        "Le, classifica por prioridade (alta/media/baixa) e resume emails. "
        "Identifica itens de acao e emails nao lidos."
    )
    pdf.table(
        ["Metodo", "Descricao", "Retorno"],
        [
            ["get_recent_emails(max)", "Lista emails recentes", "list[dict]"],
            ["summarize_emails()", "Resume com breakdown de prioridade", "dict"],
            ["get_summary()", "Alias retrocompativel", "dict"],
        ],
        [48, 72, 70],
    )
    pdf.p("Campos: total, high_priority, medium_priority, low_priority, unread, action_items, summary.")

    # 4.2 Calendar
    pdf.h2("4.2 Calendar Copilot")
    pdf.p(
        "Recupera agenda diaria, calcula horarios livres entre compromissos "
        "dentro do horario comercial (08:00-18:00) e prepara propostas de eventos."
    )
    pdf.table(
        ["Metodo", "Descricao", "Retorno"],
        [
            ["get_today_events()", "Agenda do dia", "dict"],
            ["find_free_slots(min)", "Gaps livres >= duracao pedida", "list[dict]"],
            ["propose_event(...)", "Monta payload de proposta", "dict"],
        ],
        [48, 72, 70],
    )
    pdf.h3("Algoritmo de Free Slots")
    pdf.code(
        "1. Ordena eventos por horario de inicio\n"
        "2. Percorre gaps entre work_start(08:00) e cada evento\n"
        "3. Filtra gaps >= duration_minutes solicitado\n"
        "4. Inclui gap final ate work_end(18:00)\n"
        "5. Retorna lista de {start, end, duration_minutes}"
    )

    # 4.3 News
    pdf.h2("4.3 News Briefing")
    pdf.p("Busca artigos de feeds RSS, normaliza, categoriza e gera resumo executivo agrupado.")
    pdf.table(
        ["Metodo", "Descricao", "Retorno"],
        [
            ["fetch_rss()", "Artigos brutos", "list[dict]"],
            ["normalize_articles()", "Schema uniforme", "list[dict]"],
            ["summarize_news()", "Agrupado por categoria", "dict"],
        ],
        [48, 72, 70],
    )

    # 4.4 Briefing
    pdf.h2("4.4 Daily Briefing")
    pdf.p(
        "Consolida inbox + calendario + noticias + horarios livres num briefing "
        "executivo estruturado. Persiste no banco e entrega via Telegram."
    )
    pdf.code(
        "BRIEFING DIARIO\n"
        "==============================\n"
        "AGENDA -- 3 compromisso(s)\n"
        "  - 09:00 | Call com equipe\n"
        "  - 12:00 | Almoco\n"
        "  - 15:00 | Revisao semanal\n"
        "\n"
        "HORARIOS LIVRES -- 3 slot(s)\n"
        "  - 08:00-09:00 (60min)\n"
        "  - 10:00-12:00 (120min)\n"
        "  - 16:00-18:00 (120min)\n"
        "\n"
        "INBOX -- 3 emails -- 1 prioritario(s), 1 nao lido(s).\n"
        "  * cliente@empresa.com: Reuniao pendente\n"
        "\n"
        "NOTICIAS -- 3 noticia(s) em 3 categoria(s)"
    )

    # 4.5 Approval
    pdf.add_page()
    pdf.h2("4.5 Sistema de Aprovacao (Critico)")
    pdf.p(
        "Todas as operacoes de escrita passam obrigatoriamente pelo fluxo de aprovacao. "
        "Cada transicao de estado gera um registro imutavel no audit log. "
        "Tentativa de dupla resolucao levanta ActionAlreadyResolvedError."
    )
    pdf.h3("Maquina de Estados")
    pdf.code("pending --> approved --> (executed)\npending --> rejected")

    pdf.spacer(2)
    pdf.table(
        ["Operacao", "Tipo", "Requer Aprovacao"],
        [
            ["Ler emails", "READ", "Nao"],
            ["Criar draft de email", "DRAFT", "Nao"],
            ["Enviar email", "WRITE", "SIM"],
            ["Ler calendario", "READ", "Nao"],
            ["Criar evento", "WRITE", "SIM"],
            ["Ler noticias", "READ", "Nao"],
            ["Gerar briefing", "READ", "Nao"],
        ],
        [70, 30, 90],
        align=["L", "C", "C"],
    )
    pdf.table(
        ["Metodo", "Descricao"],
        [
            ["create_email_draft(payload)", "Cria draft + AuditLog(pending)"],
            ["create_event_proposal(payload)", "Cria proposta + AuditLog(pending)"],
            ["confirm(draft)", "Aprova + AuditLog(approved) + resolved_at"],
            ["reject(draft)", "Rejeita + AuditLog(rejected) + resolved_at"],
            ["get_draft(id)", "Busca draft por ID"],
            ["list_pending()", "Lista acoes pendentes"],
        ],
        [65, 125],
    )

    # ==========================================================================
    # 5. ORQUESTRADOR
    # ==========================================================================
    pdf.add_page()
    pdf.h1("5. Orquestrador e Classificacao de Intent")

    pdf.h2("5.1 Interface Principal")
    pdf.code(
        "class Orchestrator:\n"
        "    def handle_request(self, user_id: str, message: str) -> dict:\n"
        '        # Retorno: {intent, confidence, success, data, message}\n'
        "\n"
        "# Fluxo:\n"
        "# 1. IntentClassifier.classify(message) -> ClassifiedIntent\n"
        "# 2. Dispatch via _HANDLERS[intent] -> handler function\n"
        "# 3. Handler chama servico correspondente\n"
        "# 4. Retorno estruturado com data + mensagem legivel"
    )

    pdf.h2("5.2 Intents Suportados (9)")
    pdf.table(
        ["Intent", "Comando", "Keywords", "Confianca"],
        [
            ["GET_INBOX_SUMMARY", "/inbox", "email, inbox, caixa, mensagens", "1.0 / 0.5-0.9"],
            ["GET_CALENDAR", "/agenda", "agenda, compromisso, reuniao", "1.0 / 0.5-0.9"],
            ["CREATE_EVENT", "-", "criar evento, agendar, marcar", "0.9"],
            ["GET_NEWS", "/news", "noticia, news, manchete, rss", "1.0 / 0.5-0.9"],
            ["GET_DAILY_BRIEFING", "/briefing", "briefing, resumo do dia", "1.0 / 0.9"],
            ["APPROVE_ACTION", "/approve {id}", "aprovar, confirmar + #ID", "1.0 / 0.8"],
            ["REJECT_ACTION", "/reject {id}", "rejeitar, negar + #ID", "1.0 / 0.8"],
            ["HELP", "/help, /start", "ajuda, comandos", "1.0"],
            ["UNKNOWN", "-", "(fallback)", "0.0"],
        ],
        [38, 32, 72, 48],
        align=["L", "C", "L", "C"],
    )

    pdf.h2("5.3 Pipeline de Classificacao (3 Prioridades)")
    pdf.bullet("P1 - Comandos Telegram (/inbox, /approve 42) -- confianca 1.0")
    pdf.bullet("P2 - Frases multi-palavra ('resumo do dia', 'criar evento') -- confianca 0.9")
    pdf.bullet("P3 - Keywords individuais com scoring por contagem -- confianca 0.5 a 0.85")
    pdf.spacer(2)
    pdf.p(
        "Estrutura projetada para substituicao futura por Claude com tool_use -- "
        "basta trocar o corpo de classify() mantendo o retorno ClassifiedIntent."
    )

    # ==========================================================================
    # 6. API REST
    # ==========================================================================
    pdf.add_page()
    pdf.h1("6. API REST -- 14 Endpoints")

    pdf.table(
        ["Metodo", "Path", "Descricao", "Auth"],
        [
            ["GET", "/health", "Health check", "-"],
            ["POST", "/chat", "Entry point principal (orquestrador)", "TG"],
            ["GET", "/inbox/summary", "Resumo da inbox com prioridades", "TG"],
            ["GET", "/calendar/today", "Agenda do dia", "TG"],
            ["GET", "/calendar/free-slots", "Horarios livres (param: duration)", "TG"],
            ["POST", "/calendar/propose-event", "Propor evento (via aprovacao)", "TG"],
            ["POST", "/drafts/email", "Criar draft de email (via aprovacao)", "TG"],
            ["POST", "/approvals/{id}/approve", "Aprovar acao pendente", "TG"],
            ["POST", "/approvals/{id}/reject", "Rejeitar acao pendente", "TG"],
            ["GET", "/news", "Briefing de noticias", "TG"],
            ["GET", "/news/briefing", "Alias para /news", "TG"],
            ["GET", "/briefing", "Gerar briefing diario completo", "TG"],
            ["POST", "/jobs/run-daily-briefing", "Trigger do scheduler", "Int"],
            ["POST", "/telegram/webhook", "Webhook do Telegram Bot", "TG"],
        ],
        [16, 55, 82, 37],
        align=["C", "L", "L", "C"],
    )

    pdf.h2("6.1 Exemplo: POST /chat")
    pdf.code(
        '// Request\n'
        '{"message": "mostra meus emails", "user_id": "default"}\n'
        '\n'
        '// Response\n'
        '{"intent": "get_inbox_summary", "confidence": 0.65,\n'
        ' "success": true,\n'
        ' "data": {"total": 3, "high_priority": 1, "unread": 1, ...},\n'
        ' "message": "3 emails -- 1 prioritario(s), 1 nao lido(s)."}'
    )
    pdf.h2("6.2 Exemplo: Fluxo de Aprovacao")
    pdf.code(
        '// 1. Criar draft\n'
        'POST /drafts/email {to, subject, body}\n'
        '--> {id: 1, status: "pending", type: "draft_email"}\n'
        '\n'
        '// 2. Aprovar\n'
        'POST /approvals/1/approve\n'
        '--> {id: 1, status: "approved", type: "draft_email"}\n'
        '\n'
        '// 3. Ou rejeitar\n'
        'POST /approvals/1/reject\n'
        '--> {id: 1, status: "rejected", type: "draft_email"}'
    )

    # ==========================================================================
    # 7. TELEGRAM
    # ==========================================================================
    pdf.add_page()
    pdf.h1("7. Integracao Telegram")

    pdf.p(
        "Bot Telegram implementado com httpx (sem dependencia adicional). "
        "Suporta mensagens de texto, comandos slash e callback queries para aprovacao."
    )
    pdf.table(
        ["Componente", "Implementacao", "Status"],
        [
            ["send_message()", "POST /sendMessage via httpx", "Funcional"],
            ["answer_callback_query()", "POST /answerCallbackQuery", "Funcional"],
            ["parse_update()", "Extrai text/callback de updates", "Funcional"],
            ["build_approval_keyboard()", "Inline keyboard Aprovar/Rejeitar", "Funcional"],
            ["is_authorized()", "Whitelist por TELEGRAM_ALLOWED_USER_ID", "Funcional"],
            ["Webhook endpoint", "POST /telegram/webhook no FastAPI", "Funcional"],
            ["Callback -> Command", "approve:42 -> /approve 42", "Funcional"],
        ],
        [52, 82, 56],
        align=["L", "L", "C"],
    )
    pdf.h2("7.1 Fluxo de Aprovacao via Telegram")
    pdf.code(
        "1. Usuario pede: 'responder email do cliente'\n"
        "2. Orchestrator cria DraftAction(pending)\n"
        "3. Bot envia mensagem + teclado inline [Aprovar] [Rejeitar]\n"
        "4. Usuario toca [Aprovar]\n"
        "5. Callback 'approve:42' -> traduzido para '/approve 42'\n"
        "6. Orchestrator confirma -> DraftAction(approved) + AuditLog"
    )

    # ==========================================================================
    # 8. MODELO DE DADOS
    # ==========================================================================
    pdf.h1("8. Modelo de Dados")
    pdf.p("6 entidades com ForeignKeys e ORM relationships (SQLAlchemy 2.0 DeclarativeBase):")

    pdf.table(
        ["Entidade", "Tabela", "Campos Principais", "Relacoes"],
        [
            ["User", "users", "id, name, telegram_id, created_at", "-> prefs, drafts, briefings"],
            ["UserPreference", "user_preferences", "user_id(FK), news_topics, briefing_time", "-> user"],
            ["DraftAction", "draft_actions", "user_id(FK), type, payload, status, resolved_at", "-> user"],
            ["AuditLog", "audit_logs", "action_type, status, user_id, metadata_json", "-"],
            ["NewsSource", "news_sources", "url (unique), category", "-"],
            ["DailyBriefing", "daily_briefings", "user_id(FK), content, created_at", "-> user"],
        ],
        [30, 34, 80, 46],
    )
    pdf.h2("8.1 Repositorios")
    pdf.table(
        ["Repositorio", "Metodos"],
        [
            ["UserRepository", "get, get_by_telegram_id, create, get_or_create"],
            ["DraftActionRepository", "create, get, update_status, list_pending, list_all"],
            ["AuditLogRepository", "log, list_recent"],
            ["DailyBriefingRepository", "create, get_latest"],
        ],
        [55, 135],
    )

    # ==========================================================================
    # 9. SEGURANCA
    # ==========================================================================
    pdf.add_page()
    pdf.h1("9. Modelo de Seguranca")

    pdf.h2("9.1 Cinco Camadas de Protecao")
    pdf.table(
        ["Camada", "Mecanismo", "Detalhe"],
        [
            ["1. Telegram Auth", "TELEGRAM_ALLOWED_USER_ID", "Whitelist de user ID"],
            ["2. Policy Engine", "SecurityPolicy (dataclass)", "Define acoes que precisam aprovacao"],
            ["3. Approval Flow", "DraftAction lifecycle", "pending -> approved/rejected"],
            ["4. OAuth Scopes", "Escopos minimos Google", "Read-only por padrao"],
            ["5. Audit Trail", "AuditLog (append-only)", "Registro imutavel de cada decisao"],
        ],
        [35, 55, 100],
    )

    pdf.h2("9.2 Mitigacao de Ameacas")
    pdf.table(
        ["Ameaca", "Mitigacao Implementada"],
        [
            ["Acesso nao autorizado", "Whitelist de Telegram user ID; reject silencioso"],
            ["Prompt injection via email", "Conteudo de email tratado como dados nao confiaveis"],
            ["Vazamento de segredos", "Segredos em .env via pydantic-settings; nunca no codigo"],
            ["Execucao nao autorizada", "Policy engine + fluxo de aprovacao obrigatorio"],
            ["Tampering do audit log", "Padrao append-only; sem endpoints de delete/update"],
            ["SQL injection", "SQLAlchemy ORM com queries parametrizadas"],
            ["Deps comprometidas", "pip-audit sem CVEs; verificacao continua via pre-commit"],
        ],
        [48, 142],
    )

    # ==========================================================================
    # 10. QUALITY GATE
    # ==========================================================================
    pdf.add_page()
    pdf.h1("10. Stack de Qualidade (Quality Gate)")

    pdf.p(
        "Stack completa de qualidade de codigo configurada e integrada via pyproject.toml "
        "e pre-commit hooks. Todas as ferramentas executaram com zero issues pendentes."
    )

    pdf.h2("10.1 Ferramentas Configuradas")
    pdf.table(
        ["Ferramenta", "Versao", "Categoria", "Funcao"],
        [
            ["ruff", "0.15.10", "Linter + Formatter", "Substitui flake8+black+isort (27 rule sets)"],
            ["mypy", "1.20.0", "Type Checker", "Validacao estatica de tipos + pydantic plugin"],
            ["bandit", "1.9.4", "Security Scanner", "Detecta SQL injection, segredos, eval/exec"],
            ["pip-audit", "2.10.0", "Dep Audit", "Verifica CVEs nas dependencias"],
            ["pytest-cov", "7.1.0", "Coverage", "Medicao de cobertura (threshold: 70%)"],
            ["pre-commit", "4.5.1", "Git Hooks", "Roda tudo automaticamente antes de commit"],
            ["dotenv-linter", "0.7.0", "Env Validation", "Valida formato do .env"],
            ["pytest-asyncio", "1.3.0", "Test Async", "Suporte a testes async (futuro)"],
            ["respx", "0.23.1", "HTTP Mock", "Mock de httpx para testes de integracao"],
        ],
        [32, 18, 35, 105],
    )

    pdf.h2("10.2 Ruff -- Regras Habilitadas (27 Sets)")
    pdf.code(
        "E    pycodestyle errors          W    pycodestyle warnings\n"
        "F    pyflakes                    I    isort (import sorting)\n"
        "N    pep8-naming                 UP   pyupgrade\n"
        "B    flake8-bugbear              SIM  flake8-simplify\n"
        "S    flake8-bandit (security)    A    flake8-builtins\n"
        "C4   flake8-comprehensions       T20  flake8-print\n"
        "RET  flake8-return               PTH  flake8-use-pathlib\n"
        "RUF  ruff-specific rules"
    )

    pdf.h2("10.3 Mypy -- Configuracao")
    pdf.code(
        "strict = false (progressive adoption)\n"
        "warn_return_any = true       warn_unused_configs = true\n"
        "warn_redundant_casts = true  warn_unused_ignores = true\n"
        "check_untyped_defs = true    no_implicit_optional = true\n"
        "plugins = [pydantic.mypy]\n"
        "\n"
        "Resultado: Success: no issues found in 27 source files"
    )

    pdf.h2("10.4 Bandit -- Resultado")
    pdf.code(
        "Total lines of code: 1486\n"
        "Total issues: 0 (1 suppressed: B104 bind-all intentional for Docker)\n"
        "Severity: High=0  Medium=0  Low=0"
    )

    pdf.h2("10.5 pip-audit -- Resultado")
    pdf.code("No known vulnerabilities found")

    pdf.h2("10.6 Pre-commit Hooks")
    pdf.table(
        ["Hook", "Fonte", "Acao"],
        [
            ["ruff", "ruff-pre-commit", "Lint + auto-fix"],
            ["ruff-format", "ruff-pre-commit", "Formatacao automatica"],
            ["mypy", "mirrors-mypy", "Type check com deps reais"],
            ["bandit", "PyCQA/bandit", "Security scan em app/"],
            ["trailing-whitespace", "pre-commit-hooks", "Remove espacos finais"],
            ["end-of-file-fixer", "pre-commit-hooks", "Garante newline final"],
            ["check-yaml", "pre-commit-hooks", "Valida YAML"],
            ["check-toml", "pre-commit-hooks", "Valida TOML"],
            ["check-added-large-files", "pre-commit-hooks", "Bloqueia >500KB"],
            ["check-merge-conflict", "pre-commit-hooks", "Detecta markers de conflito"],
            ["debug-statements", "pre-commit-hooks", "Detecta breakpoint()/pdb"],
            ["dotenv-linter", "wemake-services", "Valida .env files"],
        ],
        [42, 48, 100],
    )

    # ==========================================================================
    # 11. COBERTURA DE TESTES
    # ==========================================================================
    pdf.add_page()
    pdf.h1("11. Cobertura de Testes")

    pdf.table(
        ["Arquivo de Teste", "Qtd", "Escopo"],
        [
            ["test_intent_classifier.py", "17", "Keywords, frases, comandos, params, unknown"],
            ["test_orchestrator.py", "11", "Todos os intents, aprovacao E2E, erro handling"],
            ["test_services.py", "15", "Todos os metodos + backward compat"],
            ["test_approval.py", "11", "CRUD, guard dupla resolucao, queries, list_pending"],
            ["test_health.py", "1", "Health check da API (GET /health)"],
            ["conftest.py", "-", "Fixtures: in-memory SQLite, TestClient override"],
        ],
        [52, 12, 126],
        align=["L", "C", "L"],
    )
    pdf.p("Infraestrutura: banco SQLite in-memory por teste, FastAPI TestClient com override de deps. Execucao: 1.16s.")

    pdf.spacer(3)
    pdf.h2("11.1 Cobertura por Modulo")
    cov_data = [
        ("intent_classifier.py", 56, 0, 100.0),
        ("schemas.py", 53, 0, 100.0),
        ("config.py", 18, 0, 100.0),
        ("logging.py", 11, 0, 100.0),
        ("models.py", 54, 0, 100.0),
        ("approval_service.py", 39, 0, 100.0),
        ("briefing_service.py", 39, 0, 100.0),
        ("inbox_service.py", 22, 0, 100.0),
        ("news_service.py", 26, 0, 100.0),
        ("calendar_service.py", 44, 2, 95.5),
        ("rss_client.py", 28, 3, 89.3),
        ("orchestrator.py", 92, 13, 85.9),
        ("main.py", 19, 3, 84.2),
        ("calendar_client.py", 25, 4, 84.0),
        ("gmail_client.py", 27, 5, 81.5),
        ("repositories.py", 71, 16, 77.5),
        ("exceptions.py", 20, 6, 70.0),
        ("session.py", 16, 6, 62.5),
        ("routes.py", 109, 62, 43.1),
        ("telegram_bot.py", 55, 38, 30.9),
    ]
    rows = []
    for name, stmts, miss, cov in cov_data:
        pct = f"{cov:.1f}%"
        bar_len = int(cov / 5)
        bar = "|" * bar_len + "." * (20 - bar_len)
        rows.append([name, str(stmts), str(miss), pct, bar])
    pdf.table(
        ["Arquivo", "Stmts", "Miss", "Cover", "Barra"],
        rows,
        [50, 16, 14, 18, 92],
        align=["L", "C", "C", "C", "L"],
    )
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(*R.C_SUCCESS)
    pdf.cell(0, 8, "TOTAL: 824 stmts | 158 miss | 80.8% cobertura (threshold: 70%)",
             new_x="LMARGIN", new_y="NEXT")

    # ==========================================================================
    # 12. REGISTRO DE CORRECOES
    # ==========================================================================
    pdf.add_page()
    pdf.h1("12. Registro de Correcoes e Melhorias")

    pdf.h2("12.1 Ruff -- 16 Violacoes Corrigidas")
    pdf.table(
        ["Regra", "Qtd", "Descricao", "Correcao"],
        [
            ["UP042", "2", "str+Enum herdado junto", "Migrado para StrEnum"],
            ["B904", "2", "raise sem from em except", "Adicionado 'from None'"],
            ["S104", "1", "Bind 0.0.0.0 detectado", "nosec B104 (intencional Docker)"],
            ["E501", "2", "Linha >100 caracteres", "Reformatado"],
            ["I001", "4", "Imports desordenados", "Auto-sorted por isort"],
            ["UP017", "3", "timezone.utc obsoleto", "Migrado para datetime.UTC"],
            ["F401", "1", "Import nao usado", "Removido"],
            ["N806", "1", "Variavel UpperCase em funcao", "Renomeado para snake_case"],
        ],
        [18, 10, 70, 92],
        align=["C", "C", "L", "L"],
    )

    pdf.h2("12.2 Mypy -- 15 Erros de Tipo Corrigidos")
    pdf.table(
        ["Erro", "Qtd", "Arquivo(s)", "Correcao"],
        [
            ["Invalid base class 'Base'", "12", "models.py", "declarative_base() -> DeclarativeBase"],
            ["Returning Any", "2", "telegram_bot.py", "Tipagem explicita do resp.json()"],
            ["Missing return type", "1", "main.py", "AsyncGenerator[None] no lifespan"],
        ],
        [42, 10, 42, 96],
        align=["L", "C", "L", "L"],
    )

    pdf.h2("12.3 Melhorias de Arquitetura")
    for item in [
        "SQLAlchemy 2.0: migrado de declarative_base() para class Base(DeclarativeBase)",
        "Enums: migrado de (str, Enum) para StrEnum (Python 3.11+)",
        "Session typing: get_db() agora retorna Generator[Session] tipado",
        "FastAPI lifespan: migrado de @on_event('startup') para asynccontextmanager",
        "Excecao chaining: HTTPException com 'from None' para stack traces limpos",
        "datetime.UTC: uso do alias moderno ao inves de timezone.utc",
    ]:
        pdf.bullet(item)

    pdf.spacer(3)
    pdf.h2("12.4 Arquivos de Configuracao Criados")
    pdf.table(
        ["Arquivo", "Finalidade"],
        [
            ["pyproject.toml", "Config central: ruff, mypy, pytest, coverage, bandit"],
            [".pre-commit-config.yaml", "12 hooks automaticos antes de cada commit"],
            ["requirements.txt", "7 deps de producao"],
            ["requirements-dev.txt", "6 ferramentas de desenvolvimento"],
            ["requirements-test.txt", "5 deps de teste"],
        ],
        [55, 135],
    )

    # ==========================================================================
    # 13. ESTRUTURA DE ARQUIVOS
    # ==========================================================================
    pdf.add_page()
    pdf.h1("13. Estrutura de Arquivos")

    pdf.code(
        "atlas-ai-assistant/\n"
        "|\n"
        "|-- pyproject.toml                 Config central (ruff+mypy+pytest+bandit)\n"
        "|-- .pre-commit-config.yaml        12 hooks automaticos\n"
        "|-- requirements.txt               7 deps producao\n"
        "|-- requirements-dev.txt           6 ferramentas dev\n"
        "|-- requirements-test.txt          5 deps teste\n"
        "|-- Dockerfile                     Python 3.11-slim image\n"
        "|-- docker-compose.yml             Dev environment com hot-reload\n"
        "|-- .env.example                   Template de variaveis de ambiente\n"
        "|\n"
        "|-- app/\n"
        "|   |-- main.py                    FastAPI factory + lifespan + error handler\n"
        "|   |-- api/\n"
        "|   |   |-- routes.py              14 endpoints REST + webhook Telegram\n"
        "|   |   |-- schemas.py             12 Pydantic models (request/response)\n"
        "|   |-- agent/\n"
        "|   |   |-- orchestrator.py        Roteamento central de intents (9 handlers)\n"
        "|   |   |-- intent_classifier.py   Classificacao rule-based (StrEnum)\n"
        "|   |   |-- policies.py            Motor de politicas de aprovacao\n"
        "|   |-- core/\n"
        "|   |   |-- config.py              pydantic-settings (14 variaveis)\n"
        "|   |   |-- exceptions.py          4 excecoes customizadas\n"
        "|   |   |-- logging.py             Logging estruturado JSON\n"
        "|   |   |-- permissions.py         ActionType StrEnum\n"
        "|   |   |-- security.py            SecurityPolicy (read-only default)\n"
        "|   |-- db/\n"
        "|   |   |-- models.py              6 modelos ORM (DeclarativeBase)\n"
        "|   |   |-- repositories.py        4 repositorios (User, Draft, Audit, Briefing)\n"
        "|   |   |-- session.py             Engine + Session + Base + get_db()\n"
        "|   |-- integrations/\n"
        "|   |   |-- gmail_client.py        Gmail adapter (stub MCP-ready)\n"
        "|   |   |-- calendar_client.py     Calendar adapter (stub MCP-ready)\n"
        "|   |   |-- rss_client.py          RSS reader (stub)\n"
        "|   |   |-- telegram_bot.py        Telegram Bot (httpx, funcional)\n"
        "|   |   |-- google_mcp.py          (legacy, mantido para compat)\n"
        "|   |   |-- rss_reader.py          (legacy, mantido para compat)\n"
        "|   |-- services/\n"
        "|   |   |-- inbox_service.py       Inbox Copilot\n"
        "|   |   |-- calendar_service.py    Calendar Copilot + free slots\n"
        "|   |   |-- news_service.py        News Briefing + categorias\n"
        "|   |   |-- briefing_service.py    Daily Briefing consolidado\n"
        "|   |   |-- approval_service.py    Aprovacao + audit log\n"
        "|   |-- scheduler/\n"
        "|       |-- jobs.py                Job de briefing diario\n"
        "|\n"
        "|-- tests/\n"
        "|   |-- conftest.py                Fixtures (in-memory SQLite, TestClient)\n"
        "|   |-- test_intent_classifier.py  17 testes\n"
        "|   |-- test_orchestrator.py       11 testes\n"
        "|   |-- test_services.py           15 testes\n"
        "|   |-- test_approval.py           11 testes\n"
        "|   |-- test_health.py             1 teste"
    )

    # ==========================================================================
    # 14. PROXIMOS PASSOS
    # ==========================================================================
    pdf.add_page()
    pdf.h1("14. Proximos Passos")

    pdf.h2("14.1 Imediato (Pos-MVP)")
    for s in [
        "Integrar Claude real no orquestrador (tool_use substitui keyword matching)",
        "Conectar Google Workspace MCP real (Gmail + Calendar com OAuth)",
        "Implementar parser RSS real com feedparser",
        "Configurar webhook do Telegram em producao (ou polling mode)",
        "Adicionar APScheduler para briefing diario automatico",
        "Aumentar cobertura de testes: routes.py (43%) e telegram_bot.py (31%)",
    ]:
        pdf.bullet(s)

    pdf.spacer(3)
    pdf.h2("14.2 Medio Prazo")
    for s in [
        "Memoria de conversacao (historico de chat por usuario)",
        "Execucao real de acoes apos aprovacao (enviar email, criar evento)",
        "Deteccao de conflitos de horario no calendario",
        "Ranking de relevancia de noticias via Claude",
        "Briefings em linguagem natural (nao template)",
        "Migracao SQLite -> PostgreSQL quando concorrencia exigir",
        "Autenticacao JWT na API para clientes nao-Telegram",
    ]:
        pdf.bullet(s)

    pdf.spacer(3)
    pdf.h2("14.3 Longo Prazo")
    for s in [
        "Suporte multi-usuario com isolamento de dados",
        "Canal WhatsApp via Business API",
        "Interface de voz (mensagens de audio do Telegram)",
        "Integracao com task managers (Todoist, Linear, Notion)",
        "Assistente de arquivos (busca e resumo no Google Drive via MCP)",
        "Deploy cloud (Railway / Fly.io / AWS ECS)",
        "Observabilidade (Grafana + Sentry)",
        "Sistema de plugins para integracoes de terceiros",
    ]:
        pdf.bullet(s)

    # ==========================================================================
    # BACK COVER
    # ==========================================================================
    pdf.add_page()
    pdf.ln(60)
    pdf.set_font("Helvetica", "B", 20)
    pdf.set_text_color(*R.C_PRIMARY)
    pdf.cell(0, 12, "Atlas AI Assistant", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)
    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(*R.C_MUTED)
    pdf.cell(0, 7, "Versao 0.2.0 | MVP Foundation + Quality Stack", align="C",
             new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 7, "54 testes | 80.8% cobertura | 0 issues", align="C",
             new_x="LMARGIN", new_y="NEXT")
    pdf.ln(10)
    pdf.set_draw_color(*R.C_ACCENT)
    pdf.set_line_width(0.6)
    pdf.line(70, pdf.get_y(), 140, pdf.get_y())
    pdf.ln(10)
    pdf.set_font("Helvetica", "I", 9)
    pdf.cell(0, 6, "Documento gerado automaticamente em 10 de Abril de 2026", align="C",
             new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, "Python 3.14 | FastAPI | SQLAlchemy | Claude (Anthropic)", align="C",
             new_x="LMARGIN", new_y="NEXT")

    # ==========================================================================
    # SAVE
    # ==========================================================================
    out = "Atlas_AI_Assistant_Report_v2.pdf"
    pdf.output(out)
    return out


if __name__ == "__main__":
    path = build()
    print(f"Relatorio gerado: {path}")
