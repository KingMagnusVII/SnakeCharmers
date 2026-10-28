import type {ReactNode} from "react";
export default function MetricCard({label,value,delta,icon}:{label:string;value:string;delta:string;icon:ReactNode}){return <div className="metric-card"><div className="metric-top"><span>{label}</span><div className="metric-icon">{icon}</div></div><strong>{value}</strong><div className="metric-foot"><span className="metric-dot"/> {delta}</div></div>}
