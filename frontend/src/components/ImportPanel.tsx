import { FormEvent, forwardRef, useImperativeHandle, useState } from "react";
import { Link, Loader2, Upload } from "lucide-react";
import type { SourcePlatform } from "../types";

export type ImportPanelHandle = {
  recover: (payload: { sourceUrl: string; sourcePlatform: SourcePlatform; manualText?: string }) => void;
};

type Props = {
  onCreate: (payload: {
    sourceUrl: string;
    sourcePlatform: SourcePlatform;
    manualText?: string;
    importKind: "unknown" | "image" | "video" | "manual";
    files: File[];
  }) => Promise<void>;
  busy: boolean;
};

export const ImportPanel = forwardRef<ImportPanelHandle, Props>(function ImportPanel({ onCreate, busy }, ref) {
  const [sourceUrl, setSourceUrl] = useState("demo://xhs/image");
  const [sourcePlatform, setSourcePlatform] = useState<SourcePlatform>("auto");
  const [manualText, setManualText] = useState("");
  const [importKind, setImportKind] = useState<"unknown" | "image" | "video" | "manual">("unknown");
  const [files, setFiles] = useState<File[]>([]);

  useImperativeHandle(ref, () => ({
    recover(payload) {
      setSourceUrl(payload.sourceUrl);
      setSourcePlatform(payload.sourcePlatform);
      setImportKind("manual");
      setManualText(payload.manualText || "");
      setFiles([]);
    }
  }));

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await onCreate({ sourceUrl, sourcePlatform, manualText, importKind, files });
    setManualText("");
    setFiles([]);
  }

  return (
    <section className="rounded-lg border border-black/10 bg-white p-4 shadow-soft">
      <form onSubmit={submit} className="space-y-4">
        <div className="flex flex-col gap-3 lg:flex-row">
          <label className="min-w-0 flex-1">
            <span className="mb-1 block text-xs font-semibold text-ink/70">小红书 / 抖音链接</span>
            <div className="flex items-center gap-2 rounded-lg border border-black/10 bg-mist px-3 py-2">
              <Link className="h-4 w-4 shrink-0 text-herb" />
              <input
                value={sourceUrl}
                onChange={(event) => setSourceUrl(event.target.value)}
                placeholder="https://www.xiaohongshu.com/..."
                className="min-w-0 flex-1 bg-transparent text-sm text-ink outline-none"
              />
            </div>
          </label>
          <label className="w-full lg:w-44">
            <span className="mb-1 block text-xs font-semibold text-ink/70">平台</span>
            <select
              value={sourcePlatform}
              onChange={(event) => setSourcePlatform(event.target.value as SourcePlatform)}
              className="h-10 w-full rounded-lg border border-black/10 bg-white px-3 text-sm text-ink outline-none focus:border-herb"
            >
              <option value="auto">自动识别</option>
              <option value="xiaohongshu">小红书</option>
              <option value="douyin">抖音</option>
            </select>
          </label>
          <label className="w-full lg:w-44">
            <span className="mb-1 block text-xs font-semibold text-ink/70">类型</span>
            <select
              value={importKind}
              onChange={(event) => setImportKind(event.target.value as typeof importKind)}
              className="h-10 w-full rounded-lg border border-black/10 bg-white px-3 text-sm text-ink outline-none focus:border-herb"
            >
              <option value="unknown">自动判断</option>
              <option value="image">图文</option>
              <option value="video">视频</option>
              <option value="manual">手动文本</option>
            </select>
          </label>
          <button
            disabled={busy || !sourceUrl.trim()}
            className="mt-auto inline-flex h-10 items-center justify-center gap-2 rounded-lg bg-herb px-4 text-sm font-semibold text-white transition hover:bg-herb/90 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Upload className="h-4 w-4" />}
            导入
          </button>
        </div>

        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => {
              setSourceUrl("demo://xhs/image");
              setSourcePlatform("xiaohongshu");
              setImportKind("image");
            }}
            className="rounded-md border border-black/10 bg-white px-3 py-1.5 text-xs font-semibold text-ink transition hover:border-herb hover:text-herb"
          >
            小红书图文 demo
          </button>
          <button
            type="button"
            onClick={() => {
              setSourceUrl("demo://douyin/video");
              setSourcePlatform("douyin");
              setImportKind("video");
            }}
            className="rounded-md border border-black/10 bg-white px-3 py-1.5 text-xs font-semibold text-ink transition hover:border-tomato hover:text-tomato"
          >
            抖音视频 demo
          </button>
        </div>

        <div className="grid gap-3 lg:grid-cols-[1fr_260px]">
          <label>
            <span className="mb-1 block text-xs font-semibold text-ink/70">手动兜底正文</span>
            <textarea
              value={manualText}
              onChange={(event) => setManualText(event.target.value)}
              placeholder="平台抓取失败时，把笔记正文粘贴到这里。"
              className="h-20 w-full resize-none rounded-lg border border-black/10 bg-white px-3 py-2 text-sm leading-6 text-ink outline-none focus:border-herb"
            />
          </label>
          <label>
            <span className="mb-1 block text-xs font-semibold text-ink/70">本地素材</span>
            <input
              type="file"
              multiple
              accept="image/*,video/*"
              onChange={(event) => setFiles(Array.from(event.target.files || []))}
              className="block w-full rounded-lg border border-dashed border-black/20 bg-mist px-3 py-3 text-xs text-ink file:mr-3 file:rounded-md file:border-0 file:bg-ginger file:px-3 file:py-1.5 file:text-xs file:font-semibold file:text-ink"
            />
            <span className="mt-1 block text-xs text-ink/55">{files.length ? `${files.length} 个文件待上传` : "可选：图片或视频"}</span>
          </label>
        </div>
      </form>
    </section>
  );
});
