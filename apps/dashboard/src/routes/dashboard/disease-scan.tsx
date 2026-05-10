import { createFileRoute } from "@tanstack/react-router";

import { DiseaseScanPage } from "../../pages/dashboard";

export const Route = createFileRoute("/dashboard/disease-scan")({
  component: DiseaseScanPage,
});
