# SECOP Consulta Mixta — lectura reanudable y consulta del piloto 2.11-r2

## Estado de la versión publicada

`main` y `release/v2.10-estable` conservan `364acf769ee42024a876a061164708245eda57e4`. Este avance pertenece exclusivamente a `desarrollo/secop-i-regimen-especial-v211`, sobre el desarrollo anterior `d00e05e171824a3061f97a93fe23252fdc0ebc5d`. La web, el índice publicado, Croma y la configuración Render mantienen sus archivos idénticos a 2.10. No se desplegó la API experimental ni se programaron tareas.

La validación anterior se conserva en `VALIDACION_211.json`. Los resultados de esta revisión están en `VALIDACION_211_R2.json`.

## Problema corregido

Un documento parcial se reutilizaba como resultado previo sin volver a examinar sus páginas pendientes. Ahora la cola solicita solamente esas páginas y suma su evidencia a la ya conservada. Cada reanudación vuelve a descargar temporalmente el archivo para comparar su SHA-256. Si cambia, se registra `document_changed` y se conserva el resultado anterior; no se mezclan páginas de archivos distintos.

El contrato 280 del portafolio `CO1.BDOS.8263083`, archivo `625136592`, tenía pendientes las páginas 2, 4, 5 y 6. El ensayo de recuperación procesó únicamente esas cuatro páginas y conservó las páginas 1, 3, 7 y 8. Las ocho quedaron leídas con la misma huella `e9e6ba3cfa4459b77ead1ff3937bde936a4243767f3809b867c21ecbf84c814b`. Este ensayo reutilizó los bytes y el resultado OCR obtenidos realmente durante el diagnóstico; se distingue del piloto posterior, que efectuó las descargas y lecturas completas en vivo.

La lectura OCR usa una imagen completa de cada página, en escala de grises y con dimensión máxima de 2200 píxeles. PDFium cierra sus recursos antes de ejecutar Tesseract en español. `pdftoppm` queda como alternativa cuando PDFium no está instalado. Los errores distinguen fallos de renderizado, motor y tiempo; no se atribuye el problema anterior a una causa única no comprobada.

## Componentes nuevos y límites

| Componente | Resultado |
|---|---|
| `index28/reading_progress.py` | Progreso por página y compatibilidad con resultados anteriores. Conserva observaciones y límites de extracción al combinar resultados. |
| `index28/persistence.py` | Historial aditivo en `index_doc_result_versions` y pausas de fuente en `index_doc_access_state`. La lectura parcial admite hasta 64 rondas por trabajo y tres intentos por página. |
| `index28/pipeline.py` | Cataloga sin descargar, procesa la cola existente y reanuda pendientes. Un 403 pausa SECOP I durante una hora; SECOP II continúa y solo pausa el portafolio afectado cuando corresponde. El trabajo 403 puede reintentarse al terminar la espera, dentro de su cuota. |
| `index28/api.py` | API independiente de consulta de evidencia por NIT y cobertura del piloto. Devuelve página, archivo, huella, fragmento y estado de revisión. Los errores de disponibilidad son 503, sin sustituirlos por una búsqueda vacía. |
| `scripts/pilot_documentary.py` | Ensayo manual sobre referencias concretas, con base local aislada, cuotas y reporte. No acepta una base remota. |

El límite temporal de un lote impide iniciar el siguiente archivo al agotarse el presupuesto; una lectura ya iniciada termina dentro de los límites del descargador y subproceso. Las revisiones de metadatos se cuentan aparte de los documentos originales. Las tablas conservan metadatos, huellas y fragmentos de evidencia, sin PDF ni imágenes originales.

La API escucha en `127.0.0.1:10001` por defecto. Sus rutas son `GET /health`, `GET /api/documentary/status` y `GET /api/documentary/search?nit=...&limit=...`; el límite va de 1 a 200. Rechaza escrituras HTTP, parámetros duplicados y URLs arbitrarias. Se inicializa el esquema al arrancar; las solicitudes solo consultan datos. No está conectada a la interfaz 2.10.

## Piloto con fuentes reales

Se catalogaron 16 archivos de SECOP I, constancia `26-11-14749233`, y nueve de SECOP II, portafolio `CO1.BDOS.8263083`. Se seleccionaron diez archivos para lectura: uno de SECOP I y los nueve de SECOP II. Los otros quince archivos de SECOP I permanecen pendientes; catalogarlos no equivale a leerlos.

| Archivo SECOP II | Documento | Páginas leídas / reportadas | Estado automático |
|---|---|---:|---|
| `625136592` | Contrato 280 | 8 / 8 | Completo |
| `625136600` | Adjudicación 280 | 1 / 1 | Completo |
| `625136599` | Acta de inicio 280 | 2 / 2 | Completo |
| `625136593` | CDP 280 | 1 / 1 | Completo |
| `625136594` | Estudios previos 280 | 11 / 12 | Parcial; página 12 pendiente |
| `625136595` | Idoneidad 280 | 2 / 2 | Completo |
| `625136596` | Invitación 280 | 2 / 2 | Completo |
| `625136597` | Designación de supervisor 280 | 4 / 4 | Completo |
| `625136598` | Certificación 280 | 1 / 1 | Completo |

Resultado: ocho documentos completos, uno parcial y uno bloqueado de los diez seleccionados. Se procesaron 32 de las 33 páginas reportadas por SECOP II, con 29 observaciones de NIT y cero candidaturas de composición plural. La consulta local de la API recuperó esas 29 menciones del NIT `899999156`; este resultado no acredita un contrato de ese integrante ni identifica por sí solo al contratista.

La página 12 de los estudios previos produjo cero caracteres en tres intentos. La inspección visual de su render mostró una página en blanco con pequeñas marcas de escaneo. Esa observación no cambió automáticamente el estado: permanece parcial y conserva el incidente `page_unreadable`, para evitar que una ausencia de texto se trate como prueba suficiente de lectura completa.

El primer archivo seleccionado de SECOP I (`138867672`) quedó bloqueado por `http_403`. Las siguientes rondas no repitieron solicitudes a esa fuente durante la pausa. El código 3 del piloto señala los dos documentos sin lectura automática completa; no significa que los ocho resultados anteriores se hayan perdido.

## Acceso documental SECOP I

Las fichas de `21-4-12343945` y `26-11-14749233` devolvieron 403 en este entorno. Para el archivo `138695671`, los metadatos oficiales publican `http://20.96.127.85/descarga/138695671`; una comprobación diagnóstica de esa ruta exacta devolvió 406 y cuerpo vacío. Se conserva la ruta publicada como metadato, sin habilitarla como descargador seguro ni inventar una URL HTTPS equivalente. No se superaron controles de acceso ni se desactivó TLS.

Fuentes de los ensayos:

- `https://www.contratos.gov.co/consultas/detalleProceso.do?numConstancia=26-11-14749233`
- `https://www.datos.gov.co/resource/ps88-5e3v.json`
- `https://www.datos.gov.co/resource/dmgg-8hin.json?proceso=CO1.BDOS.8263083`
- `https://community.secop.gov.co/Public/Archive/RetrieveFile/Index?DocumentId=625136592&InCommunity=False&InPaymentGateway=False&DocUniqueIdentifier=`

## Reproducción en desarrollo

```bash
python -m pip install -r requirements-worker.txt
python -m index28.worker_cli catalogue --platform II --reference CO1.BDOS.8263083 --database sqlite:///desarrollo.sqlite3 --ocr
python -m index28.worker_cli work-queue --database sqlite:///desarrollo.sqlite3 --documents 10 --pages 3 --seconds 300 --ocr
python -m index28.worker_cli status --database sqlite:///desarrollo.sqlite3
python -m index28.worker_cli candidates --database sqlite:///desarrollo.sqlite3 --nit 899999156
python -m index28.api --database sqlite:///desarrollo.sqlite3
```

OCR requiere Tesseract y el modelo español `spa`. PDFium y Pillow se incluyen en `requirements-worker.txt`; `pdftoppm` solo es necesario para la alternativa de renderizado. Si falta el modelo, el incidente queda visible. `work-queue` ejecuta una ronda y devuelve su estado; hay que distinguir el éxito de ejecución del lote de la lectura completa de la cola.

```bash
python scripts/pilot_documentary.py --database sqlite:///piloto.sqlite3 --secop-i 26-11-14749233 --secop-ii CO1.BDOS.8263083 --documents-per-i 1 --documents-per-ii 9 --pages 3 --rounds 8 --seconds 900 --ocr --output resultado_piloto.json
python scripts/verify_development.py --output resultado_pruebas.json
```

Se aprobaron 68 pruebas Python, sin omisiones, y los dos ensayos de regresión JavaScript. Además, 30 pruebas pasaron con `psycopg` contra PostgreSQL compilado a WebAssembly, mediante PGlite Socket. Esa modalidad usa `scripts/run_document_pg_tests.py --pglite`, que desactiva las sentencias preparadas únicamente en el ensayo para evitar colisiones entre conexiones multiplexadas del emulador. Un PostgreSQL nativo conserva la configuración normal del controlador.

La validación SQL requiere una URL local aislada en `SECOP_TEST_DATABASE_URL`; cada prueba crea y elimina su esquema. La suite SQL terminó con código 0; el envoltorio del servidor temporal no cerró después y fue detenido por su límite de 150 segundos. Ese incidente del ensayo se registra por separado. PGlite no sustituye una validación de despliegue, carga y concurrencia sobre PostgreSQL nativo de Render. No se ejecutó una nueva validación visual de navegador: los archivos de la interfaz siguen idénticos y se verificaron sus regresiones JavaScript.

## Pendientes antes de integrar

El acceso público efectivo a documentos SECOP I continúa pendiente. También quedan la revisión de páginas sin texto, el contraste documental de contrato y composición, la ampliación de la muestra a expedientes plurales y la validación en PostgreSQL nativo. La cola y la API no atribuyen contratos por una mención de NIT. No se declara cobertura nacional ni ausencia de contratos, y la actualización incremental sigue siendo manual.
