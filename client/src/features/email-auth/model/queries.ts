import { useQuery } from "@tanstack/react-query";
import { getServiceStatus } from "./api";

export const serviceStatusQueryKey = ["service-status"] as const;

/**
 * Server-reported availability of self-service registration and the password
 * rules the register endpoint enforces.
 */
export function useServiceStatus() {
  return useQuery({
    queryKey: serviceStatusQueryKey,
    queryFn: getServiceStatus,
  });
}
