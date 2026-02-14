import { useState, useEffect, useMemo } from "react";
import { Loader2, CheckCircle, FileImage, Search, Brain, FileCheck, Shield } from "lucide-react";
import { cn } from "@/lib/utils";
import type { ValidationStepEvent } from "@/lib/api";

interface ValidationStep {
  id: string;
  label: string;
  icon: React.ElementType;
}

const NODE_TO_STEP: Record<string, { label: string; icon: React.ElementType }> = {
  validate_channel: { label: "Validando estrutura", icon: FileCheck },
  retrieve_content: { label: "Extraindo conteúdo da peça", icon: FileImage },
  validate_specs: { label: "Verificando especificações técnicas", icon: FileCheck },
  validate_branding: { label: "Analisando conformidade visual", icon: Brain },
  validate_compliance: { label: "Consultando diretrizes jurídicas", icon: Search },
  issue_final_verdict: { label: "Gerando resultado final", icon: Shield },
};

const EXPECTED_NODES: Record<string, string[]> = {
  EMAIL: ["validate_channel", "retrieve_content", "validate_specs", "validate_branding", "validate_compliance", "issue_final_verdict"],
  APP: ["validate_channel", "validate_specs", "validate_branding", "validate_compliance", "issue_final_verdict"],
};

const FALLBACK_STEPS: Record<string, ValidationStep[]> = {
  EMAIL: [
    { id: "convert", label: "Extraindo as imagens", icon: FileImage },
    { id: "retrieve", label: "Consultando diretrizes jurídicas", icon: Search },
    { id: "analyze", label: "Analisando conformidade", icon: Brain },
    { id: "result", label: "Gerando resultado", icon: FileCheck },
  ],
  APP: [
    { id: "retrieve", label: "Consultando diretrizes jurídicas", icon: Search },
    { id: "analyze", label: "Analisando conformidade visual", icon: Brain },
    { id: "result", label: "Gerando resultado", icon: FileCheck },
  ],
};

const LOADING_TIPS = [
  "Dica: Links devem apontar para domínios oficiais da Orqestra",
  "Dica: Todo e-mail precisa de link de descadastro",
  "Dica: Evite termos como 'garantido' ou 'sem risco'",
  "Dica: O nome correto é 'Orqestra' (não Orquestra)",
  "Dica: Dados pessoais sensíveis são proibidos no conteúdo",
  "Analisando milhares de diretrizes jurídicas...",
  "Verificando conformidade com boas práticas de CRM...",
];

const CHANNEL_LABELS: Record<string, string> = {
  SMS: "SMS",
  PUSH: "Push Notification",
  EMAIL: "E-mail",
  APP: "App",
};

interface Props {
  isLoading: boolean;
  channel: "SMS" | "PUSH" | "EMAIL" | "APP";
  liveSteps?: Map<string, ValidationStepEvent>;
  className?: string;
}

export function ValidationLoadingOverlay({ isLoading, channel, liveSteps, className }: Props) {
  const [fallbackStep, setFallbackStep] = useState(0);
  const [currentTip, setCurrentTip] = useState(0);

  const isSimpleChannel = channel === "SMS" || channel === "PUSH";
  const hasLiveSteps = liveSteps && liveSteps.size > 0;

  useEffect(() => {
    if (isLoading) {
      setFallbackStep(0);
      setCurrentTip(0);
    }
  }, [isLoading]);

  useEffect(() => {
    if (!isLoading || isSimpleChannel || hasLiveSteps) return;

    const fallbackSteps = FALLBACK_STEPS[channel] || [];
    const stepInterval = setInterval(() => {
      setFallbackStep((prev) => {
        if (prev >= fallbackSteps.length - 1) return prev;
        return prev + 1;
      });
    }, channel === "EMAIL" ? 8000 : 6000);

    return () => clearInterval(stepInterval);
  }, [isLoading, channel, isSimpleChannel, hasLiveSteps]);

  useEffect(() => {
    if (!isLoading || isSimpleChannel) return;

    const tipInterval = setInterval(() => {
      setCurrentTip((prev) => (prev + 1) % LOADING_TIPS.length);
    }, 4000);

    return () => clearInterval(tipInterval);
  }, [isLoading, isSimpleChannel]);

  const liveStepsUI = useMemo(() => {
    if (!hasLiveSteps) return null;

    const expectedNodes = EXPECTED_NODES[channel] || [];
    return expectedNodes.map((nodeId) => {
      const event = liveSteps!.get(nodeId);
      const meta = NODE_TO_STEP[nodeId] || { label: nodeId, icon: FileCheck };
      const label = event?.label || meta.label;
      const status: "pending" | "active" | "done" =
        event?.status === "done" ? "done" :
        event?.status === "started" ? "active" : "pending";

      return { id: nodeId, label, icon: meta.icon, status };
    });
  }, [hasLiveSteps, liveSteps, channel]);

  if (!isLoading) return null;

  if (isSimpleChannel) {
    return (
      <div className={cn(
        "fixed inset-0 z-50 flex items-center justify-center bg-background/80 backdrop-blur-sm",
        className
      )}>
        <div className="bg-card border border-border rounded-xl shadow-xl p-6 max-w-xs w-full mx-4 text-center space-y-4">
          <Loader2 className="w-10 h-10 text-primary animate-spin mx-auto" />
          <div>
            <p className="text-base font-medium text-foreground">
              Validando {CHANNEL_LABELS[channel]}
            </p>
            <p className="text-sm text-muted-foreground mt-1">
              Aguarde um momento...
            </p>
          </div>
        </div>
      </div>
    );
  }

  const fallbackSteps = FALLBACK_STEPS[channel] || [];
  const useRealSteps = liveStepsUI && liveStepsUI.length > 0;

  return (
    <div className={cn(
      "fixed inset-0 z-50 flex items-center justify-center bg-background/80 backdrop-blur-sm",
      className
    )}>
      <div className="bg-card border border-border rounded-2xl shadow-2xl p-8 max-w-md w-full mx-4 space-y-6">
        <div className="text-center space-y-2">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-primary/10 mb-2">
            <Loader2 className="w-8 h-8 text-primary animate-spin" />
          </div>
          <h3 className="text-xl font-semibold text-foreground">
            Validando Peça
          </h3>
          <p className="text-sm text-muted-foreground">
            Canal: <span className="font-medium text-foreground">{CHANNEL_LABELS[channel]}</span>
          </p>
        </div>

        <div className="space-y-3">
          {useRealSteps
            ? liveStepsUI!.map((step) => {
                const Icon = step.icon;
                const isActive = step.status === "active";
                const isComplete = step.status === "done";

                return (
                  <div
                    key={step.id}
                    className={cn(
                      "flex items-center gap-3 p-3 rounded-lg transition-all duration-300",
                      isActive && "bg-primary/10 border border-primary/20",
                      isComplete && "bg-green-500/10",
                      !isActive && !isComplete && "opacity-40"
                    )}
                  >
                    <div className={cn(
                      "flex items-center justify-center w-8 h-8 rounded-full transition-all",
                      isComplete && "bg-green-500 text-white",
                      isActive && "bg-primary text-white",
                      !isActive && !isComplete && "bg-muted text-muted-foreground"
                    )}>
                      {isComplete ? (
                        <CheckCircle className="w-4 h-4" />
                      ) : isActive ? (
                        <Loader2 className="w-4 h-4 animate-spin" />
                      ) : (
                        <Icon className="w-4 h-4" />
                      )}
                    </div>
                    <span className={cn(
                      "text-sm font-medium transition-colors",
                      isActive && "text-primary",
                      isComplete && "text-green-600",
                      !isActive && !isComplete && "text-muted-foreground"
                    )}>
                      {step.label}
                    </span>
                  </div>
                );
              })
            : fallbackSteps.map((step, index) => {
                const Icon = step.icon;
                const isActive = index === fallbackStep;
                const isComplete = index < fallbackStep;

                return (
                  <div
                    key={step.id}
                    className={cn(
                      "flex items-center gap-3 p-3 rounded-lg transition-all duration-300",
                      isActive && "bg-primary/10 border border-primary/20",
                      isComplete && "bg-green-500/10",
                      !isActive && !isComplete && "opacity-40"
                    )}
                  >
                    <div className={cn(
                      "flex items-center justify-center w-8 h-8 rounded-full transition-all",
                      isComplete && "bg-green-500 text-white",
                      isActive && "bg-primary text-white",
                      !isActive && !isComplete && "bg-muted text-muted-foreground"
                    )}>
                      {isComplete ? (
                        <CheckCircle className="w-4 h-4" />
                      ) : isActive ? (
                        <Loader2 className="w-4 h-4 animate-spin" />
                      ) : (
                        <Icon className="w-4 h-4" />
                      )}
                    </div>
                    <span className={cn(
                      "text-sm font-medium transition-colors",
                      isActive && "text-primary",
                      isComplete && "text-green-600",
                      !isActive && !isComplete && "text-muted-foreground"
                    )}>
                      {step.label}
                    </span>
                  </div>
                );
              })
          }
        </div>

        <div className="bg-muted/50 rounded-lg p-4 min-h-[60px] flex items-center justify-center">
          <p className="text-sm text-center text-muted-foreground animate-pulse">
            {LOADING_TIPS[currentTip]}
          </p>
        </div>
      </div>
    </div>
  );
}
