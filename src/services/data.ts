import type {InventoryItem, WarehouseNode} from "../types";

export const demoNotice = "DEMO DATA // connect the original backend for production values";
const zones = ["A","B","C","D"];

export const inventory: InventoryItem[] = Array.from({length:72},(_,i)=>({
  SKU_ID:`SKU-${String(1000+i).padStart(4,"0")}`,
  Description:["Fastener kit","Sensor assembly","Drive motor","Optic module","Control board","Packing insert"][i%6],
  Demand_Class:["A","B","C"][i%3], Zone:zones[i%4],
  Location_ID:`${zones[i%4]}${String(Math.floor(i/4)+1).padStart(2,"0")}-RL-B${String(i%8+1).padStart(2,"0")}-L0${i%4+1}`,
  Units: 18+(i*37)%240, Capacity: 100+(i*19)%220,
  Status:i%7===0?"REVIEW":i%5===0?"LOW STOCK":"ALLOCATED",
  Unit_Value: 8.5+(i%13)*4.25
}));

export const warehouseNodes: WarehouseNode[] = Array.from({length:180},(_,i)=>({
  Location_ID:`${zones[i%4]}-${String(Math.floor(i/4)+1).padStart(2,"0")}-${String(i%9+1).padStart(2,"0")}`,
  SKU_ID:i%5===0?"—":inventory[i%inventory.length].SKU_ID,
  Allocation_Status:i%5===0?"VACANT":"ALLOCATED",
  X_m:(i%18)*2.4, Y_m:Math.floor(i/18)*2.8, Z_m:(i%4)*1.2,
  Zone:zones[i%4], Demand_Class:["A","B","C"][i%3], Capacity:100+(i*17)%200
}));

export const formatNum=(n:number)=>new Intl.NumberFormat("en-IN",{maximumFractionDigits:1}).format(n);
