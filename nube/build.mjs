// Copia la dashboard (design/) a public/simon/ para que el Worker la sirva en /simon/.
import { cpSync, rmSync } from 'node:fs';

const destino = new URL('./public/simon/', import.meta.url);
rmSync(new URL('./public/', import.meta.url), { recursive: true, force: true });
cpSync(new URL('../design/', import.meta.url), destino, { recursive: true });
console.log('Dashboard copiada a nube/public/simon/');
