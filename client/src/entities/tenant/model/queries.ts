import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createTenant, listTenants } from "./api";
import type { TenantPage } from "./api";

export const tenantKeys = {
  all: ["tenants"] as const,
  list: (keyword: string) => [...tenantKeys.all, keyword] as const,
};

export function useTenantsQuery(keyword: string) {
  return useQuery({
    queryKey: tenantKeys.list(keyword),
    queryFn: () => listTenants(keyword, 1, 100),
    // Keep the previous list visible while a new search term loads.
    placeholderData: (previousData) => previousData,
  });
}

export function useCreateTenantMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      name,
      description,
    }: {
      name: string;
      description?: string;
    }) => createTenant(name, description),
    onSuccess: (tenant) => {
      queryClient.setQueryData<TenantPage>(tenantKeys.list(""), (current) =>
        current
          ? {
              ...current,
              items: [
                tenant,
                ...current.items.filter((item) => item.id !== tenant.id),
              ],
            }
          : current,
      );
      void queryClient.invalidateQueries({ queryKey: tenantKeys.all });
    },
  });
}
