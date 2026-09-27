import styled from "styled-components";

export const AuthPanel = styled.section`
  display: grid;
  place-items: center;
  min-height: 100svh;
  padding: clamp(
    ${({ theme }) => theme.space[6]},
    5vw,
    ${({ theme }) => theme.space[16]}
  );
  background: ${({ theme }) => theme.color.background.surface};
  @media (max-width: 920px) {
    min-height: auto;
    padding: 34px 22px 46px;
  }
`;
export const AuthCard = styled.div`
  display: flex;
  align-items: center;
  width: min(100%, 540px);
  min-height: 430px;
`;
export const AuthContent = styled.div`
  width: 100%;
  max-width: 520px;
  animation: auth-enter ${({ theme }) => theme.motion.normal} ease both;
  @keyframes auth-enter {
    from {
      opacity: 0;
      transform: translateY(12px);
    }
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }
`;
export const AuthBrand = styled.div`
  display: none;
  color: ${({ theme }) => theme.color.text.primary};
  font-size: ${({ theme }) => theme.font.size.xl};
  font-weight: ${({ theme }) => theme.font.weight.heavy};
  @media (max-width: 920px) {
    display: block;
    margin-bottom: 35px;
  }
`;
export const Eyebrow = styled.p`
  margin: 0 0 8px;
  color: ${({ theme }) => theme.color.text.muted};
  font-size: ${({ theme }) => theme.font.size.md};
`;
export const Heading = styled.h2`
  margin: 0;
  color: ${({ theme }) => theme.color.text.primary};
  font-size: ${({ theme }) => theme.font.size["3xl"]};
  line-height: ${({ theme }) => theme.font.lineHeight.snug};
  letter-spacing: -1px;
`;
export const Copy = styled.p`
  margin: 11px 0 31px;
  color: ${({ theme }) => theme.color.text.secondary};
  font-size: ${({ theme }) => theme.font.size.md};
  line-height: ${({ theme }) => theme.font.lineHeight.relaxed};
`;
