import { UserRole } from "@shared/api";

export const BUSINESS_ANALYST_ROLE: UserRole = "Analista de negócios";
export const MARKETING_MANAGER_ROLE: UserRole = "Gestor de marketing";

export function isBusinessAnalyst(role?: UserRole | null): boolean {
  return role === BUSINESS_ANALYST_ROLE;
}

export function isMarketingManager(role?: UserRole | null): boolean {
  return role === MARKETING_MANAGER_ROLE;
}

