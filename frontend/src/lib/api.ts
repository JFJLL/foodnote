import type {
  CookingStatsItem,
  HouseholdPreferences,
  ImportJob,
  MenuOrder,
  RecipeDetail,
  RecipeListItem,
  ShoppingListItem,
  SystemStatus,
  TodayMenuItem,
  WeeklyPlan
} from "../types";

function apiBaseUrl(): string {
  if (typeof window !== "undefined") {
    return window.localStorage.getItem("foodnote_api_base_url") || import.meta.env.VITE_API_BASE_URL || "";
  }
  return import.meta.env.VITE_API_BASE_URL || "";
}

async function request<T>(input: RequestInfo, init?: RequestInit): Promise<T> {
  const url = typeof input === "string" && input.startsWith("/") ? `${apiBaseUrl()}${input}` : input;
  const response = await fetch(url, {
    headers: init?.body instanceof FormData ? undefined : { "Content-Type": "application/json" },
    ...init
  });
  if (!response.ok) {
    const message = await readableErrorMessage(response);
    throw new Error(message || `Request failed: ${response.status}`);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return response.json() as Promise<T>;
}

async function readableErrorMessage(response: Response): Promise<string> {
  const raw = await response.text();
  if (!raw) return `请求失败：${response.status}`;
  try {
    const parsed = JSON.parse(raw) as { detail?: unknown; message?: unknown };
    const detail = parsed.detail ?? parsed.message;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) return detail.map((item) => item?.msg || item?.message || JSON.stringify(item)).join("；");
  } catch {
    return raw;
  }
  return raw;
}

export const api = {
  systemStatus: () => request<SystemStatus>("/api/system/status"),
  listJobs: () => request<ImportJob[]>("/api/import-jobs"),
  createJob: (payload: {
    source_url: string;
    source_platform?: "auto" | "xiaohongshu" | "douyin";
    manual_text?: string;
    media_paths?: string[];
    import_kind?: "unknown" | "image" | "video" | "manual";
  }) => request<ImportJob>("/api/import-jobs", { method: "POST", body: JSON.stringify(payload) }),
  uploadFiles: (files: File[]) => {
    const form = new FormData();
    files.forEach((file) => form.append("files", file));
    return request<{ paths: string[] }>("/api/uploads", { method: "POST", body: form });
  },
  listRecipes: () => request<RecipeListItem[]>("/api/recipes"),
  randomRecipes: (count = 1) => request<RecipeListItem[]>(`/api/recipes/random?count=${count}`),
  getPreferences: () => request<HouseholdPreferences>("/api/preferences"),
  updatePreferences: (payload: Partial<HouseholdPreferences>) =>
    request<HouseholdPreferences>("/api/preferences", { method: "PATCH", body: JSON.stringify(payload) }),
  getRecipe: (id: string) => request<RecipeDetail>(`/api/recipes/${id}`),
  updateRecipe: (id: string, payload: Partial<RecipeDetail>) =>
    request<RecipeDetail>(`/api/recipes/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  listMenu: () => request<TodayMenuItem[]>("/api/today-menu/items"),
  shoppingList: () => request<ShoppingListItem[]>("/api/today-menu/shopping-list"),
  listMenuOrders: (query = "") => request<MenuOrder[]>(`/api/menu-orders${query ? `?query=${encodeURIComponent(query)}` : ""}`),
  cookingStats: (limit = 8) => request<CookingStatsItem[]>(`/api/cooking-stats?limit=${limit}`),
  listWeeklyPlans: (limit = 3) => request<WeeklyPlan[]>(`/api/weekly-plans?limit=${limit}`),
  createWeeklyPlan: (payload: { title?: string; start_date?: string; days?: number; meals_per_day?: number; servings?: number }) =>
    request<WeeklyPlan>("/api/weekly-plans", { method: "POST", body: JSON.stringify(payload) }),
  addWeeklyPlanItemToToday: (id: string) =>
    request<TodayMenuItem>(`/api/weekly-plans/items/${id}/add-to-today`, { method: "POST" }),
  createMenuOrder: (payload: { title?: string; note?: string }) =>
    request<MenuOrder>("/api/menu-orders", { method: "POST", body: JSON.stringify(payload) }),
  restoreMenuOrder: (id: string) => request<TodayMenuItem[]>(`/api/menu-orders/${id}/restore`, { method: "POST" }),
  addMenuItem: (recipe_id: string, servings = 1, note = "") =>
    request<TodayMenuItem>("/api/today-menu/items", { method: "POST", body: JSON.stringify({ recipe_id, servings, note }) }),
  updateMenuItem: (id: string, payload: { servings?: number; note?: string }) =>
    request<TodayMenuItem>(`/api/today-menu/items/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  removeMenuItem: (id: string) => request<void>(`/api/today-menu/items/${id}`, { method: "DELETE" }),
  clearMenu: () => request<void>("/api/today-menu/items", { method: "DELETE" })
};

export function mediaUrl(path?: string | null): string | undefined {
  if (!path) return undefined;
  if (path.startsWith("http")) return path;
  if (path.startsWith("/storage")) return `${apiBaseUrl()}${path}`;
  const normalized = path.replace(/\\/g, "/");
  const storageIndex = normalized.lastIndexOf("/storage/");
  if (storageIndex >= 0) {
    return `${apiBaseUrl()}${normalized.slice(storageIndex)}`;
  }
  return undefined;
}
