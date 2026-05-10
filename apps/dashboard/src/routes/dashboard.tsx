import { createFileRoute, redirect } from "@tanstack/react-router";

import { DashboardLayout } from "../components/layout";
import { isAuthenticated } from "../store/auth-store";

export const Route = createFileRoute("/dashboard")({
  beforeLoad: () => {
    if (!isAuthenticated()) {
      throw redirect({ to: "/login" });
    }
  },
  component: DashboardLayout,
});
