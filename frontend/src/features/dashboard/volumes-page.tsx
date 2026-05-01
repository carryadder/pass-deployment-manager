import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { RefreshCw, Trash2 } from "lucide-react";

import { SystemService } from "@/api/generated";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { queryClient } from "@/lib/query-client";

function formatBytes(value?: number | null) {
  if (value == null) return "--";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let current = Math.max(value, 0);
  let unitIndex = 0;
  while (current >= 1024 && unitIndex < units.length - 1) {
    current /= 1024;
    unitIndex += 1;
  }
  return `${current.toFixed(current >= 10 ? 0 : 1)} ${units[unitIndex]}`;
}

export function VolumesPage() {
  const volumesQuery = useQuery({
    queryKey: ["inventory", "volumes"],
    queryFn: SystemService.volumes,
  });

  const [busyName, setBusyName] = useState<string | null>(null);

  const deleteMutation = useMutation({
    mutationFn: (variables: { name: string; force: boolean }) =>
      SystemService.deleteVolume(variables.name, variables.force),
    onMutate: (variables) => {
      setBusyName(variables.name);
    },
    onSettled: () => {
      setBusyName(null);
      queryClient.invalidateQueries({ queryKey: ["inventory", "volumes"] });
    },
  });

  const deleteError =
    deleteMutation.error instanceof Error ? deleteMutation.error.message : null;

  return (
    <Card className="rounded-[32px]">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="text-sm uppercase tracking-[0.2em] text-ink/45">Volumes</p>
          <h3 className="mt-2 text-2xl font-semibold">Persistent storage inventory</h3>
        </div>
        <Button variant="secondary" className="gap-2" onClick={() => volumesQuery.refetch()}>
          <RefreshCw className="h-4 w-4" /> Refresh
        </Button>
      </div>

      {deleteError ? (
        <p className="mt-4 rounded-2xl bg-coral/10 px-4 py-3 text-sm text-coral">{deleteError}</p>
      ) : null}

      <div className="mt-6 grid gap-4 md:grid-cols-2">
        {volumesQuery.data?.map((volume) => {
          const busy = busyName === volume.name && deleteMutation.isPending;
          return (
            <div key={volume.name} className="rounded-[24px] border border-ink/10 bg-mist/80 p-5">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="truncate text-lg font-semibold">{volume.name}</p>
                  <p className="mt-1 truncate text-sm text-ink/60">{volume.mountpoint}</p>
                </div>
                <div className="flex flex-col gap-2">
                  <Button
                    size="sm"
                    variant="ghost"
                    disabled={busy}
                    onClick={() => deleteMutation.mutate({ name: volume.name, force: false })}
                  >
                    <Trash2 className="mr-2 h-4 w-4" /> Remove
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    className="text-coral"
                    disabled={busy}
                    onClick={() => deleteMutation.mutate({ name: volume.name, force: true })}
                  >
                    Force
                  </Button>
                </div>
              </div>
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
                  <dd>{volume.ref_count ?? "--"}</dd>
                </div>
                <div className="flex justify-between">
                  <dt>Size</dt>
                  <dd>{formatBytes(volume.size_bytes)}</dd>
                </div>
              </dl>
            </div>
          );
        })}
        {!volumesQuery.isLoading && !(volumesQuery.data ?? []).length ? (
          <p className="text-sm text-ink/55">No volumes are currently registered.</p>
        ) : null}
      </div>
    </Card>
  );
}
