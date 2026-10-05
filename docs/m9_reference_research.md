# M9 — Revisión de referencias de UI y licencia

Revisión de repositorios consultados el 2026-10-05 para la fase Trade Sheet &
Human Execution Interface. Son referencias de producto/arquitectura; no se
copió código ni se añadió una dependencia externa.

| Referencia | Licencia y actividad observadas | Encaje / incompatibilidades | Clasificación |
|---|---|---|---|
| [FreqUI](https://github.com/freqtrade/frequi) | GPL-3.0; repositorio con actividad reciente y UI Vue/PrimeVue. | Buen ejemplo de estados de estrategia, controles y visibilidad de proceso. Está ligado al bot Freqtrade y a sus semánticas de exchange; la licencia no justifica copiar componentes a este proyecto. | STUDY ONLY |
| [TradingView Lightweight Charts](https://github.com/tradingview/lightweight-charts) | Apache-2.0; biblioteca de canvas pequeña y mantenida activamente. | Referencia para gráficos financieros con datos autorizados. M9 no muestra una serie inventada ni adopta la biblioteca porque no hay OHLCV autorizado que graficar. | STUDY ONLY |
| [OpenTerminal fork](https://github.com/Marcikschmid/OpenTerminal) | El fork revisado declara MIT. | Referencia de terminal financiera con varias áreas de producto; su alcance de plataforma completa sería desproporcionado para un cockpit individual de seis semanas. Verificar licencia/origen otra vez antes de reutilizar cualquier fork. | STUDY ONLY |
| [BackDash](https://github.com/sajalkmr/backdash) | MIT; repositorio pequeño, con 19 commits observados en la revisión. | Referencia de paneles de análisis/backtest. No resuelve el objetivo de ranking Actinver, la proveniencia PIT ni los gates M1/M7/M8. | STUDY ONLY |
| [QuantNova](https://github.com/yashvardhancse/QuantNova) | MIT; MVP inicial, con 49 commits observados en la revisión. | Referencia de flujo cuantitativo de investigación; no proporciona integración autorizada ni evidencia de plataforma/fills Actinver. | STUDY ONLY |
| [Ghostfolio](https://github.com/ghostfolio/ghostfolio) | AGPL-3.0; proyecto amplio y activamente mantenido. | Referencia de lectura de portafolio e historial. Su alcance de gestión patrimonial y obligaciones copyleft exceden la necesidad de este cockpit. | STUDY ONLY |

## Decisiones de diseño derivadas

- Priorizar un encabezado de competencia, una cola de decisión explícita,
  estados vacíos para radar/portafolio, un panel de evidencia y una cronología
  de eventos.
- Mantener auditoría y detalles de proveniencia accesibles desde una vista
  separada y una franja resumida en el inicio.
- No graficar precios, P&L, probabilidades o ranking si no vienen de un reporte
  con proveniencia verificable.
- No incluir órdenes, conexiones de exchange/broker, login al portal ni
  controles que aparenten ejecutar operaciones.
- Ningún código, activo ni dependencia de los seis proyectos se reutilizó.
