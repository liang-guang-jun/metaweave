import { api } from "@/shared/api/client";
import type { User } from "./types";

type CurrentUserResponse = {
  user_id: string;
  email: string;
  active: boolean;
};

export async function getCurrentUser(): Promise<User> {
  const response = await api.get<CurrentUserResponse>("/iam/me");
  return {
    id: response.data.user_id,
    email: response.data.email,
    active: response.data.active,
  };
}
