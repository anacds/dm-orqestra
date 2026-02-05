import { useState, useEffect } from "react";
import { Loader2, CheckCircle, FileImage, Search, Brain, FileCheck } from "lucide-react";
import { cn } from "@/lib/utils";

interface ValidationStep {
  id: string;
  label: string;
  icon: React.ElementType;
}

const VALIDATION_STEPS: Record<string, ValidationStep[]> = {
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

// overlay
const CHANNEL_LABELS: Record<string, string> = {
  SMS: "SMS",
  PUSH: "Push Notification",
  EMAIL: "E-mail",
  APP: "App",
};

interface Props {
  isLoading: boolean;
  channel: "SMS" | "PUSH" | "EMAIL" | "APP";
  className?: string;
}

export function ValidationLoadingOverlay({ isLoading, channel, className }: Props) {
  const [currentStep, setCurrentStep] = useState(0);
  const [currentTip, setCurrentTip] = useState(0);

  const isSimpleChannel = channel === "SMS" || channel === "PUSH";
  const steps = VALIDATION_STEPS[channel] || [];

  // Reset when loading starts
  useEffect(() => {
    if (isLoading) {
      setCurrentStep(0);
      setCurrentTip(0);
    }
  }, [isLoading]);

  // Progress through steps (only for complex channels)
  useEffect(() => {
    if (!isLoading || isSimpleChannel) return;

    const stepInterval = setInterval(() => {
      setCurrentStep((prev) => {
        if (prev >= steps.length - 1) return prev;
        return prev + 1;
      });
    }, channel === "EMAIL" ? 8000 : 6000);

    return () => clearInterval(stepInterval);
  }, [isLoading, channel, steps.length, isSimpleChannel]);

  // Rotate tips (only for complex channels)
  useEffect(() => {
    if (!isLoading || isSimpleChannel) return;

    const tipInterval = setInterval(() => {
      setCurrentTip((prev) => (prev + 1) % LOADING_TIPS.length);
    }, 4000);

    return () => clearInterval(tipInterval);
  }, [isLoading, isSimpleChannel]);

  if (!isLoading) return null;

  // Simple overlay for SMS and PUSH
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

  // Full overlay for EMAIL and APP
  return (
    <div className={cn(
      "fixed inset-0 z-50 flex items-center justify-center bg-background/80 backdrop-blur-sm",
      className
    )}>
      <div className="bg-card border border-border rounded-2xl shadow-2xl p-8 max-w-md w-full mx-4 space-y-6">
        {/* Header */}
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

        {/* Progress Steps */}
        <div className="space-y-3">
          {steps.map((step, index) => {
            const Icon = step.icon;
            const isActive = index === currentStep;
            const isComplete = index < currentStep;

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
          })}
        </div>

        {/* Rotating Tip */}
        <div className="bg-muted/50 rounded-lg p-4 min-h-[60px] flex items-center justify-center">
          <p className="text-sm text-center text-muted-foreground animate-pulse">
            {LOADING_TIPS[currentTip]}
          </p>
        </div>
      </div>
    </div>
  );
}
