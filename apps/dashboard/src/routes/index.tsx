import { createFileRoute, redirect } from "@tanstack/react-router";

import { isAuthenticated } from "../store/auth-store";

export const Route = createFileRoute("/")({
  beforeLoad: () => {
    throw redirect({ to: isAuthenticated() ? "/dashboard" : "/login" });
  },
});
