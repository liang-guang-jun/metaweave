import { createGlobalStyle } from 'styled-components'

export const GlobalStyle = createGlobalStyle`
  * { box-sizing: border-box; }
  html { background: ${({ theme }) => theme.color.background.inverse}; }
  body { margin: 0; min-width: 320px; overflow-x: hidden; color: ${({ theme }) => theme.color.text.primary}; background: ${({ theme }) => theme.color.background.canvas}; font-family: ${({ theme }) => theme.font.family}; }
  button, input { font: inherit; }
  button { cursor: pointer; }
  a { color: inherit; text-decoration: none; }
  ::selection { color: ${({ theme }) => theme.color.text.inverse}; background: ${({ theme }) => theme.color.interactive.primary}; }
  :focus-visible { outline: 3px solid ${({ theme }) => theme.color.border.focus}; outline-offset: 2px; }
`
