import { BarChart3, CheckCircle2, ClipboardCopy, Search, ShoppingBasket, Trash2, X } from "lucide-react";
import type { CookingStatsItem, MenuOrder, ShoppingListItem, TodayMenuItem } from "../types";

type Props = {
  items: TodayMenuItem[];
  orders: MenuOrder[];
  cookingStats: CookingStatsItem[];
  shoppingList: ShoppingListItem[];
  orderQuery: string;
  checkoutTitle: string;
  checkoutNote: string;
  onOrderQueryChange: (query: string) => void;
  onCheckoutTitleChange: (title: string) => void;
  onCheckoutNoteChange: (note: string) => void;
  onUpdate: (id: string, payload: { servings?: number; note?: string }) => void;
  onRemove: (id: string) => void;
  onClear: () => void;
  onCheckout: () => void;
  onRestoreOrder: (id: string) => void;
  onCopyShoppingList: () => void;
};

export function TodayMenu({
  items,
  orders,
  cookingStats,
  shoppingList,
  orderQuery,
  checkoutTitle,
  checkoutNote,
  onOrderQueryChange,
  onCheckoutTitleChange,
  onCheckoutNoteChange,
  onUpdate,
  onRemove,
  onClear,
  onCheckout,
  onRestoreOrder,
  onCopyShoppingList
}: Props) {
  function handleCopyShoppingList() {
    onCopyShoppingList();
  }

  return (
    <aside className="rounded-lg border border-black/10 bg-ink p-4 text-white shadow-soft">
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <ShoppingBasket className="h-5 w-5 text-ginger" />
          <h2 className="text-base font-bold">今日菜单</h2>
        </div>
        {items.length ? (
          <button onClick={onClear} className="rounded-md p-1 text-white/65 transition hover:bg-white/10 hover:text-white" aria-label="清空今日菜单">
            <Trash2 className="h-4 w-4" />
          </button>
        ) : null}
      </div>
      {items.length ? (
        <div className="space-y-2">
          {items.map((item, index) => (
            <div key={item.id} className="rounded-lg bg-white/8 px-3 py-2">
              <div className="grid grid-cols-[1.5rem_minmax(0,1fr)_5.25rem_1.5rem] items-center gap-2 sm:grid-cols-[1.5rem_minmax(0,1fr)_auto_1.5rem]">
                <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-ginger text-xs font-bold text-ink">{index + 1}</span>
                <span className="min-w-0 flex-1 truncate text-sm font-semibold">{item.recipe.title}</span>
                <div className="flex shrink-0 items-center rounded-md bg-white/10">
                  <button
                    onClick={() => onUpdate(item.id, { servings: Math.max(1, item.servings - 1) })}
                    className="h-7 w-7 text-sm font-black text-white/70 transition hover:text-white"
                    aria-label={`${item.recipe.title} 减少份数`}
                  >
                    -
                  </button>
                  <span className="w-7 text-center text-xs font-bold text-white">x{item.servings}</span>
                  <button
                    onClick={() => onUpdate(item.id, { servings: Math.min(20, item.servings + 1) })}
                    className="h-7 w-7 text-sm font-black text-white/70 transition hover:text-white"
                    aria-label={`${item.recipe.title} 增加份数`}
                  >
                    +
                  </button>
                </div>
                <button onClick={() => onRemove(item.id)} className="rounded-md p-1 text-white/55 transition hover:bg-white/10 hover:text-white" aria-label={`移除 ${item.recipe.title}`}>
                  <X className="h-4 w-4" />
                </button>
              </div>
              <input
                key={`${item.id}:${item.note}`}
                defaultValue={item.note}
                onBlur={(event) => {
                  if (event.target.value !== item.note) {
                    onUpdate(item.id, { note: event.target.value });
                  }
                }}
                placeholder="备注口味、份量或想吃时间"
                className="mt-2 h-8 w-full rounded-md border border-white/10 bg-black/10 px-2 text-xs text-white outline-none placeholder:text-white/35 focus:border-ginger"
              />
            </div>
          ))}
          <div className="rounded-lg bg-white/8 p-3">
            <label className="block text-xs font-bold text-white/70" htmlFor="checkout-title">
              菜单名称
            </label>
            <input
              id="checkout-title"
              value={checkoutTitle}
              onChange={(event) => onCheckoutTitleChange(event.target.value)}
              placeholder="例如：周五晚餐"
              className="mt-2 h-8 w-full rounded-md border border-white/10 bg-black/10 px-2 text-xs text-white outline-none placeholder:text-white/35 focus:border-ginger"
            />
            <label className="mt-3 block text-xs font-bold text-white/70" htmlFor="checkout-note">
              下单备注
            </label>
            <input
              id="checkout-note"
              value={checkoutNote}
              onChange={(event) => onCheckoutNoteChange(event.target.value)}
              placeholder="例如：少辣，多做一份明天带饭"
              className="mt-2 h-8 w-full rounded-md border border-white/10 bg-black/10 px-2 text-xs text-white outline-none placeholder:text-white/35 focus:border-ginger"
            />
          </div>
          <button
            onClick={onCheckout}
            className="flex h-10 w-full items-center justify-center gap-2 rounded-lg bg-ginger text-sm font-black text-ink transition hover:bg-ginger/90"
          >
            <CheckCircle2 className="h-4 w-4" />
            确认菜单
          </button>
          {shoppingList.length ? (
            <div className="mt-4 rounded-lg bg-white/8 p-3">
              <div className="mb-2 flex items-center justify-between gap-2">
                <h3 className="text-xs font-bold text-white/70">买菜清单</h3>
                <button
                  type="button"
                  aria-label="复制买菜清单"
                  onClick={handleCopyShoppingList}
                  className="inline-flex items-center gap-1 rounded-md bg-white/10 px-2 py-1 text-[11px] font-bold text-white transition hover:bg-white/20"
                >
                  <ClipboardCopy className="h-3.5 w-3.5" />
                  复制
                </button>
              </div>
              <div className="space-y-1.5">
                {shoppingList.slice(0, 8).map((item) => (
                  <div key={item.name} className="flex items-center justify-between gap-3 text-xs text-white/75">
                    <span className="truncate">{item.name}</span>
                    <span className="shrink-0 text-white/50">{item.amount || `x${item.servings_total}`}</span>
                  </div>
                ))}
              </div>
            </div>
          ) : null}
        </div>
      ) : (
        <p className="rounded-lg bg-white/8 p-3 text-sm leading-6 text-white/70">从菜谱卡片点加号，把今天想吃的菜先放进来。</p>
      )}
      {orders.length ? (
        <div className="mt-4 rounded-lg bg-white/8 p-3">
          <div className="mb-2 flex items-center justify-between gap-2">
            <h3 className="text-xs font-bold text-white/70">最近菜单</h3>
            <div className="flex min-w-0 flex-1 items-center gap-1 rounded-md bg-black/15 px-2">
              <Search className="h-3.5 w-3.5 shrink-0 text-white/40" />
              <input
                value={orderQuery}
                onChange={(event) => onOrderQueryChange(event.target.value)}
                placeholder="搜菜名"
                className="h-7 min-w-0 flex-1 bg-transparent text-xs text-white outline-none placeholder:text-white/35"
              />
            </div>
          </div>
          <div className="space-y-2">
            {orders.slice(0, 3).map((order) => (
              <div key={order.id} className="text-xs text-white/70">
                <div className="flex items-center justify-between gap-2">
                  <span className="truncate font-bold text-white/85">{order.title}</span>
                  <div className="flex shrink-0 items-center gap-2">
                    <span className="text-white/45">{order.item_count} 道</span>
                    <button
                      onClick={() => onRestoreOrder(order.id)}
                      className="rounded-md bg-white/10 px-2 py-1 text-[11px] font-bold text-white transition hover:bg-white/20"
                    >
                      复用
                    </button>
                  </div>
                </div>
                <p className="mt-1 line-clamp-1 text-white/45">{order.items.map((item) => `${item.recipe_title} x${item.servings}`).join(" / ")}</p>
              </div>
            ))}
          </div>
        </div>
      ) : orderQuery ? (
        <div className="mt-4 rounded-lg bg-white/8 p-3">
          <div className="mb-2 flex items-center gap-1 rounded-md bg-black/15 px-2">
            <Search className="h-3.5 w-3.5 shrink-0 text-white/40" />
            <input
              value={orderQuery}
              onChange={(event) => onOrderQueryChange(event.target.value)}
              placeholder="搜菜名"
              className="h-7 min-w-0 flex-1 bg-transparent text-xs text-white outline-none placeholder:text-white/35"
            />
          </div>
          <p className="text-xs text-white/45">没有匹配的历史菜单</p>
        </div>
      ) : null}
      {cookingStats.length ? (
        <div className="mt-4 rounded-lg bg-white/8 p-3">
          <div className="mb-2 flex items-center gap-2">
            <BarChart3 className="h-4 w-4 text-ginger" />
            <h3 className="text-xs font-bold text-white/70">常做榜</h3>
          </div>
          <div className="space-y-1.5">
            {cookingStats.slice(0, 5).map((item) => (
              <div key={`${item.recipe_id || item.recipe_title}-${item.last_cooked_at}`} className="flex items-center justify-between gap-3 text-xs text-white/70">
                <span className="truncate">{item.recipe_title}</span>
                <span className="shrink-0 text-white/45">
                  {item.cooked_count} 次 / {item.servings_total} 份
                </span>
              </div>
            ))}
          </div>
        </div>
      ) : null}
    </aside>
  );
}
