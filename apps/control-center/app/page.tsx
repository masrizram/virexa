export const dynamic = "force-dynamic";

const API = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

async function fetchJson<T>(path: string): Promise<T | null> {
  try {
    const res = await fetch(`${API}${path}`, { cache: "no-store", signal: AbortSignal.timeout(4000) });
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch {
    return null;
  }
}

type Health = { status: string; env: string; dry_run: boolean; autonomous_mode: boolean; ai_configured: boolean };
type Stats = { by_state: Record<string, number> };
type Budgets = { budgets: Record<string, number>; spent_today: Record<string, number> };
type Safety = { state: string };

function Metric({ label, value, tone }: { label: string; value: string | number; tone?: string }) {
  return (
    <div className="metric panel">
      <span className="value" style={tone ? { color: `var(--${tone})` } : undefined}>{value}</span>
      <span className="label">{label}</span>
    </div>
  );
}

export default async function Dashboard() {
  const [health, stats, budgets, safety] = await Promise.all([
    fetchJson<Health>("/health"),
    fetchJson<Stats>("/content/stats"),
    fetchJson<Budgets>("/settings/budgets"),
    fetchJson<Safety>("/safety"),
  ]);

  const states = stats?.by_state ?? {};
  const total = Object.values(states).reduce((a: number, b) => a + (b as number), 0);
  const apiUp = health !== null;

  return (
    <main style={{ padding: 20, display: "flex", flexDirection: "column", gap: 16 }}>
      <header style={{ borderRadius: 10, border: "1px solid var(--border)", background: "var(--panel)", position: "static", marginBottom: 0 }}>
        <h1 style={{ margin: 0, fontSize: 18 }}>Virexa Control Center</h1>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <span className={`badge ${apiUp ? "ok" : "bad"}`}>{apiUp ? `API ${health!.env}` : "API DOWN"}</span>
          <span className={`badge ${safety?.state === "RUNNING" ? "ok" : "warn"}`}>Safety: {safety?.state ?? "?"}</span>
          <span className={`badge ${health?.dry_run ? "warn" : "ok"}`}>{health?.dry_run ? "DRY RUN" : "LIVE"}</span>
        </div>
      </header>

      <section>
        <h2 style={{ fontSize: 13, textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--muted)" }}>Today — Pipeline</h2>
        <div className="grid grid-4">
          <Metric label="Content items (total)" value={total} />
          <Metric label="Discovered" value={states.DISCOVERED ?? 0} />
          <Metric label="Producing / QC" value={(states.PRODUCING ?? 0) + (states.QC ?? 0)} />
          <Metric label="Published" value={states.PUBLISHED ?? 0} />
          <Metric label="Completed" value={states.COMPLETED ?? 0} />
          <Metric label="Human review" value={states.HUMAN_REVIEW ?? 0} tone={states.HUMAN_REVIEW ? "warn" : undefined} />
          <Metric label="Rejected" value={states.REJECTED ?? 0} tone={states.REJECTED ? "bad" : undefined} />
          <Metric label="Failed" value={states.FAILED ?? 0} tone={states.FAILED ? "bad" : undefined} />
        </div>
      </section>

      <section>
        <h2 style={{ fontSize: 13, textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--muted)" }}>Budgets (today)</h2>
        <div className="grid grid-3">
          <Metric label={`LLM spent / $${budgets?.budgets.daily_llm_budget ?? "?"}`} value={`$${(budgets?.spent_today.llm ?? 0).toFixed(4)}`} />
          <Metric label={`Video spent / $${budgets?.budgets.daily_video_budget ?? "?"}`} value={`$${(budgets?.spent_today.video ?? 0).toFixed(4)}`} />
          <Metric label={`Total / $${budgets?.budgets.daily_total_budget ?? "?"}`} value={`$${(budgets?.spent_today.total ?? 0).toFixed(4)}`} />
        </div>
      </section>

      <section className="panel">
        <h2 style={{ fontSize: 13, textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--muted)", marginTop: 0 }}>System</h2>
        <table>
          <tbody>
            <tr><th>API</th><td className={apiUp ? "ok" : "bad"}>{apiUp ? `up (${health!.env})` : "down"}</td></tr>
            <tr><th>AI providers</th><td className={health?.ai_configured ? "ok" : "warn"}>{health?.ai_configured ? "configured" : "not configured"}</td></tr>
            <tr><th>Autonomous mode</th><td>{health?.autonomous_mode ? "ON" : "OFF"}</td></tr>
            <tr><th>DRY_RUN</th><td className={health?.dry_run ? "warn" : "ok"}>{String(health?.dry_run)}</td></tr>
            <tr><th>Safety state</th><td>{safety?.state ?? "unknown"}</td></tr>
          </tbody>
        </table>
      </section>
    </main>
  );
}
