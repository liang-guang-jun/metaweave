import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import styled from "styled-components";
import { AuthBanner } from "@/widgets/auth-banner/ui/AuthBanner";
import {
  AuthCard,
  AuthContent,
  AuthPanel,
  AuthBrand,
  Copy,
  Eyebrow,
  Heading,
} from "@/widgets/auth-panel/ui/AuthPanel";
import { EmailAuthForm } from "@/features/email-auth/ui/EmailAuthForm";
import { useServiceStatus } from "@/features/email-auth/model/queries";
import { SsoOptions } from "@/features/sso-auth/ui/SsoOptions";
import { AuthSkeleton } from "@/shared/ui/Skeleton";
import { routes } from "@/shared/config/routes";
import type { AuthPageMode } from "@/features/email-auth/model/types";
import { toast } from "sonner";

const AuthShell = styled.main`
  display: grid;
  min-height: 100svh;
  grid-template-columns: minmax(0, 1.16fr) minmax(430px, 0.84fr);
  background: ${({ theme }) => theme.color.background.surface};
  @media (max-width: 920px) {
    display: block;
    background: ${({ theme }) => theme.color.background.canvas};
  }
`;
const FooterNote = styled.p`
  margin: ${({ theme }) => theme.space[6]} 0 0;
  color: ${({ theme }) => theme.color.text.muted};
  text-align: center;
  font-size: ${({ theme }) => theme.font.size.sm};
  a {
    color: ${({ theme }) => theme.color.text.brand};
    font-weight: ${({ theme }) => theme.font.weight.semibold};
  }
`;

type AuthPageProps = { mode: AuthPageMode };

export function AuthPage({ mode }: AuthPageProps) {
  const navigate = useNavigate();
  const { tenantId } = useParams();
  const [booting, setBooting] = useState(true);
  const [switching, setSwitching] = useState(false);
  const isRegister = mode === "register";
  const { data: status } = useServiceStatus();
  const registrationEnabled = status?.register_enabled;

  useEffect(() => {
    const timer = window.setTimeout(() => setBooting(false), 520);
    return () => window.clearTimeout(timer);
  }, []);

  useEffect(() => {
    if (registrationEnabled === false && isRegister) {
      navigate(routes.login, { replace: true });
    }
  }, [registrationEnabled, isRegister, navigate]);

  const switchMode = (
    event: React.MouseEvent<HTMLAnchorElement>,
    destination: string,
  ) => {
    event.preventDefault();
    setSwitching(true);
    window.setTimeout(() => navigate(destination), 300);
  };

  const authSuccess = (completedMode: AuthPageMode) => {
    if (completedMode === "register") navigate(routes.login);
    else navigate(routes.workspace);
  };

  return (
    <AuthShell>
      <AuthBanner />
      <AuthPanel>
        <AuthCard>
          {booting || switching ? (
            <AuthSkeleton aria-label="Loading authentication">
              <span />
              <span />
              <span />
              <span />
              <span />
            </AuthSkeleton>
          ) : (
            <AuthContent key={mode}>
              <AuthBrand>MetaWeave</AuthBrand>
              <Eyebrow>
                {tenantId
                  ? `Signing in to ${tenantId}`
                  : "Use your email to continue"}
              </Eyebrow>
              <Heading>
                {isRegister ? "Create your account" : "Welcome back"}
              </Heading>
              <Copy>
                {isRegister
                  ? "Start weaving your team’s data context together."
                  : "Sign in to open your data workspace."}
              </Copy>
              <EmailAuthForm
                mode={mode}
                tenantId={tenantId}
                onSuccess={authSuccess}
              />
              {!isRegister && (
                <SsoOptions
                  onContinue={() =>
                    toast.info(
                      "SSO provider setup is required before this sign-in method can be used.",
                    )
                  }
                />
              )}
              <FooterNote>
                {isRegister ? (
                  <>
                    Already have an account?{" "}
                    <Link
                      to={routes.login}
                      onClick={(event) => switchMode(event, routes.login)}
                    >
                      Sign in
                    </Link>
                  </>
                ) : registrationEnabled ? (
                  <>
                    New to MetaWeave?{" "}
                    <Link
                      to={routes.register}
                      onClick={(event) => switchMode(event, routes.register)}
                    >
                      Create an account
                    </Link>
                  </>
                ) : null}
              </FooterNote>
            </AuthContent>
          )}
        </AuthCard>
      </AuthPanel>
    </AuthShell>
  );
}
