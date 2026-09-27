import { Pin, Plus, Search, X } from "lucide-react";
import type { RefObject, UIEvent } from "react";
import styled from "styled-components";
import type { Workspace } from "@/entities/workspace/model/types";
import { Backdrop } from "@/shared/ui/Backdrop";
import { Clickable } from "@/shared/ui/Clickable";

type WorkspaceDrawerProps = {
  open: boolean;
  query: string;
  isSearching: boolean;
  isLoadingMore: boolean;
  pinned: Workspace[];
  unpinned: Workspace[];
  filteredCount: number;
  loadChunk: number;
  listRef: RefObject<HTMLDivElement | null>;
  onClose: () => void;
  onCreate: () => void;
  onQueryChange: (value: string) => void;
  onScroll: (event: UIEvent<HTMLDivElement>) => void;
  onSelect: (workspace: Workspace) => void;
  onTogglePin: (workspaceId: string) => void;
};

const Drawer = styled.aside<{ $open: boolean }>`
  display: flex;
  position: absolute;
  top: 0;
  bottom: 0;
  left: 0;
  width: min(390px, calc(100vw - 32px));
  flex-direction: column;
  border-right: ${({ theme }) => theme.border.thin} solid
    ${({ theme }) => theme.color.border.subtle};
  background: ${({ theme }) => theme.color.background.surface};
  box-shadow: ${({ theme }) => theme.shadow.lg};
  transform: translateX(${({ $open }) => ($open ? "0" : "-100%")});
  transition: transform ${({ theme }) => theme.motion.drawer}
    ${({ theme }) => theme.motion.ease};
`;

const DrawerHeader = styled.div`
  display: flex;
  min-height: 76px;
  align-items: center;
  justify-content: space-between;
  padding: 0 ${({ theme }) => theme.space[6]};
  border-bottom: ${({ theme }) => theme.border.thin} solid
    ${({ theme }) => theme.color.border.subtle};
  h2 {
    margin: 0;
    color: ${({ theme }) => theme.color.text.primary};
    font-size: ${({ theme }) => theme.font.size.lg};
  }
`;

const DrawerContent = styled.div`
  display: flex;
  min-height: 0;
  flex: 1;
  flex-direction: column;
  padding: ${({ theme }) => theme.space[5]} ${({ theme }) => theme.space[4]};
`;

const DrawerSearch = styled.label`
  display: flex;
  min-height: 42px;
  align-items: center;
  gap: ${({ theme }) => theme.space[2]};
  padding: 0 ${({ theme }) => theme.space[3]};
  border: ${({ theme }) => theme.border.thin} solid
    ${({ theme }) => theme.color.border.default};
  border-radius: ${({ theme }) => theme.radius.md};
  color: ${({ theme }) => theme.color.text.muted};
  background: ${({ theme }) => theme.color.background.canvas};
  &:focus-within {
    border-color: ${({ theme }) => theme.color.border.focus};
  }
  input {
    width: 100%;
    border: 0;
    outline: 0;
    color: ${({ theme }) => theme.color.text.primary};
    background: transparent;
    font-size: ${({ theme }) => theme.font.size.md};
  }
`;

const SearchTools = styled.div`
  display: flex;
  align-items: center;
  gap: ${({ theme }) => theme.space[2]};
  & > label {
    min-width: 0;
    flex: 1;
  }
`;

const WorkspaceSections = styled.div`
  display: flex;
  min-height: 0;
  flex: 1;
  flex-direction: column;
  margin-top: ${({ theme }) => theme.space[4]};
`;

const WorkspaceList = styled.div`
  min-height: 0;
  overflow-y: auto;
  scrollbar-width: none;
  &::-webkit-scrollbar {
    display: none;
  }
`;

const PinnedList = styled(WorkspaceList)`
  flex: 0 1 auto;
  max-height: 60%;
`;

const UnpinnedList = styled(WorkspaceList)`
  min-height: 40%;
  flex: 1 1 40%;
`;

const WorkspacePage = styled.div`
  animation: workspace-page-in ${({ theme }) => theme.motion.fast}
    ${({ theme }) => theme.motion.ease};
  @keyframes workspace-page-in {
    from {
      opacity: 0;
      transform: translateX(8px);
    }
    to {
      opacity: 1;
      transform: translateX(0);
    }
  }
`;

const WorkspaceItem = styled.div`
  display: flex;
  width: 100%;
  min-height: 48px;
  align-items: center;
  font-size: 0.9rem;
  justify-content: space-between;
  gap: ${({ theme }) => theme.space[3]};
  padding: 0 ${({ theme }) => theme.space[2]};
  border: 0;
  border-radius: ${({ theme }) => theme.radius.md};
  color: ${({ theme }) => theme.color.text.primary};
  background: transparent;
  cursor: pointer;
  text-align: left;
  transition: background ${({ theme }) => theme.motion.fast}
    ${({ theme }) => theme.motion.ease};
  span {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  &:hover {
    background: ${({ theme }) => theme.color.interactive.secondary};
  }
  &:hover > button {
    opacity: 1;
    pointer-events: auto;
  }
`;

const PinButton = styled(Clickable)<{ $visible: boolean; $pinned: boolean }>`
  width: 30px;
  height: 30px;
  flex: 0 0 30px;
  color: ${({ theme, $pinned }) =>
    $pinned ? theme.color.text.brand : theme.color.text.muted};
  opacity: ${({ $visible, $pinned }) => ($visible || $pinned ? 1 : 0)};
  pointer-events: ${({ $visible, $pinned }) =>
    $visible || $pinned ? "auto" : "none"};
  transform: ${({ $pinned }) => ($pinned ? "rotate(0deg)" : "rotate(45deg)")};
  transition:
    transform ${({ theme }) => theme.motion.fast}
      ${({ theme }) => theme.motion.labelEase},
    filter ${({ theme }) => theme.motion.fast}
      ${({ theme }) => theme.motion.ease};
  &:hover {
    transform: translateY(-2px) rotate(0deg);
    svg {
      transform: scale(1.04);
    }
  }
  &:active {
    transform: translateY(2px) rotate(0deg) scale(0.92);
    filter: drop-shadow(
      0 5px 6px color-mix(in srgb, currentColor 32%, transparent)
    );
    svg {
      transform: scale(0.94);
      filter: drop-shadow(
        0 4px 5px color-mix(in srgb, currentColor 32%, transparent)
      );
    }
  }
`;

const Separator = styled.div`
  height: 1px;
  flex: 0 0 1px;
  margin: ${({ theme }) => theme.space[3]} ${({ theme }) => theme.space[3]};
  background: ${({ theme }) => theme.color.border.subtle};
`;

const WorkspaceSkeleton = styled.div`
  display: flex;
  min-height: 48px;
  align-items: center;
  justify-content: space-between;
  gap: ${({ theme }) => theme.space[3]};
  padding: 0 ${({ theme }) => theme.space[3]};
  animation: workspace-skeleton-in ${({ theme }) => theme.motion.fast} ease both;
  @keyframes workspace-skeleton-in {
    from {
      opacity: 0;
      transform: translateY(4px);
    }
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }
`;

const SkeletonLine = styled.span<{ $short?: boolean }>`
  display: block;
  width: ${({ $short }) => ($short ? "58%" : "78%")};
  height: 13px;
  overflow: hidden;
  border-radius: ${({ theme }) => theme.radius.sm};
  background: linear-gradient(
    90deg,
    ${({ theme }) => theme.color.border.subtle} 25%,
    ${({ theme }) => theme.color.background.elevated} 50%,
    ${({ theme }) => theme.color.border.subtle} 75%
  );
  background-size: 220% 100%;
  animation: workspace-shimmer 1.3s linear infinite;
  @keyframes workspace-shimmer {
    to {
      background-position: -220% 0;
    }
  }
`;

const SkeletonPin = styled.span`
  width: 30px;
  height: 30px;
  border-radius: ${({ theme }) => theme.radius.md};
  background: ${({ theme }) => theme.color.border.subtle};
`;

const EmptyStateText = styled.p`
  margin: ${({ theme }) => theme.space[6]} ${({ theme }) => theme.space[3]};
  color: ${({ theme }) => theme.color.text.muted};
  font-size: ${({ theme }) => theme.font.size.sm};
  text-align: center;
`;

export function WorkspaceDrawer({
  open,
  query,
  isSearching,
  isLoadingMore,
  pinned,
  unpinned,
  filteredCount,
  loadChunk,
  listRef,
  onClose,
  onCreate,
  onQueryChange,
  onScroll,
  onSelect,
  onTogglePin,
}: WorkspaceDrawerProps) {
  return (
    <Backdrop open={open} onClick={onClose}>
      <Drawer
        $open={open}
        onClick={(event) => event.stopPropagation()}
        aria-label="Workspace switcher"
      >
        <DrawerHeader>
          <h2>Workspaces</h2>
          <Clickable
            type="button"
            onClick={onClose}
            aria-label="Close workspace switcher"
          >
            <X size={18} />
          </Clickable>
        </DrawerHeader>
        <DrawerContent>
          <SearchTools>
            <DrawerSearch>
              <Search size={16} aria-hidden="true" />
              <input
                autoFocus={open}
                value={query}
                onChange={(event) => onQueryChange(event.target.value)}
                placeholder="Search workspaces..."
                aria-label="Search workspaces"
              />
            </DrawerSearch>
            <Clickable
              type="button"
              onClick={onCreate}
              title="Create new workspace"
              aria-label="Create new workspace"
            >
              <Plus size={19} />
            </Clickable>
          </SearchTools>
          {isSearching ? (
            <WorkspaceSections>
              <UnpinnedList>
                <WorkspaceSkeletonList count={loadChunk} />
              </UnpinnedList>
            </WorkspaceSections>
          ) : (
            <WorkspaceSections>
              {pinned.length > 0 && (
                <PinnedList>
                  <WorkspacePage>
                    {pinned.map((workspace) => (
                      <WorkspaceRow
                        key={workspace.id}
                        workspace={workspace}
                        onSelect={onSelect}
                        onTogglePin={onTogglePin}
                      />
                    ))}
                  </WorkspacePage>
                </PinnedList>
              )}
              {pinned.length > 0 && unpinned.length > 0 && <Separator />}
              <UnpinnedList ref={listRef} onScroll={onScroll}>
                <WorkspacePage>
                  {unpinned.map((workspace) => (
                    <WorkspaceRow
                      key={workspace.id}
                      workspace={workspace}
                      onSelect={onSelect}
                      onTogglePin={onTogglePin}
                    />
                  ))}
                  {filteredCount === 0 && (
                    <EmptyStateText>No workspaces found</EmptyStateText>
                  )}
                  {isLoadingMore && <WorkspaceSkeletonList count={2} />}
                </WorkspacePage>
              </UnpinnedList>
            </WorkspaceSections>
          )}
        </DrawerContent>
      </Drawer>
    </Backdrop>
  );
}

function WorkspaceRow({
  workspace,
  onSelect,
  onTogglePin,
}: {
  workspace: Workspace;
  onSelect: (workspace: Workspace) => void;
  onTogglePin: (workspaceId: string) => void;
}) {
  return (
    <WorkspaceItem
      role="button"
      tabIndex={0}
      onClick={() => onSelect(workspace)}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          onSelect(workspace);
        }
      }}
    >
      <span>{workspace.name}</span>
      <PinButton
        type="button"
        $visible={workspace.pinned}
        $pinned={workspace.pinned}
        onClick={(event) => {
          event.stopPropagation();
          onTogglePin(workspace.id);
        }}
        aria-label={
          workspace.pinned ? `Unpin ${workspace.name}` : `Pin ${workspace.name}`
        }
        title={workspace.pinned ? "Unpin workspace" : "Pin workspace"}
      >
        <Pin size={16} />
      </PinButton>
    </WorkspaceItem>
  );
}

function WorkspaceSkeletonList({ count }: { count: number }) {
  return (
    <>
      {Array.from({ length: count }, (_, index) => (
        <WorkspaceSkeleton key={`workspace-skeleton-${index}`}>
          <SkeletonLine $short={index % 3 === 0} />
          <SkeletonPin />
        </WorkspaceSkeleton>
      ))}
    </>
  );
}
