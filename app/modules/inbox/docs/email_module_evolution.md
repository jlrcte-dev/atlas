# Módulo de Email — Documentação Técnica

**Estado atual:** estabilizado pós-audit (após v6, v7, v7b e ajustes finais)

**Arquivos centrais:**

- `app/integrations/email_classifier.py` — classificação, scoring e sinais
- `app/modules/inbox/service.py` — orquestração, Top 5, action_items, resumo
- `app/integrations/telegram_bot.py` — formatação e envio para Telegram
- `app/modules/briefing/service.py` — briefing diário consolidado
- `app/data/user_learning.json` — remetentes aprendidos

---

## A. Visão Geral

O módulo de email é responsável por classificar, priorizar e resumir o inbox do usuário como parte do briefing diário do Atlas.

**Problema central:** volume de email é ruído. A maior parte do inbox não exige ação. Um assistente útil precisa separar o que requer atenção do que é apenas informativo — de forma previsível, rápida e auditável.

**Abordagem adotada:** filtragem e priorização puramente determinísticas. Nenhuma chamada a LLM ou modelo externo é feita durante a classificação. O resultado é reproduzível: o mesmo email sempre produz o mesmo score, a mesma prioridade e as mesmas tags.

**Objetivo do Top 5:** entregar ao usuário no Telegram não apenas uma contagem de emails, mas uma triagem operacional real — os cinco itens que genuinamente exigem atenção, explicados de forma curta. O Top 5 é a fonte primária do bloco de inbox no Telegram e no briefing diário.

**Objetivo do `action_items`:** lista separada com emails que exigem ação direta (resposta, aprovação, deadline), ordenada por score descendente. Exclui newsletters, ruído e conteúdo promocional detectado. Disponível via API e usada por consumidores que precisam de granularidade maior que o Top 5.

---

## B. Categorias

Todo email recebe uma categoria determinada por correspondência de sinais no texto `sender + subject + snippet` (normalizado para minúsculas):

| Categoria | Descrição | Precedência |
| --- | --- | --- |
| `newsletter` | Conteúdo de lista — unsubscribe, boletim, informativo, descadastrar | 1ª (absoluta) |
| `noise` | Ruído promocional ou social — cupom, oferta especial, curtiu sua foto, campanha | 2ª (absoluta) |
| `action` | Requer ação explícita — verbos imperativos ou infinitivos | 3ª |
| `update` | Informativo — atualização, relatório, comprovante | 4ª (default) |

`newsletter` e `noise` são **short-circuits absolutos**: quando detectados, o email recebe imediatamente `score=0`, `priority=baixa`, todos os flags como `False`, e `audit_tags=["NEWSLETTER_PENALIZED"]`. Nenhum sinal adicional — deadline, requires_response, learned sender, sinais financeiros, PROMOTIONAL_NOISE — altera esse resultado.

---

## C. Score Model

O score é calculado a partir de flags operacionais e heurísticas de remetente:

| Sinal | Peso | Fonte |
| --- | --- | --- |
| `has_deadline` | +4 | prazo, urgente, vencimento, deadline, hoje, amanhã… |
| `requires_response` | +4 | aguardo, por favor, ?, poderia, você pode… |
| `transactional` | +4 | PIX, transferência, nota de corretagem, nota de negociação… |
| `is_opportunity` | +2 | proposta, parceria, orçamento, reunião comercial… |
| `is_follow_up` | +2 | follow-up, lembrete, acompanhamento, conforme conversamos… |
| `human_sender` | +2 | remetente no formato `"Nome <email>"` |
| `learned_sender` | +2 | endereço listado em `user_learning.json` |
| `project` | +1 | lgpd, nova data, lei geral de proteção de dados |
| `bulk_sender` | −3 | no-reply, noreply, mailer, promomail, emkt., mkt.… |
| `promotional_noise` | −4 | conteúdo promocional detectado (ver seção G) |

**Thresholds de prioridade:**

| Score | Prioridade |
|---|---|
| ≥ 4 | `alta` |
| ≥ 0 | `media` |
| < 0 | `baixa` |

---

## D. Audit Tags

Cada classificação produz uma lista `audit_tags: list[str]` que torna o resultado auditável sem necessidade de inspecionar o score internamente. A lista é construída pela função `_build_audit_tags()`.

| Tag | Quando é emitida |
|---|---|
| `HAS_DEADLINE` | Sinal de prazo ou urgência detectado |
| `ACTION_REQUIRED` | Sinal de resposta esperada detectado (após gate de supressão) |
| `FINANCIAL_TRANSACTION` | Transação financeira confirmada (PIX realizado, nota de corretagem…) |
| `FINANCIAL_TOPIC` | Léxico financeiro ou PIX detectado (auditoria — sem impacto no score) |
| `FOLLOW_UP_PENDING` | Sinal de follow-up ou lembrete detectado |
| `OPPORTUNITY` | Sinal de proposta, parceria, reunião comercial ou orçamento detectado |
| `PROJECT_SIGNAL` | Sinal de projeto interno (LGPD, nova data) detectado |
| `IMPORTANT_SENDER_LEARNED` | Endereço do remetente está em `user_learning.json` |
| `IMPORTANT_SENDER` | Remetente está no formato `"Nome <email>"` (heurística) |
| `BULK_SENDER_PENALIZED` | Remetente é bulk-sender (no-reply, mailer, promomail…) |
| `NEWSLETTER_PENALIZED` | Categoria newsletter ou noise (short-circuit — único tag produzido) |
| `PROMOTIONAL_NOISE` | Conteúdo promocional/marketing detectado fora de contexto financeiro |

**Todas as tags são determinísticas.** Nenhuma é gerada por modelo de linguagem.

Para emails de categoria `newsletter` ou `noise`, o único tag produzido é `NEWSLETTER_PENALIZED`.

---

## E. Short Reason

`build_short_reason(audit_tags: list[str]) -> str` é uma função pública em `email_classifier.py` que traduz as audit_tags de um email em um motivo curto e legível para exibição no Telegram.

A lógica percorre uma tupla ordenada de `(tag, texto)` e retorna o texto do **primeiro par cuja tag esteja presente**. Se nenhuma tag relevante for encontrada, retorna `"Email relevante"`.

| Tag (primeira a vencer) | Short reason |
|---|---|
| `HAS_DEADLINE` | Prazo ou data identificada |
| `ACTION_REQUIRED` | Requer resposta/ação |
| `FINANCIAL_TRANSACTION` | Transação financeira |
| `FINANCIAL_TOPIC` | Assunto financeiro/pagamento |
| `FOLLOW_UP_PENDING` | Follow-up pendente |
| `IMPORTANT_SENDER_LEARNED` | Remetente prioritário |
| `IMPORTANT_SENDER` | Remetente prioritário |
| `OPPORTUNITY` | Proposta/oportunidade |
| `PROJECT_SIGNAL` | Projeto interno |
| `PROMOTIONAL_NOISE` | Conteúdo promocional |
| *(nenhuma das anteriores)* | Email relevante |

`FINANCIAL_TRANSACTION` precede `FINANCIAL_TOPIC` na ordem de prioridade: um email da Clear com nota de negociação exibe `"Transação financeira"`, não o genérico `"Assunto financeiro/pagamento"`.

---

## F. Sinais Financeiros e Transacionais

O módulo distingue dois níveis de sinal financeiro com efeitos diferentes.

### F.1 Sinais transacionais (`_TRANSACTIONAL_SIGNALS`) — score +4

Confirmam uma **transação financeira concluída ou em andamento**. Produzem:
- Score `+4` via `SCORE_WEIGHTS["transactional"]`
- Tag `FINANCIAL_TRANSACTION` nas audit_tags
- Tag `FINANCIAL_TOPIC` (sempre, pois `is_transactional → is_financial`)
- Pass-through no Top 5 para emails lidos (ver seção H)

**Sinais incluídos:**

| Sinal | Exemplo |
|---|---|
| `pix realizado` / `pix enviado` / `pix recebido` | "Pix realizado com sucesso — R$ 500,00" |
| `comprovante pix` | "Comprovante pix — transferência realizada" |
| `transferência recebida` / `transferencia recebida` | "Transferência recebida de João Lima" |
| `transferência enviada` / `transferencia enviada` | "Transferência enviada com sucesso" |
| `nota de corretagem` | "Nota de corretagem — operações de abril" |
| `nota de negociação` / `nota de negociacao` | "Clear Corretora \| Nota de Negociação" |
| `corretora` | "Aviso da sua corretora — liquidação da ordem" |
| `liquidação` / `liquidacao` | "Liquidação financeira disponível" |
| `custódia` / `custodia` | "Relatório de custódia B3" |

### F.2 Sinais financeiros de tópico (`_FINANCIAL_SIGNALS`) — auditoria apenas

Detectam léxico financeiro amplo. Produzem apenas a tag `FINANCIAL_TOPIC` — **sem impacto no score**.

**Sinais adicionais (além dos transacionais):**

`pagamento`, `fatura`, `boleto`, `nota fiscal`, `cobrança`, `cobranca`, `débito`, `debito`, `transferência`, `transferencia`, `honorários`, `honorarios`, `contrato`, `vencimento da fatura`, `pagamento pendente`, `transferência pix`, `transferencia pix`, `pagamento pix`, `negociação`, `negociacao`, `extrato`, `b3`

> **Importante:** `_TRANSACTIONAL_SIGNALS` é um subconjunto estrito de `_FINANCIAL_SIGNALS`. Todo sinal transacional também é um sinal financeiro. Isso é verificado automaticamente pelo teste `test_transactional_signals_subset_of_financial_signals`.

### F.3 Financial Guard

O **financial guard** protege emails com conteúdo financeiro da penalidade de ruído promocional:

```python
is_promo = any(sig in text for sig in _PROMO_CONTENT_SIGNALS) and not is_financial
```

Se `is_financial=True` (qualquer sinal transacional ou de tópico financeiro), `is_promo` é forçado para `False`, independentemente dos sinais de conteúdo promocional detectados. Isso garante que emails de boleto, fatura, PIX ou nota de negociação enviados por remetentes de domínio marketing (`emkt.`, `mkt.`, `noreply`) não sejam penalizados como promocionais.

---

## G. Detecção de PROMOTIONAL_NOISE

Emails com conteúdo promocional ou de marketing que não se enquadram em newsletter/noise (e portanto não são eliminados pelo short-circuit) podem conter sinais que inflam artificialmente o score — em especial `requires_response` disparado por frases como "você pode". O sistema detecta esse padrão e aplica penalidades específicas.

### G.1 Sinais de remetente (`_BULK_SENDER_SIGNALS`)

Penalizam o remetente via `bulk_sender` (−3):

| Sinal | Exemplo |
|---|---|
| `no-reply`, `noreply`, `donotreply`, `do-not-reply` | `noreply@sistema.com.br` |
| `mailer`, `notifications`, `bounce` | `mailer@empresa.com` |
| `promomail` | `azure@promomail.microsoft.com` |
| `emkt.` | `movida@emkt.movida.com.br` |
| `mkt.` | `alguem@mkt.empresa.com.br` |

> Os sinais `promomail`, `emkt.`, `mkt.` aparecem também em `_PROMO_CONTENT_SIGNALS` — intencionalmente. `_BULK_SENDER_SIGNALS` aplica a penalidade de remetente via `_sender_score()`; `_PROMO_CONTENT_SIGNALS` aplica a penalidade de ruído promocional via `is_promo`. As duas penalidades são cumulativas e corretas para remetentes de subdomínio marketing confirmado.

### G.2 Sinais de conteúdo (`_PROMO_CONTENT_SIGNALS`)

Detectam padrões de conteúdo promocional no texto completo (`sender + subject + snippet`). Ativam `is_promo=True` (sujeito ao financial guard):

| Categoria | Sinais |
|---|---|
| Subdomínio marketing | `promomail`, `emkt.`, `mkt.` |
| Headers de renderização | `visualizar este e-mail`, `visualizar como página`, `visualizar no navegador` |
| Opt-out | `para não receber mais`, `não deseja mais receber`, `nao deseja mais receber` |
| Marketing de evento | `webinar`, `evento gratuito`, `ao vivo` |
| Digest numerado | `resumo #` (ex: "Resumo #275") |
| Sazonalidade/viagem | `próximo feriado`, `proximo feriado`, `roteiro para`, `já tem roteiro`, `ja tem roteiro` |
| Motivacional/inspiracional | `até onde a dedicação`, `ate onde a dedicacao`, `quem se compromete` |
| FOMO/urgência marketing | `últimos dias`, `ultimos dias`, `imperdível`, `imperdivel` |

### G.3 Efeito no score e no ranking

Quando `is_promo=True`:

| Efeito | Valor |
|---|---|
| Score | −4 via `SCORE_WEIGHTS["promotional_noise"]` |
| Tag adicionada | `PROMOTIONAL_NOISE` |
| Score reason | `"promotional_noise"` |

Combinado com a penalidade de `bulk_sender` (−3), um email de subdomínio marketing confirmado como `emkt.movida.com.br` recebe:
- `human_sender` +2 (display name presente)
- `bulk_sender` −3
- `promotional_noise` −4
- **Score total: −5 → `baixa`**

### G.4 Exclusão de `action_items`

`action_items` em `InboxService.summarize_emails()` aplica um filtro explícito:

```python
"PROMOTIONAL_NOISE" not in classifications[e.id].audit_tags
```

Emails com `PROMOTIONAL_NOISE` são excluídos de `action_items` mesmo que possuam flags `requires_response`, `has_deadline` ou similares.

---

## H. Ranking e Top 5

`_build_top5()` em `inbox/service.py` seleciona os até 5 emails mais relevantes para o bloco executivo do Telegram e para o briefing diário.

### H.1 Hard Filters (aplicados antes do ranking)

| Filtro | Condição de exclusão |
|---|---|
| Newsletter/noise | `clf.category in ("newsletter", "noise")` |
| Lido sem ação operacional | `email.is_read=True` AND todos os flags False AND sem `FINANCIAL_TRANSACTION` |

O segundo filtro tem uma **exceção crítica**: emails lidos com tag `FINANCIAL_TRANSACTION` **não são excluídos**. Isso garante que emails de PIX, transferência ou nota de negociação já lidos permaneçam visíveis no Top 5 — transações financeiras são relevantes independentemente do status de leitura.

> **Distinção importante:** `FINANCIAL_TRANSACTION` dá pass-through. `FINANCIAL_TOPIC` genérico (boleto, fatura, extrato) **não dá**. Um email informativo de fatura já lido, sem flags operacionais, é excluído normalmente.

### H.2 Ordenação

Os emails elegíveis são ordenados por:

1. **Prioridade** — `alta` (0) → `media` (1) → `baixa` (2)
2. **Score descendente** — maior score primeiro em caso de mesma prioridade
3. **Ordem original da lista** — sort estável preserva a ordem de chegada (Gmail retorna mais recentes primeiro)

### H.3 Campos de cada item no Top 5

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

### H.4 Top 5 vs `action_items`

| | Top 5 | `action_items` |
| --- | --- | --- |
| **Propósito** | Triagem executiva para Telegram/briefing | Lista de emails com ação direta pendente |
| **Limite** | 5 itens | Sem limite |
| **Ordenação** | Prioridade + score | Score descendente |
| **Exclui newsletter/noise** | Sim | Sim |
| **Exclui PROMOTIONAL_NOISE** | Não (via ranking — o email pode aparecer mas em posição inferior) | Sim (explícito via tag check) |
| **Pass-through FINANCIAL_TRANSACTION lido** | Sim | N/A (filtro de read não se aplica a action_items) |
| **Campos expostos** | id, priority, subject, sender, short_reason, audit_tags | Todos os campos do email como dict |

---

## I. Gate de `requires_response`

O sinal `requires_response` é gerado pelo conjunto `_RESPONSE_SIGNALS`: `?`, `aguardo`, `por favor`, `poderia`, `você pode`, `voce pode`, etc.

### I.1 Problema sem o gate

Remetentes automáticos (no-reply, marketing) frequentemente usam frases como "você pode implantar", "você pode aproveitar", "poderia se beneficiar". Essas frases disparam `requires_response=True` e `+4` de score, fazendo emails promocionais atingirem prioridade `alta` indevidamente.

### I.2 Condição de supressão

```python
is_automated_sender = any(sig in email.sender.lower() for sig in _BULK_SENDER_SIGNALS)
if requires_response and (is_automated_sender or is_promo) and not is_financial:
    requires_response = False
    reason_codes = [c for c in reason_codes if c != "requires_response"]
```

O gate suprime `requires_response` quando **todas** as condições são verdadeiras:
1. `requires_response` foi inicialmente detectado
2. O remetente é automatizado (`is_automated_sender=True`) **OU** conteúdo é promocional (`is_promo=True`)
3. **Não há conteúdo financeiro** (`is_financial=False`)

### I.3 Exceções preservadas

| Caso | Comportamento |
|---|---|
| Remetente humano (`"Nome <email>"`) sem promo | `requires_response` preservado |
| Remetente noreply + conteúdo financeiro (fatura, PIX) | `requires_response` preservado |
| Remetente promomail + conteúdo financeiro (boleto emkt.) | `requires_response` preservado |
| Remetente humano com conteúdo promo (motivacional) | `requires_response` suprimido (is_promo gate) |

O gate é aplicado **antes** do scoring, de modo que o score nunca conta um `requires_response` que foi suprimido.

---

## J. Sinais de Projeto Interno

O conjunto `_PROJECT_SIGNALS` detecta emails relacionados a projetos internos com impacto operacional moderado.

**Sinais incluídos:** `lgpd`, `lei geral de proteção de dados`, `lei geral de protecao de dados`, `nova data`

**Efeito:** score `+1` via `SCORE_WEIGHTS["project"]` e tag `PROJECT_SIGNAL`.

O peso +1 é intencionalmente conservador — suficiente para diferenciar um email de projeto de um email neutro, sem inflar artificialmente a prioridade.

---

## K. Aprendizado Incremental

O sistema suporta uma lista de remetentes considerados importantes pelo usuário, mantida em arquivo JSON local.

### Arquivo e formato

```
app/data/user_learning.json
```

```json
{
  "important_senders": [
    "joao@parceiro.com.br",
    "ana.silva@cliente.com"
  ]
}
```

Entradas em branco ou não-strings são ignoradas silenciosamente. Maiúsculas e minúsculas são normalizadas para lowercase na carga.

### Carregamento

`_load_learned_senders()` usa `@lru_cache(maxsize=1)`:

- Lida **uma única vez** por processo
- **Mudanças no arquivo requerem reinício do servidor**
- Arquivo ausente: retorna `frozenset()` sem erro
- JSON inválido: emite `WARNING` no log e retorna `frozenset()`

### Matching

- Formato `"Nome <addr@dominio.com>"` → extrai `addr@dominio.com`
- Formato `"addr@dominio.com"` → usa diretamente
- Comparação **exata**: `"joao@empresa.com"` não ativa `"naojoao@empresa.com"`

### Efeito na classificação

| Efeito | Valor |
|---|---|
| Score | +2 (`SCORE_WEIGHTS["learned_sender"]`) |
| Tag adicionada | `IMPORTANT_SENDER_LEARNED` |

Um remetente learned no formato `"Nome <email>"` recebe **ambos** os bônus: `+2 (human_sender) + 2 (learned_sender) = +4` de contribuição de sender.

O short-circuit de categoria é soberano — learned senders que enviam newsletters continuam recebendo `priority=baixa`.

---

## L. Casos Reais Resolvidos

Esta seção documenta casos reais que motivaram ajustes no módulo, com o comportamento esperado após cada correção.

### L.1 XP — PIX e Transferência

**Problema:** Emails de PIX e transferência recebida da XP (`noreply@xp.com.br`) não apareciam no Top 5 quando já lidos.

**Causa:** O hard filter de "lido sem ação" excluía emails com `is_read=True` sem flags operacionais. PIX não gerava flags de ação, apenas `FINANCIAL_TOPIC`.

**Correção (v5):** Adição de `_TRANSACTIONAL_SIGNALS` com score +4 e tag `FINANCIAL_TRANSACTION`. Hard filter do Top 5 atualizado para preservar emails com `FINANCIAL_TRANSACTION`, mesmo lidos.

**Comportamento atual:**
- `noreply@xp.com.br` com "Pix recebido" → `bulk_sender(−3) + transactional(+4) = +1` → `media`
- Aparece no Top 5 mesmo lido (FINANCIAL_TRANSACTION pass)
- `short_reason = "Transação financeira"`

### L.2 Clear — Nota de Negociação

**Problema:** Email da Clear Corretora com nota de negociação não era coletado.

**Causa:** `max_results=10` era insuficiente — o email ficava fora da janela de coleta.

**Correção (v6):** `max_results` aumentado de 10 para 20 em `summarize_emails()`.

**Comportamento atual:**
- `"Clear Corretora <noreply@clear.com.br>"` com "Nota de Negociação" → `transactional(+4) + human_sender(+2) + bulk_sender(−3) = +3` → `media`
- Aparece no Top 5 (lido ou não lido, via FINANCIAL_TRANSACTION pass)
- `short_reason = "Transação financeira"`

### L.3 Azure — Promomail

**Problema:** Email do Azure (`azure@promomail.microsoft.com`) com "Com que rapidez você pode implantar?" aparecia no Top 5 com `requires_response=True` e prioridade `alta`.

**Causa:** "você pode" disparava `requires_response=True` (+4); remetente `promomail` disparava `bulk_sender` (−3); score resultante era +1 → `media`, mas aparecia no Top 5 sem filtro de promo.

**Correção (v7):**
1. `promomail` adicionado a `_BULK_SENDER_SIGNALS` e `_PROMO_CONTENT_SIGNALS`
2. Gate de `requires_response` suprime o flag para remetentes automáticos sem contexto financeiro
3. `PROMOTIONAL_NOISE` excluído de `action_items`

**Comportamento atual:**
- Score: `bulk_sender(−3) + promotional_noise(−4) = −7` → `baixa`
- `requires_response=False` (suprimido pelo gate)
- Tags: `BULK_SENDER_PENALIZED`, `PROMOTIONAL_NOISE`
- Não aparece em `action_items`

### L.4 Buildings — Digest / Newsletter

**Problema:** Email do Buildings com "Resumo #275: Baixa disponibilidade de galpões…" aparecia no Top 5 e em `action_items`.

**Caso 1 (snippet com unsubscribe):** Capturado pelo short-circuit de newsletter → `priority=baixa`, tags `["NEWSLETTER_PENALIZED"]`, excluído do Top 5 e de `action_items`.

**Caso 2 (sem unsubscribe no snippet visível):**

**Correção (v7):** `"resumo #"` adicionado a `_PROMO_CONTENT_SIGNALS`. Email recebe `PROMOTIONAL_NOISE`, score penalizado, excluído de `action_items`.

### L.5 Nelogica — Email Motivacional

**Problema:** Email de Lucas Fortes (`lucas.fortes@mail.nelogica.com.br`) com assunto "Até onde a dedicação pode te levar?" aparecia no Top 5 com `requires_response=True` (via "?") e `human_sender(+2)` → prioridade `alta`.

**Causa:** Remetente em formato `"Nome <email>"` → `human_sender=True`. "?" no assunto → `requires_response=True`. Score: `+2 + 4 = 6` → `alta`.

**Correção (v7b):** Frase `"até onde a dedicação"` adicionada a `_PROMO_CONTENT_SIGNALS`. Gate de `requires_response` estendido para suprimir quando `is_promo=True` (não apenas `is_automated_sender`).

**Comportamento atual:**
- `is_promo=True` (via "até onde a dedicação")
- `requires_response=False` (suprimido pelo gate is_promo)
- Score: `human_sender(+2) + promotional_noise(−4) = −2` → `baixa`
- Tags: `IMPORTANT_SENDER`, `PROMOTIONAL_NOISE`

### L.6 Movida — Subdomínio emkt.

**Problema:** Email da Movida (`movida@emkt.movida.com.br`) com "Já tem roteiro para o próximo feriado?" aparecia no Top 5.

**Causa:** Remetente em formato `"Nome <email>"` → `human_sender=True`. Sem sinal de bulk_sender reconhecido. Score: `+2` → `media`, aparecia no Top 5.

**Correção (v7b):**
1. `"emkt."` adicionado a `_BULK_SENDER_SIGNALS` (penalidade de remetente)
2. `"emkt."`, `"mkt."` adicionados a `_PROMO_CONTENT_SIGNALS` (penalidade de conteúdo)
3. `"próximo feriado"`, `"roteiro para"`, `"já tem roteiro"` adicionados a `_PROMO_CONTENT_SIGNALS`

**Comportamento atual:**
- Score: `human_sender(+2) + bulk_sender(−3) + promotional_noise(−4) = −5` → `baixa`
- Tags: `BULK_SENDER_PENALIZED`, `PROMOTIONAL_NOISE`

### L.7 LGPD — Projeto Interno

**Problema:** Emails sobre projeto LGPD tinham o mesmo peso que atualizações genéricas.

**Correção (v5/v7b):** `"lgpd"` adicionado a `_PROJECT_SIGNALS` com peso +1.

**Comportamento atual:**
- Email com "lgpd" de remetente humano: `human_sender(+2) + project(+1) = +3` → `media`
- Tag: `PROJECT_SIGNAL`, short_reason: `"Projeto interno"`
- Não é afetado pela detecção de ruído promocional (nenhum sinal promo normalmente presente)

---

## M. Ajustes Pós-Audit

Os ajustes a seguir foram aplicados após revisão técnica completa do módulo estabilizado.

### M.1 Remoção de "reunião" de `_OPPORTUNITY_SIGNALS`

**Problema:** As entradas `"reunião"` e `"reuniao"` em `_OPPORTUNITY_SIGNALS` causavam double-counting com `is_follow_up`. Um email de lembrete comum como "Lembrando sobre a reunião de amanhã" pontuava: `follow_up(+2) + opportunity(+2) + deadline(+4) = +8 → alta`, tratando um lembrete rotineiro como oportunidade comercial.

**Correção:** Entradas `"reunião"` e `"reuniao"` removidas de `_OPPORTUNITY_SIGNALS`.

**Preservado:** As entradas compostas `"reunião comercial"`, `"reuniao comercial"`, `"apresentação comercial"`, `"apresentacao comercial"` permanecem — capturam oportunidades comerciais reais sem falsos positivos.

**Antes/depois para "Lembrando sobre a reunião de amanhã":**

| | Antes | Depois |
| --- | --- | --- |
| `is_opportunity` | `True` | `False` |
| Score | follow_up(2) + deadline(4) + opportunity(2) = 8 | follow_up(2) + deadline(4) = 6 |
| Prioridade | `alta` | `alta` (score ainda ≥ 4) |

O impacto no ranking é moderado — emails de follow-up com deadline continuam em `alta`, mas não ganham o +2 indevido de opportunity.

### M.2 Teste de integridade de sinais

Adicionado `test_transactional_signals_subset_of_financial_signals` em `tests/test_email_classifier.py`.

O teste valida que `_TRANSACTIONAL_SIGNALS ⊆ _FINANCIAL_SIGNALS` em tempo de execução. Isso previne drift futuro: se um novo sinal transacional for adicionado sem ser incluído em `_FINANCIAL_SIGNALS`, o financial guard não protegeria esse sinal e emails de transação poderiam ser penalizados como promocionais.

### M.3 Atualização de documentação inline

- Docstring do módulo: label de versão removido para evitar defasagem futura
- Comentário da classe `EmailClassification`: atualizado para listar todas as 12 tags atuais
- Numeração de passos em `classify_email()`: duplicação de "Step 3" corrigida (pipeline renumerado de 1 a 7)
- `_PROMO_CONTENT_SIGNALS`: comentário adicionado explicando a duplicação intencional de sinais de domínio com `_BULK_SENDER_SIGNALS`

---

## N. Limitações Conhecidas

| Limitação | Detalhe |
|---|---|
| Cache por processo | `_load_learned_senders()` usa `lru_cache`. Mudanças em `user_learning.json` requerem reinício do servidor |
| "ao vivo" pode produzir falso positivo | Eventos internos transmitidos ao vivo ("CEO ao vivo respondendo dúvidas") podem disparar `is_promo=True` se não houver sinal financeiro. O financial guard não protege esse caso. Nenhuma evidência real observada — documentado para avaliação futura |
| `max_results=20` pode não capturar inbox denso | Em períodos de alto volume, emails relevantes além da posição 20 não são coletados. Aumentar `max_results` tem custo de API |
| `is_read` depende do provider | O hard filter de "lido sem ação" depende do campo `is_read` retornado pelo cliente. Se o provider sempre retornar `is_read=False`, o filtro não atua |
| Sem hot reload de learned senders | Não há endpoint para forçar recarga do `user_learning.json` em runtime |
| Sender com múltiplos `<>` | Formato malformado `"Foo <alias> <real@domain.com>"` pode extrair o alias em vez do endereço real em `_is_learned_sender` |
| `EmailMessage` assume campos não-None | `classify_email()` faz f-string com sender/subject/snippet sem guard de None. Se o provider retornar None em algum campo, a classificação falha com TypeError (capturado pelo try/except de `_classify_all` como fallback silencioso) |

---

## O. Decisões de Design

### Por que não LLM na classificação?

1. **Custo e latência:** classificar dezenas de emails por chamada de briefing via LLM seria lento e caro para uso diário
2. **Auditabilidade:** resultados determinísticos são previsíveis e debugáveis via `audit_tags`
3. **Robustez:** a classificação funciona sem dependência de API externa

### Por que financial guard e não exclusão de domínio?

Excluir domínios de marketing inteiramente causaria falsos negativos para bancos e corretoras que enviam transações via subdomínios `noreply.*` ou endereços automatizados. O financial guard preserva a relevância do conteúdo sem depender da reputação do domínio do remetente.

### Por que `action_items` exclui PROMOTIONAL_NOISE explicitamente?

Emails promocionais que escapam do short-circuit de newsletter/noise mas são penalizados como promo ainda possuem score calculado. Se esse score resultar em `media` ou `alta` (ex: email com `has_deadline` + `promotional_noise` resultando em score 0), o email poderia aparecer em `action_items`. O filtro explícito por tag evita esse caso.

### Por que audit_tags em vez de apenas o score?

O score é um número — diz "quão importante" mas não "por quê". As `audit_tags` tornam o raciocínio explícito e inspecionável via API, Telegram e logs. São também a estrutura de dados necessária para uma eventual integração com LLM como camada de refinamento posterior.

---

## P. Uso Operacional

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
    "action_items": list[dict], # emails operacionais, ordenados por score desc
    "top5": list[dict],         # até 5 emails para Telegram/briefing
    "summary": str,             # texto resumido
}
```

### Como adicionar remetentes ao aprendizado

Edite `app/data/user_learning.json`, adicione endereços e **reinicie o servidor**:

```json
{
  "important_senders": [
    "chefe@empresa.com",
    "cliente.vip@parceiro.com.br"
  ]
}
```

**Impacto esperado:**

| Situação | Score base | Score com learned | Resultado |
| --- | --- | --- | --- |
| Email neutro, remetente anônimo | 0 | +2 | `media` |
| Email neutro, remetente com nome | +2 | +4 | `alta` |
| Email de follow-up, remetente anônimo | +2 | +4 | `alta` |

### Como verificar por que um email foi ou não incluído no Top 5

Inspecione `audit_tags` na resposta de `GET /inbox/summary` (campo `items`):

| Tags presentes | Interpretação |
|---|---|
| `["NEWSLETTER_PENALIZED"]` | Short-circuit de newsletter/noise — excluído do Top 5 |
| `["PROMOTIONAL_NOISE", ...]` | Detectado como marketing — excluído de action_items, pode estar no Top 5 em posição inferior |
| `["FINANCIAL_TRANSACTION", ...]` | Transação confirmada — pass-through mesmo se lido |
| `[]` | Nenhum sinal relevante — excluído do Top 5 se lido |
