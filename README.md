# Mi Clima Rosario

Aplicación pública de información meteorológica para **Rosario, Colonia (Uruguay)**:
https://super18rosario.github.io/mi-clima-rosario/

## Prioridades de la pantalla

1. Mostrar primero una temperatura observada reciente: INIA La Estanzuela si está disponible, si no **INUMET Cardona G4** y finalmente **INUMET Colonia G3**. Si ambas faltan, indicar claramente una estimación Open-Meteo. Mostrar siempre estación, hora y que ninguna es una medición en Rosario. Pronóstico para hoy/mañana.
2. Comparación de modelos, historial de aciertos, rayos, satélites y accesos en paneles desplegables.
3. Mostrar un aviso de pasos encima del tiempo **solo** si existe confirmación reciente (máximo 45 minutos) de subida, riesgo o corte. **Ausencia de aviso no significa paso seguro**.

## Datos que funcionan

- **Estación propia Rosario SC (IROSAR145)**, vía API oficial de Weather Underground cada 10 minutos (cron-job.org + GitHub Actions). Tiene prioridad mientras su lectura no supere 30 minutos. `rosariosc.yml` solo guarda datos en el repositorio (no despliega Pages); la página lee la lectura más reciente entre GitHub Pages y `raw.githubusercontent.com`.
- **Histórico Rosario SC** en `data/rosariosc_history/AAAA-MM.csv` (UTC; temperatura y, si la estación las publica, humedad, rocío, presión, lluvia y viento). `scripts/backfill_rosariosc_history.py` recupera lecturas perdidas desde el historial git.
- **Verificación contra Rosario SC**: `scripts/verify_rosariosc.py` compara el pronóstico del día anterior (máxima, mínima y temperatura horaria) con la estación propia y publica `data/skill_rosariosc.json` (sesgo, error medio absoluto, RMSE y sesgo por franja horaria). Solo declara un modelo más preciso con al menos 30 días comunes y un intervalo de confianza del 95 % que excluya el empate.
- Open-Meteo: ECMWF, GFS e ICON. Recopilación automática aproximadamente cada tres horas mediante GitHub Actions; posibles retrasos.
- **ECMWF AIFS Single (IA, 0.25°)**: modelo adicional de evaluación, consultado con `ecmwf_aifs025_single` desde Open-Meteo. **No altera** el pronóstico principal, máximas, mínimas ni el consenso de lluvia; se guarda y compara dentro del apartado de modelos. Si AIFS falla, se mantienen los tres modelos originales. El histórico previo no se reescribe.
- AIFS comparte proveedor con ECMWF pero usa otro enfoque/modelo; **no** es una fuente meteorológica completamente independiente. Su mejor desempeño en Rosario no está probado.
- La pantalla principal presenta **una única máxima y una única mínima**, seleccionadas de ECMWF, GFS e ICON según menor error absoluto histórico respecto a **INUMET Colonia G3**. La selección para máxima y mínima es independiente. Solo se usa si los tres modelos tienen al menos 4 valores comparables y el mismo tamaño de muestra; **se etiqueta como provisional**, porque Colonia G3 no es Rosario y todavía faltan datos. Si la comparación no está disponible, se muestra una sola temperatura del primer modelo operativo (preferencia ECMWF) con aclaración de que **no es un ganador**. AIFS queda en evaluación y no interviene en esta selección. El detalle completo permanece en el panel desplegable.

- Google WeatherNext 3: descartada su integración inmediata porque requiere solicitar acceso y un servicio adicional. Se puede reconsiderar posteriormente.
- Archivo de una previsión por fecha local, emitida **antes** del día evaluado, a **hora fija**: se conserva la toma más cercana a las **21:00 de Uruguay** (ejecución de las 00:23 UTC) dentro de la ventana 15:00-24:00; fuera de esa ventana una toma solo se usa si no hay otra. Si a la toma elegida le faltó un modelo, se completa con otra toma del mismo día (anotado en `late_fills`). Cada captura indica `evaluation_issue` (hora de emisión y distancia a las 21:00). Desde esta versión el archivo incluye la temperatura horaria de cada modelo.
- **Lectura directa de INIA:** el recolector de temperatura obtiene la medición pública de `WebData.xml` (estación `INIA_LE`, campos `TimeStampString` y `Air Temperature` en °C), comprueba la fecha/hora y exige como máximo 120 minutos de antigüedad. Si falla, conserva los respaldos INUMET (La Estanzuela / Colonia G3) y, por último, la estimación Open-Meteo. El horario se interpreta como hora local de Uruguay de acuerdo con los horarios observados en la página oficial; se rechazará cualquier lectura futura, antigua o no validada. No se consultan sistemas privados.
- **Temperatura observada por estación cercana:** `scripts/current_inia.py` consulta el estado público de las estaciones automáticas de INUMET, cotejando identificadores y nombres. Prioriza INIA La Estanzuela (ID 584), incorpora Cardona G4 (ID 1737, cardonag4) como respaldo y utiliza INUMET Colonia G3 (ID 594, U560) si las otras dos faltan. Una lectura directa INIA de más de 45 minutos se compara con INUMET y se sustituye si INUMET tiene una lectura al menos 30 minutos más reciente. No hay aún histórico suficiente para determinar qué estación es más estable a largo plazo. Se exige fecha/hora con zona, lectura físicamente plausible y antigüedad máxima de 120 minutos. Se actualiza en las tareas de rayos aproximadamente cada hora y al recopilar pronósticos. El archivo público `data/current_station.json` publica únicamente la medición meteorológica ya pública, sin datos privados. La página identifica **la estación real** y la hora en vez de atribuir el valor a Rosario. Si ninguna observación es reciente, utiliza la estimación de temperatura actual de Open-Meteo debidamente etiquetada; nunca inventa una temperatura ni muestra una lectura antigua como actual. El 29/10/2026 se verificó una respuesta de Colonia G3 con lectura de 19 °C a las 13:00 hora uruguaya, cuando INIA La Estanzuela no devolvió una temperatura válida.
- Observaciones oficiales INUMET Colonia G3, **no Rosario**. Evaluación comparativa solo con días de pronóstico previo y observaciones completas. Referencia mínima de 30 días antes de cualquier ranking; no se declara ganador automáticamente.
- Datos públicos INIA La Estanzuela (temperaturas extremas y lluvia) mediante `scripts/inia.py`. Se almacenan en `data/inia_la_estanzuela.json` solo tras validar columnas, valores y fechas. Si la descarga falla, no se reemplazan datos; se reintenta al día siguiente. Se consulta el catálogo CKAN oficial como alternativa a la descarga CSV. **Sus intervalos 09:00-09:00 NO se mezclan con los aciertos diarios de INUMET (00:00-00:00)**. La nueva referencia aparece solo en el panel desplegable de precisión.
- Detecciones NOAA GOES-19 GLM próximas a Rosario, actualización horaria aproximada. **Datos incompletos o antiguos no se presentan como recuento reciente de rayos.** Cero detecciones no asegura ausencia de peligro.
- Enlace a fuentes satelitales NOAA y NASA.
- Acceso externo a Spymovil desde el sector «Mi acceso», con autenticación propia del portal.

## Control del agua: en preparación y separado de Spymovil

- Dos pasos: **Paso Méndez** y **Paso Tío Luis**.
- Spymovil actualmente conserva, sin cambios, sus alertas de **100 cm por SMS y correo**.
- Mi Clima **no está leyendo alturas en forma periódica**, **no está enviando alertas de subida** y **no registra lecturas reales**.
- La prueba con navegador confirmó acceso a una ruta de panel (`dashboard`), pero aún no obtuvo datos de las estaciones; una petición adicional fue bloqueada preventivamente.
- `scripts/water_trend.py` calcula en memoria cambios en cm y cm/h **sin conectarse a Spymovil ni modificar alarmas**; la tolerancia visual de 5 cm no es un nivel de corte vial.
- Los niveles reales, tendencias e historial deben permanecer privados en un futuro servicio autenticado: **no se almacenan en GitHub Pages, ni en este repositorio público, ni en registros de Actions**.
- Los niveles de riesgo y corte para cada paso deben establecerse mediante observaciones verificadas y seguras. La alarma de 100 cm **no equivale** a un corte confirmado.
- El archivo público `data/pasos-publicos.json` contiene únicamente estados viales sin verificar; nunca alturas privadas. No declaramos transitabilidad sin confirmación.

**Regla:** no modificar el programa Spymovil ni su configuración, estaciones o alarmas. Las consultas futuras deben ser de solo lectura, autorizadas y sin efectos secundarios.

## Concurrencia de workflows

- `clima.yml` y `rayos.yml` comparten el grupo `mi-clima-publicar` (sin cancelar ejecuciones en curso): son los únicos que despliegan GitHub Pages y se sincronizan con `main` antes de armar la página.
- `rosariosc.yml` usa su propio grupo y **solo guarda datos** (no despliega Pages), para no esperar detrás de las tareas largas.
- `recuperar-historico.yml` (manual) completa `data/rosariosc_history/` desde el historial git; comparte la cola de `rosariosc.yml`, así nunca escriben el CSV a la vez.
- `pruebas.yml` ejecuta todas las pruebas en cada pull request, solo lectura.
- Todo workflow que guarda datos reintenta el `push` hasta 3 veces y usa `[skip ci]`. Los workflows de diagnóstico son de solo lectura. `tests/test_workflows.py` verifica estas reglas.
- Riesgo residual conocido: GitHub conserva solo **una** ejecución pendiente por grupo; si `clima` y `rayos` se acumulan detrás de una ejecución larga, la pendiente más vieja se cancela. Revisar en Actions si aparecen ejecuciones «cancelled».

## Desarrollo y publicación

- Código de página: `index.html` y `service-worker.js`
- Pronósticos: `scripts/collect.py` y `.github/workflows/clima.yml`
- Observaciones y errores: `scripts/observe.py`, `data/skill.json`
- Rayos: `scripts/lightning.py` y `.github/workflows/rayos.yml`
- Pruebas aisladas de acceso a GDA: `.github/workflows/gda-authorized.yml` y `.github/workflows/gda-browser.yml`; **solo manuales, sin lecturas automáticas**.
- Tests: `python -m unittest discover -s tests -v`

Las publicaciones de pronóstico y rayos utilizan GitHub Actions y GitHub Pages. El planificador no garantiza precisión horaria. La página muestra antigüedad de los pronósticos y observaciones. No incorporar información empresarial, cookies, contraseñas ni sensores privados en este repositorio.
