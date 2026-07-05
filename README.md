# Predicciones de fútbol: Elo + Goal Index

Motor que cruza el **ranking Elo** de los equipos con su **Goal Index**
(goles a favor - goles en contra) para encontrar partidos donde ambas
métricas apuntan al mismo favorito, y calcula:

1. Probabilidad de victoria / empate / derrota.
2. Los 3 marcadores exactos más probables (ej. 2-0, 1-1, 1-0), usando un
   modelo de Poisson.

Corre **automáticamente cada 6 horas en GitHub Actions** (gratis) y publica
los resultados en una página web con **GitHub Pages** (gratis, siempre
online). No necesitas tener nada abierto en tu laptop.

## Cómo ponerlo en línea (una sola vez)

1. Crea un repositorio nuevo en GitHub (puede ser público o privado) y sube
   todo el contenido de esta carpeta.
2. Ve a **Settings → Pages** del repo, y en "Build and deployment" elige
   "Deploy from a branch", rama `main`, carpeta `/docs`. Guarda.
3. Ve a **Settings → Actions → General → Workflow permissions** y marca
   "Read and write permissions" (para que el workflow pueda guardar los
   resultados automáticamente).
4. Ve a la pestaña **Actions** del repo, entra al workflow "Actualizar
   predicciones" y dale a "Run workflow" para probarlo manualmente la
   primera vez.
5. En unos minutos tendrás tu página en:
   `https://TU-USUARIO.github.io/TU-REPOSITORIO/`

A partir de ahí, se actualiza sola cada 6 horas (puedes cambiar el horario
en `.github/workflows/update.yml`, línea del `cron`).

## Cómo correrlo en tu máquina para probar

```bash
pip install -r requirements.txt
python engine.py       # descarga datos y genera data/predicciones.json
python build_site.py   # genera docs/index.html a partir del JSON
```

Abre `docs/index.html` en el navegador para ver el resultado.

## Estructura

```
fetch_data.py     -> descarga datos crudos (ClubElo, football-data.co.uk, API-Football)
poisson_model.py  -> matemática: Elo -> 1X2, Goal Index -> marcador exacto
engine.py         -> junta todo, aplica el filtro Elo+GoalIndex, genera JSON
                     y también genera la agenda de partidos de HOY (6am)
actualizar_ligas_extra.py -> semanal, Goal Index de ligas fuera de football-data.co.uk
monitor.py        -> vigilancia en vivo: revisa marcador + presión ofensiva,
                     avisa por Telegram
resumen.py        -> envía a Telegram el resumen de partidos a vigilar hoy (7am)
telegram_utils.py -> envío de mensajes al bot de Telegram
build_site.py     -> convierte el JSON en una página HTML simple
data/             -> predicciones.json, vigilancia.json (se sobreescriben)
docs/             -> index.html (esto es lo que publica GitHub Pages)
```

## Paso 2: agenda del día + resumen matutino + alertas en vivo por Telegram

Además de la página con predicciones, el proyecto ahora hace tres cosas más:

1. **Cada día a las 6am (hora Colombia/Perú/Ecuador)**, el workflow "Agenda
   de partidos de hoy" filtra los partidos de HOY que cumplen el filtro
   Elo + Goal Index, y guarda esa lista en `data/vigilancia.json` junto con
   su `fixture_id` y hora exacta de inicio (`kickoff_utc`) de API-Football.

   **¿Por qué a las 6am del mismo día y no en la noche anterior?** Porque
   si se generara en la noche, esa petición saldría del cupo del día
   anterior — y si ese día ya se gastaron muchas peticiones vigilando
   partidos, la lista de mañana podría no generarse por falta de cupo.
   Al correr esto a las 6am del MISMO día del partido (antes de que
   arranque cualquiera), garantizamos que el **primer cupo del día** se
   use para construir la lista, sin competir con nada.

2. **A las 7am**, una hora después, el workflow "Resumen matutino a
   Telegram" te manda un mensaje con todos los partidos que se van a
   vigilar ese día: equipo favorito y marcador más probable de cada uno.
   Este paso no gasta cupo de API-Football (solo lee lo que ya se generó
   a las 6am).

3. **Cada 15 minutos**, el workflow "Vigilancia en vivo" revisa esos
   partidos mientras se juegan (solo durante la ventana horaria real de
   cada uno — ver más abajo). Si el favorito va **empatando o perdiendo
   por máximo 1 gol** Y además está **atacando constantemente** (más
   tiros y córners que el rival), te manda un mensaje a Telegram. Solo se
   avisa una vez por partido.

### Configuración necesaria (una sola vez)

**A. Cuenta gratis en API-Football** (para ver partidos en vivo):
1. Regístrate gratis en https://dashboard.api-football.com
2. Copia tu API key.
3. Plan gratis = **100 peticiones al día**. El diseño de este proyecto
   está pensado para gastar muy pocas (ver más abajo), pero si vigilas
   MUCHOS partidos en simultáneo el mismo día, podrías quedarte sin cupo.

**B. Bot de Telegram** (para recibir las alertas):
1. En Telegram, escríbele a `@BotFather` -> `/newbot` -> sigue los pasos.
   Te da un **TOKEN**.
2. Escríbele cualquier mensaje a tu bot nuevo (para que pueda responderte).
3. Abre en el navegador: `https://api.telegram.org/bot<TU_TOKEN>/getUpdates`
   y copia el número que aparece en `"chat":{"id": ...}` -> ese es tu
   **CHAT_ID**.

**C. Guarda las 3 credenciales como Secrets en GitHub:**
Ve a `Settings -> Secrets and variables -> Actions -> New repository secret`
y crea:
- `API_FOOTBALL_KEY`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

Con eso, los tres workflows nuevos (`agenda_dia.yml`, `resumen_matutino.yml`
y `monitor_vivo.yml`) ya funcionan solos.

### Sobre el indicador de "atacando constantemente"

El plan gratuito de API-Football no tiene un campo llamado literalmente
"ataques peligrosos" (eso sí lo tienen Sofascore/Flashscore, pero sin API
gratis). Lo que uso en su lugar, y que sí es gratis, es una comparación de
**tiros totales y córners** del favorito contra el rival — si el favorito
domina claramente esas dos métricas, se considera que está "atacando
constantemente". Es una aproximación razonable, no un dato oficial de
"presión". Puedes ajustar la sensibilidad en `monitor.py`
(`PRESION_MINIMA_TIROS`, `PRESION_MINIMA_CORNERS`).

### Sobre el consumo de cupo (100 peticiones/día gratis)

**Fuera de la ventana horaria de cualquier partido vigilado: 0 peticiones.**
El script (`monitor.py`) revisa primero, usando solo la hora guardada en
`vigilancia.json`, si algún partido está por comenzar o en curso. Si no hay
ninguno, no llama a la API — aunque el workflow de GitHub Actions se
ejecute cada 15 minutos las 24 horas, no gasta cupo si no hay partidos
cerca.

**Dentro de la ventana de un partido (10 min antes hasta ~130 min después):**
- Ver "todos los partidos en vivo del mundo" cuesta **1 sola petición**,
  sin importar cuántos partidos estés vigilando al mismo tiempo.
- Pedir estadísticas detalladas cuesta 1 petición **por partido**, pero
  SOLO se pide cuando ese partido ya está en empate o -1 y aún no se ha
  notificado.

**Ejemplo de un día con 4 partidos que juegan en horarios distintos:**
cada partido dura ~2h15 de ventana, revisado cada 15 min = ~9 revisiones
por partido. Si los 4 no se solapan: 4 × 9 = 36 peticiones de "en vivo"
+ las estadísticas puntuales que se disparen. Muy por debajo de 100.

**Caso límite:** una tarde con 8+ partidos empatados simultáneamente
durante gran parte del partido sí podría acercarse al límite (porque cada
uno pide estadísticas por separado en cada revisión mientras siga
empatado). Si eso te pasa seguido, sube el cron a cada 20-30 min en
`monitor_vivo.yml`, o baja `MINUTOS_DURACION_MAXIMA` en `monitor.py`.

## Limitaciones que debes saber (importante)

- **Cobertura de ligas: 38 ligas/divisiones gratis vía football-data.co.uk**
  (Inglaterra, Escocia, Alemania, Italia, España, Francia, Países Bajos,
  Bélgica, Portugal, Turquía, Grecia, y 16 países más como Argentina,
  Brasil, México, Japón, etc. — ver la lista completa en
  `LIGAS_FOOTBALL_DATA` y `LIGAS_FOOTBALL_DATA_EXTRA` en `fetch_data.py`).
  **Más** cualquier liga que agregues a `LIGAS_API_FOOTBALL_EXTRA` (ver
  siguiente punto), que se actualiza 1 vez por semana vía API-Football.
- **Filtro de "distancia considerable" de Elo:** un partido solo entra si,
  además de que el mismo equipo tiene mejor Elo Y mejor Goal Index, la
  diferencia de Elo es de **al menos 100 puntos** (`ELO_GAP_MINIMO` en
  `engine.py`, ajustable).
- **Ligas fuera de las 38 de football-data.co.uk (ej. Ecuador, Colombia,
  Perú, Libertadores, etc.):** para esas, el Goal Index se calcula con la
  tabla de posiciones de API-Football, actualizada **1 vez por semana**
  (workflow "Actualizar ligas extra"), para no competir por cupo con la
  vigilancia en vivo. Tienes que configurarlas a mano una sola vez:
  1. Busca el `league_id` correcto:
     ```bash
     python3 -c "from fetch_data import buscar_id_liga_api_football as b; print(b('Ecuador'))"
     ```
  2. Agrégalo a `LIGAS_API_FOOTBALL_EXTRA` en `fetch_data.py`:
     ```python
     LIGAS_API_FOOTBALL_EXTRA = {
         242: "Ecuador - Liga Pro",
     }
     ```
  3. Corre el workflow "Actualizar ligas extra" manualmente una vez
     (pestaña Actions -> Run workflow) para generar el primer caché.
  Si la dejas vacía (`{}`), simplemente no se usa — no rompe nada.
- **Selecciones nacionales todavía no están conectadas al motor principal.**
  ClubElo es solo de clubes. Para selecciones necesitas los datos de
  eloratings.net, cuyo formato de descarga no es tan estable como el de
  ClubElo — dejé la función `obtener_ranking_selecciones()` en
  `fetch_data.py` con instrucciones de cómo verificarla/ajustarla si la URL
  cambia. Una vez la valides, se puede replicar la misma lógica del
  `engine.py` para selecciones.
- **Emparejamiento de nombres de equipo**: ClubElo y football-data.co.uk no
  siempre escriben igual el nombre de un equipo ("Man United" vs
  "Manchester United"). El motor intenta emparejarlos automáticamente por
  similitud de texto (`buscar_equipo_similar`), pero revisa el campo
  `equipos_sin_goal_index` del JSON generado: ahí aparecen los que no se
  pudieron cruzar, para que ajustes el nombre a mano si hace falta.
- **Los pesos del modelo son ajustables.** En `poisson_model.py`,
  `predecir_partido()` combina Elo (60%) y Goal Index/Poisson (40%). Si con
  el tiempo notas que un componente predice mejor que otro, ajusta esos
  pesos.
- Esto es un modelo estadístico, no una garantía. Fuentes gratuitas pueden
  cambiar de formato sin avisar; por eso cada función de red está aislada y
  documentada para que sea fácil de arreglar si algo deja de funcionar.
