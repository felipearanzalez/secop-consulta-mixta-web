# SECOP Consulta Mixta 2.2 — Publicación web

Esta entrega es la **versión estática** del buscador. Consulta Datos Abiertos SECOP I y II desde el navegador; no realiza indexación de PDF desconocidos. Para ello hace falta la edición completa con su indexador (entregada por separado).

## Preparar la fuente en GitHub

1. Cree en GitHub un repositorio nuevo denominado `secop-consulta-mixta-web` y elija inicialmente **privado** si prefiere limitar el acceso al código. No agregue `.env`, API keys, credenciales, tokens ni PDFs.
2. Cargue en la **raíz del repositorio** `index.html`, `app.js`, `styles.css` y `render.yaml` (opcionalmente este README). Para hacerlo desde la interfaz de GitHub use **Add file > Upload files**.
3. Copie el URL del repositorio (por ejemplo `https://github.com/USUARIO/secop-consulta-mixta-web`, sustituyendo USUARIO). No comparta contraseñas ni claves de acceso.

## Publicar en Render

- En Render, seleccione **New > Static Site** y vincule ese repositorio. Use la rama predeterminada (habitualmente `main`).
- Nombre sugerido: `secop-consulta-mixta-web`.
- **Build command**: `mkdir -p dist && cp index.html app.js styles.css dist/`
- **Publish directory**: `dist`.
- No añada variables secretas: esta versión no contiene backend ni tokens.
- Espere el resultado del deploy. Cuando indique estado **Live**, abra la URL `https://<nombre>.onrender.com` que el proveedor le asigne.

Como alternativa, Render permite configurar un Blueprint que lee `render.yaml` desde el repositorio. No es necesario utilizar ambas vías.

## Validación después del despliegue

1. La página carga sin NIT precargado y sin opciones de digitalizar archivos.
2. Consulte un proveedor conocido con registros públicos; compruebe en panel de control de cobertura que las consultas se completaron y que no hubo errores de CORS o HTTP.
3. Compruebe los enlaces del registro exacto de un grupo SECOP II y de su contrato, así como el enlace a un contrato de SECOP I.
4. Confirme que una coincidencia nominal o de representante **no** figure como participación probada.
5. No interprete «sin coincidencias» como certificación de no tener contratos vigentes.

El acceso a Datos Abiertos desde el navegador sigue sujeto a disponibilidad y CORS; si falla, debe usarse la versión de servidor, que contiene proxy autenticado y trabajador documental.
