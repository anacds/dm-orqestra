import { cn } from "@/lib/utils";

interface LogoProps {
  size?: "sm" | "md" | "lg";
  showText?: boolean;
  className?: string;
}

export default function Logo({ size = "md", showText = false, className }: LogoProps) {
  const sizeClasses = {
    sm: "w-8 h-8 text-base",
    md: "w-12 h-12 text-xl",
    lg: "w-16 h-16 text-2xl",
  };

  const noteSize = {
    sm: "text-[6px]",
    md: "text-[8px]",
    lg: "text-[10px]",
  };

  return (
    <div className={cn("flex items-center gap-2 relative", className)}>
      <div className={cn("relative rounded-lg bg-gradient-to-br from-primary to-secondary flex items-center justify-center", sizeClasses[size])}>
        {/* Letter O */}
        <span className="text-white font-bold relative z-10">O</span>
      </div>
      
      {/* Musical notes - positioned around the logo like sparkles (few, subtle) */}
      <span className={cn("absolute top-0 left-1/2 -translate-x-1/2 -translate-y-full -mt-0.5 text-primary/50", noteSize[size])}>
        ♪
      </span>
      <span className={cn("absolute top-1/2 right-0 translate-x-full -translate-y-1/2 -mr-0.5 text-primary/45", noteSize[size])}>
        ♫
      </span>
      <span className={cn("absolute bottom-0 left-1/4 translate-y-full -translate-y-1/2 -mb-0.5 text-primary/50", noteSize[size])}>
        ♩
      </span>
      
      {showText && (
        <span className="hidden sm:inline text-xl font-bold text-foreground ml-2">Orqestra - Campaign Hub</span>
      )}
    </div>
  );
}

