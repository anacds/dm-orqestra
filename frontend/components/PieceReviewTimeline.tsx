import { PieceReviewEvent } from "@shared/api";
import { CheckCircle, XCircle, Send, AlertTriangle } from "lucide-react";
import { cn } from "@/lib/utils";

interface PieceReviewTimelineProps {
  events: PieceReviewEvent[];
  channel?: string; // Filter by channel if provided
  pieceId?: string; // Filter by pieceId if provided
}

const EVENT_CONFIG: Record<string, { icon: React.ReactNode; label: string; colorClass: string }> = {
  SUBMITTED: {
    icon: <Send className="h-4 w-4" />,
    label: "Submetido para revisão",
    colorClass: "bg-blue-500",
  },
  APPROVED: {
    icon: <CheckCircle className="h-4 w-4" />,
    label: "Aprovado",
    colorClass: "bg-green-500",
  },
  REJECTED: {
    icon: <XCircle className="h-4 w-4" />,
    label: "Rejeitado",
    colorClass: "bg-red-500",
  },
  MANUALLY_REJECTED: {
    icon: <AlertTriangle className="h-4 w-4" />,
    label: "Rejeitado manualmente",
    colorClass: "bg-orange-500",
  },
};

function formatDateTime(dateStr: string): string {
  const date = new Date(dateStr);
  return date.toLocaleString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatChannel(channel: string): string {
  if (channel === "EMAIL") return "E-mail";
  if (channel === "APP") return "App";
  if (channel === "PUSH") return "Push";
  return channel;
}

function getIaVerdictLabel(verdict: string | undefined): { label: string; className: string } {
  if (!verdict) return { label: "", className: "" };
  switch (verdict.toLowerCase()) {
    case "approved":
      return { label: "Aprovado", className: "text-green-600" };
    case "rejected":
      return { label: "Rejeitado", className: "text-red-600" };
    case "warning":
      return { label: "Atenção", className: "text-yellow-600" };
    default:
      return { label: verdict, className: "" };
  }
}

export function PieceReviewTimeline({ events, channel, pieceId }: PieceReviewTimelineProps) {
  // Filter events if channel or pieceId provided
  const filteredEvents = events.filter((ev) => {
    if (channel && ev.channel !== channel) return false;
    if (pieceId && ev.pieceId !== pieceId) return false;
    return true;
  });

  if (filteredEvents.length === 0) {
    return (
      <div className="text-sm text-foreground/50 py-4 text-center">
        Nenhum histórico de revisão disponível.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {filteredEvents.map((event, index) => {
        const config = EVENT_CONFIG[event.eventType] || EVENT_CONFIG.SUBMITTED;
        const iaVerdict = getIaVerdictLabel(event.iaVerdict);
        const isLast = index === filteredEvents.length - 1;

        return (
          <div key={event.id} className="relative flex gap-4">
            {/* Timeline line */}
            {!isLast && (
              <div className="absolute left-[15px] top-8 w-0.5 h-[calc(100%-8px)] bg-border" />
            )}
            
            {/* Icon */}
            <div
              className={cn(
                "flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center text-white z-10",
                config.colorClass
              )}
            >
              {config.icon}
            </div>

            {/* Content */}
            <div className="flex-1 pb-4">
              <div className="flex items-start justify-between gap-2">
                <div>
                  <p className="text-sm font-medium text-foreground">
                    {config.label}
                  </p>
                  <p className="text-xs text-foreground/60">
                    {event.actorName || event.actorId}
                    {!channel && (
                      <span className="ml-2 text-foreground/40">
                        • {formatChannel(event.channel)}
                        {event.commercialSpace && ` (${event.commercialSpace})`}
                      </span>
                    )}
                  </p>
                </div>
                <span className="text-xs text-foreground/50 whitespace-nowrap">
                  {formatDateTime(event.createdAt)}
                </span>
              </div>

              {/* Event details */}
              <div className="mt-1 space-y-1">
                {event.eventType === "SUBMITTED" && event.iaVerdict && (
                  <p className="text-xs">
                    Parecer IA:{" "}
                    <span className={cn("font-medium", iaVerdict.className)}>
                      {iaVerdict.label}
                    </span>
                  </p>
                )}
                {event.rejectionReason && (
                  <p className="text-xs text-foreground/70 bg-muted p-2 rounded mt-1">
                    Motivo: {event.rejectionReason}
                  </p>
                )}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

export default PieceReviewTimeline;
