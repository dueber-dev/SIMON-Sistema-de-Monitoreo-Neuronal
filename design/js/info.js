// Ficha de cada indicador: qué mide, por qué está en el dashboard, cómo se calcula y su umbral.
// Es la justificación de indicadores que pide la rúbrica, visible donde se usa el dato.
import { config } from './store.js';
import { etaNominal, etaThreshold } from './physics.js';
import { fmt } from './charts.js';

const n = (x, d = 1) => fmt(x, d);

export const INFO = {
  p: () => ({
    title: 'Potencia',
    que: 'Energía por segundo que entrega el panel, en mW. La mide el INA219 (V × I).',
    porque: 'Es el resultado final del sistema: todo lo demás explica por qué sube o baja. Por eso es la métrica protagonista.',
    como: 'P = V · I, calculada por el INA219 en cada muestra (1 Hz).',
    umbral: `Por debajo de ${n(config.alertas.pMin, 0)} mW con el panel conectado se avisa «Sin potencia»: falta de luz o circuito abierto.`,
  }),
  v: () => ({
    title: 'Voltaje',
    que: 'Tensión en bornes del panel, en V, medida en el bus del INA219.',
    porque: 'Cae con la temperatura y con conexiones flojas. Si el voltaje baja y la irradiancia no, hay un problema eléctrico, no de luz.',
    como: 'Lectura directa del registro de bus del INA219 (resolución 4 mV).',
    umbral: `Referencia: Voc del panel = ${n(config.panel.voc)} V. Valores cercanos a 0 V indican circuito abierto.`,
  }),
  i: () => ({
    title: 'Corriente',
    que: 'Corriente que entrega el panel, en mA, medida en la resistencia shunt del INA219.',
    porque: 'Es casi proporcional a la irradiancia: permite comprobar que el LDR y el panel «ven» la misma luz.',
    como: 'Lectura del INA219 en modo 32 V · 1 A (resolución ≈ 0,1 mA). Bajo el mínimo configurado se considera 0.',
    umbral: `Isc del panel = ${n(config.panel.isc, 0)} mA: no debería superarse.`,
  }),
  t: () => ({
    title: 'Temperatura del panel',
    que: 'Temperatura de la cara posterior del panel, en °C, medida con un LM35.',
    porque: 'El calor reduce el voltaje y la eficiencia (≈ 0,4 % por cada °C sobre 25 °C). Separa una pérdida por calor de una por suciedad.',
    como: 'LM35: 10 mV/°C leídos por el ADC de 12 bits del ESP32 (≈ 0,08 °C por paso) más el ajuste de calibración.',
    umbral: `Alerta de temperatura alta sobre ${n(config.alertas.tMax, 0)} °C (franja amarilla en la gráfica).`,
  }),
  g: () => ({
    title: 'Irradiancia',
    que: 'Potencia de la luz solar por metro cuadrado (W/m²) que llega al panel.',
    porque: 'Es la entrada del sistema. Sin ella no se puede calcular la eficiencia ni saber si una baja de potencia es por falta de sol.',
    como: `Estimada desde el LDR: % de luz × ${n(config.sensores.ldrFactor, 0)} W/m² por cada 1 %. ${config.sensores.ldrCalibrado ? 'Factor calibrado por el equipo.' : 'El factor aún no está calibrado: el valor es aproximado.'}`,
    umbral: `Por debajo de ${n(config.alertas.mantGmin, 0)} W/m² no se evalúa el mantenimiento (poca luz da lecturas poco confiables).`,
  }),
  e: () => ({
    title: 'Eficiencia real',
    que: 'Qué fracción de la energía solar que llega al panel se convierte en electricidad.',
    porque: 'Es el indicador que el modelo de ML va a predecir y el que revela suciedad o degradación, porque no depende de cuánta luz haya.',
    como: `η = P / (G · A), con A = ${n(config.panel.area, 0)} cm². Se compara con la nominal: ${n(etaNominal())} % = P_nom / (1000 W/m² · A).`,
    umbral: `Umbral de mantenimiento: ${n(config.alertas.mant, 0)} % de la nominal = ${n(etaThreshold(), 2)} %.`,
  }),
  pr: () => ({
    title: 'Rendimiento vs nominal',
    que: 'Eficiencia real expresada como porcentaje de la eficiencia nominal del fabricante.',
    porque: 'Un solo número para el usuario: 100 % es el panel nuevo en condiciones de laboratorio. Es más fácil de leer que comparar dos eficiencias.',
    como: 'Rendimiento = η real / η nominal × 100, mediana de los últimos minutos con buena luz.',
    umbral: `La marca negra del anillo es el umbral de mantenimiento (${n(config.alertas.mant, 0)} %).`,
  }),
  mant: () => ({
    title: 'Alerta de mantenimiento',
    que: 'Avisa cuando el panel rinde menos de lo esperado de forma sostenida: suciedad, sombra parcial, conexión dañada o degradación.',
    porque: 'Es la decisión que el usuario final puede tomar con el dashboard: limpiar o revisar el panel.',
    como: `Mediana de η en los últimos ${n(config.alertas.mantMin, 0)} min, solo con irradiancia ≥ ${n(config.alertas.mantGmin, 0)} W/m², comparada con el umbral. Así una nube o el atardecer no generan falsas alarmas.`,
    umbral: `Revisar si η < ${n(etaThreshold(), 2)} % (${n(config.alertas.mant, 0)} % de ${n(etaNominal())} %). Configurable en Alertas.`,
  }),
  teorica: () => ({
    title: 'Potencia medida vs teórica',
    que: 'Lo que el panel debería entregar según su ficha técnica, comparado con lo que entrega.',
    porque: 'Contrasta la medición con el cálculo teórico. La diferencia son pérdidas (cableado, suciedad, error del LDR).',
    como: `P_teórica = P_nom · G/1000 · [1 + γ · (T − 25)], con P_nom = ${n(config.panel.nominal)} W y γ = ${n(config.panel.coefT, 2)} %/°C.`,
    umbral: 'Una brecha mayor al 25 % sostenida coincide con la alerta de mantenimiento.',
  }),
  energia: () => ({
    title: 'Energía generada',
    que: 'Energía acumulada desde que empezó la sesión, en Wh.',
    porque: 'Resume la sesión en un número comparable entre días.',
    como: 'Suma de P · Δt, con Δt = 1 s.',
  }),
  pg: () => ({
    title: 'Potencia vs irradiancia',
    que: 'Cada punto es un segundo: cuánta potencia hubo para cada nivel de luz.',
    porque: 'Si el panel está sano los puntos forman una curva estrecha. Puntos por debajo indican pérdidas.',
    como: 'Dispersión con ajuste cuadrático por mínimos cuadrados. R² cerca de 1 significa una relación consistente.',
  }),
  ml: () => ({
    title: 'Eficiencia predicha',
    que: 'Eficiencia que el modelo espera según la irradiancia y la temperatura.',
    porque: 'Si la real queda muy por debajo de la predicha, hay un problema que la física no explica.',
    como: 'Modelo de demostración (regresión polinómica). Se reemplazará por el modelo del equipo vía /api/predict.',
  }),
};
