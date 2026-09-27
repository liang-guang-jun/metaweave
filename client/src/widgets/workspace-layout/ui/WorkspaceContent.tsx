import type { PropsWithChildren } from "react";
import styled from "styled-components";

const Content = styled.main`
  display: flex;
  width: 100%;
  min-height: calc(100svh - 56px);
  flex-direction: column;
  color: ${({ theme }) => theme.color.text.primary};
`;

const EmptyState = styled.div`
  display: grid;
  flex: 1;
  place-content: center;
  gap: ${({ theme }) => theme.space[2]};
  padding: ${({ theme }) => theme.space[6]};
  text-align: center;
  h1 {
    margin: 0;
    color: ${({ theme }) => theme.color.text.primary};
    font-size: ${({ theme }) => theme.font.size.xl};
  }
  p {
    max-width: 420px;
    margin: 0;
    color: ${({ theme }) => theme.color.text.muted};
    font-size: ${({ theme }) => theme.font.size.md};
  }
`;

export function WorkspaceContent({ children }: PropsWithChildren) {
  return <Content>{children}</Content>;
}

export function WorkspaceEmptyState({ title, message }: { title: string; message: string }) {
  return (
    <EmptyState>
      <h1>{title}</h1>
      <p>{message}</p>
    </EmptyState>
  );
}
