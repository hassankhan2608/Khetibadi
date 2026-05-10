import { Link, Outlet, useRouter } from "@tanstack/react-router";
import { Bot, ChartLine, Leaf, LogOut, Map, ScanLine, Settings, Sprout } from "lucide-react";

import { Button } from "@khetibadi/ui";

import { authApi } from "../lib/api";
import { queryClient } from "../lib/query-client";
import { clearAuth, useAuthUser } from "../store/auth-store";

const navItems = [
  { to: "/dashboard", label: "Overview", icon: Sprout },
  { to: "/dashboard/farm-map", label: "Farms", icon: Map },
  { to: "/dashboard/crop-advisor", label: "Crop advisor", icon: Leaf },
  { to: "/dashboard/disease-scan", label: "Disease scan", icon: ScanLine },
  { to: "/dashboard/market-prices", label: "Market", icon: ChartLine },
  { to: "/dashboard/ai-assistant", label: "Assistant", icon: Bot },
  { to: "/dashboard/settings", label: "Settings", icon: Settings },
] as const;

export function DashboardLayout() {
  const user = useAuthUser();
  const router = useRouter();

  async function logout(): Promise<void> {
    await authApi.logout().catch(() => undefined);
    clearAuth();
    queryClient.clear();
    await router.navigate({ to: "/login" });
  }

  return (
    <div className="min-h-screen bg-slate-50 text-slate-950">
      <aside className="fixed inset-y-0 left-0 hidden w-72 border-r border-slate-200 bg-white p-6 lg:block">
        <div className="flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-emerald-600 text-white">
            <Sprout aria-hidden="true" />
          </div>
          <div>
            <p className="text-lg font-bold">Khetibadi</p>
            <p className="text-sm text-slate-500">Farmer intelligence</p>
          </div>
        </div>
        <nav className="mt-10 space-y-1" aria-label="Primary navigation">
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <Link
                key={item.to}
                to={item.to}
                className="flex items-center gap-3 rounded-xl px-3 py-2 text-sm font-medium text-slate-600 transition hover:bg-emerald-50 hover:text-emerald-700 [&.active]:bg-emerald-50 [&.active]:text-emerald-700"
              >
                <Icon className="h-4 w-4" aria-hidden="true" />
                {item.label}
              </Link>
            );
          })}
        </nav>
      </aside>
      <main className="lg:pl-72">
        <header className="sticky top-0 z-10 border-b border-slate-200 bg-white/90 px-6 py-4 backdrop-blur">
          <div className="flex items-center justify-between gap-4">
            <div>
              <p className="text-sm text-slate-500">Welcome back</p>
              <h1 className="text-xl font-semibold">{user?.name ?? "Farmer"}</h1>
            </div>
            <Button variant="secondary" type="button" onClick={() => void logout()}>
              <LogOut className="mr-2 h-4 w-4" aria-hidden="true" />
              Logout
            </Button>
          </div>
        </header>
        <div className="p-6">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
