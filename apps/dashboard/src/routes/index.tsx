import { createFileRoute, redirect } from "@tanstack/react-router";

import { ensureAuthSession } from "../lib/api";

export const Route = createFileRoute("/")({
  beforeLoad: async () => {
    throw redirect({ to: (await ensureAuthSession()) ? "/dashboard" : "/login" });
  },
});
