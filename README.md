# SECOP Consulta Mixta 2.6 - Cobertura ampliada

Aplicación web estática para consultar registros públicos de SECOP I y II por identificación. Esta edición **no utiliza Croma** en su interfaz ni necesita la clave API de Croma.

## Funcionamiento de la edición web

* Conserva las secciones de ejecución reportada o posible, otros contratos, participaciones y candidatos con contratos.
* Mantiene contratos electrónicos SECOP II (`jbjy-vk9h`) y SECOP I (`f789-7hwg` y `qddk-cgux`).
* Añade **SECOP II - Procesos de Contratación** (`p6dx-8zbt`), para consultar adjudicaciones y otros procesos asociados a NIT o códigos de grupo registrados.
* Añade **Proponentes por Proceso SECOP II** (`hgi6-6wh3`), para distinguir participación en un procedimiento de adjudicación y firma.
* Cruza `id_del_portafolio` + `codigoproveedor` con `proceso_de_compra` + `codigo_proveedor` para no volver a presentar adjudicaciones ya enlazadas a contratos electrónicos recuperados en la consulta.
* Nunca contabiliza los procesos adjudicados y proponentes como contratos perfeccionados ni como ejecución acreditada.
* Mantiene informes JSON y el registro de consultas fallidas, parciales o truncadas.

## Publicación web

Archivos a publicar: `index.html`, `app.js`, `styles.css`. El sitio ya está configurado en el repositorio de GitHub y el servicio estático de Render. Los archivos `expanded26.js` e `institutional_indexer.py` se entregan como fuentes de desarrollo y pruebas; la ampliación web está integrada en `app.js`.

El enlace de la página se mantiene en:

https://secop-consulta-mixta-web.onrender.com/

## Motor piloto para fuentes institucionales

Se incluye `institutional_indexer.py` para desarrollar un indexador separado de los portales públicos de FINDETER y ASOSUPRO. **No está desplegado en la edición estática y no acredita cobertura de esas entidades.** Su base SQLite conserva inventarios, URLs, incidencias, páginas de PDF y fragmentos que contienen identificaciones, sin exigir que el usuario suba documentos.

La lectura de un NIT en un PDF es **evidencia indicativa, nunca asociación acreditada al contratista**. La relación contractual deberá confirmarse por posición en el expediente, adjudicación, contrato, integrante y porcentaje.

Para probar el piloto en un equipo o servidor de procesamiento:

```bash
python -m pip install -r requirements-institutional.txt
python institutional_indexer.py --database portal_evidence.sqlite3 --source both --pages 1 --documents 3
python institutional_indexer.py --database portal_evidence.sqlite3 --nit 800143586-1
```

Se recomienda desarrollar y ejecutar este trabajador en infraestructura con almacenamiento persistente, acceso a documentos y reintentos programados. La plataforma de hosting estático no sirve para ese procesamiento. No debe publicarse la base de datos de evidencias en un repositorio público.

## Requisitos de producción pendientes

1. Probar las nuevas consultas `p6dx-8zbt` y `hgi6-6wh3` en el navegador contra los servicios oficiales, especialmente en conjuntos muy extensos.
2. Verificar ejecución de navegación y descarga de los dos portales institucionales desde un servidor. Las pruebas incluidas simulan respuestas de red.
3. Habilitar indexación documental completa y persistente para SECOP I, portales externos y, si se requiere, otros países. **El módulo de candidatos por nombres no sustituye esa indexación.**
4. Medir la cobertura, falsos positivos y pendientes. El resultado «sin coincidencias» nunca acredita ausencia de contratos.

Consulte `docs/VALIDACION.md` y `docs/FUENTES.md`.

## Novedad 2.7: indice documental ligero

Consulte `README_INDEX27.md` para arquitectura, cobertura, API publica y despliegue.
La interfaz incorpora un panel breve de resultados documentales y fuentes;
no sube, muestra internamente ni archiva PDF. Se incluye un antecedente inicial
verificado (ASOSUPRO LP-035-2025, Contrato 002 de 2026, Consorcio Matepantano
MYM y participacion del 10% de MEYAN S.A.).

El esquema PostgreSQL puede alojarse en Render mediante `DATABASE_URL` secreta.
La actualizacion automatica nacional SECOP I / mensajes SECOP II sigue en
construccion; nunca se considera completa por la presencia de un caso piloto.
