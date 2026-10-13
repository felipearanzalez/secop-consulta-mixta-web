# SECOP Consulta Mixta — continuación del desarrollo 2.11

Este documento conserva el alcance de la primera continuación. La revisión posterior `CONTINUACION_211_R2.md` detalla la reanudación por página, el renderizado PDFium, las pausas de fuente y la API de evidencia, y actualiza los límites y comandos descritos aquí. Su verificación está en `VALIDACION_211_R2.json`.

## 1. Línea base y publicación

La versión 2.10 corresponde al commit `364acf769ee42024a876a061164708245eda57e4`. Las ramas `main` y `release/v2.10-estable` conservan esa referencia. El desarrollo se incorpora exclusivamente a `desarrollo/secop-i-regimen-especial-v211`.

Se conservan sin cambios `app.js`, `index.html`, `styles.css`, el puente Croma, los componentes `index27` y `render.yaml`. No se integran los módulos nuevos a la web ni se crean servicios o tareas programadas en Render. La rama de referencia no constituye una protección administrativa contra modificaciones futuras; la integridad se verifica con `python scripts/verify_frozen.py`.

## 2. Componentes desarrollados

| Componente | Comportamiento |
|---|---|
| `index28/discovery.py` | Descubre expedientes SECOP I con denominaciones plurales en `f789-7hwg` y `qddk-cgux`, sin conocer el NIT de los integrantes. Encola sus documentos. Un inventario parcial no permite saltar el expediente. |
| `index28/secop_i_documents.py` | Resuelve enlaces PDF observados en la ficha oficial, asociados a la misma constancia e identificador de archivo. No construye URLs supuestas ni convierte una ruta HTTP a IP en fuente validada. |
| `index28/persistence.py` | Mantiene inventarios, trabajos, revisiones, huellas, observaciones y estados en tablas SQL adicionales. Evita trabajos repetidos y coordina dos lectores mediante un identificador de turno. Un lector reemplazado no puede completar el trabajo del siguiente. |
| `index28/pipeline.py` | Procesa lotes manuales, prioriza evaluaciones y pólizas, conserva resultados previos y deja pendientes los documentos no leídos. Admite SECOP I y archivos de SECOP II. |
| `index28/composition.py` | Extrae candidaturas de integrantes con nombre, identificación y porcentaje explícito en la misma página. Excluye representantes, amparos y referencias a experiencia. No completa porcentajes por diferencia ni identifica automáticamente al adjudicatario. |
| `index28/evidence.py` y `pdf_reader.py` | Leen PDF dentro de un subproceso con límites. El OCR opcional exige Tesseract en español y procesa como máximo ocho páginas escaneadas por archivo. Los PDF e imágenes temporales se eliminan al terminar; solo se conservan hechos y fragmentos de evidencia. |
| `index28/reconciliation.py` | Conciliación aditiva por identificadores contractuales. Conserva estados, fechas, valores, categorías y Croma del JSON exportado por 2.10. Las diferencias se reportan sin sobrescribir la línea base. |
| `index28/worker_cli.py` | Permite descubrir expedientes, inspeccionar lotes, consultar evidencia pendiente y conciliar exportaciones desde la rama de desarrollo. |

## 3. Persistencia y reanudación

Las tablas `index_doc_jobs`, `index_doc_results`, `index_doc_observations` e `index_doc_inventories` son adicionales al índice existente. No se eliminan contratos ni integrantes ya verificados. No se almacenan bytes PDF ni imágenes en la base.

Cada trabajo distingue plataforma, expediente, archivo, revisión de metadatos y política del lector. Una nueva revisión conserva los resultados anteriores. Los resultados examinados se reutilizan; los fallos transitorios conservan el trabajo y permiten hasta tres intentos con espera creciente. Un HTTP 403, 404, enlace inválido o archivo incompatible queda bloqueado para revisión. Una página ilegible, un límite alcanzado o un OCR incompleto determina lectura parcial.

El barrido por `uid` constituye un recorrido del catálogo disponible al ejecutarlo. Para una nueva revisión del catálogo se utiliza una partición distinta. No garantiza por sí solo detectar modificaciones de registros anteriores ni archivos cargados después del barrido. La actualización periódica de contratos, composiciones y novedades no está programada.

## 4. Criterio para la conciliación

Los resultados de extracción se mantienen como evidencia pendiente de revisión. No ingresan a la lista de contratos de un integrante por la sola aparición de su NIT ni por el nombre de un consorcio.

Una incorporación documental a contratos exige `association_verified=true`, identificación de la persona que efectuó la revisión, fecha y evidencia revisada de contrato firmado y composición plural, ambas relacionadas con la misma clave contractual, URL autorizada, página y SHA-256. Esa estructura registra una revisión previamente realizada; el programa no autentica firmas ni sustituye el examen del expediente. El estado y las fechas publicados no certifican ejecución material.

El JSON de la web se conserva íntegramente y recibe un apartado adicional de conciliación. Los contratos SECOP II se comparan por `CO1.PCCNTR`; SECOP I utiliza el `uid` o, cuando falta, constancia, número de contrato e identificación del contratista. Los casos sin identificador suficiente no se fusionan por similitud nominal. Los registros duplicados conservan sus variantes de origen.

## 5. Ejecución local

```bash
python -m pip install -r requirements-worker.txt
python -m index28.worker_cli seed-secop-i --database sqlite:///desarrollo.sqlite3 --processes 3
python -m index28.worker_cli inspect --platform I --reference 21-4-12343945 --database sqlite:///desarrollo.sqlite3 --documents 3
python -m index28.worker_cli inspect --platform II --reference CO1.BDOS.8263083 --database sqlite:///desarrollo.sqlite3 --documents 1 --ocr
python -m index28.worker_cli candidates --database sqlite:///desarrollo.sqlite3 --nit 900317964-1
python -m index28.worker_cli reconcile --baseline exportacion_2_10.json --incoming evidencia_revisada.json
```

Para OCR se requieren `pdftoppm`, Tesseract y su modelo de español `spa`. Si falta el modelo, el resultado registra `ocr_spanish_unavailable`; no declara completada la lectura. PostgreSQL utiliza la misma interfaz mediante una URL de desarrollo en `--database`. Los comandos de inspección devuelven código 3 cuando el expediente permanece incompleto.

El archivo de incorporación para conciliación utiliza `{ "records": [...], "coverage": [...] }`. La lista `records` puede contener evidencia aún no verificada: en ese caso se conserva en `pending_evidence`, sin convertirla en contratos. La cobertura utiliza `status` con valores `ok`, `partial` o `failed`, y `truncated` cuando aplica.

## 6. Verificación

```bash
python -m pip install -r requirements-tests.txt
python scripts/verify_development.py --output resultado_pruebas.json
```

El ensayo SQL admite una base PostgreSQL local aislada en `SECOP_TEST_DATABASE_URL`. Cada prueba utiliza un esquema temporal independiente. También se verificó el controlador `psycopg` contra PostgreSQL compilado a WebAssembly mediante PGlite Socket; esta modalidad no sustituye una prueba de despliegue, carga o concurrencia del PostgreSQL nativo de Render.

Para reproducir esa modalidad de desarrollo se instala `@electric-sql/pglite` y `@electric-sql/pglite-socket` en un directorio de pruebas y se ejecuta su `pglite-server` con `--host=127.0.0.1 --max-connections=10 --run "python scripts/run_document_pg_tests.py" --include-database-url`. Estas dependencias no forman parte del servicio de producción.

La evidencia de las verificaciones y los ensayos con fuentes reales se registra en `VALIDACION_211.json`. Los ensayos con muestras controladas se distinguen de las consultas efectivas a fuentes oficiales.

## 7. Fuentes y límite de cobertura

Se verificaron directamente los esquemas de Datos Abiertos para `f789-7hwg`, `qddk-cgux`, `ps88-5e3v`, `8kpz-m6cc`, `p6dx-8zbt` y `dmgg-8hin`. Se conserva la separación entre registros contractuales, proponentes y archivos.

La [Guía para la Gestión Contractual de Entidades Estatales de Régimen Especial de la ANCP-CCE, aprobada el 30 de septiembre de 2025](https://www.colombiacompra.gov.co/wp-content/uploads/2025/09/Guia-para-la-gestion-contractual-de-Entidades-Estatales-con-Regimen-Especial-VF-2-1.pdf), pp. 26–27, distingue la gestión transaccional y la publicación de contratos firmados físicamente. Esa distinción sustenta técnicamente la inspección de documentos cuando no existe contrato electrónico en el conjunto estructurado. Corresponde a orientación oficial; no constituye certificación de un expediente concreto.

Los documentos no accesibles, los expedientes pendientes y los barridos incompletos permanecen visibles. No se declara cobertura nacional ni ausencia de contratos con base en consultas parciales. La ampliación institucional ASOSUPRO/FINDETER conserva su piloto anterior; no se habilita un rastreo nacional adicional ni se cambia su caso documentado de Matepantano.
