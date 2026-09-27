import styled, { keyframes } from "styled-components";

const shimmer = keyframes`to { transform: translateX(240%); }`;
const appear = keyframes`from { opacity: 0; transform: translateY(12px); } to { opacity: 1; transform: translateY(0); }`;

export const AuthSkeleton = styled.div`
  display: grid;
  align-content: center;
  gap: ${({ theme }) => theme.space[3]};
  width: 100%;
  min-height: 330px;
  overflow: hidden;
  animation: ${appear} ${({ theme }) => theme.motion.normal} ease both;
  span {
    display: block;
    height: 14px;
    border-radius: ${({ theme }) => theme.radius.md};
    background: linear-gradient(
      90deg,
      ${({ theme }) => theme.color.border.subtle} 25%,
      ${({ theme }) => theme.color.background.surface} 50%,
      ${({ theme }) => theme.color.border.subtle} 75%
    );
    background-size: 200% 100%;
    animation: ${shimmer} 1.4s linear infinite;
  }
  span:nth-child(1) {
    width: 33%;
    height: 24px;
  }
  span:nth-child(2) {
    width: 62%;
    height: 12px;
    margin-bottom: ${({ theme }) => theme.space[4]};
  }
  span:nth-child(3),
  span:nth-child(4) {
    height: 49px;
    border: ${({ theme }) => theme.border.thin} solid
      ${({ theme }) => theme.color.border.subtle};
    border-radius: ${({ theme }) => theme.radius.md};
  }
  span:nth-child(5) {
    width: 86%;
    height: 12px;
    margin: ${({ theme }) => theme.space[1]} auto 0;
  }
`;
