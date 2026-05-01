import { useQuery } from "@tanstack/react-query";
import { Cpu, HardDrive, Images, Layers3 } from "lucide-react";

import { SystemService } from "@/api/generated";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";

const metricCards = [
  { key: "Containers", icon: Layers3, accessor: (data: Record<string, unknown>) => data.Containers },
  { key: "Images", icon: Images, accessor: (data: Record<string, unknown>) => data.Images },
  { key: "CPUs", icon: Cpu, accessor: (data: Record<string, unknown>) => data.NCPU },
  { key: "Storage driver", icon: HardDrive, accessor: (data: Record<string, unknown>) => data.Driver },
];

export function OverviewPage() {
  const systemInfoQuery = useQuery({
    queryKey: ["system", "info"],
    queryFn: SystemService.systemInfo,
  });

  return (
    <div className="grid gap-6">
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {metricCards.map(({ key, icon: Icon, accessor }) => (
          <Card key={key} className="rounded-[28px]">
            <div className="flex items-start justify-between">
              <div>
                <p className="text-xs uppercase tracking-[0.2em] text-ink/45">{key}</p>
                <p className="mt-4 text-3xl font-semibold">
                  {systemInfoQuery.data ? String(accessor(systemInfoQuery.data) ?? "--") : "..."}
                </p>
              </div>
              <div className="rounded-2xl bg-cyan/20 p-3 text-slate">
                <Icon className="h-5 w-5" />
              </div>
            </div>
          </Card>
        ))}
      </div>

      <Card className="rounded-[32px]">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-sm uppercase tracking-[0.2em] text-ink/45">Backend connectivity</p>
            <h3 className="mt-2 text-2xl font-semibold">System inventory is reachable</h3>
          </div>
          <Badge tone={systemInfoQuery.data ? "success" : "warning"}>
            {systemInfoQuery.isError ? "Connection issue" : "API online"}
          </Badge>
        </div>
        <pre className="mt-6 overflow-x-auto rounded-3xl bg-ink p-5 text-sm text-mist/90">
          {systemInfoQuery.isLoading
            ? "Loading system info..."
            : systemInfoQuery.isError
              ? systemInfoQuery.error instanceof Error
                ? systemInfoQuery.error.message
                : "Unable to load system info."
              : JSON.stringify(systemInfoQuery.data, null, 2)}
        </pre>
      </Card>
    </div>
  );
}
