# Integración complementaria Croma — SECOP Consulta Mixta 2.5 (piloto)

## Alcance y límites

- **No se ha comprobado todavía el acceso real con la cuenta del usuario a Croma.** Pruebas automatizadas utilizan simulaciones de las respuestas externas.
- Mantiene las consultas actuales de Datos Abiertos y la separación ejecución reportada / posible / otros contratos / participación / candidatos.
- Permite buscar contratos en Croma por **NIT del contratista** (asociación directa) y, opcionalmente, **identificación del representante** (no prueba pertenencia al grupo o empresa). Estos resultados figuran por separado al final para conciliación, no se atribuyen automáticamente ni se duplican en los conteos principales.
- Las consultas de `contracts-search` se paginan hasta `CROMA_PAGE_LIMIT` páginas de 100 registros cada una. El informe señala resultados parciales, `total_reported` y `as_of`.
- No descubre por sí solo integrantes ocultos en PDF de SECOP I. No prueba ejecución vigente, ni liquidación, ni capacidad residual.

## Por qué conectar Croma a ChatGPT no activa Render

El OAuth del servidor MCP de Croma (`https://api.croma.run/mcp`) está destinado a clientes conversacionales; no concede automáticamente credenciales al dominio `secop-consulta-mixta-web.onrender.com`. El servidor Python privado utiliza la API REST de Croma (`https://api.croma.run/co/secop/contracts-search/v1`) y necesita una `CROMA_API_KEY` cargada directamente en Render, **nunca en JavaScript, GitHub ni esta conversación**.

Fuente: https://docs.usecroma.com/mcp-server y https://docs.usecroma.com/guides/colombia/secop.

## Despliegue en Render

Backend independiente: `secop-croma-bridge.onrender.com`. Código Python estándar (`croma_backend.py`), sin base de datos ni paquete externo. Ejecución: `python croma_backend.py`; la variable `PORT` la asigna Render. El sitio principal estático conserva el mismo enlace y consultas anteriores.

En el servicio **secop-croma-bridge** de Render, apartado **Environment**, crear:

- `CROMA_API_KEY` = clave **API** creada en la consola privada de Croma.
- `SECOP_ACCESS_TOKEN` = cadena privada de al menos 20 caracteres, diferente de la clave API de Croma. Sirve para evitar que terceros consuman los créditos de Croma desde nuestra interfaz pública.
- `SECOP_ORIGIN` = `https://secop-consulta-mixta-web.onrender.com`.
- Opcional `CROMA_PAGE_LIMIT` = `5` (máximo 30), `SECOP_DAILY_LIMIT` = `50` (máximo 300 solicitudes al puente por IP/día, control de proceso no distribuido).

La clave **API** solo se coloca en Render. En la web, dentro de **Contraste complementario con Croma**, ingrese la **clave de acceso al buscador** (`SECOP_ACCESS_TOKEN`, no `CROMA_API_KEY`). Marque **Consultar Croma en paralelo** y presione el botón habitual **Consultar fuentes**. La clave queda en memoria de la pestaña y se perderá al recargarla; no se guarda en almacenamiento local.

La protección actual es idónea para una **prueba piloto controlada**, no para publicar una API Croma abierta al público. Para uso institucional permanente añada autenticación por usuario, limitación de solicitudes distribuida (Redis o puerta de enlace), presupuestos y alertas de crédito. Render Free puede suspender servicios por inactividad, incrementar la latencia y restringir recursos.

## Probar conexión

1. Abrir `https://secop-croma-bridge.onrender.com/health`. `configured:true` significa que las dos variables secretas están configuradas, **no** demuestra aún que Croma haya aceptado una consulta.
2. Introducir el acceso interno al buscador en la web, consultar NIT `800143586-1`, verificar los errores de API, resultados, `as_of` y truncamiento.
3. Comparar resultados con Datos Abiertos uno a uno por ID contractual, constancia, estado y fechas. Croma procesa fuentes derivadas de SECOP, no constituye prueba oficial independiente.
4. Probar NIT `901885583-8`. El hallazgo documental del CONSORCIO AGUA POTABLE **no se presume** accesible en Croma si la plataforma no indexa miembros plurales.
5. Verificar varios registros contra enlace SECOP y modificaciones para establecer precisión real.

## Pruebas automatizadas sin credenciales ni internet

`python -m unittest discover -s tests -v`

## Resguardo de credenciales

Prohibido publicar claves, respuestas sensibles, secretos o `.env` en GitHub. Nunca incrustar `CROMA_API_KEY` en `app.js`. El endpoint rechaza llamadas sin dos variables privadas, aplica CORS específico, token de usuario, cuota local y topes de paginación; errores upstream no se interpretan como ausencia de contratos.
