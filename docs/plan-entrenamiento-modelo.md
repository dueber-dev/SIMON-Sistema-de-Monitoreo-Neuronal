# Plan de recolección de datos y entrenamiento del modelo

Actualizado: 12 de noviembre de 2026. Todas las mediciones deben quedar listas el **sábado 28 de noviembre**. Del 30 de noviembre al 3 de diciembre se entrena el modelo y se escriben los resultados. El equipo sale el 4 de diciembre.

## Qué va a predecir el modelo

El modelo predice la **potencia que el panel debería entregar** (mW) a partir de la luz, la temperatura y la hora. La diferencia entre la potencia medida y la predicha es la señal de mantenimiento: si el panel entrega menos de lo esperado durante un rato con buena luz, está sucio, sombreado o tiene una falla.

- **Entradas:** luz de la LDR (%), temperatura del LM35 (°C), hora del día (como seno y coseno) y ángulo del panel (de la bitácora).
- **Salida:** potencia (mW).
- **No usar como entrada** la irradiancia estimada con la corriente del panel (G_panel). Sale de la misma corriente que se quiere predecir y el modelo "haría trampa".

## Ventanas de medición (3 a 5 h)

El mediodía solar en San Salvador a fines de noviembre es cerca de las 11:45, así que estas dos ventanas son casi un espejo una de la otra:

| Ventana | Horario | Qué aporta |
|---|---|---|
| **M** (mañana) | 8:00 a 12:00 | Luz subiendo, panel más fresco |
| **T** (mediodía y tarde) | 11:30 a 15:30 | El pico de luz y la bajada, con el panel más caliente |
| **Corta** | 10:00 a 13:00 | Mínimo útil cuando no hay más tiempo: incluye el pico |

Lo valioso de tener M y T es que dan la **misma luz con distinta temperatura** (por ejemplo, 600 W/m² a las 9:00 con el panel a 35 °C y a las 14:30 con el panel a 55 °C). Así el modelo puede separar el efecto del calor del de la luz. Por eso conviene que de cada condición haya al menos una sesión M y una T.

Programar cada sesión en la dashboard (Sesiones → Sesiones programadas) con un nombre que diga la condición, por ejemplo `S04 limpio despejado T`.

## Cupos por clima

No sabemos qué clima va a tocar cada día, así que el plan no es un calendario fijo: es una lista de **cupos por condición**. Cada sesión se clasifica por el clima que dominó y se va llenando su cupo. Si una condición ya está llena, ese día se usa para otra que falte.

Cómo clasificar el clima de una sesión (se ve en la curva de potencia de la dashboard):
- **Despejado:** sol directo más del 75 % del tiempo; la potencia sigue una curva suave.
- **Parcial:** nubes que pasan; la potencia sube y baja varias veces por hora.
- **Nublado:** casi sin sol directo; la potencia se queda baja y plana.

| Condición | Mínimo para un modelo decente | Ideal | Nota |
|---|---:|---:|---|
| Limpio · despejado | 3 | 5 | Al menos 1 M y 1 T. Es la línea base |
| Limpio · parcial | 2 | 3 | Le enseña al modelo cambios rápidos de luz |
| Limpio · nublado | 1 | 2 | Luz baja y difusa |
| Sucio · despejado | 2 | 3 | Dos niveles: polvo ligero y polvo fuerte |
| Sucio · parcial o nublado | 0 | 1 | Para ver si la suciedad se distingue con poca luz |
| Sombra parcial | 1 | 2 | Para no confundir sombra con suciedad |
| **Total de sesiones** | **9** | **16** | |

De esas sesiones, se guardan **2 para la prueba final** que el modelo no ve al entrenar: una limpia y despejada, y una sucia. Ya están incluidas en los números de arriba. Cuando se sepa cuáles serán, se ponen en la bitácora con "PRUEBA".

**Cuántas caben:** entre el 13 y el 28 de noviembre hay 16 días. Con una sesión por día entre semana y dos por día los sábados y domingos (M y T), salen hasta unas 20 sesiones. El mínimo de 9 cabe con margen y el ideal de 16 cabe si se mide casi todos los días.

### Qué medir según cómo amanezca

| Si amanece... | Hacer |
|---|---|
| Despejado | Si falta "limpio · despejado", medir limpio. Si ya está lleno, hacer una sesión pareada: 9:00 a 12:00 limpio y 12:00 a 15:00 sucio. Así la comparación tiene casi el mismo sol |
| Parcial | Llenar "limpio · parcial"; si está lleno, sombra parcial o sucio |
| Nublado | Llenar "limpio · nublado"; si está lleno, medir igual (nunca sobra) |
| Lluvia | No sacar el equipo. La caja no es impermeable |

### Cómo ensuciar el panel de forma repetible

- Polvo fino (talco, harina o tierra cernida) echado con un colador a 30 cm del panel.
- **Ligero:** que la celda todavía se vea con claridad. **Fuerte:** que se vea opaca.
- **Tapar la LDR mientras se echa el polvo.** Es la referencia de luz: si se ensucia junto con el panel, la caída de potencia no se nota.
- Foto del panel antes y después (la ESP32-CAM de Eduardo sirve para esto).
- Limpiar el panel al terminar y anotarlo.

## ¿Aguanta 6 a 7 horas? Calor y batería

### Calor sobre las piezas impresas

Supuestos: máxima de San Salvador a fines de noviembre de unos 31 °C, sol de mediodía de unos 1000 W/m² sobre el panel inclinado y poco viento (el peor caso).

| Pieza | Temperatura estimada en el peor momento | PETG (se ablanda a ~78 °C; deformación bajo carga desde ~70 °C) | PLA (se ablanda a ~55–60 °C) |
|---|---:|---|---|
| Panel (vidrio o PET) | 31 + 0.031 × 1000 ≈ **62 °C** | — | — |
| Marco que toca el panel | ≈ 60 °C | Aguanta, 10 °C de margen | **Se deforma** |
| Plástico azul al sol directo | 55 a 65 °C | Aguanta | **Se deforma** |
| Aire dentro de la caja | 45 a 55 °C | Aguanta | Al límite |

Conclusiones:
- **La duración no es lo que derrite el plástico: es la hora.** Una pieza pequeña de plástico llega a su temperatura final en 20 a 30 minutos al sol. Después de eso, 3 h o 7 h dan lo mismo. La pieza llega a lo más caliente entre las 11:30 y las 13:30, sin importar cuánto dure la sesión.
- **PETG aguanta**, con unos 10 °C de margen en el peor caso. Lo que puede ceder con el tiempo es la bisagra de fricción, porque está apretada con el tornillo de perilla. Revisar el ángulo en el transportador al terminar.
- **Si alguna pieza sigue siendo PLA** (el avance 3 dice Hyper PLA), esa sí se puede deformar al mediodía, dure lo que dure la sesión. Hay que reimprimirla en PETG antes de la ventana T.
- El ESP32 aguanta hasta 85 °C y el INA219 hasta 125 °C: no son el problema.
- **Lo delicado es el power bank.** Las baterías de litio no deberían pasar de 45 °C mientras se descargan, y al sol directo las pasan. Ponerlo a la sombra, por ejemplo debajo del panel.

### Batería

| Consumo | Corriente a 5 V |
|---|---:|
| ESP32 con Wi-Fi mandando por HTTPS cada 5 s | ≈ 120 mA (≈ 0.6 W) |
| ESP32 + ESP32-CAM en el mismo power bank | ≈ 300–350 mA |

Un power bank de 10 000 mAh entrega unos 6 000 mAh reales a 5 V (pierde por la conversión de 3.7 V a 5 V):

| Power bank | Solo ESP32 | ESP32 + cámara |
|---|---:|---:|
| 10 000 mAh | ≈ 50 h | ≈ 18 h |
| 5 000 mAh | ≈ 25 h | ≈ 9 h |

**No se descarga en 7 h, ni de lejos.** Lo que pasa es que el ESP32 solo consume tan poco que el power bank cree que no hay nada conectado y se apaga. Por eso se reinició hoy cada minuto (sesiones v15 a v19). Arreglos, del más simple al más complicado:
1. Un power bank con modo de carga baja (en muchos se activa con dos clics en el botón).
2. Conectar la ESP32-CAM al mismo power bank: con ~300 mA ya no se apaga.
3. Una resistencia de 47 Ω y 1 W en un puerto USB libre (unos 100 mA). Gasta energía, pero con lo que dura el power bank no importa.

**La batería de 9 V con reductor no conviene.** Una pila alcalina de 9 V tiene unos 2.5 a 3 Wh útiles con esta carga: alcanza para unas 4 h con el ESP32 solo y unas 2 h con la cámara. Es menos que una sola ventana T.

### Prueba de resistencia

El primer día despejado, hacer **una sola sesión larga de 8:30 a 15:00** (cuenta para el cupo "limpio · despejado"). A las 12:30, medir con el termómetro infrarrojo el marco, la caja y el power bank. Se corta la sesión si pasa alguna de estas:
- el plástico supera 70 °C;
- el power bank está demasiado caliente para tenerlo en la mano (más de ~50 °C);
- el ángulo del transportador se movió.

Si pasa la prueba, las ventanas largas quedan habilitadas. Si no, se queda con las de 3 a 5 h.

## Bitácora por sesión

Una fila por sesión en una hoja compartida. Sin esto los datos no sirven para la rúbrica (criterio 7) ni para saber qué sesión estaba sucia.

| Campo | Ejemplo |
|---|---|
| Sesión (id de la dashboard) | v27 |
| Fecha y ventana | 2026-11-14, T 11:30–15:30 |
| Clima dominante | despejado / parcial / nublado |
| Estado del panel | limpio / polvo ligero / polvo fuerte / sombra 20 % |
| Inclinación (transportador) y orientación | 30°, sur |
| Lecturas de referencia | V e I con el multímetro, T con el termómetro IR, al inicio, a la mitad y al final |
| Incidencias | se reinició a las 12:10, se limpió la LDR |
| Uso | entrenamiento / PRUEBA |

## Antes de la primera sesión

1. **Revisar que el panel esté conectado.** La sesión v20 de hoy marcó 0.02 V y 0.4 mA: potencia cero durante 20 minutos. Antes de programar, ver en la vista En vivo que la potencia suba al poner el panel al sol.
2. Arreglar la alimentación (sección de batería).
3. Pegar el LM35 a la parte trasera del panel con pasta térmica o cinta de aluminio. Si mide el aire, el efecto de la temperatura en el modelo sale mal.
4. Revisar si la LDR se satura al sol: si marca más de ~85 % de forma sostenida, cambiar R4 a 1 kΩ **antes** de empezar. Cambiarla a la mitad deja dos conjuntos de datos que no se pueden comparar.
5. No mover el ángulo del panel en medio de una sesión. Si se cambia, programar otra.
6. La curva I-V y la validación con el multímetro se hacen **antes de que empiece la ventana**: la curva I-V necesita desconectar el panel de la PCB. Una vez en un día despejado y otra en uno nublado.

## Preparación de los datos

1. Descargar el CSV de cada sesión desde la dashboard.
2. Promediar a **1 minuto** (quita ruido y reduce filas que se parecen entre sí). Una sesión de 4 h queda en unas 240 filas.
3. Quitar los minutos con potencia casi cero por desconexión y marcar los minutos con la LDR saturada.
4. Agregar las columnas de la bitácora: `clima`, `estado_panel`, `angulo`, `ventana`.

## Entrenamiento y evaluación (30 de noviembre al 3 de diciembre)

- **Separar por sesiones, nunca por filas al azar.** Si se mezclan filas de una misma sesión entre entrenamiento y prueba, el modelo parece perfecto y no lo es. Usar validación cruzada dejando una sesión fuera, y las 2 sesiones de PRUEBA guardadas hasta el final.
- **Comparar contra una referencia física simple:** P = k · G · (1 + γ · (T − 25)), con k y γ ajustados. Si el modelo de ML no le gana a esta fórmula, no aporta.
- **Modelos a probar**, de simple a complejo: regresión lineal con G, G² y T; random forest o gradient boosting; una red neuronal pequeña (MLP de 2 capas), que es lo que el nombre del proyecto promete.
- **Métricas:** MAE y RMSE en mW, R², y error porcentual solo con potencia mayor a 50 mW (con potencias chiquitas el porcentaje se dispara).
- **Detector de suciedad:** con el residuo (medida − predicción) en ventanas de 10 min, elegir el umbral con las sesiones limpias y medir cuántos minutos sucios detecta en las sucias.

## Calendario

| Fechas | Trabajo |
|---|---|
| Vie 13 – dom 15 nov | Puntos de "Antes de la primera sesión". Prueba de resistencia el primer día despejado. Curva I-V y validación en el primer día despejado y en el primer día nublado |
| Lun 16 – vie 27 nov | Llenar cupos: una sesión por día entre semana, M y T los sábados y domingos. Revisar la tabla de cupos cada noche |
| Sáb 28 nov | Último día de medición: rellenar los cupos que falten |
| Lun 30 nov – jue 3 dic | Preparar datos, entrenar, evaluar y escribir resultados |
