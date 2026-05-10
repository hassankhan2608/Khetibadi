import { createFileRoute } from "@tanstack/react-router";

import { MarketPricesPage } from "../../pages/dashboard";

export const Route = createFileRoute("/dashboard/market-prices")({
  component: MarketPricesPage,
});
