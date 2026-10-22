# Mi Clima Rosario V6.1 — recopilación en la nube

**Estado:** paquete listo para publicar, todavía **NO desplegado en un repositorio independiente**.

## Qué hace
- Consulta separadamente ECMWF (`ecmwf_ifs`), GFS (`ncep_gfs_global`) e ICON (`icon_global`) mediante Open-Meteo.
- Guarda fecha UTC de recopilación y tres días locales (hoy, mañana y pasado mañana) en `data/latest.json`.
- Guarda la **primera recopilación de cada día** en `data/forecast_archive/AAAA-MM-DD.json`, sin sobrescribirla por actualizaciones posteriores. Permite evaluar el pronóstico emitido el día anterior sin mirar el resultado después de ocurrido.
- Publica pantalla móvil con información de lluvia/temperatura, modelos, actualización y un vínculo a Zoom Earth; NOAA de respaldo.
- No inventa confianza, porcentaje de lluvia ni ganadores: la exactitud queda pendiente hasta conseguir mediciones independientes verificadas de lluvia y temperatura cerca de Rosario.

## Publicación sin PC ni celular encendidos

**Se necesita un repositorio dedicado, sin tocar `super18rosario/super-18`.** Este paquete no crea el repositorio automáticamente. Desde GitHub crear `mi-clima-rosario` como público para utilizar Pages con el plan gratuito, y avisar para subir los archivos mediante la integración de GitHub.
1. Crear **un repositorio GitHub nuevo** y subir el contenido de esta carpeta a la rama **main**. Si usás Pages gratuito, generalmente tendrá que ser público: **solo contiene pronósticos de Rosario, no datos privados**.
2. En Settings → Pages → Build and deployment elegir **GitHub Actions**.
3. En Actions ejecutar manualmente `Mi Clima Rosario - recopilación y publicación` una vez, si la publicación inicial no se inició automáticamente.
4. Tras el primer trabajo exitoso, ingresar al enlace `https://USUARIO.github.io/REPOSITORIO/` desde Chrome Android y elegir **Añadir a pantalla principal**.
5. Revisar la fecha de la última actualización. El proceso está programado dos veces al día, aproximadamente a las 04:23 y 16:23 hora de Uruguay. GitHub puede atrasar o saltarse ejecuciones; el sistema muestra claramente si los datos no están actualizados.

No necesita configurar claves ni instalar Python en la PC. GitHub ejecuta el recolector en sus servidores. El servicio externo aún no está configurado.

## Verificaciones adicionales V6.1
- El servicio repite consultas con errores de red, HTTP 429 o HTTP 5xx, hasta 3 intentos. Errores HTTP definitivos no se repiten.
- La tarea programada ejecuta tests antes de recopilar.
- El dato de precipitación no se interpreta como lluvia observada ni como probabilidad porcentual.
- Si GitHub Pages no está activado, la tarea de despliegue puede fallar: activarlo en Settings → Pages y seleccionar GitHub Actions.

## Pruebas locales
`python -m unittest discover -s tests -v`

Para recolectar datos reales desde un equipo con internet: `python scripts/collect.py`.
Luego abrir `python -m http.server 8000` y `http://localhost:8000`.

## Limitaciones y riesgos
- Las llamadas a Open-Meteo requieren internet y quedan sujetas a sus condiciones y límites de uso (ver https://open-meteo.com/en/terms).
- La programación de GitHub Actions no es garantizada al minuto; puede fallar o suspenderse por inactividad u otros motivos. La pantalla muestra la antigüedad de los datos.
- Ni las imágenes satelitales ni el radar sin cobertura verificada se utilizan para evaluar aciertos.
- Archivar pronósticos no equivale a comparar con observaciones. Para generar un ranking fiable falta una fuente independiente de mediciones en Rosario y un criterio para los días con datos ausentes.
- `modelos que prevén lluvia` expresa conteo con umbral 0,2 mm/día, NO una probabilidad de precipitación ni una confianza estadística.
- GitHub Pages público hace públicos los archivos de histórico. No subir observaciones personales ni credenciales.