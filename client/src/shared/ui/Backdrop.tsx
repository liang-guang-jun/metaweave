import type { PropsWithChildren } from "react";
import styled from "styled-components";

type BackdropProps = PropsWithChildren<{
  open: boolean;
  center?: boolean;
  onClick?: () => void;
}>;

const BackdropRoot = styled.div<{ $open: boolean; $center: boolean }>`
  position: fixed;
  inset: 0;
  z-index: ${({ theme }) => theme.zIndex.overlay + 2};
  display: ${({ $center }) => ($center ? "grid" : "block")};
  place-items: ${({ $center }) => ($center ? "center" : "normal")};
  padding: ${({ $center, theme }) => ($center ? theme.space[5] : "0")};
  pointer-events: ${({ $open }) => ($open ? "auto" : "none")};
  background: ${({ $open }) => ($open ? "rgba(7, 19, 33, 0.32)" : "rgba(7, 19, 33, 0)")};
  backdrop-filter: blur(${({ $open }) => ($open ? "8px" : "0px")});
  opacity: ${({ $open }) => ($open ? 1 : 0)};
  transition: opacity ${({ theme }) => theme.motion.drawer} ${({ theme }) => theme.motion.ease}, background ${({ theme }) => theme.motion.drawer} ${({ theme }) => theme.motion.ease}, backdrop-filter ${({ theme }) => theme.motion.drawer} ${({ theme }) => theme.motion.ease};
`;

export function Backdrop({ open, center = false, onClick, children }: BackdropProps) {
  return <BackdropRoot $open={open} $center={center} onClick={onClick}>{children}</BackdropRoot>;
}
