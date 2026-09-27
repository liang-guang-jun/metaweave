import { useQuery } from "@tanstack/react-query";
import { getCurrentUser } from "./api";

export const currentUserQueryKey = ["current-user"] as const;

export function useCurrentUserQuery() {
  return useQuery({
    queryKey: currentUserQueryKey,
    queryFn: getCurrentUser,
  });
}
