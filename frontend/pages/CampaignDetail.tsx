import { useParams, useNavigate } from "react-router-dom";
import Header from "@/components/Header";
import { ArrowLeft, Plus, MessageSquare, Send, AlertCircle, Edit2, Save, X, Loader2, CheckCircle, FileText, Sparkles, Smartphone, MessageSquare as MessageSquareIcon, Upload, Image, FileCode, Trash2, AlertTriangle } from "lucide-react";
import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { cn } from "@/lib/utils";
import { campaignsAPI, authAPI, aiAPI, creativePiecesAPI } from "@/lib/api";
import { Campaign, Comment, CampaignStatus, AnalyzePieceResponse } from "@shared/api";
import { format, formatDistanceToNow } from "date-fns";

// Helper function to calculate content hash (same logic as backend)
async function calculateContentHash(channel: "SMS" | "Push", content: { text?: string; title?: string; body?: string }): Promise<string> {
  let contentStr = "";
  if (channel === "SMS") {
    contentStr = `SMS:${content.text || ""}`;
  } else if (channel === "Push") {
    contentStr = `Push:${content.title || ""}:${content.body || ""}`;
  }
  
  // Use Web Crypto API to calculate SHA-256 hash (same as backend)
  const encoder = new TextEncoder();
  const data = encoder.encode(contentStr);
  const hashBuffer = await crypto.subtle.digest('SHA-256', data);
  const hashArray = Array.from(new Uint8Array(hashBuffer));
  return hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
}
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";

export default function CampaignDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [isEditing, setIsEditing] = useState(false);
  const [editData, setEditData] = useState<Partial<Campaign>>({});
  const [newComment, setNewComment] = useState("");
  const [showAdjustmentDialog, setShowAdjustmentDialog] = useState(false);
  const [adjustmentComment, setAdjustmentComment] = useState("");
  const [smsText, setSmsText] = useState<string>("");
  const [pushTitle, setPushTitle] = useState<string>("");
  const [pushBody, setPushBody] = useState<string>("");
  const [isAnalyzingSms, setIsAnalyzingSms] = useState(false);
  const [isAnalyzingPush, setIsAnalyzingPush] = useState(false);
  const [smsAnalysis, setSmsAnalysis] = useState<AnalyzePieceResponse | null>(null);
  const [pushAnalysis, setPushAnalysis] = useState<AnalyzePieceResponse | null>(null);
  const [submittedSmsAnalysis, setSubmittedSmsAnalysis] = useState<AnalyzePieceResponse | null>(null);
  const [submittedPushAnalysis, setSubmittedPushAnalysis] = useState<AnalyzePieceResponse | null>(null);
  const [smsSubmitted, setSmsSubmitted] = useState(false);
  const [pushSubmitted, setPushSubmitted] = useState(false);
  const [appFiles, setAppFiles] = useState<Record<string, File | null>>({});
  const [emailFile, setEmailFile] = useState<File | null>(null);
  const [appUploading, setAppUploading] = useState<Record<string, boolean>>({});
  const [emailUploading, setEmailUploading] = useState(false);
  const [appSubmitted, setAppSubmitted] = useState<Record<string, boolean>>({});
  const [emailSubmitted, setEmailSubmitted] = useState(false);
  const [appFileUrls, setAppFileUrls] = useState<Record<string, string>>({});
  const [emailFileUrl, setEmailFileUrl] = useState<string | null>(null);
  const [statusError, setStatusError] = useState<string | null>(null);
  const [emailUploadError, setEmailUploadError] = useState<string | null>(null);
  const [appUploadErrors, setAppUploadErrors] = useState<Record<string, string>>({});
  const [activeChannelTab, setActiveChannelTab] = useState<string>("");

  
  const { data: currentUser } = useQuery({
    queryKey: ["currentUser"],
    queryFn: authAPI.getCurrentUser,
    throwOnError: false, 
  });

  const { data: campaign, isLoading, error } = useQuery({
    queryKey: ["campaign", id],
    queryFn: () => campaignsAPI.getById(id!),
    enabled: !!id,
  });

  
  useEffect(() => {
    if (campaign?.communicationChannels && campaign.communicationChannels.length > 0 && !activeChannelTab) {
      
      setActiveChannelTab(campaign.communicationChannels[0]);
    }
  }, [campaign?.communicationChannels, activeChannelTab]);

  
  useEffect(() => {
    if (campaign?.creativePieces) {
      const smsPiece = campaign.creativePieces.find(p => p.pieceType === "SMS");
      const pushPiece = campaign.creativePieces.find(p => p.pieceType === "Push");
      const appPiece = campaign.creativePieces.find(p => p.pieceType === "App");
      const emailPiece = campaign.creativePieces.find(p => p.pieceType === "E-mail");
      
      if (smsPiece && smsPiece.text) {
        setSmsText(smsPiece.text);
      }
      if (pushPiece) {
        if (pushPiece.title) setPushTitle(pushPiece.title);
        if (pushPiece.body) setPushBody(pushPiece.body);
      }
      if (appPiece && appPiece.fileUrls) {
        try {
          const fileUrls = JSON.parse(appPiece.fileUrls);
          
          setAppFileUrls(fileUrls);
          const submitted: Record<string, boolean> = {};
          Object.keys(fileUrls).forEach(space => {
            submitted[space] = true;
          });
          setAppSubmitted(submitted);
        } catch (e) {
          
        }
      }
      if (emailPiece && emailPiece.htmlFileUrl) {
        setEmailFileUrl(emailPiece.htmlFileUrl);
        setEmailSubmitted(true);
      }
    }
  }, [campaign?.creativePieces]);

  
  useEffect(() => {
    const loadAnalyses = async () => {
      if (!id || !campaign?.creativePieces) return;
      
      const smsPiece = campaign.creativePieces.find(p => p.pieceType === "SMS");
      const pushPiece = campaign.creativePieces.find(p => p.pieceType === "Push");
      
      
      if (smsPiece && smsPiece.text) {
        try {
          // Calculate hash of current content to find matching analysis
          const contentHash = await calculateContentHash("SMS", { text: smsPiece.text });
          const analysis = await aiAPI.getAnalysis(id, "SMS", contentHash);
          setSubmittedSmsAnalysis(analysis);
        } catch (error) {
          
          setSubmittedSmsAnalysis(null);
        }
      } else {
        setSubmittedSmsAnalysis(null);
      }
      
      
      if (pushPiece && (pushPiece.title || pushPiece.body)) {
        try {
          // Calculate hash of current content to find matching analysis
          const contentHash = await calculateContentHash("Push", { title: pushPiece.title, body: pushPiece.body });
          const analysis = await aiAPI.getAnalysis(id, "Push", contentHash);
          setSubmittedPushAnalysis(analysis);
        } catch (error) {
          
          setSubmittedPushAnalysis(null);
        }
      } else {
        setSubmittedPushAnalysis(null);
      }
    };
    
    loadAnalyses();
  }, [id, campaign?.creativePieces]);

  const updateMutation = useMutation({
    mutationFn: (data: Parameters<typeof campaignsAPI.update>[1]) =>
      campaignsAPI.update(id!, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["campaign", id] });
      queryClient.invalidateQueries({ queryKey: ["campaigns"] });
      setIsEditing(false);
    },
  });

  const commentMutation = useMutation({
    mutationFn: (text: string) =>
      campaignsAPI.addComment(id!, {
        author: currentUser?.full_name || "Você",
        role: currentUser?.role || "Usuário",
        text,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["campaign", id] });
      setNewComment("");
    },
  });

  const updateStatusMutation = useMutation({
    mutationFn: (newStatus: CampaignStatus) =>
      campaignsAPI.update(id!, { status: newStatus }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["campaign", id] });
      queryClient.invalidateQueries({ queryKey: ["campaigns"] });
      setStatusError(null);
    },
    onError: (error: Error) => {
      
      setStatusError(error.message || "Erro ao atualizar status da campanha");
      
      setTimeout(() => setStatusError(null), 5000);
    },
  });

  const analyzePieceMutation = useMutation({
    mutationFn: ({ channel, content }: { channel: "SMS" | "Push"; content: { text?: string; title?: string; body?: string } }) =>
      aiAPI.analyzePiece(id!, channel, content),
    onSuccess: (data, variables) => {
      if (variables.channel === "SMS") {
        setSmsAnalysis(data);
      } else {
        setPushAnalysis(data);
      }
    },
  });

  const submitCreativePieceMutation = useMutation({
    mutationFn: ({ pieceType, text, title, body }: { pieceType: "SMS" | "Push"; text?: string; title?: string; body?: string }) =>
      creativePiecesAPI.submitCreativePiece(id!, { pieceType, text, title, body }),
    onSuccess: async (data, variables) => {
      queryClient.invalidateQueries({ queryKey: ["campaign", id] });
      queryClient.invalidateQueries({ queryKey: ["campaigns"] });
      
      
      if (variables.pieceType === "SMS") {
        setSmsSubmitted(true);
        setTimeout(() => setSmsSubmitted(false), 3000);
        
        // Clear old analysis and try to find matching one for new content
        setSubmittedSmsAnalysis(null);
        try {
          const contentHash = await calculateContentHash("SMS", { text: variables.text || "" });
          const analysis = await aiAPI.getAnalysis(id!, "SMS", contentHash);
          setSubmittedSmsAnalysis(analysis);
        } catch (error) {
          
          console.log("No analysis found for submitted SMS piece");
        }
      } else {
        setPushSubmitted(true);
        setTimeout(() => setPushSubmitted(false), 3000);
        
        // Clear old analysis and try to find matching one for new content
        setSubmittedPushAnalysis(null);
        try {
          const contentHash = await calculateContentHash("Push", { title: variables.title, body: variables.body });
          const analysis = await aiAPI.getAnalysis(id!, "Push", contentHash);
          setSubmittedPushAnalysis(analysis);
        } catch (error) {
          
          console.log("No analysis found for submitted Push piece");
        }
      }
      
      
      setSmsText("");
      setPushTitle("");
      setPushBody("");
      
      setSmsAnalysis(null);
      setPushAnalysis(null);
    },
  });

  const handleAnalyzePiece = async (channel: "SMS" | "Push") => {
    if (channel === "SMS") {
      if (!smsText.trim()) {
        
        return;
      }
      setIsAnalyzingSms(true);
      try {
        await analyzePieceMutation.mutateAsync({ 
          channel: "SMS", 
          content: { text: smsText } 
        });
      } catch (error) {
        
      } finally {
        setIsAnalyzingSms(false);
      }
    } else {
      if (!pushTitle.trim() || !pushBody.trim()) {
        
        return;
      }
      setIsAnalyzingPush(true);
      try {
        await analyzePieceMutation.mutateAsync({ 
          channel: "Push", 
          content: { title: pushTitle, body: pushBody } 
        });
      } catch (error) {
        
      } finally {
        setIsAnalyzingPush(false);
      }
    }
  };

  
  useEffect(() => {
    setSmsAnalysis(null);
  }, [smsText]);

  useEffect(() => {
    setPushAnalysis(null);
  }, [pushTitle, pushBody]);

  const handleSubmitPiece = async (pieceType: "SMS" | "Push") => {
    try {
      if (pieceType === "SMS") {
        if (!smsText.trim()) return;
        await submitCreativePieceMutation.mutateAsync({ pieceType: "SMS", text: smsText });
      } else {
        if (!pushTitle.trim() || !pushBody.trim()) return;
        await submitCreativePieceMutation.mutateAsync({ pieceType: "Push", title: pushTitle, body: pushBody });
      }
    } catch (error) {
      
    }
  };

  
  
  useEffect(() => {
    if (smsSubmitted || pushSubmitted || Object.values(appSubmitted).some(v => v) || emailSubmitted) {
      const timer = setTimeout(() => {
        setSmsSubmitted(false);
        setPushSubmitted(false);
        setAppSubmitted({});
        setEmailSubmitted(false);
      }, 3000);
      return () => clearTimeout(timer);
    }
  }, [smsSubmitted, pushSubmitted, appSubmitted, emailSubmitted]);

  const handleAppFileUpload = async (commercialSpace: string, file: File | null) => {
    if (!file || !id) return;
    
    setAppUploading(prev => ({ ...prev, [commercialSpace]: true }));
    setAppUploadErrors(prev => {
      const newErrors = { ...prev };
      delete newErrors[commercialSpace];
      return newErrors;
    });
    try {
      const result = await creativePiecesAPI.uploadAppFile(id, commercialSpace, file);
      queryClient.invalidateQueries({ queryKey: ["campaign", id] });
      
      
      if (result.fileUrls) {
        try {
          const fileUrls = JSON.parse(result.fileUrls);
          setAppFileUrls(prev => ({ ...prev, ...fileUrls }));
        } catch (e) {
          
        }
      }
      
      setAppSubmitted(prev => ({ ...prev, [commercialSpace]: true }));
      setTimeout(() => {
        setAppSubmitted(prev => {
          const newState = { ...prev };
          delete newState[commercialSpace];
          return newState;
        });
      }, 3000);
      setAppFiles(prev => ({ ...prev, [commercialSpace]: null }));
    } catch (error: any) {
      
      const errorMessage = error?.message || "Erro ao fazer upload do arquivo PNG. Verifique se o arquivo é PNG válido.";
      setAppUploadErrors(prev => ({ ...prev, [commercialSpace]: errorMessage }));
      
      setTimeout(() => {
        setAppUploadErrors(prev => {
          const newErrors = { ...prev };
          delete newErrors[commercialSpace];
          return newErrors;
        });
      }, 10000);
    } finally {
      setAppUploading(prev => ({ ...prev, [commercialSpace]: false }));
    }
  };

  const handleEmailFileUpload = async (file: File | null) => {
    if (!file || !id) return;
    
    setEmailUploading(true);
    setEmailUploadError(null);
    try {
      const result = await creativePiecesAPI.uploadEmailFile(id, file);
      queryClient.invalidateQueries({ queryKey: ["campaign", id] });
      
      
      if (result.htmlFileUrl) {
        setEmailFileUrl(result.htmlFileUrl);
      }
      
      setEmailSubmitted(true);
      setTimeout(() => setEmailSubmitted(false), 3000);
      setEmailFile(null);
    } catch (error: any) {
      
      const errorMessage = error?.message || "Erro ao fazer upload do arquivo HTML. Verifique se o arquivo é HTML válido.";
      setEmailUploadError(errorMessage);
      
      setTimeout(() => setEmailUploadError(null), 10000);
    } finally {
      setEmailUploading(false);
    }
  };

  const handleDeleteAppFile = async (commercialSpace: string) => {
    if (!id) return;
    
    if (!confirm(`Tem certeza que deseja remover o arquivo do espaço comercial "${commercialSpace}"?`)) {
      return;
    }
    
    try {
      await creativePiecesAPI.deleteAppFile(id, commercialSpace);
      queryClient.invalidateQueries({ queryKey: ["campaign", id] });
      
      
      setAppFileUrls(prev => {
        const newUrls = { ...prev };
        delete newUrls[commercialSpace];
        return newUrls;
      });
      setAppSubmitted(prev => {
        const newState = { ...prev };
        delete newState[commercialSpace];
        return newState;
      });
    } catch (error) {
      
      console.error("Failed to delete app file:", error);
      alert("Erro ao remover arquivo. Tente novamente.");
    }
  };

  const handleDeleteEmailFile = async () => {
    if (!id) return;
    
    if (!window.confirm("Tem certeza que deseja remover o arquivo HTML?")) {
      return;
    }
    
    try {
      await creativePiecesAPI.deleteEmailFile(id);
      queryClient.invalidateQueries({ queryKey: ["campaign", id] });
      
      
      setEmailFileUrl(null);
      setEmailSubmitted(false);
      
      
      
      
    } catch (error: any) {
      
      console.error("Failed to delete email file:", error);
      alert(error.message || "Erro ao remover arquivo. Tente novamente.");
    }
  };

  if (!id) {
    navigate("/campaigns");
    return null;
  }

  if (isLoading) {
    return (
      <div className="min-h-screen bg-background">
        <Header />
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12 text-center">
          <Loader2 className="mx-auto size-8 text-primary animate-spin mb-4" />
          <p className="text-foreground/60">Carregando campanha...</p>
        </div>
      </div>
    );
  }

  if (error || !campaign) {
    return (
      <div className="min-h-screen bg-background">
        <Header />
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12 text-center">
          <AlertCircle className="mx-auto size-12 text-status-rejected mb-4" />
          <h3 className="text-lg font-semibold text-foreground mb-2">Campanha não encontrada</h3>
          <p className="text-foreground/60 mb-6">
            {error instanceof Error ? error.message : "A campanha que você está procurando não existe."}
          </p>
          <button
            onClick={() => navigate("/campaigns")}
            className="inline-flex items-center gap-2 px-6 py-2 rounded-lg bg-primary text-white font-semibold hover:shadow-lg transition-all"
          >
            <ArrowLeft size={20} />
            Voltar para Campanhas
          </button>
        </div>
      </div>
    );
  }

  const handleSave = () => {
    if (editData) {
      updateMutation.mutate(editData);
    }
  };

  const handleCancel = () => {
    setEditData({});
    setIsEditing(false);
  };

  const handleAddComment = () => {
    if (!newComment.trim()) return;
    commentMutation.mutate(newComment);
  };


  const formatTimestamp = (timestamp: string) => {
    try {
      return formatDistanceToNow(new Date(timestamp), { addSuffix: true });
    } catch {
      return timestamp;
    }
  };

  const getInitials = (name: string) => {
    return name
      .split(" ")
      .map((n) => n[0])
      .join("")
      .toUpperCase()
      .slice(0, 2);
  };


  const statusConfig: Record<string, { label: string; color: string; bg: string }> = {
    DRAFT: { label: "Rascunho", color: "text-slate-500", bg: "bg-slate-500/10" },
    CREATIVE_STAGE: {
      label: "Etapa Criativa",
      color: "text-blue-500",
      bg: "bg-blue-500/10",
    },
    CONTENT_REVIEW: {
      label: "Conteúdo em Revisão",
      color: "text-yellow-500",
      bg: "bg-yellow-500/10",
    },
    CONTENT_ADJUSTMENT: {
      label: "Ajuste de Conteúdo",
      color: "text-orange-500",
      bg: "bg-orange-500/10",
    },
    CAMPAIGN_BUILDING: {
      label: "Campanha em Construção",
      color: "text-purple-500",
      bg: "bg-purple-500/10",
    },
    CAMPAIGN_PUBLISHED: {
      label: "Campanha Publicada",
      color: "text-green-500",
      bg: "bg-green-500/10",
    },
  };

  
  const getAvailableActions = () => {
    if (!campaign || !currentUser) return [];

    const actions = [];
    const userRole = currentUser.role;

    
    if (userRole === "Analista de negócios") {
      if (campaign.status === "DRAFT" && campaign.createdBy === currentUser.id) {
        actions.push({
          label: "Enviar para Criação",
          status: "CREATIVE_STAGE" as CampaignStatus,
          variant: "primary",
        });
      }
      if (campaign.status === "CONTENT_REVIEW") {
        actions.push(
          {
            label: "Aprovar Conteúdo",
            status: "CAMPAIGN_BUILDING" as CampaignStatus,
            variant: "success",
          },
          {
            label: "Solicitar Ajustes",
            status: "CONTENT_ADJUSTMENT" as CampaignStatus,
            variant: "warning",
          }
        );
      }
    }

    
    if (userRole === "Analista de criação") {
      if (campaign.status === "CREATIVE_STAGE") {
        actions.push({
          label: "Enviar para Revisão",
          status: "CONTENT_REVIEW" as CampaignStatus,
          variant: "primary",
        });
      }
      if (campaign.status === "CONTENT_ADJUSTMENT") {
        actions.push({
          label: "Reenviar para Revisão",
          status: "CONTENT_REVIEW" as CampaignStatus,
          variant: "primary",
        });
      }
    }

    
    if (userRole === "Analista de campanhas") {
      if (campaign.status === "CAMPAIGN_BUILDING") {
        actions.push({
          label: "Publicar Campanha",
          status: "CAMPAIGN_PUBLISHED" as CampaignStatus,
          variant: "success",
        });
      }
    }

    return actions;
  };

  const handleStatusTransition = (newStatus: CampaignStatus) => {
    
    if (newStatus === "CONTENT_ADJUSTMENT") {
      setShowAdjustmentDialog(true);
      return;
    }
    
    updateStatusMutation.mutate(newStatus);
  };

  const handleConfirmAdjustment = () => {
    const commentText = adjustmentComment.trim();
    
    
    updateStatusMutation.mutate("CONTENT_ADJUSTMENT", {
      onSuccess: () => {
        
        if (commentText) {
          commentMutation.mutate(commentText, {
            onSuccess: () => {
              setShowAdjustmentDialog(false);
              setAdjustmentComment("");
            },
            onError: () => {
              
              setShowAdjustmentDialog(false);
              setAdjustmentComment("");
            },
          });
        } else {
          
          setShowAdjustmentDialog(false);
          setAdjustmentComment("");
        }
      },
    });
  };

  const currentStatusConfig = statusConfig[campaign.status] || statusConfig.DRAFT;

  return (
    <div className="min-h-screen bg-background">
      <Header />

      {/* Header */}
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
                        setEditData({ ...editData, name: e.target.value })
                      }
                      className="border border-border rounded-lg px-3 py-2 w-full bg-background text-foreground focus:outline-none focus:ring-2 focus:ring-primary"
                    />
                  ) : (
                    campaign?.name || ""
                  )}
                </h1>
              </div>
              <p className="text-foreground/60 mb-4">
                {campaign?.category} • {campaign?.requestingArea} • Criada por {campaign?.createdByName || "Usuário"} em{" "}
                {campaign?.createdDate ? format(new Date(campaign.createdDate), "dd/MM/yyyy") : ""}
              </p>
              <div
                className={cn(
                  "inline-block px-3 py-1 rounded-full text-sm font-medium",
                  currentStatusConfig.bg,
                  currentStatusConfig.color
                )}
              >
                {currentStatusConfig.label}
              </div>
            </div>

                <div className="flex gap-2">
                  {/* UPLOAD DE PEÇAS */}
                  {currentUser?.role === "Analista de criação" && 
                   (campaign.status === "CREATIVE_STAGE" || campaign.status === "CONTENT_ADJUSTMENT") && (
                    <button
                      onClick={() => {
                        const section = document.getElementById("creative-pieces-section");
                        if (section) {
                          section.scrollIntoView({ behavior: "smooth", block: "start" });
                        }
                      }}
                      className="flex items-center gap-2 px-4 py-2 rounded-lg bg-primary text-white font-medium hover:shadow-lg transition-all"
                    >
                      <Sparkles size={20} />
                      Upload de Peças
                    </button>
                  )}
                  {currentUser?.role === "Analista de negócios" && 
                   campaign.status === "DRAFT" && 
                   campaign.createdBy === currentUser.id && (
                    <>
                      {isEditing ? (
                        <>
                          <button
                            onClick={handleSave}
                            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-primary text-white font-medium hover:shadow-lg transition-all"
                          >
                            <Save size={20} />
                            Salvar
                          </button>
                          <button
                            onClick={handleCancel}
                            className="flex items-center gap-2 px-4 py-2 rounded-lg border border-border/50 text-foreground font-medium hover:bg-muted transition-colors"
                          >
                            <X size={20} />
                            Cancelar
                          </button>
                        </>
                      ) : (
                        <button
                          onClick={() => {
                            setEditData({ ...campaign });
                            setIsEditing(true);
                          }}
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

      {/* Main Content */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Briefing Content */}
          <div className="lg:col-span-2 space-y-4">

            {/* Campaign Details - Compact Layout */}
            <div className="space-y-4">
              {/* Informações Gerais - Combined Section */}
              <div className="p-4 rounded-lg border border-border/50 bg-card">
                <h3 className="text-base font-semibold text-foreground mb-3">Informações Gerais</h3>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                  <div>
                    <p className="text-xs text-foreground/60 mb-1">Nome</p>
                    <p className="text-sm font-medium text-foreground truncate">{campaign.name}</p>
                  </div>
                  <div>
                    <p className="text-xs text-foreground/60 mb-1">Categoria</p>
                    <p className="text-sm font-medium text-foreground">{campaign.category}</p>
                  </div>
                  <div>
                    <p className="text-xs text-foreground/60 mb-1">Área Solicitante</p>
                    <p className="text-sm font-medium text-foreground truncate">{campaign.requestingArea}</p>
                  </div>
                  <div>
                    <p className="text-xs text-foreground/60 mb-1">Prioridade</p>
                    <p className="text-sm font-medium text-foreground">{campaign.priority}</p>
                  </div>
                  <div>
                    <p className="text-xs text-foreground/60 mb-1">Data Início</p>
                    <p className="text-sm font-medium text-foreground">
                      {campaign.startDate ? format(new Date(campaign.startDate), "dd/MM/yyyy") : "-"}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-foreground/60 mb-1">Data Fim</p>
                    <p className="text-sm font-medium text-foreground">
                      {campaign.endDate ? format(new Date(campaign.endDate), "dd/MM/yyyy") : "-"}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-foreground/60 mb-1">Volume Estimado</p>
                    <p className="text-sm font-semibold text-primary">
                      {new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL", notation: "compact" }).format(
                        parseFloat(campaign.estimatedImpactVolume || "0")
                      )}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-foreground/60 mb-1">Status</p>
                    <span className={cn("px-2 py-0.5 rounded-full text-xs font-medium", currentStatusConfig.bg, currentStatusConfig.color)}>
                      {currentStatusConfig.label}
                    </span>
                  </div>
                </div>
              </div>

              {/* Objetivos e Público-Alvo - Combined */}
              <div className="p-4 rounded-lg border border-border/50 bg-card">
                <h3 className="text-base font-semibold text-foreground mb-3">Objetivos e Público-Alvo</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <p className="text-xs text-foreground/60 mb-1.5">Objetivo de Negócio</p>
                    <p className="text-sm text-foreground/80 whitespace-pre-wrap max-h-20 overflow-y-auto">
                      {campaign.businessObjective || <span className="text-foreground/60 italic">Não informado</span>}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-foreground/60 mb-1.5">Resultado Esperado / KPI</p>
                    <p className="text-sm text-foreground/80 whitespace-pre-wrap max-h-20 overflow-y-auto">
                      {campaign.expectedResult || <span className="text-foreground/60 italic">Não informado</span>}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-foreground/60 mb-1.5">Descrição do Público-Alvo</p>
                    <p className="text-sm text-foreground/80 whitespace-pre-wrap max-h-20 overflow-y-auto">
                      {campaign.targetAudienceDescription || <span className="text-foreground/60 italic">Não informado</span>}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-foreground/60 mb-1.5">Critérios de Exclusão</p>
                    <p className="text-sm text-foreground/80 whitespace-pre-wrap max-h-20 overflow-y-auto">
                      {campaign.exclusionCriteria || <span className="text-foreground/60 italic">Não informado</span>}
                    </p>
                  </div>
                </div>
              </div>

              {/* Comunicação e Execução - Combined */}
              <div className="p-4 rounded-lg border border-border/50 bg-card">
                <h3 className="text-base font-semibold text-foreground mb-3">Comunicação e Execução</h3>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div>
                    <p className="text-xs text-foreground/60 mb-2">Canais de Comunicação</p>
                    {campaign.communicationChannels && campaign.communicationChannels.length > 0 ? (
                      <div className="flex flex-wrap gap-1.5">
                        {campaign.communicationChannels.map((channel) => {
                          const hasPiece = campaign.creativePieces?.some(p => p.pieceType === channel);
                          return (
                            <span 
                              key={channel} 
                              className={cn(
                                "px-2 py-0.5 rounded-full text-xs font-medium flex items-center gap-1",
                                hasPiece 
                                  ? "bg-green-500/10 text-green-600 border border-green-500/30" 
                                  : "bg-primary/10 text-primary"
                              )}
                            >
                              {channel}
                              {hasPiece && <CheckCircle size={12} />}
                            </span>
                          );
                        })}
                      </div>
                    ) : (
                      <p className="text-xs text-foreground/60 italic">Não informado</p>
                    )}
                  </div>
                  <div>
                    <p className="text-xs text-foreground/60 mb-2">Espaços Comerciais</p>
                    {campaign.commercialSpaces && campaign.commercialSpaces.length > 0 ? (
                      <div className="flex flex-wrap gap-1.5">
                        {campaign.commercialSpaces.map((space) => (
                          <span key={space} className="px-2 py-0.5 rounded-full bg-secondary/10 text-secondary text-xs font-medium">
                            {space}
                          </span>
                        ))}
                      </div>
                    ) : (
                      <p className="text-xs text-foreground/60 italic">Não informado</p>
                    )}
                  </div>
                  <div>
                    <p className="text-xs text-foreground/60 mb-1">Tom de Comunicação</p>
                    <p className="text-sm font-medium text-foreground">{campaign.communicationTone}</p>
                  </div>
                  <div>
                    <p className="text-xs text-foreground/60 mb-1">Modelo de Execução</p>
                    <p className="text-sm font-medium text-foreground">{campaign.executionModel}</p>
                  </div>
                  <div>
                    <p className="text-xs text-foreground/60 mb-1">Evento de Disparo</p>
                    <p className="text-sm font-medium text-foreground">
                      {campaign.triggerEvent || "Não informado"}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-foreground/60 mb-1">Regra de Recência</p>
                    <p className="text-sm font-medium text-foreground">{campaign.recencyRuleDays} dias</p>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Sidebar - Comments & Actions */}
          <div className="lg:col-span-1 space-y-6">

            {/* Comments Section */}
            <div className="p-4 rounded-lg border border-border/50 bg-card">
              <h3 className="text-base font-semibold text-foreground mb-3 flex items-center gap-2">
                <MessageSquare size={18} />
                Comentários e Feedback
              </h3>

              <div className="space-y-4 mb-4 max-h-96 overflow-y-auto">
                {campaign.comments && campaign.comments.length > 0 ? (
                  campaign.comments.map((comment) => (
                    <div key={comment.id} className="pb-4 border-b border-border/50 last:border-0">
                      <div className="flex items-center gap-2 mb-2">
                        <div className="w-8 h-8 rounded-full bg-primary/20 text-primary flex items-center justify-center text-xs font-bold">
                          {getInitials(comment.author)}
                        </div>
                        <div>
                          <p className="text-sm font-medium text-foreground">
                            {comment.author}
                          </p>
                          <p className="text-xs text-foreground/50">
                            {comment.role} • {formatTimestamp(comment.timestamp)}
                          </p>
                        </div>
                      </div>
                      <p className="text-sm text-foreground/80 ml-10">
                        {comment.text}
                      </p>
                    </div>
                  ))
                ) : (
                  <p className="text-foreground/60 text-sm text-center py-4">Ainda não há comentários.</p>
                )}
              </div>

              {/* Add Comment */}
              <div className="flex gap-2">
                <input
                  type="text"
                  placeholder="Adicionar um comentário..."
                  value={newComment}
                  onChange={(e) => setNewComment(e.target.value)}
                  onKeyPress={(e) =>
                    e.key === "Enter" && handleAddComment()
                  }
                  className="flex-1 px-3 py-2 rounded-lg border border-border/50 bg-background text-foreground text-sm placeholder:text-foreground/40 focus:outline-none focus:ring-2 focus:ring-primary"
                />
                <button
                  onClick={handleAddComment}
                  className="p-2 rounded-lg bg-primary/10 text-primary hover:bg-primary/20 transition-colors"
                >
                  <Send size={18} />
                </button>
              </div>
            </div>

            {/* Quick Actions */}
            <div className="p-4 rounded-lg border border-border/50 bg-card">
              <h3 className="text-base font-semibold text-foreground mb-3">
                Ações
              </h3>
              {statusError && (
                <div className="mb-3 p-3 rounded-lg bg-red-500/10 border border-red-500/20">
                  <div className="flex items-start gap-2">
                    <AlertCircle size={16} className="text-red-600 mt-0.5 flex-shrink-0" />
                    <div className="flex-1">
                      <p className="text-sm font-medium text-red-600 mb-1">Não é possível enviar para revisão</p>
                      <p className="text-xs text-red-600/80">{statusError}</p>
                    </div>
                    <button
                      onClick={() => setStatusError(null)}
                      className="text-red-600 hover:text-red-700 flex-shrink-0"
                    >
                      <X size={14} />
                    </button>
                  </div>
                </div>
              )}
              <div className="space-y-2">
                {getAvailableActions().map((action, index) => {
                  const variantClasses = {
                    primary: "bg-blue-500/10 text-blue-700 hover:bg-blue-500/20",
                    success: "bg-green-500/10 text-green-700 hover:bg-green-500/20",
                    warning: "bg-orange-500/10 text-orange-700 hover:bg-orange-500/20",
                  };
                  
                  return (
                    <button
                      key={index}
                      onClick={() => handleStatusTransition(action.status)}
                      disabled={updateStatusMutation.isPending}
                      className={cn(
                        "w-full px-4 py-2 rounded-lg font-medium transition-colors text-sm disabled:opacity-50 disabled:cursor-not-allowed",
                        variantClasses[action.variant as keyof typeof variantClasses] || variantClasses.primary
                      )}
                    >
                      {updateStatusMutation.isPending ? "Processando..." : action.label}
                    </button>
                  );
                })}
              </div>
            </div>
          </div>
        </div>

        {/* Creative Pieces Section - For Creative Analysts, Business Analysts, and Campaign Analysts */}
        {((currentUser?.role === "Analista de negócios" && (campaign.status === "CONTENT_REVIEW" || campaign.status === "CAMPAIGN_BUILDING" || campaign.status === "CAMPAIGN_PUBLISHED")) ||
          (currentUser?.role === "Analista de criação" && (campaign.status === "CREATIVE_STAGE" || campaign.status === "CONTENT_ADJUSTMENT" || campaign.status === "CONTENT_REVIEW")) ||
          (currentUser?.role === "Analista de campanhas" && (campaign.status === "CAMPAIGN_BUILDING" || campaign.status === "CAMPAIGN_PUBLISHED"))) && (
          <div id="creative-pieces-section" className={cn(
            "mt-8",
            currentUser?.role === "Analista de criação" && "relative"
          )}>
            <div className={cn(
              "p-6 rounded-lg border",
              currentUser?.role === "Analista de criação"
                ? "bg-gradient-to-br from-purple-50/80 via-purple-50/60 to-purple-100/40 dark:from-purple-950/30 dark:via-purple-900/20 dark:to-purple-950/20 border-purple-200/50 dark:border-purple-800/30 shadow-lg shadow-purple-500/10"
                : "border-border/50 bg-card"
            )}>
              {currentUser?.role === "Analista de criação" && (
                <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-purple-400 via-purple-500 to-purple-400 rounded-t-lg" />
              )}
              <div className="flex items-center gap-3 mb-6">
                <div className={cn(
                  "p-2 rounded-lg",
                  currentUser?.role === "Analista de criação"
                    ? "bg-purple-500/20 dark:bg-purple-400/20"
                    : "bg-primary/10"
                )}>
                  {currentUser?.role === "Analista de criação" ? (
                    <Sparkles size={24} className="text-purple-600 dark:text-purple-400" />
                  ) : (
                    <FileText size={24} className="text-primary" />
                  )}
                </div>
                <div>
                  <h2 className={cn(
                    "text-xl font-semibold",
                    currentUser?.role === "Analista de criação"
                      ? "text-purple-900 dark:text-purple-100"
                      : "text-foreground"
                  )}>
                    {currentUser?.role === "Analista de negócios" 
                      ? "Revisão de Peças Criativas" 
                      : currentUser?.role === "Analista de campanhas"
                      ? "Peças Criativas"
                      : "Studio de Criação"}
                  </h2>
                  <p className={cn(
                    "text-sm",
                    currentUser?.role === "Analista de criação"
                      ? "text-purple-700/80 dark:text-purple-300/80"
                      : "text-foreground/60"
                  )}>
                    {currentUser?.role === "Analista de negócios"
                      ? "Revise todas as peças criativas antes de aprovar ou solicitar ajustes"
                      : currentUser?.role === "Analista de campanhas"
                      ? "Visualize as peças criativas aprovadas para construir a campanha"
                      : "Crie e gerencie as peças criativas para os canais de comunicação da campanha"}
                  </p>
                </div>
              </div>

              {/* Tabs by Channel */}
              {campaign.communicationChannels && campaign.communicationChannels.length > 0 && (
                <Tabs 
                  value={activeChannelTab || campaign.communicationChannels[0]} 
                  onValueChange={setActiveChannelTab}
                  className="w-full"
                >
                  <TabsList className="grid w-full mb-6" style={{ gridTemplateColumns: `repeat(${campaign.communicationChannels.length}, 1fr)` }}>
                    {campaign.communicationChannels.map((channel) => {
                      const channelIcons = {
                        "SMS": <Smartphone size={16} className="text-blue-600" />,
                        "Push": <MessageSquareIcon size={16} className="text-purple-600" />,
                        "App": <Image size={16} className="text-green-600" />,
                        "E-mail": <FileCode size={16} className="text-orange-600" />,
                      };
                      return (
                        <TabsTrigger 
                          key={channel}
                          value={channel}
                          className={cn(
                            "flex items-center justify-center gap-2",
                            currentUser?.role === "Analista de criação"
                              ? "data-[state=active]:bg-purple-500/20 data-[state=active]:text-purple-700 dark:data-[state=active]:text-purple-300"
                              : "data-[state=active]:bg-primary/10 data-[state=active]:text-primary"
                          )}
                        >
                          {channelIcons[channel as keyof typeof channelIcons]}
                          {channel}
                        </TabsTrigger>
                      );
                    })}
                  </TabsList>

                  {/* Channel Tabs Content */}
                  {campaign.communicationChannels.map((channel) => {
                    const canEdit = currentUser?.role === "Analista de criação" && 
                                    (campaign.status === "CREATIVE_STAGE" || campaign.status === "CONTENT_ADJUSTMENT");
                    const piece = campaign.creativePieces?.find(p => p.pieceType === channel);
                    
                    return (
                      <TabsContent key={channel} value={channel} className="mt-0 space-y-6">
                        {/* Creation Section - Only shown if user can edit */}
                        {canEdit && (
                          <div className="space-y-4">
                            <h3 className="text-lg font-semibold text-foreground flex items-center gap-2">
                              <Sparkles size={18} className="text-purple-600" />
                              Criação
                            </h3>
                            
                            {/* SMS Channel Creation */}
                            {channel === "SMS" && (
                    <div className="p-6 rounded-lg border border-border/50 bg-card">
                      <div className="flex items-center justify-between mb-4">
                        <div className="flex items-center gap-3">
                          <div className="p-2 rounded-lg bg-primary/10">
                            <Smartphone size={24} className="text-primary" />
                          </div>
                          <div>
                            <h4 className="text-lg font-semibold text-foreground">Texto SMS</h4>
                            <p className="text-sm text-foreground/60">Máximo recomendado: 160 caracteres</p>
                          </div>
                        </div>
                        <button
                          onClick={() => handleAnalyzePiece("SMS")}
                          disabled={isAnalyzingSms || !smsText.trim() || !!smsAnalysis}
                          className={cn(
                            "flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-all",
                            (isAnalyzingSms || !smsText.trim() || !!smsAnalysis)
                              ? "text-foreground/30 cursor-not-allowed bg-muted"
                              : "bg-primary text-white hover:bg-primary/90"
                          )}
                        >
                          {isAnalyzingSms ? (
                            <>
                              <Loader2 size={18} className="animate-spin" />
                              Validando...
                            </>
                          ) : smsAnalysis ? (
                            <>
                              <CheckCircle size={18} />
                              Análise Concluída
                            </>
                          ) : (
                            <>
                              <Sparkles size={18} />
                              Validar Peça
                            </>
                          )}
                        </button>
                      </div>
                      <div className="mt-4 space-y-3">
                        <Textarea
                          value={smsText}
                          onChange={(e) => setSmsText(e.target.value)}
                          placeholder="Digite o texto SMS..."
                          rows={4}
                          className="resize-none text-base font-medium"
                        />
                        
                        {/* Display Analysis Result */}
                        {smsAnalysis && (
                          <div className={cn(
                            "p-4 rounded-lg border-2",
                            smsAnalysis.is_valid === "valid" 
                              ? "bg-green-50 border-green-200 dark:bg-green-950/20 dark:border-green-800"
                              : smsAnalysis.is_valid === "invalid"
                              ? "bg-red-50 border-red-200 dark:bg-red-950/20 dark:border-red-800"
                              : "bg-yellow-50 border-yellow-200 dark:bg-yellow-950/20 dark:border-yellow-800"
                          )}>
                            <div className="flex items-start gap-3">
                              {smsAnalysis.is_valid === "valid" ? (
                                <CheckCircle size={20} className="text-green-600 dark:text-green-400 mt-0.5 flex-shrink-0" />
                              ) : smsAnalysis.is_valid === "invalid" ? (
                                <AlertCircle size={20} className="text-red-600 dark:text-red-400 mt-0.5 flex-shrink-0" />
                              ) : (
                                <AlertTriangle size={20} className="text-yellow-600 dark:text-yellow-400 mt-0.5 flex-shrink-0" />
                              )}
                              <div className="flex-1">
                                <p className={cn(
                                  "text-sm font-semibold mb-2",
                                  smsAnalysis.is_valid === "valid"
                                    ? "text-green-900 dark:text-green-100"
                                    : smsAnalysis.is_valid === "invalid"
                                    ? "text-red-900 dark:text-red-100"
                                    : "text-yellow-900 dark:text-yellow-100"
                                )}>
                                  {smsAnalysis.is_valid === "valid" 
                                    ? "Validação Aprovada" 
                                    : smsAnalysis.is_valid === "invalid"
                                    ? "Validação Reprovada"
                                    : "Validação com Ressalvas"}
                                </p>
                                <p className="text-sm text-foreground whitespace-pre-wrap leading-relaxed">
                                  {smsAnalysis.analysis_text}
                                </p>
                                <p className="text-xs text-foreground/60 mt-2">
                                  Análise realizada em {format(new Date(smsAnalysis.created_at), "dd/MM/yyyy 'às' HH:mm")}
                                </p>
                              </div>
                            </div>
                          </div>
                        )}
                        <div className="flex items-center justify-between">
                          <button
                            onClick={() => handleSubmitPiece("SMS")}
                            disabled={(!smsText.trim() && !smsSubmitted) || submitCreativePieceMutation.isPending}
                            className={cn(
                              "flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-all",
                              smsSubmitted
                                ? "bg-green-500 text-white cursor-default"
                                : (!smsText.trim() || submitCreativePieceMutation.isPending)
                                ? "text-foreground/30 cursor-not-allowed bg-muted"
                                : "bg-green-600 text-white hover:bg-green-700"
                            )}
                          >
                            {submitCreativePieceMutation.isPending ? (
                              <>
                                <Loader2 size={16} className="animate-spin" />
                                Enviando...
                              </>
                            ) : smsSubmitted ? (
                              <>
                                <CheckCircle size={16} />
                                Peça SMS Enviada!
                              </>
                            ) : (
                              <>
                                <CheckCircle size={16} />
                                Submeter Peça SMS
                              </>
                            )}
                          </button>
                          <span className={cn(
                            "text-xs font-medium px-2 py-1 rounded",
                            smsText.length > 160 ? "bg-red-500/10 text-red-600" : "bg-muted text-foreground/60"
                          )}>
                            {smsText.length} / 160 caracteres
                          </span>
                        </div>
                      </div>
                    </div>
                  )}

                            {/* Push Channel Creation */}
                            {channel === "Push" && (
                    <div className="p-6 rounded-lg border border-border/50 bg-card">
                      <div className="flex items-center justify-between mb-4">
                        <div className="flex items-center gap-3">
                          <div className="p-2 rounded-lg bg-primary/10">
                            <MessageSquareIcon size={24} className="text-primary" />
                          </div>
                          <div>
                            <h4 className="text-lg font-semibold text-foreground">Notificação Push</h4>
                            <p className="text-sm text-foreground/60">Título (até 50) e corpo (até 120 caracteres)</p>
                          </div>
                        </div>
                        <button
                          onClick={() => handleAnalyzePiece("Push")}
                          disabled={isAnalyzingPush || !pushTitle.trim() || !pushBody.trim() || !!pushAnalysis}
                          className={cn(
                            "flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-all",
                            (isAnalyzingPush || !pushTitle.trim() || !pushBody.trim() || !!pushAnalysis)
                              ? "text-foreground/30 cursor-not-allowed bg-muted"
                              : "bg-primary text-white hover:bg-primary/90"
                          )}
                        >
                          {isAnalyzingPush ? (
                            <>
                              <Loader2 size={18} className="animate-spin" />
                              Validando...
                            </>
                          ) : pushAnalysis ? (
                            <>
                              <CheckCircle size={18} />
                              Análise Concluída
                            </>
                          ) : (
                            <>
                              <Sparkles size={18} />
                              Validar Peça
                            </>
                          )}
                        </button>
                      </div>
                      <div className="mt-4 space-y-4">
                        <div className="space-y-2">
                          <div className="flex items-center justify-between">
                            <Label htmlFor="push-title" className="text-sm font-medium text-foreground">
                              Título
                            </Label>
                            <span className={cn(
                              "text-xs font-medium px-2 py-1 rounded",
                              pushTitle.length > 50 ? "bg-red-500/10 text-red-600" : "bg-muted text-foreground/60"
                            )}>
                              {pushTitle.length} / 50 caracteres
                            </span>
                          </div>
                          <Textarea
                            id="push-title"
                            value={pushTitle}
                            onChange={(e) => setPushTitle(e.target.value)}
                            placeholder="Digite o título da notificação push..."
                            rows={2}
                            className="resize-none text-base font-medium"
                          />
                        </div>
                        <div className="space-y-2">
                          <div className="flex items-center justify-between">
                            <Label htmlFor="push-body" className="text-sm font-medium text-foreground">
                              Corpo
                            </Label>
                            <span className={cn(
                              "text-xs font-medium px-2 py-1 rounded",
                              pushBody.length > 120 ? "bg-red-500/10 text-red-600" : "bg-muted text-foreground/60"
                            )}>
                              {pushBody.length} / 120 caracteres
                            </span>
                          </div>
                          <Textarea
                            id="push-body"
                            value={pushBody}
                            onChange={(e) => setPushBody(e.target.value)}
                            placeholder="Digite o corpo da notificação push..."
                            rows={3}
                            className="resize-none text-base font-medium"
                          />
                        </div>
                        
                        {/* Display Analysis Result */}
                        {pushAnalysis && (
                          <div className={cn(
                            "p-4 rounded-lg border-2",
                            pushAnalysis.is_valid === "valid" 
                              ? "bg-green-50 border-green-200 dark:bg-green-950/20 dark:border-green-800"
                              : pushAnalysis.is_valid === "invalid"
                              ? "bg-red-50 border-red-200 dark:bg-red-950/20 dark:border-red-800"
                              : "bg-yellow-50 border-yellow-200 dark:bg-yellow-950/20 dark:border-yellow-800"
                          )}>
                            <div className="flex items-start gap-3">
                              {pushAnalysis.is_valid === "valid" ? (
                                <CheckCircle size={20} className="text-green-600 dark:text-green-400 mt-0.5 flex-shrink-0" />
                              ) : pushAnalysis.is_valid === "invalid" ? (
                                <AlertCircle size={20} className="text-red-600 dark:text-red-400 mt-0.5 flex-shrink-0" />
                              ) : (
                                <AlertTriangle size={20} className="text-yellow-600 dark:text-yellow-400 mt-0.5 flex-shrink-0" />
                              )}
                              <div className="flex-1">
                                <p className={cn(
                                  "text-sm font-semibold mb-2",
                                  pushAnalysis.is_valid === "valid"
                                    ? "text-green-900 dark:text-green-100"
                                    : pushAnalysis.is_valid === "invalid"
                                    ? "text-red-900 dark:text-red-100"
                                    : "text-yellow-900 dark:text-yellow-100"
                                )}>
                                  {pushAnalysis.is_valid === "valid" 
                                    ? "Validação Aprovada" 
                                    : pushAnalysis.is_valid === "invalid"
                                    ? "Validação Reprovada"
                                    : "Validação com Ressalvas"}
                                </p>
                                <p className="text-sm text-foreground whitespace-pre-wrap leading-relaxed">
                                  {pushAnalysis.analysis_text}
                                </p>
                                <p className="text-xs text-foreground/60 mt-2">
                                  Análise realizada em {format(new Date(pushAnalysis.created_at), "dd/MM/yyyy 'às' HH:mm")}
                                </p>
                              </div>
                            </div>
                          </div>
                        )}
                        
                        <div className="flex justify-end pt-2">
                          <button
                            onClick={() => handleSubmitPiece("Push")}
                            disabled={((!pushTitle.trim() || !pushBody.trim()) && !pushSubmitted) || submitCreativePieceMutation.isPending}
                            className={cn(
                              "flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-all",
                              pushSubmitted
                                ? "bg-green-500 text-white cursor-default"
                                : (!pushTitle.trim() || !pushBody.trim() || submitCreativePieceMutation.isPending)
                                ? "text-foreground/30 cursor-not-allowed bg-muted"
                                : "bg-green-600 text-white hover:bg-green-700"
                            )}
                          >
                            {submitCreativePieceMutation.isPending ? (
                              <>
                                <Loader2 size={16} className="animate-spin" />
                                Enviando...
                              </>
                            ) : pushSubmitted ? (
                              <>
                                <CheckCircle size={16} />
                                Peça Push Enviada!
                              </>
                            ) : (
                              <>
                                <CheckCircle size={16} />
                                Submeter Peça Push
                              </>
                            )}
                          </button>
                        </div>
                      </div>
                    </div>
                  )}

                            {/* App Channel Creation */}
                            {channel === "App" && campaign.commercialSpaces && campaign.commercialSpaces.length > 0 && (
                    <div className="p-6 rounded-lg border border-border/50 bg-card">
                      <div className="flex items-center gap-3 mb-4">
                        <div className="p-2 rounded-lg bg-primary/10">
                          <Image size={24} className="text-primary" />
                        </div>
                        <div>
                          <h4 className="text-lg font-semibold text-foreground">Arquivos App</h4>
                          <p className="text-sm text-foreground/60">Envie 1 arquivo PNG por espaço comercial</p>
                        </div>
                      </div>
                      <div className="space-y-4">
                        {campaign.commercialSpaces.map((space) => {
                          const hasFile = !!appFileUrls[space];
                          const uploadError = appUploadErrors[space];
                          return (
                            <div key={space} className="space-y-2">
                              <div className="flex items-center justify-between">
                                <Label className="text-sm font-medium text-foreground">{space}</Label>
                                {hasFile && (
                                  <div className="flex items-center gap-2 px-2 py-1 rounded-lg bg-green-500/10">
                                    <CheckCircle size={14} className="text-green-600" />
                                    <span className="text-xs text-green-600 font-medium">Arquivo enviado</span>
                                  </div>
                                )}
                              </div>
                              <div className="flex items-center gap-3">
                                <input
                                  type="file"
                                  accept=".png"
                                  onChange={(e) => {
                                    const file = e.target.files?.[0] || null;
                                    setAppFiles(prev => ({ ...prev, [space]: file }));
                                    if (file) {
                                      handleAppFileUpload(space, file);
                                    }
                                  }}
                                  className="flex-1 text-sm text-foreground/80 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-medium file:bg-primary/10 file:text-primary hover:file:bg-primary/20"
                                  disabled={appUploading[space]}
                                />
                                {appUploading[space] && (
                                  <Loader2 size={18} className="animate-spin text-primary" />
                                )}
                                {appSubmitted[space] && !hasFile && !uploadError && (
                                  <CheckCircle size={18} className="text-green-600" />
                                )}
                              </div>
                              {uploadError && (
                                <div className="p-2 rounded-lg bg-red-500/10 border border-red-500/20">
                                  <div className="flex items-start gap-2">
                                    <AlertCircle size={14} className="text-red-600 mt-0.5 flex-shrink-0" />
                                    <div className="flex-1">
                                      <p className="text-xs font-medium text-red-600 mb-0.5">Erro ao fazer upload</p>
                                      <p className="text-xs text-red-600/80">{uploadError}</p>
                                    </div>
                                    <button
                                      onClick={() => {
                                        setAppUploadErrors(prev => {
                                          const newErrors = { ...prev };
                                          delete newErrors[space];
                                          return newErrors;
                                        });
                                      }}
                                      className="text-red-600 hover:text-red-700 flex-shrink-0"
                                    >
                                      <X size={12} />
                                    </button>
                                  </div>
                                </div>
                              )}
                              {hasFile && (
                                <div className="mt-2 p-2 rounded-lg bg-muted/30 border border-border/50">
                                  <div className="flex items-center gap-2">
                                    <Image size={14} className="text-foreground/60" />
                                    <span className="text-xs text-foreground/60">Arquivo PNG enviado</span>
                                    <div className="ml-auto flex items-center gap-2">
                                      {appFileUrls[space] && (
                                        <a
                                          href={appFileUrls[space]}
                                          target="_blank"
                                          rel="noopener noreferrer"
                                          className="text-xs text-primary hover:underline"
                                        >
                                          Ver arquivo
                                        </a>
                                      )}
                                      <button
                                        onClick={() => handleDeleteAppFile(space)}
                                        className="p-1 rounded hover:bg-red-500/10 text-red-600 hover:text-red-700 transition-colors"
                                        title="Remover arquivo"
                                      >
                                        <Trash2 size={14} />
                                      </button>
                                    </div>
                                  </div>
                                </div>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  )}

                            {/* E-mail Channel Creation */}
                            {channel === "E-mail" && (
                    <div className="p-6 rounded-lg border border-border/50 bg-card">
                      <div className="flex items-center gap-3 mb-4">
                        <div className="p-2 rounded-lg bg-primary/10">
                          <FileCode size={24} className="text-primary" />
                        </div>
                        <div>
                          <h4 className="text-lg font-semibold text-foreground">Arquivo E-mail</h4>
                          <p className="text-sm text-foreground/60">Envie 1 arquivo HTML</p>
                        </div>
                      </div>
                      <div className="space-y-3">
                        {emailFileUrl && (
                          <div className="p-3 rounded-lg bg-green-500/10 border border-green-500/20">
                            <div className="flex items-center justify-between mb-2">
                              <div className="flex items-center gap-2">
                                <CheckCircle size={16} className="text-green-600" />
                                <span className="text-sm text-green-600 font-medium">Arquivo HTML enviado</span>
                              </div>
                              <button
                                onClick={handleDeleteEmailFile}
                                className="p-1 rounded hover:bg-red-500/10 text-red-600 hover:text-red-700 transition-colors"
                                title="Remover arquivo"
                              >
                                <Trash2 size={14} />
                              </button>
                            </div>
                            <a
                              href={emailFileUrl}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-xs text-primary hover:underline flex items-center gap-1"
                            >
                              <FileCode size={12} />
                              Ver arquivo HTML
                            </a>
                          </div>
                        )}
                        <input
                          type="file"
                          accept=".html"
                          onChange={(e) => {
                            const file = e.target.files?.[0] || null;
                            setEmailFile(file);
                            if (file) {
                              handleEmailFileUpload(file);
                            }
                          }}
                          className="w-full text-sm text-foreground/80 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-medium file:bg-primary/10 file:text-primary hover:file:bg-primary/20"
                          disabled={emailUploading}
                        />
                        {emailUploadError && (
                          <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/20">
                            <div className="flex items-start gap-2">
                              <AlertCircle size={16} className="text-red-600 mt-0.5 flex-shrink-0" />
                              <div className="flex-1">
                                <p className="text-sm font-medium text-red-600 mb-1">Erro ao fazer upload do arquivo E-mail</p>
                                <p className="text-xs text-red-600/80">{emailUploadError}</p>
                              </div>
                              <button
                                onClick={() => setEmailUploadError(null)}
                                className="text-red-600 hover:text-red-700 flex-shrink-0"
                              >
                                <X size={14} />
                              </button>
                            </div>
                          </div>
                        )}
                        <div className="flex items-center gap-2">
                          {emailUploading && (
                            <>
                              <Loader2 size={16} className="animate-spin text-primary" />
                              <span className="text-sm text-foreground/60">Enviando...</span>
                            </>
                          )}
                          {emailSubmitted && !emailFileUrl && !emailUploadError && (
                            <>
                              <CheckCircle size={16} className="text-green-600" />
                              <span className="text-sm text-green-600 font-medium">Arquivo E-mail Enviado!</span>
                            </>
                          )}
                        </div>
                      </div>
                            </div>
                            )}
                          </div>
                        )}

                        {/* Visualization Section - Always visible */}
                        <div className="space-y-4">
                          <h3 className="text-lg font-semibold text-foreground flex items-center gap-2">
                            <FileText size={18} className="text-primary" />
                            Visualização
                          </h3>

                          {piece ? (
                            <>
                              {/* SMS Piece Visualization */}
                              {channel === "SMS" && piece.text && (
                            <div className="p-5 rounded-lg border-2 border-border/50 bg-background/50">
                              <div className="flex items-center justify-between mb-4">
                                <div className="flex items-center gap-2">
                                  <div className="p-1.5 rounded bg-blue-500/10">
                                    <Smartphone size={18} className="text-blue-600" />
                                  </div>
                                  <span className="text-sm font-semibold text-foreground uppercase">SMS</span>
                                </div>
                                <CheckCircle size={18} className="text-green-600" />
                              </div>
                              <div className="bg-muted/30 p-4 rounded-lg border border-border/30 mb-3">
                                <p className="text-base text-foreground whitespace-pre-wrap leading-relaxed">{piece.text}</p>
                              </div>
                              <div className="flex items-center justify-between text-xs text-foreground/60">
                                <span>{piece.text.length} caracteres</span>
                                <span>Criado em {format(new Date(piece.createdAt), "dd/MM/yyyy 'às' HH:mm")}</span>
                              </div>
                              
                              {/* Warning if piece was submitted without validation */}
                              {!submittedSmsAnalysis && (
                                <div className="mt-4 p-4 rounded-lg border-2 bg-yellow-50 border-yellow-200 dark:bg-yellow-950/20 dark:border-yellow-800">
                                  <div className="flex items-start gap-3">
                                    <AlertTriangle size={20} className="text-yellow-600 dark:text-yellow-400 mt-0.5 flex-shrink-0" />
                                    <div className="flex-1">
                                      <p className="text-sm font-semibold mb-1 text-yellow-900 dark:text-yellow-100">
                                        Peça não validada
                                      </p>
                                      <p className="text-sm text-yellow-800 dark:text-yellow-200">
                                        Esta peça criativa foi submetida sem validação automática. Recomendamos validar a peça antes de prosseguir com a campanha.
                                      </p>
                                    </div>
                                  </div>
                                </div>
                              )}
                              
                              {/* Display Analysis for Submitted SMS Piece */}
                              {submittedSmsAnalysis && (
                                <div className={cn(
                                  "mt-4 p-4 rounded-lg border-2",
                                  submittedSmsAnalysis.is_valid === "valid" 
                                    ? "bg-green-50 border-green-200 dark:bg-green-950/20 dark:border-green-800"
                                    : submittedSmsAnalysis.is_valid === "invalid"
                                    ? "bg-red-50 border-red-200 dark:bg-red-950/20 dark:border-red-800"
                                    : "bg-yellow-50 border-yellow-200 dark:bg-yellow-950/20 dark:border-yellow-800"
                                )}>
                                  <div className="flex items-start gap-3">
                                    {submittedSmsAnalysis.is_valid === "valid" ? (
                                      <CheckCircle size={20} className="text-green-600 dark:text-green-400 mt-0.5 flex-shrink-0" />
                                    ) : submittedSmsAnalysis.is_valid === "invalid" ? (
                                      <AlertCircle size={20} className="text-red-600 dark:text-red-400 mt-0.5 flex-shrink-0" />
                                    ) : (
                                      <AlertTriangle size={20} className="text-yellow-600 dark:text-yellow-400 mt-0.5 flex-shrink-0" />
                                    )}
                                    <div className="flex-1">
                                      <p className={cn(
                                        "text-sm font-semibold mb-2",
                                        submittedSmsAnalysis.is_valid === "valid"
                                          ? "text-green-900 dark:text-green-100"
                                          : submittedSmsAnalysis.is_valid === "invalid"
                                          ? "text-red-900 dark:text-red-100"
                                          : "text-yellow-900 dark:text-yellow-100"
                                      )}>
                                        {submittedSmsAnalysis.is_valid === "valid" 
                                          ? "Validação Aprovada" 
                                          : submittedSmsAnalysis.is_valid === "invalid"
                                          ? "Validação Reprovada"
                                          : "Validação com Ressalvas"}
                                      </p>
                                      <p className="text-sm text-foreground whitespace-pre-wrap leading-relaxed">
                                        {submittedSmsAnalysis.analysis_text}
                                      </p>
                                      <p className="text-xs text-foreground/60 mt-2">
                                        Análise realizada em {format(new Date(submittedSmsAnalysis.created_at), "dd/MM/yyyy 'às' HH:mm")}
                                      </p>
                                    </div>
                                  </div>
                                </div>
                              )}
                            </div>
                          )}

                              {/* Push Piece Visualization */}
                              {channel === "Push" && (piece.title || piece.body) && (
                            <div className="p-5 rounded-lg border-2 border-border/50 bg-background/50">
                              <div className="flex items-center justify-between mb-4">
                                <div className="flex items-center gap-2">
                                  <div className="p-1.5 rounded bg-purple-500/10">
                                    <MessageSquareIcon size={18} className="text-purple-600" />
                                  </div>
                                  <span className="text-sm font-semibold text-foreground uppercase">Push Notification</span>
                                </div>
                                <CheckCircle size={18} className="text-green-600" />
                              </div>
                              <div className="space-y-3 mb-3">
                                {piece.title && (
                                  <div className="bg-muted/30 p-4 rounded-lg border border-border/30">
                                    <p className="text-xs font-medium text-foreground/60 mb-1.5">TÍTULO ({piece.title.length}/50)</p>
                                    <p className="text-base font-semibold text-foreground">{piece.title}</p>
                                  </div>
                                )}
                                {piece.body && (
                                  <div className="bg-muted/30 p-4 rounded-lg border border-border/30">
                                    <p className="text-xs font-medium text-foreground/60 mb-1.5">CORPO ({piece.body.length}/120)</p>
                                    <p className="text-sm text-foreground whitespace-pre-wrap leading-relaxed">{piece.body}</p>
                                  </div>
                                )}
                              </div>
                              <div className="text-xs text-foreground/60 text-right">
                                Criado em {format(new Date(piece.createdAt), "dd/MM/yyyy 'às' HH:mm")}
                              </div>
                              
                              {/* Warning if piece was submitted without validation */}
                              {!submittedPushAnalysis && (
                                <div className="mt-4 p-4 rounded-lg border-2 bg-yellow-50 border-yellow-200 dark:bg-yellow-950/20 dark:border-yellow-800">
                                  <div className="flex items-start gap-3">
                                    <AlertTriangle size={20} className="text-yellow-600 dark:text-yellow-400 mt-0.5 flex-shrink-0" />
                                    <div className="flex-1">
                                      <p className="text-sm font-semibold mb-1 text-yellow-900 dark:text-yellow-100">
                                        Peça não validada
                                      </p>
                                      <p className="text-sm text-yellow-800 dark:text-yellow-200">
                                        Esta peça criativa foi submetida sem validação automática. Recomendamos validar a peça antes de prosseguir com a campanha.
                                      </p>
                                    </div>
                                  </div>
                                </div>
                              )}
                              
                              {/* Display Analysis for Submitted Push Piece */}
                              {submittedPushAnalysis && (
                                <div className={cn(
                                  "mt-4 p-4 rounded-lg border-2",
                                  submittedPushAnalysis.is_valid === "valid" 
                                    ? "bg-green-50 border-green-200 dark:bg-green-950/20 dark:border-green-800"
                                    : submittedPushAnalysis.is_valid === "invalid"
                                    ? "bg-red-50 border-red-200 dark:bg-red-950/20 dark:border-red-800"
                                    : "bg-yellow-50 border-yellow-200 dark:bg-yellow-950/20 dark:border-yellow-800"
                                )}>
                                  <div className="flex items-start gap-3">
                                    {submittedPushAnalysis.is_valid === "valid" ? (
                                      <CheckCircle size={20} className="text-green-600 dark:text-green-400 mt-0.5 flex-shrink-0" />
                                    ) : submittedPushAnalysis.is_valid === "invalid" ? (
                                      <AlertCircle size={20} className="text-red-600 dark:text-red-400 mt-0.5 flex-shrink-0" />
                                    ) : (
                                      <AlertTriangle size={20} className="text-yellow-600 dark:text-yellow-400 mt-0.5 flex-shrink-0" />
                                    )}
                                    <div className="flex-1">
                                      <p className={cn(
                                        "text-sm font-semibold mb-2",
                                        submittedPushAnalysis.is_valid === "valid"
                                          ? "text-green-900 dark:text-green-100"
                                          : submittedPushAnalysis.is_valid === "invalid"
                                          ? "text-red-900 dark:text-red-100"
                                          : "text-yellow-900 dark:text-yellow-100"
                                      )}>
                                        {submittedPushAnalysis.is_valid === "valid" 
                                          ? "Validação Aprovada" 
                                          : submittedPushAnalysis.is_valid === "invalid"
                                          ? "Validação Reprovada"
                                          : "Validação com Ressalvas"}
                                      </p>
                                      <p className="text-sm text-foreground whitespace-pre-wrap leading-relaxed">
                                        {submittedPushAnalysis.analysis_text}
                                      </p>
                                      <p className="text-xs text-foreground/60 mt-2">
                                        Análise realizada em {format(new Date(submittedPushAnalysis.created_at), "dd/MM/yyyy 'às' HH:mm")}
                                      </p>
                                    </div>
                                  </div>
                                </div>
                              )}
                            </div>
                          )}

                              {/* App Piece Visualization */}
                              {channel === "App" && piece.fileUrls && (() => {
                            try {
                              const fileUrls = JSON.parse(piece.fileUrls);
                              const spaces = Object.keys(fileUrls);
                              return (
                                <div className="p-5 rounded-lg border-2 border-border/50 bg-background/50">
                                  <div className="flex items-center justify-between mb-4">
                                    <div className="flex items-center gap-2">
                                      <div className="p-1.5 rounded bg-green-500/10">
                                        <Image size={18} className="text-green-600" />
                                      </div>
                                      <span className="text-sm font-semibold text-foreground uppercase">App - Imagens</span>
                                    </div>
                                    <CheckCircle size={18} className="text-green-600" />
                                  </div>
                                  <div className="space-y-4 mb-3">
                                    {spaces.map((space) => (
                                      <div key={space} className="space-y-2">
                                        <p className="text-xs font-medium text-foreground/60">{space}</p>
                                        <div className="relative rounded-lg border-2 border-border/30 overflow-hidden bg-muted/20">
                                          <img
                                            src={fileUrls[space]}
                                            alt={`Imagem para ${space}`}
                                            className="w-full h-auto max-h-96 object-contain"
                                            onError={(e) => {
                                              (e.target as HTMLImageElement).src = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='400' height='200'%3E%3Crect fill='%23ddd' width='400' height='200'/%3E%3Ctext fill='%23999' font-family='sans-serif' font-size='14' x='50%25' y='50%25' text-anchor='middle' dy='.3em'%3EImagem não disponível%3C/text%3E%3C/svg%3E";
                                            }}
                                          />
                                        </div>
                                        <a
                                          href={fileUrls[space]}
                                          target="_blank"
                                          rel="noopener noreferrer"
                                          className="text-xs text-primary hover:underline flex items-center gap-1"
                                        >
                                          <Image size={12} />
                                          Abrir imagem em nova aba
                                        </a>
                                      </div>
                                    ))}
                                  </div>
                                  <div className="text-xs text-foreground/60 text-right">
                                    Criado em {format(new Date(piece.createdAt), "dd/MM/yyyy 'às' HH:mm")}
                                  </div>
                                </div>
                              );
                            } catch (e) {
                              return null;
                            }
                          })()}

                              {/* E-mail Piece Visualization */}
                              {channel === "E-mail" && piece.htmlFileUrl && (
                            <div className="p-5 rounded-lg border-2 border-border/50 bg-background/50">
                              <div className="flex items-center justify-between mb-4">
                                <div className="flex items-center gap-2">
                                  <div className="p-1.5 rounded bg-orange-500/10">
                                    <FileCode size={18} className="text-orange-600" />
                                  </div>
                                  <span className="text-sm font-semibold text-foreground uppercase">E-mail - HTML</span>
                                </div>
                                <CheckCircle size={18} className="text-green-600" />
                              </div>
                              <div className="space-y-3 mb-3">
                                <div className="bg-muted/30 p-4 rounded-lg border border-border/30">
                                  <p className="text-xs font-medium text-foreground/60 mb-2">Preview do HTML</p>
                                  <iframe
                                    src={piece.htmlFileUrl}
                                    className="w-full h-[600px] border border-border/30 rounded bg-white"
                                    title="E-mail HTML Preview"
                                    sandbox="allow-same-origin"
                                  />
                                </div>
                                <a
                                  href={piece.htmlFileUrl}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="text-sm text-primary hover:underline flex items-center gap-2"
                                >
                                  <FileCode size={14} />
                                  Abrir arquivo HTML em nova aba
                                </a>
                              </div>
                              <div className="text-xs text-foreground/60 text-right">
                                Criado em {format(new Date(piece.createdAt), "dd/MM/yyyy 'às' HH:mm")}
                              </div>
                              </div>
                              )}
                            </>
                          ) : (
                            <div className="p-12 rounded-lg border border-border/50 bg-muted/30 text-center">
                              <FileText size={48} className="mx-auto text-foreground/40 mb-4" />
                              <h4 className="text-lg font-semibold text-foreground mb-2">Nenhuma peça criativa ainda</h4>
                              <p className="text-sm text-foreground/60">
                                {currentUser?.role === "Analista de criação"
                                  ? `Crie a peça criativa para o canal ${channel} acima para visualizá-la aqui`
                                  : currentUser?.role === "Analista de campanhas"
                                  ? "Aguardando aprovação da peça criativa"
                                  : "Aguardando criação da peça criativa"}
                              </p>
                            </div>
                          )}
                        </div>
                      </TabsContent>
                    );
                  })}
                </Tabs>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Adjustment Request Dialog */}
      <Dialog open={showAdjustmentDialog} onOpenChange={setShowAdjustmentDialog}>
        <DialogContent className="sm:max-w-[500px]">
          <DialogHeader>
            <DialogTitle>Solicitar Ajustes</DialogTitle>
            <DialogDescription>
              Especifique os ajustes necessários nas peças criadas. Este comentário será enviado junto com a solicitação.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="adjustment-comment">
                Comentários sobre os ajustes necessários
              </Label>
              <Textarea
                id="adjustment-comment"
                placeholder="Descreva detalhadamente o que precisa ser ajustado nas peças criadas..."
                value={adjustmentComment}
                onChange={(e) => setAdjustmentComment(e.target.value)}
                rows={6}
                className="resize-none"
              />
              <p className="text-xs text-foreground/60">
                Este comentário será visível para o time de criação
              </p>
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                setShowAdjustmentDialog(false);
                setAdjustmentComment("");
              }}
              disabled={updateStatusMutation.isPending}
            >
              Cancelar
            </Button>
            <Button
              onClick={handleConfirmAdjustment}
              disabled={updateStatusMutation.isPending}
              className="bg-orange-500 hover:bg-orange-600 text-white"
            >
              {updateStatusMutation.isPending ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Enviando...
                </>
              ) : (
                "Solicitar Ajustes"
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
