import styled from "styled-components";

/** Shared icon interaction surface used by compact actions across the app. */
export const Clickable = styled.button`
  display: grid;
  width: 38px;
  height: 38px;
  place-items: center;
  border: 0;
  border-radius: ${({ theme }) => theme.radius.md};
  color: ${({ theme }) => theme.color.text.secondary};
  background: transparent;
  transition: transform ${({ theme }) => theme.motion.fast} ${({ theme }) => theme.motion.ease};

  svg {
    transition:
      transform ${({ theme }) => theme.motion.fast} ${({ theme }) => theme.motion.ease},
      filter ${({ theme }) => theme.motion.fast} ${({ theme }) => theme.motion.ease};
    filter: drop-shadow(0 2px 3px color-mix(in srgb, currentColor 18%, transparent));
  }

  &:hover {
    transform: translateY(-2px);

    svg {
      transform: scale(1.08);
      filter: drop-shadow(0 1px 1px color-mix(in srgb, currentColor 10%, transparent));
    }
  }

  &:active {
    transform: translateY(1px);

    svg {
      transform: scale(0.98);
      filter: drop-shadow(0 4px 5px color-mix(in srgb, currentColor 28%, transparent));
    }
  }
`;
