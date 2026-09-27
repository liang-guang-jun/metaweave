import type { Tenant } from "./types";

export const initialTenants: Tenant[] = [
  { id: "acme", name: "Acme", description: "Primary Acme workspace tenant" },
  { id: "northstar-labs", name: "Northstar Labs", description: "Analytics and experimentation tenant" },
  { id: "contoso-data", name: "Contoso Data", description: "Enterprise data operations tenant" },
  { id: "platform-demo", name: "Platform Demo", description: "Product demonstration tenant" },
  { id: "research", name: "Research Collective", description: "Research and discovery tenant" },
  { id: "field-ops", name: "Field Operations", description: "Regional field operations tenant" },
  { id: "customer-success", name: "Customer Success", description: "Customer success programs tenant" },
  { id: "data-foundation", name: "Data Foundation", description: "Shared metadata foundation tenant" },
];

export const tenantsPerPage = 5;
