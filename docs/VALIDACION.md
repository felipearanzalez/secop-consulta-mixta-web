# Validación reproducible de SECOP 2.6

## Comandos

Con Node.js 20+ y Python 3.10+ y dependencias de procesamiento institucional:

```bash
node --check app.js
node tests/test_coverage26.js
python -m unittest discover -s tests -p 'test_institutional.py' -v
python tests/browser_smoke.py
python tests/browser_flow.py
```

Los ensayos con Playwright requieren Chromium instalado. Las pruebas del indexador institucional usan `beautifulsoup4`, `pypdf` y `reportlab` para construir un PDF sintético en memoria. `reportlab` solo es una dependencia de desarrollo y no del trabajador productivo.

## Resultados verificados localmente

* Las dos fuentes nuevas (`p6dx-8zbt`, `hgi6-6wh3`) se consultan por NIT y códigos de grupo registrados, sin búsqueda nominal indiscriminada.
* Un procedimiento adjudicado se enlaza mediante código de proveedor y código de portafolio con el contrato electrónico ya obtenido, si los identificadores exactos coinciden.
* Los procedimientos sin contrato electrónico asociado a los datos recuperados quedan en un apartado específico de *adjudicaciones por verificar*.
* Los proponentes se muestran como participantes en procedimientos, sin ser contados como contratos.
* Se excluyen asociaciones ambiguas entre NIT y denominaciones de estructuras plurales.
* Se preservan los enlaces que apuntan a los portales oficiales autorizados.
* El formulario web y los resultados se renderizan sin errores JavaScript bajo respuestas simuladas de las API.
* El rastreador institucional prioriza documentos de contratación, registra NIT y página sin afirmar pertenencia y reutiliza documentos descargados recientemente.

## No comprobado en este entorno

* Consultas reales de extremo a extremo desde el navegador a los nuevos conjuntos de datos. El ambiente de ejecución local impide resolver algunos dominios externos.
* Descarga masiva o completa de FINDETER/ASOSUPRO, cuya estructura web y accesibilidad pueden variar.
* Incorporación automática de consorcios desconocidos de SECOP I mediante PDFs a la versión web estática.
* Cobertura histórica nacional o internacional exhaustiva.

La prueba final de aceptación consiste en comprobar, usando una identificación conocida, cuántos nuevos procesos adjudicados se localizan y si los enlaces conducen a los expedientes correctos sin confundir un proceso adjudicado con la firma contractual.
