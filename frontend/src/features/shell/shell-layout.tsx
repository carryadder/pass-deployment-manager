import { useMemo } from "react";
import { Outlet, NavLink, useLocation } from "react-router-dom";
import {
  Boxes,
  FolderKanban,
  LayoutDashboard,
  LogOut,
  Network,
  ScrollText,
  Server,
  Settings,
  Shapes,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { useAuthStore } from "@/stores/auth-store";

const navigation = [
  { to: "/", label: "Projects", icon: FolderKanban },
  { to: "/services", label: "Services", icon: Boxes },
  { to: "/volumes", label: "Volumes", icon: Shapes },
  { to: "/networks", label: "Networks", icon: Network },
  { to: "/system", label: "System", icon: Server },
  { to: "/audit", label: "Audit log", icon: ScrollText },
  { to: "/settings", label: "Settings", icon: Settings },
];

export function ShellLayout() {
  const location = useLocation();
  const logout = useAuthStore((state) => state.logout);
  const currentUser = useAuthStore((state) => state.currentUser);

  const headline = useMemo(() => {
    const active = navigation.find((item) =>
      item.to === "/"
        ? location.pathname === "/"
        : location.pathname === item.to || location.pathname.startsWith(`${item.to}/`),
    );
    return active?.label ?? "Projects";
  }, [location.pathname]);

  return (
    <div className="min-h-screen bg-mist bg-grain">
      <div className="mx-auto grid min-h-screen max-w-7xl gap-6 px-4 py-4 lg:grid-cols-[280px_1fr] lg:px-6">
        <aside className="lg:sticky lg:top-4 lg:h-[calc(100vh-2rem)]">
          <Card className="flex h-full flex-col justify-between rounded-[30px] bg-ink px-5 py-6 text-mist">
            <div>
              <div className="mb-8 flex items-center gap-3">
                <div className="rounded-2xl bg-coral p-2 text-ink">
                  <LayoutDashboard className="h-5 w-5" />
                </div>
                <div>
                  <p className="text-sm uppercase tracking-[0.24em] text-mist/65">Day 21</p>
                  <h1 className="text-xl font-semibold">Operator console</h1>
                </div>
              </div>

              <nav className="space-y-2">
                {navigation.map((item) => {
                  const Icon = item.icon;
                  return (
                    <NavLink
                      key={item.to}
                      to={item.to}
                      end={item.to === "/"}
                      className={({ isActive }) =>
                        cn(
                          "flex items-center gap-3 rounded-2xl px-4 py-3 text-sm font-medium transition",
                          isActive
                            ? "bg-white text-ink"
                            : "text-mist/70 hover:bg-white/10 hover:text-mist",
                        )
                      }
                    >
                      <Icon className="h-4 w-4" />
                      {item.label}
                    </NavLink>
                  );
                })}
              </nav>
            </div>

            <div className="space-y-4">
              <div className="rounded-3xl bg-white/8 p-4">
                <p className="text-xs uppercase tracking-[0.2em] text-mist/60">Signed in</p>
                <p className="mt-2 text-sm font-semibold">{currentUser?.full_name ?? "Unknown user"}</p>
                <p className="text-sm text-mist/65">{currentUser?.email ?? "No session"}</p>
              </div>
              <Button
                variant="secondary"
                className="w-full justify-between bg-white text-ink hover:bg-mist"
                onClick={logout}
              >
                Log out
                <LogOut className="h-4 w-4" />
              </Button>
            </div>
          </Card>
        </aside>

        <main className="flex min-h-[60vh] flex-col gap-6">
          <header className="rounded-[30px] border border-ink/10 bg-white/75 px-6 py-5 shadow-panel backdrop-blur">
            <p className="text-sm uppercase tracking-[0.24em] text-ink/50">Operator workspace</p>
            <div className="mt-2 flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
              <div>
                <h2 className="text-3xl font-semibold tracking-tight">{headline}</h2>
                <p className="text-sm text-ink/65">
                  Search, operate, inspect, and watch live service metrics from the same protected operator shell.
                </p>
              </div>
            </div>
          </header>

          <Outlet />
        </main>
      </div>
    </div>
  );
}
