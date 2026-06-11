import { useEffect, useMemo, useRef, useState } from "react";
import { ChefHat, RefreshCw } from "lucide-react";
import { ImportPanel, type ImportPanelHandle } from "./components/ImportPanel";
import { JobList, recoverPlatform } from "./components/JobList";
import { PreferencesPanel } from "./components/PreferencesPanel";
import { RecipeDetailDrawer } from "./components/RecipeDetailDrawer";
import { RecipeGrid } from "./components/RecipeGrid";
import { SystemStatusBar } from "./components/SystemStatusBar";
import { TodayMenu } from "./components/TodayMenu";
import { WeeklyPlanPanel } from "./components/WeeklyPlanPanel";
import { api } from "./lib/api";
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
} from "./types";

export default function App() {
  const [recipes, setRecipes] = useState<RecipeListItem[]>([]);
  const [jobs, setJobs] = useState<ImportJob[]>([]);
  const [menuItems, setMenuItems] = useState<TodayMenuItem[]>([]);
  const [menuOrders, setMenuOrders] = useState<MenuOrder[]>([]);
  const [cookingStats, setCookingStats] = useState<CookingStatsItem[]>([]);
  const [weeklyPlan, setWeeklyPlan] = useState<WeeklyPlan | null>(null);
  const [shoppingList, setShoppingList] = useState<ShoppingListItem[]>([]);
  const [systemStatus, setSystemStatus] = useState<SystemStatus | null>(null);
  const [preferences, setPreferences] = useState<HouseholdPreferences | null>(null);
  const [selectedRecipe, setSelectedRecipe] = useState<RecipeDetail | null>(null);
  const [busy, setBusy] = useState(false);
  const [weeklyPlanLoading, setWeeklyPlanLoading] = useState(false);
  const [notice, setNotice] = useState<string>("");
  const [orderQuery, setOrderQuery] = useState("");
  const importPanelRef = useRef<ImportPanelHandle>(null);

  const activeJobs = useMemo(() => jobs.filter((job) => job.status === "queued" || job.status === "processing"), [jobs]);

  async function refreshAll() {
    const [nextStatus, nextPreferences, nextRecipes, nextJobs, nextMenu, nextShoppingList, nextOrders, nextCookingStats, nextWeeklyPlans] = await Promise.all([
      loadSection("系统状态", api.systemStatus(), systemStatus),
      loadSection("口味偏好", api.getPreferences(), preferences),
      loadSection("菜谱库", api.listRecipes(), recipes),
      loadSection("导入状态", api.listJobs(), jobs),
      loadSection("今日菜单", api.listMenu(), menuItems),
      loadSection("买菜清单", api.shoppingList(), shoppingList),
      loadSection("最近菜单", api.listMenuOrders(orderQuery), menuOrders),
      loadSection("常做统计", api.cookingStats(), cookingStats),
      loadSection("本周菜单", api.listWeeklyPlans(1), weeklyPlan ? [weeklyPlan] : [])
    ]);
    setSystemStatus(nextStatus.data);
    setPreferences(nextPreferences.data);
    setRecipes(nextRecipes.data);
    setJobs(nextJobs.data);
    setMenuItems(nextMenu.data);
    setShoppingList(nextShoppingList.data);
    setMenuOrders(nextOrders.data);
    setCookingStats(nextCookingStats.data);
    setWeeklyPlan(nextWeeklyPlans.data[0] || null);
    const failed = [nextStatus, nextPreferences, nextRecipes, nextJobs, nextMenu, nextShoppingList, nextOrders, nextCookingStats, nextWeeklyPlans].filter((result) => result.error);
    if (failed.length) {
      setNotice(failed.map((result) => result.error).join("；"));
    }
  }

  useEffect(() => {
    refreshAll().catch((error) => setNotice(error.message));
  }, []);

  useEffect(() => {
    if (!activeJobs.length) return undefined;
    const timer = window.setInterval(() => {
      refreshAll().catch((error) => setNotice(error.message));
    }, 2000);
    return () => window.clearInterval(timer);
  }, [activeJobs.length]);

  async function createImport(payload: {
    sourceUrl: string;
    sourcePlatform: "auto" | "xiaohongshu" | "douyin";
    manualText?: string;
    importKind: "unknown" | "image" | "video" | "manual";
    files: File[];
  }) {
    setBusy(true);
    setNotice("");
    try {
      const uploaded = payload.files.length ? await api.uploadFiles(payload.files) : { paths: [] };
      await api.createJob({
        source_url: payload.sourceUrl.trim(),
        source_platform: payload.sourcePlatform,
        manual_text: payload.manualText?.trim() || undefined,
        media_paths: uploaded.paths,
        import_kind: payload.importKind
      });
      setNotice("已创建导入任务。视频和多模态分析会在后台完成。");
      await refreshAll();
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "导入失败");
    } finally {
      setBusy(false);
    }
  }

  async function openRecipe(id: string) {
    setSelectedRecipe(await api.getRecipe(id));
  }

  async function saveRecipe(recipe: RecipeDetail) {
    const updated = await api.updateRecipe(recipe.id, {
      title: recipe.title,
      description: recipe.description,
      cover_path: recipe.cover_path,
      tags: recipe.tags,
      ingredients: recipe.ingredients,
      steps: recipe.steps
    });
    setSelectedRecipe(updated);
    await refreshAll();
    setNotice("菜谱已保存。");
  }

  async function addMenuItem(recipeId: string) {
    await api.addMenuItem(recipeId, preferences?.default_servings || 1);
    await refreshAll();
  }

  async function savePreferences(nextPreferences: HouseholdPreferences) {
    const updated = await api.updatePreferences(nextPreferences);
    setPreferences(updated);
    setNotice("口味偏好已保存。");
  }

  async function updateMenuItem(itemId: string, payload: { servings?: number; note?: string }) {
    await api.updateMenuItem(itemId, payload);
    await refreshAll();
  }

  async function pickRandomRecipe() {
    const [recipe] = await api.randomRecipes(1);
    if (recipe) {
      await openRecipe(recipe.id);
      setNotice(`随机推荐：${recipe.title}`);
    }
  }

  async function removeMenuItem(itemId: string) {
    await api.removeMenuItem(itemId);
    await refreshAll();
  }

  async function clearMenu() {
    await api.clearMenu();
    await refreshAll();
  }

  async function checkoutMenu() {
    const order = await api.createMenuOrder({ title: "今日菜单" });
    await refreshAll();
    setNotice(`已确认菜单：${order.item_count} 道菜。`);
  }

  async function restoreMenuOrder(orderId: string) {
    const restoredItems = await api.restoreMenuOrder(orderId);
    await refreshAll();
    setNotice(`已复用菜单：${restoredItems.length} 道菜已加入今日菜单。`);
  }

  async function updateOrderQuery(query: string) {
    setOrderQuery(query);
    const orders = await api.listMenuOrders(query);
    setMenuOrders(orders);
  }

  async function generateWeeklyPlan() {
    setWeeklyPlanLoading(true);
    try {
      const plan = await api.createWeeklyPlan({
        days: 7,
        meals_per_day: 2,
        servings: preferences?.default_servings || 1
      });
      setWeeklyPlan(plan);
      setNotice("已生成本周菜单。");
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "生成本周菜单失败");
    } finally {
      setWeeklyPlanLoading(false);
    }
  }

  async function addWeeklyPlanItemToToday(itemId: string) {
    await api.addWeeklyPlanItemToToday(itemId);
    await refreshAll();
    setNotice("已加入今日菜单。");
  }

  function recoverFailedJob(job: ImportJob) {
    importPanelRef.current?.recover({
      sourceUrl: job.source_url,
      sourcePlatform: recoverPlatform(job.source_platform),
      manualText: ""
    });
    setNotice("已回填失败链接。把浏览器里的正文粘贴进手动兜底正文，再重新导入。");
    try {
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch {
      // jsdom does not implement scrollTo; browser users still get the affordance.
    }
  }

  return (
    <main className="min-h-screen bg-mist text-ink">
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-4 px-4 py-4 lg:px-6">
        <header className="flex flex-col gap-3 rounded-lg border border-black/10 bg-white px-4 py-3 shadow-sm sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-herb text-white">
              <ChefHat className="h-6 w-6" />
            </div>
            <div>
              <h1 className="text-xl font-black tracking-normal text-ink">Foodnote</h1>
              <p className="text-sm text-ink/60">链接变菜谱，菜谱变今日菜单</p>
            </div>
          </div>
          <button
            onClick={() => refreshAll().catch((error) => setNotice(error.message))}
            className="inline-flex h-9 items-center justify-center gap-2 rounded-lg border border-black/10 px-3 text-sm font-semibold text-ink transition hover:border-herb hover:text-herb"
          >
            <RefreshCw className="h-4 w-4" />
            刷新
          </button>
        </header>

        <ImportPanel ref={importPanelRef} onCreate={createImport} busy={busy} />
        <SystemStatusBar status={systemStatus} />
        {notice ? <div className="rounded-lg border border-ginger/30 bg-ginger/15 px-3 py-2 text-sm font-medium text-ink">{notice}</div> : null}

        <div className="grid min-w-0 gap-4 lg:grid-cols-[minmax(0,1fr)_320px]">
          <div className="min-w-0 space-y-4">
            <div className="flex flex-wrap items-end justify-between gap-3">
              <div className="min-w-0">
                <h2 className="text-lg font-black text-ink">菜谱库</h2>
                <p className="text-sm text-ink/55">{recipes.length} 道菜，点击查看做法</p>
              </div>
              <button
                onClick={() => pickRandomRecipe().catch((error) => setNotice(error.message))}
                className="rounded-lg border border-black/10 bg-white px-3 py-2 text-sm font-bold text-ink transition hover:border-ginger hover:text-ginger"
              >
                随机一道
              </button>
            </div>
            <RecipeGrid recipes={recipes} onOpen={openRecipe} onAdd={addMenuItem} />
          </div>
          <div className="min-w-0 space-y-4 lg:sticky lg:top-4 lg:self-start">
            <TodayMenu
              items={menuItems}
              orders={menuOrders}
              cookingStats={cookingStats}
              shoppingList={shoppingList}
              orderQuery={orderQuery}
              onOrderQueryChange={(query) => updateOrderQuery(query).catch((error) => setNotice(error.message))}
              onUpdate={updateMenuItem}
              onRemove={removeMenuItem}
              onClear={clearMenu}
              onCheckout={checkoutMenu}
              onRestoreOrder={restoreMenuOrder}
            />
            <WeeklyPlanPanel
              plan={weeklyPlan}
              loading={weeklyPlanLoading}
              onGenerate={() => generateWeeklyPlan()}
              onAddItem={(itemId) => addWeeklyPlanItemToToday(itemId).catch((error) => setNotice(error.message))}
            />
            <PreferencesPanel preferences={preferences} onSave={savePreferences} />
            <JobList jobs={jobs} onRecover={recoverFailedJob} />
          </div>
        </div>
      </div>
      <RecipeDetailDrawer recipe={selectedRecipe} onClose={() => setSelectedRecipe(null)} onSave={saveRecipe} />
    </main>
  );
}

async function loadSection<T>(label: string, request: Promise<T>, fallback: T): Promise<{ data: T; error: string }> {
  try {
    return { data: await request, error: "" };
  } catch (error) {
    const message = error instanceof Error ? error.message : "加载失败";
    return { data: fallback, error: `${label}加载失败：${message}` };
  }
}
