import styled from "styled-components";

export const Field = styled.label<{ $index?: number }>`
  position: relative;
  display: block;
  margin-top: ${({ theme }) => theme.space[4]};
  color: ${({ theme }) => theme.color.text.primary};
  font-size: ${({ theme }) => theme.font.size.sm};
  font-weight: ${({ theme }) => theme.font.weight.regular};
  animation: field-enter ${({ theme }) => theme.motion.normal}
    ${({ $index = 0 }) => `${$index * 80}ms`} ease both;
  input {
    display: block;
    width: 100%;
    height: 54px;
    margin: 0;
    padding: ${({ theme }) => `0 ${theme.space[4]}`};
    border: ${({ theme }) => theme.border.thin} solid
      ${({ theme }) => theme.color.border.default};
    border-radius: ${({ theme }) => theme.radius.md};
    outline: 0;
    color: ${({ theme }) => theme.color.text.primary};
    background: ${({ theme }) => theme.color.background.surface};
    transition:
      border-color ${({ theme }) => theme.motion.fast}
        ${({ theme }) => theme.motion.ease},
      box-shadow ${({ theme }) => theme.motion.fast}
        ${({ theme }) => theme.motion.ease},
      background ${({ theme }) => theme.motion.fast}
        ${({ theme }) => theme.motion.ease};
    &::placeholder {
      color: transparent;
    }
    &:hover {
      border-color: ${({ theme }) => theme.color.border.focus};
    }
    &:focus {
      border-color: ${({ theme }) => theme.color.border.focus};
      box-shadow: 0 0 0 3px ${({ theme }) => theme.color.brand[100]};
    }
  }
  span {
    position: absolute;
    z-index: 1;
    top: 50%;
    left: ${({ theme }) => theme.space[4]};
    padding: 0 ${({ theme }) => theme.space[1]};
    color: ${({ theme }) => theme.color.text.muted};
    background: ${({ theme }) => theme.color.background.surface};
    font-size: ${({ theme }) => theme.font.size.md};
    font-weight: ${({ theme }) => theme.font.weight.medium};
    line-height: 1;
    pointer-events: none;
    transform: translateY(-50%);
    transform-origin: left center;
    transition:
      top ${({ theme }) => theme.motion.fast}
        ${({ theme }) => theme.motion.labelEase},
      transform ${({ theme }) => theme.motion.fast}
        ${({ theme }) => theme.motion.labelEase},
      color ${({ theme }) => theme.motion.fast}
        ${({ theme }) => theme.motion.labelEase},
      font-size ${({ theme }) => theme.motion.fast}
        ${({ theme }) => theme.motion.labelEase};
  }
  input:focus + span,
  input:not(:placeholder-shown) + span {
    top: 0;
    color: ${({ theme }) => theme.color.text.brand};
    font-size: ${({ theme }) => theme.font.size.xs};
    transform: translateY(-50%) scale(0.96);
  }
  @keyframes field-enter {
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
