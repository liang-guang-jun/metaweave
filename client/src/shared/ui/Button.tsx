import styled from "styled-components";

export const PrimaryButton = styled.button`
  width: 100%;
  min-height: 49px;
  margin-top: ${({ theme }) => theme.space[6]};
  border: 0;
  border-radius: ${({ theme }) => theme.radius.md};
  color: ${({ theme }) => theme.color.text.inverse};
  background: ${({ theme }) => theme.color.interactive.primary};
  font-weight: ${({ theme }) => theme.font.weight.bold};
  box-shadow: ${({ theme }) => theme.shadow.md};
  transition:
    transform ${({ theme }) => theme.motion.fast}
      ${({ theme }) => theme.motion.ease},
    background ${({ theme }) => theme.motion.fast}
      ${({ theme }) => theme.motion.ease};
  &:hover {
    transform: translateY(-1px);
    background: ${({ theme }) => theme.color.interactive.primaryHover};
  }
  &:disabled {
    opacity: 0.65;
    cursor: wait;
  }
`;

export const ProviderButton = styled.button`
  display: flex;
  width: 100%;
  min-height: 49px;
  align-items: center;
  justify-content: center;
  gap: ${({ theme }) => theme.space[2]};
  margin-top: ${({ theme }) => theme.space[3]};
  border: ${({ theme }) => theme.border.thin} solid
    ${({ theme }) => theme.color.border.default};
  border-radius: ${({ theme }) => theme.radius.md};
  color: ${({ theme }) => theme.color.text.primary};
  background: ${({ theme }) => theme.color.background.surface};
  font-weight: ${({ theme }) => theme.font.weight.semibold};
  transition:
    transform ${({ theme }) => theme.motion.fast}
      ${({ theme }) => theme.motion.ease},
    background ${({ theme }) => theme.motion.fast}
      ${({ theme }) => theme.motion.ease};
  &:hover {
    transform: translateY(-1px);
    background: ${({ theme }) => theme.color.interactive.secondary};
  }
  img {
    width: 21px;
    height: 21px;
    object-fit: contain;
  }
  .keycloak {
    object-fit: cover;
    object-position: left;
  }
`;
