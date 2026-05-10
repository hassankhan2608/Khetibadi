import { createFileRoute } from "@tanstack/react-router";

import { DashboardHomePage } from "../../pages/dashboard";

export const Route = createFileRoute("/dashboard/")({
  component: DashboardHomePage,
});
