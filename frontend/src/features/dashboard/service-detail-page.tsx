import type { ReactNode } from "react";
import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { Activity, ArrowLeft, Box, Clock3, Layers3, PlugZap } from "lucide-react";
import { Link, useParams, useSearchParams } from "react-router-dom";

import { ServicesService } from "@/api/generated";
import type { DeployResponse, ServiceDetailResponse, ServiceEnvEntry, ServiceMetricSample } from "@/api/generated";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

const tabs = [
  { id: "overview", label: "Overview" },
  { id: "logs", label: "Logs" },
  { id: "metrics", label: "Metrics" },
  { id: "env", label: "Env" },
  { id: "volumes", label: "Volumes" },
  { id: "settings", label: "Settings" },
  { id: "deploys", label: "Deploys" },
] as const;

type TabId = (typeof tabs)[number]["id"];

function formatPercent(value?: number | null) {
  return value == null ? "--" : `${value.toFixed(1)}%`;
}

function formatBytes(value?: number | null) {
  if (value == null) {
    return "--";
  }
  const units = ["B", "KB", "MB", "GB", "TB"];
  let current = value;
  let unitIndex = 0;
  while (current >= 1024 && unitIndex < units.length - 1) {
    current /= 1024;
    unitIndex += 1;
  }
  return `${current.toFixed(current >= 10 ? 0 : 1)} ${units[unitIndex]}`;
}

function formatDateTime(value: string) {
  return new Date(value).toLocaleString();
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
  if (hours < 24) {
    return `${hours}h ${remainder}m`;
  }
  const days = Math.floor(hours / 24);
  return `${days}d ${hours % 24}h`;
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

export function ServiceDetailPage() {
  const params = useParams<{ serviceId: string }>();
  const [searchParams, setSearchParams] = useSearchParams();
  const serviceId = params.serviceId ?? "";
  const activeTab = (searchParams.get("tab") as TabId | null) ?? "overview";

  const detailQuery = useQuery({
    queryKey: ["services", "detail", serviceId],
    queryFn: () => ServicesService.detail(serviceId),
  });
  const deploysQuery = useQuery({
    queryKey: ["services", "deploys", serviceId],
    queryFn: () => ServicesService.listDeploys(serviceId),
  });
  const envQuery = useQuery({
    queryKey: ["services", "env", serviceId],
    queryFn: () => ServicesService.listEnv(serviceId),
  });
  const metricsQuery = useQuery({
    queryKey: ["services", "metrics", serviceId, "5m"],
    queryFn: () => ServicesService.metrics(serviceId, "5m"),
  });

  const latestMetric = useMemo(() => {
    const samples = metricsQuery.data ?? [];
    return samples.length ? samples[samples.length - 1] : null;
  }, [metricsQuery.data]);

  if (detailQuery.isLoading) {
    return (
      <Card className="rounded-[32px]">
        <p className="text-sm uppercase tracking-[0.2em] text-ink/45">Loading service detail</p>
        <h3 className="mt-3 text-2xl font-semibold">Pulling service state, deploys, env, and recent events...</h3>
      </Card>
    );
  }

  if (detailQuery.isError || !detailQuery.data) {
    return (
      <Card className="rounded-[32px]">
        <p className="text-sm uppercase tracking-[0.2em] text-coral">Service unavailable</p>
        <h3 className="mt-3 text-2xl font-semibold">We could not load this service.</h3>
        <p className="mt-2 text-sm text-ink/65">
          {detailQuery.error instanceof Error ? detailQuery.error.message : "Unknown error."}
        </p>
        <Button variant="secondary" className="mt-5" onClick={() => window.history.back()}>
          Back
        </Button>
      </Card>
    );
  }

  const service = detailQuery.data;

  return (
    <div className="grid gap-6">
      <Card className="rounded-[32px]">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <Link to="/services" className="inline-flex items-center gap-2 text-sm text-ink/55 hover:text-ink">
              <ArrowLeft className="h-4 w-4" />
              Back to services
            </Link>
            <div className="mt-4 flex flex-wrap items-center gap-3">
              <h3 className="text-3xl font-semibold">{service.name}</h3>
              <Badge tone={statusTone(service.status)}>{service.status}</Badge>
            </div>
            <p className="mt-2 text-sm text-ink/65">{service.image} {service.domain ? ` - ${service.domain}` : ` - ${service.slug}`}</p>
          </div>
          <div className="grid gap-3 sm:grid-cols-3">
            <StatPill label="CPU" value={formatPercent(service.cpu_percent)} icon={Activity} />
            <StatPill label="RAM" value={formatPercent(service.memory_percent)} icon={Layers3} />
            <StatPill label="Uptime" value={formatUptime(service.uptime_seconds)} icon={Clock3} />
          </div>
        </div>

        <div className="mt-6 flex flex-wrap gap-2">
          {tabs.map((tab) => (
            <Button
              key={tab.id}
              variant={activeTab === tab.id ? "primary" : "secondary"}
              size="sm"
              onClick={() => setSearchParams({ tab: tab.id })}
            >
              {tab.label}
            </Button>
          ))}
        </div>
      </Card>

      {activeTab === "overview" ? <OverviewTab service={service} latestMetric={latestMetric} /> : null}
      {activeTab === "logs" ? <LogsTab /> : null}
      {activeTab === "metrics" ? <MetricsTab samples={metricsQuery.data ?? []} /> : null}
      {activeTab === "env" ? <EnvTab entries={envQuery.data ?? []} isLoading={envQuery.isLoading} /> : null}
      {activeTab === "volumes" ? <VolumesTab service={service} /> : null}
      {activeTab === "settings" ? <SettingsTab service={service} /> : null}
      {activeTab === "deploys" ? <DeploysTab deploys={deploysQuery.data ?? []} isLoading={deploysQuery.isLoading} /> : null}
    </div>
  );
}

function StatPill({
  label,
  value,
  icon: Icon,
}: {
  label: string;
  value: string;
  icon: typeof Activity;
}) {
  return (
    <div className="rounded-[24px] border border-ink/10 bg-mist/80 px-4 py-3">
      <div className="flex items-center justify-between gap-4">
        <div>
          <p className="text-xs uppercase tracking-[0.18em] text-ink/45">{label}</p>
          <p className="mt-2 text-lg font-semibold">{value}</p>
        </div>
        <div className="rounded-2xl bg-cyan/20 p-3 text-slate">
          <Icon className="h-4 w-4" />
        </div>
      </div>
    </div>
  );
}

function OverviewTab({
  service,
  latestMetric,
}: {
  service: ServiceDetailResponse;
  latestMetric: ServiceMetricSample | null;
}) {
  return (
    <div className="grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
      <Card className="rounded-[32px]">
        <p className="text-sm uppercase tracking-[0.2em] text-ink/45">Overview</p>
        <div className="mt-5 grid gap-4 md:grid-cols-2">
          <InfoRow label="Project" value={service.project_name ?? service.project_id} />
          <InfoRow label="Image" value={service.image} />
          <InfoRow label="Domain" value={service.domain ?? "Not attached"} />
          <InfoRow label="Network" value={service.network ?? "Default bridge"} />
          <InfoRow label="Created" value={formatDateTime(service.created_at)} />
          <InfoRow label="Updated" value={formatDateTime(service.updated_at)} />
        </div>

        <div className="mt-6 grid gap-4 md:grid-cols-2">
          <MiniCard title="Ports" icon={PlugZap}>
            {service.ports.length ? (
              service.ports.map((port) => (
                <p key={`${port.container_port}-${port.host_port}`} className="text-sm text-ink/70">
                  {port.host_port ?? "auto"} -> {port.container_port}
                </p>
              ))
            ) : (
              <p className="text-sm text-ink/55">No explicit port bindings.</p>
            )}
          </MiniCard>
          <MiniCard title="Latest metric snapshot" icon={Activity}>
            {latestMetric ? (
              <div className="space-y-2 text-sm text-ink/70">
                <p>CPU: {formatPercent(latestMetric.cpu_percent)}</p>
                <p>RAM: {formatPercent(latestMetric.memory_percent)}</p>
                <p>RX/TX: {formatBytes(latestMetric.network_rx_bytes)} / {formatBytes(latestMetric.network_tx_bytes)}</p>
              </div>
            ) : (
              <p className="text-sm text-ink/55">No metrics sampled yet.</p>
            )}
          </MiniCard>
        </div>
      </Card>

      <Card className="rounded-[32px]">
        <p className="text-sm uppercase tracking-[0.2em] text-ink/45">Recent events</p>
        <div className="mt-5 space-y-4">
          {service.recent_events.length ? (
            service.recent_events.map((event) => (
              <div key={event.event_id} className="rounded-[24px] border border-ink/10 bg-mist/75 p-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <p className="font-medium">{event.action}</p>
                  <p className="text-xs uppercase tracking-[0.18em] text-ink/45">{formatDateTime(event.created_at)}</p>
                </div>
                <p className="mt-2 text-sm text-ink/60">{event.actor_name ?? "System actor"}</p>
                {Object.keys(event.details).length ? (
                  <pre className="mt-3 overflow-x-auto rounded-2xl bg-white/75 p-3 text-xs text-ink/70">
                    {JSON.stringify(event.details, null, 2)}
                  </pre>
                ) : null}
              </div>
            ))
          ) : (
            <p className="text-sm text-ink/55">No recent service events were recorded yet.</p>
          )}
        </div>
      </Card>
    </div>
  );
}

function LogsTab() {
  return (
    <Card className="rounded-[32px]">
      <p className="text-sm uppercase tracking-[0.2em] text-ink/45">Logs</p>
      <h4 className="mt-3 text-2xl font-semibold">Live log console lands on Day 18</h4>
      <p className="mt-3 max-w-2xl text-sm text-ink/65">
        This tab is intentionally in place now so the detail view has the final navigation shape.
        The next day adds the websocket consumer, tail controls, and searchable log stream.
      </p>
    </Card>
  );
}

function MetricsTab({ samples }: { samples: ServiceMetricSample[] }) {
  const latest = samples.length ? samples[samples.length - 1] : null;

  return (
    <div className="grid gap-6 lg:grid-cols-[0.9fr_1.1fr]">
      <Card className="rounded-[32px]">
        <p className="text-sm uppercase tracking-[0.2em] text-ink/45">Metrics snapshot</p>
        {latest ? (
          <div className="mt-5 grid gap-4 sm:grid-cols-2">
            <InfoRow label="CPU" value={formatPercent(latest.cpu_percent)} />
            <InfoRow label="Memory" value={formatPercent(latest.memory_percent)} />
            <InfoRow label="Memory used" value={formatBytes(latest.memory_usage_bytes)} />
            <InfoRow label="Memory limit" value={formatBytes(latest.memory_limit_bytes)} />
            <InfoRow label="Network RX" value={formatBytes(latest.network_rx_bytes)} />
            <InfoRow label="Network TX" value={formatBytes(latest.network_tx_bytes)} />
          </div>
        ) : (
          <p className="mt-4 text-sm text-ink/55">No metric samples are available for the last 5 minutes.</p>
        )}
      </Card>

      <Card className="rounded-[32px]">
        <p className="text-sm uppercase tracking-[0.2em] text-ink/45">Recent samples</p>
        <div className="mt-5 space-y-3">
          {samples.slice(-8).reverse().map((sample) => (
            <div key={sample.timestamp} className="rounded-[24px] border border-ink/10 bg-mist/75 p-4 text-sm text-ink/70">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <p className="font-medium">{formatDateTime(sample.timestamp)}</p>
                <p>{formatPercent(sample.cpu_percent)} CPU - {formatPercent(sample.memory_percent)} RAM</p>
              </div>
            </div>
          ))}
          {!samples.length ? <p className="text-sm text-ink/55">No samples available yet.</p> : null}
        </div>
        <p className="mt-5 text-sm text-ink/55">
          Full live charts arrive on Day 19. This tab already shows the API-backed metric history for the service.
        </p>
      </Card>
    </div>
  );
}

function EnvTab({ entries, isLoading }: { entries: ServiceEnvEntry[]; isLoading: boolean }) {
  return (
    <Card className="rounded-[32px]">
      <p className="text-sm uppercase tracking-[0.2em] text-ink/45">Environment</p>
      <div className="mt-5 space-y-3">
        {isLoading ? <p className="text-sm text-ink/55">Loading environment entries...</p> : null}
        {!isLoading && !entries.length ? <p className="text-sm text-ink/55">No env entries saved for this service.</p> : null}
        {entries.map((entry) => (
          <div key={entry.key} className="flex flex-wrap items-center justify-between gap-4 rounded-[24px] border border-ink/10 bg-mist/75 p-4">
            <div>
              <p className="font-medium">{entry.key}</p>
              <p className="mt-1 text-sm text-ink/60">
                {entry.is_secret ? "Secret value hidden" : entry.value ?? "Empty value"}
              </p>
            </div>
            <Badge tone={entry.is_secret ? "warning" : "neutral"}>{entry.is_secret ? "Secret" : "Plain"}</Badge>
          </div>
        ))}
      </div>
    </Card>
  );
}

function VolumesTab({ service }: { service: ServiceDetailResponse }) {
  return (
    <Card className="rounded-[32px]">
      <p className="text-sm uppercase tracking-[0.2em] text-ink/45">Volumes</p>
      <div className="mt-5 space-y-3">
        {service.volumes.length ? (
          service.volumes.map((volume) => (
            <div key={`${volume.source}-${volume.target}`} className="rounded-[24px] border border-ink/10 bg-mist/75 p-4">
              <p className="font-medium">{volume.source}</p>
              <p className="mt-1 text-sm text-ink/60">{volume.target} - {volume.mode ?? "rw"}</p>
            </div>
          ))
        ) : (
          <p className="text-sm text-ink/55">This service is not currently using named volume mounts.</p>
        )}
      </div>
    </Card>
  );
}

function SettingsTab({ service }: { service: ServiceDetailResponse }) {
  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <Card className="rounded-[32px]">
        <p className="text-sm uppercase tracking-[0.2em] text-ink/45">Runtime policy</p>
        <div className="mt-5 grid gap-4">
          <InfoRow label="Restart policy" value={service.restart_policy ?? "Not set"} />
          <InfoRow label="Network" value={service.network ?? "Default bridge"} />
          <InfoRow label="Domain" value={service.domain ?? "No routed domain"} />
        </div>
      </Card>
      <Card className="rounded-[32px]">
        <p className="text-sm uppercase tracking-[0.2em] text-ink/45">Health check</p>
        {service.healthcheck ? (
          <pre className="mt-5 overflow-x-auto rounded-[24px] bg-ink p-4 text-sm text-mist/90">
            {JSON.stringify(service.healthcheck, null, 2)}
          </pre>
        ) : (
          <p className="mt-5 text-sm text-ink/55">No healthcheck has been configured for this service.</p>
        )}
      </Card>
    </div>
  );
}

function DeploysTab({ deploys, isLoading }: { deploys: DeployResponse[]; isLoading: boolean }) {
  return (
    <Card className="rounded-[32px]">
      <p className="text-sm uppercase tracking-[0.2em] text-ink/45">Deploy history</p>
      <div className="mt-5 space-y-3">
        {isLoading ? <p className="text-sm text-ink/55">Loading deploy history...</p> : null}
        {!isLoading && !deploys.length ? <p className="text-sm text-ink/55">No deploy history recorded yet.</p> : null}
        {deploys.map((deploy) => (
          <div key={deploy.deploy_id} className="rounded-[24px] border border-ink/10 bg-mist/75 p-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <p className="font-medium">{deploy.source_type}</p>
              <Badge tone={statusTone(deploy.status)}>{deploy.status}</Badge>
            </div>
            <p className="mt-2 text-sm text-ink/60">{deploy.image_tag ?? deploy.source_ref ?? "No image reference"}</p>
          </div>
        ))}
      </div>
    </Card>
  );
}

function MiniCard({
  title,
  icon: Icon,
  children,
}: {
  title: string;
  icon: typeof Box;
  children: ReactNode;
}) {
  return (
    <div className="rounded-[24px] border border-ink/10 bg-mist/80 p-4">
      <div className="flex items-center gap-3">
        <div className="rounded-2xl bg-cyan/20 p-2 text-slate">
          <Icon className="h-4 w-4" />
        </div>
        <p className="font-medium">{title}</p>
      </div>
      <div className="mt-4">{children}</div>
    </div>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-[24px] border border-ink/10 bg-mist/80 p-4">
      <p className="text-xs uppercase tracking-[0.18em] text-ink/45">{label}</p>
      <p className="mt-2 text-sm font-medium text-ink/75">{value}</p>
    </div>
  );
}
