# Auditoría del NIT 900317964-1 — Versión 2.10

**Empresa:** IES INGENIEROS S.A.S.  
**Problema reportado:** contratos omitidos de Gobernación del Huila y Municipio de Bucaramanga.

## Fuente primaria: Datos Abiertos SECOP II

Se verificaron **354 registros de pertenencia a estructuras plurales** del integrante en `ceth-n4bn`. Son **registros de grupo**, no 354 contratos.

| Fuente contractual | Código proveedor | Contrato | Contratista plural | Participación de IES | Estado | Inicio | Fin | Valor base publicado |
| --- | --- | --- | --- | ---: | --- | --- | --- | ---: |
| `jbjy-vk9h` | `721933083` | `CO1.PCCNTR.5365625` — 1554 de 2023 | CONSORCIO REHABILITACION IP | 90 % | Suspendido | 2024-04-01 | 2024-11-28 | $5.947.664.432 |
| `jbjy-vk9h` | `722004421` | `CO1.PCCNTR.5151026` — 184 de 2023 | CONSORCIO LA VICTORIA II | 40 % | Suspendido | 2023-08-08 | 2026-09-20 | $12.918.441.253,19 |

- Huila: [Contrato](https://community.secop.gov.co/Public/Tendering/ContractDetailView/Index?UniqueIdentifier=CO1.PCCNTR.5365625); [integrantes](https://www.datos.gov.co/resource/ceth-n4bn.json?codigo_grupo=721933083).
- Bucaramanga: [Contrato](https://community.secop.gov.co/Public/Tendering/ContractDetailView/Index?UniqueIdentifier=CO1.PCCNTR.5151026); [integrantes](https://www.datos.gov.co/resource/ceth-n4bn.json?codigo_grupo=722004421).

El campo `nit_participante` de IES figura como `9003179641`, es decir, NIT sin guion más dígito de verificación. Para ambas vinculaciones el identificador de proveedor es `701552218`.

Los dos contratos deben aparecer en **03. Otros contratos → SECOP II · Plural**. No corresponden al apartado de posible ejecución vigente, porque el estado publicado es `Suspendido`.

También constan al menos dos contratos individuales SECOP II de este proveedor por el código `701552218` (Gobernaciones de Caldas y Nariño). Deben mantenerse en la consulta normal, sin confundirlos con contratos de consorcios.

## Problema técnico y solución

La versión anterior recorría la composición de todos los grupos (más de 300 para este NIT) **antes** de consultar sus contratos. Si una consulta paginada fallaba, descartaba las páginas recuperadas. El procesamiento de muchas consultas aumentaba el riesgo de respuestas parciales y de perder expedientes de grupos consultados al final.

La versión 2.10:

1. Consulta los contratos por código de grupo **antes** de recuperar las composiciones completas.
2. Procesa hasta 50 grupos por lote y divide el lote si la fuente devuelve error o truncamiento, hasta un límite de profundidad.
3. Reintenta fallos transitorios HTTP 408/429/5xx y conserva los registros de páginas que sí obtuvo.
4. Hace visibles los contratos encontrados durante la recuperación, con fechas, estado y valor.
5. Mantiene SECOP I, SECOP II, Croma opcional, índice documental y jerarquía anterior.

## Prueba de regresión

- `node tests/test_nit_900317964.js`: 354 grupos, una falla simulada HTTP429 en un lote grande y recuperación de ambos contratos y de dos contratos individuales.
- `node tests/test_filter_retry.js`: evita la pérdida total de resultados al fallar una segunda página.
- `python tests/test_browser_900317964.py`: verifica la presentación en la categoría adecuada, los estados suspendidos, fechas, valores, enlaces y ausencia de errores JavaScript.

**Limitación:** las pruebas de regresión de esta versión simulan respuestas oficiales basadas en registros verificados. No prueban que todas las consultas de producción a Socrata terminen correctamente; los incidentes siguen auditándose y los expedientes del régimen especial requieren indexación documental incremental.
