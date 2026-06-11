import { Cpu, ImageUp, Mic2, PlugZap } from "lucide-react";
import type { ReactNode } from "react";
import type { SystemStatus } from "../types";

type Props = {
  status: SystemStatus | null;
};

export function SystemStatusBar({ status }: Props) {
  if (!status) return null;
  return (
    <section className="grid gap-2 rounded-lg border border-black/10 bg-white px-3 py-3 shadow-sm sm:grid-cols-2 lg:grid-cols-4">
      <StatusChip icon={<PlugZap className="h-4 w-4" />} label="Mimo" ready={status.mimo_configured} value={status.mimo_configured ? "已配置" : "未配置"} />
      <StatusChip
        icon={<Mic2 className="h-4 w-4" />}
        label="视频解析"
        ready={status.video_ready}
        value={status.video_ready ? "ASR 可用" : missingVideoParts(status)}
      />
      <StatusChip icon={<Cpu className="h-4 w-4" />} label="ASR" ready value={`${status.asr_model} / ${status.asr_device} / ${status.asr_compute_type}`} />
      <StatusChip
        icon={<ImageUp className="h-4 w-4" />}
        label="采集器"
        ready={status.collectors.xiaohongshu.ready || status.collectors.douyin.ready || status.ytdlp_available}
        value={`小红书${collectorLabel(status.collectors.xiaohongshu)} · 抖音${collectorLabel(status.collectors.douyin)} · yt-dlp${status.ytdlp_available ? "可用" : "未接入"}`}
      />
    </section>
  );
}

function StatusChip({ icon, label, ready, value }: { icon: ReactNode; label: string; ready: boolean; value: string }) {
  return (
    <div className="flex min-w-0 items-center gap-2 rounded-md bg-mist px-3 py-2">
      <span className={ready ? "text-herb" : "text-tomato"}>{icon}</span>
      <div className="min-w-0">
        <p className="text-xs font-bold text-ink">{label}</p>
        <p className="truncate text-xs text-ink/55">{value}</p>
      </div>
    </div>
  );
}

function missingVideoParts(status: SystemStatus): string {
  if (!status.ffmpeg_available && !status.faster_whisper_installed) return "缺少 ffmpeg / faster-whisper";
  if (!status.ffmpeg_available) return "缺少 ffmpeg";
  return "缺少 faster-whisper";
}

function collectorLabel(status: SystemStatus["collectors"]["xiaohongshu"]): string {
  if (status.ready) return "已接入";
  if (status.api_configured || status.command_configured) return "未启动";
  return "未接入";
}
