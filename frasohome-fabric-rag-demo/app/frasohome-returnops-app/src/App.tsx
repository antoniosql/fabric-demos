import { useState } from 'react';
import { answerReturnCase, isConfigured, type RagAnswer } from './lib/udfClient';

const defaultQuestion = 'El cliente quiere devolver un sofá modular comprado online hace 34 días. Indica que llegó con una pata dañada, conserva fotos del embalaje y solicita reemplazo urgente. ¿Debemos aprobar devolución, reemplazo o revisión manual?';

function EvidenceList({ answer }: { answer: RagAnswer }) {
  if (!answer.evidence?.length) return null;
  return (
    <section className="card">
      <h2>Evidencias recuperadas</h2>
      <div className="evidence-grid">
        {answer.evidence.map((e) => (
          <article className="evidence" key={`${e.documentCode}-${e.chunkNumber}`}>
            <strong>{e.documentCode}</strong>
            <span>{e.documentTitle}</span>
            <small>chunk {e.chunkNumber} · score {Number(e.score).toFixed(2)}</small>
            <p>{e.excerpt}</p>
          </article>
        ))}
      </div>
    </section>
  );
}

export default function App() {
  const [returnCaseId, setReturnCaseId] = useState('RET-2026-004219');
  const [question, setQuestion] = useState(defaultQuestion);
  const [answer, setAnswer] = useState<RagAnswer | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function runDemo() {
    setLoading(true);
    setError(null);
    setAnswer(null);
    try {
      const result = await answerReturnCase(returnCaseId, question);
      setAnswer(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="page">
      <header className="hero">
        <div>
          <p className="eyebrow">Microsoft Fabric Databases · RAG Demo</p>
          <h1>FraSoHome ReturnOps 360</h1>
          <p>
            Aplicación de soporte para decidir devoluciones y reemplazos combinando datos SQL,
            políticas internas y auditoría de IA.
          </p>
        </div>
        <div className="badge">Charlemos de SQL Server</div>
      </header>

      {!isConfigured() && (
        <section className="warning">
          <strong>Configuración pendiente.</strong> Define <code>VITE_UDF_FUNCTION_URL</code>, <code>VITE_ENTRA_CLIENT_ID</code> y <code>FABRIC_TENANT_ID</code> antes de invocar la UDF.
        </section>
      )}

      <section className="layout">
        <aside className="card case-card">
          <h2>Caso de devolución</h2>
          <label>
            Return case id
            <input value={returnCaseId} onChange={(e) => setReturnCaseId(e.target.value)} />
          </label>
          <dl>
            <dt>Cliente</dt>
            <dd>Laura Méndez · Gold · riesgo 0.12</dd>
            <dt>Producto</dt>
            <dd>Sofá modular Nordic 3 plazas</dd>
            <dt>Canal</dt>
            <dd>E-commerce</dd>
            <dt>Stock</dt>
            <dd>Disponible en almacén Madrid Sur</dd>
          </dl>
        </aside>

        <section className="card question-card">
          <h2>Pregunta RAG</h2>
          <textarea value={question} onChange={(e) => setQuestion(e.target.value)} rows={8} />
          <button onClick={runDemo} disabled={loading || !isConfigured()}>
            {loading ? 'Consultando Fabric...' : 'Obtener recomendación'}
          </button>
          {error && <p className="error">{error}</p>}
        </section>
      </section>

      {answer && (
        <>
          <section className="card result-card">
            <div className="result-title">
              <h2>Recomendación</h2>
              <span className="confidence">{Math.round(answer.confidence * 100)}% confianza</span>
            </div>
            <h3>{answer.recommendation}</h3>
            {answer.requiresManualReview && <p className="manual">Requiere revisión manual o validación adicional.</p>}
            <div className="columns">
              <div>
                <h4>Motivos</h4>
                <ul>{answer.reasons.map((r) => <li key={r}>{r}</li>)}</ul>
              </div>
              <div>
                <h4>Acciones sugeridas</h4>
                <ul>{answer.nextActions.map((a) => <li key={a}>{a}</li>)}</ul>
              </div>
            </div>
            <footer>
              <span>Audit id: {answer.auditId ?? 'n/d'}</span>
              <span>Modelo: {answer.modelName ?? 'n/d'}</span>
            </footer>
          </section>
          <EvidenceList answer={answer} />
        </>
      )}
    </main>
  );
}
