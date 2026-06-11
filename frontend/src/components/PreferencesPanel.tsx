import { Save, SlidersHorizontal } from "lucide-react";
import { useEffect, useState } from "react";
import type { HouseholdPreferences } from "../types";

type Props = {
  preferences: HouseholdPreferences | null;
  onSave: (preferences: HouseholdPreferences) => Promise<void>;
};

export function PreferencesPanel({ preferences, onSave }: Props) {
  const [preferredTags, setPreferredTags] = useState("");
  const [blockedTags, setBlockedTags] = useState("");
  const [dislikedIngredients, setDislikedIngredients] = useState("");
  const [defaultServings, setDefaultServings] = useState(1);
  const [avoidRecentDays, setAvoidRecentDays] = useState(14);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!preferences) return;
    setPreferredTags(preferences.preferred_tags.join("，"));
    setBlockedTags(preferences.blocked_tags.join("，"));
    setDislikedIngredients(preferences.disliked_ingredients.join("，"));
    setDefaultServings(preferences.default_servings);
    setAvoidRecentDays(preferences.avoid_recent_days);
  }, [preferences]);

  async function save() {
    if (!preferences) return;
    setSaving(true);
    try {
      await onSave({
        ...preferences,
        preferred_tags: splitList(preferredTags),
        blocked_tags: splitList(blockedTags),
        disliked_ingredients: splitList(dislikedIngredients),
        default_servings: defaultServings,
        avoid_recent_days: avoidRecentDays
      });
    } finally {
      setSaving(false);
    }
  }

  if (!preferences) return null;

  return (
    <section className="rounded-lg border border-black/10 bg-white p-4 shadow-sm">
      <div className="mb-3 flex items-center gap-2">
        <SlidersHorizontal className="h-5 w-5 text-herb" />
        <h2 className="text-base font-bold text-ink">口味偏好</h2>
      </div>
      <div className="space-y-3">
        <TextField label="常吃标签" value={preferredTags} onChange={setPreferredTags} placeholder="家常菜，快手" />
        <TextField label="不想吃标签" value={blockedTags} onChange={setBlockedTags} placeholder="油炸，甜口" />
        <TextField label="少用食材" value={dislikedIngredients} onChange={setDislikedIngredients} placeholder="香菜，肥肉" />
        <div className="grid grid-cols-2 gap-2">
          <NumberField label="默认份数" value={defaultServings} min={1} max={20} onChange={setDefaultServings} />
          <NumberField label="避开天数" value={avoidRecentDays} min={0} max={365} onChange={setAvoidRecentDays} />
        </div>
        <button
          onClick={save}
          disabled={saving}
          className="flex h-9 w-full items-center justify-center gap-2 rounded-lg bg-herb text-sm font-bold text-white transition hover:bg-herb/90 disabled:cursor-not-allowed disabled:opacity-60"
        >
          <Save className="h-4 w-4" />
          {saving ? "保存中" : "保存偏好"}
        </button>
      </div>
    </section>
  );
}

function TextField({ label, value, onChange, placeholder }: { label: string; value: string; onChange: (value: string) => void; placeholder: string }) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-semibold text-ink/65">{label}</span>
      <input
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        className="h-9 w-full rounded-lg border border-black/10 px-3 text-sm text-ink outline-none placeholder:text-ink/30 focus:border-herb"
      />
    </label>
  );
}

function NumberField({
  label,
  value,
  min,
  max,
  onChange
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  onChange: (value: number) => void;
}) {
  const [text, setText] = useState(String(value));

  useEffect(() => {
    setText(String(value));
  }, [value]);

  function update(valueText: string) {
    setText(valueText);
    if (!valueText.trim()) return;
    onChange(clamp(Number(valueText), min, max));
  }

  function commit() {
    const next = clamp(Number(text), min, max);
    setText(String(next));
    onChange(next);
  }

  return (
    <label className="block">
      <span className="mb-1 block text-xs font-semibold text-ink/65">{label}</span>
      <input
        inputMode="numeric"
        value={text}
        onBlur={commit}
        onChange={(event) => update(event.target.value)}
        className="h-9 w-full rounded-lg border border-black/10 px-3 text-sm text-ink outline-none focus:border-herb"
      />
    </label>
  );
}

function splitList(value: string): string[] {
  return value
    .split(/[，,]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function clamp(value: number, min: number, max: number): number {
  if (!Number.isFinite(value)) return min;
  return Math.min(max, Math.max(min, Math.round(value)));
}
