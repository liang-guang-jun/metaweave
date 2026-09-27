import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type UIEvent,
} from "react";
import { toast } from "sonner";
import styled from "styled-components";
import { selectTenant } from "@/entities/tenant/model/api";
import {
  useCreateTenantMutation,
  useTenantsQuery,
} from "@/entities/tenant/model/queries";
import type { Tenant } from "@/entities/tenant/model/types";
import { useCurrentUserQuery } from "@/entities/user/model/queries";
import {
  useCreateWorkspaceMutation,
  useWorkspacesQuery,
  workspacesPageSize,
} from "@/entities/workspace/model/queries";
import type { Workspace } from "@/entities/workspace/model/types";
import { storageKeys } from "@/shared/config/storage";
import { useDebouncedValue } from "@/shared/lib/useDebouncedValue";
import { TenantCreateModal } from "@/widgets/workspace-layout/ui/TenantCreateModal";
import { TenantSwitcherModal } from "@/widgets/workspace-layout/ui/TenantSwitcherModal";
import {
  WorkspaceContent,
  WorkspaceEmptyState,
} from "@/widgets/workspace-layout/ui/WorkspaceContent";
import { WorkspaceCreateModal } from "@/widgets/workspace-layout/ui/WorkspaceCreateModal";
import { WorkspaceDrawer } from "@/widgets/workspace-layout/ui/WorkspaceDrawer";
import { WorkspaceHeader } from "@/widgets/workspace-layout/ui/WorkspaceHeader";

const Frame = styled.div`
  min-height: 100svh;
  background: ${({ theme }) => theme.color.background.canvas};
`;

function workspaceStorageKey(tenantId: string) {
  return `${storageKeys.lastWorkspaceId}:${tenantId}`;
}

function pinnedWorkspaceIds(tenantId: string | undefined) {
  if (!tenantId) return new Set<string>();
  try {
    const raw = window.localStorage.getItem(
      `${storageKeys.pinnedWorkspaceIds}:${tenantId}`,
    );
    return new Set<string>(raw ? JSON.parse(raw) : []);
  } catch {
    return new Set<string>();
  }
}

export function WorkspaceLayout() {
  const [activeTenantId, setActiveTenantId] = useState<string>();
  const [activeTenant, setActiveTenant] = useState<Tenant>();
  const [activeWorkspace, setActiveWorkspace] = useState<Workspace>();
  const [tenantQuery, setTenantQuery] = useState("");
  const [workspaceQuery, setWorkspaceQuery] = useState("");
  const [, setPinVersion] = useState(0);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [workspaceCreateOpen, setWorkspaceCreateOpen] = useState(false);
  const [workspaceName, setWorkspaceName] = useState("");
  const [workspaceDescription, setWorkspaceDescription] = useState("");
  const [tenantCreateOpen, setTenantCreateOpen] = useState(false);
  const [tenantName, setTenantName] = useState("");
  const [tenantDescription, setTenantDescription] = useState("");
  const workspaceListRef = useRef<HTMLDivElement | null>(null);

  const currentUserQuery = useCurrentUserQuery();

  const debouncedTenantQuery = useDebouncedValue(tenantQuery, 300);
  const tenantsQuery = useTenantsQuery(debouncedTenantQuery.trim());

  const debouncedWorkspaceQuery = useDebouncedValue(
    workspaceQuery,
    workspaceQuery ? 300 : 0,
  );
  const workspacesQuery = useWorkspacesQuery(
    activeTenantId,
    debouncedWorkspaceQuery.trim(),
  );
  const createWorkspace = useCreateWorkspaceMutation();
  const createTenant = useCreateTenantMutation();

  const tenants = useMemo(
    () => tenantsQuery.data?.items ?? [],
    [tenantsQuery.data],
  );
  const tenantSearching =
    tenantsQuery.isFetching || tenantQuery !== debouncedTenantQuery;

  // Pinned workspace ids live in localStorage; bumping the pin version state
  // re-reads them after a toggle.
  const pinnedIds = pinnedWorkspaceIds(activeTenantId);
  const workspaces = (workspacesQuery.data?.pages ?? [])
    .flatMap((page) => page.items)
    .map((workspace) => ({
      ...workspace,
      pinned: pinnedIds.has(workspace.id),
    }));
  const pinned = workspaces.filter((workspace) => workspace.pinned);
  const unpinned = workspaces.filter((workspace) => !workspace.pinned);
  const workspaceSearching =
    workspacesQuery.isFetching && !workspacesQuery.isFetchingNextPage;

  const rememberedId =
    activeTenantId && !workspaceQuery.trim()
      ? window.localStorage.getItem(workspaceStorageKey(activeTenantId))
      : null;
  const rememberedWorkspace = rememberedId
    ? workspaces.find((workspace) => workspace.id === rememberedId)
    : undefined;
  const openWorkspace = activeWorkspace ?? rememberedWorkspace;

  useEffect(() => {
    if (tenantsQuery.isError) toast.error("Unable to load tenants");
  }, [tenantsQuery.isError]);

  useEffect(() => {
    if (workspacesQuery.isError) toast.error("Unable to load workspaces");
  }, [workspacesQuery.isError]);

  const selectTenantForSession = useCallback(
    async (tenant: Tenant, announce = true) => {
      try {
        await selectTenant(tenant.id);
        setActiveTenantId(tenant.id);
        setActiveTenant(tenant);
        setActiveWorkspace(undefined);
        window.localStorage.setItem(storageKeys.activeTenantId, tenant.id);
        window.localStorage.setItem(storageKeys.lastTenantId, tenant.id);
        if (announce) toast.success(`Switched to ${tenant.name}`);
        return true;
      } catch {
        toast.error(`Unable to switch to ${tenant.name}`);
        return false;
      }
    },
    [],
  );

  useEffect(() => {
    if (activeTenantId || tenants.length === 0) return;
    const rememberedTenantId = window.localStorage.getItem(
      storageKeys.lastTenantId,
    );
    const rememberedTenant = tenants.find(
      (tenant) => tenant.id === rememberedTenantId,
    );
    if (rememberedTenant) void selectTenantForSession(rememberedTenant, false);
  }, [activeTenantId, selectTenantForSession, tenants]);

  const handleWorkspaceScroll = (event: UIEvent<HTMLDivElement>) => {
    const target = event.currentTarget;
    if (target.scrollHeight - target.scrollTop - target.clientHeight >= 56)
      return;
    if (!workspacesQuery.hasNextPage || workspacesQuery.isFetchingNextPage)
      return;
    void workspacesQuery.fetchNextPage();
  };

  const switchWorkspace = (workspace: Workspace, announce = true) => {
    if (!activeTenantId) return;
    setActiveWorkspace(workspace);
    window.localStorage.setItem(
      workspaceStorageKey(activeTenantId),
      workspace.id,
    );
    setDrawerOpen(false);
    if (announce) toast.success(`Switched to ${workspace.name}`);
  };

  const togglePin = (workspaceId: string) => {
    if (!activeTenantId) return;
    const ids = pinnedWorkspaceIds(activeTenantId);
    if (ids.has(workspaceId)) ids.delete(workspaceId);
    else ids.add(workspaceId);
    window.localStorage.setItem(
      `${storageKeys.pinnedWorkspaceIds}:${activeTenantId}`,
      JSON.stringify([...ids]),
    );
    setPinVersion((version) => version + 1);
  };

  const submitWorkspace = async () => {
    const name = workspaceName.trim();
    if (!name) {
      toast.error("Enter a workspace name");
      return;
    }
    if (!activeTenantId) {
      toast.error("Select a tenant first");
      return;
    }
    try {
      const workspace = await createWorkspace.mutateAsync({
        name,
        description: workspaceDescription.trim(),
      });
      setWorkspaceName("");
      setWorkspaceDescription("");
      setWorkspaceCreateOpen(false);
      switchWorkspace(workspace, false);
      toast.success(`${name} workspace created`);
    } catch {
      toast.error("Unable to create workspace");
    }
  };

  const submitTenant = async (name: string, description: string) => {
    if (!name.trim()) {
      toast.error("Enter a tenant name");
      return false;
    }
    try {
      const tenant = await createTenant.mutateAsync({
        name: name.trim(),
        description,
      });
      const selected = await selectTenantForSession(tenant, false);
      if (selected) toast.success(`${name.trim()} tenant created`);
      return selected;
    } catch {
      toast.error("Unable to create tenant");
      return false;
    }
  };

  return (
    <Frame>
      <WorkspaceHeader
        activeWorkspace={openWorkspace}
        activeTenant={activeTenant}
        currentUser={currentUserQuery.data}
        tenants={tenants}
        tenantQuery={tenantQuery}
        tenantLoading={tenantSearching}
        onTenantQueryChange={setTenantQuery}
        onSelectTenant={(tenant) => selectTenantForSession(tenant)}
        onCreateTenant={submitTenant}
        onOpenWorkspaceSwitcher={() => setDrawerOpen(true)}
      />
      <WorkspaceContent>
        {!activeTenant ? (
          <TenantSwitcherModal
            open
            inline
            hideClose
            activeTenantId=""
            tenants={tenants}
            query={tenantQuery}
            isSearching={tenantSearching}
            onClose={() => undefined}
            onQueryChange={setTenantQuery}
            onSelect={(tenant) => {
              void selectTenantForSession(tenant);
            }}
            onCreateNew={() => {
              setTenantName("");
              setTenantDescription("");
              setTenantCreateOpen(true);
            }}
          />
        ) : !openWorkspace ? (
          <WorkspaceEmptyState
            title="Select a workspace"
            message="Click the workspace switcher in the top-left to choose a workspace."
          />
        ) : null}
      </WorkspaceContent>
      <WorkspaceDrawer
        open={drawerOpen}
        query={workspaceQuery}
        isSearching={workspaceSearching}
        isLoadingMore={workspacesQuery.isFetchingNextPage}
        pinned={pinned}
        unpinned={unpinned}
        filteredCount={workspaces.length}
        loadChunk={workspacesPageSize}
        listRef={workspaceListRef}
        onClose={() => setDrawerOpen(false)}
        onCreate={() => {
          setDrawerOpen(false);
          setWorkspaceCreateOpen(true);
        }}
        onQueryChange={setWorkspaceQuery}
        onScroll={handleWorkspaceScroll}
        onSelect={switchWorkspace}
        onTogglePin={togglePin}
      />
      <WorkspaceCreateModal
        open={workspaceCreateOpen}
        name={workspaceName}
        description={workspaceDescription}
        onNameChange={setWorkspaceName}
        onDescriptionChange={setWorkspaceDescription}
        onClose={() => setWorkspaceCreateOpen(false)}
        onCreate={() => {
          void submitWorkspace();
        }}
      />
      <TenantCreateModal
        open={tenantCreateOpen}
        name={tenantName}
        description={tenantDescription}
        onNameChange={setTenantName}
        onDescriptionChange={setTenantDescription}
        onClose={() => setTenantCreateOpen(false)}
        onCreate={() => {
          void submitTenant(tenantName, tenantDescription).then((created) => {
            if (created) {
              setTenantName("");
              setTenantDescription("");
              setTenantCreateOpen(false);
            }
          });
        }}
      />
    </Frame>
  );
}
