-- Sesiones programadas. Aplicar una sola vez a la base que ya existe:
-- npx wrangler@4 d1 execute simon --remote --file migraciones/0001_sesiones_programadas.sql
ALTER TABLE sesiones ADD COLUMN nombre TEXT;
ALTER TABLE sesiones ADD COLUMN plan_inicio INTEGER;
ALTER TABLE sesiones ADD COLUMN plan_fin INTEGER;
CREATE INDEX IF NOT EXISTS sesiones_plan ON sesiones (plan_inicio, plan_fin);
