# M9 — Trade Sheet, reportes y cockpit

M9 completa el flujo de reporte humano: genera morning report, event update y
evening review con el mismo contrato versionado, conserva proveniencia y
auditoría append-only, y permite revisión en un cockpit responsive. La versión
actual **siempre emite `NO_TRADE`**: M7 no tiene señales financieras
promovidas, M8 solo entrega simulaciones/sin decisión, y el mapeo autenticado
de símbolos de plataforma sigue sin verificarse. Ningún resultado se carga al
portal Actinver.

## Instalación y reportes

Desde la raíz del repositorio:

```powershell
python -m pip install -e .
actinver-cockpit report --type morning --context examples/m9_empty_context.template.json
actinver-cockpit verify-audit
```

El contexto de ejemplo está intencionalmente vacío. Produce un documento
`NO_TRADE` con datos “no suministrados”; no es una captura del concurso ni una
fuente financiera. Para un reporte operativo, prepara un JSON conforme a
[`m9_context.schema.json`](../schemas/m9_context.schema.json) con un ID de corte
único, hora explícita, datos del concurso/portafolio capturados por una persona,
y hora/umbral de antigüedad de cada fuente.

```powershell
actinver-cockpit report --type morning --context context.json `
  --m7-result m7_result.json --m8-result m8_result.json `
  --output-dir reports/trade_sheets --audit-file reports/audit_trail/m9.jsonl

actinver-cockpit report --type event_update --context event_context.json `
  --event-snapshot m6_event_snapshot.json

actinver-cockpit report --type evening_review --context evening_context.json
```

Tipos admitidos: `morning`, `event_update`, `evening_review`. La CLI no
sobrescribe el archivo JSON de salida; cada documento recibe UUID, versión
`1.0.0` y revisión `1`. Se puede importar el archivo en la vista **Reportes**
del cockpit.

### Cortes M6

Los event snapshots se validan con el contrato de M6. Si se adjunta uno,
`as_of_utc` es obligatorio. El reporte exige que tanto `feature_available_time`
como `ingestion_time` sean anteriores o iguales al corte, selecciona la última
revisión visible en modo `system`, elimina duplicados de evento consistentes y
rechaza duplicados con extracciones en conflicto. Los eventos solo aparecen en
la cronología con fuente, calidad, URL, timestamps y puntuaciones del extractor;
no desbloquean una operación.

### Gates M7/M8 y frescura

La CLI conserva el SHA-256 exacto de los archivos M7/M8. Si M8 enlaza un
resultado M7, los bytes recibidos deben coincidir con ese digest. Un corte de
fuente posterior al reporte se rechaza. La frescura se calcula solo cuando hay
hora de observación, hora de corte y umbral explícito; si falta alguno, se marca
`UNKNOWN`. Una fuente supera su ventana solo si su edad exacta no rebasa el
umbral.

El contrato de salida
[`trade_sheet.schema.json`](../schemas/trade_sheet.schema.json) conserva
capital/ranking/brecha/sesiones, posiciones, estado de evidencia, eventos,
timestamp, frescura y los campos operativos solicitados (tamaño, entrada,
no-perseguir, stop, targets, horizonte, catalizador, probabilidad, confianza y
contribución a `P(final_rank=1)`). Mientras sea `NO_TRADE`, cada campo de acción
queda `null`; la razón y riesgos se muestran en texto. Los outputs sintéticos,
vacíos o stale nunca se convierten en órdenes.

## Auditoría

Cada reporte genera un evento en `reports/audit_trail/m9.jsonl`. Cada línea
registra UUID, tipo, objeto, SHA-256 exacto de los bytes del archivo, digest del
evento anterior y hash del evento actual sobre JSON canónico UTF-8. La CLI toma
un lock local, verifica toda la cadena antes de agregar y vuelve a verificar
después. Una línea incompleta, evento duplicado, digest manipulado o enlace roto
detiene la escritura.

```powershell
actinver-cockpit verify-audit --audit-file reports/audit_trail/m9.jsonl
```

La interfaz también puede cargar el JSONL localmente, verificar cada hash y
confirmar que el UUID y el hash de bytes del reporte coincidan con un evento.
Un hash demuestra integridad respecto al contenido registrado, no autentica a
quien lo creó ni a la fuente financiera.

## Actividad manual y atribución posterior

El operador puede registrar capturas de saldo y fills manuales según
[`post_trade_activity.schema.json`](../schemas/post_trade_activity.schema.json),
y generar un resultado:

```powershell
actinver-cockpit attribute --activity manual_activity.json `
  --trade-sheet reports/trade_sheets/morning_<id>.json `
  --output reports/post_trade/attribution_<id>.json
```

La variación de portafolio se calcula como
`saldo_final - saldo_inicial - flujos_netos_externos`, y el retorno se divide
por el saldo inicial si es positivo. El nominal y las comisiones son sumas
descriptivas de los fills reportados. Como hoy M9 está en `NO_TRADE` y no hay
contrafactual de no-operar ni leaderboard histórico PIT, la contribución causal
de la estrategia y a `P(final_rank=1)` queda `null`. La captura manual no se
autentica con el broker; la herramienta no calcula slippage real ni envía una
orden.

## Cockpit responsive

```powershell
cd frontend
npm ci
npm run dev
```

El cockpit trabaja localmente en el navegador: importa el JSON M9 y el registro
JSONL, muestra el corte, estado `NO TRADE`, valores ausentes, evidencia,
proveniencia, eventos y auditoría. El importador rechaza reportes que intenten
traer una acción distinta de `NO_TRADE` o un campo de orden no nulo. La vista no
envía archivos a un servidor externo ni ofrece botones de compra/venta/envío.

## Limitaciones y siguiente evidencia necesaria

- Gate empírico M6/M7/M8: `NEEDS_MORE_EVIDENCE`; sin corpus noticioso ni
  OHLCV/trades históricos autorizados, forecast por instrumento promovido,
  fills autenticados de práctica o leaderboard PIT completo.
- M1 conserva ambigüedades de reglas y no tiene mapeo autenticado a símbolos y
  series del simulador.
- Los estados de frescura dependen de timestamps y umbrales proporcionados por
  cada fuente; el hash no demuestra que esos valores sean auténticos.
- Post-trade attribution es contabilidad descriptiva, no atribución causal.

El siguiente paso externo es obtener y versionar, con autorización, datos
históricos PIT, mapping oficial de instrumentos, fills de práctica y snapshots
completos de leaderboard. Hasta entonces, mantener `NO_TRADE` y dejar cualquier
entrada en Actinver bajo control manual.

El tablero de estado versionado [`ACTINVER_CONTROL_TOWER.xlsx`](../reports/ACTINVER_CONTROL_TOWER.xlsx)
resume las fuentes disponibles y las brechas de evidencia en 21 hojas. Es una
captura del repositorio, no una conexión en vivo ni una captura autenticada de
la cuenta; sus valores actuales faltantes se mantienen como `UNKNOWN`.
