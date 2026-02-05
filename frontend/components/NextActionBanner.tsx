import { Link } from "react-router-dom";
import { 
  Send, 
  Palette, 
  Eye, 
  Wrench, 
  Rocket, 
  CheckCircle,
  ArrowRight,
  AlertTriangle,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Campaign, UserResponse } from "@shared/api";

interface NextAction {
  icon: React.ReactNode;
  title: string;
  description: string;
  color: string;
  bgColor: string;
  borderColor: string;
}

interface NextActionBannerProps {
  campaign: Campaign;
  currentUser?: UserResponse;
  pieceCount?: number;
  approvedPieceCount?: number;
  totalPieceCount?: number;
  hasRejectedPieces?: boolean;
}

function getNextAction(
  campaign: Campaign, 
  currentUser: UserResponse | undefined,
  pieceCount: number,
  approvedPieceCount: number,
  totalPieceCount: number,
  hasRejectedPieces: boolean,
): NextAction | null {
  if (!currentUser) return null;

  const role = currentUser.role;
  const status = campaign.status;

  // Analista de Negócios
  if (role === "Analista de negócios") {
    if (status === "DRAFT" && campaign.createdBy === currentUser.id) {
      return {
        icon: <Send className="h-5 w-5" />,
        title: "Envie para a equipe de criação",
        description: "O briefing está pronto. Envie para a equipe criar as peças.",
        color: "text-blue-700",
        bgColor: "bg-blue-50 dark:bg-blue-950/30",
        borderColor: "border-blue-200 dark:border-blue-800",
      };
    }
    if (status === "CONTENT_REVIEW") {
      if (totalPieceCount === 0) {
        return {
          icon: <Eye className="h-5 w-5" />,
          title: "Aguardando peças para revisão",
          description: "As peças ainda estão sendo carregadas.",
          color: "text-yellow-700",
          bgColor: "bg-yellow-50 dark:bg-yellow-950/30",
          borderColor: "border-yellow-200 dark:border-yellow-800",
        };
      }
      if (approvedPieceCount < totalPieceCount) {
        return {
          icon: <Eye className="h-5 w-5" />,
          title: "Revise as peças criativas",
          description: `${approvedPieceCount} de ${totalPieceCount} peças revisadas. Aprove ou rejeite cada uma.`,
          color: "text-yellow-700",
          bgColor: "bg-yellow-50 dark:bg-yellow-950/30",
          borderColor: "border-yellow-200 dark:border-yellow-800",
        };
      }
      if (hasRejectedPieces) {
        return {
          icon: <AlertTriangle className="h-5 w-5" />,
          title: "Solicite ajustes nas peças rejeitadas",
          description: "Há peças rejeitadas. Clique em 'Solicitar Ajustes' para enviar de volta à criação.",
          color: "text-orange-700",
          bgColor: "bg-orange-50 dark:bg-orange-950/30",
          borderColor: "border-orange-200 dark:border-orange-800",
        };
      }
      return {
        icon: <CheckCircle className="h-5 w-5" />,
        title: "Todas as peças aprovadas!",
        description: "Clique em 'Aprovar Conteúdo' para avançar a campanha.",
        color: "text-green-700",
        bgColor: "bg-green-50 dark:bg-green-950/30",
        borderColor: "border-green-200 dark:border-green-800",
      };
    }
  }

  // Analista de Criação
  if (role === "Analista de criação") {
    if (status === "CREATIVE_STAGE") {
      if (pieceCount === 0) {
        const channels = campaign.communicationChannels?.join(", ") || "definidos";
        return {
          icon: <Palette className="h-5 w-5" />,
          title: "Crie as peças criativas",
          description: `Esta campanha precisa de peças para: ${channels}`,
          color: "text-purple-700",
          bgColor: "bg-purple-50 dark:bg-purple-950/30",
          borderColor: "border-purple-200 dark:border-purple-800",
        };
      }
      return {
        icon: <Send className="h-5 w-5" />,
        title: "Envie para revisão",
        description: `${pieceCount} peça(s) criada(s). Valide e envie para o analista de arte revisar.`,
        color: "text-blue-700",
        bgColor: "bg-blue-50 dark:bg-blue-950/30",
        borderColor: "border-blue-200 dark:border-blue-800",
      };
    }
    if (status === "CONTENT_ADJUSTMENT") {
      return {
        icon: <Wrench className="h-5 w-5" />,
        title: "Ajuste as peças rejeitadas",
        description: "Algumas peças foram rejeitadas. Corrija e reenvie para revisão.",
        color: "text-orange-700",
        bgColor: "bg-orange-50 dark:bg-orange-950/30",
        borderColor: "border-orange-200 dark:border-orange-800",
      };
    }
  }

  // Analista de Campanhas
  if (role === "Analista de campanhas") {
    if (status === "CAMPAIGN_BUILDING") {
      return {
        icon: <Rocket className="h-5 w-5" />,
        title: "Publique a campanha",
        description: "Todas as peças foram aprovadas. A campanha está pronta para construção.",
        color: "text-green-700",
        bgColor: "bg-green-50 dark:bg-green-950/30",
        borderColor: "border-green-200 dark:border-green-800",
      };
    }
  }

  return null;
}

export function NextActionBanner({ 
  campaign, 
  currentUser,
  pieceCount = 0,
  approvedPieceCount = 0,
  totalPieceCount = 0,
  hasRejectedPieces = false,
}: NextActionBannerProps) {
  const nextAction = getNextAction(
    campaign, 
    currentUser, 
    pieceCount,
    approvedPieceCount,
    totalPieceCount,
    hasRejectedPieces,
  );

  if (!nextAction) return null;

  return (
    <div 
      className={cn(
        "p-4 rounded-lg border-2 flex items-start gap-4",
        nextAction.bgColor,
        nextAction.borderColor
      )}
    >
      <div className={cn("p-2 rounded-lg bg-white/50 dark:bg-black/20", nextAction.color)}>
        {nextAction.icon}
      </div>
      <div className="flex-1 min-w-0">
        <h3 className={cn("font-semibold", nextAction.color)}>
          {nextAction.title}
        </h3>
        <p className="text-sm text-foreground/70 mt-0.5">
          {nextAction.description}
        </p>
      </div>
      <ArrowRight className={cn("h-5 w-5 flex-shrink-0 mt-0.5", nextAction.color)} />
    </div>
  );
}

export default NextActionBanner;
