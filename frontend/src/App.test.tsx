import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";
import type { ImportJob } from "./types";

const completedJobs: ImportJob[] = [
  {
    id: "job_1",
    source_url: "demo://xhs/image",
    source_platform: "xiaohongshu",
    status: "completed",
    import_kind: "image",
    progress_message: "Recipe draft ready",
    recipe_id: "recipe_1",
    created_at: "2026-06-10T00:00:00Z",
    updated_at: "2026-06-10T00:00:00Z"
  }
];
let mockJobs = completedJobs;

const recipe = {
  id: "recipe_1",
  title: "番茄鸡蛋面",
  description: "十分钟家常面",
  cover_path: null,
  source_url: "demo://xhs/image",
  source_platform: "xiaohongshu",
  confidence: 0.88,
  tags: ["家常菜"],
  created_at: "2026-06-10T00:00:00Z",
  updated_at: "2026-06-10T00:00:00Z",
  source_title: "番茄鸡蛋面",
  source_author: "Foodnote Demo",
  ingredients: [{ id: "ing_1", position: 0, name: "番茄", amount: "1 个", note: "" }],
  steps: [{ id: "step_1", position: 0, title: "煮面", body: "番茄炒出汁后加水煮面。", media_paths: [] }]
};
const douyinRecipe = {
  ...recipe,
  id: "recipe_2",
  title: "空气炸锅烤虾",
  description: "周末小菜",
  source_url: "demo://douyin/image",
  source_platform: "douyin",
  tags: ["海鲜", "空气炸锅"]
};

const menuItem = { id: "menu_1", recipe_id: "recipe_1", servings: 1, note: "", created_at: "now", recipe };
const menuOrder = {
  id: "order_1",
  title: "今日菜单",
  note: "",
  item_count: 1,
  created_at: "now",
  items: [{ id: "order_item_1", recipe_id: "recipe_1", recipe_title: "番茄鸡蛋面", servings: 1, note: "", position: 0 }]
};
const shoppingItems = [
  { name: "番茄", amount: "1 个 x2", note: "", recipe_titles: ["番茄鸡蛋面"], servings_total: 2 },
  { name: "鸡蛋", amount: "2 个 x2", note: "可替换土鸡蛋", recipe_titles: ["番茄鸡蛋面"], servings_total: 2 }
];
const cookingStats = [{ recipe_id: "recipe_1", recipe_title: "番茄鸡蛋面", cooked_count: 2, servings_total: 3, last_cooked_at: "now" }];
const weeklyPlan = {
  id: "week_1",
  title: "每周菜单 2026-06-15",
  start_date: "2026-06-15",
  days: 7,
  meals_per_day: 2,
  created_at: "now",
  items: [
    {
      id: "week_item_1",
      plan_id: "week_1",
      recipe_id: "recipe_1",
      day_index: 0,
      date: "2026-06-15",
      meal_label: "午餐",
      servings: 2,
      note: "",
      position: 0,
      recipe
    }
  ]
};
const systemStatus = {
  status: "ok",
  mimo_configured: true,
  ffmpeg_available: true,
  faster_whisper_installed: true,
  video_ready: true,
  ytdlp_configured: false,
  ytdlp_available: true,
  asr_model: "medium",
  asr_device: "cuda",
  asr_compute_type: "int8",
  max_upload_mb: 200,
  collectors: {
    xiaohongshu: { command_configured: false, api_configured: false, reachable: false, ready: false },
    douyin: { command_configured: true, api_configured: false, reachable: false, ready: true }
  }
};
const preferences = {
  preferred_tags: ["家常菜"],
  blocked_tags: [],
  disliked_ingredients: [],
  default_servings: 2,
  avoid_recent_days: 14,
  updated_at: "2026-06-10T00:00:00Z"
};
let mockRecipes = [recipe];
let mockMenuItems = [menuItem];
let mockMenuOrders = [menuOrder];
let mockWeeklyPlans = [weeklyPlan];
let failMenuOrders = false;
let lastMenuCreatePayload: Record<string, unknown> | null = null;
let copiedClipboardText: string | null = null;

describe("App", () => {
  beforeEach(() => {
    mockJobs = completedJobs;
    mockRecipes = [recipe];
    mockMenuItems = [menuItem];
    mockMenuOrders = [menuOrder];
    mockWeeklyPlans = [weeklyPlan];
    failMenuOrders = false;
    lastMenuCreatePayload = null;
    copiedClipboardText = null;
    Object.defineProperty(window, "scrollTo", { value: vi.fn(), writable: true });
    Object.defineProperty(window, "confirm", { value: vi.fn(() => true), writable: true });
    Object.defineProperty(window, "navigator", {
      value: {
        ...window.navigator,
        clipboard: {
          writeText: vi.fn(async (text: string) => {
            copiedClipboardText = text;
          })
        }
      },
      configurable: true
    });
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo, init?: RequestInit) => {
        const rawUrl = String(input);
        const parsed = new URL(rawUrl, "http://test.local");
        const url = `${parsed.pathname}${parsed.search}`;
        if (url === "/api/system/status") return json(systemStatus);
        if (url === "/api/preferences") {
          if (init?.method === "PATCH") return json(JSON.parse(String(init.body)));
          return json(preferences);
        }
        if (url === "/api/recipes/random?count=1") return json([recipe]);
        if (parsed.pathname === "/api/recipes") {
          const query = parsed.searchParams.get("query") || "";
          const platform = parsed.searchParams.get("platform") || "";
          return json(
            mockRecipes.filter((item) => {
              const text = [item.title, item.description, item.source_platform, ...item.tags].join(" ");
              return (!query || text.includes(query)) && (!platform || item.source_platform === platform);
            })
          );
        }
        if (url === "/api/import-jobs") {
          if (init?.method === "POST") return json(mockJobs[0], 201);
          return json(mockJobs);
        }
        if (url === "/api/import-jobs/job_failed/retry" && init?.method === "POST") {
          const retryJob: ImportJob = { ...mockJobs[0], id: "job_retry", status: "queued", progress_message: "Waiting to process", error_message: null };
          mockJobs = [retryJob, ...mockJobs];
          return json(retryJob, 201);
        }
        if (url === "/api/today-menu/items") {
          if (init?.method === "POST") {
            lastMenuCreatePayload = JSON.parse(String(init.body));
            return json(menuItem, 201);
          }
          if (init?.method === "DELETE") {
            mockMenuItems = [];
            return new Response(null, { status: 204 });
          }
          return json(mockMenuItems);
        }
        if (url === "/api/menu-orders") {
          if (init?.method === "POST") {
            lastMenuCreatePayload = JSON.parse(String(init.body));
            mockMenuItems = [];
            return json({ ...menuOrder, ...lastMenuCreatePayload }, 201);
          }
          if (failMenuOrders) return json({ detail: "Not Found" }, 404);
          return json(mockMenuOrders);
        }
        if (url.startsWith("/api/menu-orders?query=")) return json(mockMenuOrders);
        if (url === "/api/cooking-stats?limit=8") return json(cookingStats);
        if (url === "/api/weekly-plans?limit=1") return json(mockWeeklyPlans);
        if (url === "/api/weekly-plans" && init?.method === "POST") {
          mockWeeklyPlans = [weeklyPlan];
          return json(weeklyPlan, 201);
        }
        if (url === "/api/weekly-plans/items/week_item_1/add-to-today" && init?.method === "POST") {
          mockMenuItems = [menuItem];
          return json(menuItem, 201);
        }
        if (url === "/api/menu-orders/order_1/restore" && init?.method === "POST") {
          mockMenuItems = [menuItem];
          return json(mockMenuItems);
        }
        if (url === "/api/today-menu/items/menu_1" && init?.method === "PATCH") {
          return json({ id: "menu_1", recipe_id: "recipe_1", servings: 2, note: "少油", created_at: "now", recipe });
        }
        if (url === "/api/today-menu/shopping-list") return json(shoppingItems);
        if (url === "/api/recipes/recipe_1") {
          if (init?.method === "DELETE") {
            mockRecipes = mockRecipes.filter((item) => item.id !== "recipe_1");
            mockMenuItems = mockMenuItems.filter((item) => item.recipe_id !== "recipe_1");
            return new Response(null, { status: 204 });
          }
          return json(recipe);
        }
        return json({});
      })
    );
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("renders recipes and creates import jobs", async () => {
    const user = userEvent.setup();
    render(<App />);
    expect(await screen.findByRole("heading", { name: "番茄鸡蛋面" })).toBeInTheDocument();
    expect(screen.getByText("ASR 可用")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "导入" }));
    await waitFor(() => expect(screen.getByText("已创建导入任务。视频和多模态分析会在后台完成。")).toBeInTheDocument());
  });

  it("opens the recipe drawer", async () => {
    const user = userEvent.setup();
    render(<App />);
    await user.click(await screen.findByRole("button", { name: /番茄鸡蛋面.*十分钟家常面/ }));
    expect(await screen.findByText("菜谱详情")).toBeInTheDocument();
    expect(screen.getByDisplayValue("番茄鸡蛋面")).toBeInTheDocument();
  });

  it("deletes a recipe and keeps menu history intact", async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(await screen.findByRole("button", { name: /番茄鸡蛋面.*十分钟家常面/ }));
    await user.click(await screen.findByRole("button", { name: "删除菜谱" }));

    expect(window.confirm).toHaveBeenCalled();
    expect(await screen.findByText("菜谱已删除，历史菜单记录已保留。")).toBeInTheDocument();
    await waitFor(() => expect(screen.queryByRole("heading", { name: "番茄鸡蛋面" })).not.toBeInTheDocument());
    expect(screen.getByText("最近菜单")).toBeInTheDocument();
  });

  it("searches and filters the recipe library", async () => {
    const user = userEvent.setup();
    mockRecipes = [recipe, douyinRecipe];
    render(<App />);

    expect(await screen.findByRole("heading", { name: "番茄鸡蛋面" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "空气炸锅烤虾" })).toBeInTheDocument();

    await user.type(screen.getByPlaceholderText("搜菜名、标签、作者"), "海鲜");
    await waitFor(() => expect(screen.queryByRole("heading", { name: "番茄鸡蛋面" })).not.toBeInTheDocument());
    expect(screen.getByRole("heading", { name: "空气炸锅烤虾" })).toBeInTheDocument();

    await user.selectOptions(screen.getByLabelText("平台筛选"), "xiaohongshu");
    await waitFor(() => expect(screen.getByText("还没有菜谱")).toBeInTheDocument());
  });

  it("recovers failed import jobs into manual mode", async () => {
    const user = userEvent.setup();
    mockJobs = [
      {
        ...completedJobs[0],
        id: "job_failed",
        source_url: "https://www.douyin.com/video/fake",
        source_platform: "douyin",
        status: "failed",
        progress_message: "Import failed",
        error_message: "未配置 DOUYIN_DOWNLOADER_COMMAND"
      }
    ];

    render(<App />);
    await user.click(await screen.findByRole("button", { name: "手动补录" }));

    expect(screen.getByLabelText("小红书 / 抖音链接")).toHaveValue("https://www.douyin.com/video/fake");
    expect(screen.getByLabelText("平台")).toHaveValue("douyin");
    expect(screen.getByLabelText("类型")).toHaveValue("manual");
  });

  it("retries failed import jobs without losing the failed record", async () => {
    const user = userEvent.setup();
    mockJobs = [
      {
        ...completedJobs[0],
        id: "job_failed",
        source_url: "https://www.douyin.com/video/fake",
        source_platform: "douyin",
        status: "failed",
        progress_message: "Import failed",
        error_message: "采集器临时失败"
      }
    ];

    render(<App />);
    await user.click(await screen.findByRole("button", { name: "重试" }));

    expect(await screen.findByText("已重新创建导入任务，后台会再次解析这个链接。")).toBeInTheDocument();
    expect(await screen.findByText("Waiting to process")).toBeInTheDocument();
    expect(screen.getByText("Import failed")).toBeInTheDocument();
  });

  it("checks out today's menu", async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.clear(await screen.findByLabelText("菜单名称"));
    await user.type(screen.getByLabelText("菜单名称"), "周五晚餐");
    await user.type(screen.getByLabelText("下单备注"), "少辣，多做一份明天带饭");
    await user.click(await screen.findByRole("button", { name: "确认菜单" }));

    expect(lastMenuCreatePayload).toMatchObject({ title: "周五晚餐", note: "少辣，多做一份明天带饭" });
    expect(await screen.findByText("已确认菜单「周五晚餐」：1 道菜。")).toBeInTheDocument();
  });

  it("copies the shopping list as plain text", async () => {
    render(<App />);

    await screen.findByText("鸡蛋");
    fireEvent.click(screen.getByRole("button", { name: "复制买菜清单" }));

    await waitFor(() => expect(copiedClipboardText).toBe("Foodnote 买菜清单\n- 番茄：1 个 x2\n- 鸡蛋：2 个 x2（可替换土鸡蛋）"));
    expect(await screen.findByText("买菜清单已复制。")).toBeInTheDocument();
  });

  it("restores a recent menu into today's menu", async () => {
    const user = userEvent.setup();
    mockMenuItems = [];
    render(<App />);

    await user.click(await screen.findByRole("button", { name: "复用" }));

    expect(await screen.findByText("已复用菜单：1 道菜已加入今日菜单。")).toBeInTheDocument();
  });

  it("shows cooking stats and filters menu history", async () => {
    const user = userEvent.setup();
    render(<App />);

    expect(await screen.findByText("2 次 / 3 份")).toBeInTheDocument();
    await user.type(screen.getByPlaceholderText("搜菜名"), "番茄");
    expect(screen.getByPlaceholderText("搜菜名")).toHaveValue("番茄");
    expect(await screen.findByRole("button", { name: "复用" })).toBeInTheDocument();
  });

  it("generates a weekly plan and adds one meal to today's menu", async () => {
    const user = userEvent.setup();
    mockWeeklyPlans = [];
    render(<App />);

    await user.click(await screen.findByRole("button", { name: "生成" }));
    expect(await screen.findByText("已生成本周菜单。")).toBeInTheDocument();
    expect(screen.getByText("每周菜单 2026-06-15")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "加入今日菜单 番茄鸡蛋面" }));
    expect(await screen.findByText("已加入今日菜单。")).toBeInTheDocument();
  });

  it("keeps recipes visible when an optional section fails", async () => {
    failMenuOrders = true;

    render(<App />);

    expect(await screen.findByRole("heading", { name: "番茄鸡蛋面" })).toBeInTheDocument();
    expect(await screen.findByText("最近菜单加载失败：Not Found")).toBeInTheDocument();
  });

  it("saves taste preferences and uses default servings when adding a dish", async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.clear(await screen.findByLabelText("默认份数"));
    await user.type(screen.getByLabelText("默认份数"), "3");
    await user.click(screen.getByRole("button", { name: "保存偏好" }));
    expect(await screen.findByText("口味偏好已保存。")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "加菜单" }));
    expect(lastMenuCreatePayload).toMatchObject({ recipe_id: "recipe_1", servings: 3 });
  });
});

function json(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json" }
  });
}
