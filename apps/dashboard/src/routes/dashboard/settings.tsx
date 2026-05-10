import { createFileRoute } from "@tanstack/react-router";

import { SettingsPage } from "../../pages/dashboard";

export const Route = createFileRoute("/dashboard/settings")({
  component: SettingsPage,
});
