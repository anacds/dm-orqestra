import { Navigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { authAPI } from "@/lib/api";

interface ProtectedRouteProps {
  children: React.ReactNode;
}

export default function ProtectedRoute({ children }: ProtectedRouteProps) {
  const { data: user, isLoading } = useQuery({
    queryKey: ["currentUser"],
    queryFn: authAPI.getCurrentUser,
    retry: false,
    staleTime: 5 * 60 * 1000, 
    throwOnError: false, 
  });

  if (isLoading) {
    return <div>Loading...</div>;
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
}

