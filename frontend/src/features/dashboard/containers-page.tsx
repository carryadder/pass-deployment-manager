import { startTransition, useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronDown, ChevronUp, Download, PauseCircle, Play, PlayCircle, Radio, RefreshCw, Square, Trash2, Zap } from "lucide-react";

import { OpenAPI, SystemService } from "@/api/generated";
import type { ContainerSummary } from "@/api/generated";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { request } from "@/api/generated/core/request";
import { useAuthStore } from "@/stores/auth-store";
import { cn } from "@/lib/utils";

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

function formatRelativeTime(isoString: string | undefined): string {
  if (!isoString) return "—";
  const diff = Math.floor((Date.now() - new Date(isoString).getTime()) / 1000);
  if (diff < 60) return `${diff}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

function parseUptime(status: string): string | null {
  // Docker status strings like "Up 3 hours", "Up 2 minutes", "Up About an hour"
  const match = status.match(/^Up (.+)/i);
  return match ? match[1] : null;
}

function buildContainerLogsWsUrl(containerId: string, tail: number, token: string | null): string {
  const base = OpenAPI.BASE
    ? new URL(OpenAPI.BASE, window.location.origin)
    : new URL(window.location.origin);
  base.protocol = base.protocol === "https:" ? "wss:" : "ws:";
  base.pathname = `/api/containers/${encodeURIComponent(containerId)}/logs`;
  base.searchParams.set("tail", String(tail));
  base.searchParams.set("follow", "true");
  if (token) base.searchParams.set("token", token);
  return base.toString();
}

export function ContainersPage() {
  const qc = useQueryClient();
  const [search, setSearch] = useState("");
  const [confirmRemove, setConfirmRemove] = useState<string | null>(null);
  const [expandedLogs, setExpandedLogs] = useState<string | null>(null);

  const containersQuery = useQuery({
    queryKey: ["containers"],
    queryFn: SystemService.containers,
    refetchInterval: 10_000,
  });

  const actionMutation = useMutation({
    mutationFn: ({ id, action }: { id: string; action: string }) => containerAction(id, action),
    onSettled: () => qc.invalidateQueries({ queryKey: ["containers"] }),
  });

  const removeMutation = useMutation({
    mutationFn: (id: string) => deleteContainer(id),
    onSettled: () => {
      setConfirmRemove(null);
      setExpandedLogs(null);
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
            {containersQuery.error instanceof Error ? containersQuery.error.message : "Failed to load containers."}
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
              logsOpen={expandedLogs === container.id}
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
              onToggleLogs={() =>
                setExpandedLogs((prev) => (prev === container.id ? null : container.id))
              }
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
  logsOpen,
  actionError,
  onAction,
  onRemoveRequest,
  onRemoveConfirm,
  onRemoveCancel,
  onToggleLogs,
}: {
  container: ContainerSummary;
  busy: boolean;
  confirmingRemove: boolean;
  logsOpen: boolean;
  actionError: string | null;
  onAction: (action: string) => void;
  onRemoveRequest: () => void;
  onRemoveConfirm: () => void;
  onRemoveCancel: () => void;
  onToggleLogs: () => void;
}) {
  const isRunning = container.status.startsWith("Up") || container.status === "running";
  const isPaused = container.status.includes("Paused") || container.status === "paused";
  const uptime = parseUptime(container.status);
  const ports = container.ports.filter((p) => p.host_port);

  return (
    <Card className="rounded-[28px] px-5 py-4">
      <div className="flex flex-wrap items-start justify-between gap-4">
        {/* Info */}
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <p className="truncate font-semibold">{container.name}</p>
            <Badge tone={statusTone(container.status)}>{container.status}</Badge>
          </div>
          <p className="mt-1 truncate text-sm text-ink/60">{container.image}</p>
          <div className="mt-1 flex flex-wrap gap-4 text-xs text-ink/45">
            {uptime ? <span>⏱ Up {uptime}</span> : null}
            <span>Created {formatRelativeTime(container.created)}</span>
            {ports.length > 0 ? (
              <span>{ports.map((p) => `${p.host_port}→${p.container_port}`).join("  ")}</span>
            ) : null}
            <span className="font-mono">{container.id.slice(0, 12)}</span>
          </div>
        </div>

        {/* Actions */}
        <div className="flex flex-wrap items-center gap-2">
          <Button
            variant="secondary"
            size="sm"
            onClick={onToggleLogs}
            className="gap-1.5"
          >
            {logsOpen ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
            Logs
          </Button>

          {isRunning ? (
            <>
              <Button variant="secondary" size="sm" disabled={busy} onClick={() => onAction("restart")} title="Restart">
                <RefreshCw className="h-3.5 w-3.5" />
              </Button>
              <Button variant="secondary" size="sm" disabled={busy} onClick={() => onAction("stop")}>
                <Square className="h-3.5 w-3.5" /> Stop
              </Button>
              {!isPaused ? (
                <Button variant="secondary" size="sm" disabled={busy} onClick={() => onAction("pause")}>
                  Pause
                </Button>
              ) : (
                <Button variant="secondary" size="sm" disabled={busy} onClick={() => onAction("unpause")}>
                  Unpause
                </Button>
              )}
              <Button variant="secondary" size="sm" disabled={busy} onClick={() => onAction("kill")} className="text-coral" title="Kill">
                <Zap className="h-3.5 w-3.5" />
              </Button>
            </>
          ) : (
            <Button variant="secondary" size="sm" disabled={busy} onClick={() => onAction("start")}>
              <Play className="h-3.5 w-3.5" /> Start
            </Button>
          )}

          {confirmingRemove ? (
            <div className="flex items-center gap-2">
              <span className="text-xs text-coral">Remove?</span>
              <Button variant="secondary" size="sm" className="text-coral" disabled={busy} onClick={onRemoveConfirm}>Yes</Button>
              <Button variant="secondary" size="sm" onClick={onRemoveCancel}>No</Button>
            </div>
          ) : (
            <Button variant="ghost" size="sm" className="text-coral" disabled={busy} onClick={onRemoveRequest} title="Remove">
              <Trash2 className="h-3.5 w-3.5" />
            </Button>
          )}
        </div>
      </div>

      {actionError ? (
        <p className="mt-3 rounded-2xl bg-coral/10 px-3 py-2 text-xs text-coral">{actionError}</p>
      ) : null}

      {logsOpen ? <ContainerLogsPanel containerId={container.id} containerName={container.name} /> : null}
    </Card>
  );
}

type LogLine = { id: number; text: string };
const MAX_LINES = 1000;

function ContainerLogsPanel({ containerId, containerName }: { containerId: string; containerName: string }) {
  const accessToken = useAuthStore((s) => s.accessToken);
  const [lines, setLines] = useState<LogLine[]>([]);
  const [connState, setConnState] = useState<"connecting" | "open" | "error" | "closed">("connecting");
  const [manualPaused, setManualPaused] = useState(false);
  const [hoverPaused, setHoverPaused] = useState(false);
  const [search, setSearch] = useState("");
  const [reconnectKey, setReconnectKey] = useState(0);
  const nextId = useRef(0);
  const viewportRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setLines([]);
    setConnState("connecting");
    let cancelled = false;
    let reconnectTimer: number | null = null;
    const ws = new WebSocket(buildContainerLogsWsUrl(containerId, 200, accessToken));

    ws.onopen = () => { if (!cancelled) setConnState("open"); };
    ws.onmessage = (e) => {
      const text = String(e.data);
      startTransition(() => {
        setLines((prev) => {
          const next = [...prev, { id: nextId.current++, text }];
          return next.length > MAX_LINES ? next.slice(next.length - MAX_LINES) : next;
        });
      });
    };
    ws.onerror = () => { if (!cancelled) setConnState("error"); };
    ws.onclose = (e) => {
      if (cancelled) return;
      if (!e.wasClean) {
        setConnState("connecting");
        reconnectTimer = window.setTimeout(() => setReconnectKey((k) => k + 1), 2000);
      } else {
        setConnState("closed");
      }
    };

    return () => {
      cancelled = true;
      if (reconnectTimer !== null) window.clearTimeout(reconnectTimer);
      ws.close(1000, "cleanup");
    };
  }, [containerId, accessToken, reconnectKey]);

  // auto-scroll
  useEffect(() => {
    if (manualPaused || hoverPaused) return;
    const el = viewportRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [lines, manualPaused, hoverPaused]);

  const filtered = search.trim()
    ? lines.filter((l) => l.text.toLowerCase().includes(search.toLowerCase()))
    : lines;

  function downloadLogs() {
    const blob = new Blob([filtered.map((l) => l.text).join("\n")], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${containerName}.log`;
    a.click();
    URL.revokeObjectURL(url);
  }

  const connColor =
    connState === "open" ? "text-moss" :
    connState === "connecting" ? "text-slate" :
    connState === "error" ? "text-coral" : "text-ink/45";

  return (
    <div className="mt-4 rounded-[24px] border border-ink/10 bg-ink overflow-hidden">
      {/* toolbar */}
      <div className="flex flex-wrap items-center gap-3 border-b border-white/10 px-4 py-3">
        <div className={cn("flex items-center gap-1.5 text-xs font-medium", connColor)}>
          <Radio className="h-3.5 w-3.5" />
          {connState}
        </div>
        <Input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Filter logs…"
          className="h-8 w-48 rounded-xl border-white/15 bg-white/10 text-xs text-mist placeholder:text-mist/40 focus:border-white/30"
        />
        <div className="ml-auto flex items-center gap-2">
          <Button
            variant="ghost"
            size="sm"
            className="h-8 gap-1.5 text-xs text-mist/70 hover:text-mist"
            onClick={() => setManualPaused((p) => !p)}
          >
            {manualPaused ? <PlayCircle className="h-3.5 w-3.5" /> : <PauseCircle className="h-3.5 w-3.5" />}
            {manualPaused ? "Resume" : "Pause"}
          </Button>
          <Button
            variant="ghost"
            size="sm"
            className="h-8 gap-1.5 text-xs text-mist/70 hover:text-mist"
            onClick={() => setReconnectKey((k) => k + 1)}
          >
            <RefreshCw className="h-3.5 w-3.5" /> Reconnect
          </Button>
          <Button
            variant="ghost"
            size="sm"
            className="h-8 gap-1.5 text-xs text-mist/70 hover:text-mist"
            onClick={downloadLogs}
          >
            <Download className="h-3.5 w-3.5" /> Save
          </Button>
        </div>
      </div>

      {/* log viewport */}
      <div
        ref={viewportRef}
        className="h-72 overflow-auto p-4 font-mono text-xs text-mist/85 leading-5"
        onMouseEnter={() => setHoverPaused(true)}
        onMouseLeave={() => setHoverPaused(false)}
      >
        {filtered.length === 0 ? (
          <p className="text-mist/40">{connState === "connecting" ? "Connecting…" : "No output yet."}</p>
        ) : (
          filtered.map((line) => (
            <div key={line.id} className="whitespace-pre-wrap break-all py-0.5 hover:bg-white/5 px-1 rounded">
              {line.text}
            </div>
          ))
        )}
      </div>

      <div className="border-t border-white/10 px-4 py-2 text-xs text-mist/35">
        {filtered.length} lines{search ? ` matching "${search}"` : ""} · {lines.length} total buffered
      </div>
    </div>
  );
}
