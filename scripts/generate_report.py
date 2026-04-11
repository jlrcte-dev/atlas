"""Generate PDF report for Atlas AI Assistant project."""

from fpdf import FPDF
from datetime import datetime


class AtlasReport(FPDF):
    """Custom PDF with header/footer for Atlas AI Assistant."""

    def header(self):
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(100, 100, 100)
        self.cell(0, 8, "Atlas AI Assistant - Relatorio Tecnico", align="L")
        self.cell(0, 8, f"Abril 2026", align="R", new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(40, 80, 160)
        self.set_line_width(0.5)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(4)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(130, 130, 130)
        self.cell(0, 10, f"Pagina {self.page_no()}/{{nb}}", align="C")

    def section_title(self, title: str):
        self.set_font("Helvetica", "B", 14)
        self.set_text_color(30, 60, 140)
        self.ln(4)
        self.cell(0, 10, title, new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(30, 60, 140)
        self.set_line_width(0.3)
        self.line(10, self.get_y(), 120, self.get_y())
        self.ln(3)

    def subsection_title(self, title: str):
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(60, 60, 60)
        self.ln(2)
        self.cell(0, 8, title, new_x="LMARGIN", new_y="NEXT")
        self.ln(1)

    def body_text(self, text: str):
        self.set_font("Helvetica", "", 10)
        self.set_text_color(40, 40, 40)
        self.multi_cell(0, 5.5, text)
        self.ln(1)

    def bullet(self, text: str, indent: int = 10):
        self.set_font("Helvetica", "", 10)
        self.set_text_color(40, 40, 40)
        left = self.l_margin + indent
        self.set_x(left)
        w = self.w - self.r_margin - left
        self.multi_cell(w, 5.5, f"- {text}")

    def bold_bullet(self, label: str, text: str, indent: int = 10):
        self.set_font("Helvetica", "", 10)
        self.set_text_color(40, 40, 40)
        left = self.l_margin + indent
        self.set_x(left)
        w = self.w - self.r_margin - left
        self.multi_cell(w, 5.5, f"- **{label}:** {text}", markdown=True)

    def add_table(self, headers: list, rows: list, col_widths: list):
        # Header
        self.set_font("Helvetica", "B", 9)
        self.set_fill_color(30, 60, 140)
        self.set_text_color(255, 255, 255)
        for i, h in enumerate(headers):
            self.cell(col_widths[i], 7, h, border=1, fill=True, align="C")
        self.ln()

        # Rows
        self.set_font("Helvetica", "", 9)
        self.set_text_color(40, 40, 40)
        fill = False
        for row in rows:
            if self.get_y() > 265:
                self.add_page()
            if fill:
                self.set_fill_color(240, 243, 250)
            else:
                self.set_fill_color(255, 255, 255)
            max_h = 7
            for i, cell in enumerate(row):
                self.cell(col_widths[i], max_h, str(cell), border=1, fill=True)
            self.ln()
            fill = not fill
        self.ln(2)

    def code_block(self, text: str):
        self.set_font("Courier", "", 8)
        self.set_text_color(30, 30, 30)
        self.set_fill_color(245, 245, 245)
        self.set_draw_color(200, 200, 200)
        x = self.get_x()
        y = self.get_y()
        lines = text.strip().split("\n")
        h = len(lines) * 4.5 + 4
        if y + h > 270:
            self.add_page()
            y = self.get_y()
        self.rect(x, y, 190, h)
        self.set_xy(x + 2, y + 2)
        for line in lines:
            self.cell(0, 4.5, line, fill=True, new_x="LMARGIN", new_y="NEXT")
            self.set_x(x + 2)
        self.set_xy(x, y + h + 2)


def build_report() -> str:
    pdf = AtlasReport()
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=20)

    # ══════════════════════════════════════════════════════════════
    # COVER PAGE
    # ══════════════════════════════════════════════════════════════
    pdf.add_page()
    pdf.ln(50)
    pdf.set_font("Helvetica", "B", 28)
    pdf.set_text_color(30, 60, 140)
    pdf.cell(0, 15, "Atlas AI Assistant", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)
    pdf.set_font("Helvetica", "", 16)
    pdf.set_text_color(80, 80, 80)
    pdf.cell(0, 10, "Relatorio Tecnico do Projeto", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)
    pdf.set_font("Helvetica", "", 12)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 8, "Assistente Operacional Pessoal com IA", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(20)

    pdf.set_draw_color(30, 60, 140)
    pdf.set_line_width(0.8)
    pdf.line(60, pdf.get_y(), 150, pdf.get_y())
    pdf.ln(15)

    info = [
        ("Versao", "0.2.0 (MVP Foundation)"),
        ("Data", "10 de Abril de 2026"),
        ("Stack", "Python 3.14 / FastAPI / SQLAlchemy / SQLite"),
        ("Interface", "Telegram Bot + REST API"),
        ("IA Engine", "Claude (Anthropic)"),
        ("Testes", "54 testes - 100% passing"),
    ]
    for label, value in info:
        pdf.set_font("Helvetica", "B", 11)
        pdf.set_text_color(60, 60, 60)
        pdf.cell(50, 7, f"{label}:", align="R")
        pdf.set_font("Helvetica", "", 11)
        pdf.set_text_color(40, 40, 40)
        pdf.cell(0, 7, f"  {value}", new_x="LMARGIN", new_y="NEXT")

    # ══════════════════════════════════════════════════════════════
    # 1. VISAO GERAL
    # ══════════════════════════════════════════════════════════════
    pdf.add_page()
    pdf.section_title("1. Visao Geral do Projeto")

    pdf.body_text(
        "O Atlas AI Assistant e um assistente operacional pessoal alimentado por Claude, "
        "projetado para centralizar fluxos de informacao diarios (email, calendario, noticias) "
        "em inteligencia acionavel, entregue via Telegram."
    )
    pdf.body_text(
        "O sistema opera sob o principio 'assistir primeiro, executar nunca sem aprovacao' - "
        "ele le, analisa, resume e propoe acoes, mas nunca executa operacoes sensiveis de forma autonoma."
    )

    pdf.subsection_title("Principios de Design")
    principles = [
        "Read-only por padrao - nenhuma operacao de escrita sem aprovacao humana",
        "Arquitetura local-first - dados e processamento rodam localmente",
        "Baixo custo operacional - SQLite, sem infraestrutura paga alem da API Claude",
        "Composicao modular - cada modulo e independente com interface definida",
        "Seguranca como restricao - politicas aplicadas na camada de orquestracao",
        "Design single-user - MVP para um usuario; multi-tenancy e expansao futura",
    ]
    for p in principles:
        pdf.bullet(p)
    pdf.ln(2)

    # ══════════════════════════════════════════════════════════════
    # 2. MODULOS IMPLEMENTADOS
    # ══════════════════════════════════════════════════════════════
    pdf.section_title("2. Modulos Implementados")

    # ── Inbox Copilot ──
    pdf.subsection_title("2.1 Inbox Copilot")
    pdf.body_text(
        "Modulo responsavel por ler, classificar e resumir emails via integracao Gmail. "
        "Fornece breakdown por prioridade e identifica itens de acao."
    )
    pdf.add_table(
        ["Metodo", "Descricao", "Output"],
        [
            ["get_recent_emails()", "Lista emails recentes", "list[dict]"],
            ["summarize_emails()", "Resume com prioridades", "dict com breakdown"],
            ["get_summary()", "Alias de compatibilidade", "dict"],
        ],
        [55, 80, 55],
    )
    pdf.body_text("Campos retornados: total, high_priority, medium_priority, low_priority, unread, action_items, summary.")

    # ── Calendar Copilot ──
    pdf.subsection_title("2.2 Calendar Copilot")
    pdf.body_text(
        "Gerencia agenda diaria, detecta horarios livres entre compromissos "
        "e prepara propostas de eventos para aprovacao."
    )
    pdf.add_table(
        ["Metodo", "Descricao", "Output"],
        [
            ["get_today_events()", "Agenda do dia", "dict com eventos"],
            ["find_free_slots(min)", "Calcula gaps livres", "list[dict] de slots"],
            ["propose_event(...)", "Prepara proposta", "dict com payload"],
        ],
        [55, 80, 55],
    )
    pdf.body_text(
        "O algoritmo de free slots analisa gaps entre eventos dentro do horario comercial "
        "(08:00-18:00), filtrando por duracao minima solicitada."
    )

    # ── News Briefing ──
    pdf.subsection_title("2.3 News Briefing")
    pdf.body_text(
        "Busca, normaliza e categoriza artigos de feeds RSS. "
        "Agrupa por categoria e gera resumo executivo."
    )
    pdf.add_table(
        ["Metodo", "Descricao", "Output"],
        [
            ["fetch_rss()", "Lista artigos brutos", "list[dict]"],
            ["normalize_articles()", "Schema uniforme", "list[dict]"],
            ["summarize_news()", "Agrupa por categoria", "dict com breakdown"],
        ],
        [55, 80, 55],
    )

    # ── Daily Briefing ──
    pdf.subsection_title("2.4 Daily Briefing")
    pdf.body_text(
        "Consolida todos os modulos (inbox + calendario + noticias + horarios livres) "
        "em um briefing executivo estruturado e o persiste no banco de dados."
    )
    pdf.body_text("Formato de saida:")
    pdf.code_block(
        "BRIEFING DIARIO\n"
        "==============================\n"
        "\n"
        "AGENDA - 3 compromisso(s)\n"
        "  - 09:00 | Call com equipe\n"
        "  - 12:00 | Almoco\n"
        "  - 15:00 | Revisao semanal\n"
        "\n"
        "HORARIOS LIVRES - 3 slot(s)\n"
        "  - 08:00-09:00 (60min)\n"
        "  - 10:00-12:00 (120min)\n"
        "  - 16:00-18:00 (120min)\n"
        "\n"
        "INBOX - 3 emails - 1 prioritario(s)\n"
        "  * cliente@empresa.com: Reuniao pendente\n"
        "\n"
        "NOTICIAS - 3 noticia(s) em 3 categoria(s)"
    )

    # ── Approval System ──
    pdf.subsection_title("2.5 Sistema de Aprovacao (Critico)")
    pdf.body_text(
        "Todas as operacoes de escrita (enviar email, criar evento) passam obrigatoriamente "
        "pelo fluxo de aprovacao. Cada transicao de estado e registrada no audit log."
    )
    pdf.body_text("Maquina de estados:")
    pdf.code_block(
        "pending --> approved --> (executed)\n"
        "pending --> rejected"
    )
    pdf.add_table(
        ["Operacao", "Requer Aprovacao"],
        [
            ["Ler emails", "Nao"],
            ["Criar draft de email", "Nao"],
            ["Enviar email", "SIM"],
            ["Ler calendario", "Nao"],
            ["Criar evento", "SIM"],
            ["Ler noticias", "Nao"],
            ["Gerar briefing", "Nao"],
        ],
        [100, 90],
    )
    pdf.body_text(
        "Protecao contra dupla resolucao: tentar aprovar/rejeitar uma acao ja processada "
        "levanta ActionAlreadyResolvedError."
    )

    # ══════════════════════════════════════════════════════════════
    # 3. ARQUITETURA
    # ══════════════════════════════════════════════════════════════
    pdf.add_page()
    pdf.section_title("3. Arquitetura do Sistema")

    pdf.subsection_title("3.1 Fluxo de Dados")
    pdf.code_block(
        "Usuario --> Telegram Bot --> FastAPI Backend --> Orchestrator\n"
        "                                                    |\n"
        "                           +------------------------+----------+\n"
        "                           |            |           |          |\n"
        "                      InboxService  CalendarSvc  NewsSvc  ApprovalSvc\n"
        "                           |            |           |          |\n"
        "                      GmailClient  CalendarCli  RSSClient  DB Repos\n"
        "                           |            |           |          |\n"
        "                      Google MCP   Google MCP   RSS Feeds   SQLite"
    )

    pdf.subsection_title("3.2 Camadas")
    layers = [
        ("API (app/api/)", "Fronteira HTTP - validacao, serializacao, injecao de dependencias"),
        ("Agent (app/agent/)", "Decisao IA - classificacao de intent, avaliacao de politicas"),
        ("Services (app/services/)", "Logica de negocio - um servico por dominio"),
        ("Integrations (app/integrations/)", "Adaptadores externos - Gmail, Calendar, RSS, Telegram"),
        ("DB (app/db/)", "Persistencia - modelos ORM, repositorios, sessao"),
        ("Core (app/core/)", "Infraestrutura - config, logging, seguranca, excecoes"),
    ]
    for label, desc in layers:
        pdf.bold_bullet(label, desc)
    pdf.ln(2)

    pdf.subsection_title("3.3 Estrutura de Arquivos")
    pdf.code_block(
        "app/\n"
        "  main.py                   # FastAPI factory + lifespan + error handler\n"
        "  api/\n"
        "    routes.py               # 14 endpoints REST + webhook Telegram\n"
        "    schemas.py              # Pydantic request/response models\n"
        "  agent/\n"
        "    orchestrator.py         # Roteamento central de intents\n"
        "    intent_classifier.py    # Classificacao rule-based (9 intents)\n"
        "    policies.py             # Motor de politicas de aprovacao\n"
        "  core/\n"
        "    config.py               # pydantic-settings (14 vars de ambiente)\n"
        "    exceptions.py           # Hierarquia de excecoes customizadas\n"
        "    logging.py              # Logging estruturado JSON\n"
        "    permissions.py          # Enum ActionType\n"
        "    security.py             # SecurityPolicy (read-only default)\n"
        "  db/\n"
        "    models.py               # 6 modelos ORM com FK + relationships\n"
        "    repositories.py         # 4 repositorios (User, Draft, Audit, Briefing)\n"
        "    session.py              # Engine + SessionLocal + get_db()\n"
        "  integrations/\n"
        "    gmail_client.py         # Adaptador Gmail (stub MCP-ready)\n"
        "    calendar_client.py      # Adaptador Calendar (stub MCP-ready)\n"
        "    rss_client.py           # Leitor RSS (stub)\n"
        "    telegram_bot.py         # Bot Telegram via httpx\n"
        "  services/\n"
        "    inbox_service.py        # Inbox Copilot\n"
        "    calendar_service.py     # Calendar Copilot\n"
        "    news_service.py         # News Briefing\n"
        "    briefing_service.py     # Daily Briefing\n"
        "    approval_service.py     # Sistema de Aprovacao\n"
        "  scheduler/\n"
        "    jobs.py                 # Job de briefing diario\n"
        "tests/\n"
        "  conftest.py               # Fixtures (in-memory DB, TestClient)\n"
        "  test_intent_classifier.py # 17 testes\n"
        "  test_orchestrator.py      # 11 testes\n"
        "  test_services.py          # 15 testes\n"
        "  test_approval.py          # 11 testes\n"
        "  test_health.py            # 1 teste"
    )

    # ══════════════════════════════════════════════════════════════
    # 4. ORQUESTRADOR + INTENT CLASSIFIER
    # ══════════════════════════════════════════════════════════════
    pdf.add_page()
    pdf.section_title("4. Orquestrador e Classificacao de Intent")

    pdf.subsection_title("4.1 Intents Suportados")
    pdf.add_table(
        ["Intent", "Trigger (comando)", "Trigger (palavras-chave)"],
        [
            ["GET_INBOX_SUMMARY", "/inbox, /email", "email, inbox, caixa, mensagens"],
            ["GET_CALENDAR", "/agenda, /calendar", "agenda, compromisso, reuniao"],
            ["CREATE_EVENT", "-", "criar evento, agendar, marcar"],
            ["GET_NEWS", "/news, /noticias", "noticia, news, manchete"],
            ["GET_DAILY_BRIEFING", "/briefing, /resumo", "briefing, resumo do dia"],
            ["APPROVE_ACTION", "/approve, /aprovar", "aprovar, confirmar + #ID"],
            ["REJECT_ACTION", "/reject, /rejeitar", "rejeitar, negar + #ID"],
            ["HELP", "/help, /start", "ajuda, help, comandos"],
            ["UNKNOWN", "-", "(fallback)"],
        ],
        [42, 52, 96],
    )

    pdf.subsection_title("4.2 Pipeline de Classificacao (3 Prioridades)")
    pdf.body_text("1. Comandos Telegram (/inbox, /approve 42) - confianca 1.0")
    pdf.body_text("2. Frases multi-palavra ('resumo do dia', 'criar evento') - confianca 0.9")
    pdf.body_text("3. Keywords individuais com scoring por contagem - confianca 0.5 a 0.85")
    pdf.ln(1)
    pdf.body_text(
        "A estrutura foi projetada para substituicao futura por Claude com tool_use - "
        "basta trocar o corpo de classify() mantendo o retorno ClassifiedIntent."
    )

    pdf.subsection_title("4.3 Interface do Orquestrador")
    pdf.code_block(
        "class Orchestrator:\n"
        "    def handle_request(self, user_id: str, message: str) -> dict:\n"
        '        # Retorna: {"intent", "confidence", "success", "data", "message"}\n'
        "\n"
        "# Fluxo interno:\n"
        "# 1. IntentClassifier.classify(message) -> ClassifiedIntent\n"
        "# 2. Dispatch para handler especifico (inbox, calendar, news...)\n"
        "# 3. Handler chama servico correspondente\n"
        "# 4. Retorno estruturado com dados + mensagem legivel"
    )

    # ══════════════════════════════════════════════════════════════
    # 5. API ENDPOINTS
    # ══════════════════════════════════════════════════════════════
    pdf.add_page()
    pdf.section_title("5. API Endpoints")

    pdf.add_table(
        ["Metodo", "Path", "Descricao"],
        [
            ["GET", "/health", "Health check"],
            ["POST", "/chat", "Entry point principal (orquestrador)"],
            ["GET", "/inbox/summary", "Resumo da inbox com prioridades"],
            ["GET", "/calendar/today", "Agenda do dia"],
            ["GET", "/calendar/free-slots", "Horarios livres (param: duration)"],
            ["POST", "/calendar/propose-event", "Propor evento (via aprovacao)"],
            ["POST", "/drafts/email", "Criar draft de email (via aprovacao)"],
            ["POST", "/approvals/{id}/approve", "Aprovar acao pendente"],
            ["POST", "/approvals/{id}/reject", "Rejeitar acao pendente"],
            ["GET", "/news", "Briefing de noticias"],
            ["GET", "/news/briefing", "Alias para /news"],
            ["GET", "/briefing", "Gerar briefing diario completo"],
            ["POST", "/jobs/run-daily-briefing", "Trigger do scheduler"],
            ["POST", "/telegram/webhook", "Webhook do Telegram Bot"],
        ],
        [18, 62, 110],
    )

    pdf.subsection_title("5.1 Exemplo: POST /chat")
    pdf.code_block(
        '// Request\n'
        '{"message": "mostra meus emails", "user_id": "default"}\n'
        '\n'
        '// Response\n'
        '{\n'
        '  "intent": "get_inbox_summary",\n'
        '  "confidence": 0.65,\n'
        '  "success": true,\n'
        '  "data": {"total": 3, "high_priority": 1, ...},\n'
        '  "message": "3 emails - 1 prioritario(s), 1 nao lido(s)."\n'
        '}'
    )

    pdf.subsection_title("5.2 Exemplo: Fluxo de Aprovacao")
    pdf.code_block(
        '// 1. Criar draft\n'
        'POST /drafts/email\n'
        '{"to": "cliente@emp.com", "subject": "Re: Reuniao", "body": "..."}\n'
        '--> {"id": 1, "status": "pending", "type": "draft_email"}\n'
        '\n'
        '// 2. Aprovar\n'
        'POST /approvals/1/approve\n'
        '--> {"id": 1, "status": "approved", "type": "draft_email"}\n'
        '\n'
        '// 3. Ou rejeitar\n'
        'POST /approvals/1/reject\n'
        '--> {"id": 1, "status": "rejected", "type": "draft_email"}'
    )

    # ══════════════════════════════════════════════════════════════
    # 6. MODELO DE DADOS
    # ══════════════════════════════════════════════════════════════
    pdf.add_page()
    pdf.section_title("6. Modelo de Dados")

    pdf.body_text("6 entidades com ForeignKeys e ORM relationships:")
    pdf.ln(1)

    pdf.add_table(
        ["Entidade", "Tabela", "Campos Principais", "Relacoes"],
        [
            ["User", "users", "id, name, telegram_id, created_at", "-> preferences, drafts, briefings"],
            ["UserPreference", "user_preferences", "user_id(FK), news_topics, briefing_time, tz", "-> user"],
            ["DraftAction", "draft_actions", "user_id(FK), type, payload, status, resolved_at", "-> user"],
            ["AuditLog", "audit_logs", "action_type, status, user_id, metadata_json", "-"],
            ["NewsSource", "news_sources", "url (unique), category", "-"],
            ["DailyBriefing", "daily_briefings", "user_id(FK), content, created_at", "-> user"],
        ],
        [32, 35, 78, 45],
    )

    pdf.subsection_title("6.1 Repositorios")
    pdf.add_table(
        ["Repositorio", "Metodos"],
        [
            ["UserRepository", "get(), get_by_telegram_id(), create(), get_or_create()"],
            ["DraftActionRepository", "create(), get(), update_status(), list_pending(), list_all()"],
            ["AuditLogRepository", "log(), list_recent()"],
            ["DailyBriefingRepository", "create(), get_latest()"],
        ],
        [55, 135],
    )

    # ══════════════════════════════════════════════════════════════
    # 7. SEGURANCA
    # ══════════════════════════════════════════════════════════════
    pdf.section_title("7. Modelo de Seguranca")

    pdf.subsection_title("7.1 Camadas de Protecao")
    security_layers = [
        ("Camada 1 - Telegram Auth", "TELEGRAM_ALLOWED_USER_ID restringe acesso a um usuario"),
        ("Camada 2 - Policy Engine", "SecurityPolicy define quais acoes precisam aprovacao"),
        ("Camada 3 - Approval Flow", "DraftAction lifecycle: pending -> approved/rejected"),
        ("Camada 4 - OAuth Scopes", "Escopos minimos do Google (read-only por padrao)"),
        ("Camada 5 - Audit Trail", "AuditLog imutavel de cada acao e decisao"),
    ]
    for label, desc in security_layers:
        pdf.bold_bullet(label, desc)
    pdf.ln(2)

    pdf.subsection_title("7.2 Mitigacao de Ameacas")
    pdf.add_table(
        ["Ameaca", "Mitigacao"],
        [
            ["Acesso nao autorizado", "Whitelist de Telegram user ID"],
            ["Prompt injection via email", "Conteudo de email tratado como dados nao confiaveis"],
            ["Vazamento de segredos", "Segredos em .env, nunca no codigo"],
            ["Execucao nao autorizada", "Policy engine + fluxo de aprovacao obrigatorio"],
            ["Tampering do audit log", "Padrao append-only, sem endpoints de delete"],
            ["SQL injection", "SQLAlchemy ORM com queries parametrizadas"],
        ],
        [50, 140],
    )

    # ══════════════════════════════════════════════════════════════
    # 8. INTEGRACOES
    # ══════════════════════════════════════════════════════════════
    pdf.add_page()
    pdf.section_title("8. Integracoes")

    pdf.body_text(
        "Todas as integracoes estao implementadas como stubs com interfaces claras, "
        "prontas para conexao com servicos reais. Nenhuma dependencia externa e necessaria no MVP."
    )

    pdf.add_table(
        ["Adaptador", "Arquivo", "Metodos", "Status"],
        [
            ["GmailClient", "gmail_client.py", "list_recent_emails, get_email, send_email", "Stub"],
            ["GoogleCalendarClient", "calendar_client.py", "get_today_events, get_events_range, create", "Stub"],
            ["RSSClient", "rss_client.py", "fetch_all, fetch_by_category", "Stub"],
            ["TelegramBot", "telegram_bot.py", "send_message, parse_update, callbacks", "Funcional"],
        ],
        [40, 38, 72, 40],
    )

    pdf.subsection_title("8.1 Telegram Bot")
    pdf.body_text("O bot Telegram esta completamente implementado com:")
    features = [
        "Envio de mensagens via Telegram Bot API (httpx)",
        "Parsing de updates (mensagens de texto e callback queries)",
        "Autorizacao por user ID",
        "Teclado inline para aprovacao/rejeicao de acoes",
        "Webhook endpoint em POST /telegram/webhook",
        "Traducao automatica de callback data para comandos do orquestrador",
    ]
    for f in features:
        pdf.bullet(f)
    pdf.ln(2)

    # ══════════════════════════════════════════════════════════════
    # 9. TESTES
    # ══════════════════════════════════════════════════════════════
    pdf.section_title("9. Cobertura de Testes")

    pdf.body_text("54 testes automatizados com 100% de taxa de sucesso:")

    pdf.add_table(
        ["Arquivo", "Qtd", "Escopo"],
        [
            ["test_intent_classifier.py", "17", "Keywords, frases, comandos, params, unknown"],
            ["test_orchestrator.py", "11", "Todos os intents, fluxo de aprovacao E2E"],
            ["test_services.py", "15", "Todos os metodos de servico + backward compat"],
            ["test_approval.py", "11", "CRUD, guard de dupla resolucao, queries"],
            ["test_health.py", "1", "Health check da API"],
        ],
        [55, 12, 123],
    )

    pdf.body_text(
        "Infraestrutura de testes: banco SQLite in-memory por teste (conftest.py), "
        "FastAPI TestClient com override de dependencias. Execucao em 0.27s."
    )

    # ══════════════════════════════════════════════════════════════
    # 10. TECH STACK
    # ══════════════════════════════════════════════════════════════
    pdf.section_title("10. Stack Tecnologica")

    pdf.add_table(
        ["Componente", "Tecnologia", "Versao"],
        [
            ["Linguagem", "Python", "3.14"],
            ["Framework HTTP", "FastAPI", "0.135+"],
            ["ORM", "SQLAlchemy", "2.0+"],
            ["Banco de dados", "SQLite", "-"],
            ["Validacao", "Pydantic", "2.12+"],
            ["Config", "pydantic-settings", "2.13+"],
            ["HTTP Client", "httpx", "0.28+"],
            ["Testes", "pytest", "9.0+"],
            ["Container", "Docker + Compose", "-"],
            ["Interface", "Telegram Bot API", "-"],
            ["IA", "Claude (Anthropic)", "claude-sonnet-4-5"],
        ],
        [50, 70, 70],
    )

    # ══════════════════════════════════════════════════════════════
    # 11. PROXIMOS PASSOS
    # ══════════════════════════════════════════════════════════════
    pdf.add_page()
    pdf.section_title("11. Proximos Passos")

    pdf.subsection_title("11.1 Imediato (Pos-MVP)")
    next_steps = [
        "Integrar Claude real no orquestrador (substituir keyword matching por tool_use)",
        "Conectar Google Workspace MCP real (Gmail + Calendar com OAuth)",
        "Implementar parser RSS real com feedparser",
        "Configurar webhook do Telegram em producao (ou polling mode)",
        "Adicionar APScheduler para briefing diario automatico",
    ]
    for s in next_steps:
        pdf.bullet(s)
    pdf.ln(2)

    pdf.subsection_title("11.2 Medio Prazo")
    medium = [
        "Memoria de conversacao (historico de chat por usuario)",
        "Execucao real de acoes apos aprovacao (enviar email, criar evento)",
        "Deteccao de conflitos de horario no calendario",
        "Ranking de noticias por relevancia usando Claude",
        "Briefings em linguagem natural (nao template)",
        "Migracao para PostgreSQL quando necessario",
        "Autenticacao JWT na API para clientes nao-Telegram",
    ]
    for s in medium:
        pdf.bullet(s)
    pdf.ln(2)

    pdf.subsection_title("11.3 Longo Prazo")
    long_term = [
        "Suporte multi-usuario com isolamento de dados",
        "Canal WhatsApp via Business API",
        "Interface de voz (mensagens de audio do Telegram)",
        "Integracao com task managers (Todoist, Linear, Notion)",
        "Assistente de arquivos (busca e resumo no Google Drive)",
        "Deploy cloud (Railway/Fly.io/AWS ECS)",
        "Observabilidade (Grafana + Sentry)",
        "Sistema de plugins para integracoes de terceiros",
    ]
    for s in long_term:
        pdf.bullet(s)

    # ══════════════════════════════════════════════════════════════
    # SAVE
    # ══════════════════════════════════════════════════════════════
    output_path = "Atlas_AI_Assistant_Report.pdf"
    pdf.output(output_path)
    return output_path


if __name__ == "__main__":
    path = build_report()
    print(f"Relatorio gerado: {path}")
