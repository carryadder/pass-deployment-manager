import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { RefreshCw, Trash2 } from "lucide-react";

import { SystemService } from "@/api/generated";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { queryClient } from "@/lib/query-client";

const PROTECTED_NAMES = new Set(["bridge", "host", "none"]);

export function NetworksPage() {
  const networksQuery = useQuery({
    queryKey: ["inventory", "networks"],
    queryFn: SystemService.networks,
  });

  const [busyName, setBusyName] = useState<string | null>(null);

  const deleteMutation = useMutation({
    mutationFn: (name: string) => SystemService.deleteNetwork(name),
    onMutate: (name) => {
      setBusyName(name);
    },
    onSettled: () => {
      setBusyName(null);
      queryClient.invalidateQueries({ queryKey: ["inventory", "networks"] });
    },
  });

  const deleteError =
    deleteMutation.error instanceof Error ? deleteMutation.error.message : null;

  return (
    <Card className="rounded-[32px]">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="text-sm uppercase tracking-[0.2em] text-ink/45">Networks</p>
          <h3 className="mt-2 text-2xl font-semibold">Connectivity topology</h3>
        </div>
        <Button variant="secondary" className="gap-2" onClick={() => networksQuery.refetch()}>
          <RefreshCw className="h-4 w-4" /> Refresh
        </Button>
      </div>

      {deleteError ? (
        <p className="mt-4 rounded-2xl bg-coral/10 px-4 py-3 text-sm text-coral">{deleteError}</p>
      ) : null}

      <div className="mt-6 space-y-4">
        {networksQuery.data?.map((network) => {
          const protectedNetwork = PROTECTED_NAMES.has(network.name);
          const busy = busyName === network.name && deleteMutation.isPending;
          return (
            <div
              key={network.id}
              className="flex flex-col gap-3 rounded-[24px] border border-ink/10 bg-white p-5 md:flex-row md:items-center md:justify-between"
            >
              <div>
                <p className="text-lg font-semibold">{network.name}</p>
                <p className="text-sm text-ink/60">
                  {network.driver} / {network.scope}
                </p>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <Badge tone={network.internal ? "warning" : "info"}>
                  {network.internal ? "Internal" : "External"}
                </Badge>
                <Badge tone={network.attachable ? "success" : "neutral"}>
                  {network.attachable ? "Attachable" : "Fixed"}
                </Badge>
                <Badge>{network.containers} containers</Badge>
                <Button
                  size="sm"
                  variant="ghost"
                  className="text-coral"
                  disabled={busy || protectedNetwork}
                  onClick={() => deleteMutation.mutate(network.name)}
                  title={protectedNetwork ? "Built-in networks cannot be removed" : undefined}
                >
                  <Trash2 className="mr-2 h-4 w-4" /> Remove
                </Button>
              </div>
            </div>
          );
        })}
        {!networksQuery.isLoading && !(networksQuery.data ?? []).length ? (
          <p className="text-sm text-ink/55">No networks are currently registered.</p>
        ) : null}
      </div>
    </Card>
  );
}
