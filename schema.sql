CREATE TABLE IF NOT EXISTS usuarios (
  id        SERIAL PRIMARY KEY,
  whatsapp  TEXT UNIQUE NOT NULL,
  nome      TEXT,
  criado_em TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS checkins (
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

CREATE TABLE IF NOT EXISTS remedios (
  id          SERIAL PRIMARY KEY,
  user_id     INT REFERENCES usuarios(id),
  nome        TEXT NOT NULL,
  dose        TEXT,
  dose_padrao NUMERIC DEFAULT 1,
  tipo        TEXT DEFAULT 'quantidade',
  ativo       BOOLEAN DEFAULT TRUE,
  criado_em   TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS checkin_remedios (
  id         SERIAL PRIMARY KEY,
  checkin_id INT REFERENCES checkins(id) ON DELETE CASCADE,
  remedio_id INT REFERENCES remedios(id),
  quantidade NUMERIC(3,1) NOT NULL,
  desvio     NUMERIC(3,1),
  criado_em  TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS campos_config (
  id          SERIAL PRIMARY KEY,
  user_id     INT REFERENCES usuarios(id),
  campo       TEXT NOT NULL,
  ativo       BOOLEAN DEFAULT TRUE,
  ordem       INT NOT NULL,
  padrao_atual TEXT,
  baseline    TEXT,
  padrao_min  TEXT,
  padrao_max  TEXT,
  UNIQUE(user_id, campo)
);

CREATE TABLE IF NOT EXISTS checkin_sessions (
  id                 SERIAL PRIMARY KEY,
  user_id            INT REFERENCES usuarios(id),
  data_referencia    DATE NOT NULL,
  passo_atual        INT DEFAULT 1,
  respostas_parciais JSONB DEFAULT '{}',
  status             TEXT DEFAULT 'em_andamento',
  retroativo_ontem   BOOLEAN DEFAULT FALSE,
  iniciado_em        TIMESTAMP DEFAULT NOW(),
  atualizado_em      TIMESTAMP DEFAULT NOW(),
  concluido_em       TIMESTAMP,
  duracao_segundos   INT,
  passo_abandono     INT,
  UNIQUE(user_id, data_referencia)
);

CREATE TABLE IF NOT EXISTS streak (
  id            SERIAL PRIMARY KEY,
  user_id       INT REFERENCES usuarios(id),
  streak_atual  INT DEFAULT 0,
  streak_maximo INT DEFAULT 0,
  ultimo_checkin DATE,
  atualizado_em TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS streak_congelamentos (
  id        SERIAL PRIMARY KEY,
  user_id   INT REFERENCES usuarios(id),
  data      DATE NOT NULL,
  criado_em TIMESTAMP DEFAULT NOW(),
  UNIQUE(user_id, data)
);

CREATE TABLE IF NOT EXISTS periodos_baixa (
  id            SERIAL PRIMARY KEY,
  user_id       INT REFERENCES usuarios(id),
  inicio        DATE,
  fim           DATE,
  duracao_dias  INT,
  gatilhos      TEXT[],
  habitos_saida TEXT[],
  score_medio   NUMERIC,
  dor_media     NUMERIC,
  criado_em     TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS event_dispatch_log (
  id              SERIAL PRIMARY KEY,
  user_id         INT REFERENCES usuarios(id),
  tipo_evento     TEXT NOT NULL,
  data_referencia DATE NOT NULL,
  scheduled_for   TIMESTAMP NOT NULL,
  sent_at         TIMESTAMP,
  status          TEXT DEFAULT 'pendente',
  idempotency_key TEXT UNIQUE NOT NULL,
  detalhe_erro    TEXT,
  criado_em       TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS erros (
  id        SERIAL PRIMARY KEY,
  user_id   INT,
  tipo      TEXT,
  detalhe   TEXT,
  criado_em TIMESTAMP DEFAULT NOW()
);

-- Índices
CREATE INDEX IF NOT EXISTS idx_checkins_user_data            ON checkins(user_id, data);
CREATE INDEX IF NOT EXISTS idx_checkins_data_range           ON checkins(user_id, data DESC);
CREATE INDEX IF NOT EXISTS idx_checkin_sessions_status       ON checkin_sessions(status, atualizado_em);
CREATE INDEX IF NOT EXISTS idx_checkin_remedios_checkin      ON checkin_remedios(checkin_id);
CREATE INDEX IF NOT EXISTS idx_checkin_remedios_remedio      ON checkin_remedios(remedio_id);
CREATE INDEX IF NOT EXISTS idx_periodos_baixa_user           ON periodos_baixa(user_id);
CREATE INDEX IF NOT EXISTS idx_event_dispatch_tipo           ON event_dispatch_log(tipo_evento, data_referencia);
CREATE INDEX IF NOT EXISTS idx_erros_tipo                    ON erros(tipo, criado_em);
CREATE INDEX IF NOT EXISTS idx_streak_congelamentos_user_data ON streak_congelamentos(user_id, data);
CREATE UNIQUE INDEX IF NOT EXISTS idx_streak_user ON streak(user_id);

-- Seed: usuário padrão
INSERT INTO usuarios (id, whatsapp, nome)
VALUES (1, '5511999999999', 'Pedro')
ON CONFLICT DO NOTHING;

-- Seed: remédios
INSERT INTO remedios (user_id, nome, dose, dose_padrao, tipo) VALUES
  (1, 'Zolpidem', '5mg', 3, 'quantidade'),
  (1, 'Rivotril', '0,5mg', 1, 'quantidade'),
  (1, 'Tramadol',  NULL, 1, 'binario')
ON CONFLICT DO NOTHING;

-- Seed: campos_config
INSERT INTO campos_config (user_id, campo, ativo, ordem, padrao_atual, baseline, padrao_min, padrao_max) VALUES
  (1, 'dor_fisica',             TRUE,  1,  '0',       '0',  '0',  '3'),
  (1, 'energia',                TRUE,  2,  '5',       '6',  '4',  NULL),
  (1, 'sono_horas',             TRUE,  3,  '7',       '7',  NULL, NULL),
  (1, 'sono_qualidade',         TRUE,  4,  '5',       '7',  '4',  NULL),
  (1, 'exercicio',              FALSE, 5,  NULL,      NULL, NULL, NULL),
  (1, 'saude_mental',           TRUE,  6,  '5',       '7',  '4',  NULL),
  (1, 'stress_trabalho',        TRUE,  7,  '0',       '2',  '0',  '5'),
  (1, 'stress_relacionamento',  TRUE,  8,  '0',       '2',  '0',  '5'),
  (1, 'alcool',                 TRUE,  9,  'nenhum',  NULL, NULL, NULL),
  (1, 'cigarros',               TRUE,  10, '2',       '2',  NULL, NULL),
  (1, 'desempenho_social',      TRUE,  11, '5',       '5',  NULL, NULL),
  (1, 'remedios',               TRUE,  12, NULL,      NULL, NULL, NULL),
  (1, 'nota',                   TRUE,  13, NULL,      NULL, NULL, NULL)
ON CONFLICT DO NOTHING;
