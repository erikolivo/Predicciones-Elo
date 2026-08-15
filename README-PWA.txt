GESTOR DE TURNOS - PILOTO PWA + SUPABASE

Contenido
- index.html: aplicación principal
- manifest.json: configuración PWA
- sw.js: Service Worker para caché/offline
- icon-192.svg / icon-512.svg: iconos
- SUPABASE_SETUP.sql: estructura de nube ya utilizada

IMPORTANTE
1. Para probar como PWA, NO abras index.html con doble clic (file://).
2. Usa HTTPS o localhost.
3. En PC puedes probar con: python -m http.server 8080
4. Abre http://localhost:8080/ en Chrome.
5. Para instalarla en Android, publica la carpeta en un hosting HTTPS (por ejemplo GitHub Pages, Netlify o Vercel) y abre esa dirección desde Chrome.
6. La orientación preferida de la PWA es horizontal; en navegadores que no permitan bloquearla, se muestra un aviso para girar el teléfono.

SUPABASE
- El proyecto y la Publishable Key ya están incorporados en el HTML.
- La clave usada es una Publishable Key, no una Secret/Service Role Key.
- La confirmación por correo debe permanecer desactivada para este piloto, tal como se configuró durante la prueba.
