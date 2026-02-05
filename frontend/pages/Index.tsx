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
  Send,
  Palette,
  Eye,
  Wrench,
  Rocket,
} from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { campaignsAPI, authAPI } from "@/lib/api";
import { Campaign, TaskGroup } from "@shared/api";
import { useMemo } from "react";
import { format, formatDistanceToNow } from "date-fns";
import { ptBR } from "date-fns/locale";
import { isBusinessAnalyst } from "@/lib/permissions";
import { cn } from "@/lib/utils";

const TASK_CONFIG: Record<string, { icon: React.ReactNode; color: string; bgColor: string }> = {
  send_to_creative: {
    icon: <Send className="h-5 w-5" />,
    color: "text-blue-600",
    bgColor: "bg-blue-500/10",
  },
  review_content: {
    icon: <Eye className="h-5 w-5" />,
    color: "text-yellow-600",
    bgColor: "bg-yellow-500/10",
  },
  create_pieces: {
    icon: <Palette className="h-5 w-5" />,
    color: "text-purple-600",
    bgColor: "bg-purple-500/10",
  },
  adjust_pieces: {
    icon: <Wrench className="h-5 w-5" />,
    color: "text-orange-600",
    bgColor: "bg-orange-500/10",
  },
  publish_campaign: {
    icon: <Rocket className="h-5 w-5" />,
    color: "text-green-600",
    bgColor: "bg-green-500/10",
  },
};

const PRIORITY_CONFIG: Record<string, { label: string; color: string }> = {
  "Normal": { label: "Normal", color: "text-foreground/60" },
  "Alta": { label: "Alta", color: "text-orange-500" },
  "Regulatório / Obrigatório": { label: "Regulatório", color: "text-red-500" },
};

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

  const { data: myTasks, isLoading: isLoadingTasks } = useQuery({
    queryKey: ["myTasks"],
    queryFn: campaignsAPI.getMyTasks,
    enabled: !!currentUser,
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

  const statusConfig: Record<string, { label: string; color: string }> = {
    DRAFT: { label: "Rascunho", color: "text-slate-500" },
    CREATIVE_STAGE: { label: "Etapa Criativa", color: "text-blue-500" },
    CONTENT_REVIEW: { label: "Conteúdo em Revisão", color: "text-yellow-500" },
    CONTENT_ADJUSTMENT: { label: "Ajuste de Conteúdo", color: "text-orange-500" },
    CAMPAIGN_BUILDING: { label: "Campanha em Construção", color: "text-purple-500" },
    CAMPAIGN_PUBLISHED: { label: "Campanha Publicada", color: "text-green-500" },
  };

  const getRoleName = (role?: string) => {
    switch (role) {
      case "Analista de negócios": return "Analista de Negócios";
      case "Analista de criação": return "Analista de Criação";
      case "Analista de campanhas": return "Analista de Campanhas";
      default: return role || "Usuário";
    }
  };

  return (
    <div className="min-h-screen bg-background">
      <Header />

      {/* Main Content */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Welcome Section */}
        <div className="mb-8">
          <h1 className="text-3xl sm:text-4xl font-bold text-foreground mb-2">
            Olá, {currentUser?.full_name?.split(" ")[0] || "Usuário"}
          </h1>
          <p className="text-foreground/60">
            {getRoleName(currentUser?.role)} • {myTasks?.totalTasks || 0} tarefas pendentes
          </p>
        </div>

        {/* My Tasks Section - Personalized */}
        {myTasks && myTasks.taskGroups.length > 0 && (
          <div className="mb-8">
            <h2 className="text-xl font-bold text-foreground mb-4 flex items-center gap-2">
              <Clock className="h-5 w-5 text-primary" />
              Suas Tarefas
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {myTasks.taskGroups.map((group) => {
                const config = TASK_CONFIG[group.taskType] || TASK_CONFIG.send_to_creative;
                return (
                  <div
                    key={group.taskType}
                    className="p-4 rounded-lg border border-border/50 bg-card"
                  >
                    <div className="flex items-start gap-3 mb-3">
                      <div className={cn("p-2 rounded-lg", config.bgColor)}>
                        <span className={config.color}>{config.icon}</span>
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between gap-2">
                          <h3 className="font-semibold text-foreground truncate">
                            {group.title}
                          </h3>
                          <span className="flex-shrink-0 px-2 py-0.5 rounded-full bg-primary/10 text-primary text-xs font-medium">
                            {group.count}
                          </span>
                        </div>
                        <p className="text-xs text-foreground/60 mt-0.5">
                          {group.description}
                        </p>
                      </div>
                    </div>
                    <div className="space-y-2">
                      {group.tasks.slice(0, 3).map((task) => {
                        const priorityConfig = PRIORITY_CONFIG[task.priority] || PRIORITY_CONFIG.Normal;
                        return (
                          <Link
                            key={task.id}
                            to={`/campaigns/${task.campaignId}`}
                            className="block p-2 rounded-md bg-muted/50 hover:bg-muted transition-colors"
                          >
                            <div className="flex items-center justify-between gap-2">
                              <span className="text-sm font-medium text-foreground truncate">
                                {task.campaignName}
                              </span>
                              <span className={cn("text-xs flex-shrink-0", priorityConfig.color)}>
                                {priorityConfig.label}
                              </span>
                            </div>
                            <p className="text-xs text-foreground/50 mt-0.5">
                              {formatDistanceToNow(new Date(task.createdAt), { addSuffix: true, locale: ptBR })}
                            </p>
                          </Link>
                        );
                      })}
                      {group.tasks.length > 3 && (
                        <Link
                          to="/campaigns"
                          className="block text-center text-xs text-primary hover:underline py-1"
                        >
                          Ver mais {group.tasks.length - 3} tarefas
                        </Link>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Empty tasks state */}
        {myTasks && myTasks.taskGroups.length === 0 && (
          <div className="mb-8 p-6 rounded-lg border border-border/50 bg-card text-center">
            <CheckCircle className="mx-auto h-12 w-12 text-green-500 mb-3" />
            <h3 className="text-lg font-semibold text-foreground mb-1">
              Tudo em dia!
            </h3>
            <p className="text-sm text-foreground/60">
              Você não tem tarefas pendentes no momento.
            </p>
          </div>
        )}

        {/* Loading tasks */}
        {isLoadingTasks && (
          <div className="mb-8 p-6 rounded-lg border border-border/50 bg-card text-center">
            <Loader2 className="mx-auto h-8 w-8 text-primary animate-spin mb-2" />
            <p className="text-sm text-foreground/60">Carregando suas tarefas...</p>
          </div>
        )}

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
              <h2 className="text-xl font-bold text-foreground">Campanhas Recentes</h2>
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

          {/* Quick Actions - Sidebar */}
          <div>
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-xl font-bold text-foreground">
                Ações Rápidas
              </h2>
            </div>

            <div className="space-y-3">
              {canCreateCampaign && (
                <Link
                  to="/campaigns/new"
                  className="flex items-center gap-3 p-4 rounded-lg border border-primary/30 bg-primary/5 hover:bg-primary/10 transition-colors"
                >
                  <div className="p-2 rounded-lg bg-primary/20">
                    <Plus className="h-5 w-5 text-primary" />
                  </div>
                  <div>
                    <h3 className="font-semibold text-foreground">Nova Campanha</h3>
                    <p className="text-xs text-foreground/60">Criar briefing de campanha</p>
                  </div>
                </Link>
              )}
              
              <Link
                to="/campaigns"
                className="flex items-center gap-3 p-4 rounded-lg border border-border/50 bg-card hover:border-primary/30 transition-colors"
              >
                <div className="p-2 rounded-lg bg-muted">
                  <TrendingUp className="h-5 w-5 text-foreground/70" />
                </div>
                <div>
                  <h3 className="font-semibold text-foreground">Ver Campanhas</h3>
                  <p className="text-xs text-foreground/60">Listar todas as campanhas</p>
                </div>
              </Link>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
