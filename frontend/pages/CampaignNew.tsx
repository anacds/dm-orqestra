import { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQueryClient, useQuery } from "@tanstack/react-query";
import Header from "@/components/Header";
import { ArrowLeft, ArrowRight, Check, Plus, X, Loader2, Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";
import { campaignsAPI, authAPI } from "@/lib/api";
import { EnhanceObjectiveResponse } from "@shared/api";
import { isBusinessAnalyst } from "@/lib/permissions";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  CreateCampaignRequest,
  CampaignCategory,
  RequestingArea,
  CampaignPriority,
  CommunicationChannel,
  CommercialSpace,
  CommunicationTone,
  ExecutionModel,
  TriggerEvent,
} from "@shared/api";
import { useToast } from "@/components/ui/use-toast";

interface CampaignFormData {
  name: string;
  category: CampaignCategory | "";
  businessObjective: string;
  expectedResult: string;
  requestingArea: RequestingArea | "";
  startDate: string;
  endDate: string;
  priority: CampaignPriority | "";
  communicationChannels: CommunicationChannel[];
  commercialSpaces: CommercialSpace[];
  targetAudienceDescription: string;
  exclusionCriteria: string;
  estimatedImpactVolume: string;
  communicationTone: CommunicationTone | "";
  executionModel: ExecutionModel | "";
  triggerEvent: TriggerEvent | "";
  recencyRuleDays: string;
}

const CATEGORIES: CampaignCategory[] = [
  "Aquisição",
  "Cross-sell",
  "Upsell",
  "Retenção",
  "Relacionamento",
  "Regulatório",
  "Educacional",
];

const REQUESTING_AREAS: RequestingArea[] = [
  "Produtos PF",
  "Produtos PJ",
  "Compliance",
  "Canais Digitais",
  "Marketing Institucional",
];

const PRIORITIES: CampaignPriority[] = [
  "Normal",
  "Alta",
  "Regulatório / Obrigatório",
];

const COMMUNICATION_CHANNELS: CommunicationChannel[] = ["SMS", "Push", "E-mail", "App"];

const COMMERCIAL_SPACES: CommercialSpace[] = [
  "Banner superior da Home",
  "Área do Cliente",
  "Página de ofertas",
  "Comprovante do Pix",
];

const COMMUNICATION_TONES: CommunicationTone[] = [
  "Formal",
  "Informal",
  "Urgente",
  "Educativo",
  "Consultivo",
];

const EXECUTION_MODELS: ExecutionModel[] = ["Batch (agendada)", "Event-driven (por evento)"];

const TRIGGER_EVENTS: TriggerEvent[] = [
  "Fatura fechada",
  "Cliente ultrapassa limite do cartão",
  "Login no app",
  "Inatividade por 30 dias",
];

const MIN_CHARACTERS_FOR_ENHANCEMENT = 30;

const steps = [
  { id: 1, label: "Informações Básicas", description: "Dados gerais" },
  { id: 2, label: "Objetivos e Público", description: "Metas e público-alvo" },
  { id: 3, label: "Período e Volume", description: "Vigência e impacto" },
  { id: 4, label: "Comunicação", description: "Canais e execução" },
  { id: 5, label: "Revisão", description: "Confirmar dados" },
];

export default function CampaignNew() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { toast } = useToast();
  
  // checagem de permissões
  const { data: currentUser, isLoading: isLoadingUser } = useQuery({
    queryKey: ["currentUser"],
    queryFn: authAPI.getCurrentUser,
    retry: false,
    throwOnError: false,
  });
  
  const canCreateCampaign = isBusinessAnalyst(currentUser?.role);
  
  // se não tem permissão, redirect
  useEffect(() => {
    if (!isLoadingUser && currentUser && !canCreateCampaign) {
      toast({
        title: "Acesso Negado",
        description: "Apenas analistas de negócios podem criar campanhas.",
        variant: "destructive",
      });
      navigate("/", { replace: true });
    }
  }, [currentUser, isLoadingUser, canCreateCampaign, navigate, toast]);
  
  if (isLoadingUser || (currentUser && !canCreateCampaign)) {
    return null;
  }
  
  const [currentStep, setCurrentStep] = useState(1);
  const [formData, setFormData] = useState<CampaignFormData>({
    name: "",
    category: CATEGORIES[0], // primeiro valor selecionado por padrão
    businessObjective: "",
    expectedResult: "",
    requestingArea: REQUESTING_AREAS[0], // primeiro valor selecionado por padrão
    startDate: "",
    endDate: "",
    priority: PRIORITIES[0], // primeiro valor selecionado por padrão
    communicationChannels: [COMMUNICATION_CHANNELS[0]], // primeiro canal selecionado por padrão
    commercialSpaces: [],
    targetAudienceDescription: "",
    exclusionCriteria: "",
    estimatedImpactVolume: "",
    communicationTone: COMMUNICATION_TONES[0], // primeiro valor selecionado por padrão
    executionModel: EXECUTION_MODELS[0], // primeiro valor selecionado por padrão
    triggerEvent: "",
    recencyRuleDays: "",
  });

  const [errors, setErrors] = useState<Record<string, string>>({});
  const [isEnhanceDialogOpen, setIsEnhanceDialogOpen] = useState(false);
  const [isEnhancing, setIsEnhancing] = useState(false);
  const [enhancementResult, setEnhancementResult] = useState<EnhanceObjectiveResponse | null>(null);
  const [enhancingField, setEnhancingField] = useState<"businessObjective" | "expectedResult" | "targetAudienceDescription" | "exclusionCriteria" | null>(null);
  const [currentInteractionId, setCurrentInteractionId] = useState<string | null>(null);
  
  // gera um session ID único
  const sessionIdRef = useRef<string>(
    `session_${Date.now()}_${Math.random().toString(36).substring(2, 15)}`
  );
  
  const [createdCampaignId, setCreatedCampaignId] = useState<string | null>(null);

  const createMutation = useMutation({
    mutationFn: (data: CreateCampaignRequest) => campaignsAPI.create(data),
    onSuccess: (campaign) => {
      setCreatedCampaignId(campaign.id);
      queryClient.invalidateQueries({ queryKey: ["campaigns"] });
      toast({
        title: "Campanha Criada",
        description: "Sua campanha foi criada com sucesso.",
      });
      navigate(`/campaigns/${campaign.id}`);
    },
    onError: (error: Error) => {
      toast({
        title: "Erro",
        description: error.message || "Falha ao criar campanha. Por favor, tente novamente.",
        variant: "destructive",
      });
    },
  });

  const validateStep = (step: number): boolean => {
    const newErrors: Record<string, string> = {};

    switch (step) {
      case 1:
        if (!formData.name.trim()) newErrors.name = "Nome da campanha é obrigatório";
        if (!formData.category) newErrors.category = "Categoria é obrigatória";
        if (!formData.requestingArea) newErrors.requestingArea = "Área solicitante é obrigatória";
        if (!formData.priority) newErrors.priority = "Prioridade é obrigatória";
        break;
      case 2:
        if (!formData.businessObjective.trim()) newErrors.businessObjective = "Objetivo de negócio é obrigatório";
        if (!formData.expectedResult.trim()) newErrors.expectedResult = "Resultado esperado é obrigatório";
        if (!formData.targetAudienceDescription.trim()) newErrors.targetAudienceDescription = "Descrição do público-alvo é obrigatória";
        if (!formData.exclusionCriteria.trim()) newErrors.exclusionCriteria = "Critérios de exclusão são obrigatórios";
        break;
      case 3:
        if (!formData.startDate) newErrors.startDate = "Data de início é obrigatória";
        if (!formData.endDate) newErrors.endDate = "Data de fim é obrigatória";
        if (formData.startDate && formData.endDate && new Date(formData.startDate) > new Date(formData.endDate)) {
          newErrors.endDate = "Data de fim deve ser posterior à data de início";
        }
        if (!formData.estimatedImpactVolume.trim()) newErrors.estimatedImpactVolume = "Volume estimado é obrigatório";
        const volume = parseFloat(formData.estimatedImpactVolume.replace(/[^\d,.-]/g, "").replace(",", "."));
        if (isNaN(volume) || volume < 0) {
          newErrors.estimatedImpactVolume = "Volume estimado deve ser um valor numérico válido";
        }
        break;
      case 4:
        if (formData.communicationChannels.length === 0) newErrors.communicationChannels = "Selecione pelo menos um canal de comunicação";
        if (formData.communicationChannels.includes("App") && formData.commercialSpaces.length === 0) {
          newErrors.commercialSpaces = "Se App for selecionado, especifique pelo menos um espaço comercial";
        }
        if (!formData.communicationTone) newErrors.communicationTone = "Tom de comunicação é obrigatório";
        if (!formData.executionModel) newErrors.executionModel = "Modelo de execução é obrigatório";
        if (formData.executionModel === "Event-driven (por evento)" && !formData.triggerEvent) {
          newErrors.triggerEvent = "Evento de disparo é obrigatório para execução event-driven";
        }
        if (!formData.recencyRuleDays.trim()) newErrors.recencyRuleDays = "Regra de recência é obrigatória";
        const recency = parseInt(formData.recencyRuleDays);
        if (isNaN(recency) || recency < 0) {
          newErrors.recencyRuleDays = "Regra de recência deve ser um número válido";
        }
        break;
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleNext = () => {
    if (validateStep(currentStep)) {
      setCurrentStep(currentStep + 1);
      setErrors({});
    }
  };

  const handlePrevious = () => {
    setCurrentStep(currentStep - 1);
    setErrors({});
  };

  const handleCreate = () => {
    if (createMutation.isPending) return;

    if (validateStep(5)) {
      const volume = parseFloat(formData.estimatedImpactVolume.replace(/[^\d,.-]/g, "").replace(",", "."));
      const recency = parseInt(formData.recencyRuleDays);

      const campaignData: CreateCampaignRequest = {
        name: formData.name,
        category: formData.category as CampaignCategory,
        businessObjective: formData.businessObjective,
        expectedResult: formData.expectedResult,
        requestingArea: formData.requestingArea as RequestingArea,
        startDate: formData.startDate,
        endDate: formData.endDate,
        priority: formData.priority as CampaignPriority,
        communicationChannels: formData.communicationChannels,
        commercialSpaces: formData.commercialSpaces.length > 0 ? formData.commercialSpaces : undefined,
        targetAudienceDescription: formData.targetAudienceDescription,
        exclusionCriteria: formData.exclusionCriteria,
        estimatedImpactVolume: volume.toString(),
        communicationTone: formData.communicationTone as CommunicationTone,
        executionModel: formData.executionModel as ExecutionModel,
        triggerEvent: formData.triggerEvent || undefined,
        recencyRuleDays: recency,
      };

      createMutation.mutate(campaignData);
    }
  };

  const toggleChannel = (channel: CommunicationChannel) => {
    if (formData.communicationChannels.includes(channel)) {
      setFormData({
        ...formData,
        communicationChannels: formData.communicationChannels.filter((c) => c !== channel),
        commercialSpaces: channel === "App" ? [] : formData.commercialSpaces,
      });
    } else {
      setFormData({
        ...formData,
        communicationChannels: [...formData.communicationChannels, channel],
      });
    }
  };

  const toggleCommercialSpace = (space: CommercialSpace) => {
    if (formData.commercialSpaces.includes(space)) {
      setFormData({
        ...formData,
        commercialSpaces: formData.commercialSpaces.filter((s) => s !== space),
      });
    } else {
      setFormData({
        ...formData,
        commercialSpaces: [...formData.commercialSpaces, space],
      });
    }
  };

  const formatCurrency = (value: string) => {
    const cleaned = value.replace(/[^\d,.-]/g, "");
    if (!cleaned) return "";
    const normalized = cleaned.replace(",", ".");
    const number = parseFloat(normalized);
    if (isNaN(number)) return "";
    return new Intl.NumberFormat("pt-BR", {
      style: "currency",
      currency: "BRL",
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(number);
  };

  const hasEnoughCharacters = (text: string): boolean => {
    return text.trim().length >= MIN_CHARACTERS_FOR_ENHANCEMENT;
  };

  const handleEnhance = async (field: "businessObjective" | "expectedResult" | "targetAudienceDescription" | "exclusionCriteria") => {
    const fieldText = formData[field];
    
    // validação de caracteres mínimos para poder aprimorar texto
    if (!hasEnoughCharacters(fieldText)) {
      toast({
        title: "Texto muito curto",
        description: `O texto precisa ter pelo menos ${MIN_CHARACTERS_FOR_ENHANCEMENT} caracteres para ser aprimorado. Atualmente tem ${fieldText.trim().length} caracteres.`,
        variant: "destructive",
      });
      return;
    }

    if (field === "businessObjective" && !formData.businessObjective.trim()) {
      toast({
        title: "Campo vazio",
        description: "Por favor, preencha o objetivo de negócio antes de aprimorar.",
        variant: "destructive",
      });
      return;
    }

    if (field === "expectedResult") {
      if (!formData.expectedResult.trim()) {
        toast({
          title: "Campo vazio",
          description: "Por favor, preencha o resultado esperado antes de aprimorar.",
          variant: "destructive",
        });
        return;
      }
      if (!formData.businessObjective.trim()) {
        toast({
          title: "Campo obrigatório",
          description: "Por favor, preencha o objetivo de negócio antes de aprimorar o resultado esperado.",
          variant: "destructive",
        });
        return;
      }
    }

    if (field === "targetAudienceDescription") {
      if (!formData.targetAudienceDescription.trim()) {
        toast({
          title: "Campo vazio",
          description: "Por favor, preencha a descrição do público-alvo antes de aprimorar.",
          variant: "destructive",
        });
        return;
      }
      if (!formData.businessObjective.trim()) {
        toast({
          title: "Campo obrigatório",
          description: "Por favor, preencha o objetivo de negócio antes de aprimorar a descrição do público-alvo.",
          variant: "destructive",
        });
        return;
      }
    }

    if (field === "exclusionCriteria") {
      if (!formData.exclusionCriteria.trim()) {
        toast({
          title: "Campo vazio",
          description: "Por favor, preencha os critérios de exclusão antes de aprimorar.",
          variant: "destructive",
        });
        return;
      }
      if (!formData.targetAudienceDescription.trim()) {
        toast({
          title: "Campo obrigatório",
          description: "Por favor, preencha a descrição do público-alvo antes de aprimorar os critérios de exclusão.",
          variant: "destructive",
        });
        return;
      }
    }

    const textToEnhance = formData[field];
    setEnhancingField(field);
    setIsEnhancing(true);
    setIsEnhanceDialogOpen(true);
    setEnhancementResult(null);

    // Monta contexto dos outros campos com valores reais do formulário
    const enhanceableFields = ["businessObjective", "expectedResult", "targetAudienceDescription", "exclusionCriteria"] as const;
    const otherFields: Record<string, string> = {};
    for (const f of enhanceableFields) {
      if (f !== field && formData[f]?.trim()) {
        otherFields[f] = formData[f].trim();
      }
    }

    try {
      const result = await campaignsAPI.enhanceObjective(
        textToEnhance, 
        field,
        createdCampaignId || undefined,
        sessionIdRef.current,
        formData.name.trim() || undefined,
        Object.keys(otherFields).length > 0 ? otherFields : undefined
      );
      setEnhancementResult(result);
      setCurrentInteractionId(result.interactionId); // Store interaction ID for decision tracking
    } catch (error) {
      toast({
        title: "Erro ao aprimorar",
        description: error instanceof Error ? error.message : "Falha ao aprimorar o texto. Tente novamente.",
        variant: "destructive",
      });
      setIsEnhanceDialogOpen(false);
      setEnhancingField(null);
    } finally {
      setIsEnhancing(false);
    }
  };

  const handleApproveEnhancement = async () => {
    if (enhancementResult && enhancingField) {
      if (currentInteractionId) {
        try {
          await campaignsAPI.updateInteractionDecision(currentInteractionId, "approved");
        } catch (error) {
          console.error("Failed to register approval decision:", error);
        }
      }
      
      setFormData({
        ...formData,
        [enhancingField]: enhancementResult.enhancedText,
      });
      setIsEnhanceDialogOpen(false);
      setEnhancementResult(null);
      setEnhancingField(null);
      setCurrentInteractionId(null);
      toast({
        title: "Sugestão aprovada",
        description: "O campo foi atualizado com a sugestão.",
      });
    }
  };

  const handleRejectEnhancement = async () => {
    if (currentInteractionId) {
      try {
        await campaignsAPI.updateInteractionDecision(currentInteractionId, "rejected");
      } catch (error) {
        console.error("Failed to register rejection decision:", error);
      }
    }
    
    setIsEnhanceDialogOpen(false);
    setEnhancementResult(null);
    setEnhancingField(null);
    setCurrentInteractionId(null);
  };

  return (
    <div className="min-h-screen bg-background">
      <Header />

      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="mb-8">
          <button
            onClick={() => navigate("/campaigns")}
            className="flex items-center gap-2 text-primary hover:text-primary/80 transition-colors mb-6"
          >
            <ArrowLeft size={20} />
            Voltar para Campanhas
          </button>
          <h1 className="text-3xl sm:text-4xl font-bold text-foreground">Criar Campanha</h1>
          <p className="text-foreground/60 mt-2">
            Siga estes passos para criar um novo briefing de campanha
          </p>
        </div>

        {/* Step Indicator */}
        <div className="mb-12">
          <div className="flex items-center justify-between mb-8">
            {steps.map((step, idx) => (
              <div key={step.id} className="flex items-center flex-1">
                <div
                  className={cn(
                    "w-10 h-10 rounded-full flex items-center justify-center font-semibold text-sm transition-all",
                    currentStep >= step.id
                      ? "bg-primary text-white"
                      : "bg-muted text-foreground/50"
                  )}
                >
                  {currentStep > step.id ? <Check size={20} /> : <span>{step.id}</span>}
                </div>
                {idx < steps.length - 1 && (
                  <div
                    className={cn(
                      "flex-1 h-1 mx-2 transition-all",
                      currentStep > step.id ? "bg-primary" : "bg-muted"
                    )}
                  />
                )}
              </div>
            ))}
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-5 gap-2 sm:gap-0">
            {steps.map((step) => (
              <div key={step.id} className="text-center">
                <p className="text-xs sm:text-sm font-medium text-foreground">{step.label}</p>
                <p className="text-xs text-foreground/50 hidden sm:block">{step.description}</p>
              </div>
            ))}
          </div>
        </div>

        {/* Form Content */}
        <div className="bg-card border border-border/50 rounded-lg p-6 sm:p-8 mb-8">
          {/* Step 1: Informações Básicas */}
          {currentStep === 1 && (
            <div className="space-y-6">
              <div>
                <label className="block text-sm font-medium text-foreground mb-2">
                  Nome da Campanha *
                </label>
                <input
                  type="text"
                  placeholder="Ex: Campanha de Black Friday 2025"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  className={cn(
                    "w-full px-4 py-2 rounded-lg border bg-background text-foreground placeholder:text-foreground/40 focus:outline-none focus:ring-2 focus:ring-primary/50",
                    errors.name ? "border-red-500" : "border-border/50"
                  )}
                />
                {errors.name && <p className="text-red-500 text-sm mt-1">{errors.name}</p>}
              </div>

              <div>
                <label className="block text-sm font-medium text-foreground mb-2">
                  Categoria da Campanha *
                </label>
                <select
                  value={formData.category}
                  onChange={(e) => setFormData({ ...formData, category: e.target.value as CampaignCategory })}
                  className={cn(
                    "w-full px-4 py-2 rounded-lg border bg-background text-foreground focus:outline-none focus:ring-2 focus:ring-primary/50",
                    errors.category ? "border-red-500" : "border-border/50"
                  )}
                >
                  <option value="">Selecione uma categoria...</option>
                  {CATEGORIES.map((cat) => (
                    <option key={cat} value={cat}>
                      {cat}
                    </option>
                  ))}
                </select>
                {errors.category && <p className="text-red-500 text-sm mt-1">{errors.category}</p>}
              </div>

              <div>
                <label className="block text-sm font-medium text-foreground mb-2">
                  Área Solicitante *
                </label>
                <select
                  value={formData.requestingArea}
                  onChange={(e) => setFormData({ ...formData, requestingArea: e.target.value as RequestingArea })}
                  className={cn(
                    "w-full px-4 py-2 rounded-lg border bg-background text-foreground focus:outline-none focus:ring-2 focus:ring-primary/50",
                    errors.requestingArea ? "border-red-500" : "border-border/50"
                  )}
                >
                  <option value="">Selecione uma área...</option>
                  {REQUESTING_AREAS.map((area) => (
                    <option key={area} value={area}>
                      {area}
                    </option>
                  ))}
                </select>
                {errors.requestingArea && <p className="text-red-500 text-sm mt-1">{errors.requestingArea}</p>}
              </div>

              <div>
                <label className="block text-sm font-medium text-foreground mb-2">
                  Prioridade da Campanha *
                </label>
                <select
                  value={formData.priority}
                  onChange={(e) => setFormData({ ...formData, priority: e.target.value as CampaignPriority })}
                  className={cn(
                    "w-full px-4 py-2 rounded-lg border bg-background text-foreground focus:outline-none focus:ring-2 focus:ring-primary/50",
                    errors.priority ? "border-red-500" : "border-border/50"
                  )}
                >
                  <option value="">Selecione uma prioridade...</option>
                  {PRIORITIES.map((priority) => (
                    <option key={priority} value={priority}>
                      {priority}
                    </option>
                  ))}
                </select>
                {errors.priority && <p className="text-red-500 text-sm mt-1">{errors.priority}</p>}
              </div>
            </div>
          )}

          {/* Step 2: Objetivos e Público */}
          {currentStep === 2 && (
            <div className="space-y-6">
              <div>
                <div className="flex items-center justify-between mb-2">
                  <label className="block text-sm font-medium text-foreground">
                  Objetivo de Negócio *
                </label>
                  {canCreateCampaign && (
                    <TooltipProvider>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <span>
                            <button
                              type="button"
                              onClick={() => handleEnhance("businessObjective")}
                              disabled={isEnhancing || !formData.businessObjective.trim() || !hasEnoughCharacters(formData.businessObjective)}
                              className={cn(
                                "flex items-center gap-2 px-3 py-1.5 text-sm rounded-lg font-medium transition-all",
                                isEnhancing || !formData.businessObjective.trim() || !hasEnoughCharacters(formData.businessObjective)
                                  ? "text-foreground/30 cursor-not-allowed bg-muted"
                                  : "text-primary hover:bg-primary/10 bg-primary/5"
                              )}
                            >
                              {isEnhancing && enhancingField === "businessObjective" ? (
                                <>
                                  <Loader2 size={16} className="animate-spin" />
                                  Aprimorando...
                                </>
                              ) : (
                                <>
                                  <Sparkles size={16} />
                                  Aprimorar
                                </>
                              )}
                            </button>
                          </span>
                        </TooltipTrigger>
                        {!hasEnoughCharacters(formData.businessObjective) && formData.businessObjective.trim() && (
                          <TooltipContent>
                            <p>O texto precisa ter pelo menos {MIN_CHARACTERS_FOR_ENHANCEMENT} caracteres para ser aprimorado ({formData.businessObjective.trim().length}/{MIN_CHARACTERS_FOR_ENHANCEMENT})</p>
                          </TooltipContent>
                        )}
                      </Tooltip>
                    </TooltipProvider>
                  )}
                </div>
                <textarea
                  placeholder="Descreva o objetivo principal desta campanha..."
                  value={formData.businessObjective}
                  onChange={(e) => setFormData({ ...formData, businessObjective: e.target.value })}
                  rows={4}
                  className={cn(
                    "w-full px-4 py-2 rounded-lg border bg-background text-foreground placeholder:text-foreground/40 focus:outline-none focus:ring-2 focus:ring-primary/50",
                    errors.businessObjective ? "border-red-500" : "border-border/50"
                  )}
                />
                {errors.businessObjective && <p className="text-red-500 text-sm mt-1">{errors.businessObjective}</p>}
              </div>

              <div>
                <div className="flex items-center justify-between mb-2">
                  <label className="block text-sm font-medium text-foreground">
                    Resultado Esperado / KPI Principal *
                  </label>
                  {canCreateCampaign && (
                    <TooltipProvider>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <span>
                            <button
                              type="button"
                              onClick={() => handleEnhance("expectedResult")}
                              disabled={isEnhancing || !formData.expectedResult.trim() || !formData.businessObjective.trim() || !hasEnoughCharacters(formData.expectedResult)}
                              className={cn(
                                "flex items-center gap-2 px-3 py-1.5 text-sm rounded-lg font-medium transition-all",
                                isEnhancing || !formData.expectedResult.trim() || !formData.businessObjective.trim() || !hasEnoughCharacters(formData.expectedResult)
                                  ? "text-foreground/30 cursor-not-allowed bg-muted"
                                  : "text-primary hover:bg-primary/10 bg-primary/5"
                              )}
                            >
                              {isEnhancing && enhancingField === "expectedResult" ? (
                                <>
                                  <Loader2 size={16} className="animate-spin" />
                                  Aprimorando...
                                </>
                              ) : (
                                <>
                                  <Sparkles size={16} />
                                  Aprimorar
                                </>
                              )}
                            </button>
                          </span>
                        </TooltipTrigger>
                        {!hasEnoughCharacters(formData.expectedResult) && formData.expectedResult.trim() && formData.businessObjective.trim() && (
                          <TooltipContent>
                            <p>O texto precisa ter pelo menos {MIN_CHARACTERS_FOR_ENHANCEMENT} caracteres para ser aprimorado ({formData.expectedResult.trim().length}/{MIN_CHARACTERS_FOR_ENHANCEMENT})</p>
                          </TooltipContent>
                        )}
                      </Tooltip>
                    </TooltipProvider>
                  )}
                </div>
                <textarea
                  placeholder="Qual resultado ou KPI principal você espera alcançar?"
                  value={formData.expectedResult}
                  onChange={(e) => setFormData({ ...formData, expectedResult: e.target.value })}
                  rows={4}
                  className={cn(
                    "w-full px-4 py-2 rounded-lg border bg-background text-foreground placeholder:text-foreground/40 focus:outline-none focus:ring-2 focus:ring-primary/50",
                    errors.expectedResult ? "border-red-500" : "border-border/50"
                  )}
                />
                {errors.expectedResult && <p className="text-red-500 text-sm mt-1">{errors.expectedResult}</p>}
              </div>

              <div>
                <div className="flex items-center justify-between mb-2">
                  <label className="block text-sm font-medium text-foreground">
                    Descrição do Público-Alvo *
                  </label>
                  {canCreateCampaign && (
                    <TooltipProvider>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <span>
                            <button
                              type="button"
                              onClick={() => handleEnhance("targetAudienceDescription")}
                              disabled={isEnhancing || !formData.targetAudienceDescription.trim() || !formData.businessObjective.trim() || !hasEnoughCharacters(formData.targetAudienceDescription)}
                              className={cn(
                                "flex items-center gap-2 px-3 py-1.5 text-sm rounded-lg font-medium transition-all",
                                isEnhancing || !formData.targetAudienceDescription.trim() || !formData.businessObjective.trim() || !hasEnoughCharacters(formData.targetAudienceDescription)
                                  ? "text-foreground/30 cursor-not-allowed bg-muted"
                                  : "text-primary hover:bg-primary/10 bg-primary/5"
                              )}
                            >
                              {isEnhancing && enhancingField === "targetAudienceDescription" ? (
                                <>
                                  <Loader2 size={16} className="animate-spin" />
                                  Aprimorando...
                                </>
                              ) : (
                                <>
                                  <Sparkles size={16} />
                                  Aprimorar
                                </>
                              )}
                            </button>
                          </span>
                        </TooltipTrigger>
                        {!hasEnoughCharacters(formData.targetAudienceDescription) && formData.targetAudienceDescription.trim() && formData.businessObjective.trim() && (
                          <TooltipContent>
                            <p>O texto precisa ter pelo menos {MIN_CHARACTERS_FOR_ENHANCEMENT} caracteres para ser aprimorado ({formData.targetAudienceDescription.trim().length}/{MIN_CHARACTERS_FOR_ENHANCEMENT})</p>
                          </TooltipContent>
                        )}
                      </Tooltip>
                    </TooltipProvider>
                  )}
                </div>
                <textarea
                  placeholder="Descreva o público-alvo desta campanha..."
                  value={formData.targetAudienceDescription}
                  onChange={(e) => setFormData({ ...formData, targetAudienceDescription: e.target.value })}
                  rows={4}
                  className={cn(
                    "w-full px-4 py-2 rounded-lg border bg-background text-foreground placeholder:text-foreground/40 focus:outline-none focus:ring-2 focus:ring-primary/50",
                    errors.targetAudienceDescription ? "border-red-500" : "border-border/50"
                  )}
                />
                {errors.targetAudienceDescription && <p className="text-red-500 text-sm mt-1">{errors.targetAudienceDescription}</p>}
              </div>

              <div>
                <div className="flex items-center justify-between mb-2">
                  <label className="block text-sm font-medium text-foreground">
                    Critérios de Exclusão *
                  </label>
                  {canCreateCampaign && (
                    <TooltipProvider>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <span>
                            <button
                              type="button"
                              onClick={() => handleEnhance("exclusionCriteria")}
                              disabled={isEnhancing || !formData.exclusionCriteria.trim() || !formData.targetAudienceDescription.trim() || !hasEnoughCharacters(formData.exclusionCriteria)}
                              className={cn(
                                "flex items-center gap-2 px-3 py-1.5 text-sm rounded-lg font-medium transition-all",
                                isEnhancing || !formData.exclusionCriteria.trim() || !formData.targetAudienceDescription.trim() || !hasEnoughCharacters(formData.exclusionCriteria)
                                  ? "text-foreground/30 cursor-not-allowed bg-muted"
                                  : "text-primary hover:bg-primary/10 bg-primary/5"
                              )}
                            >
                              {isEnhancing && enhancingField === "exclusionCriteria" ? (
                                <>
                                  <Loader2 size={16} className="animate-spin" />
                                  Aprimorando...
                                </>
                              ) : (
                                <>
                                  <Sparkles size={16} />
                                  Aprimorar
                                </>
                              )}
                            </button>
                          </span>
                        </TooltipTrigger>
                        {!hasEnoughCharacters(formData.exclusionCriteria) && formData.exclusionCriteria.trim() && formData.targetAudienceDescription.trim() && (
                          <TooltipContent>
                            <p>O texto precisa ter pelo menos {MIN_CHARACTERS_FOR_ENHANCEMENT} caracteres para ser aprimorado ({formData.exclusionCriteria.trim().length}/{MIN_CHARACTERS_FOR_ENHANCEMENT})</p>
                          </TooltipContent>
                        )}
                      </Tooltip>
                    </TooltipProvider>
                  )}
                </div>
                <textarea
                  placeholder="Quais critérios devem ser aplicados para excluir clientes desta campanha?"
                  value={formData.exclusionCriteria}
                  onChange={(e) => setFormData({ ...formData, exclusionCriteria: e.target.value })}
                  rows={4}
                  className={cn(
                    "w-full px-4 py-2 rounded-lg border bg-background text-foreground placeholder:text-foreground/40 focus:outline-none focus:ring-2 focus:ring-primary/50",
                    errors.exclusionCriteria ? "border-red-500" : "border-border/50"
                  )}
                />
                {errors.exclusionCriteria && <p className="text-red-500 text-sm mt-1">{errors.exclusionCriteria}</p>}
              </div>
            </div>
          )}

          {/* Step 3: Período e Volume */}
          {currentStep === 3 && (
            <div className="space-y-6">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
                <div>
                  <label className="block text-sm font-medium text-foreground mb-2">
                    Data de Início *
                  </label>
                  <input
                    type="date"
                    value={formData.startDate}
                    onChange={(e) => setFormData({ ...formData, startDate: e.target.value })}
                    className={cn(
                      "w-full px-4 py-2 rounded-lg border bg-background text-foreground focus:outline-none focus:ring-2 focus:ring-primary/50",
                      errors.startDate ? "border-red-500" : "border-border/50"
                    )}
                  />
                  {errors.startDate && <p className="text-red-500 text-sm mt-1">{errors.startDate}</p>}
                </div>

                <div>
                  <label className="block text-sm font-medium text-foreground mb-2">
                    Data de Fim *
                  </label>
                  <input
                    type="date"
                    value={formData.endDate}
                    onChange={(e) => setFormData({ ...formData, endDate: e.target.value })}
                    min={formData.startDate}
                    className={cn(
                      "w-full px-4 py-2 rounded-lg border bg-background text-foreground focus:outline-none focus:ring-2 focus:ring-primary/50",
                      errors.endDate ? "border-red-500" : "border-border/50"
                    )}
                  />
                  {errors.endDate && <p className="text-red-500 text-sm mt-1">{errors.endDate}</p>}
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-foreground mb-2">
                  Volume Estimado de Impacto (R$) *
                </label>
                <input
                  type="text"
                  placeholder="R$ 0,00"
                  value={formData.estimatedImpactVolume}
                  onChange={(e) => {
                    const formatted = formatCurrency(e.target.value);
                    setFormData({ ...formData, estimatedImpactVolume: formatted });
                  }}
                  className={cn(
                    "w-full px-4 py-2 rounded-lg border bg-background text-foreground placeholder:text-foreground/40 focus:outline-none focus:ring-2 focus:ring-primary/50",
                    errors.estimatedImpactVolume ? "border-red-500" : "border-border/50"
                  )}
                />
                {errors.estimatedImpactVolume && <p className="text-red-500 text-sm mt-1">{errors.estimatedImpactVolume}</p>}
              </div>
            </div>
          )}

          {/* Step 4: Comunicação */}
          {currentStep === 4 && (
            <div className="space-y-6">
              <div>
                <label className="block text-sm font-medium text-foreground mb-2">
                  Canais de Comunicação * (Múltipla seleção)
                </label>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                  {COMMUNICATION_CHANNELS.map((channel) => (
                    <button
                      key={channel}
                      type="button"
                      onClick={() => toggleChannel(channel)}
                      className={cn(
                        "px-4 py-2 rounded-lg border text-sm font-medium transition-colors",
                        formData.communicationChannels.includes(channel)
                          ? "bg-primary text-white border-primary"
                          : "bg-background text-foreground border-border/50 hover:bg-muted"
                      )}
                    >
                      {channel}
                    </button>
                  ))}
                </div>
                {errors.communicationChannels && <p className="text-red-500 text-sm mt-1">{errors.communicationChannels}</p>}
              </div>

              {formData.communicationChannels.includes("App") && (
                <div>
                  <label className="block text-sm font-medium text-foreground mb-2">
                    Espaços Comerciais * (Múltipla seleção)
                  </label>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    {COMMERCIAL_SPACES.map((space) => (
                      <button
                        key={space}
                        type="button"
                        onClick={() => toggleCommercialSpace(space)}
                        className={cn(
                          "px-4 py-2 rounded-lg border text-sm font-medium transition-colors text-left",
                          formData.commercialSpaces.includes(space)
                            ? "bg-primary text-white border-primary"
                            : "bg-background text-foreground border-border/50 hover:bg-muted"
                        )}
                      >
                        {space}
                      </button>
                    ))}
                  </div>
                  {errors.commercialSpaces && <p className="text-red-500 text-sm mt-1">{errors.commercialSpaces}</p>}
                </div>
              )}

              <div>
                <label className="block text-sm font-medium text-foreground mb-2">
                  Tom de Comunicação *
                </label>
                <select
                  value={formData.communicationTone}
                  onChange={(e) => setFormData({ ...formData, communicationTone: e.target.value as CommunicationTone })}
                  className={cn(
                    "w-full px-4 py-2 rounded-lg border bg-background text-foreground focus:outline-none focus:ring-2 focus:ring-primary/50",
                    errors.communicationTone ? "border-red-500" : "border-border/50"
                  )}
                >
                  <option value="">Selecione um tom...</option>
                  {COMMUNICATION_TONES.map((tone) => (
                    <option key={tone} value={tone}>
                      {tone}
                    </option>
                  ))}
                </select>
                {errors.communicationTone && <p className="text-red-500 text-sm mt-1">{errors.communicationTone}</p>}
              </div>

              <div>
                <label className="block text-sm font-medium text-foreground mb-2">
                  Modelo de Execução *
                </label>
                <select
                  value={formData.executionModel}
                  onChange={(e) => {
                    setFormData({
                      ...formData,
                      executionModel: e.target.value as ExecutionModel,
                      triggerEvent: e.target.value === "Event-driven (por evento)" ? formData.triggerEvent : "",
                    });
                  }}
                  className={cn(
                    "w-full px-4 py-2 rounded-lg border bg-background text-foreground focus:outline-none focus:ring-2 focus:ring-primary/50",
                    errors.executionModel ? "border-red-500" : "border-border/50"
                  )}
                >
                  <option value="">Selecione um modelo...</option>
                  {EXECUTION_MODELS.map((model) => (
                    <option key={model} value={model}>
                      {model}
                    </option>
                  ))}
                </select>
                {errors.executionModel && <p className="text-red-500 text-sm mt-1">{errors.executionModel}</p>}
              </div>

              {formData.executionModel === "Event-driven (por evento)" && (
                <div>
                  <label className="block text-sm font-medium text-foreground mb-2">
                    Evento de Disparo *
                  </label>
                  <select
                    value={formData.triggerEvent}
                    onChange={(e) => setFormData({ ...formData, triggerEvent: e.target.value as TriggerEvent })}
                    className={cn(
                      "w-full px-4 py-2 rounded-lg border bg-background text-foreground focus:outline-none focus:ring-2 focus:ring-primary/50",
                      errors.triggerEvent ? "border-red-500" : "border-border/50"
                    )}
                  >
                    <option value="">Selecione um evento...</option>
                    {TRIGGER_EVENTS.map((event) => (
                      <option key={event} value={event}>
                        {event}
                      </option>
                    ))}
                  </select>
                  {errors.triggerEvent && <p className="text-red-500 text-sm mt-1">{errors.triggerEvent}</p>}
                </div>
              )}

              <div>
                <label className="block text-sm font-medium text-foreground mb-2">
                  Regra de Recência em Dias *
                </label>
                <input
                  type="number"
                  min="0"
                  placeholder="Ex: 30"
                  value={formData.recencyRuleDays}
                  onChange={(e) => setFormData({ ...formData, recencyRuleDays: e.target.value })}
                  className={cn(
                    "w-full px-4 py-2 rounded-lg border bg-background text-foreground placeholder:text-foreground/40 focus:outline-none focus:ring-2 focus:ring-primary/50",
                    errors.recencyRuleDays ? "border-red-500" : "border-border/50"
                  )}
                />
                {errors.recencyRuleDays && <p className="text-red-500 text-sm mt-1">{errors.recencyRuleDays}</p>}
              </div>
            </div>
          )}

          {/* Step 5: Revisão */}
          {currentStep === 5 && (
            <div className="space-y-6">
              <div className="p-4 rounded-lg bg-primary/5 border border-primary/20">
                <h3 className="font-semibold text-foreground mb-4">Resumo da Campanha</h3>

                <div className="space-y-4">
                  <div>
                    <p className="text-sm text-foreground/60">Nome da Campanha</p>
                    <p className="font-medium text-foreground">{formData.name}</p>
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <p className="text-sm text-foreground/60">Categoria</p>
                      <p className="font-medium text-foreground">{formData.category}</p>
                    </div>
                    <div>
                      <p className="text-sm text-foreground/60">Prioridade</p>
                      <p className="font-medium text-foreground">{formData.priority}</p>
                    </div>
                  </div>

                  <div>
                    <p className="text-sm text-foreground/60">Área Solicitante</p>
                    <p className="font-medium text-foreground">{formData.requestingArea}</p>
                  </div>

                  <div>
                    <p className="text-sm text-foreground/60">Objetivo de Negócio</p>
                    <p className="font-medium text-foreground">{formData.businessObjective}</p>
                  </div>

                  <div>
                    <p className="text-sm text-foreground/60">Resultado Esperado</p>
                    <p className="font-medium text-foreground">{formData.expectedResult}</p>
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <p className="text-sm text-foreground/60">Data de Início</p>
                      <p className="font-medium text-foreground">
                        {formData.startDate ? new Date(formData.startDate).toLocaleDateString("pt-BR") : "-"}
                      </p>
                    </div>
                    <div>
                      <p className="text-sm text-foreground/60">Data de Fim</p>
                      <p className="font-medium text-foreground">
                        {formData.endDate ? new Date(formData.endDate).toLocaleDateString("pt-BR") : "-"}
                      </p>
                    </div>
                  </div>

                  <div>
                    <p className="text-sm text-foreground/60">Volume Estimado</p>
                    <p className="font-medium text-foreground">{formData.estimatedImpactVolume || "R$ 0,00"}</p>
                  </div>

                  <div>
                    <p className="text-sm text-foreground/60">Canais de Comunicação</p>
                    <p className="font-medium text-foreground">{formData.communicationChannels.join(", ") || "-"}</p>
                  </div>

                  {formData.commercialSpaces.length > 0 && (
                    <div>
                      <p className="text-sm text-foreground/60">Espaços Comerciais</p>
                      <p className="font-medium text-foreground">{formData.commercialSpaces.join(", ")}</p>
                    </div>
                  )}

                  <div>
                    <p className="text-sm text-foreground/60">Tom de Comunicação</p>
                    <p className="font-medium text-foreground">{formData.communicationTone}</p>
                  </div>

                  <div>
                    <p className="text-sm text-foreground/60">Modelo de Execução</p>
                    <p className="font-medium text-foreground">{formData.executionModel}</p>
                  </div>

                  {formData.triggerEvent && (
                    <div>
                      <p className="text-sm text-foreground/60">Evento de Disparo</p>
                      <p className="font-medium text-foreground">{formData.triggerEvent}</p>
                    </div>
                  )}

                  <div>
                    <p className="text-sm text-foreground/60">Regra de Recência</p>
                    <p className="font-medium text-foreground">{formData.recencyRuleDays} dias</p>
                  </div>
                </div>
              </div>

              <div className="p-4 rounded-lg bg-blue-50 border border-blue-200">
                <p className="text-sm text-blue-900">
                  ✓ Seu briefing de campanha está pronto para ser criado e enviado para aprovação!
                </p>
              </div>
            </div>
          )}
        </div>

        {/* Navigation Buttons */}
        <div className="flex items-center justify-between gap-4">
          <button
            onClick={handlePrevious}
            disabled={currentStep === 1}
            className={cn(
              "flex items-center gap-2 px-6 py-3 rounded-lg font-medium transition-all",
              currentStep === 1
                ? "text-foreground/30 cursor-not-allowed"
                : "text-primary hover:bg-primary/10"
            )}
          >
            <ArrowLeft size={20} />
            Anterior
          </button>

          <div className="text-sm text-foreground/60">
            Etapa {currentStep} de {steps.length}
          </div>

          {currentStep < steps.length ? (
            <button
              onClick={handleNext}
              className="flex items-center gap-2 px-6 py-3 rounded-lg bg-gradient-to-r from-primary to-secondary text-white font-medium hover:shadow-lg transition-all"
            >
              Próximo
              <ArrowRight size={20} />
            </button>
          ) : (
            <button
              onClick={handleCreate}
              disabled={createMutation.isPending || !canCreateCampaign}
              className="flex items-center gap-2 px-6 py-3 rounded-lg bg-gradient-to-r from-green-500 to-emerald-500 text-white font-medium hover:shadow-lg transition-all disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {createMutation.isPending ? (
                <>
                  <Loader2 size={20} className="animate-spin" />
                  Criando...
                </>
              ) : (
                <>
                  <Check size={20} />
                  Criar Campanha
                </>
              )}
            </button>
          )}
        </div>
      </div>

      {/* Enhancement Dialog */}
      <Dialog open={isEnhanceDialogOpen} onOpenChange={setIsEnhanceDialogOpen}>
        <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Sparkles size={20} className="text-primary" />
              Sugestão de Aprimoramento
            </DialogTitle>
            <DialogDescription>
              Analise a sugestão de aprimoramento para o campo selecionado
            </DialogDescription>
          </DialogHeader>

          {isEnhancing ? (
            <div className="flex items-center justify-center py-12">
              <div className="text-center">
                <Loader2 size={32} className="animate-spin text-primary mx-auto mb-4" />
                <p className="text-foreground/60">Analisando e aprimorando o texto...</p>
              </div>
            </div>
          ) : enhancementResult ? (
            <div className="space-y-6">
              {/* Original Text */}
              <div>
                <label className="block text-sm font-medium text-foreground mb-2">
                  Texto Original
                </label>
                <div className="p-4 rounded-lg border border-border/50 bg-muted/30">
                  <p className="text-foreground whitespace-pre-wrap">
                    {enhancingField ? formData[enhancingField] : ""}
                  </p>
                </div>
              </div>

              {/* Enhanced Text */}
              <div>
                <label className="block text-sm font-medium text-foreground mb-2">
                  Texto Sugerido
                </label>
                <div className="p-4 rounded-lg border border-primary/30 bg-primary/5">
                  <p className="text-foreground whitespace-pre-wrap">{enhancementResult.enhancedText}</p>
                </div>
              </div>

              {/* Explanation */}
              <div>
                <label className="block text-sm font-medium text-foreground mb-2">
                  Explicação das Mudanças
                </label>
                <div className="p-4 rounded-lg border border-border/50 bg-blue-50 dark:bg-blue-950/20">
                  <p className="text-foreground whitespace-pre-wrap text-sm">{enhancementResult.explanation}</p>
                </div>
              </div>

              {/* Actions */}
              <div className="flex items-center justify-end gap-3 pt-4 border-t">
                <button
                  type="button"
                  onClick={handleRejectEnhancement}
                  className="px-4 py-2 rounded-lg border border-border/50 bg-background text-foreground hover:bg-muted transition-colors"
                >
                  Rejeitar
                </button>
                <button
                  type="button"
                  onClick={handleApproveEnhancement}
                  className="px-4 py-2 rounded-lg bg-primary text-white hover:bg-primary/90 transition-colors"
                >
                  Aprovar Sugestão
                </button>
              </div>
            </div>
          ) : null}
        </DialogContent>
      </Dialog>
    </div>
  );
}

