import { CampaignStatusEvent } from "@shared/api";
import { cn } from "@/lib/utils";
import { Check, FileText, Palette, Eye, Wrench, Rocket, Flag } from "lucide-react";

interface CampaignStatusTimelineProps {
  events: CampaignStatusEvent[];
  currentStatus: string;
}

// All possible statuses in order
const STATUS_ORDER = [
  "DRAFT",
  "CREATIVE_STAGE",
  "CONTENT_REVIEW",
  "CONTENT_ADJUSTMENT",
  "CAMPAIGN_BUILDING",
  "CAMPAIGN_PUBLISHED",
];

const STATUS_CONFIG: Record<string, { label: string; icon: React.ReactNode; color: string }> = {
  DRAFT: {
    label: "Rascunho",
    icon: <FileText className="h-4 w-4" />,
    color: "bg-gray-500",
  },
  CREATIVE_STAGE: {
    label: "Etapa Criativa",
    icon: <Palette className="h-4 w-4" />,
    color: "bg-blue-500",
  },
  CONTENT_REVIEW: {
    label: "Revisão",
    icon: <Eye className="h-4 w-4" />,
    color: "bg-yellow-500",
  },
  CONTENT_ADJUSTMENT: {
    label: "Ajustes",
    icon: <Wrench className="h-4 w-4" />,
    color: "bg-orange-500",
  },
  CAMPAIGN_BUILDING: {
    label: "Construção",
    icon: <Rocket className="h-4 w-4" />,
    color: "bg-purple-500",
  },
  CAMPAIGN_PUBLISHED: {
    label: "Publicada",
    icon: <Flag className="h-4 w-4" />,
    color: "bg-green-500",
  },
};

function formatDuration(seconds: number | undefined): string {
  if (seconds === undefined || seconds === null) return "";
  
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}min`;
  if (seconds < 86400) {
    const hours = Math.floor(seconds / 3600);
    const mins = Math.floor((seconds % 3600) / 60);
    return mins > 0 ? `${hours}h ${mins}min` : `${hours}h`;
  }
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  return hours > 0 ? `${days}d ${hours}h` : `${days}d`;
}

function formatDateTime(dateStr: string): string {
  const date = new Date(dateStr);
  return date.toLocaleString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function CampaignStatusTimeline({ events, currentStatus }: CampaignStatusTimelineProps) {
  // Build a map of status to event info
  const statusEventMap: Record<string, { event: CampaignStatusEvent; isVisited: boolean }> = {};
  
  for (const ev of events) {
    statusEventMap[ev.toStatus] = { event: ev, isVisited: true };
  }

  // Determine which statuses have been visited
  const visitedStatuses = new Set(events.map(e => e.toStatus));
  
  // Get the index of current status
  const currentIndex = STATUS_ORDER.indexOf(currentStatus);

  // For backwards compatibility: if no events, consider current status as visited
  if (events.length === 0 && currentStatus) {
    visitedStatuses.add(currentStatus);
  }

  // Filter out CONTENT_ADJUSTMENT if it was never visited (optional skip)
  const displayStatuses = STATUS_ORDER.filter(status => {
    // Always show if visited or is current
    if (visitedStatuses.has(status) || status === currentStatus) return true;
    // Show if it comes before current (in normal flow)
    const idx = STATUS_ORDER.indexOf(status);
    if (idx < currentIndex && status !== "CONTENT_ADJUSTMENT") return true;
    // Hide CONTENT_ADJUSTMENT if never visited (it's optional)
    return false;
  });

  return (
    <div className="w-full">
      {/* Horizontal Timeline */}
      <div className="flex items-start justify-between relative">
        {/* Connecting line */}
        <div className="absolute top-4 left-0 right-0 h-0.5 bg-border" style={{ left: '2rem', right: '2rem' }} />
        
        {displayStatuses.map((status, index) => {
          const config = STATUS_CONFIG[status];
          const eventInfo = statusEventMap[status];
          const isVisited = visitedStatuses.has(status);
          const isCurrent = status === currentStatus;
          const isPast = isVisited && !isCurrent;
          
          return (
            <div 
              key={status} 
              className="flex flex-col items-center relative z-10 flex-1"
              style={{ minWidth: '80px', maxWidth: '140px' }}
            >
              {/* Status icon circle */}
              <div
                className={cn(
                  "w-8 h-8 rounded-full flex items-center justify-center text-white transition-all",
                  isCurrent && config.color,
                  isPast && "bg-green-500",
                  !isVisited && !isCurrent && "bg-muted text-muted-foreground"
                )}
              >
                {isPast ? <Check className="h-4 w-4" /> : config.icon}
              </div>
              
              {/* Status label */}
              <span 
                className={cn(
                  "text-xs font-medium mt-2 text-center",
                  isCurrent && "text-foreground font-semibold",
                  isPast && "text-green-600",
                  !isVisited && !isCurrent && "text-foreground/40"
                )}
              >
                {config.label}
              </span>
              
              {/* Duration and date for visited statuses */}
              {eventInfo && (
                <div className="text-center mt-1">
                  <span className="text-[10px] text-foreground/50 block">
                    {formatDateTime(eventInfo.event.createdAt)}
                  </span>
                  {eventInfo.event.durationSeconds !== undefined && eventInfo.event.durationSeconds !== null && (
                    <span className="text-[10px] text-primary font-medium block">
                      {formatDuration(eventInfo.event.durationSeconds)}
                    </span>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default CampaignStatusTimeline;
