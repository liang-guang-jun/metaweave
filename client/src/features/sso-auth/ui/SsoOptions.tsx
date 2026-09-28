import styled from "styled-components";
import { ProviderButton } from "@/shared/ui/Button";

const Options = styled.div`
  animation: sso-enter ${({ theme }) => theme.motion.normal}
    ${({ theme }) => theme.motion.ease} both;
  @keyframes sso-enter {
    from {
      opacity: 0;
      transform: translateY(8px);
    }
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }
`;
const Separator = styled.div`
  display: flex;
  align-items: center;
  gap: ${({ theme }) => theme.space[3]};
  margin: ${({ theme }) => theme.space[6]} 0;
  color: ${({ theme }) => theme.color.text.muted};
  font-size: ${({ theme }) => theme.font.size.xs};
  &::before,
  &::after {
    content: "";
    height: 1px;
    flex: 1;
    background: ${({ theme }) => theme.color.border.subtle};
  }
`;

type SsoOptionsProps = { onContinue: () => void; disabled?: boolean };

export function SsoOptions({ onContinue, disabled }: SsoOptionsProps) {
  return (
    <Options>
      <Separator>OR CONTINUE WITH</Separator>
      <ProviderButton type="button" onClick={onContinue} disabled={disabled}>
        Continue with Databricks Apps
      </ProviderButton>
    </Options>
  );
}
