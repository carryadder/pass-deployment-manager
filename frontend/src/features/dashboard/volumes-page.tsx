import { useQuery } from "@tanstack/react-query";

import { SystemService } from "@/api/generated";
import { Card } from "@/components/ui/card";

export function VolumesPage() {
  const volumesQuery = useQuery({
    queryKey: ["inventory", "volumes"],
    queryFn: SystemService.volumes,
  });

  return (
    <Card className="rounded-[32px]">
      <p className="text-sm uppercase tracking-[0.2em] text-ink/45">Volumes</p>
      <h3 className="mt-2 text-2xl font-semibold">Persistent storage inventory</h3>
      <div className="mt-6 grid gap-4 md:grid-cols-2">
        {volumesQuery.data?.map((volume) => (
          <div key={volume.name} className="rounded-[24px] border border-ink/10 bg-mist/80 p-5">
            <p className="text-lg font-semibold">{volume.name}</p>
            <p className="mt-1 text-sm text-ink/60">{volume.mountpoint}</p>
            <dl className="mt-4 grid gap-2 text-sm text-ink/70">
              <div className="flex justify-between">
                <dt>Driver</dt>
                <dd>{volume.driver}</dd>
              </div>
              <div className="flex justify-between">
                <dt>Scope</dt>
                <dd>{volume.scope}</dd>
              </div>
              <div className="flex justify-between">
                <dt>Refs</dt>
                <dd>{volume.ref_count ?? "—"}</dd>
              </div>
            </dl>
          </div>
        ))}
      </div>
    </Card>
  );
}
