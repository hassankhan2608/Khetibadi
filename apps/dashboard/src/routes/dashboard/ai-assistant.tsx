import { createFileRoute } from "@tanstack/react-router";

import { AIAssistantPage } from "../../pages/dashboard";

export const Route = createFileRoute("/dashboard/ai-assistant")({
  component: AIAssistantPage,
});
