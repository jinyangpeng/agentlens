import { type ClassValue } from "clsx";
import { cn } from "@/lib/utils";

type Variant = "success" | "failed" | "running" | "neutral" | "info";

const STYLES: Record<Variant, string> = {
  success: "bg-emerald-50 text-emerald-700 ring-emerald-600/20",
  failed: "bg-red-50 text-red-700 ring-red-600/20",
  running: "bg-amber-50 text-amber-700 ring-amber-600/20",
  info: "bg-indigo-50 text-indigo-700 ring-indigo-600/20",
  neutral: "bg-slate-100 text-slate-600 ring-slate-500/20",
};

export function Badge({
  children,
  variant = "neutral",
  className,
}: {
  children: React.ReactNode;
  variant?: Variant;
  className?: ClassValue;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 px-2 py-0.5 text-xs font-medium rounded-md ring-1 ring-inset",
        STYLES[variant],
        className
      )}
    >
      {children}
    </span>
  );
}
