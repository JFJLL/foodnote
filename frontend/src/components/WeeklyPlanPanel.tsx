import { CalendarDays, Plus, Sparkles } from "lucide-react";
import type { WeeklyPlan, WeeklyPlanItem } from "../types";

type Props = {
  plan: WeeklyPlan | null;
  loading: boolean;
  onGenerate: () => void;
  onAddItem: (itemId: string) => void;
};

export function WeeklyPlanPanel({ plan, loading, onGenerate, onAddItem }: Props) {
  const groups = groupPlanItems(plan?.items || []);

  return (
    <section className="rounded-lg border border-black/10 bg-white p-4 shadow-sm">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div className="flex min-w-0 items-center gap-2">
          <CalendarDays className="h-5 w-5 shrink-0 text-herb" />
          <div className="min-w-0">
            <h2 className="truncate text-base font-black text-ink">本周菜单</h2>
            <p className="text-xs text-ink/50">{plan ? plan.title : "按偏好生成一周午晚餐"}</p>
          </div>
        </div>
        <button
          onClick={onGenerate}
          disabled={loading}
          className="inline-flex h-9 shrink-0 items-center justify-center gap-1.5 rounded-lg bg-herb px-3 text-xs font-bold text-white transition hover:bg-herb/90 disabled:cursor-not-allowed disabled:opacity-60"
        >
          <Sparkles className="h-4 w-4" />
          {plan ? "重生成" : "生成"}
        </button>
      </div>

      {plan ? (
        <div className="max-h-[420px] space-y-3 overflow-y-auto pr-1">
          {groups.map((group) => (
            <div key={group.date}>
              <div className="mb-1 flex items-center justify-between text-xs">
                <span className="font-bold text-ink">{weekdayLabel(group.date, group.dayIndex)}</span>
                <span className="text-ink/45">{group.date}</span>
              </div>
              <div className="space-y-1.5">
                {group.items.map((item) => (
                  <div key={item.id} className="grid grid-cols-[44px_minmax(0,1fr)_34px] items-center gap-2 rounded-lg bg-mist px-2 py-2">
                    <span className="rounded-md bg-white px-1.5 py-1 text-center text-[11px] font-bold text-herb">{item.meal_label}</span>
                    <div className="min-w-0">
                      <p className="truncate text-sm font-bold text-ink">{item.recipe.title}</p>
                      <p className="truncate text-xs text-ink/45">x{item.servings} · {item.recipe.tags.slice(0, 2).join(" / ") || item.recipe.source_platform}</p>
                    </div>
                    <button
                      onClick={() => onAddItem(item.id)}
                      className="flex h-8 w-8 items-center justify-center rounded-lg bg-tomato text-white transition hover:bg-tomato/90"
                      aria-label={`加入今日菜单 ${item.recipe.title}`}
                    >
                      <Plus className="h-4 w-4" />
                    </button>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <p className="rounded-lg bg-mist p-3 text-sm leading-6 text-ink/60">菜谱积累后，生成一周午晚餐计划，再按当天想吃的菜加入今日菜单。</p>
      )}
    </section>
  );
}

function groupPlanItems(items: WeeklyPlanItem[]) {
  const grouped = new Map<string, { date: string; dayIndex: number; items: WeeklyPlanItem[] }>();
  items.forEach((item) => {
    const group = grouped.get(item.date) || { date: item.date, dayIndex: item.day_index, items: [] };
    group.items.push(item);
    grouped.set(item.date, group);
  });
  return Array.from(grouped.values()).sort((left, right) => left.dayIndex - right.dayIndex);
}

function weekdayLabel(date: string, dayIndex: number): string {
  const parsed = new Date(`${date}T00:00:00`);
  const names = ["周日", "周一", "周二", "周三", "周四", "周五", "周六"];
  if (Number.isNaN(parsed.getTime())) return `第 ${dayIndex + 1} 天`;
  return names[parsed.getDay()];
}
