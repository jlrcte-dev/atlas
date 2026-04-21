# Módulo de Email — Evolução e Documentação Técnica

**Versão atual do classifier:** v4  
**Arquivos centrais:**
- `app/integrations/email_classifier.py` — classificação e scoring
- `app/modules/inbox/service.py` — orquestração, Top 5, resumo
- `app/integrations/telegram_bot.py` — formatação do Telegram
- `app/data/user_learning.json` — remetentes aprendidos

---

## A. Visão Geral

O módulo de email é responsável por classificar, priorizar e resumir o inbox do usuário como parte do briefing diário do Atlas.

**Problema central:** volume de email é ruído. A maior parte do inbox não exige ação. Um assistente útil precisa separar o que requer atenção do que é apenas informativo — de forma previsível, rápida e auditável.

**Abordagem adotada:** filtragem e priorização puramente determinísticas. Nenhuma chamada a LLM ou modelo externo é feita durante a classificação. O resultado é reproduzível: o mesmo email sempre produz o mesmo score, a mesma prioridade e as mesmas tags.

**Objetivo do Top 5:** entregar ao usuário no Telegram não apenas uma contagem de emails, mas uma triagem operacional real — os cinco itens que genuinamente exigem atenção, explicados de forma curta.

**Objetivo do resumo no Telegram:** transformar o bot de um contador de mensagens em um assistente de triagem. O usuário deve sentir controle e clareza, não volume.

---

## B. Evolução da Classificação

### Categorias

Todo email recebe uma categoria determinada por correspondência de sinais no texto `sender + subject + snippet` (normalizado para minúsculas):

| Categoria | Descrição | Precedência |
|---|---|---|
| `newsletter` | Conteúdo de lista — unsubscribe, boletim, informativo | 1ª (absoluta) |
| `noise` | Ruído promocional ou social — cupom, curtiu sua foto | 2ª (absoluta) |
| `action` | Requer ação explícita — verbos imperativos ou infinitivos | 3ª |
| `update` | Informativo — atualização, relatório, comprovante | 4ª (default) |

`newsletter` e `noise` são **short-circuits absolutos**: quando detectados, o email recebe imediatamente `score=0`, `priority=baixa`, todos os flags como `False`, e retorna sem passar pelo scoring. Nenhum sinal adicional (deadline, response, learned sender) altera esse resultado.

### Score Model

O score é calculado a partir de flags operacionais e heurísticas de remetente:

| Sinal | Peso | Fonte |
|---|---|---|
| `has_deadline` | +4 | prazo, urgente, vencimento, deadline, hoje, amanhã… |
| `requires_response` | +4 | aguardo, por favor, ?, poderia… |
| `is_opportunity` | +2 | proposta, parceria, orçamento… |
| `is_follow_up` | +2 | follow-up, lembrete, acompanhamento… |
| `human_sender` | +2 | remetente no formato "Nome \<email\>" |
| `learned_sender` | +2 | endereço listado em `user_learning.json` |
| `bulk_sender` | −3 | no-reply, noreply, mailer, notifications… |

**Thresholds de prioridade:**

| Score | Prioridade |
|---|---|
| ≥ 4 | `alta` |
| ≥ 0 | `media` |
| < 0 | `baixa` |

### Audit Tags

Cada classificação produz uma lista `audit_tags: list[str]` que torna o resultado auditável sem necessidade de inspecionar o score internamente.

| Tag | Quando é emitida |
|---|---|
| `HAS_DEADLINE` | Sinal de prazo ou urgência detectado |
| `ACTION_REQUIRED` | Sinal de resposta esperada detectado |
| `FINANCIAL_TOPIC` | Léxico financeiro ou PIX detectado |
| `FOLLOW_UP_PENDING` | Sinal de follow-up ou lembrete detectado |
| `OPPORTUNITY` | Sinal de proposta, parceria ou orçamento detectado |
| `IMPORTANT_SENDER_LEARNED` | Endereço do remetente está em `user_learning.json` |
| `IMPORTANT_SENDER` | Remetente está no formato "Nome \<email\>" (heurística) |
| `BULK_SENDER_PENALIZED` | Remetente é bulk-sender (no-reply, mailer…) |
| `NEWSLETTER_PENALIZED` | Categoria newsletter ou noise (short-circuit aplicado) |

Tags são produzidas pela função `_build_audit_tags()` em `email_classifier.py`. Para emails de categoria `newsletter` ou `noise`, o único tag produzido é `NEWSLETTER_PENALIZED`.

**Todas as tags são determinísticas.** Nenhuma é gerada por modelo de linguagem.

---

## C. Ranking e Top 5

`_build_top5()` em `inbox/service.py` seleciona os até 5 emails mais relevantes para o bloco executivo do Telegram.

### Hard Filters (aplicados antes do ranking)

Dois filtros eliminam emails antes da ordenação:

1. **Categoria newsletter ou noise** — excluídos incondicionalmente. São conteúdo de baixo valor operacional.
2. **Lidos sem sinal de ação** — um email `is_read=True` é excluído se não possuir nenhum dos seguintes flags: `requires_response`, `has_deadline`, `is_follow_up`, `is_opportunity`. Emails lidos com pelo menos um desses flags permanecem elegíveis.

### Ordenação

Os emails elegíveis são ordenados por:

1. **Prioridade** — `alta` (0) → `media` (1) → `baixa` (2)
2. **Score descendente** — maior score primeiro em caso de mesma prioridade
3. **Ordem original da lista** — sort estável preserva a ordem de chegada dos emails do provider (Gmail retorna mais recentes primeiro por padrão)

### Campos de cada item no Top 5

```python
{
    "id": str,
    "priority": "alta" | "media" | "baixa",
    "subject": str,
    "sender": str,
    "short_reason": str,
    "audit_tags": list[str],
}
```

O campo `short_reason` é gerado por `build_short_reason(audit_tags)` — ver seção D.

---

## D. Short Reason

`build_short_reason(audit_tags: list[str]) -> str` é uma função pública em `email_classifier.py` que traduz as audit_tags de um email em um motivo curto e legível para exibição no Telegram.

### Lógica

O mapeamento percorre uma tupla ordenada de `(tag, texto)` e retorna o texto do **primeiro par cuja tag esteja presente** nas audit_tags do email. Se nenhuma tag relevante for encontrada, retorna `"Email relevante"`.

### Tabela de Mapeamento

| Tag (primeira a vencer) | Short reason |
|---|---|
| `HAS_DEADLINE` | Prazo ou data identificada |
| `ACTION_REQUIRED` | Requer resposta/ação |
| `FINANCIAL_TOPIC` | Assunto financeiro/pagamento |
| `FOLLOW_UP_PENDING` | Follow-up pendente |
| `IMPORTANT_SENDER_LEARNED` | Remetente prioritário |
| `IMPORTANT_SENDER` | Remetente prioritário |
| `OPPORTUNITY` | Proposta/oportunidade |
| *(nenhuma das anteriores)* | Email relevante |

**O short_reason é estritamente determinístico.** Não há geração de texto, nenhum LLM é consultado. Dado o mesmo conjunto de audit_tags, o motivo produzido é sempre o mesmo.

---

## E. Sinais Financeiros e PIX

O conjunto `_FINANCIAL_SIGNALS` em `email_classifier.py` detecta conteúdo financeiro pelo léxico do texto do email (`sender + subject + snippet`).

### Sinais gerais

`pagamento`, `fatura`, `boleto`, `nota fiscal`, `cobrança`, `cobranca`, `débito`, `debito`, `transferência`, `transferencia`, `honorários`, `honorarios`, `contrato`, `vencimento da fatura`, `pagamento pendente`

### Sinais específicos de PIX

`pix enviado`, `pix recebido`, `comprovante pix`, `transferência pix`, `transferencia pix`, `pagamento pix`

### Comportamento

A detecção de qualquer sinal financeiro (incluindo PIX) produz a tag `FINANCIAL_TOPIC` nas `audit_tags` do email.

**A detecção financeira não altera o score.** Ela é exclusivamente para auditoria e para compor o `short_reason` no Telegram (`"Assunto financeiro/pagamento"`).

Emails de categoria `newsletter` ou `noise` que contenham sinais financeiros **não recebem** `FINANCIAL_TOPIC` — o short-circuit de categoria é absoluto e retorna antes da detecção de sinais.

---

## F. Aprendizado Incremental (Fase 1)

O sistema suporta uma forma simples de memória adaptativa: uma lista de remetentes considerados importantes pelo usuário. Essa lista é mantida em um arquivo JSON local editável.

### Arquivo

```
app/data/user_learning.json
```

### Formato esperado

```json
{
  "important_senders": [
    "joao@parceiro.com.br",
    "ana.silva@cliente.com"
  ]
}
```

Cada entrada deve ser um endereço de email completo (`local@dominio.tld`). Entradas em branco ou não-strings são ignoradas silenciosamente. Maiúsculas e minúsculas são normalizadas para lowercase na carga.

### Carregamento

O arquivo é lido pela função `_load_learned_senders()` decorada com `@lru_cache(maxsize=1)`. Isso significa:

- A leitura ocorre **uma única vez** por processo, na primeira classificação que precisar do dado
- **Mudanças no arquivo só são aplicadas após reinício do servidor**
- Se o arquivo não existir: retorna `frozenset()` silenciosamente, sem erro
- Se o JSON for inválido: emite `WARNING` no log e retorna `frozenset()`, sem interromper a classificação

### Matching

O endereço é extraído do campo `sender` do email antes da comparação:

- Formato `"Nome Completo <addr@dominio.com>"` → extrai `addr@dominio.com`
- Formato sem display name `"addr@dominio.com"` → usa o campo diretamente

A comparação é **exata** por endereço de email. Correspondências parciais por substring são intencionalmente evitadas para prevenir falsos-positivos (ex: `"joao@empresa.com"` não ativa `"naojoao@empresa.com"`).

### Efeito na Classificação

Quando o remetente é encontrado na lista:

| Efeito | Valor |
|---|---|
| Score | +2 (via `SCORE_WEIGHTS["learned_sender"]`) |
| Audit tag adicionada | `IMPORTANT_SENDER_LEARNED` |
| Score reason adicionada | `"learned_sender"` |

Um remetente learned que também está no formato `"Nome <email>"` recebe **ambos** os bônus: `+2` de `human_sender` e `+2` de `learned_sender` (total `+4` de contribuição de sender).

### Interação com Newsletter

O short-circuit de categoria é soberano. Um remetente listado em `user_learning.json` que enviar um email de newsletter **continua recebendo** `priority=baixa` e `audit_tags=["NEWSLETTER_PENALIZED"]`. O bônus de learned sender **não é aplicado** a emails de categoria newsletter ou noise.

---

## G. Limitações Atuais

| Limitação | Detalhe |
|---|---|
| Cache por processo | `_load_learned_senders()` usa `lru_cache`. Mudanças em `user_learning.json` requerem reinício do servidor para ter efeito |
| Sem hot reload | Não há endpoint ou mecanismo para forçar a recarga do JSON em runtime |
| Dependência de `is_read` do provider | O hard filter de "lido sem ação" depende do campo `is_read` retornado pelo cliente de email. Se o provider sempre retornar `is_read=False`, o filtro não atua |
| PIX dentro de FINANCIAL_TOPIC | Sinais PIX compartilham a tag `FINANCIAL_TOPIC` com outros sinais financeiros. Não há distinção entre "pix" e "fatura genérica" na camada de tag |
| Sem persistência avançada | A lista de learned senders é um arquivo plano. Não há histórico de interações, feedback do usuário ou aprendizado automático baseado em comportamento |
| Timestamp como tiebreaker implícito | O critério de desempate por recência usa a ordem estável do sort, que pressupõe que o provider retorna emails do mais recente para o mais antigo. Isso é verdade para o Gmail, mas pode variar em outros providers |

---

## H. Decisões de Design

### Por que não banco de dados para os learned senders?

Um arquivo JSON local é suficiente para o caso de uso de Fase 1: um único usuário, lista pequena, sem necessidade de histórico ou consultas complexas. Introduzir SQLite ou outro banco adicionaria infraestrutura sem benefício real nesta fase.

### Por que não LLM na classificação?

Três razões:

1. **Custo e latência**: classificar dezenas de emails por chamada de briefing via LLM seria lento e caro para uso diário
2. **Auditabilidade**: resultados determinísticos são previsíveis e debugáveis. O usuário pode entender e corrigir as regras; um modelo não oferece essa transparência
3. **Robustez**: a classificação funciona sem dependência de API externa. Uma falha na API da Anthropic não impede o briefing

### Por que abordagem determinística primeiro?

O princípio central: **reduzir ruído antes de adicionar inteligência**. Uma triagem que funciona de forma previsível e auditável entrega mais valor no dia a dia do que uma triagem "inteligente" que às vezes acerta e às vezes surpreende o usuário negativamente.

### Por que audit_tags em vez de apenas o score?

O score é um número — ele diz "quão importante" mas não "por que". As `audit_tags` tornam o raciocínio do sistema explícito e inspecionável. Isso também cria a estrutura de dados necessária para uma futura integração com LLM (ver seção I).

---

## I. Preparação para Integração com LLM (Futuro)

O sistema atual já produz sinais estruturados que permitem uma integração futura com LLM **sem redesign da arquitetura**.

### O que já existe

- `audit_tags`: lista de sinais interpretáveis por um modelo de linguagem
- `short_reason`: texto mapeado que pode ser substituído por geração contextual
- `score` e `score_reasons`: dados numéricos que podem enriquecer um prompt
- `category`, `priority`, flags booleanos: contexto estruturado para qualquer camada superior

### Como a integração seria adicionada

Uma camada LLM seria inserida **após** a classificação determinística, usando os sinais já computados para refinar ou enriquecer — não para substituir. As regras determinísticas continuariam soberanas para:

- Filtros absolutos (newsletter, noise)
- Score base e prioridade
- Hard filters do Top 5

O LLM atuaria como **camada complementar de refinamento**, nunca como substituto da lógica de triagem principal.

---

## J. Uso Operacional

### Como adicionar remetentes ao aprendizado

Edite o arquivo `app/data/user_learning.json` e adicione os endereços desejados:

```json
{
  "important_senders": [
    "chefe@empresa.com",
    "cliente.vip@parceiro.com.br",
    "joao.silva@fornecedor.com"
  ]
}
```

Salve o arquivo e **reinicie o servidor** (`uvicorn` ou o processo FastAPI). A nova lista será carregada na primeira classificação.

### Impacto esperado no Top 5

Um remetente adicionado ao `user_learning.json` recebe `+2` no score. Isso significa:

- Um email de atualização (`score=0` base) de um learned sender anônimo passa a ter `score=2` → permanece `media`
- Um email de atualização de um learned sender nomeado (`"Nome <email>"`) recebe `+2 (human_sender) + 2 (learned_sender) = +4` → sobe para `alta`
- Um email de follow-up (`score=2` base) de um learned sender anônimo passa a ter `score=4` → sobe para `alta`

Emails de categoria newsletter ou noise de learned senders **não são afetados** — o short-circuit de categoria é absoluto.

### Como verificar se um email foi afetado

Inspecione `audit_tags` na resposta do endpoint `GET /inbox/summary`. A presença de `IMPORTANT_SENDER_LEARNED` confirma que o remetente foi reconhecido via `user_learning.json`.

### Estrutura do resultado de `summarize_emails()`

```python
{
    "total": int,
    "high_priority": int,
    "medium_priority": int,
    "low_priority": int,
    "unread": int,
    "newsletter_count": int,
    "items": list[dict],        # todos os emails como dicts
    "action_items": list[dict], # emails com flags operacionais, por score desc
    "top5": list[dict],         # até 5 emails para o bloco executivo do Telegram
    "summary": str,             # texto resumido para exibição
}
```
