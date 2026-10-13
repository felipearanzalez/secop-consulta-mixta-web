# SECOP Consulta Mixta — desarrollo controlado posterior a 2.10

**Estado:** conectores, cola documental persistente, descubrimiento de expedientes, OCR opcional y conciliación desarrollados y verificados en rama independiente; no integrados a la web. Detalle y reproducción en `DESARROLLO_211_CONTINUACION.md` y `VALIDACION_211.json`.

## Regla de congelamiento

- `main`, desplegada por Render en `https://secop-consulta-mixta-web.onrender.com`, conserva el commit **`364acf769ee42024a876a061164708245eda57e4`** (versión 2.10).
- La rama `release/v2.10-estable` apunta al mismo commit y sirve de referencia para regresar a él.
- Todo desarrollo nuevo se incorpora exclusivamente a `desarrollo/secop-i-regimen-especial-v211`.
- Render mantiene `autoDeploy: yes` vinculado a `main`: por tanto **no se deben hacer commits a `main`** hasta aprobar la liberación. Crear una rama no configura protección ni desactiva automáticamente Render.
- No reemplazar el motor de búsqueda, no modificar la interfaz ni eliminar el contraste voluntario con Croma.

## Componentes incorporados a la rama experimental

| Archivo | Función y límites |
|---|---|
| `index28/secop_i_inventory.py` | Inventario previo de proponentes/archivos SECOP I, desde 2019 y anteriores, por constancia exacta. No descarga PDF. |
| `index28/socrata.py` | Consultas acotadas a fuentes de Datos Abiertos, con lista cerrada de conjuntos/campos, paginación y errores visibles. |
| `index28/expediente_secop_i.py` | Une registros contractuales `f789-7hwg` y `qddk-cgux` con `tauh-5jvn`, `ps88-5e3v` y `8kpz-m6cc`, sin atribuir contratos por simple aparición de un proponente. |
| `index28/regimen_especial_secop2.py` | Consulta portafolios `CO1.BDOS` en `jbjy-vk9h`, `p6dx-8zbt` y `dmgg-8hin`; diferencia modalidad especial reportada, contratos estructurados y documentos sin examinar. |
| `index28/evidence.py` | Lee temporalmente PDF textual y admite OCR opcional en español, con límites de bytes, páginas y tiempo. Registra indicios de NIT y candidaturas de composición, con página y huella; no declara pertenencia por una mención. |
| `index28/document_worker.py` | Selecciona documentos de interés y solo permite descargar PDF de una ruta HTTPS autorizada; no conserva el archivo. Puede guardar únicamente indicios en el esquema existente de PostgreSQL/SQLite. |
| `index28/checkpoints.py` | Tabla SQL independiente de marcadores de avance. Un fallo conserva el último cursor satisfactorio. No hay ejecuciones programadas. |
| `index28/cli.py` | Prueba manual de inventarios oficiales, sin escribir en PostgreSQL. |

## Expedientes de prueba con datos reales contrastados

**SECOP I.** Constancia `21-4-12343945` (Aguas de Bogotá, IES INGENIEROS, CTO 129-2021). `f789-7hwg` reporta contrato de prestación de servicios, fecha de firma `2021-09-16` y finalización `2023-05-13`. `ps88-5e3v` publica referencias a otrosíes; sus rutas descargables indican una IP sobre HTTP y **no se consideran una URL segura validada**. Fuente: `https://www.contratos.gov.co/consultas/detalleProceso.do?numConstancia=21-4-12343945`.

**SECOP II.** Portafolio `CO1.BDOS.8263083` de la ESE Hospital San Antonio de Chía. El conjunto `dmgg-8hin` recupera, entre otros, referencias a `CONTRATO 280.pdf`, `ACTA DE INICIO 280.pdf`, `ADJUDICACION 280.pdf`, mientras la consulta del mismo portafolio a `jbjy-vk9h` no devolvió contrato estructurado. Estos resultados **no acreditan por sí solos la firma ni la modalidad jurídica**: debe examinarse el PDF original. Fuente: `https://www.datos.gov.co/resource/dmgg-8hin.json?proceso=CO1.BDOS.8263083`.

**ASOSUPRO.** El contrato Matepantano 002 de 2026 sigue en el índice documental 2.7 como caso verificado con enlace al contrato y póliza. El rastreador institucional de ASOSUPRO/FINDETER existe en código experimental; su indexación nacional no está activada.

## Plan de operación y control de integridad

1. Validar la accesibilidad de PDF públicos sin credenciales, captchas ni redirecciones a dominios ajenos; bloquear rutas HTTP antiguas y errores de contenido.
2. Examinar un lote de expedientes reales de SECOP I y régimen especial: contratos, evaluaciones, pólizas, constitución plural, actas de inicio y suspensiones.
3. Conservar solamente NIT, razón social, porcentaje, identificador del contrato, fechas reportadas, fuente, páginas verificadas, huellas, revisión y errores; **ningún PDF de forma permanente**.
4. Exigir evidencia suficiente de (a) contrato celebrado y (b) composición exacta para promover indicios a contratos plurales. Un estado SECOP no certifica ejecución material.
5. Usar `index_scan_checkpoints` para reanudar inspecciones parciales sin saltar registros. No alimentar ni modificar datos de producción desde pruebas.
6. Conciliar con 2.10 por identificadores contractuales. La versión aprobada deberá conservar, por lo menos, los casos `900317964-1` (Huila 1554/2023, Bucaramanga 184/2023), `800143586-1` (MEYAN/ASOSUPRO) y `901601837-5` (AGREOBRAS/ASOSUPRO), además de sus campos y enlaces. Croma continúa estrictamente opcional.
7. Solo después de validación real y decisión del usuario, habilitar actualización incremental y una lectura complementaria en el buscador.

## Fechas y actualización (propuestas; NO implementadas)

- Contratos con estado en ejecución, suspendido o modificado: actualización del índice como máximo cada **6 horas** y cotejo en vivo al consultar.
- Composiciones y documentos nuevos: **diaria** si la fuente responde y permite inspección.
- Terminados o liquidados: verificación menos frecuente, por ejemplo **semanal**.
- Mostrar siempre fecha y origen del dato. La fecha publicada por SECOP no equivale a fecha actual de ejecución.
- No provisionar Render Cron ni servicios pagos sin autorización. El PostgreSQL gratuito vigente tiene expiración anunciada para **12 de noviembre de 2026**; prever respaldo y migración.

## Comandos de validación local

```bash
python -m unittest discover -s tests -p 'test_expedientes_incrementales.py' -v
python -m unittest discover -s tests -p 'test_secop_i_inventory.py' -v
python -m unittest discover -s tests -p 'test_index27.py' -v
python -m index28.cli --secop-i 21-4-12343945
python -m index28.cli --secop-ii CO1.BDOS.8263083
```

En una máquina sin salida a internet, las pruebas inyectan muestras estructuradas previamente contrastadas con las API públicas. Los comandos CLI de la última sección requieren acceso real a `www.datos.gov.co`.

**Condición para la integración:** ensayos reales reproducibles, sin pérdidas de la versión 2.10, sin presunciones de pertenencia, sin resultados "cero contratos" si existe una fuente parcial y sin publicar contratos por mera coincidencia de NIT.
