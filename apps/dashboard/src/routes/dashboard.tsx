import { createFileRoute, redirect } from "@tanstack/react-router";

import { DashboardLayout } from "../components/layout";
import { ensureAuthSession } from "../lib/api";

export const Route = createFileRoute("/dashboard")({
  beforeLoad: async () => {
    if (!(await ensureAuthSession())) {
      throw redirect({ to: "/login" });
    }
  },
  component: DashboardLayout,
});
