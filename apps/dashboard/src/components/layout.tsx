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
    await router.navigate({ to: "/login" });
    clearAuth();
    queryClient.clear();
  }

  return (
    <div className="min-h-screen text-[#2d2217]">
      <aside className="fixed inset-y-0 left-0 hidden w-[19rem] border-r border-[#d8c4a5] bg-[#2f5d3a] p-6 text-[#fffaf0] shadow-[18px_0_55px_rgba(47,93,58,0.18)] lg:block">
        <div className="rounded-[1.75rem] border border-[#f3dfb4]/25 bg-[#fffaf0]/10 p-4 backdrop-blur">
          <div className="flex items-center gap-3">
          <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-[#f3dfb4] text-[#2f5d3a] shadow-lg shadow-[#1d3f27]/20">
            <Sprout aria-hidden="true" />
          </div>
          <div>
            <p className="text-xl font-black tracking-tight">Khetibadi</p>
            <p className="text-sm text-[#efe3d1]">Mitti se market tak</p>
          </div>
          </div>
        </div>
        <nav className="mt-8 space-y-2" aria-label="Primary navigation">
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <Link
                key={item.to}
                to={item.to}
                activeOptions={{ exact: true }}
                className="flex items-center gap-3 rounded-2xl px-4 py-3 text-sm font-semibold text-[#e9dcc5] transition hover:bg-[#fffaf0]/10 hover:text-white [&.active]:bg-[#f3dfb4] [&.active]:text-[#2f5d3a] [&.active]:shadow-lg [&.active]:shadow-[#1e3d27]/20"
              >
                <Icon className="h-4 w-4" aria-hidden="true" />
                {item.label}
              </Link>
            );
          })}
        </nav>
        <div className="absolute bottom-6 left-6 right-6 rounded-[1.5rem] border border-[#f3dfb4]/25 bg-[#244b2f] p-4 text-sm text-[#efe3d1]">
          <p className="font-bold text-[#f3dfb4]">Today’s rhythm</p>
          <p className="mt-1">Check mandi prices, scan leaves, and plan soil nutrition from one gateway.</p>
        </div>
      </aside>
      <main className="lg:pl-[19rem]">
        <header className="sticky top-0 z-10 border-b border-[#d8c4a5] bg-[#fffaf0]/85 px-4 py-4 backdrop-blur-xl md:px-6">
          <div className="flex items-center justify-between gap-4">
            <div>
              <p className="text-sm font-semibold text-[#b87924]">Welcome back</p>
              <h1 className="text-2xl font-black tracking-tight text-[#2d2217]">{user?.name ?? "Farmer"}</h1>
            </div>
            <Button variant="secondary" type="button" onClick={() => void logout()}>
              <LogOut className="mr-2 h-4 w-4" aria-hidden="true" />
              Logout
            </Button>
          </div>
          <nav className="mt-4 flex gap-2 overflow-x-auto pb-1 lg:hidden" aria-label="Primary navigation">
            {navItems.map((item) => {
              const Icon = item.icon;
              return (
                <Link
                  key={item.to}
                  to={item.to}
                  activeOptions={{ exact: true }}
                  className="flex shrink-0 items-center gap-2 rounded-full border border-[#d8c4a5] bg-[#fffaf0] px-3 py-2 text-xs font-extrabold text-[#6d5a40] shadow-sm transition hover:bg-[#f7eddc] [&.active]:border-[#2f5d3a] [&.active]:bg-[#2f5d3a] [&.active]:text-[#fffaf0]"
                >
                  <Icon className="h-3.5 w-3.5" aria-hidden="true" />
                  {item.label}
                </Link>
              );
            })}
          </nav>
        </header>
        <div className="p-5 md:p-8">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
