import styled, { keyframes } from "styled-components";
import { Database, Network, Sparkles, Workflow } from "lucide-react";
import { Brand } from "@/shared/ui/Brand";
import { DataCanvas } from "./DataCanvas";

const enter = keyframes`from { opacity: 0; transform: translateY(12px); } to { opacity: 1; transform: translateY(0); }`;
const Banner = styled.section`
  position: relative;
  isolation: isolate;
  overflow: hidden;
  min-height: 100svh;
  padding: clamp(
    ${({ theme }) => theme.space[6]},
    3vw,
    ${({ theme }) => theme.space[12]}
  );
  color: ${({ theme }) => theme.color.text.inverse};
  background:
    radial-gradient(
      ellipse at 15% 5%,
      ${({ theme }) => theme.color.auth.bannerGlowPrimary} 0%,
      transparent 44%
    ),
    radial-gradient(
      ellipse at 87% 86%,
      ${({ theme }) => theme.color.auth.bannerGlowSecondary} 0%,
      transparent 48%
    ),
    ${({ theme }) => theme.color.auth.bannerBackground};
  &::before {
    position: absolute;
    z-index: -1;
    inset: 0;
    content: "";
    opacity: 0.36;
    background-image:
      linear-gradient(
        ${({ theme }) => theme.color.auth.bannerGrid} 1px,
        transparent 1px
      ),
      linear-gradient(
        90deg,
        ${({ theme }) => theme.color.auth.bannerGrid} 1px,
        transparent 1px
      );
    background-size: 44px 44px;
    mask-image: linear-gradient(to bottom, black, transparent 84%);
  }
  @media (max-width: 920px) {
    min-height: 480px;
    padding: 28px;
  }
  @media (max-width: 520px) {
    min-height: 436px;
  }
`;
const BannerCopy = styled.div`
  position: absolute;
  z-index: ${({ theme }) => theme.zIndex.content};
  top: clamp(130px, 18vh, 210px);
  left: clamp(24px, 4vw, 72px);
  max-width: 520px;
  animation: ${enter} 0.7s ease-out both;
  @media (max-width: 920px) {
    top: auto;
    bottom: 42px;
    left: 28px;
    right: 28px;
    max-width: 570px;
  }
  @media (max-height: 820px) and (min-width: 921px) {
    top: 112px;
    max-width: 480px;
  }
`;
const Label = styled.p`
  display: flex;
  align-items: center;
  gap: ${({ theme }) => theme.space[2]};
  margin: 0 0 19px;
  color: ${({ theme }) => theme.color.accent.cyan};
  font-size: ${({ theme }) => theme.font.size.xs};
  font-weight: ${({ theme }) => theme.font.weight.bold};
  letter-spacing: ${({ theme }) => theme.font.letterSpacing.wide};
  text-transform: uppercase;
`;
const HeroTitle = styled.h1`
  max-width: 540px;
  margin: 0;
  color: ${({ theme }) => theme.color.auth.heroTitle};
  font-size: ${({ theme }) => theme.font.size["4xl"]};
  font-weight: ${({ theme }) => theme.font.weight.heavy};
  line-height: ${({ theme }) => theme.font.lineHeight.tight};
  letter-spacing: ${({ theme }) => theme.font.letterSpacing.tight};
`;
const GradientText = styled.span`
  background: linear-gradient(100deg, #72ddff 0%, #b9b1ff 90%);
  background-clip: text;
  -webkit-background-clip: text;
  color: transparent;
`;
const HeroDescription = styled.p`
  max-width: 470px;
  margin: 18px 0 0;
  color: ${({ theme }) => theme.color.auth.heroDescription};
  font-size: ${({ theme }) => theme.font.size.lg};
  line-height: ${({ theme }) => theme.font.lineHeight.relaxed};
`;
const CapabilityList = styled.div`
  display: flex;
  flex-wrap: wrap;
  gap: ${({ theme }) => theme.space[2]};
  margin-top: 27px;
`;
const Capability = styled.span`
  display: flex;
  align-items: center;
  gap: ${({ theme }) => theme.space[1]};
  padding: 7px 10px;
  border: ${({ theme }) => theme.border.thin} solid
    ${({ theme }) => theme.color.auth.capabilityBorder};
  border-radius: ${({ theme }) => theme.radius.pill};
  color: ${({ theme }) => theme.color.auth.capabilityText};
  background: ${({ theme }) => theme.color.auth.capabilityBackground};
  font-size: ${({ theme }) => theme.font.size.xs};
  backdrop-filter: blur(8px);
`;

export function AuthBanner() {
  return (
    <Banner>
      <Brand>MetaWeave</Brand>
      <DataCanvas />
      <BannerCopy>
        <Label>
          <Sparkles size={14} />
          Unified data intelligence
        </Label>
        <HeroTitle>
          Where your data <GradientText>connects.</GradientText>
        </HeroTitle>
        <HeroDescription>
          Bring business meaning, metadata, models, and visual transformations
          together in one collaborative workspace.
        </HeroDescription>
        <CapabilityList>
          <Capability>
            <Database size={13} />
            Metadata
          </Capability>
          <Capability>
            <Network size={13} />
            Data modeling
          </Capability>
          <Capability>
            <Workflow size={13} />
            Visual ETL
          </Capability>
        </CapabilityList>
      </BannerCopy>
    </Banner>
  );
}
