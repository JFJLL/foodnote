import { Plus, Utensils } from "lucide-react";
import { mediaUrl } from "../lib/api";
import type { RecipeListItem } from "../types";

type Props = {
  recipes: RecipeListItem[];
  onOpen: (id: string) => void;
  onAdd: (id: string) => void;
};

export function RecipeGrid({ recipes, onOpen, onAdd }: Props) {
  if (!recipes.length) {
    return (
      <section className="flex min-h-[340px] items-center justify-center rounded-lg border border-dashed border-black/15 bg-white p-8 text-center">
        <div className="max-w-sm">
          <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-lg bg-ginger/20 text-ginger">
            <Utensils className="h-7 w-7" />
          </div>
          <h2 className="text-xl font-bold text-ink">还没有菜谱</h2>
          <p className="mt-2 text-sm leading-6 text-ink/60">先导入一条小红书美食链接。没有 API key 时可以用 demo 链接检查本地流程。</p>
        </div>
      </section>
    );
  }

  return (
    <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
      {recipes.map((recipe) => (
        <article key={recipe.id} className="group overflow-hidden rounded-lg border border-black/10 bg-white shadow-sm transition hover:-translate-y-0.5 hover:shadow-soft">
          <button onClick={() => onOpen(recipe.id)} className="block w-full text-left">
            <div className="relative aspect-[4/3] bg-mist">
              {mediaUrl(recipe.cover_path) ? (
                <img src={mediaUrl(recipe.cover_path)} alt={recipe.title} className="h-full w-full object-cover" />
              ) : (
                <div className="flex h-full w-full items-center justify-center bg-[linear-gradient(135deg,#F5F7F2,#F7DFA9_55%,#F4B3A5)] text-sm font-semibold text-ink/55">
                  Foodnote
                </div>
              )}
              <div className="absolute left-3 top-3 rounded-md bg-white/90 px-2 py-1 text-xs font-semibold text-herb">
                {Math.round(recipe.confidence * 100)}%
              </div>
            </div>
            <div className="p-3">
              <h3 className="line-clamp-1 text-base font-bold text-ink">{recipe.title}</h3>
              <p className="mt-1 line-clamp-2 min-h-10 text-sm leading-5 text-ink/60">{recipe.description || "已生成菜谱草稿，建议打开后校对步骤。"}</p>
              <div className="mt-3 flex flex-wrap gap-1.5">
                {recipe.tags.slice(0, 3).map((tag) => (
                  <span key={tag} className="rounded-md bg-mist px-2 py-1 text-xs font-medium text-ink/65">
                    {tag}
                  </span>
                ))}
              </div>
            </div>
          </button>
          <div className="flex items-center justify-between border-t border-black/5 px-3 py-2">
            <span className="text-xs text-ink/45">{recipe.source_platform}</span>
            <button
              onClick={() => onAdd(recipe.id)}
              className="inline-flex h-8 items-center gap-1 rounded-lg bg-tomato px-3 text-xs font-bold text-white transition hover:bg-tomato/90"
            >
              <Plus className="h-4 w-4" />
              加菜单
            </button>
          </div>
        </article>
      ))}
    </section>
  );
}
