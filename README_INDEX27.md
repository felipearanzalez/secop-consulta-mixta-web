# Indice ligero SECOP 2.7 - primer piloto

## Objetivo

Descubrir contratos y composicion plural al consultar un NIT **sin almacenar PDFs**.
Persisten solo hechos contractuales, NIT, porcentajes, estado de corroboracion,
URL de fuente, pagina y fecha de indexacion. Todas las fuentes deben ser publicas.

## Arquitectura

- `index27/store.py`: tablas Postgres en Render; compatible con SQLite para desarrollo/pruebas.
- `index27/verified_cases.json`: evidencia inicial verificada: ASOSUPRO LP-035-2025,
  contrato 002/2026, Consorcio Matepantano MYM (MEYAN SA 10%, MYM Inconser 80%, Agreobras 10%).
- `index27/api.py`: API publica de **solo lectura** `/api/index/search?nit=800143586-1`
  y `/health`, con origen restringido al sitio SECOP 2.7, limite basico y sin claves en el navegador.
- `index27/worker.py`: consume el rastreador limitado de FINDETER y ASOSUPRO,
  procesa PDFs **en memoria** e importa menciones de NIT exclusivamente como
  `indicio_no_verificado`. No atribuye contratos ni porcentajes basandose en menciones.
- `index27.js`: modulo pequeno de resultados con enlaces a la evidencia y un contador.

## Publicacion

La pagina estatica conserva el enlace actual. El backend usa PostgreSQL como
almacenamiento persistente mediante `DATABASE_URL` privada; Render misma region.
**El plan Free de Postgres expira tras 30 dias**: realizar respaldo/exportacion o migrar
antes del vencimiento. No provisionar planes pagos sin aprobacion.

El indice al inicio tiene **1 contrato documental acreditado y 3 integrantes**.
No equivale a cobertura nacional, ni incluye los mensajes dinamicos de SECOP II.
El programa de lectura general de SECOP I y la vinculacion automatica de cualquier
consorcio siguen siendo fases posteriores y necesitan validacion de archivos de origen.

## Seguridad y trazabilidad

- Sin uploads de usuario, sin URLs arbitrarias, sin claves API front-end.
- No se almacenan PDF, imagenes escaneadas ni documentos originales.
- Un NIT encontrado incidentalmente se registra como indicio, jamas como contrato.
- Se guarda el estado de corroboracion, URL, tipo de prueba y pagina.
- Se admite futura huella SHA256 cuando el fichero original este accesible.
- La caducidad o eliminacion de la fuente puede impedir corroboraciones posteriores.

## Ejecutar tests

```
python -m unittest discover -s tests -p 'test_index27.py' -v
python -m py_compile index27/*.py
node --check app.js
```

## Operacion del rastreador (pendiente programacion en nube)

```
python -m index27.worker --source asosupro --pages 1 --documents 3
```

Su salida **no** certifica asociacion al contrato. Hasta que existan pruebas reales
de conectividad, esta tarea no se considera operativa en produccion.
