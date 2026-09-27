import { Building2, Check, Plus, Search, X } from "lucide-react";
import { useState } from "react";
import styled from "styled-components";
import type { Tenant } from "@/entities/tenant/model/types";
import { Backdrop } from "@/shared/ui/Backdrop";
import { Clickable } from "@/shared/ui/Clickable";

type TenantSwitcherModalProps = {
  open: boolean;
  activeTenantId: string;
  tenants: Tenant[];
  query: string;
  isSearching: boolean;
  inline?: boolean;
  hideClose?: boolean;
  onClose: () => void;
  onQueryChange: (value: string) => void;
  onSelect: (tenant: Tenant) => void;
  onCreateNew: () => void;
};

const Modal = styled.div`
  width: min(100%, 460px);
  height: min(360px, calc(100dvh - 32px));
  min-height: 0;
  display: flex;
  flex-direction: column;
  box-sizing: border-box;
  padding: ${({ theme }) => theme.space[6]};
  border: ${({ theme }) => theme.border.thin} solid
    ${({ theme }) => theme.color.border.subtle};
  border-radius: ${({ theme }) => theme.radius.lg};
  background: ${({ theme }) => theme.color.background.surface};
  box-shadow: ${({ theme }) => theme.shadow.lg};
`;

const InlineRoot = styled.div`
  display: grid;
  width: 100%;
  min-height: 100%;
  place-items: center;
  padding: ${({ theme }) => theme.space[6]};
`;

const ModalHeader = styled.div`
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: ${({ theme }) => theme.space[4]};
  h2 {
    margin: 0;
    color: ${({ theme }) => theme.color.text.primary};
    font-size: ${({ theme }) => theme.font.size.xl};
  }
  p {
    margin: ${({ theme }) => theme.space[2]} 0 0;
    color: ${({ theme }) => theme.color.text.muted};
    font-size: ${({ theme }) => theme.font.size.sm};
  }
`;

const SearchBox = styled.label`
  display: flex;
  min-height: 44px;
  align-items: center;
  gap: ${({ theme }) => theme.space[2]};
  margin-top: ${({ theme }) => theme.space[5]};
  padding: 0 ${({ theme }) => theme.space[3]};
  border: ${({ theme }) => theme.border.thin} solid
    ${({ theme }) => theme.color.border.default};
  border-radius: ${({ theme }) => theme.radius.md};
  color: ${({ theme }) => theme.color.text.muted};
  background: ${({ theme }) => theme.color.background.canvas};
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
  }
`;

const Suggestions = styled.div`
  min-height: 0;
  flex: 1 1 auto;
  display: flex;
  flex-direction: column;
  margin-top: ${({ theme }) => theme.space[2]};
  border: ${({ theme }) => theme.border.thin} solid
    ${({ theme }) => theme.color.border.subtle};
  border-radius: ${({ theme }) => theme.radius.md};
  background: ${({ theme }) => theme.color.background.elevated};
  overflow: hidden;
`;

const TenantItems = styled.div`
  min-height: 0;
  flex: 1 1 auto;
  overflow-y: auto;
  padding: ${({ theme }) => theme.space[1]};
  scrollbar-width: none;
  &::-webkit-scrollbar {
    display: none;
  }
`;

const CreateTenantArea = styled.div`
  flex: 0 0 auto;
  padding: ${({ theme }) => theme.space[1]};
  border-top: ${({ theme }) => theme.border.thin} solid
    ${({ theme }) => theme.color.border.subtle};
`;

const Suggestion = styled.button<{ $highlighted: boolean; $create?: boolean }>`
  display: flex;
  width: 100%;
  min-height: 42px;
  align-items: center;
  gap: ${({ theme }) => theme.space[3]};
  padding: 0 ${({ theme }) => theme.space[3]};
  border: 0;
  border-radius: ${({ theme }) => theme.radius.sm};
  color: ${({ theme, $create }) =>
    $create ? theme.color.text.brand : theme.color.text.primary};
  background: ${({ theme, $highlighted }) =>
    $highlighted ? theme.color.interactive.secondary : "transparent"};
  font-size: ${({ theme }) => theme.font.size.sm};
  font-weight: ${({ theme, $create }) =>
    $create ? theme.font.weight.semibold : theme.font.weight.regular};
  text-align: left;
  cursor: pointer;
  svg:last-child {
    margin-left: auto;
    color: ${({ theme }) => theme.color.text.muted};
  }
  &:hover {
    background: ${({ theme }) => theme.color.interactive.secondary};
  }
`;

const TenantSkeleton = styled.div`
  display: flex;
  min-height: 42px;
  align-items: center;
  gap: ${({ theme }) => theme.space[3]};
  padding: 0 ${({ theme }) => theme.space[3]};
`;

const TenantSkeletonIcon = styled.span`
  width: 17px;
  height: 17px;
  border-radius: ${({ theme }) => theme.radius.sm};
  background: ${({ theme }) => theme.color.border.subtle};
`;

const TenantSkeletonLine = styled.span<{ $short?: boolean }>`
  width: ${({ $short }) => ($short ? "48%" : "66%")};
  height: 12px;
  border-radius: ${({ theme }) => theme.radius.sm};
  background: linear-gradient(
    90deg,
    ${({ theme }) => theme.color.border.subtle} 25%,
    ${({ theme }) => theme.color.background.surface} 50%,
    ${({ theme }) => theme.color.border.subtle} 75%
  );
  background-size: 220% 100%;
  animation: tenant-shimmer 1.25s linear infinite;
  @keyframes tenant-shimmer {
    to {
      background-position: -220% 0;
    }
  }
`;

const EmptyState = styled.p`
  margin: ${({ theme }) => theme.space[5]} ${({ theme }) => theme.space[3]};
  color: ${({ theme }) => theme.color.text.muted};
  font-size: ${({ theme }) => theme.font.size.sm};
  text-align: center;
`;

export function TenantSwitcherModal({
  open,
  activeTenantId,
  tenants,
  query,
  isSearching,
  inline = false,
  hideClose = false,
  onClose,
  onQueryChange,
  onSelect,
  onCreateNew,
}: TenantSwitcherModalProps) {
  const [highlightedIndex, setHighlightedIndex] = useState(0);
  const optionCount = tenants.length + 1;
  const chooseHighlighted = () => {
    const selected = tenants[highlightedIndex];
    if (selected) onSelect(selected);
    else onCreateNew();
  };

  const content = (
    <Modal
      role="dialog"
      aria-modal="true"
      aria-labelledby="tenant-switcher-title"
      onClick={(event) => event.stopPropagation()}
    >
      <ModalHeader>
        <div>
          <h2 id="tenant-switcher-title">Switch tenant</h2>
          <p>Choose a tenant to continue.</p>
        </div>
        {!hideClose && (
          <Clickable
            type="button"
            onClick={onClose}
            aria-label="Close tenant switcher"
            title="Close tenant switcher"
          >
            <X size={18} />
          </Clickable>
        )}
      </ModalHeader>
      <SearchBox>
        <Search size={17} aria-hidden="true" />
        <input
          autoFocus={open}
          role="combobox"
          aria-expanded="true"
          aria-controls="tenant-suggestions"
          value={query}
          onChange={(event) => {
            setHighlightedIndex(0);
            onQueryChange(event.target.value);
          }}
          onKeyDown={(event) => {
            if (event.key === "ArrowDown") {
              event.preventDefault();
              setHighlightedIndex((index) => (index + 1) % optionCount);
            } else if (event.key === "ArrowUp") {
              event.preventDefault();
              setHighlightedIndex(
                (index) => (index - 1 + optionCount) % optionCount,
              );
            } else if (event.key === "Enter") {
              event.preventDefault();
              chooseHighlighted();
            } else if (event.key === "Escape" && !inline) onClose();
          }}
          placeholder="Search tenants..."
          aria-label="Search tenants"
        />
      </SearchBox>
      <Suggestions>
        <TenantItems
          id="tenant-suggestions"
          role="listbox"
          aria-label="Tenant suggestions"
        >
          {isSearching ? (
            <TenantSkeletonList />
          ) : tenants.length === 0 ? (
            <EmptyState>No tenants found</EmptyState>
          ) : (
            tenants.map((tenant, index) => (
              <Suggestion
                key={tenant.id}
                type="button"
                role="option"
                aria-selected={tenant.id === activeTenantId}
                $highlighted={highlightedIndex === index}
                onMouseEnter={() => setHighlightedIndex(index)}
                onClick={() => onSelect(tenant)}
              >
                <Building2 size={17} />
                <span>{tenant.name}</span>
                {tenant.id === activeTenantId && <Check size={16} />}
              </Suggestion>
            ))
          )}
        </TenantItems>
        <CreateTenantArea>
          <Suggestion
            type="button"
            role="option"
            $create
            $highlighted={highlightedIndex === tenants.length}
            onMouseEnter={() => setHighlightedIndex(tenants.length)}
            onClick={onCreateNew}
          >
            <Plus size={17} />
            <span>Create New Tenant</span>
          </Suggestion>
        </CreateTenantArea>
      </Suggestions>
    </Modal>
  );

  if (inline) return <InlineRoot>{content}</InlineRoot>;
  return (
    <Backdrop open={open} center onClick={onClose}>
      {content}
    </Backdrop>
  );
}

function TenantSkeletonList() {
  return (
    <>
      {Array.from({ length: 5 }, (_, index) => (
        <TenantSkeleton key={`tenant-skeleton-${index}`}>
          <TenantSkeletonIcon />
          <TenantSkeletonLine $short={index % 3 === 0} />
        </TenantSkeleton>
      ))}
    </>
  );
}
