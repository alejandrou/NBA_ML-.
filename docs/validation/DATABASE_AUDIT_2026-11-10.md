# Auditoría integral de la base de datos — 2026-11-10

Auditoría independiente y de solo lectura de la base de datos PostgreSQL del
proyecto (`nba`), de su esquema, de los procesos que la construyen y de cómo la
usa la aplicación. No se modificó ningún dato, estructura ni archivo de código;
el único archivo creado es este informe.

**Seguimiento del 2026-11-11 (F8-022).** Se conserva la auditoría como fotografía
del día 10. Después, el propietario autorizó resolver H-01, H-02, H-03 y H-14:
`nba` alcanzó `0012`, se creó una copia en otro disco, se cambió la conexión a
IPv4 y se eliminó la base temporal. La revisión posterior añadió verificación
SHA-256 de los archivos, una rutina repetible de copia y ensayos de restauración
de los volcados anterior y posterior a la migración. Véanse el
[registro de migración](MIGRATION_HEAD_HANDOVER.md) y el
[procedimiento de recuperación](BACKUP_AND_RESTORE.md). Los demás hallazgos
mantienen su alcance original; no se consideran resueltos por esta tarjeta.

## Cómo leer este documento

Cada afirmación lleva una de estas tres etiquetas:

| Etiqueta | Significado |
|---|---|
| **DEMOSTRADO** | Lo observé ejecutando una consulta, un comando o leyendo el código exacto. La evidencia está junto al hallazgo y es reproducible (apéndice A). |
| **RIESGO** | No ha fallado, pero el diseño o la configuración permiten que falle. Se explica el escenario. |
| **NO VERIFICADO** | No pude comprobarlo sin escribir, sin leer secretos o sin contactar con la fuente. Se dice por qué. |

Gravedad: **Alta** (bloquea un objetivo del proyecto o puede causar pérdida
difícil de recuperar), **Media** (degrada la operación o la fiabilidad),
**Baja** (deuda, coste pequeño o higiene).

---

## 1. Resumen ejecutivo

**Veredicto: el diseño es sólido y los datos almacenados son de calidad muy
alta; los problemas reales están en la operación (estado desactualizado,
copias de seguridad, conexión) y no en el modelo.**

Lo más importante, en orden:

1. **La base persistente está tres revisiones por detrás del código**
   (`0009` frente a `0012`). El sondeo de disponibilidad de la API responde
   `503`, el esquema `ml` no existe y, por tanto, el flujo de predicciones
   recién fusionado (#72–#74) no puede ejecutarse contra `nba`. La temporada en
   curso (2026-27) no está en la base ni en la caché de instantáneas.
2. **La última copia de seguridad es anterior a la carga de partidos.** El
   volcado más reciente es del 2026-10-24; las 14.435 filas de partidos y las
   474.309 líneas de jugador se cargaron el 2026-10-31. La base es reconstruible
   desde la caché HTML, pero la caché (1,2 GB, ~17.600 páginas, ≥30 h de
   descarga con límite de ritmo) vive en un solo disco y no se versiona.
3. **Cada conexión nueva tarda ~5 s** porque `DATABASE_URL` usa `localhost`
   (5.043 ms medidos) en lugar de `127.0.0.1` (29–40 ms). Afecta a cada comando
   de la CLI, al primer sondeo de la API y a cada conexión nueva del pool.
4. **Toda la plataforma, API incluida, se conecta como superusuario con la
   contraseña por defecto publicada en el repositorio.** Está mitigado (puerto
   solo en loopback) y es una decisión registrada (F6-018), pero la API ni
   siquiera abre sus transacciones en modo solo lectura, que costaría una línea.
5. **La guarda "solo desde `origin/main`" protege 5 de los 10 comandos que
   escriben.** Los cinco backfills históricos escriben en `DATABASE_URL` desde
   cualquier rama con solo pasar una bandera.
6. **Un defecto de carga silencioso:** `birth_date` es `NULL` en las 15.005
   filas del roster aunque la página fuente lo publica; el conversor solo
   acepta formato ISO y descarta el resto sin avisar.

Lo que está bien y está comprobado: integridad referencial sin huérfanos, cero
duplicados de grano, aritmética de box scores exacta en las 28.870 líneas de
equipo y 307.064 líneas jugadas, totales de temporada idénticos a la suma de
partidos en 8 de 12 temporadas (las 4 restantes difieren exactamente por los 7
partidos en cuarentena documentados), y consultas de la API en 4–8 ms.

### Tabla de hallazgos

| ID | Hallazgo | Gravedad | Estado |
|---|---|---|---|
| H-01 | `nba` en revisión `0009`; código en `0012`. Readiness 503, sin esquema `ml`, sin temporada 2027 | Alta | DEMOSTRADO |
| H-02 | Copia de seguridad anterior a la carga de partidos; caché en un solo disco | Alta | DEMOSTRADO (copias) / NO VERIFICADO (copias externas) |
| H-03 | Conexión en frío de ~5 s por `localhost` | Media | DEMOSTRADO |
| H-04 | Superusuario con credenciales por defecto para todo; sesiones de la API no son solo lectura a nivel de base | Media | DEMOSTRADO (riesgo aceptado en F6-018) |
| H-05 | Guarda de destino de carga ausente en 5 de 10 comandos de escritura | Media | DEMOSTRADO |
| H-06 | `birth_date` siempre `NULL`: pérdida silenciosa de dato en 15.005 filas | Media | DEMOSTRADO |
| H-07 | `cache_path` no portable e inconsistente (rutas absolutas de Windows con nombre de usuario frente a relativas) | Media | DEMOSTRADO |
| H-08 | El upsert de estadísticas reescribe todas las filas y `updated_at` en cada ejecución | Baja | DEMOSTRADO |
| H-09 | Linaje repetido por fila: 85 de 135 MB en `player_game_totals` | Baja | DEMOSTRADO |
| H-10 | Estadísticas del planificador obsoletas; indicios de reinicio no limpio | Baja | DEMOSTRADO |
| H-11 | Columnas y estructuras muertas o redundantes (53 columnas siempre `NULL`, `team_aliases`, etc.) | Baja | DEMOSTRADO |
| H-12 | Sin restricciones `CHECK` en las 32 tablas anchas; identificador público anulable | Baja | DEMOSTRADO |
| H-13 | Los 7 partidos en cuarentena no dejan rastro en la base | Baja | DEMOSTRADO |
| H-14 | Base sobrante `nba_f8006_tmp` (354 MB) que la guarda trata como persistente | Baja | DEMOSTRADO |
| H-15 | Documentación de migraciones desfasada | Baja | DEMOSTRADO |
| R-01 | Sin `statement_timeout` ni límite de transacción inactiva en la API | Baja | RIESGO |
| R-02 | Escritores concurrentes sin bloqueo (select-luego-insert) | Baja | RIESGO |
| R-03 | Backfills de estadísticas en una única transacción para todo el archivo | Baja | RIESGO |
| R-04 | Volumen Docker sin política de reinicio; `down -v` lo destruye | Media | RIESGO |
| R-05 | El código heredado (`db_manager/`, Peewee) apunta por defecto a la misma base | Baja | RIESGO |

---

## 2. Alcance, método y límites

### Qué se ejecutó

Todo en modo solo lectura. Las consultas SQL se lanzaron con
`default_transaction_read_only=on` forzado en la sesión (comprobado con
`SHOW`), y los scripts de Python con `postgresql_readonly=True` o únicamente
peticiones `GET` contra la aplicación en proceso.

| Comprobación | Herramienta |
|---|---|
| Inventario de bases, roles, esquemas, tablas, índices, restricciones, extensiones, configuración del servidor, reglas `pg_hba` | `psql` en el contenedor, catálogo del sistema |
| Perfil de datos e integridad: conteos exactos, huérfanos, duplicados, coherencia aritmética, conciliación entre granos | ~70 consultas SQL |
| Deriva entre modelos SQLAlchemy y esquema real | script con `sqlalchemy.inspect` |
| Comportamiento real de la API contra `nba` | `TestClient` en proceso, 26 rutas, solo `GET` |
| Latencia de conexión `localhost` frente a `127.0.0.1` | script de medición |
| Aceptación de las credenciales por defecto del repositorio | intento de conexión de solo lectura |
| Planes de ejecución de 8 consultas representativas (5 actuales, 3 de rutas planificadas) | `EXPLAIN (ANALYZE, BUFFERS)` |
| Validador propio del proyecto | `nba-data validate official-stats` |
| Pruebas unitarias offline | `pytest -m "not integration and not live"`: 1.878 superadas, 0 fallos |
| Lectura de código | modelos, 12 migraciones, repositorios, cargadores, CLI, API, guarda de carga, CI |
| Inventario de caché y copias | listado de `data/raw/html` y `../nba-backups` |

### Qué no se hizo, a propósito

- No se aplicó ninguna migración, `ANALYZE`, `VACUUM` ni restauración.
- No se leyó `.env`. Solo se comprobó, por comparación de objetos, que la URL
  configurada coincide con la URL por defecto del repositorio.
- No se contactó con Basketball Reference.
- No se ejecutó la vía de integración (`scripts/validate_database.sh`), porque
  crea y borra bases de datos.

### Entorno auditado

| | |
|---|---|
| Servidor | PostgreSQL 16.13 en Docker (`postgres:16`, contenedor `nba_postgres`), UTF8, `en_US.utf8` |
| Publicación del puerto | `127.0.0.1:5432` únicamente |
| Bases | `nba` (502 MB), `nba_f8006_tmp` (354 MB), `postgres` |
| Revisión aplicada en `nba` | `0009_games_and_box_scores` |
| Cabeza del repositorio | `0012_ml_predictions` |
| Código | rama `main`, commit `b094613` |

---

## 3. Cómo está construida la base

### 3.1 Flujo de datos

```text
Basketball Reference
   │  cliente HTTP único, limitado a 10 req/min, ≥6 s entre peticiones,
   │  detrás de un manifiesto aprobado y de la bandera --owner-approved
   ▼
Caché HTML en disco (data/raw/html, .html.gz, nunca se sobrescribe)
   │  + caché de instantáneas con marca de tiempo para páginas que cambian
   ▼
Parsers puros  →  normalizadores  →  validadores (puertas que fallan cerradas)
   ▼
Cargadores idempotentes (select por clave natural, luego insert/update)
   ▼
PostgreSQL  ──►  API FastAPI de solo lectura  ──►  web (planificada)
            └─►  ML: lectura de partidos, escritura de ml.predictions
```

La fuente de verdad es la caché, no la base. La base es un producto derivado y
reconstruible: el archivo completo se recarga sin tocar la red. Esta decisión
(ADR 0003) es la más importante del diseño y condiciona el resto: explica por
qué se eliminó el esquema `raw` (revisión `0008`) y por qué una copia de
seguridad de la base importa menos que una copia de la caché (H-02).

### 3.2 Esquemas y granos

| Esquema | Tablas | Contenido |
|---|---|---|
| `core` | 8 | Identidad: `seasons`, `teams`, `team_aliases`, `players`, `team_seasons`, `player_seasons`, `player_team_seasons`, `games` |
| `stats` | 35 | Estadísticas oficiales tal como las publica la fuente: 1 tabla de roster, 32 tablas anchas (8 familias × 4 granos) y 2 tablas de partido |
| `ml` | 2 (solo en código) | `model_versions`, `predictions`. **No existe en `nba`** |
| `features` | 0 | Reservado para métricas generadas; no hay ninguna |
| `public` | 1 | `alembic_version` |

Las 8 familias son `totals`, `per_game`, `per_minute`, `per_poss`, `advanced`,
`shooting`, `adj_shooting` y `pbp`. Los 4 granos son jugador-temporada y
jugador-equipo-temporada, cada uno en temporada regular y en postemporada.

### 3.3 Contenido real (conteos exactos)

| Tabla | Filas | Nota |
|---|---|---|
| `core.seasons` | 27 | 2000–2026, todas `NBA` |
| `core.teams` | 37 | Un registro por código de Basketball Reference (identidad por "era de código") |
| `core.team_aliases` | 805 | Una fila por equipo-temporada (ver H-11) |
| `core.team_seasons` | 805 | 29–30 por temporada |
| `core.players` | 2.693 | 2.654 con página de equipo + 39 creados desde box scores |
| `core.player_seasons` | 13.258 | |
| `core.player_team_seasons` | 15.005 | |
| `core.games` | 14.435 | Solo temporadas 2015–2026; todas `final` |
| `stats.team_game_totals` | 28.870 | Exactamente 2 por partido |
| `stats.player_game_totals` | 474.309 | 307.064 jugadas + 167.245 ausencias |
| `stats.player_season_*` (8) | 13.249 cada una | |
| `stats.player_team_season_*` (8) | 14.993 cada una | |
| `stats.player_team_season_roster` | 15.005 | |
| `stats.player_postseason_*` (8) | 5.531 cada una | |
| `stats.player_team_postseason_*` (8) | 5.531 cada una | |

Reparto del tamaño (502 MB): `player_game_totals` 172 MB (34 %); las 32 tablas
anchas y el roster ~320 MB; `team_game_totals` 11 MB; todo `core` ~10 MB.

Coincidencia caché ↔ base, comprobada: 805 páginas de equipo = 805
`team_seasons`; 2.654 páginas de jugador = 2.693 − 39 jugadores; 14.482 box
scores en caché cubren los 14.435 cargados más los 7 en cuarentena y los del
piloto.

---

## 4. Hallazgos detallados

### H-01 · La base persistente va tres revisiones por detrás — Alta — DEMOSTRADO

**Evidencia**

- `SELECT * FROM alembic_version` → `0009_games_and_box_scores`.
- La cabeza resuelta desde los scripts del repositorio es
  `0012_ml_predictions`.
- Deriva detectada comparando modelos con la base real:

  ```text
  EXTRA COLUMN in DB:   core.players slug              (la quita 0011)
  EXTRA INDEX in DB:    core.teams ix_core_teams_bref_id (lo quita 0010)
  MISSING TABLE in DB:  ml.model_versions              (la crea 0012)
  MISSING TABLE in DB:  ml.predictions                 (la crea 0012)
  ```

- `GET /api/v1/health/ready` contra `nba` → `503 {"detail":"Database schema not ready"}`.
- `core.seasons` no tiene la fila 2027 (`GET /api/v1/seasons/2027` → 404), y no
  existe el directorio `data/raw/snapshots`. El código declara
  `CURRENT_SEASON_END_YEAR = 2027` y la temporada 2026-27 empezó hace unas tres
  semanas.

**Consecuencias**

- Cualquier orquestador o usuario que confíe en el sondeo de disponibilidad ve
  el servicio como caído. Las rutas de datos siguen respondiendo `200` porque no
  dependen del sondeo, así que el sistema está en un estado ambiguo: "no listo"
  pero sirviendo.
- `nba-data ml register-model`, `ml predict` y `ml activate` fallarían contra
  `nba` porque sus tablas no existen. El trabajo de #74 ("publicar predicciones
  previas al partido") no es ejecutable hoy sobre la base real.
- El objetivo visible del proyecto —predecir el partido de esta noche— está
  bloqueado por tres pasos operativos pendientes: migrar, adquirir la temporada
  2027 y cargarla (tarjetas F8-020 y F8-008 en `backlog/`).

**Matiz importante.** No es un defecto de diseño: el flujo exige que el
propietario aplique cada migración con una instrucción explícita, y eso es
correcto. El hallazgo es que el desfase existe ahora y tiene efecto.

**Las tres revisiones pendientes son seguras de aplicar**, comprobado en `nba`:

| Revisión | Precondición | Estado en `nba` |
|---|---|---|
| `0010` quita `ix_core_teams_bref_id` | el índice existe | existe; `uq_core_teams_bref_id` cubre la misma columna |
| `0011` quita `core.players.slug` | ninguna fila con `slug` | 0 filas con valor |
| `0012` crea el esquema `ml` | el esquema no existe | no existe |

**Recomendación.** Seguir el procedimiento de
`docs/validation/MIGRATION_HEAD_HANDOVER.md` (copia, preflight, aplicar,
verificar) para `0010`–`0012`. Antes, tomar la copia que pide H-02. Considerar
que el sondeo de disponibilidad distinga "esquema por detrás pero compatible"
de "esquema incompatible": hoy cualquier migración fusionada tumba el sondeo
hasta que alguien la aplica a mano, aunque sea puramente aditiva.

---

### H-02 · Copias de seguridad atrasadas y caché en un solo disco — Alta — DEMOSTRADO / NO VERIFICADO

**Evidencia**

- `../nba-backups/` contiene tres volcados; el más reciente es
  `nba-before-0009.dump`, de 2026-10-24 23:05 (22 MB).
- Las tablas de partido se crearon el 2026-10-31 (`min(created_at)` y
  `max(updated_at)` en `player_game_totals` y `team_game_totals`). Ningún
  volcado contiene las 14.435 + 28.870 + 474.309 filas de partidos.
- `archive_mode = off`; no hay ningún mecanismo automático de copia en el
  repositorio ni en `docker-compose.yml`.
- La carpeta de copias está en el mismo disco que el proyecto y que el volumen
  de Docker.
- `data/raw/` está en `.gitignore`: 1,2 GB, ~17.600 cuerpos de página.

**Consecuencias**

- Perder el volumen de Docker hoy cuesta rehacer las cargas: del orden de 1 a 2
  horas de proceso offline (la carga de partidos sola tardó 31–63 min según la
  documentación), más las aprobaciones. Molesto, no grave, **mientras exista la
  caché**.
- Perder la caché es lo grave. Reconstruirla exige volver a descargar ~17.600
  páginas a 10 por minuto: un mínimo de ~30 horas de peticiones reales, con una
  aprobación del propietario por cada ejecución, y con el riesgo de que la
  fuente haya cambiado páginas que hoy se consideran inmutables. Los nombres de
  jugador, por ejemplo, se re-renderizan de forma retroactiva.
- Un fallo de disco se lleva a la vez la base, las copias y la caché.

**No verificado.** Si existe una copia fuera de este disco (nube, disco
externo, copia del sistema). No hay rastro de ella en el repositorio.

**Recomendación**

1. Copiar `data/raw/` y `data/models/` a un segundo medio. Es el activo
   irreemplazable; pesa 1,2 GB y casi no cambia.
2. Tomar un `pg_dump -Fc` ahora, antes de aplicar `0010`–`0012`.
3. Añadir "volcado tras cada carga" al procedimiento de carga, igual que ya se
   exige antes de cada migración.
4. Probar una restauración sobre una base desechable al menos una vez. Un
   volcado no restaurado es una hipótesis.

---

### H-03 · Cada conexión nueva tarda unos 5 segundos — Media — DEMOSTRADO

**Evidencia.** Medición de conexión en frío, dos repeticiones por host:

```text
cold connect via 'localhost':  5043 ms, 5067 ms
cold connect via '127.0.0.1':    40 ms,   29 ms
```

El valor por defecto de `DATABASE_URL` en `settings.py` y en `.env.example` usa
`localhost`, y la configuración activa coincide con ese valor por defecto. El
contenedor publica el puerto solo en `127.0.0.1`. En Windows, `localhost` se
resuelve primero a `::1`; ese intento se agota al llegar a
`connect_timeout = 5` y solo entonces se prueba IPv4. Los 5 s son exactamente
el tiempo de espera configurado.

El propio proyecto ya conoce el efecto: `SYSTEM_DESIGN.md` dice que la vía de
validación "usa IPv4 para `localhost`, evitando los retrasos de IPv6 en
Windows". La corrección se aplicó a esa vía y no al valor por defecto.

**Consecuencias**

- La primera llamada a `/api/v1/health/ready` tardó 5.157 ms. Su presupuesto
  declarado es de 2 s (`API_READINESS_TIMEOUT_SECONDS`), que solo acota la
  consulta, no la conexión.
- Cada comando de la CLI paga 5 s antes de hacer nada.
- El pool de la API (5 conexiones + 10 de desbordamiento) crea conexiones bajo
  demanda: cada vez que la concurrencia supera lo ya abierto, una petición
  espera 5 s. Lo mismo tras un reinicio del contenedor, cuando `pool_pre_ping`
  descarta las conexiones muertas.

**Recomendación.** Cambiar el host a `127.0.0.1` en `.env`, `.env.example` y el
valor por defecto de `Settings.database_url`. Es el cambio con mejor relación
impacto/esfuerzo de todo el informe.

---

### H-04 · Superusuario con credenciales por defecto para todo — Media — DEMOSTRADO

**Evidencia**

- Un único rol no del sistema, `nba`, con `SUPERUSER`, `CREATEDB`,
  `CREATEROLE`, `REPLICATION` y `BYPASSRLS`.
- Las credenciales por defecto del repositorio (presentes en `.env.example`,
  `settings.py`, `alembic.ini`, `docker-compose.yml`, CI y 20 archivos más) son
  aceptadas por TCP y dan superusuario. Una contraseña incorrecta se rechaza,
  así que la autenticación funciona; lo que ocurre es que la contraseña es la
  publicada.
- `pg_hba`: `trust` para conexiones locales del contenedor, `scram-sha-256`
  para el resto. `ssl = off`.
- La API usa ese mismo rol. `get_request_session` abre una sesión normal, sin
  `postgresql_readonly` ni `default_transaction_read_only`.

**Mitigaciones comprobadas**

- El puerto está publicado solo en `127.0.0.1` (`docker inspect`).
- La API no tiene ninguna ruta de escritura (26 rutas, todas `GET`), lee solo a
  través de `db/repositories/queries/` y nunca hace `commit`.
- Las consultas están parametrizadas. El único SQL interpolado es
  `SET LOCAL statement_timeout = {entero}`, calculado desde configuración.
  Una inyección de prueba en la ruta (`/players/x' OR 1=1--`) devuelve
  `404 Player not found`.
- La decisión está registrada: F6-018 declina separar el rol, con condiciones
  de reapertura explícitas (salir de loopback, segunda persona o servicio, ruta
  de escritura, despliegue fuera de la máquina del propietario).

**Valoración independiente.** La decisión es razonable para una plataforma
local de un solo propietario, y las condiciones de reapertura son las
correctas. Dos matices que el registro de la decisión no recoge:

1. La garantía de solo lectura de la API es **solo de código**. Hacerla también
   de base de datos no requiere un segundo rol: basta con que el motor de la API
   abra sus conexiones con `default_transaction_read_only=on` (o la opción
   `postgresql_readonly=True`, que el proyecto ya usa en `ml evaluate` y en el
   preflight). Coste: una línea. No añade ninguno de los costes operativos que
   F6-018 cita contra el rol separado.
2. Un superusuario de PostgreSQL puede ejecutar programas en el contenedor
   (`COPY ... FROM PROGRAM`). Cualquier proceso local que alcance
   `127.0.0.1:5432` —incluido software no relacionado con el proyecto— tiene ese
   poder con una contraseña pública. El riesgo real es bajo, pero es mayor que
   "puede leer estadísticas de baloncesto".

**Recomendación.** Aplicar el punto 1 ya. Mantener F6-018 tal cual. Si alguna
vez se cumple una condición de reapertura, crear el rol de solo lectura y
cambiar la contraseña antes de exponer nada.

---

### H-05 · La guarda de destino de carga cubre la mitad de los escritores — Media — DEMOSTRADO

**Evidencia.** `require_load_target` (`db/load_guard.py`) rechaza cargar una
base persistente si `HEAD` no está en `origin/main` o si `src`/`alembic` tienen
cambios sin confirmar. Solo se invoca desde dos funciones de `cli/main.py`:

| Comando que escribe | ¿Guarda? |
|---|---|
| `backfill offline` | **No** |
| `backfill stats` | **No** |
| `backfill player-stats` | **No** |
| `backfill player-postseason-stats` | **No** |
| `backfill games` | **No** |
| `backfill current-season-identity` | Sí |
| `backfill current-season-games` | Sí |
| `ml register-model` | Sí |
| `ml activate` | Sí |
| `ml predict` | Sí |

Los cinco primeros solo exigen su bandera `--execute-approved-*` y escriben en
lo que diga `DATABASE_URL`, que por defecto es la base persistente `nba`.

**Consecuencia.** La regla de `AGENTS.md` ("una carga en `nba` solo desde
`origin/main` fusionado") está aplicada por código para los comandos nuevos y
solo por disciplina para los antiguos, que son precisamente los que escriben
más filas (más de 800.000 entre todos). Un agente o una persona en una rama de
trabajo, con un parser a medio cambiar, puede reescribir el archivo histórico
con una sola bandera. `SYSTEM_DESIGN.md` afirma que los comandos de `ml`
"ejecutan la misma guarda que los otros cargadores", lo que da a entender una
cobertura que no existe.

**Recomendación.** Llamar a `require_load_target` en los cinco backfills
históricos, en el mismo punto donde ya se comprueba la bandera. Es código que
ya existe y ya está probado.

---

### H-06 · `birth_date` se pierde en silencio — Media — DEMOSTRADO

**Evidencia**

- `SELECT count(birth_date), count(*) FROM stats.player_team_season_roster` →
  `0` de `15.005`.
- La página fuente sí lo publica. En la página en caché de BOS 2020:

  ```html
  <td class="left " data-stat="birth_date" csk="19961024">October 24, 1996</td>
  ```

- El cargador (`team_season_stats.py`, `_to_date`) solo intenta
  `date.fromisoformat` y, si falla, devuelve `None` sin registrar nada:

  ```python
  try:
      return date.fromisoformat(cleaned)
  except ValueError:
      return None
  ```

  "October 24, 1996" no es ISO, así que todas las filas quedan a `NULL`.
- `OFFICIAL_STATS_SCHEMA.md` (línea 233) ya dice que `birth_date` "debería"
  parsearse; nunca se hizo.

**Consecuencias.** La columna existe, está documentada y parece poblada a ojos
de quien lea el esquema, pero no contiene nada. Ningún validador lo detecta:
`validate official-stats` informa `all_null_data_rows: 0` porque la fila tiene
otros datos. Va contra el principio del propio proyecto de que las puertas
fallen cerradas y de que "malformado" no se confunda con "ausente". Hoy no lo
consume la API (el roster no se sirve), pero la fecha de nacimiento es el dato
natural para cualquier variable de edad en el predictor de jugadores (F8-009).

**Recomendación.** Leer el atributo `csk` (`AAAAMMDD`), que es estable, o
aceptar el formato largo. Hacer que un valor presente pero no convertible sea
un error o una incidencia contada, no un `NULL`. Añadir a la validación un
control de "columna íntegramente nula" por tabla (ver H-11).

---

### H-07 · `cache_path` no es portable ni coherente — Media — DEMOSTRADO

**Evidencia.** Dos formatos conviven en la misma columna de linaje:

```text
stats.player_season_totals   C:\Users\<usuario>\Desktop\...\data\raw\html\basketball-reference\players-a-abdulma02.html-82dd….html.gz
stats.player_game_totals     data\raw\html\basketball-reference\boxscores-201410280nop.html-3ab3….html.gz
```

- Rutas absolutas en el 100 % de las filas de `player_season_totals` (13.249)
  y `player_team_season_totals` (14.993); el mismo cargador escribe las otras
  30 tablas anchas y el roster.
- Rutas relativas, con separador de Windows, en las 474.309 filas de
  `player_game_totals`.

**Consecuencias**

- El linaje deja de resolver en cuanto el repositorio se mueva de carpeta, se
  use el otro árbol de trabajo (`../Scraping nba-reference-app`), otra máquina
  o Linux (CI, un contenedor).
- La ruta incluye el nombre de usuario del sistema operativo. No se sirve por
  la API (`cache_path` está en `UNPUBLISHED_COLUMNS`, comprobado), pero viaja
  en cada volcado.
- Una reconstrucción en otra ubicación produce valores distintos y, por H-08,
  reescribe todas las filas.
- No se puede cruzar el linaje entre tablas por igualdad de texto.

**Recomendación.** Guardar una clave de caché independiente de la máquina: el
nombre del archivo (que ya contiene un hash) o la ruta relativa con `/`. La
ruta absoluta se deriva de `SCRAPER_CACHE_DIR` cuando haga falta. Se puede
combinar con H-09.

---

### H-08 · El upsert de estadísticas reescribe todo en cada ejecución — Baja — DEMOSTRADO

**Evidencia.** `StatsRepository._upsert` asigna todos los valores, todo el
linaje y `updated_at = datetime.now(UTC)` siempre que la fila existe, sin
comparar. En la base:

- 315.152 de 329.437 filas de las 33 tablas de temporada (95,7 %) tienen
  `updated_at ≠ created_at`.
- `max(updated_at)` es 2026-10-24 en todas ellas: la fecha en que se cargó la
  temporada 2026, cuando solo 582 jugador-temporadas eran nuevas.

El repositorio de partidos sí lo hace bien: `_assign_changed` solo escribe lo
que difiere y una repetición informa `unchanged`.

**Consecuencias.** `updated_at` significa "última carga", no "último cambio",
y eso lo hace inútil para detectar qué cambió en la fuente. Cada repetición
genera ~330.000 versiones muertas de fila y el WAL correspondiente. Las dos
mitades del esquema tienen semánticas distintas para la misma columna.

Además, `onupdate=func.now()` es un comportamiento del ORM: no hay ningún
disparador en la base (0 disparadores), así que un `UPDATE` hecho fuera de
SQLAlchemy no toca `updated_at`.

**Recomendación.** Reutilizar el patrón de `_assign_changed` en `_upsert`.

---

### H-09 · El linaje se repite en cada fila — Baja — DEMOSTRADO

**Evidencia.** En `stats.player_game_totals`, las columnas `source_url`,
`cache_path`, `parser_version` y las dos marcas de tiempo ocupan **85 MB de
135 MB** de datos de fila (63 %). Hay 14.435 valores distintos de `cache_path`
para 474.309 filas: el linaje depende del partido, no de la línea del jugador.
`core.games`, que es donde ese dato pertenece, no tiene ninguna columna de
linaje.

Lo mismo ocurre a menor escala en las tablas anchas: las 8 familias de un
jugador salen de la misma página y repiten el mismo linaje 8 veces.

**Consecuencia.** Es una dependencia funcional parcial (el linaje depende de
una parte de la clave). A la escala actual solo cuesta espacio: la tabla más
grande del sistema es mayoritariamente texto repetido. No afecta a la
corrección.

**Recomendación.** No es urgente. Si se toca el esquema por H-07, mover el
linaje de partido a `core.games` (o a una tabla `source_pages` referenciada por
id) y reducir `player_game_totals` a menos de la mitad.

---

### H-10 · Estadísticas del planificador obsoletas — Baja — DEMOSTRADO

**Evidencia**

- 41 de 43 tablas no tienen ningún `ANALYZE` ni `autoanalyze` registrado, y
  figuran con `n_live_tup = 0`.
- Las estimaciones de `pg_class.reltuples` son anteriores a la carga de la
  temporada 2026: `player_seasons` 12.676 estimadas frente a 13.258 reales (la
  diferencia, 582, es exactamente la temporada 2026); `players` 2.551 frente a
  2.693.
- `core.players` figura con `n_live_tup = 39`: las 39 inserciones del
  2026-10-31.

La lectura coherente es que los contadores acumulados se reiniciaron entre el
24 y el 31 de octubre (lo que hace PostgreSQL tras un apagado no limpio) y que,
desde entonces, el autovacuum cree que esas tablas están casi vacías y no las
analiza porque ya no cambian. El contenedor no tiene política de reinicio y
llevaba 46 minutos levantado durante la auditoría.

**Consecuencia.** Ninguna medible hoy: todos los planes observados son
correctos y rápidos (§6). Es una condición latente que puede producir un mal
plan cuando lleguen consultas más complejas (rutas de partidos, búsquedas).

**Recomendación.** Ejecutar `ANALYZE` al final de cada carga masiva e
incluirlo en el procedimiento. Apagar el contenedor con `docker compose stop`
antes de cerrar Docker.

---

### H-11 · Columnas y estructuras muertas o redundantes — Baja — DEMOSTRADO

Cada línea está medida en `nba`.

| Elemento | Evidencia | Valoración |
|---|---|---|
| `rk` en las 24 tablas de grano jugador-temporada y de postemporada | 0 valores no nulos | La fuente no publica ranking en la página del jugador. Columna muerta en 24 tablas |
| `player_name_display` en esas mismas 24 tablas | 0 valores no nulos | Igual. Además está marcada como "no promesa" en el contrato |
| `fg_pts_added`, `ts_pts_added` en postemporada (2 tablas) | 0 valores no nulos; en temporada regular están al 100 % | Probablemente la fuente no los publica en playoffs. **No verificado** contra la página |
| `birth_date` | 0 de 15.005 | Defecto, ver H-06 |
| `core.teams.franchise_id` | 0 de 37 | Decisión documentada en `BUSINESS_RULES.md`; correcto mantenerla sin escribir |
| `core.teams.current_abbreviation` | idéntica a `basketball_reference_team_id` en 37 de 37 | Redundante bajo la regla de "era de código" |
| `core.seasons.label` | igual a `season_year` como texto en 27 de 27 | Redundante; la API la sirve |
| `core.team_aliases` | 805 filas, `from = to` en todas, 37 combinaciones distintas; 0 lecturas por índice | La tabla modela rangos pero guarda una fila por temporada. Duplica `team_seasons` × `teams` y nadie la lee |
| `core.player_team_seasons.roster_number` / `roster_position` | 0 diferencias con `stats.player_team_season_roster` | Dato duplicado en dos esquemas |
| `id` sustituto en las 34 tablas de `stats` | `player_game_totals_pkey`: 10 MB, 0 usos; las demás claves primarias tampoco se usan | Cada tabla tiene ya una clave natural única. El `id` solo se usa como desempate de orden en una consulta |
| `core.players.slug`, `ix_core_teams_bref_id` | pendientes de `0011` y `0010` | Ya resuelto en código |

**Consecuencia.** Ruido: quien lea el esquema asume que esas columnas tienen
datos. La API publica `rk: null` en cada respuesta agregada (observado). En
total hay 53 columnas íntegramente nulas.

**Recomendación.** Sin urgencia. Decidir para `team_aliases` si se colapsa a
rangos reales o se elimina; documentar `rk`/`player_name_display` como no
disponibles en ese grano o dejar de servirlas; añadir a `validate
official-stats` un control de columnas íntegramente nulas con una lista de
excepciones justificadas, que habría detectado H-06.

---

### H-12 · Poca integridad declarativa en las tablas anchas — Baja — DEMOSTRADO

**Evidencia**

- Las 32 tablas anchas y el roster no tienen ni una restricción `CHECK`. Las 5
  que hay en `stats` son de las dos tablas de partido.
- 973 de 1.226 columnas de `stats` admiten `NULL`.
- `core.players.basketball_reference_player_id` es la clave pública de la API
  y admite `NULL`. Hay 0 nulos; la API filtra `IS NOT NULL` en cada consulta
  para compensarlo.
- `source_team_code`, `core.seasons.league` y `season_year` no tienen
  restricción de dominio.

**Contexto.** Los datos están limpios hoy (§5): 0 negativos, 0 porcentajes
fuera de [0, 1], 0 incoherencias aritméticas. Las invariantes existen, pero
viven en validadores de Python que se ejecutan a mano; la base aceptaría una
fila inválida de un cargador futuro. Las tablas de partido, más recientes,
demuestran que el equipo ya sabe hacerlo bien: sus `CHECK` están congelados en
la migración y fijados a los modelos por una prueba.

**Recomendación.** Añadir `NOT NULL` a `basketball_reference_player_id` y unos
pocos `CHECK` baratos (`g >= 0`, `gs <= g`, `fg <= fga`, porcentajes entre 0 y
1) en las tablas `totals`. No hace falta cubrir las 552 columnas numéricas.

---

### H-13 · Los partidos en cuarentena no dejan rastro en la base — Baja — DEMOSTRADO

**Evidencia.** Catorce equipo-temporadas tienen 81 partidos en vez de 82:

| Temporada | Equipos | Partidos que faltan |
|---|---|---|
| 2017 | LAC, UTA | 1 |
| 2018 | BRK, DEN, GSW, MEM, NOP, UTA | 3 |
| 2023 | DEN, GSW, LAC, PHO | 2 |
| 2024 | CLE, PHI | 1 |

Coinciden exactamente con los 7 partidos en cuarentena de
`GAME_DATASET_ACQUISITION.md`: seis por `minutes_mismatch` (diferencias de 5 a
84 segundos entre la suma de jugadores y el total del equipo) y uno por
`player_sum_mismatch` (una pérdida de balón de diferencia).

Efecto medido al conciliar los totales de temporada con la suma de líneas de
partido:

| Temporada | Jugadores comparados | Difieren en partidos jugados |
|---|---|---|
| 2015, 2019–2022, 2025, 2026 | 3.847 | 0 |
| 2016 | 476 | 0 (3 difieren en 1 asistencia: incoherencia de la fuente) |
| 2017 | 486 | 22 |
| 2018 | 540 | 65 |
| 2023 | 539 | 40 |
| 2024 | 572 | 21 |

**Valoración.** Poner en cuarentena un partido cuyos números no cuadran es la
decisión correcta y está bien documentada. El problema es que **la base no
sabe que esos partidos existen**: no hay fila en `core.games` ni tabla de
incidencias. Un consumidor (la futura ruta de partidos, el predictor) no puede
distinguir "partido no cargado" de "partido que no se jugó", y verá a 148
jugador-temporadas con un partido menos que su total oficial sin explicación.
Para el predictor, la ausencia altera los días de descanso y la racha de dos
equipos por partido.

**Recomendación.** Registrar los partidos en cuarentena, sea como filas de
`core.games` con un estado propio y sin totales, sea en una tabla de calidad de
datos. Valorar una tolerancia explícita para `minutes_mismatch` de pocos
segundos, que es redondeo de la fuente y no un error de marcador: en los siete
casos el resultado final coincide.

---

### H-14 · Base sobrante `nba_f8006_tmp` — Baja — DEMOSTRADO

354 MB, copia completa en revisión `0009` (14.435 partidos, 474.309 líneas),
sin actividad desde el 2026-10-28 y sin conexiones. Su nombre no empieza por
`nba_test`, así que la guarda de carga la trata como persistente, y tampoco
entra en los nombres que acepta la vía de integración. Es un ensayo de F8-006
que no se limpió. Ocupa el 41 % del espacio de datos del servidor.

**Recomendación.** Que el propietario la elimine tras confirmar que no la
necesita. Para futuros ensayos, usar el prefijo `nba_test_tmp_`, que el resto
de herramientas ya reconoce.

---

### H-15 · Documentación de migraciones desfasada — Baja — DEMOSTRADO

- `MIGRATION_HEAD_HANDOVER.md` describe `nba` como situada en "`0009` — la
  cabeza del repositorio". La cabeza es `0012` desde el 2026-11-08.
- `SYSTEM_DESIGN.md` afirma que los comandos de `ml` usan "la misma guarda que
  los otros cargadores"; cinco de esos cargadores no la tienen (H-05).
- `OFFICIAL_STATS_SCHEMA.md` describe `birth_date` como un dato que se
  convierte; no se convierte (H-06).

Ninguna causa un fallo, pero las tres inducen a una conclusión falsa sobre el
estado real.

---

## 5. Lo que está bien — verificado

Esta sección no es cortesía: cada línea es una hipótesis de fallo que se
comprobó y no se cumplió.

### Integridad estructural

- 0 restricciones sin validar, 0 índices inválidos.
- 47 claves foráneas, todas `NO ACTION`: nada se borra en cascada por
  accidente.
- El validador del proyecto (`validate official-stats`) informa 0 en tablas o
  columnas ausentes, granos duplicados, huérfanos, códigos sintéticos, mezcla
  regular/postemporada, linaje y rangos numéricos. Su único fallo es
  `coverage_artifact_missing`: falla cerrado porque no se le pasó el artefacto
  de cobertura, que es el comportamiento diseñado.

### Identidad

- 2.693 jugadores, 0 sin identificador, 0 con el nombre de reserva, 0 con
  formato de identificador anómalo. Hay 10 nombres repetidos entre jugadores
  distintos, lo que confirma que el nombre no puede ser clave.
- 37 equipos; ningún `TOT` ni marcador `nTM` en `core`. Las cuatro
  restricciones `ck_core_*_not_synthetic` están presentes.
- Todo `player_season` tiene al menos un paso por equipo; todo paso tiene su
  fila de roster.
- El código de origen de los agregados es coherente con los pasos: los 1.633
  marcadores `2TM`–`5TM` coinciden con el número real de equipos en todos los
  casos. Los 3 jugadores con código real y dos equipos (`harrish01` 2023,
  `klebima01` 2025, `machasc01` 2013) estuvieron en la plantilla del segundo
  equipo sin jugar; es correcto.

### Estadísticas de temporada

- Totales: 0 violaciones de `fg ≤ fga`, `fg3 ≤ fg3a`, `ft ≤ fta`,
  `orb + drb = trb`, `fg2 + fg3 = fg`, `pts = 2·fg2 + 3·fg3 + ft`; 0 negativos;
  0 casos de `gs > g`; 0 porcentajes fuera de rango.
- **Total de temporada = suma de pasos** en partidos, puntos y minutos para las
  13.249 jugador-temporadas, sin que el sistema calcule nunca una a partir de
  la otra. Son dos fuentes independientes (página del jugador y páginas de
  equipo) que coinciden al 100 %.
- Las columnas repetidas entre familias (`g`, `mp`, `age`) coinciden entre
  `totals`, `advanced` y `per_game`; los puntos por partido coinciden con
  `pts / g`.
- Las 9 jugador-temporadas sin totales corresponden a jugadores que estuvieron
  en plantilla sin disputar un minuto.

### Partidos y box scores

- 14.435 partidos, todos `final`; 0 con fecha o código local distintos de los
  de su identificador; 0 fuera de la ventana de su temporada; 0 duplicados de
  fecha y equipos; ningún equipo juega dos veces el mismo día.
- Exactamente 2 totales de equipo por partido, con el lado correcto; 0 empates.
- Los minutos de equipo solo toman los valores posibles: 240 más múltiplos de
  25 por prórroga (hasta 4 prórrogas).
- 0 errores aritméticos en 28.870 totales de equipo y 307.064 líneas jugadas.
- Exactamente 5 titulares en cada uno de los 28.870 equipo-partidos.
- **Suma de jugadores = total del equipo** en puntos, tiros, rebotes y
  asistencias, en los 28.870 casos. Las pérdidas de balón del equipo superan a
  la suma de jugadores en 13.705 casos y nunca al revés, como establece la
  regla de negocio.
- Toda línea ausente tiene motivo y carece de estadísticas; toda línea jugada
  tiene segundos. Un "no jugó" y un "jugó con ceros" son siempre distinguibles.
- Todo jugador con línea jugada pertenece a la plantilla de ese equipo en esa
  temporada.
- Temporadas 2020 (1.059 partidos, burbuja incluida) y 2021 (72 por equipo)
  con los conteos correctos. Las tres finales de Copa están marcadas como sede
  neutral. La asistencia nula se concentra donde debe: 88 partidos de la
  burbuja y 577 de la temporada 2021.

### Seguridad y operación

- Puerto publicado solo en loopback.
- Sin SQL construido con datos de petición.
- Las columnas internas (`id`, claves foráneas, linaje, marcas de tiempo) no
  salen por la API.
- La vía de integración exige una autorización explícita y un nombre de base
  de la lista permitida **antes** de crear el motor: una configuración errónea
  no llega a abrir un socket.
- CI aplica las migraciones, ejecuta `alembic check` y hace ida y vuelta de la
  última revisión en cada cambio.
- Las migraciones destructivas son prudentes: `0008` borra sin `CASCADE`,
  `0011` se niega a ejecutarse si la columna tiene valores y bloquea la tabla
  durante la comprobación.

---

## 6. Rendimiento y escalabilidad

### Medido

| Consulta | Tiempo de ejecución | Plan |
|---|---|---|
| Lista de jugadores, última página (orden por nombre) | 2,2 ms | Recorrido secuencial de 2.693 filas + ordenación en memoria (286 kB) |
| Temporadas de un jugador | 0,10 ms | Índices únicos |
| Estadísticas por paso de un jugador-temporada | 0,15 ms | Índices únicos |
| Historial completo para ML (14.435 partidos con ambos totales) | 30 ms | Uniones hash, 2.459 bloques |
| *Futura:* registro de partidos de un jugador en una temporada | 4,9 ms en frío | Índice por `player_id`, 939 bloques leídos |
| *Futura:* partidos de una temporada, primera página | 0,86 ms | Índice por fecha + filtro |
| *Futura:* box score de un partido | 0,78 ms | Índice único `(game_id, player_id)` |
| *Futura:* búsqueda por nombre con `ILIKE '%…%'` | 0,68 ms | Recorrido secuencial |

Latencia extremo a extremo de la API en proceso, una vez abierta la conexión:
mediana de 4–6 ms por ruta, máximo observado 51 ms.

### Valoración

- **No hay ningún problema de rendimiento de consultas.** El conjunto de datos
  es pequeño (medio gigabyte) y cabe entero en memoria.
- Los índices existentes cubren todas las consultas actuales y las tres rutas
  planificadas que probé. **No recomiendo añadir ninguno ahora**: `core.games`
  no tiene índice por `season_id` y `core.players` no lo tiene por nombre, pero
  las consultas que los usarían tardan menos de 1 ms.
- La paginación por `OFFSET` es correcta a este tamaño (máximo 100 por página
  sobre 2.693 filas).
- `shared_buffers` es el valor por defecto (128 MB) para una base de 502 MB.
  Irrelevante con un solo usuario.
- El único problema de latencia real es la conexión (H-03).

### Proyección

`player_game_totals` crece ~39.500 filas y ~14 MB por temporada. Cargar hacia
atrás hasta 2000 añadiría ~590.000 filas y ~215 MB. Las claves `integer`
admiten 2.100 millones; la secuencia más avanzada va por 474.309. No hay límite
de escala a la vista en el alcance declarado (NBA).

El play-by-play (F8-015, en planificación) sí cambiaría el orden de magnitud:
unos 450 eventos por partido serían ~6,5 millones de filas para 2015–2026. Ese
sería el momento de revisar H-09 (linaje por fila) y de plantear
particionamiento por temporada, no antes.

---

## 7. Valoración de las decisiones de diseño

| Decisión | Valoración | Justificación |
|---|---|---|
| Caché HTML como fuente de verdad; base reconstruible (ADR 0003) | **Acertada** | Permite recargar sin red y cambiar parsers sin volver a descargar. Desplaza el riesgo a la caché (H-02) |
| Separación `core` / `stats` / `features` / `ml` | **Acertada** | Identidad, dato oficial y dato generado no se mezclan. Comprobado: 0 objetos generados en `stats` |
| Tablas anchas, una por familia y grano (32 tablas) | **Aceptable, con coste** | Es un espejo fiel de la fuente, fácil de validar contra la página. Coste: columnas repetidas entre familias (`g`, `mp`, `age`, `position`), 53 columnas muertas, cada cambio se multiplica por 4 granos. La alternativa (tabla larga clave-valor) sería peor para tipos y consultas. Mantener |
| Agregado de temporada guardado aparte, nunca calculado desde los pasos | **Acertada** | Los porcentajes y métricas avanzadas no son sumables. Verificado que ambas fuentes coinciden donde sí lo son |
| `TOT`/`nTM` como metadato y nunca como equipo, con `CHECK` en la base | **Acertada** | Regla semántica (no una lista) aplicada en código y en cuatro restricciones |
| Identidad de equipo por "era de código" sin linaje de franquicia | **Acertada para v1** | El caso de Charlotte demuestra que un único campo de linaje tendría que elegir bando. Dejar `franchise_id` vacío es honesto |
| Claves naturales de Basketball Reference como claves públicas; `id` interno oculto | **Acertada** | Sobrevive a una reconstrucción |
| Resultado del partido guardado una sola vez (`team_game_totals.pts`) | **Acertada** | Sin doble fuente de verdad |
| Claves foráneas compuestas para atar equipos y temporada del partido | **Acertada** | Hace imposible un partido con un equipo de otra temporada. El índice único redundante que exige está justificado |
| Línea de jugador referida a `core.players`, no a `player_team_seasons` | **Acertada** | Los inactivos y la temporada en curso no tienen jugador-temporada |
| Hora en ET sin convertir, fecha aparte | **Aceptable** | Conserva lo publicado. Quien necesite un instante absoluto tendrá que componerlo |
| `Numeric(10,4)` para todos los decimales | **Aceptable** | Exacto y con margen de sobra |
| `String(n)` con mucho margen | **Sin riesgo** | Máximos observados muy por debajo: nombre 24 de 200, premios 33 de 200, universidad 78 de 200 |
| Cargadores select-luego-insert portables en vez de `ON CONFLICT` | **Aceptable** | Correcto con un solo escritor; las restricciones únicas son la red de seguridad (R-02) |
| Predicciones inmutables, una por (partido, modelo, corte), un único modelo activo por índice parcial | **Acertada** | Trazabilidad completa. No verificada en la base real porque el esquema no está aplicado |
| Un solo rol superusuario | **Aceptable hoy, frágil** | Ver H-04 |
| Migración manual con aprobación del propietario | **Acertada, con efecto secundario** | Protege el archivo; a cambio, cada fusión con migración deja el sondeo en 503 (H-01) |

### Coherencia con los objetivos del proyecto

| Objetivo | Estado real |
|---|---|
| Archivo histórico de estadísticas oficiales 2000–2026 | **Cumplido** y verificado |
| API de solo lectura | **Parcial**: sirve 16 de las 35 tablas de `stats` (temporada regular). Postemporada (16 tablas, 88.496 filas) y partidos (503.179 filas, la tabla más grande del sistema) no tienen ruta. Están en `backlog/` (F6-014, F6-020, F6-021) |
| Datos por partido para el predictor | **Cumplido** para 2015–2026, salvo 7 partidos. No hay partidos de 2000–2014 |
| Predicciones previas al partido | **Bloqueado** por H-01 |
| Mantener la temporada en curso | **No iniciado** en la base real |
| Métricas generadas en `features` | **No iniciado**; las variables de ML se calculan en memoria, lo que es coherente con la regla |

Pruebas unitarias offline (`pytest -m "not integration and not live"`): **1.878
superadas, 0 fallos**, 296 excluidas por marcador, en 202 s. Ninguna de ellas
detecta H-05 ni H-06, lo que indica que ambos huecos tampoco están cubiertos por
pruebas.

---

## 8. Riesgos potenciales (no demostrados)

**R-01 · Sin límites de tiempo en las sesiones de la API.** Solo el sondeo de
disponibilidad fija `statement_timeout`. El servidor tiene
`statement_timeout = 0` e `idle_in_transaction_session_timeout = 0`. Una
consulta patológica ocuparía una de las 15 conexiones indefinidamente. Hoy
ninguna consulta se acerca; el riesgo crecerá con las rutas de partidos y la
búsqueda. Mitigación: fijar ambos límites en las opciones de conexión de la
API.

**R-02 · Escritores concurrentes.** Todos los `get_or_create` consultan y
luego insertan, sin bloqueo ni `ON CONFLICT`. Dos cargas simultáneas chocarían
en una restricción única y una abortaría: falla de forma segura, pero falla.
Nada impide lanzar dos cargas a la vez. Mitigación: un bloqueo consultivo
(`pg_advisory_lock`) al inicio de cada comando de carga.

**R-03 · Transacción única para todo el archivo.** Los backfills de
estadísticas envuelven la carga completa en un `session.begin()` con un punto
de guardado por página. Es seguro (todo o nada), pero un fallo tardío descarta
todo el trabajo y la transacción retiene versiones de fila durante minutos. El
backfill de partidos, que confirma por partido, es el patrón preferible.

**R-04 · Durabilidad del volumen.** Los datos viven en un volumen con nombre
de Docker. `docker compose down -v` lo destruye sin preguntar (la
documentación ya lo advierte). El contenedor no tiene política de reinicio.
Combinado con H-02, es el escenario de pérdida más probable.

**R-05 · Código heredado apuntando a la misma base.** `db_manager/db_conf.py`
(Peewee) usa por defecto la misma base, usuario y contraseña, y
`db_manager/` llama a `create_tables`. Ejecutar `scrape_main.py` crearía tablas
en `public` de `nba` y haría scraping en vivo sin pasar por el interlock de
aprobación. No se ejecutó. `AGENTS.md` lo marca como solo lectura, pero nada lo
impide técnicamente.

**R-06 · Dependencia del orden de carga en un nombre.** `clavevi01` se guarda
como "Victor Claver" o "Víctor Claver" según qué fuente se cargue primero.
Documentado en `BUSINESS_RULES.md`; es el único caso.

**R-07 · Orden dependiente de la configuración regional.** La lista de
jugadores ordena por `full_name` bajo `en_US.utf8`. Es determinista en este
servidor, pero una reconstrucción con otra intercalación cambiaría el orden de
las páginas.

---

## 9. Lo que no se pudo verificar

| Aspecto | Motivo |
|---|---|
| Que los volcados existentes se restauran correctamente | Restaurar es escribir |
| Existencia de copias fuera de este disco | Fuera del alcance observable |
| Contenido de `.env` más allá de que su URL coincide con la de por defecto | No se leen secretos |
| Que las revisiones `0010`–`0012` se aplican sin incidencias sobre `nba` | No se aplican migraciones. Sí comprobé sus precondiciones (H-01) y que CI las ejecuta sobre una base vacía |
| Las pruebas de integración contra PostgreSQL | Crean y borran bases |
| Exactitud de los datos frente a la fuente en vivo | No se contacta con Basketball Reference. La coherencia interna y entre páginas en caché sí está comprobada |
| Por qué `fg_pts_added` y `ts_pts_added` son nulos en postemporada | Requiere inspeccionar la tabla de playoffs de varias páginas; indicio de que la fuente no los publica |
| El árbol de trabajo `app` (`../Scraping nba-reference-app`) y el código web | Fuera del alcance: no accede a la base directamente por diseño |
| Comportamiento de `ml.predictions` con datos reales | El esquema no existe en `nba` |
| Cifrado de disco, permisos del sistema, configuración de Docker Desktop | Fuera del alcance observable |

---

## 10. Plan de mejora priorizado

Ordenado por impacto real dividido por esfuerzo. Ninguna acción se ejecutó.

### Ahora (minutos, sin cambio de esquema)

| # | Acción | Resuelve | Esfuerzo |
|---|---|---|---|
| 1 | Copiar `data/raw/` y `data/models/` a un segundo medio | H-02 | Minutos |
| 2 | `pg_dump -Fc` de `nba` fuera del disco | H-02 | Minutos |
| 3 | Cambiar el host de `DATABASE_URL` a `127.0.0.1` (`.env`, `.env.example`, valor por defecto) | H-03 | 3 líneas |
| 4 | Aplicar `0010`–`0012` con el procedimiento de traspaso | H-01 | El propietario, ~10 min |

### Pronto (una tarjeta pequeña cada una)

| # | Acción | Resuelve |
|---|---|---|
| 5 | Llamar a `require_load_target` en los cinco backfills históricos | H-05 |
| 6 | Abrir las conexiones de la API en solo lectura y con `statement_timeout` | H-04, R-01 |
| 7 | Convertir `birth_date` desde `csk` y hacer que un valor no convertible cuente como incidencia; recargar el roster | H-06 |
| 8 | Añadir a la validación un control de columnas íntegramente nulas | H-06, H-11 |
| 9 | `ANALYZE` y volcado al final de cada procedimiento de carga | H-10, H-02 |
| 10 | Eliminar `nba_f8006_tmp` | H-14 |
| 11 | Corregir los tres pasajes de documentación | H-15 |

### Cuando se toque el esquema (agrupar en una revisión)

| # | Acción | Resuelve |
|---|---|---|
| 12 | Linaje portable: clave de caché en lugar de ruta; mover el linaje de partido a `core.games` | H-07, H-09 |
| 13 | Upsert de estadísticas que solo escriba lo que cambia | H-08 |
| 14 | Registrar los partidos en cuarentena en la base | H-13 |
| 15 | `NOT NULL` en `basketball_reference_player_id` y unos pocos `CHECK` en `totals` | H-12 |
| 16 | Decidir el destino de `team_aliases`, `current_abbreviation`, `label` y las columnas `roster_*` duplicadas | H-11 |

### No hacer

- **No añadir índices.** Ninguna consulta medida los necesita.
- **No separar el rol de base de datos todavía.** La decisión de F6-018 se
  sostiene; el punto 6 da la mayor parte del beneficio sin su coste.
- **No rediseñar las tablas anchas.** El coste de la redundancia es bajo y la
  correspondencia uno a uno con la fuente es lo que hace verificable el archivo.
- **No particionar ni ajustar memoria del servidor.** No hay carga que lo
  justifique hasta que llegue el play-by-play.

---

## Apéndice A · Reproducción

Todas las consultas se ejecutaron así, lo que impide cualquier escritura:

```bash
docker exec -i \
  -e PGOPTIONS="-c default_transaction_read_only=on -c statement_timeout=120000" \
  nba_postgres psql -X -U <usuario> -d nba
```

Consultas clave:

```sql
-- H-01
SELECT version_num FROM public.alembic_version;
SELECT count(*) FROM core.players WHERE slug IS NOT NULL;

-- H-06
SELECT count(birth_date), count(*) FROM stats.player_team_season_roster;

-- H-07
SELECT cache_path FROM stats.player_season_totals LIMIT 1;
SELECT cache_path FROM stats.player_game_totals LIMIT 1;

-- H-08
SELECT count(*) FILTER (WHERE created_at <> updated_at), count(*), max(updated_at)
FROM stats.player_season_totals;

-- H-09
SELECT pg_size_pretty(sum(pg_column_size(source_url) + pg_column_size(cache_path)
                        + pg_column_size(parser_version) + 16)::bigint) AS linaje,
       pg_size_pretty(sum(pg_column_size(p.*))::bigint) AS fila
FROM stats.player_game_totals p;

-- H-10
SELECT c.relname, c.reltuples::int AS estimadas FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace WHERE n.nspname = 'core' AND c.relkind = 'r';

-- H-13: equipos con un número de partidos distinto de 82
SELECT s.season_year, ts.team_abbreviation, count(*)
FROM core.games g
JOIN core.seasons s ON s.id = g.season_id
JOIN core.team_seasons ts ON ts.id IN (g.home_team_season_id, g.away_team_season_id)
WHERE g.game_type = 'regular_season' AND s.season_year NOT IN (2020, 2021)
GROUP BY 1, 2 HAVING count(*) <> 82;

-- §5: suma de jugadores frente a total del equipo
WITH s AS (
  SELECT game_id, team_season_id, sum(pts) pts, sum(trb) trb, sum(ast) ast, sum(tov) tov
  FROM stats.player_game_totals WHERE participation = 'played' GROUP BY 1, 2)
SELECT count(*) FILTER (WHERE s.pts <> t.pts) AS pts_mal,
       count(*) FILTER (WHERE s.trb <> t.trb) AS trb_mal,
       count(*) FILTER (WHERE s.ast <> t.ast) AS ast_mal,
       count(*) FILTER (WHERE s.tov > t.tov)  AS tov_excede
FROM s JOIN stats.team_game_totals t USING (game_id, team_season_id);

-- §5: total de temporada frente a suma de pasos
WITH x AS (
  SELECT pts.player_season_id, sum(t.g) g, sum(t.pts) pts, sum(t.mp) mp
  FROM core.player_team_seasons pts
  JOIN stats.player_team_season_totals t ON t.player_team_season_id = pts.id GROUP BY 1)
SELECT count(*) FILTER (WHERE x.g <> s.g OR x.pts <> s.pts OR x.mp <> s.mp)
FROM x JOIN stats.player_season_totals s USING (player_season_id);
```

H-03 se reproduce midiendo `engine.connect()` con el host de la URL en
`localhost` y en `127.0.0.1`. H-04 se reproduce intentando una conexión de solo
lectura con la URL por defecto de `Settings`. H-05 se reproduce con
`grep -n require_load_target src/nba_data/cli/main.py`.

## Apéndice B · Configuración del servidor observada

| Parámetro | Valor | Comentario |
|---|---|---|
| `shared_buffers` | 128 MB | Por defecto |
| `work_mem` | 4 MB | Por defecto; suficiente (la mayor ordenación observada usa 1,3 MB) |
| `max_connections` | 100 | La API usa como máximo 15 |
| `statement_timeout` | 0 | Sin límite (R-01) |
| `idle_in_transaction_session_timeout` | 0 | Sin límite (R-01) |
| `fsync`, `full_page_writes`, `synchronous_commit` | `on` | Durabilidad correcta |
| `data_checksums` | `off` | No se detectaría corrupción silenciosa de disco |
| `archive_mode` | `off` | Sin recuperación a un punto en el tiempo |
| `ssl` | `off` | Aceptable solo en loopback |
| `password_encryption` | `scram-sha-256` | Correcto |
| `log_min_duration_statement` | −1 | No se registran consultas lentas |
| `autovacuum` | `on` | Ver H-10 |
| Extensiones | solo `plpgsql` | |
| Vistas, vistas materializadas, disparadores | 0 | |
| Comentarios de tabla o columna | 0 | El esquema solo está documentado fuera de la base |
