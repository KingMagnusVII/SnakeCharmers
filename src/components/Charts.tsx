import { inventory, warehouseNodes, routeRows, evaluation } from "../services/data";

const colors = ["#00e5ff", "#8b5cf6", "#00d68f", "#ffb84d", "#ff5577"];
const panelStyle: React.CSSProperties = {
  width: "100%", minHeight: 260, padding: 16, boxSizing: "border-box",
  color: "#dce8f7", overflow: "hidden",
};

function ThreeDBarChart({ labels, values }: { labels: string[]; values: number[] }) {
  const max = Math.max(...values, 1);
  return <div style={{ ...panelStyle, display: "flex", alignItems: "end", justifyContent: "space-around", gap: 12, paddingTop: 35, perspective: 700 }}>
    {labels.map((label, i) => {
      const height = Math.max(8, (values[i] / max) * 145);
      return <div key={label} style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column", alignItems: "center", gap: 12 }}>
        <strong style={{ color: colors[i % colors.length], fontSize: 12 }}>{values[i].toLocaleString("en-IN")}</strong>
        <div style={{
          width: "65%", maxWidth: 62, height, position: "relative", transform: "skewY(-8deg)",
          transformStyle: "preserve-3d", background: `linear-gradient(90deg, ${colors[i % colors.length]}55, ${colors[i % colors.length]})`,
          boxShadow: `8px 8px 0 ${colors[i % colors.length]}33, 0 0 20px ${colors[i % colors.length]}22`,
          borderTop: `2px solid ${colors[i % colors.length]}`, borderRadius: "4px 4px 0 0",
        }} />
        <span style={{ fontSize: 10, textAlign: "center", color: "#9aabc1", overflowWrap: "anywhere" }}>{label}</span>
      </div>;
    })}
  </div>;
}

function ThreeDPieChart({ labels, values }: { labels: string[]; values: number[] }) {
  const total = values.reduce((sum, value) => sum + value, 0);
  let cursor = 0;
  const segments = values.map((value, i) => {
    const start = cursor; cursor += total ? value / total * 100 : 0;
    return `${colors[i % colors.length]} ${start}% ${cursor}%`;
  });
  const gradient = `conic-gradient(${segments.join(", ")})`;
  return <div style={{ ...panelStyle, display: "flex", flexWrap: "wrap", alignItems: "center", justifyContent: "center", gap: 28 }}>
    <div style={{ width: 180, height: 180, flexShrink: 0, position: "relative", marginTop: -10 }}>
      <div style={{ position: "absolute", inset: "15px 0 -10px", borderRadius: "50%", background: gradient, filter: "brightness(0.48)", transform: "rotateX(58deg)", boxShadow: "0 16px 20px #0008" }} />
      <div style={{ position: "absolute", inset: 0, borderRadius: "50%", background: gradient, transform: "rotateX(58deg)", boxShadow: "0 0 22px #00e5ff18", border: "1px solid #ffffff22" }} />
    </div>
    <div style={{ display: "grid", gap: 12, minWidth: 120 }}>
      {labels.map((label, i) => <div key={label} style={{ display: "grid", gridTemplateColumns: "10px 1fr auto", gap: 8, alignItems: "center", fontSize: 12 }}>
        <span style={{ width: 9, height: 9, borderRadius: 2, background: colors[i % colors.length] }} />
        <span style={{ color: "#a9b8cc" }}>{label}</span>
        <strong>{values[i].toLocaleString("en-IN")}</strong>
      </div>)}
    </div>
  </div>;
}

export function DemandChart() {
  const labels = ["Class A", "Class B", "Class C"];
  const values = labels.map(label => inventory.filter(item => item.Demand_Class === label.slice(-1)).length);
  return <ThreeDPieChart labels={labels} values={values} />;
}

export function AllocationChart() {
  const labels = ["Allocated", "Vacant"];
  const values = labels.map(label => warehouseNodes.filter(node =>
    node.Allocation_Status === (label === "Allocated" ? "ALLOCATED" : "VACANT")
  ).length);
  return <ThreeDBarChart labels={labels} values={values} />;
}

export function RouteChart() {
  const distances = routeRows.map(row => Number(row.Distance_m)).filter(value => Number.isFinite(value) && value >= 0);
  const total = evaluation.total_distance_m?.optimized ?? distances.reduce((sum, value) => sum + value, 0);
  const complete = routeRows.filter(row => String(row.Complete).toLowerCase() === "true").length;
  const max = Math.max(...distances, 1);
  const shown = distances.slice(0, 60);
  return <div className="route-chart">
    <div className="metrics-inline">
      <span>OPTIMIZED DISTANCE <b>{total.toLocaleString("en-IN", { maximumFractionDigits: 1 })} m</b></span>
      <span>ROUTES <b>{routeRows.length.toLocaleString("en-IN")}</b></span>
      <span>COMPLETE <b>{complete.toLocaleString("en-IN")}</b></span>
    </div>
    {shown.length ? <>
      <div className="route-bars" role="img" aria-label={`Route distances for the first ${shown.length} of ${distances.length} route records, in metres`}>
        {shown.map((distance, i) => <i key={i} title={`Route ${i + 1}: ${distance.toFixed(1)} m`} style={{ height: `${Math.max(3, distance / max * 100)}%` }} />)}
      </div>
      <div className="route-chart-axis"><span>ROUTE 1</span><span>Each bar = one order's route distance (m)</span><span>ROUTE {shown.length}</span></div>
      {distances.length > shown.length && <p>SHOWING FIRST {shown.length} OF {distances.length} ROUTES</p>}
    </> : <div className="empty-state">NO ROUTE DATA LOADED — start the Python API and load optimized pipeline outputs.</div>}
    <p>OPTIMIZED ROUTE OUTPUT // MAGNUS PIPELINE</p>
  </div>;
}

export function TrendChart() {
  const baseline = evaluation.total_distance_m?.baseline ?? 0;
  const optimized = evaluation.total_distance_m?.optimized ?? 0;
  const delta = optimized - baseline;
  const improvement = baseline > 0 ? (baseline - optimized) / baseline * 100 : 0;
  const hasEvaluation = baseline > 0 || optimized > 0;
  const max = Math.max(...[baseline, optimized], 1);
  const same = hasEvaluation && Math.abs(delta) < 0.05;
  return <div className="route-chart">
    {!hasEvaluation && <div className="empty-state">NO EVALUATION METRICS LOADED — verify evaluation_comparison.csv and restart the API.</div>}
    {hasEvaluation && <>
      <div className="comparison-bars">
        {([[ "BASELINE", baseline ], [ "OPTIMIZED", optimized ]] as [string, number][]).map(([label, value], i) =>
          <div key={label}>
            <strong>{value.toLocaleString("en-IN", { maximumFractionDigits: 1 })} m</strong>
            <div className="comparison-bar" style={{ height: `${Math.max(12, value / max * 160)}px`, background: colors[i] }} />
            <span>{label}</span>
          </div>
        )}
      </div>
      <div className={`evaluation-result ${same ? "no-improvement" : improvement > 0 ? "improved" : "regressed"}`}>
        {same ? "NO DISTANCE IMPROVEMENT RECORDED — baseline and optimized totals are equal." :
          improvement > 0 ? `${improvement.toFixed(1)}% shorter route distance in the optimized evaluation.` :
          `${Math.abs(improvement).toFixed(1)}% longer route distance in the optimized evaluation.`}
        <small>Difference: {delta > 0 ? "+" : ""}{delta.toLocaleString("en-IN", { maximumFractionDigits: 1 })} m · Same evaluation file and sample required for a fair comparison.</small>
      </div>
    </>}
    <p>ROUTE DISTANCE COMPARISON // EVALUATION CSV</p>
  </div>;
}
