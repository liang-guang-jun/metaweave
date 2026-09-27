import { X } from "lucide-react";
import styled from "styled-components";
import { Backdrop } from "@/shared/ui/Backdrop";
import { Clickable } from "@/shared/ui/Clickable";

type TenantCreateModalProps = {
  open: boolean;
  name: string;
  description: string;
  onNameChange: (name: string) => void;
  onDescriptionChange: (description: string) => void;
  onClose: () => void;
  onCreate: () => void;
};

const Modal = styled.div`
  width: min(100%, 460px);
  padding: ${({ theme }) => theme.space[6]};
  border: ${({ theme }) => theme.border.thin} solid ${({ theme }) => theme.color.border.subtle};
  border-radius: ${({ theme }) => theme.radius.lg};
  background: ${({ theme }) => theme.color.background.surface};
  box-shadow: ${({ theme }) => theme.shadow.lg};
`;

const ModalHeader = styled.div`
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: ${({ theme }) => theme.space[4]};
  h2 { margin: 0; color: ${({ theme }) => theme.color.text.primary}; font-size: ${({ theme }) => theme.font.size.xl}; }
  p { margin: ${({ theme }) => theme.space[2]} 0 0; color: ${({ theme }) => theme.color.text.muted}; font-size: ${({ theme }) => theme.font.size.sm}; }
`;

const Field = styled.label`
  display: grid;
  gap: ${({ theme }) => theme.space[2]};
  margin-top: ${({ theme }) => theme.space[5]};
  color: ${({ theme }) => theme.color.text.secondary};
  font-size: ${({ theme }) => theme.font.size.sm};
  font-weight: ${({ theme }) => theme.font.weight.semibold};
  input, textarea { width: 100%; border: ${({ theme }) => theme.border.thin} solid ${({ theme }) => theme.color.border.default}; border-radius: ${({ theme }) => theme.radius.md}; outline: 0; padding: ${({ theme }) => theme.space[3]}; color: ${({ theme }) => theme.color.text.primary}; background: ${({ theme }) => theme.color.background.canvas}; font: inherit; font-weight: ${({ theme }) => theme.font.weight.regular}; resize: vertical; }
  input { min-height: 44px; }
  textarea { min-height: 112px; }
  input:focus, textarea:focus { border-color: ${({ theme }) => theme.color.border.focus}; box-shadow: 0 0 0 3px ${({ theme }) => theme.color.brand[100]}; }
`;

const ModalActions = styled.div`
  display: flex;
  justify-content: flex-end;
  gap: ${({ theme }) => theme.space[2]};
  margin-top: ${({ theme }) => theme.space[6]};
`;

const ActionButton = styled.button<{ $primary?: boolean }>`
  min-height: 40px;
  padding: 0 ${({ theme }) => theme.space[4]};
  border: ${({ theme }) => theme.border.thin} solid ${({ theme, $primary }) => ($primary ? "transparent" : theme.color.border.default)};
  border-radius: ${({ theme }) => theme.radius.md};
  color: ${({ theme, $primary }) => ($primary ? theme.color.text.inverse : theme.color.text.secondary)};
  background: ${({ theme, $primary }) => ($primary ? theme.color.interactive.primary : "transparent")};
  font-weight: ${({ theme }) => theme.font.weight.semibold};
  &:hover { background: ${({ theme, $primary }) => ($primary ? theme.color.interactive.primaryHover : theme.color.interactive.secondary)}; }
`;

export function TenantCreateModal({ open, name, description, onNameChange, onDescriptionChange, onClose, onCreate }: TenantCreateModalProps) {
  return (
    <Backdrop open={open} center onClick={onClose}>
      <Modal role="dialog" aria-modal="true" aria-labelledby="create-tenant-title" onClick={(event) => event.stopPropagation()}>
        <ModalHeader><div><h2 id="create-tenant-title">Create tenant</h2><p>Add a tenant and optionally describe its purpose.</p></div><Clickable type="button" onClick={onClose} aria-label="Close create tenant modal" title="Close"><X size={18} /></Clickable></ModalHeader>
        <Field><span>Tenant name</span><input autoFocus={open} value={name} onChange={(event) => onNameChange(event.target.value)} placeholder="e.g. Acme" /></Field>
        <Field><span>Description <em>(optional)</em></span><textarea value={description} onChange={(event) => onDescriptionChange(event.target.value)} placeholder="Describe this tenant" /></Field>
        <ModalActions><ActionButton type="button" onClick={onClose}>Cancel</ActionButton><ActionButton type="button" $primary onClick={onCreate}>Create tenant</ActionButton></ModalActions>
      </Modal>
    </Backdrop>
  );
}
