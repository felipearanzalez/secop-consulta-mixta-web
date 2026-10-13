# Arquitectura prevista para cobertura ampliada

## Estado actual

1. **Sitio estático Render:** formulario por NIT, consultas públicas estructuradas SECOP I/II; sin claves privadas para esas consultas.
2. **Fuentes nacionales estructuradas:** contratos electrónicos, SECOP I, grupos, proveedores, procesos y proponentes SECOP II.
3. **Presentación de evidencia:** enlaces oficiales, secciones diferenciadas por nivel jurídico y reporte de incidencias.
4. **Croma:** retirado de la vista web de esta edición. El servicio complementario anterior de Render no se borra ni reutiliza sin autorización adicional.

## Siguiente despliegue (pendiente)

1. Trabajador de indexación documental permanente, con fuentes verificadas y reintentos.
2. Base PostgreSQL con tablas de contratos, procesos, documentos y evidencias de integrantes; índice invertido por NIT y cédula.
3. Servicio API de consulta a ese índice que devuelva asociaciones con enlace, página y nivel de verificación.
4. Monitoreo de cobertura, documentos no procesados, costos y errores por entidad.

Un sitio estático no puede mantener una base documental nacional ni ejecutar la descarga y OCR de miles de documentos fuera de cada consulta. El trabajador institucional incluido usa SQLite como piloto aislado y requiere infraestructura persistente antes de conectarlo al buscador.
