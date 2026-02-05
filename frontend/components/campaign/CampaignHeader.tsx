import { useNavigate } from "react-router-dom";
import { ArrowLeft, Edit2, Save, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { Campaign, UserResponse } from "@shared/api";
import { format } from "date-fns";

interface StatusConfig {
  label: string;
  color: string;
  bg: string;
}

interface CampaignHeaderProps {
  campaign: Campaign;
  currentUser?: UserResponse;
  isEditing: boolean;
  editData: Partial<Campaign>;
  statusConfig: StatusConfig;
  onEditStart: () => void;
  onEditSave: () => void;
  onEditCancel: () => void;
  onEditChange: (data: Partial<Campaign>) => void;
}

export function CampaignHeader({
  campaign,
  currentUser,
  isEditing,
  editData,
  statusConfig,
  onEditStart,
  onEditSave,
  onEditCancel,
  onEditChange,
}: CampaignHeaderProps) {
  const navigate = useNavigate();

  const canEdit =
    currentUser?.role === "Analista de negócios" &&
    campaign.status === "DRAFT" &&
    campaign.createdBy === currentUser.id;

  return (
    <div className="border-b border-border/40 bg-card/50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <button
          onClick={() => navigate("/campaigns")}
          className="flex items-center gap-2 text-primary hover:text-primary/80 transition-colors mb-6"
        >
          <ArrowLeft size={20} />
          Voltar para Campanhas
        </button>

        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div className="flex-1">
            <div className="flex items-center gap-3 mb-3">
              <h1 className="text-3xl sm:text-4xl font-bold text-foreground">
                {isEditing ? (
                  <input
                    type="text"
                    value={editData.name || campaign.name}
                    onChange={(e) =>
                      onEditChange({ ...editData, name: e.target.value })
                    }
                    className="border border-border rounded-lg px-3 py-2 w-full bg-background text-foreground focus:outline-none focus:ring-2 focus:ring-primary"
                  />
                ) : (
                  campaign?.name || ""
                )}
              </h1>
            </div>
            <p className="text-foreground/60 mb-4">
              {campaign?.category} • {campaign?.requestingArea} • Criada por{" "}
              {campaign?.createdByName || "Usuário"} em{" "}
              {campaign?.createdDate
                ? format(new Date(campaign.createdDate), "dd/MM/yyyy")
                : ""}
            </p>
            <div
              className={cn(
                "inline-block px-3 py-1 rounded-full text-sm font-medium",
                statusConfig.bg,
                statusConfig.color
              )}
            >
              {statusConfig.label}
            </div>
          </div>

          <div className="flex gap-2">
            {canEdit && (
              <>
                {isEditing ? (
                  <>
                    <button
                      onClick={onEditSave}
                      className="flex items-center gap-2 px-4 py-2 rounded-lg bg-primary text-white font-medium hover:shadow-lg transition-all"
                    >
                      <Save size={20} />
                      Salvar
                    </button>
                    <button
                      onClick={onEditCancel}
                      className="flex items-center gap-2 px-4 py-2 rounded-lg border border-border/50 text-foreground font-medium hover:bg-muted transition-colors"
                    >
                      <X size={20} />
                      Cancelar
                    </button>
                  </>
                ) : (
                  <button
                    onClick={onEditStart}
                    className="flex items-center gap-2 px-4 py-2 rounded-lg border border-border/50 text-foreground font-medium hover:bg-muted transition-colors"
                  >
                    <Edit2 size={20} />
                    Editar
                  </button>
                )}
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default CampaignHeader;
