import { useParams, useNavigate } from "react-router-dom";
import Header from "@/components/Header";
import { ValidationLoadingOverlay } from "@/components/ValidationLoadingOverlay";
import { PieceReviewTimeline } from "@/components/PieceReviewTimeline";
import { CampaignStatusTimeline } from "@/components/CampaignStatusTimeline";
import { NextActionBanner } from "@/components/NextActionBanner";
import { ArrowLeft, Plus, MessageSquare, Send, AlertCircle, Edit2, Save, X, Loader2, CheckCircle, FileText, Sparkles, Smartphone, MessageSquare as MessageSquareIcon, Upload, Image, FileCode, Trash2, AlertTriangle, ChevronUp, ChevronDown, User, History, Download } from "lucide-react";
import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { cn } from "@/lib/utils";
import { campaignsAPI, authAPI, aiAPI, creativePiecesAPI, type AnalyzePieceInput } from "@/lib/api";
import { Campaign, Comment, CampaignStatus, AnalyzePieceResponse, PieceReviewEvent, CampaignStatusEvent } from "@shared/api";
import { format, formatDistanceToNow } from "date-fns";

// Content hash calculation removed — backend handles cache lookup internally.
// For SMS/PUSH: backend returns the latest cached result for (campaign_id, channel).
// For EMAIL/APP: backend uses piece_id / commercial_space.

// Helper function to download a creative piece via backend proxy
async function downloadCreativePiece(
  campaignId: string,
  channel: "EMAIL" | "APP",
  filename: string,
  commercialSpace?: string
): Promise<void> {
  try {
    const params = new URLSearchParams({
      channel,
      filename,
    });
    if (commercialSpace) {
      params.set("commercial_space", commercialSpace);
    }
    
    const response = await fetch(`/api/campaigns/${campaignId}/download-piece?${params.toString()}`, {
      credentials: "include",
    });
    
    if (!response.ok) {
      throw new Error(`Download failed: ${response.status}`);
    }
    
    const blob = await response.blob();
    const blobUrl = window.URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = blobUrl;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(blobUrl);
  } catch (error) {
    console.error("Download failed:", error);
    alert("Erro ao baixar arquivo. Tente novamente.");
  }
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
import { Collapsible, CollapsibleContent } from "@/components/ui/collapsible";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

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
  const [emailPieceId, setEmailPieceId] = useState<string | null>(null);
  const [appPieceId, setAppPieceId] = useState<string | null>(null);
  const [emailAnalysis, setEmailAnalysis] = useState<AnalyzePieceResponse | null>(null);
  const [appAnalysis, setAppAnalysis] = useState<Record<string, AnalyzePieceResponse | null>>({});
  const [isAnalyzingEmail, setIsAnalyzingEmail] = useState(false);
  const [isAnalyzingAppBySpace, setIsAnalyzingAppBySpace] = useState<Record<string, boolean>>({});
  const isAnalyzingAnyApp = Object.values(isAnalyzingAppBySpace).some(Boolean);
  const [mmValidatingPiece, setMmValidatingPiece] = useState<string | null>(null); // key: "channel:pieceId:space"
  const [mmAnalysisResults, setMmAnalysisResults] = useState<Record<string, AnalyzePieceResponse>>({}); // key → resultado
  const [statusError, setStatusError] = useState<string | null>(null);
  const [emailUploadError, setEmailUploadError] = useState<string | null>(null);
  const [skipEmailAnalysisFetch, setSkipEmailAnalysisFetch] = useState(false);
  const [appUploadErrors, setAppUploadErrors] = useState<Record<string, string>>({});
  const [activeChannelTab, setActiveChannelTab] = useState<string>("");
  const [studioOpen, setStudioOpen] = useState(false);
  const [rejectionDialogOpen, setRejectionDialogOpen] = useState(false);
  const [rejectionDialogPayload, setRejectionDialogPayload] = useState<{
    pr: { pieceId: string; commercialSpace: string };
    uiChannel: string;
    action: "reject" | "manually_reject";
    spaceLabel?: string;
  } | null>(null);
  const [rejectionReasonInput, setRejectionReasonInput] = useState("");

  
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

  // Query for piece review history (timeline)
  const { data: reviewHistory = [] } = useQuery({
    queryKey: ["pieceReviewHistory", id],
    queryFn: () => campaignsAPI.getPieceReviewHistory(id!),
    enabled: !!id && (campaign?.status === "CONTENT_REVIEW" || campaign?.status === "CONTENT_ADJUSTMENT" || campaign?.status === "CAMPAIGN_BUILDING" || campaign?.status === "CAMPAIGN_PUBLISHED"),
  });

  // Query for status history (horizontal timeline)
  const { data: statusHistoryData } = useQuery({
    queryKey: ["statusHistory", id],
    queryFn: () => campaignsAPI.getStatusHistory(id!),
    enabled: !!id,
  });

  const [showHistoryTimeline, setShowHistoryTimeline] = useState(false);

  
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
          setAppPieceId(appPiece.id);
          setAppFileUrls(fileUrls);
          const submitted: Record<string, boolean> = {};
          Object.keys(fileUrls).forEach(space => {
            submitted[space] = true;
          });
          setAppSubmitted(submitted);
        } catch (e) {
          /* ignore */
        }
      } else {
        setAppPieceId(null);
        setAppFileUrls({});
        setAppSubmitted({});
        setAppAnalysis({});
      }
      if (emailPiece && emailPiece.htmlFileUrl) {
        setEmailFileUrl(emailPiece.htmlFileUrl);
        setEmailPieceId(emailPiece.id);
        setEmailSubmitted(true);
      } else {
        setEmailPieceId(null);
        setEmailFileUrl(null);
        setEmailSubmitted(false);
        setEmailAnalysis(null);
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
          const analysis = await aiAPI.getAnalysis(id, "SMS");
          setSubmittedSmsAnalysis(analysis);
        } catch {
          setSubmittedSmsAnalysis(null);
        }
      } else {
        setSubmittedSmsAnalysis(null);
      }

      if (pushPiece && (pushPiece.title || pushPiece.body)) {
        try {
          const analysis = await aiAPI.getAnalysis(id, "Push");
          setSubmittedPushAnalysis(analysis);
        } catch {
          setSubmittedPushAnalysis(null);
        }
      } else {
        setSubmittedPushAnalysis(null);
      }

      const emailPiece = campaign.creativePieces.find(p => p.pieceType === "E-mail");
      if (emailPiece?.id) {
        // Skip fetch if we just uploaded a new file (to avoid restoring old cached analysis)
        if (skipEmailAnalysisFetch) {
          setSkipEmailAnalysisFetch(false);
          // Keep emailAnalysis as null (already set in handleEmailFileUpload)
        } else {
          try {
            const analysis = await aiAPI.getAnalysis(id, "E-mail", { pieceId: emailPiece.id });
            setEmailAnalysis(analysis);
          } catch {
            setEmailAnalysis(null);
          }
        }
      } else {
        setEmailAnalysis(null);
      }

      const appPiece = campaign.creativePieces.find(p => p.pieceType === "App");
      if (appPiece?.id && appPiece?.fileUrls) {
        try {
          const fileUrls = JSON.parse(appPiece.fileUrls) as Record<string, string>;
          const next: Record<string, AnalyzePieceResponse | null> = {};
          await Promise.all(
            Object.keys(fileUrls).map(async (space) => {
              try {
                const a = await aiAPI.getAnalysis(id, "App", { pieceId: appPiece.id, commercialSpace: space });
                next[space] = a;
              } catch {
                next[space] = null;
              }
            })
          );
          setAppAnalysis(next);
        } catch {
          setAppAnalysis({});
        }
      } else {
        setAppAnalysis({});
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

  const submitForReviewMutation = useMutation({
    mutationFn: (pieceReviews: { channel: string; pieceId: string; commercialSpace?: string; iaVerdict: string | null }[]) =>
      campaignsAPI.submitForReview(id!, pieceReviews),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["campaign", id] });
      queryClient.invalidateQueries({ queryKey: ["campaigns"] });
      setStatusError(null);
    },
    onError: (error: Error) => {
      setStatusError(error.message || "Erro ao submeter para revisão");
      setTimeout(() => setStatusError(null), 5000);
    },
  });

  const reviewPieceMutation = useMutation({
    mutationFn: (params: { channel: string; pieceId: string; commercialSpace?: string; action: "approve" | "reject" | "manually_reject"; rejectionReason?: string }) =>
      campaignsAPI.reviewPiece(id!, params),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["campaign", id] });
      queryClient.invalidateQueries({ queryKey: ["campaigns"] });
    },
  });

  type AnalyzeTarget = "sms" | "push" | "email" | "app";
  const analyzePieceMutation = useMutation({
    mutationFn: ({ input }: { input: AnalyzePieceInput; target: AnalyzeTarget; space?: string }) =>
      aiAPI.analyzePiece(id!, input),
    onSuccess: (data, { target, space }) => {
      if (target === "sms") setSmsAnalysis(data);
      else if (target === "push") setPushAnalysis(data);
      else if (target === "email") setEmailAnalysis(data);
      else if (target === "app" && space) setAppAnalysis(prev => ({ ...prev, [space]: data }));
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

        // Backend returns the latest cached result for this campaign+channel
        let analysis: AnalyzePieceResponse | null = null;
        try {
          analysis = await aiAPI.getAnalysis(id!, "SMS");
        } catch {
          /* no stored analysis */
        }
        // If no cached analysis found but we have a current smsAnalysis, use it as fallback
        if (!analysis && smsAnalysis) {
          analysis = smsAnalysis;
        }
        setSubmittedSmsAnalysis(analysis);
      } else {
        setPushSubmitted(true);
        setTimeout(() => setPushSubmitted(false), 3000);

        // Backend returns the latest cached result for this campaign+channel
        let analysis: AnalyzePieceResponse | null = null;
        try {
          analysis = await aiAPI.getAnalysis(id!, "Push");
        } catch {
          /* no stored analysis */
        }
        // If no cached analysis found but we have a current pushAnalysis, use it as fallback
        if (!analysis && pushAnalysis) {
          analysis = pushAnalysis;
        }
        setSubmittedPushAnalysis(analysis);
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
      if (!smsText.trim()) return;
      setIsAnalyzingSms(true);
      try {
        await analyzePieceMutation.mutateAsync({
          input: { channel: "SMS", content: { body: smsText } },
          target: "sms",
        });
      } catch {
        /* already surfaced */
      } finally {
        setIsAnalyzingSms(false);
      }
    } else {
      if (!pushTitle.trim() || !pushBody.trim()) return;
      setIsAnalyzingPush(true);
      try {
        await analyzePieceMutation.mutateAsync({
          input: { channel: "Push", content: { title: pushTitle, body: pushBody } },
          target: "push",
        });
      } catch {
        /* already surfaced */
      } finally {
        setIsAnalyzingPush(false);
      }
    }
  };

  const handleAnalyzePieceEmail = async () => {
    if (!id || !emailPieceId) return;
    setIsAnalyzingEmail(true);
    try {
      await analyzePieceMutation.mutateAsync({
        input: { channel: "EMAIL", content: { campaign_id: id, piece_id: emailPieceId } },
        target: "email",
      });
    } catch {
      /* already surfaced */
    } finally {
      setIsAnalyzingEmail(false);
    }
  };

  const handleAnalyzePieceApp = async (space: string) => {
    if (!id || !appPieceId) return;
    setIsAnalyzingAppBySpace(prev => ({ ...prev, [space]: true }));
    try {
      await analyzePieceMutation.mutateAsync({
        input: { channel: "APP", content: { campaign_id: id, piece_id: appPieceId, commercial_space: space } },
        target: "app",
        space,
      });
    } catch {
      /* already surfaced */
    } finally {
      setIsAnalyzingAppBySpace(prev => ({ ...prev, [space]: false }));
    }
  };

  // --- Marketing Manager: Validar com IA (peças sem parecer de IA) ---
  const handleMmValidateWithIa = async (
    pr: { channel: string; pieceId: string; commercialSpace?: string }
  ) => {
    if (!id || !campaign) return;
    const key = `${pr.channel}:${pr.pieceId}:${pr.commercialSpace || ""}`;
    setMmValidatingPiece(key);
    try {
      const ch = pr.channel.toUpperCase();
      let input: AnalyzePieceInput;

      if (ch === "SMS") {
        const piece = campaign.creativePieces?.find(p => p.pieceType === "SMS");
        if (!piece?.text) throw new Error("Conteúdo SMS não encontrado");
        input = { channel: "SMS", content: { body: piece.text } };
      } else if (ch === "PUSH") {
        const piece = campaign.creativePieces?.find(p => p.pieceType === "Push");
        if (!piece?.title || !piece?.body) throw new Error("Conteúdo Push não encontrado");
        input = { channel: "Push", content: { title: piece.title, body: piece.body } };
      } else if (ch === "EMAIL") {
        const piece = campaign.creativePieces?.find(p => p.pieceType === "E-mail");
        if (!piece?.id) throw new Error("Peça de e-mail não encontrada");
        input = { channel: "EMAIL", content: { campaign_id: id, piece_id: piece.id } };
      } else if (ch === "APP") {
        const piece = campaign.creativePieces?.find(p => p.pieceType === "App");
        if (!piece?.id || !pr.commercialSpace) throw new Error("Peça App não encontrada");
        input = { channel: "APP", content: { campaign_id: id, piece_id: piece.id, commercial_space: pr.commercialSpace } };
      } else {
        throw new Error(`Canal desconhecido: ${ch}`);
      }

      // 1. Executar validação de IA
      const result = await aiAPI.analyzePiece(id, input);
      const iaVerdict: "approved" | "rejected" = result.is_valid === "valid" ? "approved" : "rejected";

      // 2. Guardar resultado para exibir justificativas
      setMmAnalysisResults(prev => ({ ...prev, [key]: result }));

      // 3. Atualizar ia_verdict no piece_review
      await campaignsAPI.updateIaVerdict(id, {
        channel: ch,
        pieceId: pr.pieceId,
        commercialSpace: pr.commercialSpace,
        iaVerdict,
      });

      queryClient.invalidateQueries({ queryKey: ["campaign", id] });
      queryClient.invalidateQueries({ queryKey: ["campaigns"] });
    } catch (error: any) {
      setStatusError(error.message || "Erro ao validar com IA");
      setTimeout(() => setStatusError(null), 5000);
    } finally {
      setMmValidatingPiece(null);
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
      if (result.id) setAppPieceId(result.id);
      if (result.fileUrls) {
        try {
          const fileUrls = JSON.parse(result.fileUrls);
          setAppFileUrls(prev => ({ ...prev, ...fileUrls }));
        } catch (e) {
          /* ignore */
        }
      }
      setAppAnalysis(prev => {
        const next = { ...prev };
        delete next[commercialSpace];
        return next;
      });
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
    setSkipEmailAnalysisFetch(true); // Evita re-fetch da análise antiga após upload
    try {
      const result = await creativePiecesAPI.uploadEmailFile(id, file);
      queryClient.invalidateQueries({ queryKey: ["campaign", id] });
      if (result.id) setEmailPieceId(result.id);
      if (result.htmlFileUrl) setEmailFileUrl(result.htmlFileUrl);
      setEmailAnalysis(null);
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
      setAppAnalysis(prev => {
        const next = { ...prev };
        delete next[commercialSpace];
        return next;
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
      setEmailPieceId(null);
      setEmailSubmitted(false);
      setEmailAnalysis(null);
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


  const channelToApi = (ch: string) => {
    if (ch === "Push") return "PUSH";
    if (ch === "E-mail") return "EMAIL";
    if (ch === "App") return "APP";
    return "SMS";
  };

  const buildPieceReviewsForSubmit = (): { channel: string; pieceId: string; commercialSpace?: string; iaVerdict: string | null }[] => {
    if (!campaign?.creativePieces?.length) return [];
    const out: { channel: string; pieceId: string; commercialSpace?: string; iaVerdict: string | null }[] = [];
    const smsPiece = campaign.creativePieces.find(p => p.pieceType === "SMS");
    const pushPiece = campaign.creativePieces.find(p => p.pieceType === "Push");
    const emailPiece = campaign.creativePieces.find(p => p.pieceType === "E-mail");
    const appPiece = campaign.creativePieces.find(p => p.pieceType === "App");
    const toIa = (a: AnalyzePieceResponse | null | undefined): "approved" | "rejected" | null => {
      if (!a) return null; // não validado por IA
      return a.is_valid === "valid" ? "approved" : "rejected";
    };
    if (smsPiece?.id) {
      const a = submittedSmsAnalysis ?? smsAnalysis;
      out.push({ channel: "SMS", pieceId: smsPiece.id, iaVerdict: toIa(a) });
    }
    if (pushPiece?.id) {
      const a = submittedPushAnalysis ?? pushAnalysis;
      out.push({ channel: "PUSH", pieceId: pushPiece.id, iaVerdict: toIa(a) });
    }
    if (emailPiece?.id) {
      out.push({ channel: "EMAIL", pieceId: emailPiece.id, iaVerdict: toIa(emailAnalysis) });
    }
    if (appPiece?.id && appPiece.fileUrls) {
      try {
        const urls = JSON.parse(appPiece.fileUrls) as Record<string, string>;
        Object.keys(urls).forEach(space => {
          out.push({
            channel: "APP",
            pieceId: appPiece!.id,
            commercialSpace: space,
            iaVerdict: toIa(appAnalysis[space]),
          });
        });
      } catch {
        /* ignore */
      }
    }
    return out;
  };

  const computeReviewState = (c: Campaign) => {
    const pr = c.pieceReviews ?? [];
    let allApproved = pr.length > 0;
    let anyRejected = false;
    for (const r of pr) {
      const ia = r.iaVerdict ? r.iaVerdict.toLowerCase() : null;
      const hu = (r.humanVerdict || "").toLowerCase();
      // ia null = não validado por IA → depende do humano (como "rejected")
      const approved = (ia === "approved" && hu !== "manually_rejected") || ((ia === "rejected" || ia === null) && hu === "approved");
      const rejected = (ia === "approved" && hu === "manually_rejected") || ((ia === "rejected" || ia === null) && hu === "rejected");
      if (!approved) allApproved = false;
      if (rejected) anyRejected = true;
    }
    return { allApproved, anyRejected };
  };

  const getPieceReviewsForChannel = (ch: string) => {
    const apiCh = channelToApi(ch);
    return (campaign?.pieceReviews ?? []).filter((r) => (r.channel || "").toUpperCase() === apiCh);
  };

  const openRejectionDialog = (payload: {
    pr: { pieceId: string; commercialSpace: string };
    uiChannel: string;
    action: "reject" | "manually_reject";
    spaceLabel?: string;
  }) => {
    setRejectionDialogPayload(payload);
    setRejectionReasonInput("");
    setRejectionDialogOpen(true);
  };

  const confirmRejection = () => {
    if (!rejectionDialogPayload || !id) return;
    const reason = rejectionReasonInput.trim() || undefined;
    reviewPieceMutation.mutate(
      {
        channel: channelToApi(rejectionDialogPayload.uiChannel),
        pieceId: rejectionDialogPayload.pr.pieceId,
        commercialSpace: rejectionDialogPayload.pr.commercialSpace || undefined,
        action: rejectionDialogPayload.action,
        rejectionReason: reason,
      },
      {
        onSettled: () => {
          setRejectionDialogOpen(false);
          setRejectionDialogPayload(null);
          setRejectionReasonInput("");
        },
      }
    );
  };

  const showPieceReviewBlock =
    (currentUser?.role === "Gestor de marketing" && campaign?.status === "CONTENT_REVIEW") ||
    (currentUser?.role === "Analista de negócios" && campaign?.status === "CONTENT_REVIEW") ||
    (currentUser?.role === "Analista de criação" && campaign?.status === "CONTENT_ADJUSTMENT");
  const showPieceReviewActions =
    currentUser?.role === "Gestor de marketing" && campaign?.status === "CONTENT_REVIEW";

  type PieceReviewType = NonNullable<NonNullable<Campaign["pieceReviews"]>[number]>;
  const renderPieceReviewBlock = (
    pr: PieceReviewType,
    uiChannel: string,
    spaceLabel?: string,
    showActions?: boolean
  ) => {
    const ia = pr.iaVerdict ? pr.iaVerdict.toLowerCase() : null;
    const hu = (pr.humanVerdict || "").toLowerCase();
    const notValidatedByIa = ia === null;
    const needsHuman = ia === "rejected" || notValidatedByIa;
    const canApproveReject = needsHuman && hu === "pending";
    const canManuallyReject = ia === "approved" && hu !== "manually_rejected";
    const pending = reviewPieceMutation.isPending;
    const displayActions = showActions !== false;
    const reviewed = hu !== "pending";
    const isApproved = hu === "approved" || (ia === "approved" && hu !== "manually_rejected");
    const isRejected = hu === "rejected" || hu === "manually_rejected";
    const blockVariant = isRejected ? "red" : isApproved ? "green" : "yellow";
    const variantClasses = {
      green: "bg-green-50 border-green-200 dark:bg-green-950/20 dark:border-green-800",
      red: "bg-red-50 border-red-200 dark:bg-red-950/20 dark:border-red-800",
      yellow: "bg-yellow-50 border-yellow-200 dark:bg-yellow-950/20 dark:border-yellow-800",
    };
    const iaLabel = notValidatedByIa ? "Não validado" : ia === "approved" ? "Aprovado" : "Reprovado";
    const huLabel = hu === "approved" ? "Aprovado" : hu === "rejected" ? "Reprovado" : hu === "manually_rejected" ? "Reprovado manualmente" : "Pendente";

    return (
      <div className={cn("mt-4 p-4 rounded-lg border-2", variantClasses[blockVariant])}>
        <div className="flex items-start gap-3">
          {blockVariant === "green" ? (
            <CheckCircle size={20} className="text-green-600 dark:text-green-400 mt-0.5 flex-shrink-0" />
          ) : blockVariant === "red" ? (
            <AlertCircle size={20} className="text-red-600 dark:text-red-400 mt-0.5 flex-shrink-0" />
          ) : (
            <AlertTriangle size={20} className="text-yellow-600 dark:text-yellow-400 mt-0.5 flex-shrink-0" />
          )}
          <div className="flex-1 min-w-0 space-y-2">
            {spaceLabel && <p className="text-xs font-medium text-foreground/60">{spaceLabel}</p>}
            <p className="text-sm font-semibold text-foreground">Revisão da peça</p>
            <div className="flex flex-wrap items-center gap-2 text-xs">
              <span className={cn(
                "font-medium px-2 py-0.5 rounded",
                ia === "approved" && "bg-green-500/20 text-green-800 dark:text-green-200",
                ia === "rejected" && "bg-red-500/20 text-red-800 dark:text-red-200",
                notValidatedByIa && "bg-gray-500/20 text-gray-800 dark:text-gray-200",
              )}>
                Parecer IA: {iaLabel}
              </span>
              <span className={cn(
                "font-medium px-2 py-0.5 rounded",
                hu === "approved" && "bg-green-500/20 text-green-800 dark:text-green-200",
                (hu === "rejected" || hu === "manually_rejected") && "bg-red-500/20 text-red-800 dark:text-red-200",
                hu === "pending" && "bg-muted text-foreground/70",
              )}>
                Revisão humana: {huLabel}
              </span>
            </div>
            {reviewed && pr.reviewedAt && (
              <p className="text-xs text-foreground/70 flex items-center gap-1.5">
                <User size={14} className="flex-shrink-0" />
                Revisado por <span className="font-medium text-foreground">{pr.reviewedByName || "Usuário"}</span>
                {" "}em {format(new Date(pr.reviewedAt), "dd/MM/yyyy 'às' HH:mm")}
              </p>
            )}
            {isRejected && pr.rejectionReason && (
              <div className="rounded-lg border border-red-500/20 bg-red-500/5 p-3">
                <p className="text-xs font-medium text-red-800 dark:text-red-200 mb-1">Motivo da reprovação</p>
                <p className="text-sm text-foreground whitespace-pre-wrap leading-relaxed">{pr.rejectionReason}</p>
              </div>
            )}
            {/* Botão "Validar com IA" — apenas para MM quando a peça não foi validada por IA */}
            {displayActions && notValidatedByIa && hu === "pending" && showPieceReviewActions && (() => {
              const pieceKey = `${channelToApi(uiChannel)}:${pr.pieceId}:${pr.commercialSpace || ""}`;
              const isValidating = mmValidatingPiece === pieceKey;
              return (
                <div className="pt-1">
                  <button
                    onClick={() => handleMmValidateWithIa({ channel: channelToApi(uiChannel), pieceId: pr.pieceId, commercialSpace: pr.commercialSpace || undefined })}
                    disabled={isValidating}
                    className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium bg-primary/10 text-primary hover:bg-primary/20 border border-primary/30 disabled:opacity-50 transition-colors"
                  >
                    {isValidating ? <Loader2 size={14} className="animate-spin" /> : <Sparkles size={14} />}
                    {isValidating ? "Validando..." : "Validar com IA"}
                  </button>
                </div>
              );
            })()}
            {/* Resultado detalhado da análise de IA (MM ou qualquer perfil com análise em cache) */}
            {(() => {
              const pieceKey = `${channelToApi(uiChannel)}:${pr.pieceId}:${pr.commercialSpace || ""}`;
              const ch = channelToApi(uiChannel);
              // Primeiro tenta resultado local (MM acabou de validar), depois busca do cache carregado ao abrir a página
              const analysis = mmAnalysisResults[pieceKey]
                || (ch === "SMS" ? submittedSmsAnalysis : null)
                || (ch === "PUSH" ? submittedPushAnalysis : null)
                || (ch === "EMAIL" ? emailAnalysis : null)
                || (ch === "APP" && pr.commercialSpace ? appAnalysis[pr.commercialSpace] : null);
              if (!analysis) return null;
              const isValid = analysis.is_valid === "valid";
              return (
                <div className={cn(
                  "mt-2 p-3 rounded-lg border",
                  isValid
                    ? "bg-green-50/50 border-green-200 dark:bg-green-950/10 dark:border-green-800"
                    : "bg-red-50/50 border-red-200 dark:bg-red-950/10 dark:border-red-800"
                )}>
                  <div className="flex items-start gap-2">
                    {isValid ? (
                      <CheckCircle size={16} className="text-green-600 dark:text-green-400 mt-0.5 flex-shrink-0" />
                    ) : (
                      <AlertCircle size={16} className="text-red-600 dark:text-red-400 mt-0.5 flex-shrink-0" />
                    )}
                    <div className="flex-1 min-w-0">
                      <p className={cn(
                        "text-xs font-semibold mb-1",
                        isValid ? "text-green-800 dark:text-green-200" : "text-red-800 dark:text-red-200"
                      )}>
                        {isValid ? "Conteúdo aprovado pela IA" : "Validação reprovada pela IA"}
                      </p>
                      <p className="text-sm text-foreground whitespace-pre-wrap leading-relaxed">
                        {analysis.analysis_text}
                      </p>
                      {analysis.created_at && (
                        <p className="text-xs text-foreground/50 mt-1.5">
                          Análise em {format(new Date(analysis.created_at), "dd/MM/yyyy 'às' HH:mm")}
                        </p>
                      )}
                    </div>
                  </div>
                </div>
              );
            })()}
            {displayActions && (canApproveReject || canManuallyReject) && (
              <div className="flex flex-wrap gap-2 pt-1">
                {canApproveReject && (
                  <>
                    <button
                      onClick={() => reviewPieceMutation.mutate({ channel: channelToApi(uiChannel), pieceId: pr.pieceId, commercialSpace: pr.commercialSpace || undefined, action: "approve" })}
                      disabled={pending}
                      className="px-3 py-1.5 rounded-lg text-sm font-medium bg-green-500/10 text-green-700 dark:text-green-300 hover:bg-green-500/20 border border-green-500/30 disabled:opacity-50 transition-colors"
                    >
                      Aprovar
                    </button>
                    <button
                      onClick={() => openRejectionDialog({ pr: { pieceId: pr.pieceId, commercialSpace: pr.commercialSpace || "" }, uiChannel, action: "reject", spaceLabel })}
                      disabled={pending}
                      className="px-3 py-1.5 rounded-lg text-sm font-medium bg-red-500/10 text-red-700 dark:text-red-300 hover:bg-red-500/20 border border-red-500/30 disabled:opacity-50 transition-colors"
                    >
                      Reprovar
                    </button>
                  </>
                )}
                {canManuallyReject && (
                  <button
                    onClick={() => openRejectionDialog({ pr: { pieceId: pr.pieceId, commercialSpace: pr.commercialSpace || "" }, uiChannel, action: "manually_reject", spaceLabel })}
                    disabled={pending}
                    className="px-3 py-1.5 rounded-lg text-sm font-medium border border-border bg-background/50 text-foreground hover:bg-muted/50 disabled:opacity-50 transition-colors"
                  >
                    Reprovar manualmente
                  </button>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    );
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

  
  type ActionItem = { 
    kind: "status" | "submit_for_review"; 
    label: string; 
    status?: CampaignStatus; 
    variant: string; 
    disabled?: boolean;
    disabledReason?: string;
  };

  const getAvailableActions = (): ActionItem[] => {
    if (!campaign || !currentUser) return [];

    const actions: ActionItem[] = [];
    const userRole = currentUser.role;

    if (userRole === "Analista de negócios") {
      if (campaign.status === "DRAFT" && campaign.createdBy === currentUser.id) {
        actions.push({ kind: "status", label: "Enviar para Criação", status: "CREATIVE_STAGE" as CampaignStatus, variant: "primary" });
      }
    }

    if (userRole === "Gestor de marketing") {
      if (campaign.status === "CONTENT_REVIEW") {
        const { allApproved, anyRejected } = computeReviewState(campaign);
        const pieceReviews = campaign.pieceReviews || [];
        const approvedCount = pieceReviews.filter(r => {
          const ia = r.iaVerdict ? r.iaVerdict.toLowerCase() : null;
          const hu = (r.humanVerdict || "").toLowerCase();
          return hu === "approved" || (hu === "pending" && ia === "approved");
        }).length;
        const totalCount = pieceReviews.length;
        
        actions.push(
          { 
            kind: "status", 
            label: "Aprovar Conteúdo", 
            status: "CAMPAIGN_BUILDING" as CampaignStatus, 
            variant: "success", 
            disabled: !allApproved,
            disabledReason: !allApproved 
              ? `Todas as peças precisam estar aprovadas (${approvedCount}/${totalCount} aprovadas)`
              : undefined
          },
          { 
            kind: "status", 
            label: "Solicitar Ajustes", 
            status: "CONTENT_ADJUSTMENT" as CampaignStatus, 
            variant: "warning", 
            disabled: !anyRejected,
            disabledReason: !anyRejected 
              ? "Só é possível solicitar ajustes quando há peças rejeitadas"
              : undefined
          }
        );
      }
    }

    if (userRole === "Analista de criação") {
      const pieces = buildPieceReviewsForSubmit();
      const noPieces = pieces.length === 0;
      const channels = campaign.communicationChannels || [];
      
      if (campaign.status === "CREATIVE_STAGE") {
        actions.push({
          kind: "submit_for_review",
          label: "Enviar para Revisão",
          variant: "primary",
          disabled: noPieces,
          disabledReason: noPieces 
            ? `Crie pelo menos uma peça criativa para os canais: ${channels.join(", ")}`
            : undefined
        });
      }
      if (campaign.status === "CONTENT_ADJUSTMENT") {
        actions.push({
          kind: "submit_for_review",
          label: "Reenviar para Revisão",
          variant: "primary",
          disabled: noPieces,
          disabledReason: noPieces 
            ? "Não há peças criativas para reenviar"
            : undefined
        });
      }
    }

    if (userRole === "Analista de campanhas") {
      if (campaign.status === "CAMPAIGN_BUILDING") {
        actions.push({ kind: "status", label: "Publicar Campanha", status: "CAMPAIGN_PUBLISHED" as CampaignStatus, variant: "success" });
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

  // Determine which channel is currently being analyzed
  const currentAnalyzingChannel = isAnalyzingEmail
    ? "EMAIL"
    : isAnalyzingSms
    ? "SMS"
    : isAnalyzingPush
    ? "PUSH"
    : isAnalyzingAnyApp
    ? "APP"
    : null;

  return (
    <div className="min-h-screen bg-background">
      <Header />

      {/* Validation Loading Overlay */}
      {currentAnalyzingChannel && (
        <ValidationLoadingOverlay
          isLoading={true}
          channel={currentAnalyzingChannel}
        />
      )}

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
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 flex flex-col gap-8">
        {/* Status Timeline - Horizontal */}
        <div className="p-4 rounded-lg border border-border/50 bg-card">
          <h3 className="text-sm font-semibold text-foreground mb-4">Jornada da Campanha</h3>
          <CampaignStatusTimeline 
            events={statusHistoryData?.events || []} 
            currentStatus={statusHistoryData?.currentStatus || campaign.status} 
          />
        </div>

        {/* Next Action Banner - Shows what the user should do next */}
        <NextActionBanner
          campaign={campaign}
          currentUser={currentUser}
          pieceCount={campaign.creativePieces?.length || 0}
          approvedPieceCount={
            (campaign.pieceReviews || []).filter(r => {
              const hu = (r.humanVerdict || "").toLowerCase();
              const ia = r.iaVerdict ? r.iaVerdict.toLowerCase() : null;
              return hu === "approved" || (hu === "pending" && ia === "approved");
            }).length
          }
          totalPieceCount={(campaign.pieceReviews || []).length}
          hasRejectedPieces={
            (campaign.pieceReviews || []).some(r => {
              const hu = (r.humanVerdict || "").toLowerCase();
              const ia = r.iaVerdict ? r.iaVerdict.toLowerCase() : null;
              return hu === "rejected" || hu === "manually_rejected" || (hu === "pending" && ia === "rejected");
            })
          }
        />
        
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 order-2">
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
                <TooltipProvider>
                  {getAvailableActions().map((action, index) => {
                    const variantClasses = {
                      primary: "bg-blue-500/10 text-blue-700 hover:bg-blue-500/20",
                      success: "bg-green-500/10 text-green-700 hover:bg-green-500/20",
                      warning: "bg-orange-500/10 text-orange-700 hover:bg-orange-500/20",
                    };
                    const isSubmit = action.kind === "submit_for_review";
                    const pending = isSubmit ? submitForReviewMutation.isPending : updateStatusMutation.isPending;
                    const disabled = pending || !!action.disabled;
                    
                    const buttonElement = (
                      <button
                        onClick={() => {
                          if (isSubmit) submitForReviewMutation.mutate(buildPieceReviewsForSubmit());
                          else if (action.status) handleStatusTransition(action.status);
                        }}
                        disabled={disabled}
                        className={cn(
                          "w-full px-4 py-2 rounded-lg font-medium transition-colors text-sm disabled:opacity-50 disabled:cursor-not-allowed",
                          variantClasses[action.variant as keyof typeof variantClasses] || variantClasses.primary
                        )}
                      >
                        {pending ? "Processando..." : action.label}
                      </button>
                    );
                    
                    // Wrap in tooltip if disabled with reason
                    if (disabled && action.disabledReason) {
                      return (
                        <Tooltip key={index}>
                          <TooltipTrigger asChild>
                            <span className="block">{buttonElement}</span>
                          </TooltipTrigger>
                          <TooltipContent side="left" className="max-w-xs">
                            <p className="text-sm">{action.disabledReason}</p>
                          </TooltipContent>
                        </Tooltip>
                      );
                    }
                    
                    return <div key={index}>{buttonElement}</div>;
                  })}
                </TooltipProvider>
              </div>
            </div>
          </div>
        </div>

        {/* Creative Pieces Section - For Creative Analysts, Business Analysts, and Campaign Analysts */}
        {((currentUser?.role === "Analista de negócios" && (campaign.status === "CONTENT_REVIEW" || campaign.status === "CAMPAIGN_BUILDING" || campaign.status === "CAMPAIGN_PUBLISHED")) ||
          (currentUser?.role === "Gestor de marketing" && (campaign.status === "CONTENT_REVIEW" || campaign.status === "CONTENT_ADJUSTMENT" || campaign.status === "CAMPAIGN_BUILDING" || campaign.status === "CAMPAIGN_PUBLISHED")) ||
          (currentUser?.role === "Analista de criação" && (campaign.status === "CREATIVE_STAGE" || campaign.status === "CONTENT_ADJUSTMENT" || campaign.status === "CONTENT_REVIEW")) ||
          (currentUser?.role === "Analista de campanhas" && (campaign.status === "CAMPAIGN_BUILDING" || campaign.status === "CAMPAIGN_PUBLISHED"))) && (
          <div id="creative-pieces-section" className="order-1 w-full">
            <div className={cn(
              "rounded-lg border overflow-hidden",
              currentUser?.role === "Analista de criação"
                ? "bg-gradient-to-br from-purple-50/80 via-purple-50/60 to-purple-100/40 dark:from-purple-950/30 dark:via-purple-900/20 dark:to-purple-950/20 border-purple-200/50 dark:border-purple-800/30 shadow-lg shadow-purple-500/10"
                : "border-border/50 bg-card"
            )}>
              {currentUser?.role === "Analista de criação" && (
                <div className="h-0.5 bg-gradient-to-r from-purple-400 via-purple-500 to-purple-400" />
              )}
              {/* Faixa fina sempre visível */}
              <div className={cn(
                "flex items-center justify-between gap-3 px-4 py-2.5",
                currentUser?.role === "Analista de criação"
                  ? "bg-purple-50/60 dark:bg-purple-950/20"
                  : "bg-muted/30"
              )}>
                <div className="flex items-center gap-2 min-w-0">
                  <div className={cn(
                    "p-1.5 rounded-md shrink-0",
                    currentUser?.role === "Analista de criação"
                      ? "bg-purple-500/20 dark:bg-purple-400/20"
                      : "bg-primary/10"
                  )}>
                    {currentUser?.role === "Analista de criação" ? (
                      <Sparkles size={18} className="text-purple-600 dark:text-purple-400" />
                    ) : (
                      <FileText size={18} className="text-primary" />
                    )}
                  </div>
                  <span className={cn(
                    "text-sm font-medium truncate",
                    currentUser?.role === "Analista de criação"
                      ? "text-purple-900 dark:text-purple-100"
                      : "text-foreground"
                  )}>
                    {currentUser?.role === "Analista de negócios" 
                      ? "Revisão de Peças Criativas" 
                      : currentUser?.role === "Analista de campanhas"
                      ? "Peças Criativas"
                      : "Peças Criativas"}
                  </span>
                  {/* History toggle button */}
                  {reviewHistory.length > 0 && (
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        setShowHistoryTimeline(!showHistoryTimeline);
                      }}
                      className={cn(
                        "ml-2 flex items-center gap-1 px-2 py-1 rounded text-xs font-medium transition-colors",
                        showHistoryTimeline
                          ? "bg-primary/20 text-primary"
                          : "bg-muted text-foreground/70 hover:bg-muted/80"
                      )}
                    >
                      <History size={14} />
                      Histórico
                    </button>
                  )}
                </div>
                <button
                  type="button"
                  onClick={() => setStudioOpen(!studioOpen)}
                  className={cn(
                    "flex items-center gap-1.5 shrink-0 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors",
                    currentUser?.role === "Analista de criação"
                      ? "bg-purple-500/20 text-purple-800 dark:text-purple-200 hover:bg-purple-500/30"
                      : "bg-primary/10 text-primary hover:bg-primary/20"
                  )}
                >
                  {studioOpen ? (
                    <>
                      <ChevronUp size={16} />
                      Recolher
                    </>
                  ) : (
                    <>
                      <Sparkles size={16} />
                      Ver peças
                    </>
                  )}
                </button>
              </div>

              <Collapsible open={studioOpen} onOpenChange={setStudioOpen}>
                <CollapsibleContent>
                  {/* History Timeline */}
                  {showHistoryTimeline && reviewHistory.length > 0 && (
                    <div className="px-4 py-4 border-t border-border/40 bg-muted/30">
                      <div className="flex items-center justify-between mb-4">
                        <h4 className="text-sm font-semibold text-foreground flex items-center gap-2">
                          <History size={16} />
                          Histórico de Revisões
                        </h4>
                        <button
                          type="button"
                          onClick={() => setShowHistoryTimeline(false)}
                          className="text-xs text-foreground/60 hover:text-foreground"
                        >
                          Fechar
                        </button>
                      </div>
                      <div className="max-h-96 overflow-y-auto">
                        <PieceReviewTimeline events={reviewHistory} />
                      </div>
                    </div>
                  )}
                  <div className="px-4 pb-6 pt-2 border-t border-border/40">
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
                      <TabsContent key={channel} value={channel} className="mt-0">
                        <div className={cn(
                          "grid gap-6",
                          canEdit
                            ? "grid-cols-1 lg:grid-cols-[minmax(0,440px)_1fr]"
                            : "grid-cols-1"
                        )}>
                          {/* Creation Section - Left, upload/criação */}
                          {canEdit && (
                            <div className="space-y-4">
                              <h3 className="text-base font-semibold text-foreground flex items-center gap-2">
                                <Sparkles size={16} className="text-purple-600" />
                                Criação
                              </h3>
                              
                              {/* SMS Channel Creation */}
                              {channel === "SMS" && (
                    <div className="p-4 rounded-lg border border-border/50 bg-card">
                      <div className="flex items-center justify-between mb-3">
                        <div className="flex items-center gap-2">
                          <div className="p-1.5 rounded-lg bg-primary/10">
                            <Smartphone size={20} className="text-primary" />
                          </div>
                          <div>
                            <h4 className="text-base font-semibold text-foreground">Texto SMS</h4>
                            <p className="text-xs text-foreground/60">Máximo recomendado: 160 caracteres</p>
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
                          className="resize-none text-sm font-medium"
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
                                    ? "Conteúdo aprovado" 
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
                    <div className="p-4 rounded-lg border border-border/50 bg-card">
                      <div className="flex items-center justify-between mb-3">
                        <div className="flex items-center gap-2">
                          <div className="p-1.5 rounded-lg bg-primary/10">
                            <MessageSquareIcon size={20} className="text-primary" />
                          </div>
                          <div>
                            <h4 className="text-base font-semibold text-foreground">Notificação Push</h4>
                            <p className="text-xs text-foreground/60">Título (até 50) e corpo (até 120 caracteres)</p>
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
                            <Label htmlFor="push-title" className="text-xs font-medium text-foreground">
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
                            className="resize-none text-sm font-medium"
                          />
                        </div>
                        <div className="space-y-2">
                          <div className="flex items-center justify-between">
                            <Label htmlFor="push-body" className="text-xs font-medium text-foreground">
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
                            className="resize-none text-sm font-medium"
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
                                    ? "Conteúdo aprovado" 
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
                    <div className="p-4 rounded-lg border border-border/50 bg-card">
                      <div className="flex items-center gap-2 mb-3">
                        <div className="p-1.5 rounded-lg bg-primary/10">
                          <Image size={20} className="text-primary" />
                        </div>
                        <div>
                          <h4 className="text-base font-semibold text-foreground">Arquivos App</h4>
                          <p className="text-xs text-foreground/60">Envie 1 arquivo PNG por espaço comercial</p>
                        </div>
                      </div>
                      <div className="space-y-4">
                        {campaign.commercialSpaces.map((space) => {
                          const hasFile = !!appFileUrls[space];
                          const uploadError = appUploadErrors[space];
                          return (
                            <div key={space} className="space-y-2">
                              <div className="flex items-center justify-between">
                                <Label className="text-xs font-medium text-foreground">{space}</Label>
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
                                <div className="mt-2 space-y-2">
                                  <div className="p-2 rounded-lg bg-muted/30 border border-border/50">
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
                                          onClick={() => handleAnalyzePieceApp(space)}
                                          disabled={!appPieceId || isAnalyzingAnyApp || !!appAnalysis[space]}
                                          className={cn(
                                            "flex items-center gap-1.5 px-2 py-1 rounded text-xs font-medium transition-all",
                                            (!appPieceId || isAnalyzingAnyApp || !!appAnalysis[space])
                                              ? "text-foreground/30 cursor-not-allowed bg-muted"
                                              : "bg-primary text-white hover:bg-primary/90"
                                          )}
                                        >
                                          {isAnalyzingAppBySpace[space] ? (
                                            <Loader2 size={12} className="animate-spin" />
                                          ) : appAnalysis[space] ? (
                                            <CheckCircle size={12} />
                                          ) : (
                                            <Sparkles size={12} />
                                          )}
                                          {isAnalyzingAppBySpace[space] ? "Validando..." : appAnalysis[space] ? "Análise OK" : "Validar"}
                                        </button>
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
                                  {appAnalysis[space] && (
                                    <div className={cn(
                                      "p-3 rounded-lg border-2",
                                      appAnalysis[space]!.is_valid === "valid"
                                        ? "bg-green-50 border-green-200 dark:bg-green-950/20 dark:border-green-800"
                                        : appAnalysis[space]!.is_valid === "invalid"
                                        ? "bg-red-50 border-red-200 dark:bg-red-950/20 dark:border-red-800"
                                        : "bg-yellow-50 border-yellow-200 dark:bg-yellow-950/20 dark:border-yellow-800"
                                    )}>
                                      <div className="flex items-start gap-2">
                                        {appAnalysis[space]!.is_valid === "valid" ? (
                                          <CheckCircle size={16} className="text-green-600 dark:text-green-400 mt-0.5 flex-shrink-0" />
                                        ) : appAnalysis[space]!.is_valid === "invalid" ? (
                                          <AlertCircle size={16} className="text-red-600 dark:text-red-400 mt-0.5 flex-shrink-0" />
                                        ) : (
                                          <AlertTriangle size={16} className="text-yellow-600 dark:text-yellow-400 mt-0.5 flex-shrink-0" />
                                        )}
                                        <div className="flex-1 min-w-0">
                                          <p className={cn(
                                            "text-xs font-semibold mb-1",
                                            appAnalysis[space]!.is_valid === "valid"
                                              ? "text-green-900 dark:text-green-100"
                                              : appAnalysis[space]!.is_valid === "invalid"
                                              ? "text-red-900 dark:text-red-100"
                                              : "text-yellow-900 dark:text-yellow-100"
                                          )}>
                                            {appAnalysis[space]!.is_valid === "valid"
                                              ? "Conteúdo aprovado"
                                              : appAnalysis[space]!.is_valid === "invalid"
                                              ? "Validação Reprovada"
                                              : "Validação com Ressalvas"}
                                          </p>
                                          <p className="text-xs text-foreground whitespace-pre-wrap leading-relaxed">
                                            {appAnalysis[space]!.analysis_text}
                                          </p>
                                        </div>
                                      </div>
                                    </div>
                                  )}
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
                    <div className="p-4 rounded-lg border border-border/50 bg-card">
                      <div className="flex items-center justify-between gap-2 mb-3">
                        <div className="flex items-center gap-2">
                          <div className="p-1.5 rounded-lg bg-primary/10">
                            <FileCode size={20} className="text-primary" />
                          </div>
                          <div>
                            <h4 className="text-base font-semibold text-foreground">Arquivo E-mail</h4>
                            <p className="text-xs text-foreground/60">Envie 1 arquivo HTML</p>
                          </div>
                        </div>
                        <button
                          onClick={handleAnalyzePieceEmail}
                          disabled={isAnalyzingEmail || !emailFileUrl || !emailPieceId || !!emailAnalysis}
                          className={cn(
                            "flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-all",
                            (isAnalyzingEmail || !emailFileUrl || !emailPieceId || !!emailAnalysis)
                              ? "text-foreground/30 cursor-not-allowed bg-muted"
                              : "bg-primary text-white hover:bg-primary/90"
                          )}
                        >
                          {isAnalyzingEmail ? (
                            <>
                              <Loader2 size={18} className="animate-spin" />
                              Validando...
                            </>
                          ) : emailAnalysis ? (
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
                        {emailAnalysis && (
                          <div className={cn(
                            "p-4 rounded-lg border-2",
                            emailAnalysis.is_valid === "valid"
                              ? "bg-green-50 border-green-200 dark:bg-green-950/20 dark:border-green-800"
                              : emailAnalysis.is_valid === "invalid"
                              ? "bg-red-50 border-red-200 dark:bg-red-950/20 dark:border-red-800"
                              : "bg-yellow-50 border-yellow-200 dark:bg-yellow-950/20 dark:border-yellow-800"
                          )}>
                            <div className="flex items-start gap-3">
                              {emailAnalysis.is_valid === "valid" ? (
                                <CheckCircle size={20} className="text-green-600 dark:text-green-400 mt-0.5 flex-shrink-0" />
                              ) : emailAnalysis.is_valid === "invalid" ? (
                                <AlertCircle size={20} className="text-red-600 dark:text-red-400 mt-0.5 flex-shrink-0" />
                              ) : (
                                <AlertTriangle size={20} className="text-yellow-600 dark:text-yellow-400 mt-0.5 flex-shrink-0" />
                              )}
                              <div className="flex-1">
                                <p className={cn(
                                  "text-sm font-semibold mb-2",
                                  emailAnalysis.is_valid === "valid"
                                    ? "text-green-900 dark:text-green-100"
                                    : emailAnalysis.is_valid === "invalid"
                                    ? "text-red-900 dark:text-red-100"
                                    : "text-yellow-900 dark:text-yellow-100"
                                )}>
                                  {emailAnalysis.is_valid === "valid"
                                    ? "Conteúdo aprovado"
                                    : emailAnalysis.is_valid === "invalid"
                                    ? "Validação Reprovada"
                                    : "Validação com Ressalvas"}
                                </p>
                                <p className="text-sm text-foreground whitespace-pre-wrap leading-relaxed">
                                  {emailAnalysis.analysis_text}
                                </p>
                                <p className="text-xs text-foreground/60 mt-2">
                                  Análise realizada em {format(new Date(emailAnalysis.created_at), "dd/MM/yyyy 'às' HH:mm")}
                                </p>
                              </div>
                            </div>
                          </div>
                        )}
                      </div>
                            </div>
                            )}
                          </div>
                        )}

                        {/* Visualization Section - Right, or full width when !canEdit */}
                        <div className={cn("space-y-4", !canEdit && "lg:col-span-2")}>
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
                                          ? "Conteúdo aprovado" 
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
                              {showPieceReviewBlock && (() => {
                                const pr = getPieceReviewsForChannel("SMS")[0];
                                return pr ? renderPieceReviewBlock(pr, "SMS", undefined, showPieceReviewActions) : null;
                              })()}
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
                                          ? "Conteúdo aprovado" 
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
                              {showPieceReviewBlock && (() => {
                                const pr = getPieceReviewsForChannel("Push")[0];
                                return pr ? renderPieceReviewBlock(pr, "Push", undefined, showPieceReviewActions) : null;
                              })()}
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
                                        <div className="relative rounded-lg border-2 border-border/30 overflow-hidden bg-muted/20 max-w-sm">
                                          <img
                                            src={fileUrls[space]}
                                            alt={`Imagem para ${space}`}
                                            className="w-full h-auto max-h-56 object-contain"
                                            onError={(e) => {
                                              (e.target as HTMLImageElement).src = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='400' height='200'%3E%3Crect fill='%23ddd' width='400' height='200'/%3E%3Ctext fill='%23999' font-family='sans-serif' font-size='14' x='50%25' y='50%25' text-anchor='middle' dy='.3em'%3EImagem não disponível%3C/text%3E%3C/svg%3E";
                                            }}
                                          />
                                        </div>
                                        <div className="flex items-center gap-3">
                                          <a
                                            href={fileUrls[space]}
                                            target="_blank"
                                            rel="noopener noreferrer"
                                            className="text-xs text-primary hover:underline flex items-center gap-1"
                                          >
                                            <Image size={12} />
                                            Abrir imagem em nova aba
                                          </a>
                                          {(currentUser?.role === "Analista de negócios" || currentUser?.role === "Analista de campanhas") && (
                                            <button
                                              type="button"
                                              onClick={() => {
                                                const spaceName = space.replace(/\s+/g, "_").replace(/[^a-zA-Z0-9_]/g, "");
                                                downloadCreativePiece(
                                                  campaign.id,
                                                  "APP",
                                                  `app-${campaign.name.replace(/\s+/g, "_")}-${spaceName}.png`,
                                                  space
                                                );
                                              }}
                                              className="text-xs text-primary hover:underline flex items-center gap-1"
                                            >
                                              <Download size={12} />
                                              Baixar imagem
                                            </button>
                                          )}
                                        </div>
                                        {/* Warning if this piece was submitted without validation */}
                                        {!appAnalysis[space] && (
                                          <div className="p-3 rounded-lg border-2 bg-yellow-50 border-yellow-200 dark:bg-yellow-950/20 dark:border-yellow-800">
                                            <div className="flex items-start gap-2">
                                              <AlertTriangle size={16} className="text-yellow-600 dark:text-yellow-400 mt-0.5 flex-shrink-0" />
                                              <div className="flex-1 min-w-0">
                                                <p className="text-xs font-semibold mb-0.5 text-yellow-900 dark:text-yellow-100">
                                                  Peça não validada
                                                </p>
                                                <p className="text-xs text-yellow-800 dark:text-yellow-200">
                                                  Esta peça foi submetida sem validação automática. Recomendamos validar antes de prosseguir.
                                                </p>
                                              </div>
                                            </div>
                                          </div>
                                        )}
                                        {showPieceReviewBlock && (() => {
                                          const pr = getPieceReviewsForChannel("App").find((r) => r.commercialSpace === space);
                                          return pr ? renderPieceReviewBlock(pr, "App", space, showPieceReviewActions) : null;
                                        })()}
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
                                <div className="bg-muted/30 p-4 rounded-lg border border-border/30 max-w-2xl">
                                  <p className="text-xs font-medium text-foreground/60 mb-2">Preview do HTML</p>
                                  <iframe
                                    src={piece.htmlFileUrl}
                                    className="w-full h-[320px] border border-border/30 rounded bg-white"
                                    title="E-mail HTML Preview"
                                    sandbox="allow-same-origin"
                                  />
                                </div>
                                <div className="flex items-center gap-4">
                                  <a
                                    href={piece.htmlFileUrl}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="text-sm text-primary hover:underline flex items-center gap-2"
                                  >
                                    <FileCode size={14} />
                                    Abrir arquivo HTML em nova aba
                                  </a>
                                  {(currentUser?.role === "Analista de negócios" || currentUser?.role === "Analista de campanhas") && (
                                    <button
                                      type="button"
                                      onClick={() => downloadCreativePiece(
                                        campaign.id,
                                        "EMAIL",
                                        `email-${campaign.name.replace(/\s+/g, "_")}.html`
                                      )}
                                      className="text-sm text-primary hover:underline flex items-center gap-2"
                                    >
                                      <Download size={14} />
                                      Baixar HTML
                                    </button>
                                  )}
                                </div>
                              </div>
                              {/* Warning if piece was submitted without validation */}
                              {!emailAnalysis && (
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
                              {showPieceReviewBlock && (() => {
                                const pr = getPieceReviewsForChannel("E-mail")[0];
                                return pr ? renderPieceReviewBlock(pr, "E-mail", undefined, showPieceReviewActions) : null;
                              })()}
                              <div className="text-xs text-foreground/60 text-right mt-3">
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
                        </div>
                      </TabsContent>
                    );
                  })}
                </Tabs>
              )}
                  </div>
                </CollapsibleContent>
              </Collapsible>
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

      {/* Rejection reason Dialog (Reprovar / Reprovar manualmente) */}
      <Dialog open={rejectionDialogOpen} onOpenChange={(open) => { if (!open) { setRejectionDialogOpen(false); setRejectionDialogPayload(null); setRejectionReasonInput(""); } }}>
        <DialogContent className="sm:max-w-[500px]">
          <DialogHeader>
            <DialogTitle>
              {rejectionDialogPayload?.action === "manually_reject" ? "Reprovar manualmente" : "Reprovar peça"}
            </DialogTitle>
            <DialogDescription>
              Descreva o problema com a peça (opcional). O motivo será registrado e visível para o time de criação.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="rejection-reason">Motivo da reprovação</Label>
              <Textarea
                id="rejection-reason"
                placeholder="Ex.: Texto não está alinhado às diretrizes de tom; imagem com resolução inadequada..."
                value={rejectionReasonInput}
                onChange={(e) => setRejectionReasonInput(e.target.value)}
                rows={5}
                className="resize-none"
                maxLength={2000}
              />
              <p className="text-xs text-foreground/60">
                Opcional. Máximo 2.000 caracteres.
              </p>
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                setRejectionDialogOpen(false);
                setRejectionDialogPayload(null);
                setRejectionReasonInput("");
              }}
              disabled={reviewPieceMutation.isPending}
            >
              Cancelar
            </Button>
            <Button
              onClick={confirmRejection}
              disabled={reviewPieceMutation.isPending}
              className="bg-red-600 hover:bg-red-700 text-white"
            >
              {reviewPieceMutation.isPending ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Enviando...
                </>
              ) : (
                "Confirmar reprovação"
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
