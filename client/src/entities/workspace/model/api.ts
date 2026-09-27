import { api } from "@/shared/api/client";
import type { Workspace } from "./types";

type WorkspacePageResponse = {
  items: Array<{
    workspace_id: string;
    tenant_id: string;
    display_name: string;
    description: string;
    active: boolean;
  }>;
  total: number;
  page: number;
  size: number;
  pages: number;
  has_next: boolean;
};

export type WorkspacePage = {
  items: Workspace[];
  total: number;
  page: number;
  size: number;
  pages: number;
  hasNext: boolean;
};

export async function listWorkspaces(
  keyword = "",
  page = 1,
  size = 20,
): Promise<WorkspacePage> {
  const response = await api.get<WorkspacePageResponse>("/catalog/workspaces", {
    params: { keyword, page, size },
  });
  return {
    ...response.data,
    items: response.data.items.map((item) => ({
      id: item.workspace_id,
      name: item.display_name,
      description: item.description,
      pinned: false,
    })),
    hasNext: response.data.has_next,
  };
}

export async function createWorkspace(name: string, description?: string) {
  const response = await api.post<WorkspacePageResponse["items"][number]>(
    "/catalog/workspaces",
    { display_name: name, description: description ?? "" },
  );
  return {
    id: response.data.workspace_id,
    name: response.data.display_name,
    description: response.data.description,
    pinned: false,
  } satisfies Workspace;
}
