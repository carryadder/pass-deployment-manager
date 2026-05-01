import { RouterProvider, createBrowserRouter } from "react-router-dom";

import { Card } from "@/components/ui/card";
import { LoginPage } from "@/features/auth/login-page";
import { useAuthBootstrap } from "@/features/auth/use-auth-bootstrap";
import { AuditPage } from "@/features/dashboard/audit-page";
import { NetworksPage } from "@/features/dashboard/networks-page";
import { NotFoundPage } from "@/features/dashboard/not-found-page";
import { OverviewPage } from "@/features/dashboard/overview-page";
import { ServiceDetailPage } from "@/features/dashboard/service-detail-page";
import { ServicesPage } from "@/features/dashboard/services-page";
import { SettingsPage } from "@/features/dashboard/settings-page";
import { SystemPage } from "@/features/dashboard/system-page";
import { VolumesPage } from "@/features/dashboard/volumes-page";
import { RequireAuth } from "@/features/shell/require-auth";
import { ShellLayout } from "@/features/shell/shell-layout";

const router = createBrowserRouter([
  {
    path: "/login",
    element: <LoginPage />,
  },
  {
    element: <RequireAuth />,
    children: [
      {
        element: <ShellLayout />,
        children: [
          { path: "/", element: <OverviewPage /> },
          { path: "/services", element: <ServicesPage /> },
          { path: "/services/:serviceId", element: <ServiceDetailPage /> },
          { path: "/volumes", element: <VolumesPage /> },
          { path: "/networks", element: <NetworksPage /> },
          { path: "/system", element: <SystemPage /> },
          { path: "/audit", element: <AuditPage /> },
          { path: "/settings", element: <SettingsPage /> },
        ],
      },
    ],
  },
  {
    path: "*",
    element: <NotFoundPage />,
  },
]);

function AppBoot() {
  const { hydrated, isLoading } = useAuthBootstrap();

  if (!hydrated || isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-mist bg-grain p-6">
        <Card className="rounded-[30px] px-8 py-10 text-center">
          <p className="text-sm uppercase tracking-[0.24em] text-ink/45">Loading workspace</p>
          <h1 className="mt-3 text-2xl font-semibold">Hydrating session and API client...</h1>
        </Card>
      </div>
    );
  }

  return <RouterProvider router={router} />;
}

export default AppBoot;
