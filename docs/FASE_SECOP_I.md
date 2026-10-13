# Piloto SECOP I: inventario de expedientes — rama de desarrollo

Este piloto no modifica el portal productivo ni acredita contratos por metadatos.

## Fuentes oficiales confirmadas (octubre 2026)

| Fuente | Dataset | Uso |
| --- | --- | --- |
| SECOP I procesos (vigente) | `f789-7hwg` | Proceso, contratista y fechas cuando publicados |
| SECOP I historico | `qddk-cgux` | Contratos previos al periodo del conjunto principal |
| SECOP I proponentes | `tauh-5jvn` | Participantes registrados por proceso; NIT a veces indefinido |
| SECOP I archivos desde 2019 | `ps88-5e3v` | Numero de constancia, nombre, tipo y ruta declarada del archivo |
| SECOP I archivos historicos | `8kpz-m6cc` | Archivos historicos; cubrimiento temporal se validara por registros |
| SECOP II archivos desde 2025 (siguiente fase) | `dmgg-8hin` | ID documento, proceso CO1.BDOS y URL publica |

### Datos de muestras reales extraidos de la API publica

- `ps88-5e3v`: numero_de_constancia `26-12-14816016`; identificador `140064067`; descripcion `CDP`; ruta `http://20.96.127.85/descarga/140064067`.
- `tauh-5jvn`: id_proceso `21-15-12242613`; proponente publicado con `num_doc_proponente = No Definido`.
- `8kpz-m6cc`: numero_de_constancia `18-4-7989814` y ruta de descarga como objeto `{ "url": "http://20.96.127.85/descarga/41902803" }`.

Estas muestras son estructuradas, no evidencia de participacion, firma o vigencia. Las URLs HTTP directas a IP no se descargan automaticamente por razones de seguridad y porque aun no se ha validado su funcionamiento.

## Paso siguiente, antes de integrar al buscador

1. Confirmar un acceso publico y seguro a archivos reales de SECOP I y a sus enlaces desde la ficha oficial del proceso; si no es posible, mantener registro solo de metadatos y fuente sin simular una lectura.
2. Elegir 10 expedientes de prueba: contratos individuales, consorcios publicados sin NIT de integrantes, uniones temporales, documentos PDF textuales y escaneados, expedientes sin archivos.
3. En pruebas controladas, procesar temporalmente PDF, extraer citas precisas con pagina y crear indice documental con NIT/razon social, porcentaje y enlace.
4. Solo considerar acreditado el contrato cuando exista contrato suscrito o documento equivalente, y composicion con identificacion/participacion demostrables; las fechas de ejecucion se deben verificar independientemente.
5. Registrar en PostgreSQL cursores, ultima fecha de consulta, archivos ya procesados, errores y resultados de extraccion. No usar SQLite en memoria como marcador de avance permanente.
6. Piloto de 1.000 documentos sujetos a disponibilidad y presupuesto de computo, antes de aprobar una indexacion nacional.
7. Luego habilitar regimen especial II en `p6dx-8zbt` mas `dmgg-8hin` y mensajes publicos solo cuando se valide su acceso.

## Operacion y costos

- La web 2.8 de Render sigue separada.
- Render Cron conlleva un coste adicional; no provisionar sin autorizacion. El codigo se prueba localmente.
- La base Postgres Free vence el 12-11-2026 y requiere exportacion o migracion antes de esa fecha.

## Comandos de prueba

```sh
python -m unittest discover -s tests -p 'test_secop_i_inventory.py' -v
```
