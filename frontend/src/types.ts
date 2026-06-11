export type JobStatus = "queued" | "processing" | "failed" | "completed";
export type SourcePlatform = "auto" | "xiaohongshu" | "douyin";

export type ImportJob = {
  id: string;
  source_url: string;
  source_platform: string;
  status: JobStatus;
  import_kind: "unknown" | "image" | "video" | "manual";
  progress_message: string;
  error_message?: string | null;
  recipe_id?: string | null;
  created_at: string;
  updated_at: string;
};

export type Ingredient = {
  id?: string;
  position?: number;
  name: string;
  amount: string;
  note?: string;
};

export type RecipeStep = {
  id?: string;
  position?: number;
  title: string;
  body: string;
  media_paths: string[];
  transcript_excerpt?: string;
  confidence?: number;
};

export type RecipeListItem = {
  id: string;
  title: string;
  description: string;
  cover_path?: string | null;
  source_url: string;
  source_platform: string;
  confidence: number;
  tags: string[];
  created_at: string;
  updated_at: string;
};

export type RecipeDetail = RecipeListItem & {
  source_title?: string | null;
  source_author?: string | null;
  ingredients: Ingredient[];
  steps: RecipeStep[];
};

export type TodayMenuItem = {
  id: string;
  recipe_id: string;
  servings: number;
  note: string;
  created_at: string;
  recipe: RecipeListItem;
};

export type ShoppingListItem = {
  name: string;
  amount: string;
  note: string;
  recipe_titles: string[];
  servings_total: number;
};

export type MenuOrderItem = {
  id: string;
  recipe_id?: string | null;
  recipe_title: string;
  servings: number;
  note: string;
  position: number;
};

export type MenuOrder = {
  id: string;
  title: string;
  note: string;
  item_count: number;
  created_at: string;
  items: MenuOrderItem[];
};

export type CookingStatsItem = {
  recipe_id?: string | null;
  recipe_title: string;
  cooked_count: number;
  servings_total: number;
  last_cooked_at: string;
};

export type WeeklyPlanItem = {
  id: string;
  plan_id: string;
  recipe_id: string;
  day_index: number;
  date: string;
  meal_label: string;
  servings: number;
  note: string;
  position: number;
  recipe: RecipeListItem;
};

export type WeeklyPlan = {
  id: string;
  title: string;
  start_date: string;
  days: number;
  meals_per_day: number;
  created_at: string;
  items: WeeklyPlanItem[];
};

export type CollectorStatus = {
  command_configured: boolean;
  api_configured: boolean;
  reachable: boolean;
  ready: boolean;
};

export type SystemStatus = {
  status: string;
  mimo_configured: boolean;
  ffmpeg_available: boolean;
  faster_whisper_installed: boolean;
  video_ready: boolean;
  ytdlp_configured: boolean;
  ytdlp_available: boolean;
  asr_model: string;
  asr_device: string;
  asr_compute_type: string;
  max_upload_mb: number;
  collectors: Record<"xiaohongshu" | "douyin", CollectorStatus>;
};

export type HouseholdPreferences = {
  preferred_tags: string[];
  blocked_tags: string[];
  disliked_ingredients: string[];
  default_servings: number;
  avoid_recent_days: number;
  updated_at: string;
};
