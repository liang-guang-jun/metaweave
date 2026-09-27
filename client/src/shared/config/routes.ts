export const routes = {
  login: '/login',
  register: '/register',
  tenantPattern: '/tenant/:tenantId',
  tenant: (tenantId: string) => `/tenant/${tenantId}`,
  workspace: '/app',
} as const
