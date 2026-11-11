# Auditoría integral del proyecto — 2026-11-10

Auditoría independiente del repositorio en el commit `b094613` (`main`, árbol
limpio). Este documento recoge qué se comprobó, qué problemas se encontraron y,
para cada uno, el cambio propuesto con el detalle suficiente para convertirlo en
una tarjeta.

La auditoría fue de solo lectura. No se modificó código, no se arrancó la base
de datos, no se contactó con Basketball Reference y no se ejecutó ninguna
operación Git que mute el repositorio.

**Seguimiento del 2026-11-11 (F8-022).** Este informe conserva las observaciones
del día 10. La parte de copias de seguridad de §3.5 se abordó después con un
comando repetible, copias de caché/modelos/informes verificadas por SHA-256 en
otro disco y ensayos de restauración. El procedimiento incluye copiar después
de cada adquisición, carga y escritura de modelos/predicciones; no hay
planificador automático ni copia fuera de la máquina. Evidencia y límites en
[Backup and recovery](BACKUP_AND_RESTORE.md). Los demás hallazgos siguen
pendientes salvo que su propia tarjeta documente otro resultado.

## Cómo leer este documento

Cada hallazgo lleva una etiqueta de certeza:

| Etiqueta | Significado |
|---|---|
| **Demostrado** | Comprobado leyendo el código o ejecutando una verificación; la evidencia se cita. |
| **Riesgo** | La condición existe en el código o en el entorno, pero el daño depende de algo que aún no ha ocurrido. |
| **Hipótesis** | No comprobado; hay que verificarlo antes de actuar. |

Ningún cambio de este documento está autorizado por el documento. Los que
implican acciones críticas según `AGENTS.md` (crear roles en la base de datos,
ejecuciones live, tocar la caché real) se señalan como tales y necesitan la
instrucción directa del propietario. Los cambios deben entrar por el ciclo
normal (`Plan this task: …` → `planning/` → `backlog/`); aquí no se asignan
identificadores de tarjeta.

---

## 1. Resumen

El proyecto es sólido en ingeniería y honesto en lo que afirma. Las
validaciones pasan, la CI está en verde y las cifras del informe del predictor
coinciden con los artefactos locales. No se encontró fuga temporal en las
variables del modelo.

La debilidad principal no es técnica sino de producto: el predictor existe y
escribe predicciones en `ml.predictions`, pero ni la API ni una web las sirven,
y el refresco de la temporada en curso no está operativo. El track `data` va
muy por delante del track `app`.

Los problemas técnicos más relevantes son tres: una página de error con HTTP
200 puede quedar archivada para siempre como si fuera válida; existe una ruta
de adquisición live con menos protecciones que las demás; y los activos que no
se pueden regenerar rápidamente (caché HTML, base de datos, artefacto del
modelo) viven en un solo disco sin rutina de copia.

### Tabla de hallazgos

| # | Hallazgo | Certeza | Importancia | Track |
|---|---|---|---|---|
| 1 | El producto no está cerrado de extremo a extremo | Demostrado | Alta | app + data |
| 2 | Una respuesta 200 de error puede envenenar la caché | Demostrado | Alta | data |
| 3 | `backfill acquire` queda fuera del interlock completo | Demostrado | Media-alta | data |
| 4 | El interlock de aprobación es de honor, no técnico | Riesgo | Media | shared |
| 5 | Activos irreemplazables en un solo disco | Riesgo | Media-alta | data / propietario |
| 6 | El ritmo del cliente se salta tras un error de transporte | Demostrado | Media (latente) | data |
| 7 | La métrica evaluada no es la que se servirá | Riesgo | Media | data |
| 8 | La API se conecta como superusuario | Riesgo (conocido) | Media; bloquea despliegue | app + data |
| 9 | Duplicación creciente en manifiestos y adquisiciones | Demostrado | Media | data |
| 10 | Documentación desfasada | Demostrado | Baja-media | cualquiera |
| 11 | Menores: empaquetado, dependencias, cobertura, licencia, términos de uso | Mixto | Baja | varios |

---

## 2. Qué se comprobó

### Ejecutado en esta auditoría

| Comprobación | Resultado |
|---|---|
| `uv run ruff check .` | Sin incidencias. |
| `uv run mypy src/nba_data` | Sin incidencias en 114 ficheros. |
| `uv run python scripts/validate_tasks.py` | `Task validation passed.` |
| `uv run pytest` | Código de salida 0. Se recogen 2.174 tests; 296 son de `tests/integration` y necesitan PostgreSQL, que no estaba arrancado, así que no se ejecutaron en local. |
| `gh run list` | Las 8 últimas ejecuciones de CI con éxito, incluida la de `b094613` en `main`. El workflow ejecuta el carril PostgreSQL con `alembic upgrade head`, `alembic check` y round-trip de la última revisión. |
| Informe ML local frente al documento | `reports/ml/f8-007/evaluation-2.json` tiene SHA-256 `f0968b863e78…`, modelo seleccionado `logistic`, log loss de test 0,6011821774 frente a 0,6874485159 del baseline, 1.230 partidos, 14.435 partidos de historia, huella de entrada `95d297abaf04…`. Todo coincide con `docs/ml/TEAM_PREDICTOR_EVALUATION.md`. |
| Integridad del artefacto | El SHA-256 de `data/models/logistic-team-pregame-v1-f369530d6c6e/model.joblib` coincide con `model_sha256` de su `metadata.json`. Temporadas de entrenamiento 2022–2026, scikit-learn 1.9.1. |
| Secretos | `git log --all -- .env` vacío; `git grep` de patrones de contraseña, token y clave sin resultados fuera de valores por defecto de desarrollo (`nba`/`nba`). |
| Ritmo del cliente tras un error | Reproducido con `httpx.MockTransport` (sin red); ver hallazgo 6. |
| Ayuda de `nba-data backfill acquire` | Solo expone `--execute-approved-manifest`; ver hallazgo 3. |

### Revisado leyendo código

`scraping/client.py`, `scraping/cache.py`, `scraping/cache_writer.py`,
`scraping/backfill_manifest.py`, `scraping/game_season_manifest.py`,
`scraping/game_season_acquisition.py`, `config/settings.py`, `db/session.py`,
`db/load_guard.py`, toda la capa `api/` de jugadores y estadísticas,
`api/services/readiness.py`, y todo `ml/` (`elo`, `splits`, `team_games`,
`team_features`, `models`, `evaluation`, `predict`, `artifact`, `inventory`),
además de las órdenes `ml` y `backfill` de `cli/main.py`.

### No verificado

- **El contenido real de la base `nba`.** El contenedor `nba_postgres` estaba
  parado y no se arrancó. Las cifras de filas de los documentos no se
  contrastaron con la base.
- **Los tests de integración en local.** Solo consta su resultado en CI.
- **Los parsers contra páginas reales.** Se revisaron los tests con fixtures
  recortadas, no la caché real.
- **Cualquier ruta live.** No se hizo ninguna petición externa.
- **Los loaders en detalle.** `loaders/games.py`, `team_season_stats.py` y
  `player_page_stats.py` no se leyeron línea a línea; su idempotencia consta en
  los documentos de validación y en los tests, no en esta auditoría.

---

## 3. Hallazgos y cambios propuestos

### 3.1 El producto no está cerrado de extremo a extremo

**Certeza:** demostrado. **Importancia:** alta.

**Qué pasa.** `docs/ml/PREDICTOR_PLAN.md` define el producto como una consulta
de enfrentamiento: elegir un partido y obtener la probabilidad de victoria de
cada equipo. Hoy:

- La API registra cinco routers: `health`, `teams`, `seasons`, `players` y
  `player_stats` (`src/nba_data/api/app.py`). No sirve partidos, box scores ni
  predicciones.
- Están en `tasks/backlog/` sin empezar: F6-014 (postemporada), F6-019
  (búsqueda por nombre), F6-020 (partidos y box scores), F6-021 (predicción),
  F6-022 (identidad de jugador), y toda la web: F7-002 a F7-005.
- `tasks/CROSS_TRACK.md` tiene tres entradas abiertas de `data` hacia `app`
  (F8-002 → F6-020, F8-014 → F6-020, F8-010 → F6-021).
- El worktree `app` (`../Scraping nba-reference-app`) está en `39a030a`, del
  2026-10-25, 21 commits por detrás de `main`.
- F8-008 (mantener al día la temporada en curso) y F8-020 (recuperación
  acotada) siguen en backlog, con la temporada 2026-27 ya empezada.

**Por qué importa.** El valor del trabajo de datos y de ML solo se materializa
cuando alguien puede consultar una predicción. Mientras tanto, cada tarjeta
nueva de `data` (F8-009, F8-015, F8-019) aumenta la distancia entre lo que la
base contiene y lo que se puede ver.

**Cambio propuesto.**

1. Reordenar prioridades para cerrar una rebanada vertical mínima antes de
   ampliar el modelo:
   1. F6-020 — rutas de partidos y box scores.
   2. F6-021 — ruta de predicción de un partido.
   3. F7-002 — andamiaje de la web.
   4. F7-005 — páginas de partidos y predicción.
   5. F8-008 (con F8-020 y el hallazgo 3.2 resueltos) — datos al día.
2. Dejar F8-009, F8-015 y F8-019 detrás de esa rebanada. Mejorar un modelo que
   nadie consulta tiene un retorno nulo hasta que exista la consulta.
3. Poner al día el worktree `app` con `origin/main` antes de empezar F6-020
   (operación Git: necesita la instrucción del propietario).

**Criterio de aceptación.** Con la base local cargada, una petición a la ruta
de predicción devuelve las probabilidades de un partido programado de 2026-27,
y una página de la web las muestra.

**Nota.** Esto es una recomendación de prioridad, no un defecto de código. La
decisión es del propietario.

---

### 3.2 Una respuesta 200 de error puede envenenar la caché

**Certeza:** demostrado en código. **Importancia:** alta.

**Qué pasa.** `validate_html_for_cache`
(`src/nba_data/scraping/cache_writer.py`) acepta cualquier cuerpo no vacío que
empiece por `<!doctype html` o `<html`. Una página de error, de mantenimiento
o de desafío anti-bot servida con HTTP 200 cumple esa condición.

El diseño de la caché agrava el efecto:

- `write_html_to_cache_safely` nunca sobrescribe un cuerpo existente.
- Los bucles de adquisición tratan `cache_path.exists()` como cobertura y no
  vuelven a pedir la página (`game_season_acquisition.py`, y los equivalentes
  de las demás rutas).

El resultado es que una respuesta mala queda archivada como válida para
siempre, y los recuentos de cobertura la cuentan como adquirida. El problema
está identificado en `tasks/planning/F8-021-…md`, pero la tarjeta sigue en
`planning/` y su alcance excluye expresamente las rutas antiguas ("No changes
to older acquisition commands").

**Por qué importa.** Las páginas de temporadas cerradas ya pasaron por los
parsers y los loaders, que habrían fallado con una página de error. El riesgo
real está en la ruta de la temporada en curso, que se ejecutará de forma
repetida y donde un fallo silencioso deja un hueco permanente en los datos que
alimentan las predicciones.

**Cambio propuesto.**

1. Promover F8-021 a `backlog/` resolviendo sus dos decisiones abiertas:
   - **Evidencia mínima de identidad por tipo de página.** Propuesta: para un
     box score, que el HTML contenga el identificador de partido solicitado
     (el canónico o el `og:url`) y las dos tablas de box básico; para una
     página de equipo-temporada, que el `h1` resuelva al equipo y año pedidos
     (el parser de `parsers/team_season.py` ya extrae ese `h1`); para un mes de
     calendario, lo que F8-013 ya comprueba.
   - **Procedimiento de recuperación no destructivo.** Propuesta: una orden de
     diagnóstico offline que recorra la caché, aplique el mismo contrato y
     liste las entradas que no lo cumplen, sin borrar nada. La retirada de una
     entrada mala la hace el propietario a mano (es una operación sobre datos
     reales).
2. Implementar la comprobación en una única función compartida de
   "pedir → validar contenido → escribir", en lugar de añadirla solo a la ruta
   de temporada actual. Ver hallazgo 3.9.
3. Ejecutar la orden de diagnóstico sobre la caché existente. Es offline y de
   solo lectura.

**Tests que debe traer.**

- 200 con HTML de error → la ejecución se detiene, no se escribe nada.
- 200 con una página válida de otro partido o equipo → se detiene.
- Tras el rechazo, una segunda ejecución con respuesta correcta escribe la
  página.
- Flags de aprobación, ritmo, techos e inmutabilidad de la caché intactos.

**Ficheros.** `scraping/cache_writer.py`,
`scraping/current_season_acquisition.py`, `scraping/game_season_acquisition.py`,
los parsers como fuente del contrato, y sus tests unitarios.

---

### 3.3 `backfill acquire` queda fuera del interlock completo

**Certeza:** demostrado. **Importancia:** media-alta.

**Qué pasa.** `AGENTS.md` describe el interlock como el conjunto de los flags
`--owner-approved`, el esquema de manifiesto y las guardas de adquisición.
Cinco órdenes de `acquisition` exigen `--owner-approved` y
`--execute-approved-manifest`. La orden `nba-data backfill acquire`
(`src/nba_data/cli/main.py`, función `backfill_acquire`) es distinta:

| Protección | Órdenes `acquisition acquire-*` | `backfill acquire` |
|---|---|---|
| `--owner-approved` | Sí | **No** |
| `--execute-approved-manifest` | Sí | Sí |
| Rechazo del User-Agent de ejemplo | Sí en `game_season` y `current_season` (comprobado) | **No**: no llama a ningún validador de ajustes |
| Escritura atómica y sin sobrescritura | `write_html_to_cache_safely` | **No**: usa `HtmlCache.set`, que escribe directamente en la ruta final |
| Validación mínima del HTML | `validate_html_for_cache` | **No** |
| Presupuesto de peticiones | `max_requests` en las rutas nuevas | **No** |

Lo que sí la limita: el manifiesto debe tener `status: approved`,
`approved_by_owner: true`, como máximo 5 URLs, solo páginas de equipo-temporada
de `basketball-reference.com` por HTTPS, y el cliente respeta el suelo de 6
segundos. El alcance del daño es pequeño; la inconsistencia con la regla
escrita es clara.

Además, `nba-data info` imprime "Phase 1 foundation CLI. No live scraping
commands are enabled.", que es falso: hay seis órdenes live.

**Cambio propuesto.** Elegir una de dos opciones; la primera es la recomendada.

- **Opción A — retirar la orden.** `backfill acquire` y `backfill dry-run` son
  el piloto inicial de 5 URLs (F4B). La adquisición de equipo-temporada ya
  tiene su ruta propia (`acquisition acquire-nba-team-seasons`). Retirar las
  dos órdenes, `acquire_backfill_manifest` y `run_backfill_acquisition`,
  conservando el validador de manifiesto solo si otros módulos lo usan.
  Comprobar antes qué tests y qué manifiestos de `tasks/manifests/` dependen de
  ella (`F4B-LIVE-001-pilot-team-season-20260525.json`,
  `tests/fixtures/manifests/approved_team_season_manifest.json`,
  `tests/unit/test_backfill_manifest.py`).
- **Opción B — igualarla.** Añadir `--owner-approved`, el rechazo del
  User-Agent de ejemplo, `validate_html_for_cache` y
  `write_html_to_cache_safely`, con `max_requests` igual al número de entradas.

En ambos casos, corregir el texto de `info` para que describa el estado real, y
el `help` del grupo `acquisition` ("Phase 4D-A acquisition planning
utilities"), que ya no describe lo que contiene.

**Atención.** `AGENTS.md` prohíbe renombrar, quitar o debilitar el interlock.
La opción A elimina una ruta live y la B la endurece; ninguna lo debilita. Aun
así, conviene que la tarjeta lo diga expresamente y que el propietario elija la
opción.

**Tests.** Opción A: los tests de la orden desaparecen con ella y el resto de
la suite sigue pasando. Opción B: un test por cada protección añadida, con el
mismo patrón que `tests/unit/test_game_season_acquisition.py`.

---

### 3.4 El interlock de aprobación es de honor, no técnico

**Certeza:** riesgo. **Importancia:** media.

**Qué pasa.** La aprobación de una ejecución live se compone de campos JSON del
manifiesto (`status`, `approved_at`, `approval_basis`, `approved_by_owner`) y
de flags de línea de órdenes. Un agente con acceso de escritura al repositorio
y a la terminal puede producir ambos igual que el propietario. Lo que de verdad
impide una ejecución no autorizada son las instrucciones de `AGENTS.md` y el
modo de permisos de la herramienta, no el código.

El interlock sí cumple bien otra función: hace imposible una ejecución live
*accidental* (un test, un comando mal copiado, una variable de entorno), y
obliga a que el alcance exacto quede escrito y revisable.

**Cambio propuesto.** No hace falta más maquinaria; hace falta describirlo con
precisión y, si se quiere, un único refuerzo barato.

1. En `AGENTS.md`, sección "Live-scraping approval gate", añadir una frase que
   diga qué garantiza y qué no: evita ejecuciones accidentales y fija el
   alcance; no autentica al propietario.
2. Refuerzo opcional, a decidir por el propietario: que las órdenes
   `acquire-*` exijan además una variable de entorno que solo se define en la
   sesión de terminal del propietario y que no está en `.env` ni en el
   repositorio. No es criptografía, pero separa "quien puede editar ficheros"
   de "quien lanzó la sesión".

**Track.** `shared`, porque toca `AGENTS.md`.

---

### 3.5 Activos irreemplazables en un solo disco

**Certeza:** riesgo. **Importancia:** media-alta.

**Qué pasa.** `.gitignore` excluye `data/raw/`, `data/models/`, `data/exports/`
y `reports/`. Eso es correcto para Git, pero significa que estos activos solo
existen en esta máquina:

| Activo | Dónde | Coste de regenerarlo |
|---|---|---|
| Caché HTML | `data/raw/html` | Semanas: decenas de miles de páginas a 10 peticiones por minuto, con aprobación del propietario por lote. |
| Snapshots de páginas cambiantes | `data/raw/snapshots` | No regenerable: son el estado de una página en un momento. |
| Base de datos `nba` | Volumen Docker `nba_postgres_data` | Horas de recarga offline desde la caché, si la caché existe. |
| Artefacto del modelo | `data/models/logistic-team-pregame-v1-f369530d6c6e` | Minutos si la base existe (la evaluación es determinista), pero `ml.model_versions` guarda su hash: sin el fichero exacto no se puede predecir. |
| Informes de ejecución | `reports/` | No regenerables: son la evidencia de las ejecuciones live. |

Las únicas copias documentadas son volcados puntuales anteriores a una
migración (`Projects/nba-backups/nba-before-0008.dump`, `-0009`,
`-f8003-2026`), en el mismo disco. No hay ninguna rutina periódica ni copia
fuera de la máquina. Un `docker volume rm`, un `docker compose down -v` o un
fallo de disco se llevan todo.

**Cambio propuesto.**

1. Un script `scripts/dev/backup.ps1` (y su equivalente en Bash si se quiere)
   que haga, en este orden:
   1. Volcado de la base dentro del contenedor y copia al host, que es el
      método que ya funcionó según `MIGRATION_HEAD_HANDOVER.md`:

      ```powershell
      docker compose exec -T postgres pg_dump -U nba -Fc -f /tmp/nba.dump nba
      docker cp nba_postgres:/tmp/nba.dump "$Destino\nba-$Fecha.dump"
      docker compose exec -T postgres rm /tmp/nba.dump
      ```

      No usar `>` desde PowerShell 5.1 para un volcado binario: la redirección
      recodifica la salida y corrompe el fichero.
   2. Verificación: `pg_restore -l` sobre la copia y comparación de `md5` entre
      el contenedor y el host.
   3. Copia incremental de `data/raw`, `data/models` y `reports` al destino
      (`robocopy /E /XO` sin `/MIR` ni `/PURGE`, para que un borrado accidental
      en origen no se propague).
   4. Un fichero de registro con fecha, tamaños y hashes.
2. El destino es un parámetro obligatorio, fuera del repositorio y, a ser
   posible, en otro disco o en un almacenamiento externo. El script se niega a
   escribir dentro del árbol de trabajo.
3. Un documento corto `docs/validation/BACKUP_AND_RESTORE.md` con: cuándo
   ejecutarlo (después de cada adquisición live y de cada carga a `nba`), cómo
   restaurar en una base desechable `nba_test_*` y comprobar recuentos, y qué
   no cubre.
4. Probar la restauración una vez en una base desechable. Una copia que nunca
   se ha restaurado no es una copia verificada.

**Acciones críticas.** Ejecutar el volcado lee la base persistente y no la
modifica, pero el script toca datos reales; la primera ejecución debería
hacerla el propietario. Escribir el script y el documento es trabajo seguro.

---

### 3.6 El ritmo del cliente se salta tras un error de transporte

**Certeza:** demostrado. **Importancia:** media, hoy latente.

**Qué pasa.** En `BasketballReferenceClient._get_from_network`
(`src/nba_data/scraping/client.py`, líneas 141–149), `_last_request_at` se
actualiza después de que `self._client.get(...)` devuelva una respuesta. Si la
llamada lanza una excepción (`ConnectTimeout`, `ReadTimeout`, error de red), la
marca no se actualiza y la siguiente petición no espera.

Reproducción sin red, con `httpx.MockTransport`, reloj y `sleeper` inyectados:

```text
1.ª petición  → ConnectTimeout
2.ª petición  → esperas registradas: []        (debería ser [6.0])
3.ª petición  → esperas registradas: [6.0]     (tras una respuesta, sí espera)
```

Hoy no produce una violación real porque todos los bucles de adquisición
revisados se detienen en la primera excepción. Pero la regla de `AGENTS.md`
("al menos 6 segundos entre peticiones") es una propiedad del cliente, y el
cliente no la garantiza. Cualquier código futuro que capture el error y
continúe la rompe sin darse cuenta.

Hay una variante entre procesos: `_last_request_at` empieza en `None`, así que
la primera petición de cada proceso sale sin espera. Relanzar una orden varias
veces seguidas (por ejemplo tras un fallo) produce peticiones sin separación.

**Cambio propuesto.**

1. Registrar el instante del intento pase lo que pase:

   ```python
   self._request_count += 1
   try:
       response = self._client.get(
           url,
           headers={"User-Agent": self.settings.scraper_user_agent},
           follow_redirects=self._follow_redirects,
       )
   finally:
       # Un intento fallido también ha tocado el servidor, o lo ha intentado.
       self._last_request_at = self._clock()
   ```

2. Test nuevo en `tests/unit/test_rate_limited_client.py`: una primera petición
   que lanza `httpx.ConnectTimeout`, una segunda correcta, y la aserción de que
   el `sleeper` recibió al menos `MINIMUM_SCRAPER_DELAY_SECONDS`.
3. Variante entre procesos, opcional y a valorar: persistir la hora de la
   última petición en un fichero pequeño fuera de la caché de páginas (por
   ejemplo junto a los informes de ejecución) y esperar al arrancar si han
   pasado menos de 6 segundos. Es más código y más superficie; solo merece la
   pena si se van a relanzar órdenes de forma automática.

**Atención.** Este cambio modifica el comportamiento de un componente del
interlock, endureciéndolo. Debe ir con su test y sin tocar los reintentos de
5xx ni el tratamiento de 429.

---

### 3.7 La métrica evaluada no es la que se servirá

**Certeza:** riesgo metodológico. **Importancia:** media.

No se encontró ningún error en el protocolo: los datos de entrenamiento son
estrictamente anteriores a cada temporada objetivo, la temporada de test se lee
después de la selección, y las variables usan solo resultados con fecha
anterior o igual a D−2 (comprobado en `team_features.py` y cubierto por
`test_changing_any_result_after_the_cutoff_leaves_every_feature_equal` y
vecinos). Un 67 % de acierto con log loss 0,60 es el rango esperable para un
modelo de equipos; no es una cifra sospechosa.

Lo que sigue son diferencias entre lo evaluado y lo que se va a publicar, y
puntos del protocolo que conviene dejar por escrito.

#### 3.7.a La población evaluada y la servida no coinciden

- La evaluación puntúa **todos** los partidos de temporada regular, incluidos
  los primeros de cada equipo, con las variables de ventana imputadas por la
  mediana.
- `predict.py` no emite predicción si alguno de los dos equipos tiene menos de
  5 partidos completos (`MIN_PRIOR_GAMES`), y retiene los partidos de sede
  desconocida o competición sin confirmar.
- En la evaluación el corte es siempre D−2 con todos los resultados cargados.
  En producción es `min(D−2, última fecha completa)`: una predicción emitida
  con una semana de antelación, o con la base atrasada, usa datos más viejos.

El 0,6012 es por tanto una cota de referencia, no la expectativa de lo
publicado.

**Cambio propuesto.** Una orden de solo lectura, `nba-data ml score-predictions`:

- Une `ml.predictions` con estado `available` con los partidos `final` y su
  resultado.
- Para cada partido y versión de modelo usa la fila de `cutoff_date` más
  reciente, e informa aparte por antigüedad del corte (días entre el corte y el
  partido), que es justo la variable que la evaluación no cubre.
- Calcula log loss, Brier, acierto e intervalos reutilizando
  `score_predictions` y `calibration_bins` de `ml/evaluation.py`.
- Compara con el baseline de tasa local y con la cifra de evaluación guardada
  en los metadatos del modelo.
- No escribe en la base. Sesión `REPEATABLE READ` de solo lectura, como
  `ml evaluate`.

Con unas semanas de temporada, esto dice si el modelo servido se comporta como
el evaluado.

#### 3.7.b La regla de calibración no tiene umbral

`_check_calibration` conserva el sigmoide si `calibrated < raw`. Se conservó
por una mejora de 0,6029236 a 0,6027633 (0,00016), mientras que la selección
entre modelos exige que todo el intervalo del 95 % quede por debajo de cero.
Además, el sigmoide se ajustó sobre las salidas del modelo entrenado para el
pliegue 2024 y se aplica al modelo final, entrenado con otras temporadas.

El efecto práctico es despreciable, pero añade una pieza al artefacto sin
evidencia de que ayude.

**Cambio propuesto.** No tocar el modelo activo (las reglas se fijaron antes de
ver resultados, y cambiarlas ahora sería ajustar a posteriori). Para la próxima
evaluación —la que traiga F8-009— registrar por adelantado en
`PREDICTOR_PLAN.md` que la calibración se conserva solo si el intervalo de la
diferencia queda entero por debajo de cero, igual que la selección.

#### 3.7.c La rejilla de la regresión logística toca el borde

`C = 0,01` fue el valor elegido en las tres ventanas y es el más pequeño de la
rejilla. El propio informe lo declara y no la amplió, que es lo correcto.

**Cambio propuesto.** En la próxima evaluación, extender la rejilla hacia abajo
(`0,001`, `0,003`) y declararlo antes de ejecutarla.

#### 3.7.d Falta un baseline externo

El modelo se compara con la tasa de victoria local y con Elo. No hay
comparación con cuotas de cierre del mercado, que son la referencia habitual de
"qué tan bueno es posible". Sin ella no se sabe cuánto margen queda.

**Cambio propuesto.** Opcional y de investigación: conseguir un histórico de
cuotas de cierre para una o dos temporadas y calcular su log loss sobre los
mismos partidos. Es una fuente externa nueva: necesita decisión del propietario
y va por `Plan this task`.

#### 3.7.e Limitaciones ya declaradas que conviene mantener visibles

- Los 7 partidos en cuarentena (`ml/inventory.py`) no están en `core.games`,
  así que las ventanas y el descanso de los equipos implicados ignoran un
  partido.
- Los playoffs no entran en la historia de Elo ni de las ventanas.
- El artefacto final se reentrena con 2022–2026 y hereda el calibrador de 2024.

No requieren cambio; sí que sigan documentadas donde están.

---

### 3.8 La API se conecta como superusuario

**Certeza:** riesgo, ya conocido (auditoría del 2026-09-08, hallazgo 2).
**Importancia:** media en local; bloquea cualquier despliegue.

**Qué pasa.** Hay un único rol, `nba`, superusuario, con contraseña `nba` por
defecto, y todos los componentes lo usan a través de `DATABASE_URL`. La API es
de solo lectura por construcción (solo GET, sesión que nunca hace commit,
consultas únicamente en `db/repositories/queries/`), pero la base no lo impone.
La mitad de red está cerrada: `docker-compose.yml` publica el puerto en
`127.0.0.1`.

F6-018, en backlog, propone dejarlo documentado en un ADR en lugar de
corregirlo. Su argumento principal es el coste: cada tabla que añada una
migración necesitaría un `GRANT`, o la API fallaría.

**Valoración.** Para un uso local de un solo propietario, la decisión de F6-018
es razonable. El argumento del coste, sin embargo, tiene solución estándar:
`ALTER DEFAULT PRIVILEGES` concede el permiso automáticamente a las tablas
futuras.

**Cambio propuesto.** Mantener F6-018 como está, y añadir al ADR la condición
que lo reabre y el diseño ya resuelto, para no rediseñarlo el día que haga
falta:

```sql
CREATE ROLE nba_api LOGIN PASSWORD '<fuera del repositorio>';
GRANT CONNECT ON DATABASE nba TO nba_api;
GRANT USAGE ON SCHEMA core, stats, ml, public TO nba_api;
GRANT SELECT ON ALL TABLES IN SCHEMA core, stats, ml TO nba_api;
GRANT SELECT ON public.alembic_version TO nba_api;
ALTER DEFAULT PRIVILEGES FOR ROLE nba IN SCHEMA core, stats, ml
    GRANT SELECT ON TABLES TO nba_api;
```

- `public.alembic_version` hace falta porque la sonda de readiness la lee.
- La API leería una variable propia (por ejemplo `API_DATABASE_URL`, con
  `DATABASE_URL` como valor por defecto), de modo que el cambio sea de
  configuración y no de código.
- Condición de reapertura: en cuanto la API o la base sean accesibles desde
  fuera de `127.0.0.1`, el rol de solo lectura deja de ser opcional.

**Acción crítica.** Crear un rol es una operación sobre la base persistente:
solo con instrucción directa del propietario. Escribir el ADR no lo es.

---

### 3.9 Duplicación creciente en manifiestos y adquisiciones

**Certeza:** demostrado. **Importancia:** media.

**Qué pasa.** Cada nueva adquisición se ha construido copiando la anterior para
no tocar una ruta ya validada. El resultado medido:

| Par de módulos | Similitud de líneas |
|---|---|
| `game_pilot_manifest.py` ↔ `game_season_manifest.py` | 0,58 |
| `game_pilot_acquisition.py` ↔ `game_season_acquisition.py` | 0,70 |
| `offline_player_stats_backfill.py` ↔ `offline_player_postseason_stats_backfill.py` | 0,73 |

- Cinco módulos de manifiesto y seis de adquisición suman unas 4.900 líneas.
- El escritor seguro de caché existe en tres copias: `cache_writer.py` y
  copias privadas en `nba_team_season_acquisition.py` y
  `player_page_acquisition.py` (lo dice el propio docstring de
  `cache_writer.py`).
- `PLACEHOLDER_USER_AGENT` y su comprobación están definidos por separado en
  `game_season_acquisition.py` y `current_season_acquisition.py`.
- `cli/main.py` tiene 1.631 líneas y el bloque de rechazo
  "`Refusing acquisition without --owner-approved…`" aparece cinco veces.

**Por qué importa.** La decisión de copiar fue prudente: protege rutas live ya
probadas. El coste aparece ahora: cada mejora de seguridad hay que aplicarla N
veces o aceptar que solo cubre la ruta nueva. F8-021 es el ejemplo: arregla la
ruta de temporada actual y deja las demás como están. El hallazgo 3.3 es el
mismo fenómeno visto desde el otro lado.

**Cambio propuesto.** Consolidar por capas, de menor a mayor riesgo, una
tarjeta por paso y sin cambiar comportamiento en ninguno:

1. **Validación de ajustes.** Un único
   `validate_live_acquisition_settings(settings)` con el rechazo del
   User-Agent de ejemplo y los límites de ritmo; las rutas lo llaman en lugar
   de su copia. Los tests existentes de cada ruta deben seguir pasando sin
   cambios.
2. **Paso de adquisición.** Una función `fetch_validate_write(client, cache,
   url, contract)` que encapsule pedir, validar el contenido (hallazgo 3.2) y
   escribir con `write_html_to_cache_safely`. Las rutas nuevas la adoptan
   primero.
3. **Escritor de caché.** Sustituir las dos copias privadas por
   `cache_writer.py`. El docstring advierte de que la copia compartida publica
   con una primitiva distinta (rechaza un destino existente); es un cambio de
   comportamiento solo bajo escritura concurrente, y hay que decirlo en la
   tarjeta.
4. **CLI.** Extraer el rechazo de flags a un único ayudante y partir
   `cli/main.py` en un módulo por grupo (`cli/acquisition.py`,
   `cli/backfill.py`, `cli/validation.py`, `cli/ml.py`), manteniendo nombres de
   órdenes y opciones.
5. **Manifiestos.** Dejar para el final, y solo si sigue creciendo: los
   contratos tienen diferencias reales (techos, temporadas admitidas, tipos de
   página) y unificarlos es donde más fácil es debilitar algo sin querer.

**Regla para todos los pasos.** Nada de esto puede relajar una comprobación.
Cada tarjeta debe listar las protecciones que toca y demostrar con los tests
existentes, sin editarlos, que siguen en pie.

---

### 3.10 Documentación desfasada

**Certeza:** demostrado. **Importancia:** baja-media.

| Dónde | Qué dice | Qué es cierto | Cambio |
|---|---|---|---|
| `docs/ml/PREDICTOR_PLAN.md`, cabecera | "Status: proposal, pending owner validation… Nothing in it is implemented." | Las etapas 1 a 3 están hechas y parte de la 5 (F8-010, F8-012 a F8-014). | Sustituir la cabecera por un estado por etapa, con la tarjeta que la cerró. |
| `README.md` | Describe scraper → PostgreSQL → API. No menciona partidos, box scores, ML ni las órdenes `nba-data ml`. | Existen `ml evaluate`, `register-model`, `activate`, `predict`, y los esquemas `ml` y de partidos. | Añadir una sección "Predictor" con las cuatro órdenes y enlaces a `PREDICTOR_PLAN.md` y `TEAM_PREDICTOR_EVALUATION.md`; añadir ambos a "Key docs". |
| `pyproject.toml`, `description` | "…scraping, caching, parsing, and analytics." | Incluye un predictor y una API. | Actualizar la descripción. |
| `nba-data info` | "No live scraping commands are enabled." | Hay seis órdenes live. | Ver hallazgo 3.3. |
| `src/nba_data/ml/splits.py`, docstring | "calibration and selection 2025" | `CALIBRATION_SEASON = 2024`; el sigmoide se ajusta en 2024 y se comprueba en 2025. | Corregir la frase: "calibración ajustada en 2024 y comprobada en 2025; selección en 2025". |
| `docs/ml/TEAM_PREDICTOR_EVALUATION.md` | "scored once"; "Two runs gave a byte-identical report". | En `reports/ml/f8-007/` hay `evaluation.json` (20:22) y `evaluation-2.json` (20:45) con hashes distintos. La diferencia es solo de formato: el segundo añade `input_sha256`, `history_only_game_ids_by_season`, `calibration_bins` por pliegue y la lista de cuarentenas. Las métricas y el artefacto son los mismos. | Añadir una frase que lo explique: hubo una ejecución anterior con un formato de informe más corto y las mismas cifras. |
| `AGENTS.md`, rutas legadas | Cita `etl_process.ipynb`. | `.gitignore` excluye `*.ipynb`; en la raíz hay `internet_proyect_tocheck.ipynb` (1,7 MB) sin seguimiento. | Aclarar qué cuadernos existen y cuáles son referencia. Cambio `shared`. |

Ninguno de estos cambios toca comportamiento. Pueden ir en una sola tarjeta de
documentación, salvo el de `AGENTS.md`, que es `shared`.

---

### 3.11 Menores

**3.11.a La readiness depende de ficheros fuera del paquete — riesgo.**
`api/services/readiness.py` localiza `alembic.ini` con
`Path(__file__).resolve().parents[4]`, es decir, en la raíz del checkout.
`pyproject.toml` empaqueta solo `src/nba_data`. Una API instalada desde el
wheel no encontraría `alembic.ini` ni `alembic/versions`, la sonda caería en el
`except Exception` y respondería 503 siempre. Hoy la API solo se ejecuta desde
el checkout, así que no falla. Cambio: o bien incluir `alembic.ini` y
`alembic/` en el wheel (`[tool.hatch.build.targets.wheel.force-include]`) y
resolverlos como recursos del paquete, o bien documentar en
`API_ARCHITECTURE.md` que la API se ejecuta solo desde el checkout. Decidirlo
cuando exista un plan de despliegue.

**3.11.b `scikit-learn` es dependencia de runtime de todo el paquete —
demostrado.** `tests/unit/test_ml_dependency_boundary.py` impide que la API lo
importe, pero instalar la API instala igualmente scikit-learn, numpy y scipy.
Cambio: moverlo a un extra opcional (`[project.optional-dependencies] ml`) y
que las órdenes `ml` den un mensaje claro si falta. Toca `pyproject.toml` y
`uv.lock`: tarjeta `shared`.

**3.11.c No se mide la cobertura — demostrado.** No hay `pytest-cov` ni umbral
en CI. Con 2.174 tests la cobertura es probablemente alta, pero no se sabe
dónde no llega. Cambio: añadir `pytest-cov` al grupo `dev` e informar la
cobertura en CI sin umbral al principio; fijar un umbral solo después de ver la
cifra. `shared`.

**3.11.d `mypy` solo cubre `src/nba_data` — demostrado y deliberado.** El
workflow lo declara. `scripts/` contiene código que protege operaciones reales
(`preflight_migration_data.py`, `claim_task.py`, `validate_tasks.py`). Cambio:
ampliar el alcance a `scripts/`; dejar `tests/` fuera.

**3.11.e No hay fichero `LICENSE` — demostrado.** Sin licencia, el código es
"todos los derechos reservados" por defecto. Si el repositorio es o será
público, conviene decidirlo. Decisión del propietario.

**3.11.f Términos de uso de Basketball Reference — hipótesis por comprobar.**
Ningún documento del repositorio trata los términos de uso de Sports Reference;
solo se mencionan los de NBA.com (ADR 0020, `PREDICTOR_PLAN.md`). El proyecto
cumple el límite de ritmo publicado, pero el ritmo no es lo único que suelen
regular esos términos: también el uso de los datos para construir bases de
datos derivadas, para entrenar modelos y para redistribuirlos. No se ha
verificado qué dicen hoy. Cambio: que el propietario lea los términos y la
política de uso de datos vigentes, y registre la conclusión en un ADR. Importa
sobre todo si la API o la web llegan a ser públicas, porque entonces se
redistribuyen estadísticas obtenidas del sitio.

**3.11.g `HtmlCache.set` no es atómico — demostrado, impacto bajo.** Escribe el
gzip directamente en la ruta final. Una interrupción a mitad deja un fichero
truncado que `HtmlCache.get` intentará leer como válido. Solo lo usa la ruta
del hallazgo 3.3 y `BasketballReferenceClient.fetch` cuando se le pasa una
caché. Se resuelve con el hallazgo 3.3 (opción A) o haciendo que `set` escriba
en temporal y renombre.

**3.11.h La clave de caché depende de la URL literal — riesgo bajo.**
`path_for_url` hace SHA-256 de la URL tal cual; `https://basketball-reference.com/x`
y `https://www.basketball-reference.com/x` son entradas distintas. Los
manifiestos nuevos exigen el host con `www.`; el del piloto acepta ambos. Sin
cambio propuesto mientras los manifiestos sigan fijando el host.

**3.11.i Peso del proceso — observación, no defecto.** El flujo de trabajo
tiene su propio código y pruebas (`validate_tasks.py` 946 líneas,
`claim_task.py` 303, sus tests 1.340), 18 ficheros de skills y 20 ADR. Para un
proyecto local de un solo propietario es mucho, pero funciona: 70 tarjetas
cerradas, CI estable, historial limpio. Lo único que cabe vigilar es que el
proceso no consuma el tiempo que le falta al track `app` (hallazgo 3.1).

---

## 4. Lo que está bien y conviene no romper

- **Separación de capas en la API.** Routers, servicios y consultas están
  separados; los mensajes de error son cadenas fijas que no interpolan entrada
  del usuario; las columnas internas se excluyen por lista explícita
  (`UNPUBLISHED_COLUMNS`).
- **Readiness que nunca responde 500.** La sonda convierte cualquier fallo en
  un resultado y acota el tiempo en la base con `statement_timeout` y en la
  conexión con `connect_timeout`.
- **Protocolo de evaluación fijado de antemano.** Selección por intervalo de
  bootstrap por bloques semanales, preferencia por el modelo más simple,
  temporada de test leída al final, inventario de partidos que detiene la
  evaluación si falta uno.
- **Variables sin fuga.** Corte D−2, ventanas que se reinician por temporada,
  tasas como cociente de acumulados, `None` en lugar de cero cuando no hay
  datos.
- **Artefactos y publicaciones que no sobrescriben.** `save_artifact`,
  `publish_text` y `write_html_to_cache_safely` rechazan un destino existente
  distinto; `load_artifact` comprueba el hash antes de deserializar.
- **Predicciones que no se reescriben.** Clave única por partido, modelo y
  corte con `ON CONFLICT DO NOTHING`; un partido ya jugado conserva la
  predicción que se emitió.
- **Guarda de carga.** `require_load_target` impide cargar una base persistente
  desde código que no esté en `origin/main` o con cambios sin confirmar.
- **CI que no puede pasar en vacío.** `NBA_DATA_REQUIRE_POSTGRES_INTEGRATION`
  convierte en fallo cualquier salto por entorno.

---

## 5. Orden de trabajo recomendado

| Orden | Cambio | Hallazgo | Esfuerzo | Acción crítica |
|---|---|---|---|---|
| 1 | Marcar el instante de la petición en `finally` + test | 3.6 | Muy bajo | No |
| 2 | Corregir documentación desfasada y el texto de `info` | 3.10, 3.3 | Bajo | No |
| 3 | Script y documento de copia; primera copia y restauración de prueba | 3.5 | Bajo | La ejecución, sí |
| 4 | Retirar o igualar `backfill acquire` | 3.3 | Bajo | No (decisión del propietario sobre la opción) |
| 5 | Validación de identidad del contenido en una función compartida; diagnóstico offline de la caché | 3.2, 3.9 | Medio | No |
| 6 | Rutas de partidos y de predicción en la API | 3.1 | Medio | No |
| 7 | Web mínima con la página de predicción | 3.1 | Medio-alto | No |
| 8 | Refresco de la temporada en curso operativo | 3.1 | Medio | Las ejecuciones live, sí |
| 9 | `ml score-predictions` | 3.7.a | Bajo-medio | No |
| 10 | Consolidación por capas de adquisiciones y CLI | 3.9 | Medio, repartido | No |
| 11 | ADR del rol de la base con el diseño de solo lectura | 3.8 | Bajo | Crear el rol, sí |
| 12 | Términos de uso, licencia, cobertura, extra `ml`, empaquetado | 3.11 | Bajo cada uno | No |

Los pasos 1 a 4 son pequeños e independientes. El 5 debería ir antes del 8,
porque el refresco continuo es donde una página mala hace más daño. Los pasos 6
y 7 son del track `app` y pueden avanzar en paralelo con el 5 en su propio
worktree.
