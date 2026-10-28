import type {InventoryItem, WarehouseNode} from "../types";

export let demoNotice = "CONNECTING // Magnus pipeline";
const zones = ["A","B","C","D"];

export let inventory: InventoryItem[] = [];
export let warehouseNodes: WarehouseNode[] = [];
export let evaluation: Record<string,{baseline:number;optimized:number;change:number}> = {};
export let routeRows: Record<string,unknown>[] = [];
export let validationRows: Record<string,unknown>[] = [];
export let validationAvailable = false;
export let dataReady = false;

const demoInventory: InventoryItem[] = Array.from({length:72},(_,i)=>({
  SKU_ID:`SKU-${String(1000+i).padStart(4,"0")}`,
  Description:["Fastener kit","Sensor assembly","Drive motor","Optic module","Control board","Packing insert"][i%6],
  Demand_Class:["A","B","C"][i%3], Zone:zones[i%4],
  Location_ID:`${zones[i%4]}${String(Math.floor(i/4)+1).padStart(2,"0")}-RL-B${String(i%8+1).padStart(2,"0")}-L0${i%4+1}`,
  Units:18+(i*37)%240, Capacity:100+(i*19)%220,
  Status:i%7===0?"REVIEW":i%5===0?"LOW STOCK":"ALLOCATED",
  Unit_Value:8.5+(i%13)*4.25
}));
const demoNodes: WarehouseNode[] = Array.from({length:180},(_,i)=>({
  Location_ID:`${zones[i%4]}-${String(Math.floor(i/4)+1).padStart(2,"0")}-${String(i%9+1).padStart(2,"0")}`,
  SKU_ID:i%5===0?"—":demoInventory[i%demoInventory.length].SKU_ID,
  Allocation_Status:i%5===0?"VACANT":"ALLOCATED",
  X_m:(i%18)*2.4,Y_m:Math.floor(i/18)*2.8,Z_m:(i%4)*1.2,
  Zone:zones[i%4],Demand_Class:["A","B","C"][i%3],Capacity:100+(i*17)%200
}));

inventory = demoInventory;
warehouseNodes = demoNodes;

export async function loadBackendData(): Promise<void> {
  const base=(import.meta.env.VITE_API_BASE_URL as string|undefined)?.replace(/\/$/,"") || "http://127.0.0.1:8000";
  try {
    const [inv,nodes,overview,routes]=await Promise.all([
      fetch(`${base}/api/inventory`).then(r=>{if(!r.ok) throw new Error(`inventory ${r.status}`);return r.json()}),
      fetch(`${base}/api/warehouse/nodes`).then(r=>{if(!r.ok) throw new Error(`warehouse ${r.status}`);return r.json()}),
      fetch(`${base}/api/overview`).then(r=>{if(!r.ok) throw new Error(`overview ${r.status}`);return r.json()}),
      fetch(`${base}/api/routes`).then(r=>{if(!r.ok) throw new Error(`routes ${r.status}`);return r.json()}),
      fetch(`${base}/api/validation`).then(r=>{if(!r.ok) throw new Error(`validation ${r.status}`);return r.json()})
    ]);
    // A reachable API can still have no generated pipeline CSVs. Do not replace
    // the usable demo dataset with empty arrays and incorrectly label it live.
    if (!Array.isArray(inv) || inv.length === 0 || !Array.isArray(nodes) || nodes.length === 0) {
      throw new Error("API is reachable but inventory/warehouse outputs are empty. Run the pipeline first.");
    }
    inventory=inv as InventoryItem[];
    warehouseNodes=nodes as WarehouseNode[];
    evaluation=overview.evaluation ?? {};
    routeRows=Array.isArray(routes) ? routes as Record<string,unknown>[] : [];
    validationRows=Array.isArray(validation.rows) ? validation.rows as Record<string,unknown>[] : [];
    validationAvailable=Boolean(validation.available);
    dataReady=true;
    demoNotice=routeRows.length
      ? "LIVE DATA // Magnus pipeline outputs"
      : "LIVE INVENTORY // route CSV missing; run the pipeline to generate optimized_routes.csv";
  } catch (error) {
    console.warn("Magnus API unavailable; using local demo fallback.",error);
    demoNotice="DEMO FALLBACK // API data unavailable or pipeline outputs missing; run scripts\\run_pipeline.py, then restart the API";
    dataReady=false;
    validationRows=[];
    validationAvailable=false;
  }
}

export const formatNum=(n:number)=>new Intl.NumberFormat("en-IN",{maximumFractionDigits:1}).format(n);
