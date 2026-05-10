import { QueryClientProvider } from "@tanstack/react-query";
import { Outlet, createRootRoute } from "@tanstack/react-router";

import { queryClient } from "../lib/query-client";

export const Route = createRootRoute({
  component: () => (
    <QueryClientProvider client={queryClient}>
      <Outlet />
    </QueryClientProvider>
  ),
});
