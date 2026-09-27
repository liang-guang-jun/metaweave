import {
  useInfiniteQuery,
  useMutation,
  useQueryClient,
} from "@tanstack/react-query";
import { createWorkspace, listWorkspaces } from "./api";

export const workspacesPageSize = 20;

export const workspaceKeys = {
  all: ["workspaces"] as const,
  list: (tenantId: string, keyword: string) =>
    [...workspaceKeys.all, tenantId, keyword] as const,
};

export function useWorkspacesQuery(
  tenantId: string | undefined,
  keyword: string,
) {
  const tenantKey = tenantId ?? "";

  return useInfiniteQuery({
    queryKey: workspaceKeys.list(tenantKey, keyword),
    queryFn: ({ pageParam }) =>
      listWorkspaces(keyword, pageParam, workspacesPageSize),
    initialPageParam: 1,
    getNextPageParam: (lastPage) =>
      lastPage.hasNext ? lastPage.page + 1 : undefined,
    enabled: Boolean(tenantId),
    // Keep the current list visible while a new search term loads, but never
    // carry another tenant's pages across a tenant switch.
    placeholderData: (previousData, previousQuery) =>
      previousQuery?.queryKey[1] === tenantKey ? previousData : undefined,
  });
}

export function useCreateWorkspaceMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      name,
      description,
    }: {
      name: string;
      description?: string;
    }) => createWorkspace(name, description),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: workspaceKeys.all });
    },
  });
}
