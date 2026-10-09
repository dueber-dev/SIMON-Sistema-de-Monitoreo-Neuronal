# DISEÑO DEL DASHBOARD SIMON: por qué mostramos lo que mostramos

Este documento explica para quién diseñamos el dashboard, qué indicadores elegimos y por qué, y cómo funcionan las alertas. Está pensado como respaldo del criterio *Diseño del dashboard* de la rúbrica y como guía para la presentación.

## 1. Usuario final

Cuando empezamos a rediseñar el prototipo en Streamlit nos dimos cuenta de que mostraba los datos, pero no ayudaba a tomar ninguna decisión. Por eso lo primero fue definir quién lo usa y qué necesita saber:

1. **Quien opera el panel** (en nuestro caso, el equipo durante las pruebas de laboratorio). Necesita saber de un vistazo si el panel está generando, si algo está fuera de rango y si hay que limpiarlo o revisarlo.
2. **Quien analiza los datos** (el equipo que entrena el modelo de ML). Necesita los históricos, las unidades físicas correctas y poder exportar cada sesión en CSV.
3. **Quien evalúa el proyecto** (docente o jurado). Necesita entender cada número sin que se lo expliquemos, por eso cada indicador tiene un botón **i** con su definición.

Tuvimos en cuenta además una condición práctica: la laptop se conecta a la red Wi‑Fi del ESP32, que no tiene internet, por lo que todo el dashboard funciona sin conexión externa. También se usa en proyector, así que la jerarquía visual tenía que leerse a distancia.

## 2. Decisiones de diseño

- **Una métrica protagonista.** La potencia es el resultado final del sistema y todo lo demás explica por qué sube o baja. Por eso ocupa la tarjeta principal y la gráfica más grande.
- **Un color fijo por variable**, siempre el mismo en todas las vistas: potencia en naranja, voltaje en azul, corriente en aqua, temperatura en violeta, irradiancia en ámbar y eficiencia en magenta. La paleta la validamos con un script de contraste y simulación de daltonismo (la temperatura iba en rojo, sin embargo, no se distinguía del naranja de la potencia, así que la cambiamos).
- **Las alertas nunca dependen solo del color.** Cada estado lleva ícono y texto ("Revisar o limpiar el panel"), y los umbrales se dibujan como una línea con su valor escrito y una franja suave en la zona de alerta.
- **Un solo eje por gráfica.** El prototipo ponía voltaje y corriente juntos con escalas distintas, lo que sugiere relaciones que no existen. Ahora cada variable tiene su gráfica.
- **Unidades físicas.** La irradiancia se muestra en W/m² (estimada a partir del LDR calibrado) y el porcentaje crudo del LDR queda como dato secundario.

## 3. Indicadores y su justificación

| Indicador | Unidad | Cómo se obtiene | Por qué está en el dashboard |
|---|---|---|---|
| Potencia | mW | INA219 (V · I) | Resultado final del sistema |
| Voltaje | V | Bus del INA219 | Detecta conexiones flojas y el efecto del calor |
| Corriente | mA | Shunt del INA219 | Es casi proporcional a la luz: valida que el LDR y el panel vean lo mismo |
| Temperatura | °C | LM35 (10 mV/°C, ADC de 12 bits del ESP32) | El calor baja la eficiencia (≈ 0,4 % por °C sobre 25 °C) |
| Irradiancia | W/m² | % del LDR × factor de calibración | Es la entrada del sistema: sin ella no hay eficiencia |
| Eficiencia real | % | η = P / (G · A) | No depende de cuánta luz haya, así que revela suciedad o degradación |
| Rendimiento vs nominal | % | η real / η nominal | Un solo número: 100 % es el panel nuevo en laboratorio |
| Potencia teórica | mW | P_nom · G/1000 · [1 + γ(T − 25)] | Contrasta la medición con el cálculo de la ficha técnica |
| Energía | Wh | Σ P · Δt | Resume una sesión para compararla con otras |

## 4. Eficiencia real vs nominal

La eficiencia nominal sale de la ficha técnica, en condiciones estándar (1000 W/m², 25 °C):

η nominal = P_nom / (1000 W/m² · A)

La eficiencia real se calcula con cada muestra:

η real = P / (G · A)

Ambas se muestran juntas en la tarjeta de eficiencia, en la gráfica "Eficiencia real vs nominal" y en el anillo de rendimiento. Básicamente, la distancia entre las dos líneas es lo que el panel está perdiendo.

## 5. Umbral de alerta de mantenimiento

La primera idea fue avisar apenas la eficiencia bajara de un valor fijo. Sin embargo, al probarla con el simulador nos dimos cuenta de que cualquier nube o el atardecer disparaban la alarma, por lo que la regla final tiene tres condiciones:

1. Solo se evalúa con **irradiancia ≥ 300 W/m²**, porque con poca luz las lecturas son poco confiables.
2. Se usa la **mediana de los últimos 5 minutos**, no el valor instantáneo, para que solo cuente una pérdida sostenida.
3. Se compara contra el **75 % de la eficiencia nominal**.

Si la mediana queda por debajo, el estado del sistema muestra "Revisar o limpiar el panel", la franja amarilla de la gráfica de eficiencia lo hace visible y el anillo de rendimiento queda por debajo de su marca. Los tres valores son configurables en *Configuración → Alertas*. La alerta de temperatura es independiente: el calor baja la eficiencia, pero no es algo que se arregle limpiando el panel.

## 6. Históricos

Cada sesión es un CSV con el mismo formato que genera el ESP32. En **Sesiones** se ven todas en un calendario, se pueden comparar dos de ellas y descargar. En **Análisis** cualquier sesión muestra su resumen, la serie de cada variable con sus umbrales, la relación potencia-irradiancia, el efecto de la temperatura y la tabla de datos. Las sesiones que cruzaron el umbral de mantenimiento aparecen marcadas con "Revisar panel".

## 7. Escenarios de prueba

En *Configuración → Conexión*, con el simulador activo, se puede cambiar el escenario en vivo:

| Escenario | Qué cambia | Qué debería mostrar el dashboard |
|---|---|---|
| Normal | Sol con nubes pasajeras | Todo en rango, rendimiento ≈ 85 % |
| Nublado | Irradiancia ≈ 40 % | Menos potencia, pero eficiencia estable y sin alerta de mantenimiento |
| Panel sucio | 30 % menos de luz útil | Eficiencia bajo el umbral y alerta "Revisar o limpiar el panel" en ≈ 3 a 4 min |
| Calor extremo | +20 °C | Alerta de temperatura y caída de eficiencia, sin alerta de mantenimiento |

El cambio es gradual (≈ 1 minuto), como pasaría en la realidad. Para una demostración más rápida se puede bajar la ventana de mantenimiento a 1 minuto.

## 8. Limitaciones y pendientes

- **Datos del panel de ejemplo.** La potencia nominal (1 W), el área (110 cm²) y el Voc (6 V) son valores de ejemplo hasta que tengamos la ficha técnica del panel real. La eficiencia depende directamente de ellos, por eso el dashboard los marca como "Datos de ejemplo" hasta que se verifiquen.
- **LDR sin calibrar.** El factor de 10 W/m² por cada 1 % es aproximado. Para calibrarlo podemos tomar una lectura en un día despejado al mediodía (≈ 1000 W/m²) o compararlo contra un piranómetro.
- **Modelo de ML de demostración.** La vista de predicción usa una regresión polinómica entrenada en el navegador para mostrar cómo se verá el modelo real.
- **Datos simulados.** La maqueta usa un simulador con la misma trama del ESP32. El siguiente paso es el backend FastAPI que conecta el dashboard con el hardware.

## 9. Relación con la rúbrica

| Requisito de la rúbrica | Dónde se cumple |
|---|---|
| V, I, potencia, temperatura, irradiancia y eficiencia | Tarjetas de En vivo, Análisis y tabla de datos |
| Organización clara y unidades correctas | Jerarquía por métrica protagonista, un color por variable, unidades SI en todas las vistas |
| Eficiencia real vs nominal | Tarjeta de eficiencia, gráfica comparativa y anillo de rendimiento |
| Históricos | Vistas Sesiones y Análisis |
| Umbral de alerta de mantenimiento visualizado | Línea y franja en la gráfica de eficiencia, marca en el anillo, estado del sistema |
| Diseño pensado en el usuario final | Sección 1 y decisiones de la sección 2 |
| Indicadores justificados | Sección 3 y botón **i** de cada indicador |

En resumen, el dashboard pasó de mostrar números a decir qué hacer con ellos, y ese cambio nos obligó a entender mejor la física del panel que estamos midiendo.
