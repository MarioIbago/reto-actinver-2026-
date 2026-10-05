# Memo premercado — Reto Actinver — 6 de octubre de 2026

**Corte de preparación:** 5-oct-2026, 16:04:08 CDMX
**Decisión:** **NO_TRADE**
**Órdenes anticipadas:** **0**
**Universo revisado:** las 16 emisoras de la watchlist
**Ejecución:** exclusivamente manual; no se envía, programa ni modifica ninguna orden.

## Instrucción para mañana

No recomiendo dejar órdenes de compra anticipadas esta noche. Ninguna emisora
pasó todos los filtros de catalizador, precio, riesgo/recompensa, cotización
ejecutable, identidad exacta del simulador y estado actual de la cuenta. Los
precios son referencias retrasadas de barras regulares, no posturas bid/ask ni
precios Actinver. Al preparar este memo, las barras de las 14:00 tenían 124
minutos de antigüedad.

El corte usa la barra final programada 13:55–14:00 CDMX. Durante el horario de
verano estadounidense, el horario continuo publicado por BMV es 07:30–14:00
CDMX. La barra coincide con esa ventana, pero no autentica su precio de cierre
ni la serie del simulador. Una cotización posterior de EE. UU. fue posterior al
cierre regular y se excluyó.

## Lista de vigilancia

| Emisora / símbolo de mercado | Última barra | Cambio día | Condición de reevaluación |
|---|---:|---:|---|
| Boeing (BA) | USD 192.77 | -0.42% | Contrato PAC-3 de USD 14.7bn aún no definitizado; exigir ruptura y sostén 195.02–196 con volumen. Invalida <190; falta objetivo para R/R. |
| Broadcom (AVGO) | USD 362.875 | +2.18% | Esperar retroceso 353–357 y estabilización; no perseguir >363. No hubo catalizador nuevo. |
| NVIDIA (NVDA) | USD 239.11 | +2.19% | Esperar retroceso 232–235 y recuperación; resultados previos, no catalizador de hoy. |
| Applied Materials (AMAT) | USD 542.28 | +0.41% | Máximo 545.814 no alcanzó ruptura >546 con volumen. |
| Wells Fargo (WFC) | USD 81.435 | +1.22% | Tocó 80.50–81.20, pero cerró arriba. Morgan Stanley elevó EW→OW y Top Pick (fuente secundaria); no hay soporte confirmado ni R/R intradía suficiente. Resultados 13-oct. |
| América Móvil B (AMXB.MX) | MXN 20.09 | +3.77% | Arriba de zona 19.70–19.85; cerca del tope 20.10. Autenticar serie B de Actinver. |
| GAP B (GAPB.MX) | MXN 379.01 | +3.89% | Sobre el límite de no perseguir 376 y fuera de la entrada 366–370. No comprar arriba del límite. |
| Grupo México B (GMEXICOB.MX) | MXN 235.70 | +1.25% | Cobre subió en snapshot matutino; esperar consolidación y catalizador fresco. |
| Industrias Peñoles (PE&OLES.MX) | MXN 890.51 | +0.92% | Sin retroceso/consolidación; metales son contexto, no catalizador propio. |
| ASUR B (ASURB.MX) | MXN 433.32 | +1.61% | Adquisición CPC reportada el 28-sep; tráfico oficial localizado sigue en agosto. Exigir septiembre y confirmación técnica. |
| OMA B (OMAB.MX) | MXN 215.56 | +0.66% | Tráfico de septiembre programado para 8-oct, no mañana. |
| Volaris A (VOLARA.MX) | MXN 11.77 | -1.26% | Tráfico oficial de septiembre no verificado; precio débil, sin reversión con volumen. |
| Banorte O (GFNORTEO.MX) | MXN 187.41 | -1.49% | Sesión bajista con RVol 1.22; volumen no confirma reversión. |
| Walmex (WALMEX.MX) | MXN 46.44 | +0.58% | Sin venta mensual de septiembre verificada; resultados 3T programados para 27-oct. |
| Cemex CPO (CEMEXCPO.MX) | MXN 17.36 | -0.46% | Negociación condicional con Vicat del 1-oct, sin términos; esperar actualización primaria. |
| Alpek A (ALPEKA.MX) | MXN 14.56 | -1.29% | Extensión previa de 20 sesiones y sesión débil con RVol 0.37; esperar consolidación y catalizador nuevo. |

RVol es el volumen acumulado al cierre dividido por el promedio de las 19
sesiones previas al mismo corte. La tabla completa con apertura, máximos/mínimos,
volumen, fuentes y contexto está en el
[reporte comparativo de cierre](../../intraday/2026-10-05_1600_cdmx.md).

Hay discrepancias entre proveedores: para BA, una instantánea posterior al
cierre reportó máximo USD 194.15 y las barras de Yahoo USD 195.23; ninguna
confirma sostén sobre USD 195.02–196. Para AVGO, los mínimos fueron USD 354.14
y USD 356.14; el último cierre regular quedó cerca de USD 363 sin confirmación
de estabilización. Ninguna referencia se trata como ejecutable.

### R/R del escenario GAP que compartió el usuario

Para la entrada MXN 366–370, invalidación 356 y objetivo base 400, el R/R antes
de costos sería 2.14:1–3.40:1. Desde la barra final de 379.01 hasta 400 frente
a invalidación 356, el R/R aproximado es 0.91:1; además, supera el límite de no
perseguir 376. Por eso esa hipótesis no está activa. Para los demás nombres
faltan objetivos, invalidaciones o ambos; no inventé esos valores.

### Enmienda de investigación de WFC

Fuentes secundarias publicadas el 5-oct reportan que Morgan Stanley cambió la
recomendación de Wells Fargo de Equal Weight a Overweight, mantuvo el objetivo
en USD 102 y la designó Top Pick. El aviso oficial de Wells Fargo solo repite
que Q3 se publicará el 13-oct; no contiene guidance nueva. El precio tocó
USD 80.94, dentro de la zona de referencia, y cerró en USD 81.435 por encima
de ella. Frente al máximo intradía USD 82.22, el recorrido observado desde el
cierre fue USD 0.785 versus USD 0.935 hasta USD 80.50 (R/R diagnóstico 0.84:1).
El máximo y la frontera son referencias observadas, no un objetivo ni stop de
tesis aprobados; no usar el objetivo de analista de USD 102 como objetivo
temporal de operación. WFC sigue en WATCH: no dejar orden anticipada.
[TheFly vía TipRanks](https://www.tipranks.com/news/the-fly/wells-fargo-upgraded-to-overweight-from-equal-weight-at-morgan-stanley-thefly-news) ·
[Benzinga](https://www.benzinga.com/analyst-stock-ratings/upgrades/26/10/62160112/this-wells-fargo-analyst-turns-bullish-here-are-top-5-upgrades-for-monday) ·
[Wells Fargo: fecha oficial de resultados](https://newsroom.wf.com/news-releases/news-details/2026/Wells-Fargo-to-Announce-Third-Quarter-2026-Earnings-on-Oct--13-2026/default.aspx)

## Estado de cuenta y costos

El snapshot de MXN 1,000,000 compartido por el usuario está marcado como no
verificado y no se usa para dimensionar posiciones. Siguen desconocidos el
efectivo, posiciones, P&L, ranking, brecha al líder y costos efectivos. No hay
tamaño ni asignación calculados. La comisión de 0.10% más IVA disponible en
bases corresponde a un documento identificado como edición 2025; su aplicación
al simulador 2026 no se confirmó.

## Protocolo previo a cualquier decisión manual

1. En la sesión del 6-oct, actualizar noticias primarias, cotización y volumen.
2. Confirmar bid/ask, mercado, moneda y serie exacta dentro de Actinver.
3. Capturar valor de cuenta, efectivo, posiciones, P&L, ranking y costos.
4. Recalcular riesgo/recompensa con datos frescos; estos umbrales son puertas
   de reevaluación, no órdenes limitadas.
5. Si abre fuera de condición o falla una verificación, permanecer en NO_TRADE.

La GitHub Action valida el memo y archiva junto a él el informe comparativo. No
consulta datos en vivo, no usa IA y no se conecta a Actinver.

**Resultado:** NO_TRADE; 16 emisoras; órdenes: 0; portafolio no verificado.
**Siguiente paso:** revisión con datos frescos durante la sesión del 6-oct y
nueva decisión al superar cada puerta.
