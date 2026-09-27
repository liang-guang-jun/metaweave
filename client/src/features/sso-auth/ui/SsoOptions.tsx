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

function MicrosoftIcon() {
  return (
    <svg viewBox="0 0 23 23" aria-hidden="true" width="20" height="20">
      <path fill="#f35325" d="M1 1h10v10H1z" />
      <path fill="#81bc06" d="M12 1h10v10H12z" />
      <path fill="#05a6f0" d="M1 12h10v10H1z" />
      <path fill="#ffba08" d="M12 12h10v10H12z" />
    </svg>
  );
}

type SsoOptionsProps = { onContinue: () => void };

export function SsoOptions({ onContinue }: SsoOptionsProps) {
  return (
    <Options>
      <Separator>OR CONTINUE WITH</Separator>
      <ProviderButton type="button" onClick={onContinue}>
        <img
          className="keycloak"
          src="https://www.keycloak.org/resources/images/logo.svg"
          alt="Keycloak"
        />
        Continue with Keycloak
      </ProviderButton>
      <ProviderButton type="button" onClick={onContinue}>
        <MicrosoftIcon />
        Continue with Entra ID
      </ProviderButton>
    </Options>
  );
}
