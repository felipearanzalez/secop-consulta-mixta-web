# Plan de operacion del indice documental

1. **Publicacion inicial**: sitio SECOP 2.7 + prueba documental verificada de ASOSUPRO.
2. **Base ligera**: Render PostgreSQL; se requiere configurar `DATABASE_URL` desde
   el panel privado del servicio web. En Render se recomienda la URL interna,
   misma region Virginia. No enviar conexion ni credenciales al chat.
3. **Lectura periodica**: ejecutar `python -m index27.worker --source asosupro --pages 1 --documents 3`
   desde un cron/worker una vez validados permisos, conectividad y limites de descarga.
   El actual worker solo produce menciones de NIT no confirmadas.
4. **Ascenso de evidencia**: contrato firmado + documento que muestre composicion,
   porcentajes sumando 100 y enlace publico. Sin esos soportes no atribuir contrato.
5. **SECOP I**: incorporar descubrimiento de expedientes y lectura automatica
   de evaluaciones, contratos y polizas; capturar cobertura por fuente y errores.
6. **SECOP II**: desarrollar conector autorizado a mensajes publicos y anexos;
   no suponer acceso abierto al contenido transaccional a partir de una URL.
7. **Persistencia**: conservar solo referencia, NIT, vinculo contractual, porcentaje,
   pagina, enlace, huella digital opcional, fecha de revision y errores.
8. **Costos**: PostgreSQL Free se vence el 12-11-2026; no hay plan pago autorizado.

## Prueba de aceptacion

NIT `800143586-1` debe hallar `CONSORCIO MATEPANTANO MYM`, participacion 10%,
contrato 002 de 2026 ASOSUPRO, PDF de contrato y PDF de poliza como fuentes.
No debe etiquetarse 'en ejecucion' por el mero hecho de que haya contrato.

## Limitaciones verificadas

- Se probó el servidor HTTP y el almacenamiento SQLite localmente, no aun la
  conexion externa PostgreSQL/Render.
- Las pruebas de navegador se realizaron con API simulada y casos de fallo.
- No existe aun rastreo nacional continuo de documentos SECOP I / SECOP II.
- Las fuentes pueden retirarse o cambiar: la URL y la huella opcional no son
  una copia archivada del contenido original.
