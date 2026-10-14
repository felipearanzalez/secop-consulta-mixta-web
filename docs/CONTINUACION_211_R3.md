# SECOP Consulta Mixta — contraste documental y vista experimental 2.11-r3

Los contratos físicos pueden no tener adjudicatario identificable ni contrato electrónico en los conjuntos estructurados. Además, un contrato suspendido puede quedar fuera de la sección de ejecución y seguir apareciendo entre otros registros. Esta fase permite consultar esos registros junto con la evidencia documental, conservando su procedencia y sus límites.

El desarrollo se guarda únicamente en `desarrollo/secop-i-regimen-especial-v211`, sobre `3fceb8ec2fad8dae1c66e4c43c46f4be008aa375`. `main` y `release/v2.10-estable` conservan `364acf769ee42024a876a061164708245eda57e4`. Los nueve archivos comprobados por `scripts/verify_frozen.py` siguen idénticos a 2.10. No se modificaron servicios, bases de producción ni configuración Render; la vista nueva no está desplegada.

## Comportamiento desarrollado

| Componente | Resultado |
|---|---|
| `index28/special_discovery.py` | Descubre portafolios de régimen especial sin exigir NIT ni adjudicación afirmativa. Un inventario parcial conserva el último cursor satisfactorio. Barridos manuales de hasta 20 expedientes. |
| `index28/portal.py` | Cataloga hasta 200 enlaces PDF visibles dentro del expediente FINDETER solicitado y los conecta a la cola persistente. Descarga únicamente HTTPS y rutas del mismo expediente; no inventa archivos ni conserva originales. |
| `index28/composition.py` | Reconoce cláusulas de integrantes con denominación o NIT partidos entre líneas y separa el cierre de la cláusula de las referencias al supervisor. Los porcentajes siguen siendo candidaturas, sin atribución automática. |
| `index28/evidence.py` | Recupera identificaciones de formularios financieros con encabezados explícitos, aunque el valor del NIT esté separado de su etiqueta. No asigna nombres ni porcentajes por proximidad en una tabla. |
| `index28/review.py` | Conserva consultas originales 2.10 en una tabla independiente y agrega anotaciones para una fecha de corte. Retiene contratos suspendidos y vencidos; separa adjudicaciones y evidencia pendiente. |
| `index28/api.py`, `web211/` | Consulta de contraste local por NIT y fecha, filtro de suspendidos, fragmentos con página, fuentes y exportación. Los errores de fuente no se convierten en ausencia de contratos. |
| `scripts/capture_review_sources.cjs`, `index28/public_bridge.py` | Ejecutan el motor congelado desde Node con transporte público limitado a los conjuntos oficiales utilizados. La captura SECOP no consulta Croma; una exportación original importada conserva íntegramente sus datos de Croma. |

FINDETER publica el archivo como `informe_definitivo_de_verificacion_de_requisitos_habilitantes.pdf`. El filtro anterior, que exigía nombres como evaluación o informe final, lo omitía. El nuevo catálogo conserva todos los PDF visibles dentro de la ruta del expediente, sin incluir enlaces de navegación institucional ajenos. Los informes de verificación se clasifican como evaluación para priorizar su lectura.

## Ensayo con fuentes públicas

El piloto descargó documentos públicos en esta fase e importó una consulta real del motor 2.10 guardada el **14 de octubre de 2026 a las 02:52:34 UTC**. No volvió a consultar todo el universo estructurado. La fecha de corte utilizada para el contraste fue `2026-09-08`; las anotaciones no reconstruyen el estado histórico a ese día.

| Caso | Resultado observado en la nueva consulta |
|---|---|
| INVIAS 3460-2024, `CO1.PCCNTR.6644739` | Conservado como suspendido, con la fuente contractual original. |
| RENTAN, `CO1.BDOS.7805277`, acta `597148931` | Dos páginas leídas. La cláusula de la página 1 produce candidaturas INTRAMAQ 90 % y MINOICA 10 % bajo CONSORCIO MEJORAMIENTO SUROESTE. No se promueve a contrato verificado. |
| FINDETER `PAF-INVIAS-O-082-2023` | Veinte PDF catalogados. El informe de habilitantes recupera el NIT de INTRAMAQ en la página 88 y su fragmento; no asigna automáticamente el 40 % de la tabla. |
| INVIAS LP-DEO-SVR-063-2025, `CO1.BDOS.9231141` | Conservado entre adjudicaciones por verificar; no se transforma en contrato electrónico. |

La consulta reúne **42 registros contractuales, un suspendido, tres adjudicaciones por verificar y dos archivos con evidencia para el NIT consultado**. Estos totales describen la muestra guardada, no una certificación de exhaustividad. La cola del piloto contiene 59 archivos: uno leído completo, uno parcial y 57 pendientes. El informe FINDETER tiene 121 páginas; se leyó de forma dirigida únicamente la 88 y **quedan 120 pendientes**. La lectura general puede continuar con la cola reanudable.

Huellas de los documentos descargados:

- RENTAN `597148931`: `0cb41c0a4ee982ae8bb34a77c27ff3fcf005a3dc2cc1a0780644dc2c717f615c`.
- FINDETER, informe de habilitantes: `653551203d1a1c7c30f0b8bf1cc3ed071993bc9ca31c278bcce8444081212e90`.

Fuentes públicas del piloto:

- [Metadatos RENTAN](https://www.datos.gov.co/resource/dmgg-8hin.json?proceso=CO1.BDOS.7805277).
- [Acta de inicio RENTAN](https://community.secop.gov.co/Public/Archive/RetrieveFile/Index?DocumentId=597148931&InCommunity=False&InPaymentGateway=False&DocUniqueIdentifier=).
- [Convocatoria FINDETER](https://www.findeter.gov.co/convocatorias/paf-invias-o-082-2023).
- [Informe de requisitos habilitantes](https://www.findeter.gov.co/system/files/convocatorias/PAF-INVIAS-O-082-2023/informe_definitivo_de_verificacion_de_requisitos_habilitantes.pdf).

Un ensayo independiente de descubrimiento real encontró `CO1.BDOS.10000000`, sin contrato estructurado, y puso nueve documentos en la cola. No descargó esos nueve archivos ni efectuó un barrido nacional.

## Uso en desarrollo

```bash
python -m pip install -r requirements-worker.txt

# Importar una exportación original o capturar una consulta SECOP nueva.
node scripts/capture_review_sources.cjs 900102268-1 consulta.json
python -m index28.worker_cli import-query --database sqlite:///desarrollo.sqlite3 --file consulta.json

# Alimentar y procesar la cola: operaciones separadas de las solicitudes web.
python -m index28.worker_cli catalogue --platform II --reference CO1.BDOS.7805277 --database sqlite:///desarrollo.sqlite3
python -m index28.worker_cli catalogue-portal --reference PAF-INVIAS-O-082-2023 --database sqlite:///desarrollo.sqlite3
python -m index28.worker_cli seed-special --database sqlite:///desarrollo.sqlite3 --processes 3
python -m index28.worker_cli work-queue --database sqlite:///desarrollo.sqlite3 --documents 10 --pages 3 --seconds 300
python -m index28.worker_cli review --database sqlite:///desarrollo.sqlite3 --nit 900102268-1 --cutoff 2026-09-08
python -m index28.api --database sqlite:///desarrollo.sqlite3
```

Abrir `http://127.0.0.1:10001/review/`. La vista consulta datos previamente importados e indexados; no lanza un barrido nacional al pulsar Consultar. Las rutas nuevas son `GET /api/review/search?nit=...&cutoff=YYYY-MM-DD` y `GET /api/review/export?nit=...&cutoff=YYYY-MM-DD`. La exportación conserva la consulta original completa. Continúan disponibles las rutas documentales de r2 y el esquema SQL existente, con una tabla aditiva de consultas.

El piloto reproducible requiere una consulta original guardada y una base local aislada:

```bash
python scripts/pilot_phase3.py --database sqlite:///piloto.sqlite3 --snapshot consulta.json --output resultado_piloto.json
python scripts/verify_development.py --output resultado_pruebas.json
```

## Validación y pendientes

Pasaron **79 pruebas Python sin omisiones**, las **tres regresiones JavaScript**, las verificaciones de sintaxis y congelamiento, y **41 pruebas con psycopg contra PostgreSQL en WebAssembly mediante PGlite Socket**. El servidor SQL temporal cerró correctamente. La comprobación HTTP del piloto confirmó los totales, la exportación sin pérdida del original y los tres archivos de la vista. La interfaz nueva tiene comprobaciones de HTTP y lógica JavaScript; no se realizó una inspección visual con navegador.

Antes de integrar siguen pendientes la lectura documental completa, el vínculo comprobado entre composición y contrato celebrado, las cesiones y novedades a la fecha de corte, y la validación de despliegue y concurrencia en PostgreSQL nativo. Los 403 de SECOP I registrados en r2 siguen siendo un límite conocido y no se reensayaron en este piloto. La cobertura nacional, las actualizaciones programadas y el cálculo de capacidad residual siguen fuera de esta fase.
