import { Building2, ChevronsUpDown, LogOut, UserRound } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import styled from "styled-components";
import type { Tenant } from "@/entities/tenant/model/types";
import { TenantCreateModal } from "@/widgets/workspace-layout/ui/TenantCreateModal";
import { TenantSwitcherModal } from "@/widgets/workspace-layout/ui/TenantSwitcherModal";

type ProfilePanelProps = {
  open: boolean;
  username: string;
  email: string;
  initials?: string;
  activeTenant: Tenant | undefined;
  tenants: Tenant[];
  tenantQuery: string;
  tenantLoading: boolean;
  onTenantQueryChange: (value: string) => void;
  onSelectTenant: (tenant: Tenant) => Promise<boolean>;
  onCreateTenant: (name: string, description: string) => Promise<boolean>;
  onAccount: () => void;
  onLogout: () => void;
};

const Panel = styled.section<{ $open: boolean }>`
  position: absolute;
  top: calc(100% + ${({ theme }) => theme.space[3]});
  right: 0;
  z-index: ${({ theme }) => theme.zIndex.overlay + 1};
  width: 280px;
  padding: ${({ theme }) => theme.space[2]};
  border: ${({ theme }) => theme.border.thin} solid
    ${({ theme }) => theme.color.border.subtle};
  border-radius: ${({ theme }) => theme.radius.lg};
  background: ${({ theme }) => theme.color.background.elevated};
  box-shadow: ${({ theme }) => theme.shadow.lg};
  opacity: ${({ $open }) => ($open ? 1 : 0)};
  pointer-events: ${({ $open }) => ($open ? "auto" : "none")};
  transform: ${({ $open }) =>
    $open ? "translateY(0) scale(1)" : "translateY(-6px) scale(.98)"};
  transform-origin: top right;
  transition:
    opacity ${({ theme }) => theme.motion.fast}
      ${({ theme }) => theme.motion.ease},
    transform ${({ theme }) => theme.motion.fast}
      ${({ theme }) => theme.motion.ease};
`;

const ProfileInfo = styled.div`
  display: flex;
  align-items: center;
  gap: ${({ theme }) => theme.space[3]};
  padding: ${({ theme }) => theme.space[3]};
`;

const ProfileAvatar = styled.div`
  display: grid;
  width: 44px;
  height: 44px;
  flex: 0 0 44px;
  place-items: center;
  border-radius: 50%;
  color: ${({ theme }) => theme.color.text.inverse};
  background: ${({ theme }) => theme.color.accent.violet};
  font-size: ${({ theme }) => theme.font.size.sm};
  font-weight: ${({ theme }) => theme.font.weight.bold};
`;

const ProfileText = styled.div`
  min-width: 0;
  strong,
  span {
    display: block;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  strong {
    color: ${({ theme }) => theme.color.text.primary};
    font-size: ${({ theme }) => theme.font.size.md};
    font-weight: ${({ theme }) => theme.font.weight.semibold};
  }
  span {
    margin-top: ${({ theme }) => theme.space[1]};
    color: ${({ theme }) => theme.color.text.muted};
    font-size: ${({ theme }) => theme.font.size.sm};
  }
`;

const Divider = styled.div`
  height: 1px;
  margin: ${({ theme }) => theme.space[2]} 0;
  background: ${({ theme }) => theme.color.border.subtle};
`;

const PanelAction = styled.button<{ $danger?: boolean }>`
  display: flex;
  width: 100%;
  min-height: 42px;
  align-items: center;
  gap: ${({ theme }) => theme.space[3]};
  padding: 0 ${({ theme }) => theme.space[3]};
  border: 0;
  border-radius: ${({ theme }) => theme.radius.md};
  color: ${({ theme, $danger }) =>
    $danger ? theme.color.status.error : theme.color.text.secondary};
  background: transparent;
  font-size: ${({ theme }) => theme.font.size.sm};
  font-weight: ${({ theme }) => theme.font.weight.semibold};
  text-align: left;
  transition:
    background ${({ theme }) => theme.motion.fast}
      ${({ theme }) => theme.motion.ease},
    transform ${({ theme }) => theme.motion.fast}
      ${({ theme }) => theme.motion.ease};
  svg:last-child {
    margin-left: auto;
    color: ${({ theme }) => theme.color.text.muted};
  }
  &:hover {
    background: ${({ theme }) => theme.color.interactive.secondary};
    transform: translateX(2px);
  }
  &:active {
    transform: translateX(2px) translateY(1px);
  }
`;

export function ProfilePanel({
  open,
  username,
  email,
  initials = "MW",
  activeTenant,
  tenants,
  tenantQuery,
  tenantLoading,
  onTenantQueryChange,
  onSelectTenant,
  onCreateTenant,
  onAccount,
  onLogout,
}: ProfilePanelProps) {
  const [tenantModalOpen, setTenantModalOpen] = useState(false);
  const [tenantCreateOpen, setTenantCreateOpen] = useState(false);
  const [tenantName, setTenantName] = useState("");
  const [tenantDescription, setTenantDescription] = useState("");

  const handleTenantSelect = async (tenant: Tenant) => {
    if (await onSelectTenant(tenant)) setTenantModalOpen(false);
  };

  const handleCreateTenant = () => {
    setTenantModalOpen(false);
    setTenantName("");
    setTenantDescription("");
    setTenantCreateOpen(true);
  };

  const createTenant = async () => {
    const name = tenantName.trim();
    if (!name) {
      toast.error("Enter a tenant name");
      return;
    }
    if (await onCreateTenant(name, tenantDescription.trim())) {
      setTenantName("");
      setTenantDescription("");
      setTenantCreateOpen(false);
    }
  };

  return (
    <>
      <Panel $open={open} aria-hidden={!open} aria-label="Profile panel">
        <ProfileInfo>
          <ProfileAvatar aria-hidden="true">{initials}</ProfileAvatar>
          <ProfileText>
            <strong>{username}</strong>
            <span>{email}</span>
          </ProfileText>
        </ProfileInfo>
        <Divider />
        <PanelAction type="button" onClick={() => setTenantModalOpen(true)}>
          <Building2 size={17} />
          <span>{activeTenant?.name ?? "Select tenant"}</span>
          <ChevronsUpDown size={16} />
        </PanelAction>
        <Divider />
        <PanelAction type="button" onClick={onAccount}>
          <UserRound size={17} />
          <span>Account</span>
        </PanelAction>
        <PanelAction type="button" $danger onClick={onLogout}>
          <LogOut size={17} />
          <span>Logout</span>
        </PanelAction>
      </Panel>
      <TenantSwitcherModal
        open={tenantModalOpen}
        activeTenantId={activeTenant?.id ?? ""}
        tenants={tenants}
        query={tenantQuery}
        isSearching={tenantLoading}
        onClose={() => setTenantModalOpen(false)}
        onQueryChange={onTenantQueryChange}
        onSelect={handleTenantSelect}
        onCreateNew={handleCreateTenant}
      />
      <TenantCreateModal
        open={tenantCreateOpen}
        name={tenantName}
        description={tenantDescription}
        onNameChange={setTenantName}
        onDescriptionChange={setTenantDescription}
        onClose={() => setTenantCreateOpen(false)}
        onCreate={createTenant}
      />
    </>
  );
}
