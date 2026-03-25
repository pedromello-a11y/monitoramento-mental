# 🧠 Monitoramento Mental

Bot de rastreamento diário de saúde mental e hábitos via WhatsApp, com botões interativos, nota de voz assíncrona, análise por IA, sistema de streak, acompanhamento de remédios e detecção de períodos de baixa.

> **Documento vivo.** Atualize sempre que uma etapa for concluída ou uma decisão mudar. Para retomar contexto em nova conversa com Claude, cole este README + sua pergunta.

-----

## ⚓ Alicerces

1. **Fricção mínima no input** — check-in completável em menos de 90 segundos. Padrões pré-selecionados minimizam toques. Medir uso real antes de simplificar.
1. **Zero dependência de ação ativa** — o bot dispara sozinho às 22h. Se a solução exige iniciativa diária do usuário, ela falha.
1. **Dados nunca se perdem silenciosamente** — estado do check-in persistido no banco. Erros logados. Recuperação via /ontem ou /checkin.
1. **Interface onde o usuário já está** — WhatsApp para input diário. Dashboard para configuração e análise.
1. **Banco de dados é a fonte da verdade** — nunca salvar estado crítico só em memória ou sessão.
1. **Construir em fases** — Fase 1 funcionando muito bem antes de qualquer extra.
1. **O sistema observa, não diagnostica** — linguagem sempre observacional e reflexiva, nunca clínica.
1. **Padrão adaptativo ≠ baseline analítico** — separação obrigatória entre default de preenchimento (UX) e referência de saúde (análise).
1. **WhatsApp = operacional. Dashboard = configuração.** — comandos simples e diários no WhatsApp. Tudo complexo no dashboard.
1. **Webhook nunca bloqueia** — responder HTTP 200 imediatamente. Processamento pesado sempre em background.
1. **Fallback web obrigatório** — se WhatsApp cair, endpoint `/checkin-web` permite registro manual pelo navegador (Fase 1).

-----

## Stack

|Componente            |Ferramenta                     |Custo                        |
|----------------------|-------------------------------|-----------------------------|
|Interface input       |WhatsApp via Whapi.cloud       |Sandbox grátis / $35/mês pago|
|Interface configuração|Streamlit (dashboard)          |Incluso Railway              |
|Fallback input        |Endpoint web `/checkin-web`    |Incluso Railway              |
|Backend               |Python + FastAPI               |—                            |
|Agendamento           |Railway Cron → endpoint interno|Incluso Railway              |
|Hospedagem            |Railway                        |Já pago                      |
|Banco de Dados        |PostgreSQL nativo Railway      |Incluso                      |
|Transcrição de voz    |OpenAI Whisper API (assíncrono)|~$0.006/min                  |
|Análise de notas      |OpenAI GPT-4o-mini (assíncrono)|~$0.01/dia                   |
|Conversão de áudio    |ffmpeg (OGG → MP3, com cleanup)|Grátis                       |


> **APScheduler descartado** — Railway Cron + endpoint `/internal/cron/22h` é mais previsível, sem risco de duplicata por escalonamento ou restart.

> Se Streamlit se mostrar limitado após uso real, migrar para React é cirúrgico — só o frontend muda.

-----

## Variáveis de Ambiente

```
WHAPI_TOKEN=           # token do canal Whapi
OPENAI_API_KEY=        # sua key OpenAI
DATABASE_URL=          # gerado pelo PostgreSQL do Railway
MY_WHATSAPP=           # seu número (ex: 5511999999999)
CHECKIN_HOUR=22
TIMEZONE=America/Sao_Paulo
INTERNAL_CRON_SECRET=  # token secreto para proteger endpoint de cron
```

-----

## Divisão de Responsabilidades

```
WHATSAPP (operacional diário)        DASHBOARD (configuração e análise)
─────────────────────────────        ──────────────────────────────────
/checkin — iniciar check-in          Cadastrar / editar / remover remédios
/ontem — check-in retroativo         Ativar / desativar campos
/cancelar — abortar check-in         Reordenar campos
/streak — ver sequência              Editar padrões adaptativos
/congelar — congelar streak          Editar baselines analíticos
/resumo — últimos 7 dias             Histórico e correlações
/remedios — consulta rápida          Períodos de baixa
                                     Relatórios e exportações futuras

FALLBACK WEB (se WhatsApp indisponível)
───────────────────────────────────────
/checkin-web — formulário HTML simples para registro manual
```

-----

## Padrão Adaptativo vs Baseline Analítico

**Separação obrigatória.**

|Conceito              |Função                                    |Atualização                                      |Onde editar|
|----------------------|------------------------------------------|-------------------------------------------------|-----------|
|**Padrão adaptativo** |Default de preenchimento no check-in (UX) |Automático — mediana dos últimos 30 dias com clamp|Dashboard  |
|**Baseline analítico**|Referência de saúde para alertas e análise|Manual — nunca automático                        |Dashboard  |

**Regra:** alertas sempre comparam vs baseline. Nunca vs padrão adaptativo. O sistema nunca trata comportamento frequente como automaticamente saudável.

### Clamps do Padrão Adaptativo

O padrão adaptativo nunca pode migrar para valores que normalizam estados ruins. Limites obrigatórios:

|Campo                |Padrão mín.|Padrão máx.|Lógica                                          |
|---------------------|-----------|-----------|--------------------------------------------------|
|Dor física           |0          |3          |Default nunca sobe acima de 3                     |
|Energia              |4          |10         |Default nunca desce abaixo de 4                   |
|Sono — qualidade     |4          |10         |Default nunca desce abaixo de 4                   |
|Saúde mental         |4          |10         |Default nunca desce abaixo de 4                   |
|Stress trabalho      |0          |5          |Default nunca sobe acima de 5                     |
|Stress relacionamento|0          |5          |Default nunca sobe acima de 5                     |
|Cigarros             |0          |sem limite |Contagem real, sem clamp                          |

**Cálculo:** `clamp(mediana_30_dias, min, max)`. Usar mediana ao invés de média para reduzir influência de outliers.

-----

## Campos do Check-in

|Campo                |Tipo             |Padrão inicial|Baseline inicial|Notas                           |
|---------------------|-----------------|--------------|----------------|--------------------------------|
|Dor física           |0-10             |0             |0               |Escala subjetiva                |
|Energia              |0-10             |5             |6               |Escala subjetiva                |
|Sono — horas         |numérico 0-16    |7             |7               |Horas reais, incremento 0.5h    |
|Sono — qualidade     |0-10             |5             |7               |Escala subjetiva                |
|Exercício            |opções           |desabilitado  |—               |                                |
|Saúde mental         |0-10             |5             |7               |Escala subjetiva                |
|Stress trabalho      |0-10             |0             |2               |Escala subjetiva                |
|Stress relacionamento|0-10             |0             |2               |Escala subjetiva                |
|Álcool               |opções           |Nenhum        |—               |                                |
|Cigarros             |numérico 0-40   |2             |2               |Contagem real de cigarros       |
|Desempenho social    |0-10             |5             |5               |Escala subjetiva                |
|Remédios             |por remédio      |a definir     |a definir       |Gerado dinamicamente da tabela  |
|Nota livre           |voz/texto        |opcional      |—               |                                |

**Sono — horas:** campo numérico real (não escala subjetiva). Botões no WhatsApp: `[4][5][6][7][8][9][10][+]`. Botão `[+]` permite digitar valor livre (ex: 5.5, 11, 3).

**Cigarros:** contagem real de cigarros fumados no dia. Botões: `[0][1][2][3][5][8][10][+]`. Botão `[+]` para valores acima de 10.

**Remédios:** passo gerado dinamicamente a partir da tabela `remedios` (filtrando `ativo=TRUE`). Botões variam conforme `tipo`: quantidade gera `[0][0.5][1][2][3+]`, binário gera `[✅ Sim][❌ Não]`.

-----

## Fluxo do Check-in Diário (22h, Brasília)

Estado persistido em `checkin_sessions` a cada passo — retomável após restart.
Input inválido em qualquer passo → bot repete a pergunta atual gentilmente.

```
── BLOCO FÍSICO ──────────────────────────────────────

PASSO 1 — Dor física (0-10)               padrão: 0
  [0][1][2][3][4][5][6][7][8][9][10]
  0 = sem dor | 5 = presente, afetou o dia | 10 = incapacitante

PASSO 2 — Energia (0-10)                  padrão: 5
  [0][1][2][3][4][5][6][7][8][9][10]
  0 = sem energia | 5 = funcional | 10 = muita energia

PASSO 3 — Sono — horas (real)             padrão: 7
  [4][5][6][7][8][9][10][+]
  horas dormidas de fato — [+] para digitar valor livre

PASSO 4 — Sono — qualidade (0-10)         padrão: 5
  [0][1][2][3][4][5][6][7][8][9][10]
  0 = acordou destruído | 5 = razoável | 10 = energia total

PASSO 5 — Exercício                       padrão: desabilitado
  [🏃 Corrida]  [🚶 Caminhada]  [🏊 Natação]  [❌ Nenhum]

── BLOCO MENTAL / EMOCIONAL ──────────────────────────

PASSO 6 — Saúde mental (0-10)             padrão: 5
  [0][1][2][3][4][5][6][7][8][9][10]
  0 = funcionamento comprometido | 5 = neutro | 10 = excelente

PASSO 7 — Stress trabalho (0-10)          padrão: 0
  [0][1][2][3][4][5][6][7][8][9][10]
  0 = nenhum | 5 = moderado, ocupou espaço mental | 10 = dia dominado

PASSO 8 — Stress relacionamento (0-10)    padrão: 0
  [0][1][2][3][4][5][6][7][8][9][10]
  (mesmas âncoras do stress trabalho)

── BLOCO COMPORTAMENTAL ──────────────────────────────

PASSO 9 — Álcool                          padrão: Nenhum
  [❌ Nenhum]  [🍺 Pouco]  [🍻 Moderado]  [💀 Muito]

PASSO 10 — Cigarros (contagem real)       padrão: 2
  [0][1][2][3][5][8][10][+]
  número de cigarros — [+] para digitar valor livre

PASSO 11 — Desempenho social (0-10)       padrão: 5
  [0][1][2][3][4][5][6][7][8][9][10]
  0 = em casa o dia todo | 5 = saídas normais | 10 = excesso de roles

── BLOCO REMÉDIOS (gerado dinamicamente) ─────────────

PASSO 12 — Remédios (quantidade por remédio)
  → Gerado a partir de SELECT * FROM remedios WHERE ativo=TRUE ORDER BY id
  → tipo='quantidade': [0][0.5][1][2][3+]
  → tipo='binario':    [✅ Sim][❌ Não]
  → desvio vs baseline calculado automaticamente

── BLOCO LIVRE ───────────────────────────────────────

PASSO 13 — Nota do dia (opcional)
  [🎤 Áudio]  [✏️ Texto]  [⏭️ Pular]

  Fluxo de voz (assíncrono — webhook não bloqueia):
  1. Webhook recebe áudio → responde HTTP 200 imediatamente
  2. Bot confirma: "🎤 Áudio recebido, processando..."
  3. Background task: ffmpeg OGG→MP3 → Whisper → GPT categoriza
  4. Cleanup obrigatório em bloco finally (arquivos .ogg e .mp3)
  5. Bot manda resultado como mensagem separada (~10-15s depois)
     Output: { "categorias": [...], "sentimento": "...", "resumo": "..." }

──────────────────────────────────────────────────────
✅ Resumo ao finalizar:
  🩺 Dor 2  ⚡ Energia 7  😴 Sono 7h / qualidade 6
  🧠 Mental 7  💼 Stress trab 3  ❤️ Stress rel 0
  🍺 Pouco  🚬 3  👥 Social 5
  💊 Zolpidem 1  Rivotril 0.5  🔥 34 dias seguidos
```

**Tempo estimado: 45s confirmando padrões | 90s com nota de voz**

### Tratamento de Input Inválido

Qualquer mensagem fora do esperado durante o check-in (figurinha, áudio no passo errado, texto livre num passo de botões):

```
Bot repete: "Não entendi essa resposta. 😊
             [repete os botões do passo atual]"
```

### Abortar Check-in

```
/cancelar → "Check-in cancelado.
              Você pode retomar quando quiser com /checkin."
            → sessão marcada como 'cancelado' no banco
```

### Timeout de Sessão

Sessão em `em_andamento` por mais de 2 horas sem atualização → marcada automaticamente como `abandonado`.

**Mecanismo de execução:** Railway Cron a cada hora bate em `POST /internal/cron/cleanup-sessoes`. O endpoint executa:

```sql
UPDATE checkin_sessions
SET status = 'abandonado',
    passo_abandono = passo_atual,
    atualizado_em = NOW()
WHERE status = 'em_andamento'
  AND atualizado_em < NOW() - INTERVAL '2 hours';
```

### Concorrência no Check-in

Se o cron das 22h disparar e o usuário mandar `/checkin` simultaneamente:

1. Antes de criar sessão, verificar se já existe sessão para aquela `data_referencia`
2. Se existe sessão `em_andamento` → retomar a existente (responder com o passo atual)
3. Se existe sessão `concluido` → informar que já fez o check-in do dia
4. Constraint UNIQUE(user_id, data_referencia) protege no banco como última barreira

### /ontem — Regras de Conflito

1. Se já existe check-in `concluido` para ontem → "Já existe check-in para ontem. Quer sobrescrever? [Sim][Não]"
2. Se existe sessão `em_andamento` para ontem → retomar sessão existente
3. Se existe sessão `abandonado` ou `cancelado` → criar nova sessão (limpa a anterior)
4. Se não existe → criar sessão retroativa normalmente

-----

## Medição de Uso Real

Registrado em `checkin_sessions` sem nenhuma ação extra:

- Horário de início e conclusão
- Duração total em segundos
- Passo de abandono (se houver)
- Taxa de conclusão acumulada

Aparece no resumo semanal:

```
⏱ Tempo médio do check-in: 52s  |  ✅ Conclusão: 94%
```

**Plano B — não implementar agora.** Só se taxa de conclusão cair abaixo de 80% após 30 dias:

- Modo rápido: só campos com desvio do padrão
- Agrupamento por blocos com confirmação única

-----

## Sistema de Streak

```
Incrementa → check-in feito até 23h59
Congela    → /congelar (não quebra, não incrementa — 3x/mês)
Zera       → dia passar sem check-in
```

**Pressão crescente, acolhimento na perda:**

```
22h00 → "🔥 34 dias seguidos. Hora do check-in de hoje."

22h30 → (só se não respondeu)
        "Ainda dá tempo para registrar hoje. 🙂"

23h15 → (só se não respondeu)
        "⚠️ Última chance hoje.
         34 dias. Vai perder por falta de 60 segundos?"

23h59 → (só se não respondeu)
        "Hoje não rolou registrar. Tudo bem.
         Seu histórico continua salvo.
         Amanhã você retoma. 🌙"

Dia seguinte após quebra:
        "Novo começo — dia 1.
         O registro de hoje já é progresso."
```

**Marcos comemorativos:**

```
7d   → "🔥 1 semana seguida. Você está criando um hábito real."
14d  → "🔥 2 semanas. Isso já diz muito sobre você."
30d  → "🔥 30 dias. Um mês inteiro de dados sobre você mesmo."
60d  → "🔥 60 dias. Seus dados já mostram padrões reais."
100d → "🔥 100 dias. Consistência construída um dia de cada vez."
365d → "🔥 1 ano. Você tem uma série histórica completa."
```

**Dia difícil** (saúde mental ≤ 4 + remédios acima do baseline):

```
"Parece que foi um dia mais pesado.
 Registrado. Um dia de cada vez. 🌙"
```

-----

## Agendamento — Railway Cron

Railway Cron bate nos endpoints internos no horário certo.
Cada disparo verifica `event_dispatch_log` antes de enviar — idempotente por design.

```
Cron 22h00  → POST /internal/cron/checkin         (disparo principal)
Cron 22h30  → POST /internal/cron/lembrete1       (lembrete suave)
Cron 23h15  → POST /internal/cron/lembrete2       (lembrete com pressão)
Cron 23h59  → POST /internal/cron/streak           (verifica perdas)
Cron */1h   → POST /internal/cron/cleanup-sessoes  (timeout de sessões abandonadas)
Cron dom 10h → POST /internal/cron/semanal         (resumo semanal)
Cron dia 1  → POST /internal/cron/mensal           (fechamento mensal)
```

Todos os endpoints protegidos por `INTERNAL_CRON_SECRET` no header.

**Fluxo de idempotência em cada endpoint:**

```python
key = f"{user_id}:{tipo_evento}:{data_referencia}"
if event_dispatch_log.exists(key):
    return  # já enviado, ignorar
# processar e registrar
event_dispatch_log.insert(key, status="enviado")
```

-----

## Fallback Web (Fase 1)

Endpoint HTML mínimo para registro manual se WhatsApp estiver indisponível. Não precisa ser bonito — só funcional.

```
GET  /checkin-web     → formulário HTML com todos os campos ativos
POST /checkin-web     → salva check-in direto no banco
```

Lógica: mesma do check-in normal (verifica sessão existente, valida campos, salva em `checkins`). Sem streak automático — streak só conta via WhatsApp para manter incentivo de usar o canal principal.

**Quando usar:** se Whapi cair, se número for banido, ou enquanto aguarda upgrade de plano.

-----

## Detecção de Períodos de Baixa

Automática, sem marcador manual. Tom observacional — o sistema nota padrões, não diagnostica.

**Critério de entrada** — 3 de 4 por 2+ dias consecutivos:

- Saúde mental ≤ 4
- Dor física ≥ 6
- Energia ≤ 3
- Sono qualidade ≤ 3

**Alerta de entrada:**

```
"Seus indicadores ficaram mais baixos por alguns dias seguidos.
 Vale observar isso com atenção. Como você está se sentindo?"
```

**Alerta de saída** (indicadores melhorando por 3+ dias):

```
"Seus indicadores melhoraram nos últimos dias. 📈
 Score mental: 3.4 → 7.2  |  Dor: 7.1 → 2.8
 Esse período durou 11 dias.
 O que você acha que ajudou?
 Faz sentido registrar na nota de hoje?"
```

**Alerta de remédios acima do baseline por 3 dias:**

```
"Notamos que o uso de Rivotril ficou acima do seu referencial
 por 3 dias seguidos. Score médio nesses dias: 3.8.
 Só uma observação — quer notar algo sobre isso?"
```

-----

## Banco de Dados

```sql
CREATE TABLE usuarios (
  id         SERIAL PRIMARY KEY,
  whatsapp   TEXT UNIQUE NOT NULL,
  nome       TEXT,
  criado_em  TIMESTAMP DEFAULT NOW()
);

CREATE TABLE checkins (
  id                    SERIAL PRIMARY KEY,
  user_id               INT REFERENCES usuarios(id),
  data                  DATE NOT NULL,
  dor_fisica            INT CHECK (dor_fisica BETWEEN 0 AND 10),
  energia               INT CHECK (energia BETWEEN 0 AND 10),
  sono_horas            NUMERIC(3,1) CHECK (sono_horas BETWEEN 0 AND 16),
  sono_qualidade        INT CHECK (sono_qualidade BETWEEN 0 AND 10),
  exercicio             TEXT,
  saude_mental          INT CHECK (saude_mental BETWEEN 0 AND 10),
  stress_trabalho       INT CHECK (stress_trabalho BETWEEN 0 AND 10),
  stress_relacionamento INT CHECK (stress_relacionamento BETWEEN 0 AND 10),
  alcool                TEXT,
  cigarros              INT CHECK (cigarros BETWEEN 0 AND 40),
  desempenho_social     INT CHECK (desempenho_social BETWEEN 0 AND 10),
  remedios_tomados      JSONB,
  nota_raw              TEXT,
  nota_categorias       TEXT[],
  nota_sentimento       TEXT,
  criado_em             TIMESTAMP DEFAULT NOW(),
  UNIQUE(user_id, data)
);

CREATE TABLE checkin_remedios (
  id          SERIAL PRIMARY KEY,
  checkin_id  INT REFERENCES checkins(id) ON DELETE CASCADE,
  remedio_id  INT REFERENCES remedios(id),
  quantidade  NUMERIC(3,1) NOT NULL,
  desvio      NUMERIC(3,1),  -- quantidade - dose_padrao
  criado_em   TIMESTAMP DEFAULT NOW()
);

CREATE TABLE remedios (
  id           SERIAL PRIMARY KEY,
  user_id      INT REFERENCES usuarios(id),
  nome         TEXT NOT NULL,
  dose         TEXT,
  dose_padrao  NUMERIC DEFAULT 1,  -- baseline analítico
  tipo         TEXT DEFAULT 'quantidade', -- 'quantidade' ou 'binario'
  ativo        BOOLEAN DEFAULT TRUE,
  criado_em    TIMESTAMP DEFAULT NOW()
);

INSERT INTO remedios (user_id, nome, dose, dose_padrao, tipo) VALUES
  (1, 'Zolpidem', '5mg', 1, 'quantidade'),
  (1, 'Rivotril',  NULL, 1, 'quantidade'),
  (1, 'Tramadol',  NULL, 1, 'binario');

CREATE TABLE campos_config (
  id           SERIAL PRIMARY KEY,
  user_id      INT REFERENCES usuarios(id),
  campo        TEXT NOT NULL,
  ativo        BOOLEAN DEFAULT TRUE,
  ordem        INT NOT NULL,
  padrao_atual TEXT,  -- default UX — mediana 30 dias com clamp
  baseline     TEXT,  -- referência analítica — só via dashboard
  padrao_min   TEXT,  -- clamp mínimo do padrão adaptativo
  padrao_max   TEXT,  -- clamp máximo do padrão adaptativo
  UNIQUE(user_id, campo)
);

INSERT INTO campos_config (user_id, campo, ativo, ordem, padrao_atual, baseline, padrao_min, padrao_max) VALUES
  (1, 'dor_fisica',             TRUE,  1,  '0',       '0',   '0', '3'),
  (1, 'energia',                TRUE,  2,  '5',       '6',   '4', NULL),
  (1, 'sono_horas',             TRUE,  3,  '7',       '7',   NULL, NULL),
  (1, 'sono_qualidade',         TRUE,  4,  '5',       '7',   '4', NULL),
  (1, 'exercicio',              FALSE, 5,  NULL,      NULL,  NULL, NULL),
  (1, 'saude_mental',           TRUE,  6,  '5',       '7',   '4', NULL),
  (1, 'stress_trabalho',        TRUE,  7,  '0',       '2',   '0', '5'),
  (1, 'stress_relacionamento',  TRUE,  8,  '0',       '2',   '0', '5'),
  (1, 'alcool',                 TRUE,  9,  'nenhum',  NULL,  NULL, NULL),
  (1, 'cigarros',               TRUE,  10, '2',       '2',   NULL, NULL),
  (1, 'desempenho_social',      TRUE,  11, '5',       '5',   NULL, NULL),
  (1, 'remedios',               TRUE,  12, NULL,      NULL,  NULL, NULL),
  (1, 'nota',                   TRUE,  13, NULL,      NULL,  NULL, NULL);

CREATE TABLE checkin_sessions (
  id                 SERIAL PRIMARY KEY,
  user_id            INT REFERENCES usuarios(id),
  data_referencia    DATE NOT NULL,
  passo_atual        INT DEFAULT 1,
  respostas_parciais JSONB DEFAULT '{}',
  status             TEXT DEFAULT 'em_andamento',
  -- em_andamento | concluido | abandonado | cancelado
  retroativo_ontem   BOOLEAN DEFAULT FALSE,
  iniciado_em        TIMESTAMP DEFAULT NOW(),
  atualizado_em      TIMESTAMP DEFAULT NOW(),
  concluido_em       TIMESTAMP,
  duracao_segundos   INT,
  passo_abandono     INT,
  UNIQUE(user_id, data_referencia)
);

CREATE TABLE streak (
  id             SERIAL PRIMARY KEY,
  user_id        INT REFERENCES usuarios(id),
  streak_atual   INT DEFAULT 0,
  streak_maximo  INT DEFAULT 0,
  ultimo_checkin DATE,
  atualizado_em  TIMESTAMP DEFAULT NOW()
);

CREATE TABLE streak_congelamentos (
  id        SERIAL PRIMARY KEY,
  user_id   INT REFERENCES usuarios(id),
  data      DATE NOT NULL,
  criado_em TIMESTAMP DEFAULT NOW(),
  UNIQUE(user_id, data)
);

CREATE TABLE periodos_baixa (
  id             SERIAL PRIMARY KEY,
  user_id        INT REFERENCES usuarios(id),
  inicio         DATE,
  fim            DATE,
  duracao_dias   INT,
  gatilhos       TEXT[],
  habitos_saida  TEXT[],
  score_medio    NUMERIC,
  dor_media      NUMERIC,
  criado_em      TIMESTAMP DEFAULT NOW()
);

CREATE TABLE event_dispatch_log (
  id               SERIAL PRIMARY KEY,
  user_id          INT REFERENCES usuarios(id),
  tipo_evento      TEXT NOT NULL,
  data_referencia  DATE NOT NULL,
  scheduled_for    TIMESTAMP NOT NULL,
  sent_at          TIMESTAMP,
  status           TEXT DEFAULT 'pendente',
  -- pendente | enviado | erro | ignorado
  idempotency_key  TEXT UNIQUE NOT NULL,
  -- formato: user_id:tipo_evento:data_referencia
  detalhe_erro     TEXT,
  criado_em        TIMESTAMP DEFAULT NOW()
);

CREATE TABLE erros (
  id        SERIAL PRIMARY KEY,
  user_id   INT,
  tipo      TEXT,
  detalhe   TEXT,
  criado_em TIMESTAMP DEFAULT NOW()
);

-- Índices para queries de relatório e detecção de baixa
CREATE INDEX idx_checkins_user_data ON checkins(user_id, data);
CREATE INDEX idx_checkins_data_range ON checkins(user_id, data DESC);
CREATE INDEX idx_checkin_sessions_status ON checkin_sessions(status, atualizado_em);
CREATE INDEX idx_checkin_remedios_checkin ON checkin_remedios(checkin_id);
CREATE INDEX idx_checkin_remedios_remedio ON checkin_remedios(remedio_id);
CREATE INDEX idx_periodos_baixa_user ON periodos_baixa(user_id);
CREATE INDEX idx_event_dispatch_tipo ON event_dispatch_log(tipo_evento, data_referencia);
CREATE INDEX idx_erros_tipo ON erros(tipo, criado_em);
CREATE INDEX idx_streak_congelamentos_user_data ON streak_congelamentos(user_id, data);
```

-----

## Comandos do WhatsApp

```
/checkin    → inicia check-in manual
/ontem      → check-in retroativo para ontem (com tratamento de conflito)
/cancelar   → aborta check-in em andamento
/streak     → sequência atual e máxima
/congelar   → congela streak 1 dia (máx 3x/mês — verificado por data real)
/resumo     → últimos 7 dias com comparação
/remedios   → lista remédios ativos e doses padrão
```

### /congelar — Validação

```python
# Contar congelamentos do mês corrente
count = SELECT COUNT(*) FROM streak_congelamentos
        WHERE user_id = ? AND date_trunc('month', data) = date_trunc('month', CURRENT_DATE)

if count >= 3:
    "Você já usou 3 congelamentos este mês. Próximo reset dia 1."
else:
    INSERT INTO streak_congelamentos (user_id, data) VALUES (?, CURRENT_DATE)
    "Streak congelado hoje. Você tem {2-count} congelamentos restantes este mês."
```

-----

## Dashboard (Streamlit)

URL pública no Railway. Bot manda link no resumo semanal a partir do **dia 30**.

**Telas:**

- **Hoje** — check-in do dia, streak, comparação com baseline
- **Histórico** — linha do tempo (30/90/365 dias), períodos de baixa destacados
- **Correlações** — variáveis vs saúde mental, insights observacionais
- **Remédios** — consumo mês a mês, desvio do baseline, cadastro e edição (usa tabela `checkin_remedios` para queries)
- **Configurações** — ativar/desativar/reordenar campos, padrões, baselines e clamps
- **Períodos de baixa** — duração, frequência, gatilhos, hábitos de saída

-----

## Relatórios Automáticos

**Todo domingo 10h:**

```
📊 Sua semana

🩺 Dor: 2.1  ⚡ Energia: 7.2  😴 Sono: 6.8h / qualidade 5.4
🧠 Mental: 7.1  (↑ vs 6.4 semana passada)
💼 Stress trab: 3.2  ❤️ Stress rel: 0.8
🚬 Cigarros: média 2.8
💊 Remédios: dentro do baseline em 6 de 7 dias
🔥 Sequência: 34 dias
⏱ Tempo médio check-in: 52s  |  ✅ Conclusão: 100%

Nos dias com exercício, seu score mental foi 2 pontos
acima dos dias sem. Faz sentido pra você?
```

> **Nota:** campo exercício só aparece no relatório se estiver ativo (`campos_config.ativo=TRUE`).

**Todo dia 1:**

```
📅 Fechamento do mês

🧠 Score médio: 6.8  🩺 Dor: 2.4  ⚡ Energia: 6.9
😴 Sono: 6.9h / qualidade 5.1  |  Dias: 30 de 30 ✅

🚬 Cigarros: média 2.8 (↓ vs 3.4 mês passado)
💊 Zolpidem: 18 dias (↓ vs 24 mês passado)

Períodos de baixa: 1 episódio (8 dias)
Padrão observado: stress trabalho acima de 7 por 3 dias
+ sono qualidade abaixo de 3.
O que acha? Quer observar isso no próximo mês?
```

-----

## Fases de Implementação

### Fase 1 — Core (semana 1-2)

Check-in completo, estado persistido, Railway Cron (incluindo cleanup-sessoes), idempotência, voz assíncrona, /cancelar, tratamento de input inválido, streak com congelamento por data, concorrência no check-in, conflito no /ontem, fallback web, remédios dinâmicos.
**Validar:** funcionando todo dia sem quebrar?

### Fase 2 — Inteligência (semana 3-4)

Detecção de períodos de baixa, padrões adaptativos com mediana e clamp, relatórios automáticos.
**Validar:** insights fazem sentido com os dados reais?

### Fase 3 — Dashboard (após 30 dias)

Streamlit completo. Bot começa a mandar o link.
**Validar:** você usa o dashboard? Experiência no celular é boa?

### Fase 4 — Refinamento

Se taxa de conclusão cair abaixo de 80%, avaliar modo rápido.

-----

## 🧩 Blocos de Execução da Fase 1 — Guia para Economia de Créditos

**Princípio:** cole o README inteiro como contexto (input é barato), mas peça UMA coisa por vez (output controlado). Só avance para o próximo bloco quando o anterior estiver testado e funcionando.

**Regra de ouro:** se algo der erro, cole o traceback completo — não descreva o erro com suas palavras. Correção cirúrgica custa 10x menos que "revise tudo".

---

### BLOCO A — Estrutura + Banco + Config

**O que pedir:**
```
[Cole o README inteiro]

Implementar BLOCO A — Estrutura do projeto:
- Estrutura de pastas do projeto
- requirements.txt com todas as dependências da Fase 1
- Procfile para Railway
- nixpacks.toml (incluir ffmpeg)
- Schema SQL completo (todas as tabelas + índices + seed data)
- Arquivo de config (env vars, database connection, constantes)
- main.py com FastAPI básico (health check + init do banco)
- Módulo de conexão com banco (async SQLAlchemy ou asyncpg)

NÃO implementar: webhook, check-in, cron, voz, comandos.
Gerar todos os arquivos completos, prontos para deploy.
```

**Testar antes de avançar:**
- [ ] Deploy no Railway funciona sem erro
- [ ] Health check responde 200
- [ ] Tabelas criadas no PostgreSQL
- [ ] Seed data inserida (remédios + campos_config)

---

### BLOCO B — Webhook + Máquina de Estados do Check-in

**O que pedir:**
```
[Cole o README inteiro]

Implementar BLOCO B — Webhook + Check-in:
- Endpoint POST /webhook para receber mensagens do Whapi
- Máquina de estados do check-in (todos os 13 passos)
- Estado persistido em checkin_sessions a cada passo
- Envio de botões interativos via Whapi
- Tratamento de input inválido (repetir pergunta)
- Campos com botão [+] para valor livre (sono_horas, cigarros)
- Remédios dinâmicos lidos da tabela
- Salvamento em checkins + checkin_remedios ao concluir
- Resumo final formatado com emojis
- Concorrência: verificar sessão existente antes de criar
- /checkin manual (iniciar check-in)

O BLOCO A já está implementado. Usar a estrutura existente.
NÃO implementar: cron, voz, /ontem, /cancelar, streak, outros comandos.
```

**Testar antes de avançar:**
- [ ] /checkin inicia fluxo completo
- [ ] Botões aparecem no WhatsApp
- [ ] Padrões pré-selecionados funcionam
- [ ] Valor livre funciona (sono 5.5, cigarros 15)
- [ ] Input inválido repete a pergunta
- [ ] Dados salvos no banco corretamente
- [ ] Resumo final aparece formatado

---

### BLOCO C — Endpoints Cron + Idempotência + Streak

**O que pedir:**
```
[Cole o README inteiro]

Implementar BLOCO C — Cron + Streak:
- POST /internal/cron/checkin (disparo 22h com streak no texto)
- POST /internal/cron/lembrete1 (22h30 — suave)
- POST /internal/cron/lembrete2 (23h15 — com pressão)
- POST /internal/cron/streak (23h59 — verificar perdas)
- POST /internal/cron/cleanup-sessoes (timeout >2h → abandonado)
- Proteção por INTERNAL_CRON_SECRET em todos os endpoints
- Idempotência via event_dispatch_log em cada endpoint
- Lógica de streak: incrementar, zerar, marcos comemorativos
- Mensagem de dia difícil (mental ≤ 4 + remédios acima baseline)
- Tabela streak atualizada ao concluir check-in

Os BLOCOS A e B já estão implementados.
NÃO implementar: voz, /ontem, /cancelar, /congelar, fallback web, relatórios.
```

**Testar antes de avançar:**
- [ ] curl nos endpoints cron funciona com header correto
- [ ] Sem header → 403
- [ ] Disparo duplicado não gera mensagem duplicada
- [ ] Streak incrementa ao concluir check-in
- [ ] Lembretes só disparam se não respondeu
- [ ] Cleanup marca sessões abandonadas

---

### BLOCO D — Voz Assíncrona

**O que pedir:**
```
[Cole o README inteiro]

Implementar BLOCO D — Processamento de voz:
- Detecção de áudio no webhook (passo 13 do check-in)
- HTTP 200 imediato + mensagem "🎤 Áudio recebido, processando..."
- Background task: download do áudio → ffmpeg OGG→MP3 → Whisper → GPT-4o-mini
- Cleanup obrigatório de .ogg e .mp3 em bloco finally
- Resultado enviado como mensagem separada
- Output GPT: { categorias, sentimento, resumo }
- Salvar nota_raw, nota_categorias, nota_sentimento no checkin

Os BLOCOS A, B e C já estão implementados.
NÃO implementar: /ontem, /cancelar, /congelar, fallback web, relatórios.
```

**Testar antes de avançar:**
- [ ] Enviar áudio no passo 13 → resposta imediata
- [ ] Resultado aparece ~10-15s depois
- [ ] Arquivos temporários deletados (verificar no servidor)
- [ ] Dados salvos no check-in correto

---

### BLOCO E — Comandos WhatsApp

**O que pedir:**
```
[Cole o README inteiro]

Implementar BLOCO E — Comandos WhatsApp:
- /ontem com todas as regras de conflito (concluido → perguntar sobrescrever,
  em_andamento → retomar, abandonado/cancelado → criar nova)
- /cancelar → marcar sessão como cancelado
- /streak → mostrar streak atual e máximo
- /congelar → com validação de 3x/mês via tabela streak_congelamentos
- /resumo → últimos 7 dias formatado
- /remedios → listar remédios ativos e doses

Os BLOCOS A, B, C e D já estão implementados.
NÃO implementar: fallback web, relatórios semanais/mensais.
```

**Testar antes de avançar:**
- [ ] /ontem com check-in existente → pergunta sobrescrita
- [ ] /cancelar durante check-in → sessão cancelada
- [ ] /congelar 4x no mesmo mês → bloqueado na 4ª
- [ ] /streak → números corretos
- [ ] /resumo → dados dos últimos 7 dias
- [ ] /remedios → lista atualizada

---

### BLOCO F — Fallback Web + Deploy Final

**O que pedir:**
```
[Cole o README inteiro]

Implementar BLOCO F — Fallback web + ajustes finais:
- GET /checkin-web → formulário HTML simples com campos ativos
- POST /checkin-web → salvar check-in no banco (sem streak)
- Verificar sessão existente antes de salvar
- Revisar Procfile e nixpacks.toml para deploy final
- Garantir que todos os endpoints estão registrados no main.py

Os BLOCOS A-E já estão implementados.
Esse é o último bloco da Fase 1.
```

**Testar antes de avançar:**
- [ ] /checkin-web renderiza formulário
- [ ] Submissão salva no banco
- [ ] Não quebra se já existe check-in do dia
- [ ] Deploy final no Railway funciona

---

### Dicas de Economia Durante a Execução

1. **Nunca peça "revise o código inteiro"** — aponte arquivo + função + erro
2. **Não peça explicações junto com código** — se quer código, peça só código
3. **Teste localmente entre blocos** — cada correção com traceback real custa menos
4. **Se Claude Code disponível, use para código** — chat para decisões estratégicas
5. **Um bloco por conversa nova** — contexto limpo evita confusão e retrabalho

-----

## Prompt para Claude Code

```
Projeto: Monitoramento Mental
Bot de saúde mental via WhatsApp. Check-in diário em blocos com padrões
adaptativos separados de baselines analíticos, streak com pressão crescente
e acolhimento na perda, voz assíncrona por IA, remédios dinâmicos,
idempotência no agendamento via Railway Cron.
Implementar APENAS Fase 1 agora.

STACK:
- Python + FastAPI
- Railway Cron → endpoints /internal/cron/* (NÃO usar APScheduler)
- Whapi.cloud — WHAPI_TOKEN
- OpenAI Whisper + GPT-4o-mini — OPENAI_API_KEY
- PostgreSQL Railway — DATABASE_URL
- ffmpeg (OGG→MP3 — cleanup obrigatório em bloco finally)
- Streamlit (Fase 3 — não implementar agora)

REGRAS DE ARQUITETURA OBRIGATÓRIAS:
1. Webhook NUNCA bloqueia — responder HTTP 200 imediato sempre
2. Processamento de voz SEMPRE em background task (asyncio)
3. Cleanup de arquivos .ogg e .mp3 SEMPRE em bloco finally
4. Estado do check-in SEMPRE persistido em checkin_sessions (nunca em memória)
5. Todo disparo verificar idempotency_key antes de enviar
6. Endpoints /internal/cron/* protegidos por INTERNAL_CRON_SECRET no header
7. Remédios SEMPRE gerados dinamicamente da tabela (nunca hardcoded)
8. Antes de criar sessão, SEMPRE verificar se já existe para aquela data

AGENDAMENTO via Railway Cron:
POST /internal/cron/checkin         → 22h00 (disparo principal)
POST /internal/cron/lembrete1       → 22h30 (lembrete suave)
POST /internal/cron/lembrete2       → 23h15 (lembrete com pressão)
POST /internal/cron/streak          → 23h59 (verificar perdas)
POST /internal/cron/cleanup-sessoes → */1h (timeout sessões abandonadas >2h)
POST /internal/cron/semanal         → domingo 10h
POST /internal/cron/mensal          → dia 1 de cada mês

TRATAMENTO DE INPUT INVÁLIDO:
- Input inesperado durante check-in → repetir pergunta atual gentilmente
- /cancelar → marcar sessão como 'cancelado', confirmar ao usuário
- Sessão em_andamento há mais de 2h → cron cleanup marca como 'abandonado'

CONCORRÊNCIA NO CHECK-IN:
- Antes de criar sessão, verificar se já existe para data_referencia
- Se em_andamento → retomar existente
- Se concluido → informar que já fez o check-in
- UNIQUE(user_id, data_referencia) como última barreira

/ONTEM — REGRAS DE CONFLITO:
- Se concluido para ontem → perguntar se quer sobrescrever
- Se em_andamento para ontem → retomar
- Se abandonado/cancelado → criar nova sessão

FLUXO DE VOZ ASSÍNCRONO:
1. Webhook recebe áudio → HTTP 200 imediato
2. Bot confirma: "🎤 Áudio recebido, processando..."
3. Background task: ffmpeg OGG→MP3 → Whisper → GPT
4. Finally: deletar arquivos temporários
5. Bot manda resultado como mensagem separada

SEPARAÇÃO OBRIGATÓRIA:
- campos_config.padrao_atual → default UX, mediana 30 dias com clamp
- campos_config.baseline → referência analítica, NUNCA automático
- campos_config.padrao_min/padrao_max → limites do padrão adaptativo
- Alertas sempre vs baseline, nunca vs padrao_atual
- Cálculo padrão: clamp(mediana_30_dias, padrao_min, padrao_max)

CAMPOS:
Bloco físico:    dor_fisica(0-10, pad=0, base=0) energia(0-10, pad=5, base=6)
                 sono_horas(NUMERIC 0-16, pad=7, base=7) sono_qualidade(0-10, pad=5, base=7)
                 exercicio(opções, off)
Bloco mental:    saude_mental(0-10, pad=5, base=7) stress_trabalho(0-10, pad=0, base=2)
                 stress_relacionamento(0-10, pad=0, base=2)
Bloco comp:      alcool(opções, nenhum) cigarros(INT 0-40, pad=2, base=2)
                 desempenho_social(0-10, pad=5, base=5)
Bloco remédios:  DINÂMICO — ler da tabela remedios WHERE ativo=TRUE
                 tipo='quantidade' → botões [0][0.5][1][2][3+]
                 tipo='binario' → botões [✅ Sim][❌ Não]
                 Salvar em checkin_remedios (normalizado) E em checkins.remedios_tomados (JSONB)
Bloco livre:     nota assíncrona

SONO_HORAS: botões [4][5][6][7][8][9][10][+] onde [+] pede valor livre
CIGARROS: botões [0][1][2][3][5][8][10][+] onde [+] pede valor livre

STREAK:
- Congelamento: tabela streak_congelamentos com data real (máx 3/mês por contagem)
- Validação: COUNT(*) WHERE date_trunc('month', data) = date_trunc('month', CURRENT_DATE)
22h00 → "🔥 N dias seguidos. Hora do check-in de hoje."
22h30 → "Ainda dá tempo para registrar hoje. 🙂"
23h15 → "⚠️ Última chance hoje. N dias. Vai perder por falta de 60 segundos?"
23h59 → "Hoje não rolou registrar. Tudo bem. Amanhã você retoma. 🌙"
Marcos: 7, 14, 30, 60, 100, 365 dias

FALLBACK WEB (implementar na Fase 1):
GET  /checkin-web → formulário HTML simples com campos ativos
POST /checkin-web → salva check-in no banco (sem streak)

COMANDOS WHATSAPP (apenas esses — nada de configuração):
/checkin, /ontem, /cancelar, /streak, /congelar, /resumo, /remedios

BANCO — criar todas as tabelas com user_id + índices:
usuarios, checkins, checkin_remedios, remedios, campos_config,
checkin_sessions, streak, streak_congelamentos, periodos_baixa,
event_dispatch_log, erros
Índices: idx_checkins_user_data, idx_checkins_data_range,
idx_checkin_sessions_status, idx_checkin_remedios_checkin,
idx_checkin_remedios_remedio, idx_periodos_baixa_user,
idx_event_dispatch_tipo, idx_erros_tipo, idx_streak_congelamentos_user_data

REMÉDIOS SEED:
Zolpidem 5mg dose_padrao=1 tipo=quantidade
Rivotril dose_padrao=1 tipo=quantidade
Tramadol dose_padrao=1 tipo=binario

DEPLOY:
requirements.txt, Procfile, nixpacks.toml (ffmpeg)
Variáveis: WHAPI_TOKEN, OPENAI_API_KEY, DATABASE_URL,
MY_WHATSAPP, INTERNAL_CRON_SECRET, TIMEZONE=America/Sao_Paulo
```

-----

## Rodando Localmente

Passos mínimos para subir o app e visualizar o fallback web `/checkin-web`.

```bash
# 1. Criar e ativar virtualenv
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

# 2. Instalar dependências
pip install -r requirements.txt

# 3. Preencher variáveis de ambiente
# Já existe .env com DATABASE_URL vazio — suficiente para subir sem banco.
# Para salvar dados, preencha DATABASE_URL com a URL do Postgres.

# 4. Subir o servidor
uvicorn main:app --reload

# 5. Abrir no navegador
# http://localhost:8000/checkin-web   ← formulário de fallback web
# http://localhost:8000/health        ← health check
# http://localhost:8000/docs          ← documentação automática (FastAPI)
```

**Comportamento sem banco:**
- `GET /checkin-web` — renderiza o formulário normalmente.
- `POST /checkin-web` (submeter o formulário) — retorna página de diagnóstico (503) com instrução para preencher `DATABASE_URL`. Não estoura 500.
- Webhook e cron ignoram requisições (retornam 403 ou "ignored") sem as variáveis de ambiente.

-----

## Roadmap Futuro

- [ ] Fase 2: períodos de baixa + padrões adaptativos (mediana + clamp) + relatórios
- [ ] Fase 3: dashboard Streamlit completo
- [ ] Modo rápido (só se conclusão < 80%)
- [ ] Exportar CSV pelo dashboard
- [ ] Integração Apple Health / Google Fit
- [ ] /fuso para viagens
- [ ] Análise preditiva antes de entrar em baixa
- [ ] React + FastAPI se Streamlit for limitante

-----

## Riscos Conhecidos

|Risco                                 |Probabilidade|Mitigação                                                        |
|--------------------------------------|-------------|-----------------------------------------------------------------|
|Sandbox Whapi bloqueando disparo ativo|Alta         |**Testar no dia 0** — se falhar, upgrade imediato                |
|WhatsApp totalmente indisponível      |Baixa        |Fallback web `/checkin-web` funcional desde Fase 1               |
|Mensagem duplicada por restart        |Baixa        |Railway Cron + idempotency_key eliminam esse risco               |
|Estado perdido em restart             |Baixa        |checkin_sessions persiste cada passo                             |
|Vazamento de disco com ffmpeg         |Baixa        |Cleanup obrigatório em bloco finally                             |
|Webhook travado processando voz       |Baixa        |HTTP 200 imediato + processamento em background                  |
|Input inválido travando check-in      |Média        |Bot repete pergunta + /cancelar disponível                       |
|Ban de número (API não-oficial)       |Baixa        |Fallback web + usar número secundário se quiser zero risco       |
|Áudio OGG rejeitado pelo Whisper      |Certa        |ffmpeg converte antes — testar isoladamente                      |
|Check-in longo demais                 |Média        |Medir 30 dias antes de simplificar                               |
|Sessão dupla por concorrência         |Baixa        |Verificar sessão existente antes de criar + UNIQUE constraint    |
|Conflito /ontem com check-in existente|Média        |Perguntar se quer sobrescrever — regras documentadas             |
|Padrão adaptativo normaliza estado ruim|Média       |Mediana com clamp obrigatório por campo                          |

-----

## Checklist de Execução

**Antes de tudo — validar Sandbox:**

- [ ] 0. Criar conta Whapi → escanear QR → **testar disparo ativo imediatamente**
  - Se falhar: fazer upgrade para plano pago antes de continuar

**Fase 1:**

- [ ] 1. Criar projeto Railway → PostgreSQL → DATABASE_URL
- [ ] 2. Configurar variáveis de ambiente (incluindo INTERNAL_CRON_SECRET)
- [ ] 3. Colar prompt do Claude Code → gerar todos os arquivos
- [ ] 4. Fazer deploy no Railway
- [ ] 5. Configurar webhook no Whapi → `https://SEU-APP.railway.app/webhook`
- [ ] 6. Configurar Railway Cron (7 horários — incluindo cleanup-sessoes a cada hora)
- [ ] 7. Testar /checkin — fluxo completo com padrões pré-selecionados
- [ ] 8. Testar sono_horas com valor livre (ex: 5.5)
- [ ] 9. Testar cigarros com valor acima de 10
- [ ] 10. Testar input inválido — bot deve repetir a pergunta
- [ ] 11. Testar /cancelar — sessão marcada como cancelado
- [ ] 12. Testar retomada após simular restart (sessão em_andamento)
- [ ] 13. Testar concorrência — /checkin quando cron já disparou
- [ ] 14. Testar /ontem com check-in existente — confirmar pergunta de sobrescrita
- [ ] 15. Testar envio de áudio — confirmar HTTP 200 imediato + resultado assíncrono
- [ ] 16. Confirmar cleanup dos arquivos .ogg e .mp3 após transcrição
- [ ] 17. Testar /congelar — verificar contagem mensal correta
- [ ] 18. Testar fallback web /checkin-web — formulário funcional
- [ ] 19. Aguardar 22h — validar disparo e idempotência
- [ ] 20. Validar lembretes 22h30 e 23h15
- [ ] 21. Verificar que remédios são gerados dinamicamente da tabela

**Fase 2:**

- [ ] 22. Após 30 dias validar padrões adaptativos (mediana + clamp) vs baselines
- [ ] 23. Validar linguagem observacional nos alertas de baixa

**Fase 3:**

- [ ] 24. Cadastrar remédios pelo dashboard com doses padrão
- [ ] 25. Configurar campos pelo dashboard (incluindo clamps)
- [ ] 26. Validar todas as telas e link no resumo semanal
- [ ] 27. Checar taxa de conclusão — abaixo de 80% avaliar modo rápido

-----

## ❌ Decisões Descartadas

### APScheduler para agendamento

Descartado — risco de duplicata em restart e escalonamento. Railway Cron + endpoints internos é mais previsível e seguro.

### Webhook síncrono para voz

Descartado — risco de timeout do Whapi e processamento duplicado. HTTP 200 imediato + background task é obrigatório.

### Telegram Bot

Descartado — fricção comportamental de abrir outro app.
**Reconsiderar se** Whapi Sandbox não suportar botões.

### WhatsApp API Oficial (Meta + BSP)

Descartado — R$100-200/mês + templates obrigatórios.
**Reconsiderar se** escalar para outros usuários.

### Google Forms + link

Descartado — fragmentado, menos fluido.
**Fallback emergencial** se precisar de algo em 15 minutos.

### Supabase / Render / Fly.io

Descartados — Railway já pago resolve tudo.

### Baileys self-hosted

Descartado — overhead de manutenção contínua.

### Metabase

Descartado — container separado desnecessário.

### React + FastAPI agora

No roadmap — Streamlit entrega 80% do valor primeiro.

### Comandos de configuração no WhatsApp

Descartado — toda configuração vai para o dashboard.

### Marcador manual de período de baixa

Descartado — detecção automática é mais confiável.

### Simplificação prematura do check-in

Descartado — medir 30 dias antes de qualquer mudança.

### Multiusuário completo agora

Descartado — schema com user_id mas lógica de auth para quando escalar.

### Campos com escalas diferentes

Descartado para escalas subjetivas — 0-10 universal permite comparação direta.
**Exceção:** sono_horas (numérico real 0-16) e cigarros (contagem real 0-40) usam valores reais por serem medidas objetivas.

### Campo congelamentos na tabela streak

Descartado — contador simples sem referência temporal. Substituído por tabela `streak_congelamentos` com data real para validação por mês corrente.

-----

## Contexto

Projeto pessoal — Pedro. Conversa de briefing completa salva no Claude.ai.
Este README é o documento vivo. Atualize o checklist conforme executa.
