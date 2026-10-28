const base = ((import.meta.env.VITE_API_BASE_URL as string|undefined) || "http://127.0.0.1:8000").replace(/\/$/,"");

export async function apiGet<T>(path:string):Promise<T>{
  const response=await fetch(`${base}${path}`);
  if(!response.ok) throw new Error(`API ${response.status}: ${response.statusText}`);
  return response.json() as Promise<T>;
}

export const endpoints={
  overview:"/api/overview",
  warehouse:"/api/warehouse/nodes",
  inventory:"/api/inventory",
  routes:"/api/routes",
  validation:"/api/validation",
  downloads:"/api/downloads",
};
