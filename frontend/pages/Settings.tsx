import Header from "@/components/Header";
import { ArrowLeft, User, Mail, Shield, Loader2, AlertCircle } from "lucide-react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { authAPI } from "@/lib/api";

export default function Settings() {
  const { data: user, isLoading, error } = useQuery({
    queryKey: ["currentUser"],
    queryFn: authAPI.getCurrentUser,
    throwOnError: false, // Don't throw on 401, it's expected when not logged in
  });

  return (
    <div className="min-h-screen bg-background">
      <Header />
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <Link to="/" className="flex items-center gap-2 text-primary hover:text-primary/80 mb-8">
          <ArrowLeft size={20} />
          Voltar para o Painel
        </Link>

        <div className="mb-8">
          <h1 className="text-3xl font-bold text-foreground mb-2">Configurações</h1>
          <p className="text-foreground/60">
            Gerencie sua conta e visualize suas informações
          </p>
        </div>

        {isLoading ? (
          <div className="text-center py-12">
            <Loader2 className="mx-auto size-8 text-primary animate-spin mb-4" />
            <p className="text-foreground/60">Carregando informações...</p>
          </div>
        ) : error ? (
          <div className="text-center py-12 border border-border/50 rounded-lg bg-card">
            <AlertCircle className="mx-auto size-12 text-status-rejected mb-4" />
            <h3 className="text-lg font-semibold text-foreground mb-2">Erro ao carregar informações</h3>
            <p className="text-foreground/60">
              {error instanceof Error ? error.message : "Não foi possível carregar suas informações."}
            </p>
          </div>
        ) : user ? (
          <div className="space-y-6">
            {/* User Information Card */}
            <div className="rounded-lg border border-border/50 bg-card p-6">
              <h2 className="text-xl font-semibold text-foreground mb-6 flex items-center gap-2">
                <User size={24} />
                Informações do Usuário
              </h2>
              
              <div className="space-y-4">
                <div className="flex items-start gap-4">
                  <div className="p-2 rounded-lg bg-primary/10 text-primary">
                    <Mail size={20} />
                  </div>
                  <div className="flex-1">
                    <p className="text-sm text-foreground/60 mb-1">E-mail</p>
                    <p className="text-base font-medium text-foreground">{user.email}</p>
                  </div>
                </div>

                {user.full_name && (
                  <div className="flex items-start gap-4">
                    <div className="p-2 rounded-lg bg-primary/10 text-primary">
                      <User size={20} />
                    </div>
                    <div className="flex-1">
                      <p className="text-sm text-foreground/60 mb-1">Nome Completo</p>
                      <p className="text-base font-medium text-foreground">{user.full_name}</p>
                    </div>
                  </div>
                )}

                {user.role && (
                  <div className="flex items-start gap-4">
                    <div className="p-2 rounded-lg bg-primary/10 text-primary">
                      <Shield size={20} />
                    </div>
                    <div className="flex-1">
                      <p className="text-sm text-foreground/60 mb-1">Perfil de Acesso</p>
                      <p className="text-base font-medium text-foreground">{user.role}</p>
                    </div>
                  </div>
                )}

                <div className="flex items-start gap-4">
                  <div className="p-2 rounded-lg bg-primary/10 text-primary">
                    <Shield size={20} />
                  </div>
                  <div className="flex-1">
                    <p className="text-sm text-foreground/60 mb-1">Status da Conta</p>
                    <p className="text-base font-medium text-foreground">
                      {user.is_active ? (
                        <span className="text-green-500">Ativa</span>
                      ) : (
                        <span className="text-red-500">Inativa</span>
                      )}
                    </p>
                  </div>
                </div>
              </div>
            </div>

            {/* Placeholder for future settings */}
            <div className="rounded-lg border border-border/50 bg-card p-6">
              <h2 className="text-xl font-semibold text-foreground mb-4">Outras Configurações</h2>
              <p className="text-foreground/60 text-sm">
                Mais opções de configuração estarão disponíveis em breve.
              </p>
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
}
