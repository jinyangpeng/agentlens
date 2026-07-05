import { useState } from "react";
import { ChevronRight, ChevronDown, Copy, Check } from "lucide-react";
import { cn } from "@/lib/utils";

interface Props {
  data: unknown;
  label?: string;
  defaultOpen?: boolean;
  className?: string;
}

function format(data: unknown): string {
  if (data === undefined) return "undefined";
  if (data === null) return "null";
  if (typeof data === "string") return data;
  try {
    return JSON.stringify(data, null, 2);
  } catch {
    return String(data);
  }
}

export default function JsonViewer({ data, label, defaultOpen = false, className }: Props) {
  const [open, setOpen] = useState(defaultOpen);
  const [copied, setCopied] = useState(false);
  const text = format(data);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* ignore */
    }
  };

  return (
    <div className={cn("rounded-md border border-slate-200 bg-slate-50/60 overflow-hidden", className)}>
      <div className="flex items-center">
        <button
          onClick={() => setOpen(!open)}
          className="flex items-center flex-1 min-w-0 px-2.5 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-100 transition-colors"
        >
          {open ? (
            <ChevronDown className="w-3.5 h-3.5 mr-1 shrink-0 text-slate-400" />
          ) : (
            <ChevronRight className="w-3.5 h-3.5 mr-1 shrink-0 text-slate-400" />
          )}
          <span className="truncate">{label ?? "JSON"}</span>
        </button>
        <button
          onClick={copy}
          className="p-1.5 mr-1 text-slate-400 hover:text-slate-700 hover:bg-slate-100 rounded transition-colors"
          title="复制"
        >
          {copied ? <Check className="w-3.5 h-3.5 text-emerald-600" /> : <Copy className="w-3.5 h-3.5" />}
        </button>
      </div>
      {open && (
        <pre className="px-3 py-2.5 text-xs mono leading-relaxed overflow-auto max-h-96 text-slate-700 border-t border-slate-200 bg-white">
          {text}
        </pre>
      )}
    </div>
  );
}
