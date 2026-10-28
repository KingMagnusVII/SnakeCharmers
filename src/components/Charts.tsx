import { useMemo } from "react";
import { inventory, warehouseNodes } from "../services/data";

const colors = ["#00e5ff", "#8b5cf6", "#00d68f", "#ffb84d", "#ff5577"];

function BarChart({labels,values}:{labels:string[];values:number[]}){
 const max=Math.max(...values,1);
 return <div className="chart-box bar-chart">{labels.map((label,i)=><div className="bar-item" key={label}><strong style={{color:colors[i%colors.length]}}>{values[i].toLocaleString("en-IN")}</strong><div className="bar" style={{height:`${Math.max(8,(values[i]/max)*145)}px`,background:`linear-gradient(90deg,${colors[i%colors.length]}55,${colors[i%colors.length]})`}}/><span>{label}</span></div>)}</div>
}
function PieChart({labels,values}:{labels:string[];values:number[]}){
 const total=values.reduce((a,b)=>a+b,0); let cursor=0;
 const segments=values.map((v,i)=>{const start=cursor;cursor+=total?v/total*100:0;return `${colors[i%colors.length]} ${start}% ${cursor}%`});
 return <div className="chart-box pie-layout"><div className="pie" style={{background:`conic-gradient(${segments.join(",")})`}}/><div className="pie-legend">{labels.map((l,i)=><div key={l}><i style={{background:colors[i%colors.length]}}/><span>{l}</span><strong>{values[i]}</strong></div>)}</div></div>
}
export function DemandChart(){const data=useMemo(()=>{const labels=["Class A","Class B","Class C"];return {labels,values:labels.map(l=>inventory.filter(i=>i.Demand_Class===l.slice(-1)).length)}},[]);return <PieChart {...data}/>}
export function AllocationChart(){const labels=["Allocated","Vacant"];const values=labels.map(l=>warehouseNodes.filter(n=>n.Allocation_Status===(l==="Allocated"?"ALLOCATED":"VACANT")).length);return <BarChart labels={labels} values={values}/>}
export function RouteChart(){const points=[[15,75],[28,48],[42,63],[57,28],[73,43],[88,16]];const route=points.map(([x,y])=>`${x},${y}`).join(" ");return <div className="route-chart"><svg viewBox="0 0 100 100" width="100%" height="230"><polyline points={route} fill="none" stroke="#00e5ff" strokeWidth="2"/><polyline points={route} fill="none" stroke="#00e5ff" strokeWidth="6" opacity=".12"/>{points.map(([x,y],i)=><circle key={i} cx={x} cy={y} r="2.5" fill="#00e5ff"/>)}</svg><p>ILLUSTRATIVE ROUTE // NOT CONNECTED TO THE OPTIMIZATION SOLVER</p></div>}
export function TrendChart(){const values=[28,35,31,49,43,62,56,76];const points=values.map((v,i)=>`${8+i*12},${90-v}`).join(" ");return <div className="route-chart"><svg viewBox="0 0 100 100" width="100%" height="220"><polygon points={`8,90 ${points} 92,90`} fill="#00e5ff" opacity=".12"/><polyline points={points} fill="none" stroke="#00e5ff" strokeWidth="1.8"/>{values.map((v,i)=><circle key={i} cx={8+i*12} cy={90-v} r="1.8" fill="#00e5ff"/>)}</svg><p>WEEKLY THROUGHPUT INDEX // ILLUSTRATIVE DEMO DATA</p></div>}
