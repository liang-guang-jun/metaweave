import styled, { keyframes } from "styled-components";
import { useTheme } from "@/shared/theme/useTheme";
import { themes } from "@/shared/theme/themes";

const flow = keyframes`to { stroke-dashoffset: 0; }`;
const Canvas = styled.svg`
  position: absolute;
  z-index: ${({ theme }) => theme.zIndex.content};
  right: clamp(-74px, 1vw, -12px);
  bottom: 22px;
  width: min(53vw, 620px);
  height: auto;
  overflow: hidden;
  opacity: 0.84;
  .line {
    fill: none;
    stroke: ${({ theme }) => theme.color.auth.nodeLine};
    stroke-width: 1.25;
    stroke-dasharray: 4 7;
    stroke-dashoffset: 58;
    animation: ${flow} 2.5s linear infinite;
  }
  .violet {
    stroke: ${({ theme }) => theme.color.auth.nodeLineSecondary};
    animation-duration: 3.8s;
  }
  .node {
    transform: none;
  }
  .delay,
  .late {
    animation: none;
  }
  @media (max-width: 920px) {
    right: -104px;
    bottom: -40px;
    width: 580px;
    opacity: 0.7;
  }
  @media (max-width: 520px) {
    width: 530px;
    right: -180px;
    bottom: -30px;
  }
`;

export function DataCanvas() {
  const { resolvedTheme } = useTheme();
  const { color } = themes[resolvedTheme];
  const nodeFill = "url(#nodeFill)";
  const text = color.auth.nodeText;
  const muted = color.neutral[400];
  const border = color.auth.nodeBorder;
  const accent = color.auth.nodeAccent;
  const accentAlt = color.auth.nodeAccentAlt;

  return (
    <Canvas viewBox="0 0 760 430" aria-hidden="true">
      <defs>
        <linearGradient id="nodeFill">
          <stop stopColor={color.auth.nodeBackground} />
          <stop offset="1" stopColor={color.auth.nodeBackgroundEnd} />
        </linearGradient>
        <marker
          id="mappingArrow"
          markerWidth="5"
          markerHeight="5"
          refX="4"
          refY="2.5"
          orient="auto"
        >
          <path d="M0 0L5 2.5L0 5Z" fill={accent} />
        </marker>
      </defs>

      <path
        className="line"
        d="M103 122C211 96 244 159 329 180s126-31 194-81"
      />
      <path
        className="line violet"
        d="M103 122c63 69 138 137 227 133s145 55 261 19"
      />
      <path className="line" d="M329 180c61 38 116 89 262 94" />
      <path className="line violet" d="M470 81C382 38 254 52 166 122" />
      <path className="line violet" d="M548 118C584 151 604 176 596 222" />

      <g className="node source-node">
        <rect
          x="36"
          y="56"
          width="150"
          height="136"
          rx="14"
          fill={nodeFill}
          stroke={border}
          strokeOpacity=".7"
        />
        <circle cx="58" cy="78" r="10" fill={accent} />
        <text
          x="77"
          y="82"
          fill={text}
          fontSize="11"
          fontWeight="700"
          fontFamily="sans-serif"
        >
          Source
        </text>
        <g transform="translate(49 98)">
          <rect
            width="124"
            height="22"
            rx="5"
            fill="#0a2035"
            stroke={border}
            strokeOpacity=".55"
          />
          <ellipse cx="12" cy="7" rx="5" ry="2.5" fill={accent} />
          <path
            d="M7 7v7c0 3 10 3 10 0V7"
            fill="none"
            stroke={accent}
            strokeWidth="1.2"
          />
          <text x="25" y="11" fill={text} fontSize="8" fontFamily="sans-serif">
            customer
          </text>
          <text x="25" y="18" fill={muted} fontSize="6" fontFamily="sans-serif">
            12 columns
          </text>
        </g>
        <g transform="translate(49 124)">
          <rect
            width="124"
            height="22"
            rx="5"
            fill="#0a2035"
            stroke={border}
            strokeOpacity=".55"
          />
          <ellipse cx="12" cy="7" rx="5" ry="2.5" fill={accent} />
          <path
            d="M7 7v7c0 3 10 3 10 0V7"
            fill="none"
            stroke={accent}
            strokeWidth="1.2"
          />
          <text x="25" y="11" fill={text} fontSize="8" fontFamily="sans-serif">
            orders
          </text>
          <text x="25" y="18" fill={muted} fontSize="6" fontFamily="sans-serif">
            8 columns
          </text>
        </g>
        <g transform="translate(49 150)">
          <rect
            width="124"
            height="22"
            rx="5"
            fill="#0a2035"
            stroke={border}
            strokeOpacity=".55"
          />
          <ellipse cx="12" cy="7" rx="5" ry="2.5" fill={accent} />
          <path
            d="M7 7v7c0 3 10 3 10 0V7"
            fill="none"
            stroke={accent}
            strokeWidth="1.2"
          />
          <text x="25" y="11" fill={text} fontSize="8" fontFamily="sans-serif">
            products
          </text>
          <text x="25" y="18" fill={muted} fontSize="6" fontFamily="sans-serif">
            6 columns
          </text>
        </g>
      </g>

      <g className="node delay model-node">
        <rect
          x="255"
          y="128"
          width="150"
          height="128"
          rx="14"
          fill={nodeFill}
          stroke={color.auth.nodeBorderAccent}
          strokeOpacity=".75"
        />
        <circle cx="278" cy="150" r="10" fill={accentAlt} />
        <text
          x="297"
          y="154"
          fill={text}
          fontSize="11"
          fontWeight="700"
          fontFamily="sans-serif"
        >
          Model
        </text>
        <g stroke={color.auth.nodeBorderAccent} strokeWidth="1" fill="#142a50">
          <rect x="270" y="175" width="50" height="34" rx="5" />
          <rect x="340" y="175" width="50" height="34" rx="5" />
        </g>
        <g fill={text} fontSize="7" fontFamily="sans-serif">
          <text x="278" y="187">
            Customer
          </text>
          <text x="278" y="198" fill={muted}>
            id · name
          </text>
          <text x="348" y="187">
            Order
          </text>
          <text x="348" y="198" fill={muted}>
            id · total
          </text>
        </g>
        <path d="M320 192h20" stroke={accentAlt} strokeWidth="1.5" />
        <circle cx="330" cy="192" r="2.5" fill={accentAlt} />
        <path d="M270 224h120" stroke={muted} strokeOpacity=".7" />
        <text x="270" y="243" fill={muted} fontSize="7" fontFamily="sans-serif">
          1 relationship · 2 entities
        </text>
      </g>

      <g className="node late mapping-node">
        <rect
          x="520"
          y="210"
          width="162"
          height="132"
          rx="14"
          fill={nodeFill}
          stroke={border}
          strokeOpacity=".7"
        />
        <circle cx="543" cy="232" r="10" fill={accent} />
        <text
          x="562"
          y="236"
          fill={text}
          fontSize="11"
          fontWeight="700"
          fontFamily="sans-serif"
        >
          Mapping
        </text>
        <g transform="translate(538 253)">
          <rect
            width="38"
            height="24"
            rx="5"
            fill="#0a2035"
            stroke={border}
            strokeOpacity=".55"
          />
          <text x="9" y="15" fill={text} fontSize="7" fontFamily="sans-serif">
            input
          </text>
          <path
            d="M42 12h14"
            stroke={accent}
            strokeWidth="1.3"
            markerEnd="url(#mappingArrow)"
          />
          <rect
            x="60"
            width="43"
            height="24"
            rx="5"
            fill="#142a50"
            stroke={accentAlt}
            strokeOpacity=".8"
          />
          <text x="68" y="15" fill={text} fontSize="7" fontFamily="sans-serif">
            filter
          </text>
          <path
            d="M107 12h12"
            stroke={accent}
            strokeWidth="1.3"
            markerEnd="url(#mappingArrow)"
          />
          <rect
            x="124"
            width="30"
            height="24"
            rx="5"
            fill="#0a2035"
            stroke={border}
            strokeOpacity=".55"
          />
          <text x="130" y="15" fill={text} fontSize="7" fontFamily="sans-serif">
            out
          </text>
        </g>
        <path d="M538 292h142" stroke={muted} strokeOpacity=".7" />
        <text x="538" y="313" fill={muted} fontSize="7" fontFamily="sans-serif">
          Filter → Calculate → Select
        </text>
      </g>

      <g className="node term-node">
        <rect
          x="450"
          y="28"
          width="146"
          height="112"
          rx="14"
          fill={nodeFill}
          stroke={border}
          strokeOpacity=".7"
        />
        <circle cx="473" cy="50" r="10" fill={accent} />
        <text
          x="492"
          y="54"
          fill={text}
          fontSize="11"
          fontWeight="700"
          fontFamily="sans-serif"
        >
          Term
        </text>
        <g fill={text} fontSize="8" fontFamily="sans-serif">
          <text x="470" y="77">
            ⌄ Customer
          </text>
          <text x="484" y="94" fill={muted}>
            ▸ Customer ID
          </text>
          <text x="484" y="109" fill={muted}>
            ▸ Customer Type
          </text>
          <text x="484" y="124" fill={muted}>
            ▸ Customer Status
          </text>
        </g>
        <circle
          cx="562"
          cy="75"
          r="4"
          fill="none"
          stroke={accentAlt}
          strokeWidth="1.2"
        />
        <path d="M562 71v8M558 75h8" stroke={accentAlt} strokeWidth="1" />
      </g>
    </Canvas>
  );
}
