import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Play, RefreshCw, Square, Trash2, Zap } from "lucide-react";

import { SystemService } from "@/api/generated";
import type { ContainerSummary } from "@/api/generated";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { request } from "@/api/generated/core/request";

function containerAction(containerId: string, action: string) {
  return request<Record<string, unknown>>({
    method: "POST",
    url: `/api/containers/${encodeURIComponent(containerId)}/${action}`,
  });
}

function deleteContainer(containerId: string, force = true) {
  return request<Record<string, unknown>>({
    method: "DELETE",
    url: `/api/containers/${encodeURIComponent(containerId)}?force=${force}&volumes=false`,
  });
}

function statusTone(status: string): "success" | "warning" | "info" | "neutral" {
  if (status.startsWith("Up") || status === "running") return "success";
  if (status.startsWith("Exited") || status === "exited") return "neutral";
  if (status.includes("Paused") || status === "paused") return "warning";
  return "info";
}

export function ContainersPage() {
  const qc = useQueryClient();
  const [search, setSearch] = useState("");
  const [confirmRemove, setConfirmRemove] = useState<string | null>(null);

  const containersQuery = useQuery({
    queryKey: ["containers"],
    queryFn: SystemService.containers,
    refetchInterval: 10_000,
  });

  const actionMutation = useMutation({
    mutationFn: ({ id, action }: { id: string; action: string }) =>
      containerAction(id, action),
    onSettled: () => qc.invalidateQueries({ queryKey: ["containers"] }),
  });

  const removeMutation = useMutation({
    mutationFn: (id: string) => deleteContainer(id),
    onSettled: () => {
      setConfirmRemove(null);
      qc.invalidateQueries({ queryKey: ["containers"] });
    },
  });

  const containers: ContainerSummary[] = containersQuery.data ?? [];
  const filtered = search.trim()
    ? containers.filter(
        (c) =>
          c.name.toLowerCase().includes(search.toLowerCase()) ||
          c.image.toLowerCase().includes(search.toLowerCase()) ||
          c.status.toLowerCase().includes(search.toLowerCase()),
      )
    : containers;

  const running = containers.filter((c) => c.status.startsWith("Up") || c.status === "running").length;

  return (
    <div className="grid gap-6">
      <Card className="rounded-[32px]">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-sm uppercase tracking-[0.2em] text-ink/45">Docker</p>
            <h3 className="mt-2 text-2xl font-semibold">Containers</h3>
            <p className="mt-1 text-sm text-ink/65">
              All containers on the Docker host.{" "}
              <span className="font-medium text-ink">{running} running</span>
              {" · "}
              {containers.length} total
            </p>
          </div>
          <div className="flex items-center gap-3">
            <Input
              placeholder="Search name, image, status…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-64"
            />
            <Button
              variant="secondary"
              size="sm"
              onClick={() => containersQuery.refetch()}
              disabled={containersQuery.isFetching}
            >
              <RefreshCw className={`h-4 w-4 ${containersQuery.isFetching ? "animate-spin" : ""}`} />
            </Button>
          </div>
        </div>

        {containersQuery.isError ? (
          <p className="mt-4 rounded-2xl bg-coral/10 px-4 py-3 text-sm text-coral">
            {containersQuery.error instanceof Error
              ? containersQuery.error.message
              : "Failed to load containers."}
          </p>
        ) : null}
      </Card>

      {containersQuery.isLoading ? (
        <Card className="rounded-[32px]">
          <p className="text-sm text-ink/55">Loading containers...</p>
        </Card>
      ) : filtered.length === 0 ? (
        <Card className="rounded-[32px]">
          <p className="text-sm text-ink/55">
            {search ? "No containers match your search." : "No containers found on the Docker host."}
          </p>
        </Card>
      ) : (
        <div className="grid gap-3">
          {filtered.map((container) => (
            <ContainerRow
              key={container.id}
              container={container}
              busy={
                (actionMutation.isPending && actionMutation.variables?.id === container.id) ||
                (removeMutation.isPending && removeMutation.variables === container.id)
              }
              confirmingRemove={confirmRemove === container.id}
              actionError={
                actionMutation.isError && actionMutation.variables?.id === container.id
                  ? actionMutation.error instanceof Error
                    ? actionMutation.error.message
                    : "Action failed"
                  : null
              }
              onAction={(action) => actionMutation.mutate({ id: container.id, action })}
              onRemoveRequest={() => setConfirmRemove(container.id)}
              onRemoveConfirm={() => removeMutation.mutate(container.id)}
              onRemoveCancel={() => setConfirmRemove(null)}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function ContainerRow({
  container,
  busy,
  confirmingRemove,
  actionError,
  onAction,
  onRemoveRequest,
  onRemoveConfirm,
  onRemoveCancel,
}: {
  container: ContainerSummary;
  busy: boolean;
  confirmingRemove: boolean;
  actionError: string | null;
  onAction: (action: string) => void;
  onRemoveRequest: () => void;
  onRemoveConfirm: () => void;
  onRemoveCancel: () => void;
}) {
  const isRunning = container.status.startsWith("Up") || container.status === "running";
  const isPaused = container.status.includes("Paused") || container.status === "paused";

  const ports = container.ports.filter((p) => p.host_port);

  return (
    <Card className="rounded-[28px] px-5 py-4">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <p className="truncate font-semibold">{container.name}</p>
            <Badge tone={statusTone(container.status)}>{container.status}</Badge>
          </div>
          <p className="mt-1 truncate text-sm text-ink/60">{container.image}</p>
          {ports.length > 0 ? (
            <p className="mt-1 text-xs text-ink/45">
              {ports.map((p) => `${p.host_port}→${p.container_port}`).join("  ")}
            </p>
          ) : null}
          <p className="mt-1 font-mono text-xs text-ink/35">{container.id.slice(0, 12)}</p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {isRunning ? (
            <>
              <Button
                variant="secondary"
                size="sm"
                disabled={busy}
                onClick={() => onAction("restart")}
                title="Restart"
              >
                <RefreshCw className="h-3.5 w-3.5" />
              </Button>
              <Button
                variant="secondary"
                size="sm"
                disabled={busy}
                onClick={() => onAction("stop")}
                title="Stop"
              >
                <Square className="h-3.5 w-3.5" />
                Stop
              </Button>
              {!isPaused ? (
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={busy}
                  onClick={() => onAction("pause")}
                  title="Pause"
                >
                  Pause
                </Button>
              ) : (
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={busy}
                  onClick={() => onAction("unpause")}
                  title="Unpause"
                >
                  Unpause
                </Button>
              )}
              <Button
                variant="secondary"
                size="sm"
                disabled={busy}
                onClick={() => onAction("kill")}
                title="Kill"
                className="text-coral"
              >
                <Zap className="h-3.5 w-3.5" />
              </Button>
            </>
          ) : (
            <Button
              variant="secondary"
              size="sm"
              disabled={busy}
              onClick={() => onAction("start")}
              title="Start"
            >
              <Play className="h-3.5 w-3.5" />
              Start
            </Button>
          )}

          {confirmingRemove ? (
            <div className="flex items-center gap-2">
              <span className="text-xs text-coral">Remove?</span>
              <Button
                variant="secondary"
                size="sm"
                className="text-coral"
                disabled={busy}
                onClick={onRemoveConfirm}
              >
                Yes
              </Button>
              <Button variant="secondary" size="sm" onClick={onRemoveCancel}>
                No
              </Button>
            </div>
          ) : (
            <Button
              variant="ghost"
              size="sm"
              className="text-coral"
              disabled={busy}
              onClick={onRemoveRequest}
              title="Remove"
            >
              <Trash2 className="h-3.5 w-3.5" />
            </Button>
          )}
        </div>
      </div>

      {actionError ? (
        <p className="mt-3 rounded-2xl bg-coral/10 px-3 py-2 text-xs text-coral">{actionError}</p>
      ) : null}
    </Card>
  );
}
