import { Bell, ChevronDown, CircleHelp, Search, Settings } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import styled from "styled-components";
import brandDarkAsset from "@/assets/brand-dark.png";
import brandLightAsset from "@/assets/brand-light.png";
import { ThemeSwitcher } from "@/features/theme-switcher/ui/ThemeSwitcher";
import type { Tenant } from "@/entities/tenant/model/types";
import {
  displayNameFromEmail,
  initialsFromEmail,
} from "@/entities/user/model/profile";
import type { User } from "@/entities/user/model/types";
import type { Workspace } from "@/entities/workspace/model/types";
import { routes } from "@/shared/config/routes";
import { clearAccessToken } from "@/shared/lib/auth";
import { useTheme } from "@/shared/theme/useTheme";
import { Clickable } from "@/shared/ui/Clickable";
import { ProfilePanel } from "@/widgets/workspace-layout/ui/ProfilePanel";
import { SettingsDropdown } from "@/widgets/workspace-layout/ui/SettingsDropdown";

type WorkspaceHeaderProps = {
  activeWorkspace: Workspace | undefined;
  activeTenant: Tenant | undefined;
  currentUser: User | undefined;
  tenants: Tenant[];
  tenantQuery: string;
  tenantLoading: boolean;
  onTenantQueryChange: (value: string) => void;
  onSelectTenant: (tenant: Tenant) => Promise<boolean>;
  onCreateTenant: (name: string, description: string) => Promise<boolean>;
  onOpenWorkspaceSwitcher: () => void;
};

const GlobalHeader = styled.header`
  position: sticky;
  top: 0;
  z-index: ${({ theme }) => theme.zIndex.overlay};
  display: grid;
  grid-template-columns: minmax(320px, 1fr) minmax(260px, 520px) minmax(
      240px,
      1fr
    );
  min-height: 56px;
  align-items: center;
  gap: ${({ theme }) => theme.space[6]};
  padding: 0 ${({ theme }) => theme.space[8]};
  border-bottom: ${({ theme }) => theme.border.thin} solid
    ${({ theme }) => theme.color.border.subtle};
  background: ${({ theme }) => theme.color.background.surface};
  @media (max-width: 900px) {
    grid-template-columns: auto 1fr;
    gap: ${({ theme }) => theme.space[4]};
    padding: 0 ${({ theme }) => theme.space[5]};
  }
  @media (max-width: 560px) {
    padding: ${({ theme }) => theme.space[4]};
  }
`;

const HeaderLeft = styled.div`
  display: flex;
  min-width: 0;
  align-items: center;
  gap: ${({ theme }) => theme.space[5]};
`;

const Brand = styled.a`
  display: flex;
  width: 140px;
  align-items: center;
  white-space: nowrap;
  img {
    display: block;
    width: 100%;
    height: auto;
  }
`;

const WorkspaceSwitcher = styled.button`
  display: flex;
  min-width: 190px;
  min-height: 44px;
  align-items: center;
  justify-content: space-between;
  gap: ${({ theme }) => theme.space[2]};
  padding: 0 ${({ theme }) => theme.space[2]};
  border: 0;
  border-radius: ${({ theme }) => theme.radius.md};
  color: ${({ theme }) => theme.color.text.secondary};
  background: transparent;
  font-size: ${({ theme }) => theme.font.size.sm};
  font-weight: ${({ theme }) => theme.font.weight.semibold};
  text-align: left;
  transition:
    transform ${({ theme }) => theme.motion.fast}
      ${({ theme }) => theme.motion.ease},
    background ${({ theme }) => theme.motion.fast}
      ${({ theme }) => theme.motion.ease};
  span {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  &:hover {
    background: ${({ theme }) => theme.color.interactive.secondary};
  }
  @media (max-width: 700px) {
    width: 148px;
  }
  @media (max-width: 560px) {
    width: 122px;
  }
`;

const SearchBox = styled.label`
  display: flex;
  height: 42px;
  align-items: center;
  gap: ${({ theme }) => theme.space[2]};
  padding: 0 ${({ theme }) => theme.space[3]};
  border: ${({ theme }) => theme.border.thin} solid
    ${({ theme }) => theme.color.border.default};
  border-radius: ${({ theme }) => theme.radius.md};
  color: ${({ theme }) => theme.color.text.muted};
  background: ${({ theme }) => theme.color.background.canvas};
  transition:
    border-color ${({ theme }) => theme.motion.fast}
      ${({ theme }) => theme.motion.ease},
    box-shadow ${({ theme }) => theme.motion.fast}
      ${({ theme }) => theme.motion.ease};
  &:focus-within {
    border-color: ${({ theme }) => theme.color.border.focus};
    box-shadow: 0 0 0 3px ${({ theme }) => theme.color.brand[100]};
  }
  input {
    width: 100%;
    border: 0;
    outline: 0;
    color: ${({ theme }) => theme.color.text.primary};
    background: transparent;
    font-size: ${({ theme }) => theme.font.size.md};
    &::placeholder {
      color: ${({ theme }) => theme.color.text.muted};
    }
  }
  kbd {
    padding: 2px 6px;
    border: ${({ theme }) => theme.border.thin} solid
      ${({ theme }) => theme.color.border.default};
    border-radius: ${({ theme }) => theme.radius.sm};
    color: ${({ theme }) => theme.color.text.muted};
    background: ${({ theme }) => theme.color.background.surface};
    font-size: ${({ theme }) => theme.font.size.xs};
    white-space: nowrap;
  }
  @media (max-width: 900px) {
    grid-column: 1 / -1;
    grid-row: 2;
  }
`;

const HeaderActions = styled.div`
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: ${({ theme }) => theme.space[2]};
  @media (max-width: 560px) {
    gap: ${({ theme }) => theme.space[1]};
  }
`;

const ProfileMenu = styled.div`
  position: relative;
`;

const SettingsMenu = styled.div`
  position: relative;
`;

const Avatar = styled.button`
  display: grid;
  width: 34px;
  height: 34px;
  place-items: center;
  border: 0;
  border-radius: 50%;
  color: ${({ theme }) => theme.color.text.inverse};
  background: ${({ theme }) => theme.color.accent.violet};
  font-size: ${({ theme }) => theme.font.size.xs};
  font-weight: ${({ theme }) => theme.font.weight.bold};
  transition: transform ${({ theme }) => theme.motion.fast}
    ${({ theme }) => theme.motion.ease};
  &:hover {
    transform: translateY(-2px) scale(1.04);
  }
  &:active {
    transform: translateY(1px) scale(0.98);
  }
`;

export function WorkspaceHeader({
  activeWorkspace,
  activeTenant,
  currentUser,
  tenants,
  tenantQuery,
  tenantLoading,
  onTenantQueryChange,
  onSelectTenant,
  onCreateTenant,
  onOpenWorkspaceSwitcher,
}: WorkspaceHeaderProps) {
  const navigate = useNavigate();
  const { resolvedTheme } = useTheme();
  const [profileOpen, setProfileOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const profileMenuRef = useRef<HTMLDivElement>(null);
  const settingsMenuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!profileOpen) return undefined;
    const closeOnOutsideClick = (event: MouseEvent) => {
      if (!profileMenuRef.current?.contains(event.target as Node))
        setProfileOpen(false);
    };
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setProfileOpen(false);
    };
    document.addEventListener("mousedown", closeOnOutsideClick);
    document.addEventListener("keydown", closeOnEscape);
    return () => {
      document.removeEventListener("mousedown", closeOnOutsideClick);
      document.removeEventListener("keydown", closeOnEscape);
    };
  }, [profileOpen]);

  useEffect(() => {
    if (!settingsOpen) return undefined;
    const closeOnOutsideClick = (event: MouseEvent) => {
      if (!settingsMenuRef.current?.contains(event.target as Node)) {
        setSettingsOpen(false);
      }
    };
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setSettingsOpen(false);
    };
    document.addEventListener("mousedown", closeOnOutsideClick);
    document.addEventListener("keydown", closeOnEscape);
    return () => {
      document.removeEventListener("mousedown", closeOnOutsideClick);
      document.removeEventListener("keydown", closeOnEscape);
    };
  }, [settingsOpen]);

  const handleLogout = () => {
    clearAccessToken();
    setProfileOpen(false);
    toast.success("You have been logged out");
    navigate(routes.login);
  };

  const brandAsset =
    resolvedTheme === "dark" ? brandDarkAsset : brandLightAsset;
  const profileInitials = currentUser
    ? initialsFromEmail(currentUser.email) || "MW"
    : "MW";
  const profileName = currentUser
    ? displayNameFromEmail(currentUser.email)
    : "MetaWeave User";
  const profileEmail = currentUser?.email ?? "";

  return (
    <GlobalHeader>
      <HeaderLeft>
        <Brand href="/app" aria-label="MetaWeave">
          <img src={brandAsset} alt="MetaWeave" />
        </Brand>
        <WorkspaceSwitcher
          type="button"
          onClick={onOpenWorkspaceSwitcher}
          aria-label="Switch workspace"
        >
          <span>{activeWorkspace?.name ?? "Workspace"}</span>
          <ChevronDown size={16} aria-hidden="true" />
        </WorkspaceSwitcher>
      </HeaderLeft>
      <SearchBox>
        <Search size={17} aria-hidden="true" />
        <input
          aria-label="Search workspace"
          placeholder="Search workspace..."
        />
        <kbd>⌘ K</kbd>
      </SearchBox>
      <HeaderActions>
        <ThemeSwitcher />
        <Clickable type="button" title="Help" aria-label="Help">
          <CircleHelp size={18} />
        </Clickable>
        <Clickable
          type="button"
          title="Notifications"
          aria-label="Notifications"
        >
          <Bell size={18} />
        </Clickable>
        <SettingsMenu ref={settingsMenuRef}>
          <Clickable
            type="button"
            title="Settings"
            aria-label="Settings"
            aria-expanded={settingsOpen}
            aria-haspopup="menu"
            onClick={() => {
              setSettingsOpen((open) => !open);
              setProfileOpen(false);
            }}
          >
            <Settings size={18} />
          </Clickable>
          <SettingsDropdown
            open={settingsOpen}
            onSelect={(label) => {
              setSettingsOpen(false);
              toast.info(`${label} settings are coming soon`);
            }}
          />
        </SettingsMenu>
        <ProfileMenu ref={profileMenuRef}>
          <Avatar
            type="button"
            title="Account menu"
            aria-label="Account menu"
            aria-expanded={profileOpen}
            aria-haspopup="dialog"
            onClick={() => {
              setProfileOpen((open) => !open);
              setSettingsOpen(false);
            }}
          >
            {profileInitials}
          </Avatar>
          <ProfilePanel
            open={profileOpen}
            username={profileName}
            email={profileEmail}
            initials={profileInitials}
            activeTenant={activeTenant}
            tenants={tenants}
            tenantQuery={tenantQuery}
            tenantLoading={tenantLoading}
            onTenantQueryChange={onTenantQueryChange}
            onSelectTenant={onSelectTenant}
            onCreateTenant={onCreateTenant}
            onAccount={() => {
              setProfileOpen(false);
              toast.info("Account settings are coming soon");
            }}
            onLogout={handleLogout}
          />
        </ProfileMenu>
      </HeaderActions>
    </GlobalHeader>
  );
}
