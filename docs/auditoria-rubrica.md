# Auditoría del avance SIMON

Referencia inicial: commit `84b5d766fd87937e3d5d82f0e56dd07406415272`. Se revisaron firmware, cliente TCP, Streamlit, la maqueta web y su documentación. El contraste documental incluyó el informe v9, dos imágenes de la rúbrica y una fotografía del montaje. No se recibieron CSV experimentales, bitácora de instrumentos ni firmware de cámara.

## Dictamen y calificación estimada

El diseño del dashboard reúne los requisitos visuales de sobresaliente. La evidencia del circuito todavía no permite sostener esa calificación en todos los criterios. Una mejora editorial no sustituye la validación de compatibilidad eléctrica y de las cuatro magnitudes físicas.

Se supone una conversión proporcional de niveles: nota sobre 10 = Σ(peso × nivel/4)/10. La rúbrica suministrada define pesos y niveles, pero no explicita su conversión a una escala de 10. La calificación final y la defensa oral corresponden a la docente.

| Criterio | Peso | Nivel propuesto con documento revisado | Aporte sobre 10 | Evidencia y límite |
|---|---:|---:|---:|---|
| Microcontrolador, acondicionamiento y alimentación | 25 % | 2/4 | 1.250 | ESP32 e INA219 definidos y cálculos disponibles; LM35 descrito a 3.3 V, calibración y carga física sin verificar. El esquema a 5 V es una propuesta pendiente. |
| Diseño del dashboard | 30 % | 4/4 | 3.000 | Seis indicadores, unidades, eficiencia nominal, históricos, umbral visual y usuario final. La rúbrica admite boceto o prototipo; se acredita diseño, no adquisición real. |
| Simulación o pruebas físicas integradas | 30 % | 2/4 | 1.500 | Ensayos V/I relatados y contrastados; sin datos primarios ni validación de temperatura/irradiancia. El simulador JS no simula el circuito de adquisición. |
| Documentación y presentación | 15 % | 3/4 provisional | 1.125 | Informe corregido, esquema propuesto, materiales, captura y referencias; falta cerrar evidencias y observar la participación y dominio de todos los integrantes. |
| **Total estimado** | **100 %** | | **6.875/10 ≈ 6.9** | Estimación conservadora de las evidencias disponibles. |

Para el paquete original se estima aproximadamente 6.5/10 (niveles 2, 4, 2, 2), debido a contradicciones entre implementación y texto. Con compatibilidad física y configuración verificadas, el primer criterio podría subir a 3 y el total a 7.5. Con esa mejora y ensayos completos de varios escenarios al nivel 4, el total sería 9.0. Un 10 requiere nivel 4 en todos los criterios, incluida evidencia completa y defensa del equipo. No se garantiza ninguna nota.

## Hallazgos y correcciones verificables

| Hallazgo | Ubicación inicial | Corrección o decisión |
|---|---|---|
| El modo ESP32 cambiaba el texto a conectado y cero pérdidas, aunque todos los datos seguían saliendo de `sim.js`. | `store.js`, `app.js`, `views/live.js`, `views/configuracion.js` | La maqueta fuerza el origen simulado, corrige preferencias persistidas y bloquea la selección de hardware pendiente. |
| La ventana de mantenimiento interpretaba segundos como número de muestras y aceptaba solo 60 muestras para una ventana de 300 s. | `physics.js`, función `maintenance` | Se filtra por timestamps; se exige la extensión del periodo y 90 % de segundos distintos con buena luz. Una muestra final sin suficiente luz impide evaluar. |
| Para un número par de muestras se tomaba el elemento superior como mediana. | `physics.js` | Se promedian los dos elementos centrales. |
| Las métricas de ML se calculan sobre el mismo conjunto usado para entrenar. | `ml.js`, `views/prediccion.js` | Se identifica el resultado como ajuste sobre entrenamiento sintético, sin validación independiente. No se presenta como modelo neuronal validado. |
| Se explicaba la tensión de bus como tensión exacta del panel y el circuito abierto como voltaje cercano a cero. | `info.js` | Se aclara VIN− respecto de GND y que un circuito abierto puede conservar Voc con corriente nula. |
| Se afirmaba que la eficiencia no dependía de luz y que el calor no podía causar alerta de mantenimiento. | `info.js`, `docs/justificacion-dashboard.md` | Se declaran efectos de temperatura, carga y calibración; el umbral actual no compensa temperatura. |
| Se sugería calibrar irradiancia suponiendo 1000 W/m² en un día despejado. | Configuración y justificación | Se requiere referencia radiométrica simultánea; se elimina esa equivalencia como método de calibración. |
| El receptor aceptaba valores no finitos, podía bloquearse sin datos y no separaba reinicios del reloj. | `codigo_esp32_prueba2.py` | Se validan seis campos finitos, se limita la trama a 512 bytes, se añade timeout de 10 s y se abre otro CSV al retroceder el tiempo. Los valores válidos conservan su texto original. |
| El informe declaraba INA219 16 V/400 mA, filtro 0.1 mA y promedio de 30 lecturas. | Informe v9 frente a `.ino` | El Word se alinea con 32 V/1 A, filtro `< 0.01 mA` y una lectura por canal. No se cambió el firmware ni se afirmó que una propuesta estuviera desplegada. |
| Potencias de la tabla de exteriores inconsistentes con V × I. | Informe v9, tabla de mediciones | Se conservan V e I, se recalcula P y se preservan las potencias originales como antecedente. No se inventaron muestras. |
| El informe daba por integrada la maqueta, la cámara, aislamiento entre USB y causas de fallos de alimentación. | Informe v9 | Se distingue implementación verificable, ampliación prevista e hipótesis sin mediciones suficientes. |

## Pruebas de software

Comando reproducible, con Node.js 22.7 o posterior:

```sh
node --test tests/physics.test.mjs
python -m unittest discover -s tests -p 'test_*.py'
```

Ocho pruebas aprobadas: unidades de eficiencia y potencia teórica; rechazo de un minuto como cinco; baja eficiencia sostenida y estado normal; muestras escasas/duplicadas; oscuridad actual; mediana par; historial y entradas inválidas; imposibilidad de declarar hardware conectado desde la configuración.

Seis pruebas adicionales del receptor Python aprobadas: conservación de precisión y signo, rechazo de datos inválidos, fragmentación/agrupación TCP, límite de trama, separación de reinicios con continuidad al reconectar y rechazo de registros sin crear archivos vacíos. Se usa un socket de prueba controlado; no el dispositivo físico. Total: 14 pruebas aprobadas.

En navegador se verificaron las cinco vistas (En vivo, Análisis, Predicción ML, Sesiones y Configuración), sin errores de JavaScript. También se reprodujo una preferencia antigua con `modo: esp32`: la página permaneció identificada como simulador y el botón de hardware quedó deshabilitado. Esta revisión no equivale a probar cada control ni a certificar accesibilidad.

Las pruebas son exclusivamente de software. No se compiló ni flasheó el firmware, no se conectó el ESP32 físico y no se verificó la cadena hardware a CSV. El Word se comprobó visualmente página por página mediante renderizado en Microsoft Word; el renderizador LibreOffice del paquete no estaba disponible en este entorno Windows.

## Pendientes técnicos que requieren otra etapa

1. **Canal térmico:** comprobar modelo y pinout del LM35, corregir alimentación según especificación, medir salida, fijar atenuación y calibrar ADC contra referencia. Confirmar contacto térmico con el panel.
2. **Canal de luz:** medir extremos del divisor y posible saturación; calibrar varios niveles contra piranómetro o celda de referencia calibrada en el mismo plano. Un luxómetro mide una magnitud fotométrica y no proporciona directamente W/m² sin un modelo validado.
3. **Circuito:** medir carga real y verificar resistores de al menos 0.5 W, shunt, continuidad de GND y puntos donde se conectan las puntas del tester. Documentar tensiones de alimentación bajo Wi-Fi.
4. **Firmware:** fijar versiones de ESP32 y librerías, documentar atenuación y conversión ADC. El filtro actual borra corrientes negativas, lo que puede ocultar un cableado invertido. Evaluar preservar signo y caracterizar offset antes de elegir umbral; la configuración de la maqueta no modifica el firmware.
5. **Registro:** probar la nueva validación, timeout y separación de reinicios contra el ESP32 real. TCP no recupera muestras durante una desconexión. Un reinicio cuyo reloj ya supere la última lectura al reconectar no puede identificarse inequívocamente sin un identificador de arranque en la trama; esa extensión del protocolo queda pendiente.
6. **Streamlit:** separar ejes de V y mA, mostrar luz relativa como tal, manejar filas parciales o inválidas y eliminar el argumento de precisión no calibrada. Este prototipo se distingue del diseño web evaluado.
7. **Maqueta:** varios controles son preparatorios (offset LM35, rango INA, corriente mínima, reconexión, timeout y sonido). No se presentan como ajustes efectivos del hardware. La energía integra un segundo por muestra y puede subestimar tiempo transcurrido si el navegador reduce la frecuencia de los temporizadores. Validar configuración positiva y rangos antes de una conexión física.
8. **Predicción y alertas:** separar entrenamiento y evaluación por sesiones; comparar con una referencia simple; distinguir calor y carga de suciedad. Las medias de sesión no sustituyen una detección temporal de eventos.
9. **Ensayos:** conservar CSV original, fecha completa, duración, posición del panel, carga e instrumentos. Registrar V, I, T y G en varias condiciones y repetir; reportar incertidumbre y criterios de aceptación definidos antes del ensayo.
10. **Cámara, autonomía y costos:** verificar solo si se incluyen en el alcance; no afirmar que existen firmware, aislamiento USB, duración medida o gastos comprobados sin sus respaldos.

## Lecturas reportadas y trazabilidad

Las seis filas del informe dan errores de voltaje entre +2.35 % y +2.71 %, y exactamente −2.20 % de corriente. Esa proporcionalidad debe contrastarse con la bitácora, sin concluir por ello que los datos son falsos. El producto de las lecturas arroja diferencias de potencia de aproximadamente +0.10 % a +0.45 % por compensación de signos; no es una certificación metrológica.

La fotografía acredita el montaje y su alimentación USB, pero no lecturas, rangos ni desempeño. Si no se conservan los registros originales, corresponde repetir el ensayo y documentarlo con su fecha real, sin reconstruir fotografías o CSV como si provinieran de la sesión anterior.

## Fuentes técnicas

- [Texas Instruments LM35](https://www.ti.com/lit/ds/symlink/lm35.pdf): alimentación mínima y transferencia térmica.
- [Texas Instruments INA219](https://www.ti.com/lit/ds/symlink/ina219.pdf): límites de bus, medición y resolución.
- [Adafruit INA219](https://github.com/adafruit/Adafruit_INA219/blob/master/Adafruit_INA219.cpp): escalas del modo 32 V/1 A. Debe fijarse la versión realmente instalada en el equipo.
- [Espressif ADC](https://docs.espressif.com/projects/arduino-esp32/en/latest/api/adc.html): conversión, calibración y atenuación del ADC.
