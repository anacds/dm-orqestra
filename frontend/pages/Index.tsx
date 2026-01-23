import { Link } from "react-router-dom";
import Header from "@/components/Header";
import {
  ArrowRight,
  Clock,
  CheckCircle,
  AlertCircle,
  Plus,
  TrendingUp,
  Loader2,
} from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { campaignsAPI, authAPI } from "@/lib/api";
import { Campaign } from "@shared/api";
import { useMemo } from "react";
import { format } from "date-fns";
import { isBusinessAnalyst } from "@/lib/permissions";

export default function Dashboard() {
  const { data: campaigns = [], isLoading, error } = useQuery({
    queryKey: ["campaigns"],
    queryFn: campaignsAPI.getAll,
  });
  
  const { data: currentUser } = useQuery({
    queryKey: ["currentUser"],
    queryFn: authAPI.getCurrentUser,
    retry: false,
    throwOnError: false,
  });
  
  const canCreateCampaign = isBusinessAnalyst(currentUser?.role);

  const stats = useMemo(() => {
    const validCampaigns = campaigns.filter(c => c.createdDate && !isNaN(new Date(c.createdDate).getTime()));

    const activeCampaigns = validCampaigns.filter(
      (c) => c.status === "DRAFT" || 
             c.status === "CREATIVE_STAGE" || 
             c.status === "CONTENT_REVIEW" || 
             c.status === "CONTENT_ADJUSTMENT" ||
             c.status === "CAMPAIGN_BUILDING"
    ).length;
    const pendingApprovals = validCampaigns.filter((c) => c.status === "CONTENT_REVIEW").length;
    const approvedThisMonth = validCampaigns.filter((c) => {
      if (c.status !== "CAMPAIGN_PUBLISHED") return false;
      const created = new Date(c.createdDate);
      const now = new Date();
      return created.getMonth() === now.getMonth() && created.getFullYear() === now.getFullYear();
    }).length;

    return [
      {
        label: "Campanhas Ativas",
        value: activeCampaigns.toString(),
        icon: TrendingUp,
        color: "text-blue-500",
      },
      {
        label: "Aprovações Pendentes",
        value: pendingApprovals.toString(),
        icon: Clock,
        color: "text-yellow-500",
      },
      {
        label: "Aprovadas Este Mês",
        value: approvedThisMonth.toString(),
        icon: CheckCircle,
        color: "text-green-500",
      },
      {
        label: "Total de Campanhas",
        value: campaigns.length.toString(),
        icon: TrendingUp,
        color: "text-purple-500",
      },
    ];
  }, [campaigns]);

  const recentCampaigns = useMemo(() => {
    return campaigns
      .filter((c) => c.createdDate) // Only include campaigns with valid dates
      .sort((a, b) => {
        const dateA = new Date(a.createdDate).getTime();
        const dateB = new Date(b.createdDate).getTime();
        // Handle invalid dates
        if (isNaN(dateA)) return 1;
        if (isNaN(dateB)) return -1;
        return dateB - dateA;
      })
      .slice(0, 3);
  }, [campaigns]);

      const statusConfig = {
        DRAFT: { label: "Rascunho", color: "text-slate-500" },
        CREATIVE_STAGE: { label: "Etapa Criativa", color: "text-blue-500" },
        CONTENT_REVIEW: { label: "Conteúdo em Revisão", color: "text-yellow-500" },
        CONTENT_ADJUSTMENT: { label: "Ajuste de Conteúdo", color: "text-orange-500" },
        CAMPAIGN_BUILDING: { label: "Campanha em Construção", color: "text-purple-500" },
        CAMPAIGN_PUBLISHED: { label: "Campanha Publicada", color: "text-green-500" },
      };

  return (
    <div className="min-h-screen bg-background">
      <Header />

      {/* Main Content */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Welcome Section */}
        <div className="mb-8">
          <h1 className="text-3xl sm:text-4xl font-bold text-foreground mb-2">
            Meu painel
          </h1>
              <p className="text-foreground/60">
                {campaigns.filter((c) => c.status === "CONTENT_REVIEW").length} aprovações pendentes e{" "}
                {campaigns.filter((c) => c.status === "DRAFT").length} campanhas em rascunho
              </p>
        </div>

        {/* Stats Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
          {stats.map((stat, idx) => {
            const Icon = stat.icon;
            return (
              <div
                key={idx}
                className="p-6 rounded-lg border border-border/50 bg-card"
              >
                <div className="flex items-center justify-between mb-3">
                  <h3 className="text-sm font-medium text-foreground/70">
                    {stat.label}
                  </h3>
                  <Icon className={`size-5 ${stat.color}`} />
                </div>
                <p className="text-2xl sm:text-3xl font-bold text-foreground">
                  {stat.value}
                </p>
              </div>
            );
          })}
        </div>

        {/* Main Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Recent Campaigns - Main Column */}
          <div className="lg:col-span-2">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-2xl font-bold text-foreground">Todas as Campanhas</h2>
              <Link
                to="/campaigns"
                className="text-sm text-primary hover:underline flex items-center gap-1"
              >
                Ver todas <ArrowRight size={16} />
              </Link>
            </div>

            {isLoading ? (
              <div className="text-center py-12">
                <Loader2 className="mx-auto size-8 text-primary animate-spin mb-4" />
                <p className="text-foreground/60">Carregando campanhas...</p>
              </div>
            ) : error ? (
              <div className="text-center py-12 border border-border/50 rounded-lg bg-card">
                <AlertCircle className="mx-auto size-12 text-status-rejected mb-4" />
                <h3 className="text-lg font-semibold text-foreground mb-2">Erro ao carregar campanhas</h3>
                <p className="text-foreground/60 mb-4">
                  {error instanceof Error ? error.message : "Ocorreu um erro inesperado."}
                </p>
              </div>
            ) : campaigns.length === 0 ? (
              <div className="text-center py-12 border border-border/50 rounded-lg bg-card">
                <p className="text-foreground/60 mb-4">Ainda não há campanhas</p>
                {canCreateCampaign && (
                  <Link
                    to="/campaigns/new"
                    className="inline-flex items-center gap-2 px-6 py-2 rounded-lg bg-primary text-white font-semibold hover:shadow-lg transition-all"
                  >
                    <Plus size={20} />
                    Criar Sua Primeira Campanha
                  </Link>
                )}
              </div>
            ) : (
              <div className="space-y-3">
                {campaigns.slice(0, 5).map((campaign) => (
                  <Link
                    key={campaign.id}
                    to={`/campaigns/${campaign.id}`}
                    className="block p-4 rounded-lg border border-border/50 bg-card hover:border-primary/30 transition-colors"
                  >
                    <div className="flex items-center justify-between mb-2">
                      <h3 className="font-semibold text-foreground">{campaign.name}</h3>
                      <span
                        className={`text-xs font-medium ${
                          statusConfig[campaign.status]?.color || "text-foreground/60"
                        }`}
                      >
                        {statusConfig[campaign.status]?.label || campaign.status}
                      </span>
                    </div>
                    <p className="text-sm text-foreground/60 mb-2">{campaign.category}</p>
                    <div className="flex items-center justify-between text-xs">
                      <span className="text-foreground/50">
                        {campaign.createdDate ? (
                          `Criada em ${format(new Date(campaign.createdDate), "dd/MM/yyyy")}`
                        ) : (
                          "Data de criação indisponível"
                        )}
                      </span>
                    </div>
                  </Link>
                ))}
              </div>
            )}
          </div>

          {/* Recent Campaigns - Sidebar */}
          <div>
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-2xl font-bold text-foreground">
                Campanhas Recentes
              </h2>
              <Link
                to="/campaigns/new"
                className="p-2 hover:bg-muted rounded-lg transition-colors"
              >
                <Plus size={20} />
              </Link>
            </div>

            <div className="space-y-3">
              {recentCampaigns.length === 0 ? (
                <div className="text-center py-8 text-foreground/60 text-sm">
                  Nenhuma campanha recente
                </div>
              ) : (
                recentCampaigns.map((campaign) => (
                  <Link
                    key={campaign.id}
                    to={`/campaigns/${campaign.id}`}
                    className="block p-4 rounded-lg border border-border/50 bg-card hover:border-primary/30 hover:shadow-md transition-all"
                  >
                    <div className="mb-3">
                      <h3 className="font-semibold text-foreground text-sm mb-1 line-clamp-2">
                        {campaign.name}
                      </h3>
                      <div className="flex items-center gap-2">
                        <span
                          className={`text-xs font-medium ${
                            statusConfig[campaign.status]?.color || "text-foreground/60"
                          }`}
                        >
                          {statusConfig[campaign.status]?.label || campaign.status}
                        </span>
                        <span className="text-xs text-foreground/50">
                          {campaign.createdDate ? format(new Date(campaign.createdDate), "dd/MM") : "N/A"}
                        </span>
                      </div>
                    </div>
                    <div className="space-y-1.5">
                      <div className="flex items-center justify-between text-xs">
                        <span className="text-foreground/60">Canal</span>
                        <span className="text-foreground/70">
                          {campaign.category}
                        </span>
                      </div>
                    </div>
                  </Link>
                ))
              )}
              {canCreateCampaign && (
                <Link
                  to="/campaigns/new"
                  className="block w-full p-4 rounded-lg border border-dashed border-border/50 text-center text-foreground/60 hover:text-foreground hover:border-primary/30 transition-colors"
                >
                  <Plus size={20} className="mx-auto mb-2" />
                  <span className="text-sm font-medium">Criar Campanha</span>
                </Link>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
