import styled from "styled-components";

/** Thin gray rule that divides stacked groups of content. */
export const Separator = styled.div`
  width: 100%;
  height: 1px;
  margin: ${({ theme }) => theme.space[2]} 0;
  background: ${({ theme }) => theme.color.border.default};
`;
