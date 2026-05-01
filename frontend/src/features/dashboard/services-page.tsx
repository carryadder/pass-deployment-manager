import { useQuery } from "@tanstack/react-query";

import { SystemService } from "@/api/generated";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";

export function ServicesPage() {
  const containersQuery = useQuery({
    queryKey: ["inventory", "containers"],
    queryFn: SystemService.containers,
  });

  return (
    <Card className="rounded-[32px]">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm uppercase tracking-[0.2em] text-ink/45">Services</p>
          <h3 className="mt-2 text-2xl font-semibold">Container inventory</h3>
        </div>
        <Badge tone="info">{containersQuery.data?.length ?? 0} items</Badge>
      </div>

      <div className="mt-6 overflow-hidden rounded-[28px] border border-ink/10">
        <table className="min-w-full divide-y divide-ink/10 text-left text-sm">
          <thead className="bg-ink/5 text-ink/60">
            <tr>
              <th className="px-4 py-3 font-medium">Name</th>
              <th className="px-4 py-3 font-medium">Image</th>
              <th className="px-4 py-3 font-medium">Status</th>
              <th className="px-4 py-3 font-medium">Ports</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-ink/10 bg-white">
            {containersQuery.data?.map((container) => (
              <tr key={container.id}>
                <td className="px-4 py-3 font-medium">{container.name}</td>
                <td className="px-4 py-3 text-ink/70">{container.image}</td>
                <td className="px-4 py-3">
                  <Badge tone={container.status === "running" ? "success" : "warning"}>{container.status}</Badge>
                </td>
                <td className="px-4 py-3 text-ink/70">
                  {container.ports.length
                    ? container.ports
                        .map((port) => `${port.host_port ?? "auto"} → ${port.container_port}`)
                        .join(", ")
                    : "No published ports"}
                </td>
              </tr>
            ))}
            {!containersQuery.isLoading && !containersQuery.data?.length ? (
              <tr>
                <td colSpan={4} className="px-4 py-8 text-center text-ink/55">
                  No containers returned by the backend yet.
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
