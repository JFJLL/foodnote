import { AlertCircle, CheckCircle2, Clock3, Loader2 } from "lucide-react";
import type { ImportJob, SourcePlatform } from "../types";

const statusIcon = {
  queued: <Clock3 className="h-4 w-4" />,
  processing: <Loader2 className="h-4 w-4 animate-spin" />,
  failed: <AlertCircle className="h-4 w-4" />,
  completed: <CheckCircle2 className="h-4 w-4" />
};

export function JobList({
  jobs,
  onRecover
}: {
  jobs: ImportJob[];
  onRecover?: (job: ImportJob) => void;
}) {
  const visible = jobs.slice(0, 4);
  if (!visible.length) return null;

  return (
    <section className="rounded-lg border border-black/10 bg-white p-3">
      <div className="mb-2 flex items-center justify-between">
        <h2 className="text-sm font-bold text-ink">导入状态</h2>
        <span className="text-xs text-ink/50">{jobs.length} 条</span>
      </div>
      <div className="space-y-2">
        {visible.map((job) => (
          <article key={job.id} className="rounded-lg bg-mist px-3 py-2">
            <div className="flex items-center gap-2 text-xs font-semibold text-ink">
              <span className={job.status === "failed" ? "text-tomato" : job.status === "completed" ? "text-herb" : "text-ginger"}>
                {statusIcon[job.status]}
              </span>
              <span className="truncate">{job.progress_message}</span>
            </div>
            {job.error_message ? <p className="mt-1 line-clamp-2 text-xs text-tomato">{job.error_message}</p> : null}
            {job.status === "failed" && onRecover ? (
              <button
                type="button"
                onClick={() => onRecover(job)}
                className="mt-2 rounded-md border border-tomato/30 bg-white px-2 py-1 text-xs font-bold text-tomato transition hover:bg-tomato hover:text-white"
              >
                用这个链接手动补录
              </button>
            ) : null}
          </article>
        ))}
      </div>
    </section>
  );
}

export function recoverPlatform(platform: string): SourcePlatform {
  if (platform === "xiaohongshu" || platform === "douyin") return platform;
  return "auto";
}
