-- Base de datos D1 de SIMON. Aplicar con: npx wrangler d1 execute simon --remote --file schema.sql
CREATE TABLE IF NOT EXISTS sesiones (
  id     INTEGER PRIMARY KEY AUTOINCREMENT,
  clave  TEXT NOT NULL UNIQUE,   -- la genera el ESP32 en cada encendido; «plan-…» en las programadas
  inicio INTEGER NOT NULL,       -- ms desde 1970
  fin    INTEGER NOT NULL,       -- hora de la última lectura recibida
  n      INTEGER NOT NULL DEFAULT 0,
  nombre      TEXT,              -- solo programadas: nombre opcional
  plan_inicio INTEGER,           -- solo programadas: todo lo que llegue en [plan_inicio, plan_fin)
  plan_fin    INTEGER            --   va a esta sesión aunque el ESP32 se reinicie
);

CREATE TABLE IF NOT EXISTS lecturas (
  id     INTEGER PRIMARY KEY AUTOINCREMENT,
  sesion INTEGER NOT NULL REFERENCES sesiones(id),
  ts     INTEGER NOT NULL,       -- ms desde 1970
  seg    INTEGER NOT NULL,       -- segundos desde que arrancó el ESP32
  v      REAL NOT NULL,          -- V
  i      REAL NOT NULL,          -- mA
  p      REAL NOT NULL,          -- mW
  t      REAL NOT NULL,          -- °C
  luz    REAL NOT NULL           -- % del LDR
);

CREATE INDEX IF NOT EXISTS lecturas_sesion ON lecturas (sesion, id);

CREATE TABLE IF NOT EXISTS fotos (
  id     INTEGER PRIMARY KEY AUTOINCREMENT,
  ts     INTEGER NOT NULL,       -- ms desde 1970
  b64    TEXT NOT NULL           -- imagen JPEG codificada en base64
);

CREATE INDEX IF NOT EXISTS sesiones_plan ON sesiones (plan_inicio, plan_fin);
