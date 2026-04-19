# Módulo Inbox / Email — Atlas AI Assistant

> Documentação técnica oficial. Ciclo V1–V2 concluído. Última atualização: Abril 2026.

---

## 1. Objetivo

O módulo Inbox classifica, prioriza e sumariza emails do inbox do usuário, entregando ao briefing diário uma visão operacional clara do que exige atenção imediata, o que é follow-up, o que é ruído.

**Responsabilidades:**

- Buscar emails recentes via provedor configurado (Gmail ou Outlook)
- Classificar cada email em uma categoria funcional (`action`, `update`, `newsletter`, `noise`)
- Detectar flags operacionais por email (`requires_response`, `has_deadline`, `is_follow_up`, `is_opportunity`)
- Computar score de prioridade determinístico
- Derivar prioridade: `alta`, `media`, `baixa`
- Ordenar `action_items` por score
- Entregar payload estruturado ao `BriefingService`

---

## 2. Evolução

### Estado Inicial

Listagem simples de emails sem qualquer critério de relevância. Todos os emails tratados igualmente — sem classificação, sem prioridade, sem identificação de ação requerida.

### V1 — Classificação por Categoria e Flags

Introdução de 4 categorias funcionais com precedência explícita:

```
newsletter → noise → action → update
```

- **newsletter:** email contém padrões de lista de distribuição (`unsubscribe`, `descadastrar`, `boletim`…)
- **noise:** email contém padrões de promoção ou notificação social (`oferta especial`, `cupom`, `curtiu sua foto`…)
- **action:** email contém verbo de ação explícito (`responda`, `confirme`, `aprove`, `assine`…)
- **update:** default seguro para qualquer email não classificado como newsletter, noise ou action

Short-circuit absoluto para `newsletter` e `noise`: retornam imediatamente com `score=0` e `priority="baixa"`, sem computar flags ou score.

Flags operacionais detectadas para emails `action` e `update`:

| Flag | Ativa quando o texto contém |
|---|---|
| `requires_response` | `"?"`, `"aguardo"`, `"por favor"`, `"você pode"`, `"gostaria de saber"`… |
| `has_deadline` | `"prazo"`, `"urgente"`, `"vencimento"`, `"até amanhã"`, `"data limite"`… |
| `is_follow_up` | `"follow-up"`, `"lembrete"`, `"conforme conversamos"`, `"reminder"`… |
| `is_opportunity` | `"proposta"`, `"parceria"`, `"orçamento"`, `"reunião comercial"`… |

### V2 — Score Contextual e Priorização

Modelo de score determinístico com pesos por flag e heurística de remetente:

| Sinal | Peso |
|---|---|
| `has_deadline` | +4 |
| `requires_response` | +4 |
| `is_opportunity` | +2 |
| `is_follow_up` | +2 |
| `human_sender` | +2 |
| `bulk_sender` | −3 |

**`human_sender`:** ativado quando o remetente tem formato `"Nome <email>"` (nome antes do `<`). Boost para emails de pessoas nomeadas.

**`bulk_sender`:** ativado quando o endereço do remetente contém `no-reply`, `noreply`, `donotreply`, `mailer`, `notifications`, `bounce`. Penaliza remetentes automatizados não filtrados como newsletter/noise.

Thresholds de prioridade:

```
score ≥ 4  →  "alta"
score ≥ 0  →  "media"
score < 0  →  "baixa"
```

`action_items` no payload: emails com qualquer flag operacional (`requires_response`, `has_deadline`, `is_follow_up`, `is_opportunity`), ordenados por `score` decrescente.

---

## 3. Arquitetura

### Visão de Componentes

```
app/integrations/
  email_classifier.py    ← classificação individual de um email
  email_models.py        ← EmailMessage dataclass
  base_email_client.py   ← interface abstrata do cliente
  gmail_client.py        ← implementação Gmail
  outlook_client.py      ← implementação Outlook

app/modules/inbox/
  service.py             ← orquestra: busca, classifica, sumariza
```

### Fluxo Completo

```
Provedor configurado (Gmail ou Outlook)
        │
        ▼
  InboxService.summarize_emails()
        │
        ├── client.list_recent_emails()
        │   • busca emails recentes
        │   • retorna list[EmailMessage]
        │   • falha total → retorna payload vazio seguro
        │
        ├── _classify_all(emails)
        │   • para cada email: classify_email(email)
        │   • atualiza email.priority em lugar (source of truth)
        │   • falha individual → fallback (category="update", priority="baixa")
        │   • nunca aborta o loop
        │
        ├── separação por prioridade
        │   • high = emails com priority=="alta"
        │   • medium = emails com priority=="media"
        │   • low = emails com priority=="baixa"
        │   • unread = emails com is_read==False
        │
        ├── action_items
        │   • emails com qualquer flag operacional
        │   • ordenados por score decrescente
        │
        └── _build_summary()
            • texto com contagem por tipo
            │
            ▼
  BriefingService._compose()
  • consome inbox["summary"]
  • consome inbox["action_items"] → usa sender e subject
```

### Separação de Responsabilidades

- `email_classifier.py`: responsabilidade única — classificar um `EmailMessage` individual. Não faz I/O, não mantém estado.
- `inbox/service.py`: orquestra — busca emails, aplica classificação em lote, agrega resultados, entrega payload.
- Clientes (`GmailClient`, `OutlookClient`): responsabilidade única — buscar e normalizar emails do provedor.

---

## 4. Modelo de Decisão

### Texto de Análise

```python
text = f"{email.sender} {email.subject} {email.snippet}".lower()
```

O classificador opera sobre a concatenação de remetente, assunto e snippet (prévia do corpo). Não acessa o corpo completo do email.

### Lógica de Classificação de Categoria

```
1. _has_signal(text, _NEWSLETTER_SIGNALS) → "newsletter"  (short-circuit)
2. _has_signal(text, _NOISE_SIGNALS)      → "noise"       (short-circuit)
3. _has_signal(text, _ACTION_VERBS)       → "action"
4. _has_signal(text, _UPDATE_SIGNALS)     → "update"
5. default                                → "update"
```

`newsletter` e `noise` encerram o processamento imediatamente: `score=0`, `priority="baixa"`, todas as flags `False`.

### Cálculo de Score

O score é computado apenas para emails `action` e `update`. Flags são detectadas primeiro; o score reutiliza os resultados sem processamento redundante de texto.

```python
score = 0
if has_deadline:        score += 4
if requires_response:   score += 4
if is_opportunity:      score += 2
if is_follow_up:        score += 2

# heurística de remetente (análise do campo sender)
if bulk_sender:         score -= 3
if human_sender:        score += 2
```

### Heurística de Remetente

`bulk_sender`: qualquer substring de `_BULK_SENDER_SIGNALS` (`"no-reply"`, `"noreply"`, `"mailer"`, `"notifications"`, `"bounce"`) no endereço do remetente.

`human_sender`: remetente tem `"<"` no campo e texto antes do `"<"` é não-vazio — padrão `"Nome Sobrenome <email>"`.

Os dois sinais são mutuamente exclusivos na prática: um remetente bulk raramente tem nome humano antes do `<`.

### `action_items` — Ordenação

```python
action_emails = sorted(
    [e for e in emails if any_operational_flag(classifications[e.id])],
    key=lambda e: -classifications[e.id].score
)
```

Critério: score decrescente. Emails com múltiplos sinais positivos (deadline + requires_response + human_sender = score 10) aparecem antes de emails com sinal único (follow-up = score 2).

### Summary Textual

```python
parts = [f"{len(emails)} email(s)"]
if n_need_action:   parts.append(f"{n_need_action} exige(m) ação")
if n_follow_up:     parts.append(f"{n_follow_up} follow-up(s)")   # não duplo-contado com need_action
if n_newsletter:    parts.append(f"{n_newsletter} newsletter(s)")
if n_noise:         parts.append(f"{n_noise} ruído(s)")
if unread:          parts.append(f"{len(unread)} não lido(s)")
return " — ".join(parts) + "."
```

`n_need_action`: emails com `requires_response` OR `has_deadline`.
`n_follow_up`: emails com `is_follow_up` que **não** têm `requires_response` nem `has_deadline` (evita dupla contagem).

---

## 5. Garantias

### Determinismo

O classificador não mantém estado entre chamadas. A mesma combinação de `sender + subject + snippet` sempre produz a mesma `EmailClassification`. Não há randomness, timestamps internos ou dependências externas no classificador.

### Resiliência

- Falha no provedor de email (Gmail/Outlook indisponível): `summarize_emails()` captura a exceção e retorna payload vazio estruturado — nunca propaga o erro para o briefing.
- Falha na classificação de um email individual: `_classify_all()` captura, loga aviso, atribui `_FALLBACK_CLASSIFICATION` (`category="update"`, `priority="baixa"`, `reason_codes=["classification_error"]`) e continua.
- Nenhum erro individual interrompe o processamento do inbox.

### Compatibilidade com BriefingService

O `BriefingService._compose()` consome:

```python
inbox["summary"]              # string → garantido
inbox["action_items"]         # list[dict] → garantido
action_item["sender"]         # campo presente → garantido
action_item["subject"]        # campo presente → garantido
```

### Payload Completo de `summarize_emails()`

```python
{
    "total"           : int,
    "high_priority"   : int,
    "medium_priority" : int,
    "low_priority"    : int,
    "unread"          : int,
    "items"           : list[dict],   # todos os emails como dict
    "action_items"    : list[dict],   # emails com flags operacionais, ordenados por score
    "summary"         : str,
}
```

---

## 6. Limitações Conhecidas

### Heurística Textual

- O classificador analisa apenas `sender + subject + snippet`. Não acessa o corpo completo do email. Emails com contexto relevante apenas no corpo não são detectados corretamente.
- `"?"` como sinal único em `_RESPONSE_SIGNALS` é amplo: qualquer email com ponto de interrogação no snippet ativa `requires_response=True`, adicionando +4 ao score. Com `SCORE_THRESHOLD_HIGH=4`, isso é suficiente para `"alta"` sem nenhum outro sinal. A maioria dos emails conversacionais de humanos contém `"?"`.
- Emails em inglês que não contêm sinais PT-BR (`"prazo"`, `"urgente"`, `"aguardo"`) e também não contêm os sinais EN presentes nos sets (`"action required"`, `"deadline"`, `"follow-up"`) tendem a cair em `"update"` com score neutro.

### Ausência de Contexto Profundo

- Não há análise de thread: um email de resposta a uma conversa longa é tratado como email isolado.
- Não há aprendizado: o sistema não melhora com o comportamento real do usuário.
- Não há distinção entre remetentes conhecidos e desconhecidos além da heurística `human_sender`/`bulk_sender`.
- `is_opportunity` pode ser ativado por emails de spam sofisticado que contêm "proposta" ou "parceria" sem ser filtrado como noise (se não contiver sinais de `_NOISE_SIGNALS`).

### Labels de Prioridade

- O módulo Email usa `"alta/media/baixa"` (PT-BR) enquanto o módulo News usa `"high/medium/low"` (EN). Qualquer código que compare prioridades entre os dois módulos precisará de mapeamento explícito.

### `_FALLBACK_CLASSIFICATION` — Singleton Mutable

O objeto `_FALLBACK_CLASSIFICATION` em `inbox/service.py` é uma instância de `@dataclass` criada uma vez no nível de módulo e reutilizada para todos os emails que falham na classificação. Os campos `reason_codes` e `score_reasons` são listas. Se qualquer código futuro modificar esses campos no objeto compartilhado, a mutação afetará todas as classificações de fallback subsequentes na mesma sessão. Atualmente o código não faz isso, mas é uma fragilidade estrutural.

---

## 7. Próximos Passos

### Calibração com Uso Real (V2.1)

- Observar proporção de emails `"alta"` nos primeiros dias. Se > 60% do inbox (excluindo newsletter/noise) for `"alta"`, investigar `"?"` em `_RESPONSE_SIGNALS` como causa.
- Avaliar se `"?"` deve ser substituído por sinais compostos mais específicos (`"aguardo sua resposta"`, `"pode me responder"`) para reduzir inflação de `"alta"`.
- Monitorar `reason_codes=["classification_error"]` nos logs para detectar emails que disparam o fallback.

### Melhorias Candidatas (sem prazo definido)

- **Análise de thread:** considerar o histórico da conversa para contextualizar um email de resposta.
- **Remetentes conhecidos:** lista de remetentes sempre relevantes (independente de keywords) ou sempre irrelevantes.
- **Padronização de labels:** alinhar `"alta/media/baixa"` com `"high/medium/low"` do módulo News para facilitar comparações futuras.
- **Score de credibilidade por domínio de remetente:** domínios corporativos conhecidos recebem bônus; domínios suspeitos recebem penalidade.
