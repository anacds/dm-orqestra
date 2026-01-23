import { Link } from "react-router-dom";
import Header from "@/components/Header";
import { Plus, Search, Clock, CheckCircle, AlertCircle, FileText, Loader2 } from "lucide-react";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { cn } from "@/lib/utils";
import { campaignsAPI, authAPI } from "@/lib/api";
import { Campaign } from "@shared/api";
import { format } from "date-fns";
import { isBusinessAnalyst } from "@/lib/permissions";

const statusConfig = {
      draft: {
        label: "Rascunho",
        color: "text-status-draft",
        bgColor: "bg-status-draft/10",
        icon: FileText,
      },
      creative_stage: {
        label: "Etapa Criativa",
        color: "text-blue-500",
        bgColor: "bg-blue-500/10",
        icon: FileText,
      },
      content_review: {
        label: "Conteúdo em Revisão",
        color: "text-yellow-500",
        bgColor: "bg-yellow-500/10",
        icon: Clock,
      },
      content_adjustment: {
        label: "Ajuste de Conteúdo",
        color: "text-orange-500",
        bgColor: "bg-orange-500/10",
        icon: AlertCircle,
      },
      campaign_building: {
        label: "Campanha em Construção",
        color: "text-purple-500",
        bgColor: "bg-purple-500/10",
        icon: CheckCircle,
      },
      campaign_published: {
        label: "Campanha Publicada",
        color: "text-green-500",
        bgColor: "bg-green-500/10",
        icon: CheckCircle,
      },
    };

export default function Campaigns() {
  const [searchTerm, setSearchTerm] = useState("");
  
  const { data: currentUser } = useQuery({
    queryKey: ["currentUser"],
    queryFn: authAPI.getCurrentUser,
    retry: false,
    throwOnError: false,
  });
  
  const canCreateCampaign = isBusinessAnalyst(currentUser?.role);
  const [selectedStatus, setSelectedStatus] = useState<string | null>(null);

  const { data: campaigns = [], isLoading, error } = useQuery({
    queryKey: ["campaigns"],
    queryFn: campaignsAPI.getAll,
  });

  const filteredCampaigns = campaigns.filter((c) => {
    const matchesSearch = c.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      c.channel.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesStatus = !selectedStatus || c.status.toLowerCase() === selectedStatus;
    return matchesSearch && matchesStatus;
  });

  const formatDate = (dateString: string) => {
    try {
      return format(new Date(dateString), "dd/MM/yyyy");
    } catch {
      return dateString;
    }
  };

  return (
    <div className="min-h-screen bg-background">
      <Header />

      {/* Page Header */}
      <div className="border-b border-border/40 bg-card/50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 mb-8">
            <div>
              <h1 className="text-3xl sm:text-4xl font-bold text-foreground mb-2">
                Campanhas
              </h1>
              <p className="text-foreground/60">
                Gerencie e acompanhe todos os briefings e aprovações de campanhas
              </p>
            </div>
            <Link
              to="/campaigns/new"
              className="inline-flex items-center gap-2 px-4 sm:px-6 py-2 sm:py-3 rounded-lg bg-gradient-to-r from-primary to-secondary text-white font-semibold hover:shadow-lg transition-all"
            >
              <Plus size={20} />
              Nova Campanha
            </Link>
          </div>

          {/* Filters */}
          <div className="flex flex-col sm:flex-row gap-4">
            <div className="flex-1">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-foreground/40 size-5" />
                <input
                  type="text"
                  placeholder="Buscar campanhas..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="w-full pl-10 pr-4 py-2 rounded-lg border border-border/50 bg-background text-foreground placeholder:text-foreground/40 focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary"
                />
              </div>
            </div>
                <div className="flex flex-wrap gap-2">
                  {["draft", "creative_stage", "content_review", "content_adjustment", "campaign_building", "campaign_published"].map((status) => {
                const config = statusConfig[status as keyof typeof statusConfig];
                return (
                  <button
                    key={status}
                    onClick={() => setSelectedStatus(selectedStatus === status ? null : status)}
                    className={cn(
                      "px-3 sm:px-4 py-2 rounded-lg text-sm font-medium transition-colors",
                      selectedStatus === status
                        ? cn(config.bgColor, config.color, "ring-1 ring-offset-0 ring-current")
                        : "bg-muted text-foreground/60 hover:bg-muted/80"
                    )}
                  >
                    {config.label}
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      </div>

      {/* Campaigns List */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {isLoading ? (
          <div className="text-center py-12">
            <Loader2 className="mx-auto size-8 text-primary animate-spin mb-4" />
            <p className="text-foreground/60">Carregando campanhas...</p>
          </div>
        ) : error ? (
          <div className="text-center py-12">
            <AlertCircle className="mx-auto size-12 text-status-rejected mb-4" />
            <h3 className="text-lg font-semibold text-foreground mb-2">Erro ao carregar campanhas</h3>
            <p className="text-foreground/60">{error instanceof Error ? error.message : "Erro desconhecido"}</p>
          </div>
        ) : filteredCampaigns.length === 0 ? (
          <div className="text-center py-12">
            <FileText className="mx-auto size-12 text-foreground/20 mb-4" />
            <h3 className="text-lg font-semibold text-foreground mb-2">Nenhuma campanha encontrada</h3>
            <p className="text-foreground/60 mb-6">
              {searchTerm || selectedStatus ? "Tente ajustar seus filtros" : "Crie sua primeira campanha para começar"}
            </p>
            {!searchTerm && !selectedStatus && canCreateCampaign && (
              <Link
                to="/campaigns/new"
                className="inline-flex items-center gap-2 px-6 py-2 rounded-lg bg-primary text-white font-semibold hover:shadow-lg transition-all"
              >
                <Plus size={20} />
                Criar Campanha
              </Link>
            )}
          </div>
        ) : (
          <div className="space-y-4">
            {filteredCampaigns.map((campaign) => {
              const statusKey = campaign.status.toLowerCase() as keyof typeof statusConfig;
              const StatusIcon = statusConfig[statusKey]?.icon || FileText;
              return (
                <Link
                  key={campaign.id}
                  to={`/campaigns/${campaign.id}`}
                  className="block p-6 rounded-lg border border-border/50 bg-card hover:border-primary/30 hover:shadow-md transition-all duration-300"
                >
                  <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 mb-4">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-start gap-3">
                        <div className={cn("mt-1 p-2 rounded-lg", statusConfig[statusKey]?.bgColor || "bg-muted")}>
                          <StatusIcon className={cn("size-5", statusConfig[statusKey]?.color || "text-foreground/60")} />
                        </div>
                        <div className="min-w-0 flex-1">
                          <h3 className="text-lg font-semibold text-foreground truncate">
                            {campaign.name}
                          </h3>
                          <p className="text-sm text-foreground/60 mt-1">
                            {campaign.category} • {campaign.requestingArea} • Criada em {formatDate(campaign.createdDate)}
                          </p>
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-2 px-3 py-1 rounded-full text-sm font-medium"
                      style={{
                        backgroundColor: `hsl(var(--primary) / 0.1)`,
                        color: `hsl(var(--primary))`,
                      }}>
                      {statusConfig[campaign.status.toLowerCase() as keyof typeof statusConfig]?.label || campaign.status}
                    </div>
                  </div>

                </Link>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
