import styled from "styled-components";

export const Brand = styled.div`
  color: ${({ theme }) => theme.color.auth.heroTitle};
  font-size: ${({ theme }) => theme.font.size.xl};
  font-weight: ${({ theme }) => theme.font.weight.heavy};
  letter-spacing: -0.5px;
`;
