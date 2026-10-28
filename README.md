# Mi Clima Rosario

Aplicación pública de información meteorológica para **Rosario, Colonia (Uruguay)**:
https://super18rosario.github.io/mi-clima-rosario/

## Prioridades de la pantalla

1. Mostrar primero temperatura estimada y pronóstico para hoy/mañana.
2. Comparación de modelos, historial de aciertos, rayos, satélites y accesos en paneles desplegables.
3. Mostrar un aviso de pasos encima del tiempo **solo** si existe confirmación reciente (máximo 45 minutos) de subida, riesgo o corte. **Ausencia de aviso no significa paso seguro**.

## Datos que funcionan

- Open-Meteo: ECMWF, GFS e ICON. Recopilación automática aproximadamente cada tres horas mediante GitHub Actions; posibles retrasos.
- **ECMWF AIFS Single (IA, 0.25°)**: modelo adicional de evaluación, consultado con `ecmwf_aifs025_single` desde Open-Meteo. **No altera** el pronóstico principal, máximas, mínimas ni el consenso de lluvia; se guarda y compara dentro del apartado de modelos. Si AIFS falla, se mantienen los tres modelos originales. El histórico previo no se reescribe.
- AIFS comparte proveedor con ECMWF pero usa otro enfoque/modelo; **no** es una fuente meteorológica completamente independiente. Su mejor desempeño en Rosario no está probado.
- Google WeatherNext 3: descartada su integración inmediata porque requiere solicitar acceso y un servicio adicional. Se puede reconsiderar posteriormente.
- Archivo de primera previsión de cada fecha local, para poder evaluar lo previsto **antes** del día.
- **Temperatura actual observada:** INUMET publica lecturas de la estación automática INIA La Estanzuela, identificador 584. `scripts/current_inia.py` consulta solamente la página pública `https://www.inumet.gub.uy/tiempo/estaciones-meteorologicas-automaticas`, valida variable 47 (`TempAire`), identificador de estación y fecha/hora. Se refresca aproximadamente cada hora mediante `rayos.yml`, además del recolector de pronóstico. **Sólo se muestra como medición si la observación tiene menos de 120 minutos** y se indica que es en La Estanzuela, no en Rosario. Si no hay observación reciente, se muestra «— °C · Sin dato»; **no se sustituye por una estimación**. La página de INIA muestra lecturas en vivo para visitantes, pero su fuente JavaScript rechazó temporalmente la consulta automatizada; por su parte, INUMET devolvió un valor nulo para la variable de temperatura de esta estación en la última prueba. La conexión automática todavía no está confirmada. No incluye datos privados ni sensores Spymovil.\n- Observaciones oficiales INUMET Colonia G3, **no Rosario**. Evaluación comparativa solo con días de pronóstico previo y observaciones completas. Referencia mínima de 30 días antes de cualquier ranking; no se declara ganador automáticamente.
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

## Desarrollo y publicación

- Código de página: `index.html` y `service-worker.js`
- Pronósticos: `scripts/collect.py` y `.github/workflows/clima.yml`
- Observaciones y errores: `scripts/observe.py`, `data/skill.json`
- Rayos: `scripts/lightning.py` y `.github/workflows/rayos.yml`
- Pruebas aisladas de acceso a GDA: `.github/workflows/gda-authorized.yml` y `.github/workflows/gda-browser.yml`; **solo manuales, sin lecturas automáticas**.
- Tests: `python -m unittest discover -s tests -v`

Las publicaciones de pronóstico y rayos utilizan GitHub Actions y GitHub Pages. El planificador no garantiza precisión horaria. La página muestra antigüedad de los pronósticos y observaciones. No incorporar información empresarial, cookies, contraseñas ni sensores privados en este repositorio.
