import { createFileRoute } from "@tanstack/react-router";

import { CropAdvisorPage } from "../../pages/dashboard";

export const Route = createFileRoute("/dashboard/crop-advisor")({
  component: CropAdvisorPage,
});
