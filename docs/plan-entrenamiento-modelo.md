# Plan de recolección de datos y entrenamiento del modelo

Fecha: 12 de noviembre de 2026.

## Qué va a predecir el modelo

El modelo predice la **potencia que el panel debería entregar** (mW) a partir de la luz, la temperatura y la hora. La diferencia entre la potencia medida y la predicha es la señal de mantenimiento: si el panel entrega menos de lo esperado durante un rato con buena luz, está sucio, sombreado o tiene una falla.

- **Entradas:** luz de la LDR (%), temperatura del LM35 (°C), hora del día (como seno y coseno) y ángulo del panel (de la bitácora).
- **Salida:** potencia (mW).
- **No usar como entrada** la irradiancia estimada con la corriente del panel (G_panel). Sale de la misma corriente que se quiere predecir y el modelo "haría trampa".

## Cuántos datos hacen falta

A 1 Hz, una ventana de 7 h da unas 25 000 filas por día. El número de filas no es el problema: cada segundo se parece mucho al anterior. Lo que cuenta es **cuántos días distintos** hay, porque el modelo se evalúa con días que nunca vio.

| Bloque | Días | Para qué |
|---|---:|---|
| Panel limpio, días variados | 8 | Línea base: cómo responde el panel sano a la luz y al calor |
| Panel con suciedad controlada | 3 | Enseñar cómo se ve una caída de eficiencia (polvo, harina fina o una tira de cinta que tape el 10–20 %) |
| Sombra parcial | 1 | Separar sombra de suciedad |
| Prueba final, sin tocar | 2 | Días que solo se usan para la nota final del modelo (1 limpio, 1 sucio) |
| **Total** | **14** | **Unos 3 semanas de calendario contando días perdidos por lluvia o fallas** |

Mínimo para presentar algo defendible: **6 días** (4 limpio, 1 sucio, 1 de prueba). Con menos de eso el modelo memoriza los días y no generaliza.

## Ventana diaria

- **Ventana programada: 8:30 a 15:30** todos los días de medición. Así entra la luz baja de la mañana, el pico del mediodía y la bajada de la tarde, que es justo el rango que el modelo necesita ver.
- Si no se puede todo el día: **10:00 a 14:00** como mínimo (es la ventana de la caracterización I-V del avance 3).
- Los días de suciedad, dividir en dos sesiones programadas el mismo día: 9:00–11:30 limpio y 12:00–14:30 sucio. Así se compara con la misma luz y el mismo calor.

Cada día se programa en la dashboard (Sesiones → Sesiones programadas) con un nombre que diga la condición, por ejemplo `D03 limpio despejado 30°`.

## Bitácora por sesión

Una fila por sesión en una hoja compartida. Sin esto los datos no sirven para la rúbrica (criterio 7) ni para etiquetar la suciedad.

| Campo | Ejemplo |
|---|---|
| Sesión (id de la dashboard) | v27 |
| Fecha y ventana | 2026-11-14, 8:30–15:30 |
| Estado del panel | limpio / polvo ligero / harina 10 % / sombra |
| Inclinación (transportador) y orientación | 30°, sur |
| Clima | despejado / nubes pasajeras / nublado |
| Lecturas de referencia | V y I con multímetro, T con termómetro IR, a las 10:00, 12:00 y 14:00 |
| Incidencias | se reinició a las 11:40, se limpió la LDR |

## Preparación de los datos

1. Descargar el CSV de cada sesión desde la dashboard.
2. Promediar a **1 minuto** (quita ruido y reduce filas que se parecen entre sí).
3. Quitar minutos con potencia casi cero por noche o desconexión, y marcar los minutos donde la LDR está saturada (más de ~85 %).
4. Agregar las columnas de la bitácora: `estado_panel`, `angulo`, `clima`.

## Entrenamiento y evaluación

- **División por días, nunca por filas al azar.** Si se mezclan filas del mismo día entre entrenamiento y prueba, el modelo parece perfecto y no lo es. Usar validación cruzada dejando un día fuera y los 2 días de prueba guardados hasta el final.
- **Comparar contra una referencia física simple:** P = k · G · (1 + γ · (T − 25)), con k y γ ajustados. Si el modelo de ML no le gana a esta fórmula, no aporta.
- **Modelos a probar**, de simple a complejo: regresión lineal con G, G² y T; random forest o gradient boosting; una red neuronal pequeña (MLP de 2 capas), que es lo que el nombre del proyecto promete.
- **Métricas:** MAE y RMSE en mW, R², y error porcentual solo con potencia mayor a 50 mW (con potencias chiquitas el porcentaje explota).
- **Detector de suciedad:** con el residuo (medida − predicción) en ventanas de 10 min, elegir el umbral con los días limpios y medir cuántos minutos sucios detecta en los días sucios (precisión y exhaustividad).

## Antes de empezar a medir

Estos puntos afectan la calidad de todo el conjunto de datos, así que conviene resolverlos antes del día 1:

1. **Alimentación:** el power bank apaga el ESP32. La sesión programada evita que los datos queden partidos, pero no recupera los minutos que estuvo apagado.
2. **LM35 pegado a la parte trasera del panel** con pasta térmica o cinta de aluminio. Si mide el aire, el efecto de la temperatura en el modelo sale mal.
3. **Revisar si la LDR se satura al sol.** Si marca más de ~85 % de forma sostenida, cambiar R4 a 1 kΩ antes de recolectar. Cambiarla a mitad de la recolección deja dos conjuntos de datos que no se pueden comparar.
4. No mover el panel de ángulo en medio de una sesión. Si se cambia, programar otra sesión.

## Calendario propuesto

| Semana | Trabajo |
|---|---|
| 13–16 nov | Resolver los 4 puntos de arriba. Curva I-V en sol pleno y nublado. Validación contra multímetro y termómetro. Primeros 2 días limpios |
| 17–23 nov | 6 días limpios más y 2 días con suciedad |
| 24–30 nov | 1 día con sombra y 1 de suciedad más, 2 días de prueba. Entrenar, evaluar, escribir resultados |
