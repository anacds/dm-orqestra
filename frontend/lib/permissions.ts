import { UserRole } from "@shared/api";

export const BUSINESS_ANALYST_ROLE: UserRole = "Analista de negócios";

export function isBusinessAnalyst(role?: UserRole | null): boolean {
  return role === BUSINESS_ANALYST_ROLE;
}

