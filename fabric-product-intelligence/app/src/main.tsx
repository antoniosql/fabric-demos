import React, { useMemo, useState } from "react";
import ReactDOM from "react-dom/client";
import {
  Activity,
  AlertTriangle,
  Bot,
  Boxes,
  CheckCircle2,
  GitBranch,
  LayoutDashboard,
  ListChecks,
  Search,
  ShieldCheck,
  Sparkles,
  Target
} from "lucide-react";
import { fallbackData } from "./data/fallback";
import "./styles.css";

type View = "governance" | "intelligence";

function App() {
  const [view, setView] = useState<View>("governance");
  const [query, setQuery] = useState("Which customers have a high score but have not purchased recently?");
  const data = fallbackData;
  const failedRules = useMemo(
    () => data.governance.rules.filter((rule) => rule.status === "Failed"),
    [data]
  );

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <ShieldCheck size={28} />
          <div>
            <strong>Fabric Sessions</strong>
            <span>Retail omnicanal</span>
          </div>
        </div>
        <button
          className={view === "governance" ? "nav-item active" : "nav-item"}
          onClick={() => setView("governance")}
        >
          <LayoutDashboard size={18} />
          Gobierno
        </button>
        <button
          className={view === "intelligence" ? "nav-item active" : "nav-item"}
          onClick={() => setView("intelligence")}
        >
          <Sparkles size={18} />
          Inteligencia
        </button>
      </aside>

      <section className="workspace">
        {view === "governance" ? (
          <GovernanceView failedRules={failedRules} />
        ) : (
          <IntelligenceView query={query} setQuery={setQuery} />
        )}
      </section>
    </main>
  );
}

function GovernanceView({ failedRules }: { failedRules: typeof fallbackData.governance.rules }) {
  const { summary, rules, actions } = fallbackData.governance;
  return (
    <>
      <header className="page-header">
        <div>
          <p className="eyebrow">Sesion A</p>
          <h1>Gobierno operativo</h1>
        </div>
        <div className="toolbar">
          <button className="icon-button" title="Review lineage">
            <GitBranch size={18} />
          </button>
          <button className="primary-button">
            <ListChecks size={18} />
            Crear accion
          </button>
        </div>
      </header>

      <div className="kpi-grid">
        <Metric title="Score global" value={`${summary.global_score}%`} icon={<Activity size={20} />} />
        <Metric title="Reglas fallidas" value={String(summary.failed_rules)} icon={<AlertTriangle size={20} />} />
        <Metric title="Acciones abiertas" value={String(summary.open_actions)} icon={<ListChecks size={20} />} />
        <Metric title="Activos criticos" value="7" icon={<Boxes size={20} />} />
      </div>

      <div className="split">
        <section className="panel">
          <div className="panel-header">
            <h2>Quality cockpit</h2>
            <span>{failedRules.length} fallos activos</span>
          </div>
          <div className="table">
            {rules.map((rule) => (
              <div className="table-row" key={rule.result_id}>
                <div>
                  <strong>{rule.rule_name}</strong>
                  <span>{rule.quality_dimension} · {rule.severity}</span>
                </div>
                <div className="score-cell">
                  <span className={rule.status === "Failed" ? "badge danger" : "badge ok"}>
                    {rule.status}
                  </span>
                  <strong>{rule.score.toFixed(2)}%</strong>
                </div>
              </div>
            ))}
          </div>
        </section>

        <section className="panel">
          <div className="panel-header">
            <h2>Action board</h2>
            <span>Remediacion</span>
          </div>
          {actions.map((action) => (
            <article className="action-item" key={action.action_id}>
              <div>
                <strong>{action.title}</strong>
                <span>{action.owner_upn}</span>
              </div>
              <p>{action.business_impact}</p>
              <span className="badge warn">{action.status}</span>
            </article>
          ))}
        </section>
      </div>

      <section className="wide-panel">
        <div className="panel-header">
          <h2>Linaje e impacto</h2>
          <span>{"raw CSV -> bronze -> curated -> features/scores -> app/agent"}</span>
        </div>
        <div className="lineage">
          {["Raw CSV", "Bronze", "Curated", "Features", "Scores", "App + Agent"].map((node) => (
            <div className="lineage-node" key={node}>
              <GitBranch size={16} />
              {node}
            </div>
          ))}
        </div>
      </section>
    </>
  );
}

function IntelligenceView({
  query,
  setQuery
}: {
  query: string;
  setQuery: (value: string) => void;
}) {
  const { metrics, top_customers: customers } = fallbackData.intelligence;
  return (
    <>
      <header className="page-header">
        <div>
          <p className="eyebrow">Sesion B</p>
          <h1>Scoring, ontologia y agente</h1>
        </div>
        <div className="toolbar">
          <button className="icon-button" title="Search customers">
            <Search size={18} />
          </button>
          <button className="primary-button">
            <Bot size={18} />
            Preguntar
          </button>
        </div>
      </header>

      <div className="kpi-grid">
        <Metric title="Modelo" value={String(metrics.model_version)} icon={<Target size={20} />} />
        <Metric title="ROC AUC" value={String(metrics.roc_auc ?? "n/a")} icon={<Activity size={20} />} />
        <Metric title="PR AUC" value={String(metrics.pr_auc ?? "n/a")} icon={<CheckCircle2 size={20} />} />
        <Metric title="Clientes top" value={String(customers.length)} icon={<Sparkles size={20} />} />
      </div>

      <div className="split">
        <section className="panel">
          <div className="panel-header">
            <h2>Ranking de clientes</h2>
            <span>Score actual</span>
          </div>
          <div className="table">
            {customers.map((customer) => (
              <div className="table-row" key={customer.customer_id}>
                <div>
                  <strong>{customer.customer_id}</strong>
                  <span>{customer.recommended_action}</span>
                </div>
                <div className="score-cell">
                  <span className="badge ok">{customer.score_band}</span>
                  <strong>{customer.score.toFixed(3)}</strong>
                </div>
              </div>
            ))}
          </div>
        </section>

        <section className="panel agent-panel">
          <div className="panel-header">
            <h2>Data Agent</h2>
            <span>Pregunta prevalidada</span>
          </div>
          <textarea value={query} onChange={(event) => setQuery(event.target.value)} />
          <div className="agent-answer">
            <Bot size={18} />
            <p>
              The agent will answer from curated tables, the semantic model and the ontology. It must use
              latest scores and never expose personal contact data.
            </p>
          </div>
        </section>
      </div>

      <section className="wide-panel">
        <div className="panel-header">
          <h2>Ontologia de pedidos</h2>
          <span>{"Customer -> Order -> OrderLine -> Product -> Return -> Score"}</span>
        </div>
        <div className="ontology-grid">
          {["Customer", "Order", "OrderLine", "Product", "Return", "StockSnapshot", "CustomerScore"].map(
            (entity) => (
              <div className="ontology-node" key={entity}>{entity}</div>
            )
          )}
        </div>
      </section>
    </>
  );
}

function Metric({ title, value, icon }: { title: string; value: string; icon: React.ReactNode }) {
  return (
    <section className="metric">
      <div>{icon}</div>
      <span>{title}</span>
      <strong>{value}</strong>
    </section>
  );
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
