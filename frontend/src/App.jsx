import { Fragment, useRef, useState } from "react";

const NAV = [
  { id: "overview", label: "Vista general", icon: "home" },
  { id: "reports", label: "Reportes", icon: "reports" },
  { id: "evidence", label: "Evidencia", icon: "evidence" },
  { id: "audit", label: "Auditoría", icon: "audit" },
];

const DEFAULT_EVIDENCE = {
  m1_symbol_mapping: { status: "UNVERIFIED", detail: "El mapeo de símbolos de la plataforma no está autenticado." },
  m7: { status: "NO_PROMOTED_SIGNALS", detail: "M7 no tiene señales financieras promovidas." },
  m8: { status: "SIMULATION_ONLY", detail: "M8 está limitado a simulaciones y no emite decisiones." },
};

const EVENT_LABELS = {
  earnings_release: "Resultados",
  earnings_guidance: "Guía de resultados",
  revenue_guidance: "Guía de ingresos",
  dividend: "Dividendo",
  merger_acquisition: "Fusión o adquisición",
  capital_raise: "Aumento de capital",
  regulatory: "Regulación",
  litigation: "Litigio",
  product_launch: "Lanzamiento de producto",
  management_change: "Cambio directivo",
  macro_policy: "Política macroeconómica",
  macro_data: "Dato macroeconómico",
  fx_commodity: "Divisas o materias primas",
  index_rebalance: "Rebalanceo de índice",
  trading_halt: "Suspensión de mercado",
  actinver_rule_change: "Cambio en reglas del concurso",
  other: "Otro evento",
};

const REPORT_TYPES = {
  morning: "Morning report",
  event_update: "Actualización de evento",
  evening_review: "Revisión de cierre",
};

const FLOW_STEPS = [
  { code: "01 / INPUT", title: "PIT DATA", status: "NO SNAPSHOT" },
  { code: "02 / ALPHA", title: "M7 SIGNAL", status: "0 PROMOTED" },
  { code: "03 / MODEL", title: "M8 RANK", status: "SIMULATION" },
  { code: "04 / GATE", title: "M9 REPORT", status: "NO_TRADE" },
  { code: "05 / USER", title: "ACTINVER", status: "MANUAL ONLY" },
];

function Icon({ name, size = 20 }) {
  const paths = {
    home: <><path d="m3 10 9-7 9 7"/><path d="M5 9.5V20h14V9.5"/><path d="M9 20v-6h6v6"/></>,
    reports: <><path d="M8 3H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V8z"/><path d="M8 3v5h5"/><path d="M8 13h8M8 17h8"/></>,
    evidence: <><path d="M12 3 20 6v5c0 5-3.4 8.2-8 10-4.6-1.8-8-5-8-10V6z"/><path d="m9 12 2 2 4-4"/></>,
    audit: <><path d="M5 3h10l4 4v14H5z"/><path d="M14 3v5h5M8 12h8M8 16h8"/><path d="m8 8 1 1 2-2"/></>,
    warning: <><path d="m10.3 3.7-8 14A1.5 1.5 0 0 0 3.6 20h16.8a1.5 1.5 0 0 0 1.3-2.3l-8-14a2 2 0 0 0-3.4 0Z"/><path d="M12 9v4M12 17h.01"/></>,
    cash: <><ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v5c0 1.7 3.6 3 8 3s8-1.3 8-3V5M4 10v5c0 1.7 3.6 3 8 3 1.4 0 2.8-.2 4-.5M4 15v4c0 1.7 3.6 3 8 3 1.4 0 2.8-.2 4-.5"/></>,
    rank: <><path d="M12 3v18M5 7h14M6 7l-4 7h8zM18 7l-4 7h8zM8 21h8"/></>,
    gap: <><path d="M4 18V9M10 18V5M16 18v-7M22 18V3"/></>,
    calendar: <><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M16 3v4M8 3v4M3 10h18"/></>,
    target: <><circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="4"/><path d="M12 2v4M22 12h-4M12 22v-4M2 12h4"/></>,
    search: <><circle cx="10.8" cy="10.8" r="7.2"/><path d="m16 16 5 5"/></>,
    portfolio: <><path d="M12 3v9h9"/><path d="M20.5 15a9 9 0 1 1-8.5-12"/></>,
    bell: <><path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9"/><path d="M10 21h4"/></>,
    upload: <><path d="M12 16V4M7 9l5-5 5 5"/><path d="M4 15v4a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-4"/></>,
    file: <><path d="M5 3h10l4 4v14H5z"/><path d="M14 3v5h5M8 12h8M8 16h8"/></>,
    check: <><path d="m5 12 4 4L19 6"/></>,
    clock: <><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></>,
    arrow: <><path d="M5 12h14M13 6l6 6-6 6"/></>,
  };
  return <svg aria-hidden="true" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">{paths[name] || paths.file}</svg>;
}

function stableStringify(value) {
  if (value === null || typeof value !== "object") return JSON.stringify(value);
  if (Array.isArray(value)) return `[${value.map(stableStringify).join(",")}]`;
  return `{${Object.keys(value).sort().map((key) => `${JSON.stringify(key)}:${stableStringify(value[key])}`).join(",")}}`;
}

async function sha256(buffer) {
  if (!globalThis.crypto?.subtle) throw new Error("SHA-256 requiere abrir el cockpit en localhost o un origen seguro.");
  const digest = await globalThis.crypto.subtle.digest("SHA-256", buffer);
  return Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, "0")).join("");
}

async function hashText(text) {
  return sha256(new TextEncoder().encode(text));
}

function validateTradeSheet(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("El archivo debe contener un objeto JSON.");
  if (value.schema_version !== 1 || !REPORT_TYPES[value.report_type]) throw new Error("El reporte no cumple la versión 1 del contrato M9.");
  if (value.decision_status !== "NO_TRADE" || value.decision?.action !== "NO_TRADE") {
    throw new Error("El cockpit bloqueó el archivo: solo muestra reportes NO_TRADE de la versión actual.");
  }
  if (typeof value.report_id !== "string" || !value.created_at_utc || !value.evidence || !value.provenance) {
    throw new Error("Faltan campos requeridos de decisión, evidencia o proveniencia.");
  }
  const nullFields = ["symbol", "target_size_actipesos", "entry_range_actipesos", "no_pursue_above_actipesos", "stop_or_invalidation", "targets_actipesos", "exit_logic", "horizon_sessions", "catalyst", "probability_estimate", "confidence", "estimated_contribution_to_p1"];
  if (nullFields.some((key) => value.decision[key] !== null)) throw new Error("El reporte contiene campos de operación no permitidos por el estado NO_TRADE.");
}

async function verifyAuditLog(text) {
  if (text.length === 0) return { valid: true, events: [], tail: null };
  if (!text.endsWith("\n")) throw new Error("La última línea del registro está incompleta.");
  const lines = text.split(/\r?\n/).filter(Boolean);
  const events = [];
  const ids = new Set();
  let previous = null;
  for (let index = 0; index < lines.length; index += 1) {
    let event;
    try { event = JSON.parse(lines[index]); } catch { throw new Error(`La línea ${index + 1} no es JSON válido.`); }
    if (!event || typeof event !== "object" || Array.isArray(event)) throw new Error(`La línea ${index + 1} no es un evento JSON.`);
    if (typeof event.event_id !== "string" || ids.has(event.event_id)) throw new Error(`Identificador de evento inválido o duplicado en la línea ${index + 1}.`);
    if (!event.occurred_at_utc || !event.object_id || !["TRADE_SHEET_CREATED", "POST_TRADE_ATTRIBUTION_CREATED"].includes(event.event_type)) throw new Error(`Faltan campos de auditoría en la línea ${index + 1}.`);
    if (event.previous_event_sha256 !== previous) throw new Error(`La cadena de hashes se rompe en la línea ${index + 1}.`);
    const expected = await hashText(stableStringify(Object.fromEntries(Object.entries(event).filter(([key]) => key !== "event_sha256"))));
    if (event.event_sha256 !== expected) throw new Error(`El hash del evento no coincide en la línea ${index + 1}.`);
    if (!/^[0-9a-f]{64}$/.test(event.object_sha256 || "")) throw new Error(`El hash del objeto no es válido en la línea ${index + 1}.`);
    ids.add(event.event_id);
    previous = event.event_sha256;
    events.push(event);
  }
  return { valid: true, events, tail: previous };
}

function formatMoney(value) {
  if (value === null || value === undefined || !Number.isFinite(Number(value))) return "No disponible";
  return new Intl.NumberFormat("es-MX", { style: "currency", currency: "MXN", maximumFractionDigits: 0 }).format(Number(value));
}

function formatDate(value, includeTime = true) {
  if (!value) return "Sin dato";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Fecha inválida";
  return new Intl.DateTimeFormat("es-MX", includeTime ? { dateStyle: "medium", timeStyle: "short", timeZone: "America/Mexico_City" } : { dateStyle: "medium", timeZone: "America/Mexico_City" }).format(date);
}

function metricValue(label, report) {
  const competition = report?.competition;
  if (label === "Capital") return competition?.capital_actipesos == null ? "No suministrado" : formatMoney(competition.capital_actipesos);
  if (label === "Posición") return competition?.rank == null ? "No disponible" : `${competition.rank}°`;
  if (label === "Brecha") return competition?.gap_to_first_actipesos == null ? "No disponible" : formatMoney(competition.gap_to_first_actipesos);
  return competition?.sessions_remaining == null ? "No suministradas" : `${competition.sessions_remaining} sesiones`;
}

function freshnessLabel(status) {
  if (status === "CURRENT") return "En ventana";
  if (status === "STALE") return "Stale";
  return "Desconocida";
}

function sourceStatusLabel(item) {
  const value = item?.status || "NOT_SUPPLIED";
  if (value === "NOT_SUPPLIED") return "No disponible";
  if (value === "NO_PROMOTED_SIGNALS") return "Sin señales promovidas";
  if (value === "SIMULATION_ONLY") return "Solo simulación";
  if (value === "NO_DECISION") return "Sin decisión";
  if (value === "NEEDS_MORE_EVIDENCE") return "Falta evidencia";
  if (value === "UNVERIFIED") return "Sin verificar";
  if (value === "PASS") return "PASS";
  return value.replaceAll("_", " ");
}

function MetricCard({ icon, label, value }) {
  return <article className="metric-card">
    <div className={`metric-icon ${icon}`}><Icon name={icon} size={19} /></div>
    <div className="metric-copy"><span className="metric-label">{label}</span><strong>{value}</strong></div>
    <span className="metric-foot" aria-hidden="true">—</span>
  </article>;
}

function SectionTitle({ icon, title, action }) {
  return <div className="section-title"><div className="section-title-label"><Icon name={icon} size={20} /><h2>{title}</h2></div>{action}</div>;
}

function EmptyState({ icon, title, detail }) {
  return <div className="empty-state"><div className="empty-icon"><Icon name={icon} size={35} /></div><strong>{title}</strong><p>{detail}</p></div>;
}

function TradingFlowDiagram() {
  return <article className="card flow-card" aria-labelledby="flow-title">
    <div className="flow-heading">
      <div><span className="flow-kicker">SYSTEM MAP / 01</span><h2 id="flow-title">Cadena de decisión</h2></div>
      <span className="flow-disclaimer">ESQUEMA · SIN DATOS DE MERCADO</span>
    </div>
    <div className="flow-track" role="list" aria-label="Flujo desde datos PIT hasta ejecución manual">
      {FLOW_STEPS.map((step, index) => <Fragment key={step.code}>
        <div className={`flow-node ${index === 3 ? "flow-node-stop" : ""}`} role="listitem">
          <span className="flow-node-code">{step.code}</span>
          <strong>{step.title}</strong>
          <span className="flow-node-status">{step.status}</span>
        </div>
        {index < FLOW_STEPS.length - 1 && <span className="flow-arrow" aria-hidden="true">→</span>}
      </Fragment>)}
    </div>
    <div className="flow-output"><span>$ route --status</span><strong>HALT / NO_TRADE</strong><span>ORDEN: SOLO MANUAL</span></div>
  </article>;
}

function App() {
  const [activeView, setActiveView] = useState("overview");
  const [report, setReport] = useState(null);
  const [reportSha, setReportSha] = useState(null);
  const [reportName, setReportName] = useState("");
  const [audit, setAudit] = useState(null);
  const [auditName, setAuditName] = useState("");
  const [error, setError] = useState("");
  const reportInput = useRef(null);
  const auditInput = useRef(null);

  async function onReportSelected(event) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    try {
      const raw = await file.text();
      const nextReport = JSON.parse(raw);
      validateTradeSheet(nextReport);
      const digest = await sha256(await file.arrayBuffer());
      setReport(nextReport);
      setReportSha(digest);
      setReportName(file.name);
      setError("");
    } catch (exception) {
      setError(exception instanceof Error ? exception.message : "No se pudo leer el reporte.");
    }
  }

  async function onAuditSelected(event) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    try {
      const verified = await verifyAuditLog(await file.text());
      setAudit(verified);
      setAuditName(file.name);
      setError("");
    } catch (exception) {
      setAudit({ valid: false, events: [], error: exception instanceof Error ? exception.message : "No se pudo verificar el registro." });
      setAuditName(file.name);
      setError("");
    }
  }

  const auditedReport = Boolean(report && reportSha && audit?.valid && audit.events.some((event) => event.event_type === "TRADE_SHEET_CREATED" && event.object_id === report.report_id && event.object_sha256 === reportSha));
  const freshnessRows = report?.evidence?.freshness || [];
  const evidence = report?.evidence || DEFAULT_EVIDENCE;
  const navTitle = NAV.find((item) => item.id === activeView)?.label || "Vista general";
  const riskItems = report?.decision?.risks || [];

  return <div className="app-shell">
    <aside className="sidebar">
      <a className="brand" href="#overview" onClick={(event) => { event.preventDefault(); setActiveView("overview"); }} aria-label="Actinver 2026, vista general">
        <span className="brand-mark"><span /></span><span>ACTINVER <b>2026</b></span>
      </a>
      <div className="sidebar-caption">OPERACIÓN</div>
      <nav aria-label="Navegación principal" className="primary-nav">
        {NAV.map((item) => <button key={item.id} type="button" className={`nav-link ${activeView === item.id ? "active" : ""}`} aria-label={item.label} aria-current={activeView === item.id ? "page" : undefined} onClick={() => { setActiveView(item.id); setError(""); }}>
          <Icon name={item.icon} size={19} /><span>{item.label}</span>{activeView === item.id && <span className="nav-indicator" />}
        </button>)}
      </nav>
      <div className="sidebar-spacer" />
      <div className="sidebar-foot">
        <span className="sidebar-foot-icon"><Icon name="evidence" size={16} /></span>
        <div><strong>Solo revisión humana</strong><small>Sin conexión de órdenes</small></div>
      </div>
      <span className="sidebar-version">M9 · Reporte 1.0.0</span>
    </aside>

    <main className="main-shell">
      <header className="topbar">
        <div className="topbar-heading">
          <div className="eyebrow">ACTINVER 2026 <span className="eyebrow-separator">//</span> READ ONLY</div>
          <h1>Terminal de investigación</h1>
          <p>Fecha de corte: <strong>{formatDate(report?.as_of_utc)}</strong></p>
        </div>
        <div className="topbar-actions">
          <span className="no-trade-pill"><Icon name="warning" size={15} />NO TRADE</span>
          <button className="button button-outline" type="button" onClick={() => reportInput.current?.click()}><Icon name="upload" size={17} /><span>Importar reporte</span></button>
          <input ref={reportInput} className="sr-only" type="file" accept=".json,application/json" aria-label="Seleccionar reporte M9 JSON" onChange={onReportSelected} />
        </div>
      </header>

      <div className="content-wrap">
        <div className="terminal-command" role="note" aria-label="Cockpit M9 en modo de solo lectura">
          <span className="command-host">actinver@m9</span><span className="command-path">:~/research</span><span className="command-prompt">$</span><span>cockpit --read-only</span><span className="command-state">NO_TRADE</span>
        </div>
        {error && <div className="error-banner" role="alert"><Icon name="warning" size={17} /><span>{error}</span><button type="button" onClick={() => setError("")} aria-label="Cerrar mensaje">×</button></div>}
        <div className="view-heading"><div><span className="view-kicker">PANEL DEL OPERADOR</span><h2>{activeView === "overview" ? "Competencia" : navTitle}</h2></div>{report && <div className="report-meta"><span className="meta-dot" />{REPORT_TYPES[report.report_type]}<span className="meta-separator">·</span>{formatDate(report.created_at_utc)}</div>}</div>

        {activeView === "overview" && <>
          <section aria-label="Estado de la competencia" className="metric-grid">
            <MetricCard icon="cash" label="Capital" value={metricValue("Capital", report)} />
            <MetricCard icon="rank" label="Posición" value={metricValue("Posición", report)} />
            <MetricCard icon="gap" label="Brecha al primer lugar" value={metricValue("Brecha", report)} />
            <MetricCard icon="calendar" label="Sesiones restantes" value={metricValue("Sesiones restantes", report)} />
          </section>

          <section className="overview-grid">
            <div className="primary-column">
              <article className="card action-card">
                <SectionTitle icon="target" title="Acción de hoy" />
                <div className="action-state">
                  <span className="action-icon"><Icon name="warning" size={25} /></span>
                  <div><strong>NO TRADE</strong><p>{report?.decision?.summary_reason || "No hay un pronóstico M7 validado disponible."}</p></div>
                </div>
                <div className="action-foot"><Icon name="clock" size={15} /><span>{report ? `Reporte ${report.report_id}` : "Sin reporte M9 importado"}</span><span className="foot-lock">Ejecución manual</span></div>
              </article>

              <TradingFlowDiagram />

              <div className="lower-cards">
                <article className="card lower-card">
                  <SectionTitle icon="search" title="Radar de candidatos" />
                  <EmptyState icon="search" title="Sin candidatos con evidencia validada." detail="M7 no tiene forecasts financieros promovidos para evaluar." />
                </article>
                <article className="card lower-card">
                  <SectionTitle icon="portfolio" title="Portafolio" />
                  <Positions report={report} />
                </article>
              </div>
            </div>

            <aside className="rail-column" aria-label="Evidencia y eventos">
              <article className="card evidence-card">
                <SectionTitle icon="file" title="Salud de evidencia" action={<button className="text-button" type="button" onClick={() => setActiveView("evidence")}>Detalle <Icon name="arrow" size={14} /></button>} />
                <div className="evidence-list">
                  <EvidenceRow label="Pronóstico M7" value={sourceStatusLabel(evidence.m7)} tone="red" detail={evidence.m7?.detail} />
                  <EvidenceRow label="Escenarios M8" value={sourceStatusLabel(evidence.m8)} tone="amber" detail={evidence.m8?.detail} />
                  <EvidenceRow label="Símbolos M1" value={sourceStatusLabel(evidence.m1_symbol_mapping)} tone="red" detail={evidence.m1_symbol_mapping?.detail} />
                  <EvidenceRow label="Frescura de datos" value={freshnessRows.length ? freshnessLabel(freshnessRows.some((row) => row.status === "STALE") ? "STALE" : freshnessRows.every((row) => row.status === "CURRENT") ? "CURRENT" : "UNKNOWN") : "Desconocida"} tone="slate" detail={freshnessRows.length ? `${freshnessRows.length} fuente(s) en el reporte` : "No hay tiempos de fuente para verificar."} />
                </div>
                <div className="source-line"><span className="source-status-dot" />Gate empírico: NEEDS_MORE_EVIDENCE</div>
              </article>

              <article className="card events-card">
                <SectionTitle icon="bell" title="Eventos materiales" action={<span className="event-count">{report?.material_events?.length || 0}</span>} />
                <Events report={report} compact />
              </article>
            </aside>
          </section>

          <AuditStrip audit={audit} report={report} auditedReport={auditedReport} auditName={auditName} onImport={() => auditInput.current?.click()} />
        </>}

        {activeView === "reports" && <ReportsView report={report} reportName={reportName} onImport={() => reportInput.current?.click()} />}
        {activeView === "evidence" && <EvidenceView report={report} reportSha={reportSha} />}
        {activeView === "audit" && <AuditView audit={audit} auditName={auditName} report={report} auditedReport={auditedReport} onImport={() => auditInput.current?.click()} />}
        <input ref={auditInput} className="sr-only" type="file" accept=".jsonl,.ndjson,text/plain" aria-label="Seleccionar registro de auditoría JSONL" onChange={onAuditSelected} />
        {activeView === "overview" && riskItems.length > 0 && <p className="risk-count-note">Reporte con {riskItems.length} condición(es) que bloquean una instrucción.</p>}
      </div>
      <footer className="app-footer"><span>Actinver 2026 · Cockpit de investigación</span><span>Manual only <span className="footer-dot" /> No envía órdenes</span></footer>
    </main>
  </div>;
}

function EvidenceRow({ label, value, tone, detail }) {
  return <div className="evidence-row" title={detail || undefined}><span className={`evidence-dot ${tone}`} /><span className="evidence-name">{label}</span><span className="evidence-value">{value}</span></div>;
}

function Positions({ report }) {
  const positions = report?.portfolio?.positions;
  if (positions == null) return <EmptyState icon="portfolio" title="Posiciones actuales: No suministradas." detail="No se cuenta con un corte de portafolio para el periodo actual." />;
  if (positions.length === 0) return <EmptyState icon="portfolio" title="Sin posiciones reportadas." detail="El corte importado no contiene posiciones; confirma la captura de origen." />;
  return <div className="position-list">
    {positions.slice(0, 5).map((position) => <div className="position-row" key={position.instrument_id}><span><small>ID de instrumento</small><strong>{position.instrument_id}</strong></span><strong>{formatMoney(position.market_value_actipesos)}</strong></div>)}
    {positions.length > 5 && <p className="position-more">y {positions.length - 5} más · revisa el reporte fuente</p>}
  </div>;
}

function Events({ report, compact = false }) {
  const events = report?.material_events || [];
  if (!events.length) return <EmptyState icon="calendar" title="Sin eventos verificados." detail="No hay eventos materiales confirmados para el corte." />;
  return <div className={`event-list ${compact ? "compact" : ""}`}>
    {events.map((event) => <article className="event-item" key={event.event_id}>
      <span className="event-marker" />
      <div className="event-copy">
        <div className="event-item-top"><strong>{EVENT_LABELS[event.event_type] || event.event_type}</strong><time>{formatDate(event.event_time || event.available_at_utc)}</time></div>
        <p>{event.entities?.map((entity) => entity.mention).filter(Boolean).join(", ") || "Sin emisora confirmada"} · materialidad {event.materiality}</p>
        <a href={event.source_url} target="_blank" rel="noreferrer">Fuente: {event.publisher || event.source_id}</a>
      </div>
    </article>)}
  </div>;
}

function AuditStrip({ audit, report, auditedReport, auditName, onImport }) {
  const latest = audit?.valid ? audit.events.slice(-3).reverse() : [];
  return <section className="card audit-strip">
    <SectionTitle icon="audit" title="Registro de revisión" action={<button className="button button-small button-soft" type="button" onClick={onImport}><Icon name="upload" size={15} />Importar JSONL</button>} />
    {audit?.valid ? <>
      <div className={`audit-verify-banner ${auditedReport ? "verified" : ""}`}><span className="verify-icon"><Icon name={auditedReport ? "check" : "file"} size={17} /></span><span>{auditedReport ? "El hash del reporte coincide con un evento auditado." : report ? "Cadena válida; este reporte no aparece en el registro importado." : "Cadena de auditoría íntegra."}</span><small>{audit.events.length} eventos · {auditName}</small></div>
      {latest.length ? <AuditTable events={latest} /> : <EmptyState icon="file" title="Sin registros de revisión." detail="Aún no hay eventos M9 en el archivo importado." />}
    </> : <div className="audit-empty"><div><strong>{audit?.valid === false ? "No se pudo verificar el registro." : "Sin registros de revisión."}</strong><p>{audit?.error || "Importa el JSONL generado por actinver-cockpit verify-audit."}</p></div>{audit?.error && <span className="audit-badge failed">Hash inválido</span>}</div>}
  </section>;
}

function AuditTable({ events }) {
  return <div className="table-wrap"><table className="audit-table"><thead><tr><th>Fecha</th><th>Tipo</th><th>Objeto</th><th>Hash del evento</th></tr></thead><tbody>{events.map((event) => <tr key={event.event_id}><td>{formatDate(event.occurred_at_utc)}</td><td><span className="type-chip">{event.event_type === "TRADE_SHEET_CREATED" ? "Trade sheet" : "Atribución"}</span></td><td className="mono">{event.object_id.slice(0, 12)}…</td><td className="mono">{event.event_sha256.slice(0, 16)}…</td></tr>)}</tbody></table></div>;
}

function ReportsView({ report, reportName, onImport }) {
  return <div className="subpage-grid">
    <section className="card report-workflow-card">
      <SectionTitle icon="reports" title="Reportes del operador" />
      <p className="section-intro">Genera y conserva cortes versionados desde la CLI. Importa el JSON resultante para consultarlo y ligarlo con su huella de auditoría.</p>
      <div className="report-type-list">
        {Object.entries(REPORT_TYPES).map(([type, label]) => <div className={`report-type-row ${report?.report_type === type ? "loaded" : ""}`} key={type}>
          <span className="report-type-icon"><Icon name={type === "morning" ? "calendar" : type === "event_update" ? "bell" : "audit"} size={17} /></span>
          <div><strong>{label}</strong><small>{report?.report_type === type ? `Cargado: ${reportName}` : "Se genera con contexto, evidencia disponible y corte temporal explícito."}</small></div>
          <span className={`type-state ${report?.report_type === type ? "loaded" : ""}`}>{report?.report_type === type ? "Cargado" : "Pendiente"}</span>
        </div>)}
      </div>
      <button className="button button-primary" type="button" onClick={onImport}><Icon name="upload" size={16} />Importar un reporte M9</button>
    </section>
    <section className="card report-current-card">
      <SectionTitle icon="file" title="Reporte actual" />
      {report ? <div className="current-report-detail">
        <span className="report-type-badge">{REPORT_TYPES[report.report_type]}</span>
        <h3>NO TRADE</h3><p>{report.decision.summary_reason}</p>
        <dl><dt>Creado</dt><dd>{formatDate(report.created_at_utc)}</dd><dt>Corte</dt><dd>{formatDate(report.as_of_utc)}</dd><dt>Reporte</dt><dd className="mono">{report.report_id}</dd></dl>
      </div> : <EmptyState icon="file" title="Ningún reporte cargado." detail="Importa morning, event update o evening review en formato JSON." />}
    </section>
    <section className="card command-card">
      <SectionTitle icon="terminal" title="Flujo reproducible" />
      <p>Desde la raíz del repositorio, instala el paquete y crea el reporte desde un contexto estructurado:</p>
      <pre><code>actinver-cockpit report --type morning --context context.json</code></pre>
      <p>Usa <code>event_update</code> para un nuevo corte de eventos M6 o <code>evening_review</code> para el cierre. La CLI guarda un JSON versionado y agrega su SHA-256 al registro append-only.</p>
      <span className="safe-note"><Icon name="evidence" size={15} />Los gates M7/M8 actuales mantienen el resultado en NO TRADE.</span>
    </section>
  </div>;
}

function EvidenceView({ report, reportSha }) {
  if (!report) return <section className="card no-report-card"><EmptyState icon="evidence" title="Importa un reporte para inspeccionar la evidencia." detail="Sin un archivo M9, las fuentes y sus hashes no se inventan." /></section>;
  const evidence = report.evidence;
  return <div className="subpage-grid evidence-page">
    <section className="card evidence-summary-card">
      <SectionTitle icon="evidence" title="Estado de los gates" />
      <div className="evidence-list expanded">
        <EvidenceRow label="Mapeo de símbolos M1" value={sourceStatusLabel(evidence.m1_symbol_mapping)} tone="red" detail={evidence.m1_symbol_mapping.detail} />
        <EvidenceRow label="Pronóstico M7" value={sourceStatusLabel(evidence.m7)} tone="red" detail={evidence.m7.detail} />
        <EvidenceRow label="Brain de torneo M8" value={sourceStatusLabel(evidence.m8)} tone="amber" detail={evidence.m8.detail} />
      </div>
      <div className="gate-explainer"><Icon name="warning" size={19} /><div><strong>El resultado operativo es NO TRADE.</strong><p>Un gate de software no equivale a evidencia empírica. Los outputs M7/M8 actuales no autorizan una recomendación.</p></div></div>
    </section>
    <section className="card freshness-page-card">
      <SectionTitle icon="clock" title="Frescura y disponibilidad" />
      {(evidence.freshness || []).length ? <div className="freshness-list">{evidence.freshness.map((row) => <div className="freshness-row" key={row.source_id}><div><strong>{row.source_id}</strong><small>Observado: {formatDate(row.observed_at_utc)}</small></div><span className={`freshness-chip ${row.status.toLowerCase()}`}>{freshnessLabel(row.status)}</span><span className="freshness-age">{row.age_minutes_at_as_of == null ? "Edad desconocida" : `${row.age_minutes_at_as_of} min`}</span></div>)}</div> : <EmptyState icon="clock" title="Frescura desconocida." detail="El reporte no trae timestamps con umbrales de antigüedad verificables." />}
    </section>
    <section className="card provenance-card">
      <SectionTitle icon="file" title="Proveniencia del reporte" />
      <HashRow label="ID de reporte" value={report.report_id} />
      <HashRow label="SHA-256 del archivo" value={reportSha} />
      <HashRow label="Contexto" value={report.provenance.context_id} secondary={report.provenance.context_sha256} />
      <HashRow label="M7 exact bytes" value={report.provenance.m7_result_sha256} />
      <HashRow label="M8 exact bytes" value={report.provenance.m8_result_sha256} />
      {(report.provenance.source_files || []).map((source) => <HashRow key={source.source_id} label={`Snapshot ${source.source_id.slice(0, 12)}`} value={source.sha256} />)}
      <p className="provenance-note">Los hashes registran el contenido recibido; por sí solos no autentican el origen ni la validez científica de una fuente.</p>
    </section>
    <section className="card event-evidence-card">
      <SectionTitle icon="bell" title="Eventos en el corte" />
      <Events report={report} />
    </section>
  </div>;
}

function HashRow({ label, value, secondary }) {
  return <div className="hash-row"><span>{label}</span><div>{value ? <code title={value}>{value}</code> : <em>No suministrado</em>}{secondary && <code className="secondary-hash" title={secondary}>{secondary}</code>}</div></div>;
}

function AuditView({ audit, auditName, report, auditedReport, onImport }) {
  return <div className="subpage-grid audit-page">
    <section className="card audit-import-card">
      <SectionTitle icon="audit" title="Verificación del registro" />
      <p className="section-intro">Importa el archivo JSONL generado por la CLI. Se verifica cada hash de evento y el enlace al evento anterior.</p>
      <button className="button button-primary" type="button" onClick={onImport}><Icon name="upload" size={16} />Importar registro JSONL</button>
      {audit?.valid && <div className="audit-state success"><Icon name="check" size={17} /><span>Cadena íntegra · {audit.events.length} eventos</span><small>{auditName}</small></div>}
      {audit?.valid === false && <div className="audit-state danger"><Icon name="warning" size={17} /><span>Verificación fallida</span><small>{audit.error}</small></div>}
    </section>
    <section className="card audit-link-card">
      <SectionTitle icon="file" title="Vínculo con el reporte actual" />
      {report ? <div className={`audit-link-state ${auditedReport ? "verified" : "unmatched"}`}><span className="verify-icon"><Icon name={auditedReport ? "check" : "warning"} size={18} /></span><div><strong>{auditedReport ? "Hash del reporte confirmado" : "Reporte sin coincidencia auditada"}</strong><p>{auditedReport ? "El ID y el SHA-256 del archivo coinciden con un evento de creación." : "Importa el JSONL que contiene la creación de este reporte y revisa el digest del archivo."}</p></div></div> : <EmptyState icon="file" title="Sin reporte M9 cargado." detail="El vínculo se comprueba contra el archivo importado." />}
    </section>
    <section className="card audit-table-card">
      <SectionTitle icon="clock" title="Eventos append-only" action={<span className={`audit-badge ${audit?.valid ? "verified" : ""}`}>{audit?.valid ? "Hash válido" : "Sin verificar"}</span>} />
      {audit?.valid && audit.events.length ? <AuditTable events={[...audit.events].reverse()} /> : <EmptyState icon="file" title={audit?.valid === false ? "El registro requiere revisión." : "Sin registros de auditoría."} detail={audit?.error || "Verifica un archivo JSONL para consultar la cadena completa."} />}
    </section>
  </div>;
}

export default App;
