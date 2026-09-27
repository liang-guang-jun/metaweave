import {
  Settings2,
  SlidersHorizontal,
  UserRound,
  UserRoundGroup,
  Users,
} from "lucide-react";
import { Fragment } from "react";
import styled from "styled-components";
// import { Separator } from "@/shared/ui/Separator";

type SettingsDropdownProps = {
  open: boolean;
  onSelect: (label: string) => void;
};

type SettingsItem = {
  label: string;
  icon: typeof Settings2;
};

const sections: Array<{ title: string; items: SettingsItem[] }> = [
  {
    title: "Workspace",
    items: [
      { label: "General", icon: SlidersHorizontal },
      { label: "Members", icon: Users },
    ],
  },
  {
    title: "Tenant",
    items: [
      { label: "General", icon: SlidersHorizontal },
      { label: "Members", icon: Users },
      { label: "Groups", icon: UserRoundGroup },
      // { label: "Service Principals", icon: KeyRound },
      // Do not need SP settings for now
    ],
  },
  {
    title: "Security",
    items: [{ label: "Accounts", icon: UserRound }],
  },
];

const Dropdown = styled.div<{ $open: boolean }>`
  position: absolute;
  top: calc(100% + ${({ theme }) => theme.space[3]});
  right: 0;
  z-index: ${({ theme }) => theme.zIndex.overlay + 1};
  width: 238px;
  padding: ${({ theme }) => theme.space[2]};
  border: ${({ theme }) => theme.border.thin} solid
    ${({ theme }) => theme.color.border.subtle};
  border-radius: ${({ theme }) => theme.radius.lg};
  background: ${({ theme }) => theme.color.background.elevated};
  box-shadow: ${({ theme }) => theme.shadow.lg};
  opacity: ${({ $open }) => ($open ? 1 : 0)};
  pointer-events: ${({ $open }) => ($open ? "auto" : "none")};
  transform: ${({ $open }) =>
    $open ? "translateY(0) scale(1)" : "translateY(-6px) scale(.98)"};
  transform-origin: top right;
  transition:
    opacity ${({ theme }) => theme.motion.fast}
      ${({ theme }) => theme.motion.ease},
    transform ${({ theme }) => theme.motion.fast}
      ${({ theme }) => theme.motion.ease};
`;

const SectionTitle = styled.h3`
  margin: ${({ theme }) => theme.space[2]} ${({ theme }) => theme.space[3]};
  color: ${({ theme }) => theme.color.text.muted};
  font-size: ${({ theme }) => theme.font.size.xs};
  font-weight: ${({ theme }) => theme.font.weight.semibold};
  letter-spacing: 0.08em;
  text-transform: uppercase;
`;

const Item = styled.button`
  display: flex;
  width: 100%;
  min-height: 38px;
  align-items: center;
  gap: ${({ theme }) => theme.space[3]};
  padding: 0 ${({ theme }) => theme.space[3]};
  border: 0;
  border-radius: ${({ theme }) => theme.radius.md};
  color: ${({ theme }) => theme.color.text.secondary};
  background: transparent;
  font-size: ${({ theme }) => theme.font.size.sm};
  font-weight: ${({ theme }) => theme.font.weight.medium};
  text-align: left;
  cursor: pointer;
  transition:
    color ${({ theme }) => theme.motion.fast}
      ${({ theme }) => theme.motion.ease},
    background ${({ theme }) => theme.motion.fast}
      ${({ theme }) => theme.motion.ease},
    transform ${({ theme }) => theme.motion.fast}
      ${({ theme }) => theme.motion.ease};

  svg {
    flex: 0 0 auto;
    color: ${({ theme }) => theme.color.text.muted};
    transition: transform ${({ theme }) => theme.motion.fast}
      ${({ theme }) => theme.motion.ease};
  }

  &:hover {
    color: ${({ theme }) => theme.color.text.primary};
    background: ${({ theme }) => theme.color.interactive.secondary};
    transform: translateX(2px);

    svg {
      transform: scale(1.08);
      color: ${({ theme }) => theme.color.text.brand};
    }
  }

  &:active {
    transform: translateX(2px) translateY(1px) scale(0.98);
  }
`;

export function SettingsDropdown({ open, onSelect }: SettingsDropdownProps) {
  return (
    <Dropdown
      $open={open}
      role="menu"
      aria-label="Settings"
      aria-hidden={!open}
    >
      {sections.map((section) => (
        <Fragment key={section.title}>
          {/* {index > 0 ? <Separator role="separator" /> : null} */}
          <section>
            <SectionTitle>{section.title}</SectionTitle>
            {section.items.map(({ label, icon: Icon }) => (
              <Item
                key={`${section.title}-${label}`}
                type="button"
                role="menuitem"
                onClick={() => onSelect(`${section.title} ${label}`)}
              >
                <Icon size={16} aria-hidden="true" />
                <span>{label}</span>
              </Item>
            ))}
          </section>
        </Fragment>
      ))}
    </Dropdown>
  );
}
