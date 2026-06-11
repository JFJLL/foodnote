import { useEffect, useMemo, useRef, useState } from "react";
import { ChefHat, RefreshCw, Search } from "lucide-react";
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
  const [recipeQuery, setRecipeQuery] = useState("");
  const [recipePlatform, setRecipePlatform] = useState("");
  const [orderQuery, setOrderQuery] = useState("");
  const [checkoutTitle, setCheckoutTitle] = useState("今日菜单");
  const [checkoutNote, setCheckoutNote] = useState("");
  const importPanelRef = useRef<ImportPanelHandle>(null);

  const activeJobs = useMemo(() => jobs.filter((job) => job.status === "queued" || job.status === "processing"), [jobs]);

  async function refreshAll() {
    const [nextStatus, nextPreferences, nextRecipes, nextJobs, nextMenu, nextShoppingList, nextOrders, nextCookingStats, nextWeeklyPlans] = await Promise.all([
      loadSection("系统状态", api.systemStatus(), systemStatus),
      loadSection("口味偏好", api.getPreferences(), preferences),
      loadSection("菜谱库", api.listRecipes(recipeQuery, recipePlatform), recipes),
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

  async function deleteRecipe(recipeId: string) {
    const confirmed = window.confirm("删除后会从菜谱库、今日菜单和未确认周计划中移除；历史菜单记录会保留。确定删除这道菜吗？");
    if (!confirmed) return;
    await api.deleteRecipe(recipeId);
    setSelectedRecipe(null);
    await refreshAll();
    setNotice("菜谱已删除，历史菜单记录已保留。");
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
    const title = checkoutTitle.trim() || "今日菜单";
    const order = await api.createMenuOrder({ title, note: checkoutNote.trim() });
    setCheckoutTitle("今日菜单");
    setCheckoutNote("");
    await refreshAll();
    setNotice(`已确认菜单「${order.title}」：${order.item_count} 道菜。`);
  }

  async function restoreMenuOrder(orderId: string) {
    const restoredItems = await api.restoreMenuOrder(orderId);
    await refreshAll();
    setNotice(`已复用菜单：${restoredItems.length} 道菜已加入今日菜单。`);
  }

  async function copyShoppingList() {
    if (!shoppingList.length) {
      setNotice("买菜清单为空。");
      return;
    }
    const text = formatShoppingList(shoppingList);
    if (!window.navigator.clipboard?.writeText) {
      setNotice("当前浏览器不支持一键复制。");
      return;
    }
    await window.navigator.clipboard.writeText(text);
    setNotice("买菜清单已复制。");
  }

  async function updateOrderQuery(query: string) {
    setOrderQuery(query);
    const orders = await api.listMenuOrders(query);
    setMenuOrders(orders);
  }

  async function updateRecipeQuery(query: string) {
    setRecipeQuery(query);
    setRecipes(await api.listRecipes(query, recipePlatform));
  }

  async function updateRecipePlatform(platform: string) {
    setRecipePlatform(platform);
    setRecipes(await api.listRecipes(recipeQuery, platform));
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

  async function retryFailedJob(job: ImportJob) {
    await api.retryJob(job.id);
    await refreshAll();
    setNotice("已重新创建导入任务，后台会再次解析这个链接。");
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
              <div className="flex w-full flex-col gap-2 sm:w-auto sm:flex-row">
                <label className="flex h-10 min-w-0 items-center gap-2 rounded-lg border border-black/10 bg-white px-3 text-sm text-ink shadow-sm sm:w-64">
                  <Search className="h-4 w-4 shrink-0 text-ink/45" />
                  <span className="sr-only">搜索菜谱</span>
                  <input
                    value={recipeQuery}
                    onChange={(event) => updateRecipeQuery(event.target.value).catch((error) => setNotice(error.message))}
                    placeholder="搜菜名、标签、作者"
                    className="min-w-0 flex-1 bg-transparent text-sm outline-none placeholder:text-ink/35"
                  />
                </label>
                <label className="sr-only" htmlFor="recipe-platform-filter">
                  平台筛选
                </label>
                <select
                  id="recipe-platform-filter"
                  value={recipePlatform}
                  onChange={(event) => updateRecipePlatform(event.target.value).catch((error) => setNotice(error.message))}
                  className="h-10 rounded-lg border border-black/10 bg-white px-3 text-sm font-semibold text-ink shadow-sm outline-none transition hover:border-herb focus:border-herb"
                >
                  <option value="">全部平台</option>
                  <option value="xiaohongshu">小红书</option>
                  <option value="douyin">抖音</option>
                </select>
                <button
                  onClick={() => pickRandomRecipe().catch((error) => setNotice(error.message))}
                  className="h-10 rounded-lg border border-black/10 bg-white px-3 text-sm font-bold text-ink shadow-sm transition hover:border-ginger hover:text-ginger"
                >
                  随机一道
                </button>
              </div>
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
              checkoutTitle={checkoutTitle}
              checkoutNote={checkoutNote}
              onOrderQueryChange={(query) => updateOrderQuery(query).catch((error) => setNotice(error.message))}
              onCheckoutTitleChange={setCheckoutTitle}
              onCheckoutNoteChange={setCheckoutNote}
              onUpdate={updateMenuItem}
              onRemove={removeMenuItem}
              onClear={clearMenu}
              onCheckout={checkoutMenu}
              onRestoreOrder={restoreMenuOrder}
              onCopyShoppingList={() => copyShoppingList().catch((error) => setNotice(error.message))}
            />
            <WeeklyPlanPanel
              plan={weeklyPlan}
              loading={weeklyPlanLoading}
              onGenerate={() => generateWeeklyPlan()}
              onAddItem={(itemId) => addWeeklyPlanItemToToday(itemId).catch((error) => setNotice(error.message))}
            />
            <PreferencesPanel preferences={preferences} onSave={savePreferences} />
            <JobList jobs={jobs} onRecover={recoverFailedJob} onRetry={(job) => retryFailedJob(job).catch((error) => setNotice(error.message))} />
          </div>
        </div>
      </div>
      <RecipeDetailDrawer recipe={selectedRecipe} onClose={() => setSelectedRecipe(null)} onSave={saveRecipe} onDelete={deleteRecipe} />
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

function formatShoppingList(items: ShoppingListItem[]): string {
  return [
    "Foodnote 买菜清单",
    ...items.map((item) => {
      const amount = item.amount || `x${item.servings_total}`;
      const note = item.note ? `（${item.note}）` : "";
      return `- ${item.name}：${amount}${note}`;
    })
  ].join("\n");
}
