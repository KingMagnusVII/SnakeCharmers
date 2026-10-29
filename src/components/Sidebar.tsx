import {Activity,BookOpen,Boxes,ChartNoAxesCombined,CircleDollarSign,ClipboardCheck,Download,LayoutDashboard,Map,PackageSearch,PackageX,Route,SlidersHorizontal,X,Menu} from "lucide-react";
import type {ModuleKey} from "../types";

const modules:{key:ModuleKey;label:string;icon:typeof Activity;num:string}[]=[
 {key:"overview",label:"System Overview",icon:LayoutDashboard,num:"01"},
 {key:"warehouse",label:"Warehouse Explorer",icon:Map,num:"02"},
 {key:"inventory",label:"Slotting & Inventory",icon:Boxes,num:"03"},
 {key:"sku",label:"SKU Finder",icon:PackageSearch,num:"04"},
 {key:"outOfStock",label:"Out-of-Stock Products",icon:PackageX,num:"05"},
 {key:"simulator",label:"What-If Simulator",icon:SlidersHorizontal,num:"06"},
 {key:"routes",label:"Pick Routes",icon:Route,num:"07"},
 {key:"analytics",label:"Analytics",icon:ChartNoAxesCombined,num:"08"},
 {key:"validation",label:"Validation",icon:ClipboardCheck,num:"09"},
 {key:"downloads",label:"Downloads",icon:Download,num:"10"},
 {key:"roi",label:"Advanced ROI",icon:CircleDollarSign,num:"11"},
 {key:"guide",label:"Project Guide",icon:BookOpen,num:"12"},
];

export default function Sidebar({active,onSelect,open,onClose,live}:{active:ModuleKey;onSelect:(key:ModuleKey)=>void;open:boolean;onClose:()=>void;live:boolean}){
 return <><div className={`scrim ${open?"show":""}`} onClick={onClose}/><aside className={`sidebar ${open?"open":""}`}><div className="brand"><div className="brand-mark">SC<span>+</span></div><div><strong>SNAKECHARMERS</strong><small>WAREHOUSE INTELLIGENCE</small></div><button className="icon-button mobile-close" onClick={onClose}><X size={18}/></button></div><div className="side-label">COMMAND TERMINAL <span>V5.1</span></div><nav>{modules.map(m=>{const Icon=m.icon;return <button key={m.key} className={`nav-item ${active===m.key?"active":""}`} onClick={()=>{onSelect(m.key);onClose()}}><span className="nav-num">{m.num}</span><Icon size={17}/><span>{m.label}</span>{active===m.key&&<i/>}</button>})}</nav><div className="sidebar-bottom"><div className="signal-row"><span className="pulse-dot"/> PIPELINE DATALINK</div><div className="signal-copy">{live?"LIVE MODE // MAGNUS API":"DEMO MODE // LOCAL FALLBACK"}</div><div className="network-box"><span>NET STATUS</span><b>{live?"● CONNECTED":"● OFFLINE"}</b><span>PACKET LOSS</span><b>—</b><span>UPTIME</span><b>SESSION</b></div><div className="side-footer">SECURE VIEW // BUILD 1.0.0</div></div></aside></>
}
export function MenuButton({onClick}:{onClick:()=>void}){return <button className="icon-button menu-button" onClick={onClick}><Menu size={20}/></button>}
