import { createFileRoute } from "@tanstack/react-router";

import { FarmMapPage } from "../../pages/dashboard";

export const Route = createFileRoute("/dashboard/farm-map")({
  component: FarmMapPage,
});
