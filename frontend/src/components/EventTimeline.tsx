import type { TraceEvent } from "@/types/trace";
import EventCard from "./EventCard";

interface Props {
  events: TraceEvent[];
  /** 会话场景下，每事件所属 trace 的索引（0-based） */
  getSourceIndex?: (e: TraceEvent) => number | undefined;
  /** 会话场景下，每事件所属 trace 的名称 */
  getSourceName?: (e: TraceEvent) => string | undefined;
}

export default function EventTimeline({ events, getSourceIndex, getSourceName }: Props) {
  const sorted = [...events].sort(
    (a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
  );
  if (sorted.length === 0) {
    return (
      <div className="text-center py-12 text-slate-400">
        <p className="text-sm">无事件</p>
      </div>
    );
  }
  return (
    <div className="relative pl-5">
      <span className="absolute left-1.5 top-2 bottom-2 w-px bg-slate-200" aria-hidden />
      <ol className="space-y-2">
        {sorted.map((e, i) => {
          const si = getSourceIndex?.(e);
          const sn = getSourceName?.(e);
          return (
            <li key={e.event_id} className="relative">
              <span
                className={`absolute -left-[14px] top-4 w-2 h-2 rounded-full ring-4 ring-white ${
                  e.is_middleware ? "bg-orange-500" : "bg-indigo-500"
                }`}
                aria-hidden
              />
              <EventCard
                event={e}
                depth={0}
                index={i}
                sourceIndex={si}
                sourceName={sn}
              />
            </li>
          );
        })}
      </ol>
    </div>
  );
}
