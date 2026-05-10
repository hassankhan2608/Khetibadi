import { Store, useStore } from "@tanstack/react-store";

import type { AuthSession, User } from "@khetibadi/types";

export interface AuthState {
  user: User | null;
  token: string | null;
}

export const authStore = new Store<AuthState>({
  user: null,
  token: null,
});

export function setAuth(session: AuthSession): void {
  authStore.setState(() => ({ user: session.user, token: session.access_token }));
}

export function clearAuth(): void {
  authStore.setState(() => ({ user: null, token: null }));
}

export function useAuthUser(): User | null {
  return useStore(authStore, (state) => state.user);
}

export function useAuthToken(): string | null {
  return useStore(authStore, (state) => state.token);
}

export function getAccessToken(): string | null {
  return authStore.state.token;
}

export function isAuthenticated(): boolean {
  return authStore.state.token !== null;
}
