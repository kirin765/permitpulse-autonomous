const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ||
  (process.env.VERCEL_URL ? `https://${process.env.VERCEL_URL}/api/v1` : "http://localhost:8000/api/v1");
const SUPABASE_CONNECTED = Boolean(
  process.env.NEXT_PUBLIC_SUPABASE_URL && process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY,
);

type SLOMetric = {
  metric_name: string;
  metric_value: number;
  target_value: number;
  status: string;
};

async function fetchAutonomy() {
  try {
    const response = await fetch(`${API_BASE}/system/autonomy-status`, { cache: "no-store" });
    if (!response.ok) {
      throw new Error("failed");
    }
    return response.json();
  } catch {
    return {
      city_snapshots: {},
      recent_autonomy_events: [],
      recent_rollbacks: [],
      stale_cities: ["NYC", "LA", "SF"],
    };
  }
}

async function fetchSLO() {
  try {
    const response = await fetch(`${API_BASE}/system/slo`, { cache: "no-store" });
    if (!response.ok) {
      throw new Error("failed");
    }
    return response.json();
  } catch {
    return { metrics: [] as SLOMetric[] };
  }
}

export default async function HomePage() {
  const [autonomy, slo] = await Promise.all([fetchAutonomy(), fetchSLO()]);

  return (
    <main>
      <section className="hero">
        <span className="badge">Zero-Human-Ops Mode</span>
        <h1>PermitPulse</h1>
        <p>
          Address-level STR compliance intelligence with fully autonomous ingestion, decisions,
          deployment recovery, billing actions, and operational monitoring.
        </p>

        <div className="grid">
          <article className="card">
            <strong>Active Cities</strong>
            <p className="kpi">{Object.keys(autonomy.city_snapshots || {}).length}</p>
          </article>
          <article className="card">
            <strong>Stale Cities</strong>
            <p className="kpi">{(autonomy.stale_cities || []).length}</p>
          </article>
          <article className="card">
            <strong>Recent Rollbacks</strong>
            <p className="kpi">{(autonomy.recent_rollbacks || []).length}</p>
          </article>
          <article className="card">
            <strong>Supabase</strong>
            <p className="kpi">{SUPABASE_CONNECTED ? "Connected" : "Not Set"}</p>
          </article>
        </div>
      </section>

      <section style={{ marginTop: 20 }}>
        <div className="grid">
          {(slo.metrics || []).map((metric: SLOMetric) => (
            <article key={metric.metric_name} className="card">
              <strong>{metric.metric_name}</strong>
              <p className="kpi">{metric.metric_value.toFixed(2)}%</p>
              <p>Target: {metric.target_value.toFixed(2)}%</p>
              <p>Status: {metric.status}</p>
            </article>
          ))}
          {(slo.metrics || []).length === 0 ? (
            <article className="card">
              <strong>SLO Metrics</strong>
              <p>Run autonomy cycle to populate metrics.</p>
            </article>
          ) : null}
        </div>
      </section>
    </main>
  );
}
