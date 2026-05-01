import { useMemo, useState } from "react";
import { useMutation, useQueries, useQuery } from "@tanstack/react-query";
import { Plus, RefreshCw, Search, Trash2 } from "lucide-react";
import { Link } from "react-router-dom";

import { ServicesService } from "@/api/generated";
import type { CreateServiceRequest, ServiceMetricSample, ServiceSummary } from "@/api/generated";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Sparkline, type SparklineSample } from "@/features/dashboard/service-metrics-shared";
import { queryClient } from "@/lib/query-client";

const initialForm: CreateServiceRequest = {
  name: "",
  image: "nginx:latest",
  cpus: 0.5,
  memory_mb: 256,
  disk_mb: null,
  env: {},
  ports: [{ container_port: 80, host_port: 8080 }],
  volumes: [],
  network: null,
  domain: "",
  restart_policy: "unless-stopped",
  pids_limit: 256,
};

function formatPercent(value?: number | null) {
  return value == null ? "--" : `${value.toFixed(1)}%`;
}

function formatUptime(value?: number | null) {
  if (value == null) {
    return "--";
  }
  const minutes = Math.floor(value / 60);
  if (minutes < 60) {
    return `${minutes}m`;
  }
  const hours = Math.floor(minutes / 60);
  const remainder = minutes % 60;
  return `${hours}h ${remainder}m`;
}

function statusTone(status: string): "success" | "warning" | "info" | "neutral" {
  if (status === "running") {
    return "success";
  }
  if (status.includes("queued") || status === "rolling_out" || status === "build_queued") {
    return "info";
  }
  if (status === "stopped") {
    return "neutral";
  }
  return "warning";
}

export function ServicesPage() {
  const [search, setSearch] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState<CreateServiceRequest>(initialForm);
  const [busyServiceId, setBusyServiceId] = useState<string | null>(null);

  const servicesQuery = useQuery({
    queryKey: ["services", "list"],
    queryFn: ServicesService.list,
  });

  const createMutation = useMutation({
    mutationFn: ServicesService.create,
    onSuccess: () => {
      setShowCreate(false);
      setForm(initialForm);
      queryClient.invalidateQueries({ queryKey: ["services", "list"] });
    },
  });

  const actionMutation = useMutation({
    mutationFn: async ({
      serviceId,
      action,
    }: {
      serviceId: string;
      action: "start" | "stop" | "restart" | "redeploy" | "delete";
    }) => {
      setBusyServiceId(serviceId);
      if (action === "start") {
        return ServicesService.start(serviceId);
      }
      if (action === "stop") {
        return ServicesService.stop(serviceId);
      }
      if (action === "restart") {
        return ServicesService.restart(serviceId);
      }
      if (action === "redeploy") {
        return ServicesService.redeploy(serviceId);
      }
      return ServicesService.delete(serviceId);
    },
    onSettled: () => {
      setBusyServiceId(null);
      queryClient.invalidateQueries({ queryKey: ["services", "list"] });
    },
  });

  const filteredServices = useMemo(() => {
    const term = search.trim().toLowerCase();
    if (!term) {
      return servicesQuery.data ?? [];
    }
    return (servicesQuery.data ?? []).filter((service) =>
      [service.name, service.image, service.status, service.domain ?? ""].some((value) =>
        value.toLowerCase().includes(term),
      ),
    );
  }, [search, servicesQuery.data]);

  const createError =
    createMutation.error instanceof Error ? createMutation.error.message : "Unable to create service.";
  const actionError =
    actionMutation.error instanceof Error ? actionMutation.error.message : "Unable to perform action.";
  const sparklineQueries = useQueries({
    queries: filteredServices.slice(0, 8).map((service) => ({
      queryKey: ["services", "metrics", "sparkline", service.service_id],
      queryFn: () => ServicesService.metrics(service.service_id, "5m"),
      staleTime: 15_000,
      refetchInterval: 20_000,
    })),
  });
  const sparklineByServiceId = new Map<string, ServiceMetricSample[]>();
  filteredServices.slice(0, 8).forEach((service, index) => {
    sparklineByServiceId.set(service.service_id, sparklineQueries[index]?.data ?? []);
  });

  return (
    <div className="grid gap-6">
      <Card className="rounded-[32px]">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-sm uppercase tracking-[0.2em] text-ink/45">Services</p>
            <h3 className="mt-2 text-2xl font-semibold">Live deployment inventory</h3>
            <p className="mt-2 max-w-2xl text-sm text-ink/65">
              Search, create, and operate services from one table, now with quick metric sparklines
              so you can spot trouble before opening the detail view.
            </p>
          </div>
          <div className="flex flex-col gap-3 sm:flex-row">
            <div className="relative min-w-[240px]">
              <Search className="pointer-events-none absolute left-4 top-3.5 h-4 w-4 text-ink/35" />
              <Input
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Search name, image, status..."
                className="pl-10"
              />
            </div>
            <Button variant="secondary" className="gap-2" onClick={() => servicesQuery.refetch()}>
              <RefreshCw className="h-4 w-4" />
              Refresh
            </Button>
            <Button className="gap-2" onClick={() => setShowCreate((current) => !current)}>
              <Plus className="h-4 w-4" />
              {showCreate ? "Close form" : "New service"}
            </Button>
          </div>
        </div>

        {showCreate ? (
          <div className="mt-6 rounded-[28px] border border-ink/10 bg-mist/80 p-5">
            <div className="mb-4">
              <p className="text-sm uppercase tracking-[0.18em] text-ink/45">Create service</p>
              <h4 className="mt-2 text-xl font-semibold">Launch a Docker-backed service</h4>
            </div>
            <form
              className="grid gap-4 md:grid-cols-2"
              onSubmit={(event) => {
                event.preventDefault();
                createMutation.mutate(form);
              }}
            >
              <label className="space-y-2 text-sm text-ink/70">
                <span>Name</span>
                <Input
                  value={form.name}
                  onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))}
                  placeholder="hello-web"
                />
              </label>
              <label className="space-y-2 text-sm text-ink/70">
                <span>Image</span>
                <Input
                  value={form.image}
                  onChange={(event) => setForm((current) => ({ ...current, image: event.target.value }))}
                  placeholder="nginx:latest"
                />
              </label>
              <label className="space-y-2 text-sm text-ink/70">
                <span>CPU</span>
                <Input
                  type="number"
                  min="0.1"
                  step="0.1"
                  value={form.cpus}
                  onChange={(event) =>
                    setForm((current) => ({ ...current, cpus: Number(event.target.value || 0.5) }))
                  }
                />
              </label>
              <label className="space-y-2 text-sm text-ink/70">
                <span>Memory (MB)</span>
                <Input
                  type="number"
                  min="64"
                  step="64"
                  value={form.memory_mb}
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      memory_mb: Number(event.target.value || 256),
                    }))
                  }
                />
              </label>
              <label className="space-y-2 text-sm text-ink/70">
                <span>Container port</span>
                <Input
                  type="number"
                  min="1"
                  max="65535"
                  value={form.ports?.[0]?.container_port ?? 80}
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      ports: [
                        {
                          container_port: Number(event.target.value || 80),
                          host_port: current.ports?.[0]?.host_port ?? null,
                        },
                      ],
                    }))
                  }
                />
              </label>
              <label className="space-y-2 text-sm text-ink/70">
                <span>Host port</span>
                <Input
                  type="number"
                  min="1"
                  max="65535"
                  value={form.ports?.[0]?.host_port ?? ""}
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      ports: [
                        {
                          container_port: current.ports?.[0]?.container_port ?? 80,
                          host_port: event.target.value ? Number(event.target.value) : null,
                        },
                      ],
                    }))
                  }
                  placeholder="8080"
                />
              </label>
              <label className="space-y-2 text-sm text-ink/70 md:col-span-2">
                <span>Domain</span>
                <Input
                  value={form.domain ?? ""}
                  onChange={(event) => setForm((current) => ({ ...current, domain: event.target.value || null }))}
                  placeholder="hello.localhost"
                />
              </label>
              {createMutation.isError ? (
                <p className="md:col-span-2 rounded-2xl bg-coral/10 px-4 py-3 text-sm text-coral">
                  {createError}
                </p>
              ) : null}
              <div className="md:col-span-2 flex flex-wrap gap-3">
                <Button type="submit" disabled={createMutation.isPending}>
                  {createMutation.isPending ? "Creating..." : "Create service"}
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  onClick={() => {
                    setShowCreate(false);
                    setForm(initialForm);
                  }}
                >
                  Cancel
                </Button>
              </div>
            </form>
          </div>
        ) : null}

        {actionMutation.isError ? (
          <p className="mt-6 rounded-2xl bg-coral/10 px-4 py-3 text-sm text-coral">{actionError}</p>
        ) : null}

        <div className="mt-6 overflow-hidden rounded-[28px] border border-ink/10">
          <table className="min-w-full divide-y divide-ink/10 text-left text-sm">
            <thead className="bg-ink/5 text-ink/60">
              <tr>
                <th className="px-4 py-3 font-medium">Name</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 font-medium">Image</th>
                <th className="px-4 py-3 font-medium">CPU%</th>
                <th className="px-4 py-3 font-medium">RAM%</th>
                <th className="px-4 py-3 font-medium">Signals</th>
                <th className="px-4 py-3 font-medium">Uptime</th>
                <th className="px-4 py-3 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-ink/10 bg-white">
              {filteredServices.map((service) => (
                <ServiceRow
                  key={service.service_id}
                  service={service}
                  samples={sparklineByServiceId.get(service.service_id) ?? []}
                  busy={busyServiceId === service.service_id && actionMutation.isPending}
                  onAction={(action) => actionMutation.mutate({ serviceId: service.service_id, action })}
                />
              ))}
              {!servicesQuery.isLoading && !filteredServices.length ? (
                <tr>
                  <td colSpan={8} className="px-4 py-8 text-center text-ink/55">
                    No services match the current search yet.
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}

function ServiceRow({
  service,
  samples,
  busy,
  onAction,
}: {
  service: ServiceSummary;
  samples: ServiceMetricSample[];
  busy: boolean;
  onAction: (action: "start" | "stop" | "restart" | "redeploy" | "delete") => void;
}) {
  const sparklines = buildServiceSparklines(samples);

  return (
    <tr>
      <td className="px-4 py-4">
        <Link to={`/services/${service.service_id}`} className="font-medium text-ink hover:text-slate">
          {service.name}
        </Link>
        <div className="text-xs text-ink/50">{service.domain || service.slug}</div>
      </td>
      <td className="px-4 py-4">
        <Badge tone={statusTone(service.status)}>{service.status}</Badge>
      </td>
      <td className="px-4 py-4 text-ink/70">{service.image}</td>
      <td className="px-4 py-4 text-ink/70">{formatPercent(service.cpu_percent)}</td>
      <td className="px-4 py-4 text-ink/70">{formatPercent(service.memory_percent)}</td>
      <td className="px-4 py-4">
        <div className="grid w-[220px] grid-cols-2 gap-2">
          <MiniSparkline label="CPU" samples={sparklines.cpu} tone="text-coral" />
          <MiniSparkline label="RAM" samples={sparklines.memory} tone="text-cyan" />
          <MiniSparkline label="Net" samples={sparklines.network} tone="text-moss" />
          <MiniSparkline label="Disk" samples={sparklines.disk} tone="text-slate" />
        </div>
      </td>
      <td className="px-4 py-4 text-ink/70">{formatUptime(service.uptime_seconds)}</td>
      <td className="px-4 py-4">
        <div className="flex flex-wrap gap-2">
          <Button size="sm" variant="secondary" disabled={busy} onClick={() => onAction("start")}>
            Start
          </Button>
          <Button size="sm" variant="secondary" disabled={busy} onClick={() => onAction("stop")}>
            Stop
          </Button>
          <Button size="sm" variant="secondary" disabled={busy} onClick={() => onAction("restart")}>
            Restart
          </Button>
          <Button size="sm" variant="ghost" disabled={busy} onClick={() => onAction("redeploy")}>
            Redeploy
          </Button>
          <Button size="sm" variant="ghost" className="text-coral" disabled={busy} onClick={() => onAction("delete")}>
            <Trash2 className="mr-2 h-4 w-4" />
            Delete
          </Button>
        </div>
      </td>
    </tr>
  );
}

function buildServiceSparklines(samples: ServiceMetricSample[]) {
  const cpu: SparklineSample[] = samples.map((sample) => ({
    timestamp: sample.timestamp,
    value: sample.cpu_percent,
  }));
  const memory: SparklineSample[] = samples.map((sample) => ({
    timestamp: sample.timestamp,
    value: sample.memory_percent,
  }));
  const network: SparklineSample[] = samples.map((sample, index) => {
    if (index === 0) {
      return { timestamp: sample.timestamp, value: 0 };
    }
    const previous = samples[index - 1];
    const deltaSeconds = Math.max((new Date(sample.timestamp).getTime() - new Date(previous.timestamp).getTime()) / 1000, 1);
    return {
      timestamp: sample.timestamp,
      value: Math.max(sample.network_rx_bytes - previous.network_rx_bytes, 0) / deltaSeconds,
    };
  });
  const disk: SparklineSample[] = samples.map((sample, index) => {
    if (index === 0) {
      return { timestamp: sample.timestamp, value: 0 };
    }
    const previous = samples[index - 1];
    const deltaSeconds = Math.max((new Date(sample.timestamp).getTime() - new Date(previous.timestamp).getTime()) / 1000, 1);
    const currentTotal = sample.block_read_bytes + sample.block_write_bytes;
    const previousTotal = previous.block_read_bytes + previous.block_write_bytes;
    return {
      timestamp: sample.timestamp,
      value: Math.max(currentTotal - previousTotal, 0) / deltaSeconds,
    };
  });

  return { cpu, memory, network, disk };
}

function MiniSparkline({
  label,
  samples,
  tone,
}: {
  label: string;
  samples: SparklineSample[];
  tone: string;
}) {
  return (
    <div className="rounded-2xl border border-ink/10 bg-mist/70 px-2 py-2">
      <p className="mb-1 text-[10px] uppercase tracking-[0.18em] text-ink/45">{label}</p>
      <Sparkline samples={samples} strokeClassName={tone} />
    </div>
  );
}
