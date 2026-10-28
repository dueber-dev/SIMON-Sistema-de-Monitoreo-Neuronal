-- Base de datos D1 de SIMON. Aplicar con: npx wrangler d1 execute simon --remote --file schema.sql
CREATE TABLE IF NOT EXISTS sesiones (
  id     INTEGER PRIMARY KEY AUTOINCREMENT,
  clave  TEXT NOT NULL UNIQUE,   -- la genera el ESP32 en cada encendido
  inicio INTEGER NOT NULL,       -- ms desde 1970
  fin    INTEGER NOT NULL,       -- hora de la última lectura recibida
  n      INTEGER NOT NULL DEFAULT 0
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
