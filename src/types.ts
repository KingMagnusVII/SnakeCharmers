export type ModuleKey = "overview" | "warehouse" | "inventory" | "sku" | "outOfStock" | "simulator" | "routes" | "analytics" | "validation" | "downloads" | "roi";
export type WarehouseNode = {Location_ID:string; SKU_ID:string; Allocation_Status:"ALLOCATED"|"VACANT"; X_m:number; Y_m:number; Z_m:number; Zone:string; Demand_Class:string; Capacity:number};
export type InventoryItem = {SKU_ID:string; Description:string; Demand_Class:string; Zone:string; Location_ID:string; Units:number; Capacity:number; Status:string; Unit_Value:number};
export type Metric = {label:string;value:string;delta:string;icon:string};
