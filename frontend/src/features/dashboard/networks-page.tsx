import { useQuery } from "@tanstack/react-query";

import { SystemService } from "@/api/generated";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";

export function NetworksPage() {
  const networksQuery = useQuery({
    queryKey: ["inventory", "networks"],
    queryFn: SystemService.networks,
  });

  return (
    <Card className="rounded-[32px]">
      <p className="text-sm uppercase tracking-[0.2em] text-ink/45">Networks</p>
      <h3 className="mt-2 text-2xl font-semibold">Connectivity topology</h3>
      <div className="mt-6 space-y-4">
        {networksQuery.data?.map((network) => (
          <div
            key={network.id}
            className="flex flex-col gap-3 rounded-[24px] border border-ink/10 bg-white p-5 md:flex-row md:items-center md:justify-between"
          >
            <div>
              <p className="text-lg font-semibold">{network.name}</p>
              <p className="text-sm text-ink/60">{network.driver} / {network.scope}</p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Badge tone={network.internal ? "warning" : "info"}>
                {network.internal ? "Internal" : "External"}
              </Badge>
              <Badge tone={network.attachable ? "success" : "neutral"}>
                {network.attachable ? "Attachable" : "Fixed"}
              </Badge>
              <Badge>{network.containers} containers</Badge>
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
}
