# Registro de fuentes de SECOP Consulta Mixta 2.6

## Conjuntos con consulta implementada en la interfaz

| Dataset | Descripción | Tratamiento |
|---|---|---|
| `qmzu-gj57` | Proveedores registrados SECOP II | Identificaciones y códigos de proveedor |
| `ceth-n4bn` | Grupos de proveedores SECOP II | Pertenencia publicada, porcentajes y códigos de grupo |
| `jbjy-vk9h` | Contratos electrónicos SECOP II | Contratos publicados, estados, fechas, valores |
| `f789-7hwg` | SECOP I - procesos | Contratación SECOP I 2018+ |
| `qddk-cgux` | Histórico SECOP I | Contratación histórica |
| `p6dx-8zbt` | SECOP II - Procesos de Contratación | **Nuevo:** adjudicaciones y procedimientos, no contratos firmados |
| `hgi6-6wh3` | Proponentes por Proceso SECOP II | **Nuevo:** proveedores relacionados a procesos, no contratos |

Fuentes de los dos nuevos conjuntos:

- https://www.datos.gov.co/d/p6dx-8zbt
- https://www.datos.gov.co/d/hgi6-6wh3

En `p6dx-8zbt`, `nit_del_proveedor_adjudicado` y `codigoproveedor` son las claves de búsqueda; `id_del_portafolio`, `id_del_proceso`, `id_adjudicacion`, `adjudicado` y `urlproceso` permiten identificación y trazabilidad. En `hgi6-6wh3`, se usan `nit_proveedor`, `codigo_proveedor` e `id_procedimiento`. Las columnas se validan contra metadatos de cada fuente en el momento de la consulta.

## Fuentes institucionales con indexador piloto no desplegado

- FINDETER: https://www.findeter.gov.co/convocatorias
- ASOSUPRO: https://contratacion.asosupro.gov.co/site/index

Se ha preparado un programa de inventario y rastreo documental para estas dos fuentes, pero **sus resultados aún no alimentan el buscador público**. No atribuirles cobertura hasta contar con procesamiento y pruebas reales.

## Fuentes pendientes

- Universidades públicas, con portales heterogéneos.
- Empresa de Acueducto y Alcantarillado de Bogotá (EAAB-ESP), Grupo Energía Bogotá y otras E.S.P., distinguiendo sus regímenes y portales.
- Fuentes peruanas (SEACE, Provías Descentralizado y Unidad Ejecutora 118); requieren RUC e identificación de sujetos extranjeros, sin vincularlos automáticamente por nombres similares.

## Restricciones técnicas y jurídicas

«En ejecución» es un estado publicado, no una certificación de vigencia contractual; deben examinarse suspensiones, prórrogas, terminación y liquidación. Las adjudicaciones o apariciones como proponente no prueban suscripción. Una coincidencia de NIT en documentos institucionales puede corresponder a la entidad contratante, aseguradora, representante, integrante o un tercero; debe clasificarse según el documento y el papel específico.

Todo error HTTP, pérdida de conectividad, metadato ausente, límite de paginación o bloqueo de descarga debe registrarse como fuente incompleta.
