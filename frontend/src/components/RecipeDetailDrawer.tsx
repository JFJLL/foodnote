import { FormEvent, useEffect, useMemo, useState } from "react";
import { ExternalLink, Save, X } from "lucide-react";
import { mediaUrl } from "../lib/api";
import type { Ingredient, RecipeDetail, RecipeStep } from "../types";

type Props = {
  recipe: RecipeDetail | null;
  onClose: () => void;
  onSave: (recipe: RecipeDetail) => Promise<void>;
};

export function RecipeDetailDrawer({ recipe, onClose, onSave }: Props) {
  const [draft, setDraft] = useState<RecipeDetail | null>(recipe);
  const ingredientText = useMemo(() => (draft?.ingredients || []).map((item) => [item.name, item.amount, item.note || ""].join(" | ")).join("\n"), [draft?.ingredients]);
  const stepText = useMemo(() => (draft?.steps || []).map((item) => [item.title, item.body].filter(Boolean).join("\n")).join("\n---\n"), [draft?.steps]);

  useEffect(() => setDraft(recipe), [recipe]);

  if (!recipe || !draft) return null;

  async function saveDraft() {
    if (!draft) return;
    await onSave(draft);
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await saveDraft();
  }

  function updateIngredients(value: string) {
    const ingredients: Ingredient[] = value
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean)
      .map((line) => {
        const [name, amount = "", note = ""] = line.split("|").map((part) => part.trim());
        return { name, amount, note };
      });
    setDraft((current) => (current ? { ...current, ingredients } : current));
  }

  function updateSteps(value: string) {
    const steps: RecipeStep[] = value
      .split("\n---\n")
      .map((block) => block.trim())
      .filter(Boolean)
      .map((block) => {
        const [title = "", ...bodyLines] = block.split("\n");
        const body = bodyLines.join("\n").trim() || title;
        return { title: body === title ? "" : title.trim(), body, media_paths: [] };
      });
    setDraft((current) => (current ? { ...current, steps } : current));
  }

  return (
    <div className="fixed inset-0 z-50 bg-black/35">
      <div className="ml-auto flex h-full w-full max-w-3xl flex-col bg-white shadow-soft">
        <header className="flex items-center justify-between border-b border-black/10 px-4 py-3">
          <div className="min-w-0">
            <p className="text-xs font-semibold text-herb">菜谱详情</p>
            <h2 className="truncate text-lg font-bold text-ink">{recipe.title}</h2>
          </div>
          <button onClick={onClose} className="rounded-lg p-2 text-ink/60 transition hover:bg-mist hover:text-ink" aria-label="关闭详情">
            <X className="h-5 w-5" />
          </button>
        </header>

        <form onSubmit={submit} className="min-h-0 flex-1 overflow-y-auto p-4">
          <div className="grid gap-4 lg:grid-cols-[220px_1fr]">
            <div>
              <div className="aspect-[4/3] overflow-hidden rounded-lg bg-mist">
                {mediaUrl(draft.cover_path) ? (
                  <img src={mediaUrl(draft.cover_path)} alt={draft.title} className="h-full w-full object-cover" />
                ) : (
                  <div className="flex h-full items-center justify-center bg-[linear-gradient(135deg,#F5F7F2,#F7DFA9,#F4B3A5)] text-sm font-bold text-ink/55">Foodnote</div>
                )}
              </div>
              <a href={draft.source_url} target="_blank" rel="noreferrer" className="mt-3 inline-flex items-center gap-2 rounded-lg border border-black/10 px-3 py-2 text-sm font-semibold text-ink transition hover:border-herb hover:text-herb">
                <ExternalLink className="h-4 w-4" />
                原链接
              </a>
            </div>
            <div className="space-y-3">
              <label className="block">
                <span className="mb-1 block text-xs font-semibold text-ink/65">菜名</span>
                <input
                  value={draft.title}
                  onChange={(event) => setDraft({ ...draft, title: event.target.value })}
                  className="h-10 w-full rounded-lg border border-black/10 px-3 text-sm font-semibold text-ink outline-none focus:border-herb"
                />
              </label>
              <label className="block">
                <span className="mb-1 block text-xs font-semibold text-ink/65">简介</span>
                <textarea
                  value={draft.description}
                  onChange={(event) => setDraft({ ...draft, description: event.target.value })}
                  className="h-20 w-full resize-none rounded-lg border border-black/10 px-3 py-2 text-sm leading-6 text-ink outline-none focus:border-herb"
                />
              </label>
              <label className="block">
                <span className="mb-1 block text-xs font-semibold text-ink/65">标签</span>
                <input
                  value={draft.tags.join("，")}
                  onChange={(event) => setDraft({ ...draft, tags: event.target.value.split(/[，,]/).map((tag) => tag.trim()).filter(Boolean) })}
                  className="h-10 w-full rounded-lg border border-black/10 px-3 text-sm text-ink outline-none focus:border-herb"
                />
              </label>
            </div>
          </div>

          <div className="mt-5 grid gap-4 lg:grid-cols-2">
            <label>
              <span className="mb-1 block text-xs font-semibold text-ink/65">食材，每行：名称 | 用量 | 备注</span>
              <textarea
                value={ingredientText}
                onChange={(event) => updateIngredients(event.target.value)}
                className="h-56 w-full resize-none rounded-lg border border-black/10 px-3 py-2 text-sm leading-6 text-ink outline-none focus:border-herb"
              />
            </label>
            <label>
              <span className="mb-1 block text-xs font-semibold text-ink/65">步骤，用 --- 分隔</span>
              <textarea
                value={stepText}
                onChange={(event) => updateSteps(event.target.value)}
                className="h-56 w-full resize-none rounded-lg border border-black/10 px-3 py-2 text-sm leading-6 text-ink outline-none focus:border-herb"
              />
            </label>
          </div>

          <section className="mt-5">
            <h3 className="mb-2 text-sm font-bold text-ink">制作步骤</h3>
            <div className="space-y-2">
              {draft.steps.map((step, index) => (
                <article key={`${step.title}-${index}`} className="rounded-lg bg-mist p-3">
                  <div className="mb-1 flex items-center gap-2">
                    <span className="flex h-6 w-6 items-center justify-center rounded-md bg-herb text-xs font-bold text-white">{index + 1}</span>
                    <h4 className="text-sm font-bold text-ink">{step.title || "步骤"}</h4>
                  </div>
                  <p className="text-sm leading-6 text-ink/70">{step.body}</p>
                  {step.transcript_excerpt ? <p className="mt-2 text-xs text-ink/45">ASR：{step.transcript_excerpt}</p> : null}
                </article>
              ))}
            </div>
          </section>
        </form>

        <footer className="border-t border-black/10 p-3">
          <button onClick={saveDraft} className="inline-flex h-10 w-full items-center justify-center gap-2 rounded-lg bg-herb px-4 text-sm font-bold text-white transition hover:bg-herb/90">
            <Save className="h-4 w-4" />
            保存修改
          </button>
        </footer>
      </div>
    </div>
  );
}
