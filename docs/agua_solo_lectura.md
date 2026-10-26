# Control de agua: solo lectura

Regla irrevocable del proyecto: no modificar el programa Spymovil, su configuracion, usuarios, sensores ni sus alarmas de 100 cm por SMS y correo.

Mi Clima puede iniciar sesion en forma autorizada y consultar lecturas en modo solo lectura, pero NO debe ejecutar operaciones de escritura, borrado, cambios de umbrales ni confirmacion/desactivacion de alertas en Spymovil.

El calculo de alturas y velocidad se realiza localmente sobre copias de lecturas. Hasta 5 cm inclusive se muestra 0; por encima se muestra la altura original. Nunca alterar la lectura original.

Las mediciones y credenciales son privadas. No guardar esos datos en el repositorio publico ni en GitHub Pages. La publicacion de riesgos y cortes requiere confirmacion y datos actuales, sin revelar alturas.

Los umbrales para cortar Paso Mendez o Paso Tio Luis aun no estan determinados. La alarma Spymovil a 100 cm NO es automaticamente un corte de camino.

Estado actual: aun no hay lectura automatica continua desde Spymovil a Mi Clima, ni alertas propias activas.
