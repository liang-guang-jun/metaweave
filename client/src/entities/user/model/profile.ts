export function displayNameFromEmail(email: string): string {
  const local = email.split("@")[0]?.trim() ?? "";
  if (!local) return email;
  return local
    .split(/[._-]+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

export function initialsFromEmail(email: string): string {
  const name = displayNameFromEmail(email);
  const parts = name.split(/\s+/).filter(Boolean);
  const first = parts[0] ?? "";
  if (!first) return "";
  if (parts.length === 1) return first.slice(0, 2).toUpperCase();
  return `${first.charAt(0)}${(parts[1] ?? "").charAt(0)}`.toUpperCase();
}
