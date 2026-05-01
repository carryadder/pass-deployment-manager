import { startTransition, useEffect, useMemo, useState } from "react";
import { Activity, ArrowDownToLine, HardDrive, MemoryStick, Radio } from "lucide-react";
import { useQuery } from "@tanstack/react-query";

import { OpenAPI, ServicesService } from "@/api/generated";
import type { ServiceMetricSample } from "@/api/generated";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
  formatBytes,
  formatDateTime,
  formatPercent,
  Sparkline,
  type SparklineSample,
} from "@/features/dashboard/service-metrics-shared";
import { useAuthStore } from "@/stores/auth-store";

const rangeOptions = ["5m", "1h", "24h"] as const;
type MetricsRange = (typeof rangeOptions)[number];
type ConnectionState = "connecting" | "live" | "closed" | "error";

function buildMetricsSocketUrl(serviceId: string, range: MetricsRange, token: string | null) {
  const base = OpenAPI.BASE
    ? new URL(OpenAPI.BASE, window.location.origin)
    : new URL(window.location.origin);
  base.protocol = base.protocol === "https:" ? "wss:" : "ws:";
  base.pathname = `/api/services/${serviceId}/metrics`;
  base.searchParams.set("range", range);
  if (token) {
    base.searchParams.set("token", token);
  }
  return base.toString();
}

function useLiveMetrics(serviceId: string, range: MetricsRange) {
  const accessToken = useAuthStore((state) => state.accessToken);
  const [samples, setSamples] = useState<ServiceMetricSample[]>([]);
  const [connectionState, setConnectionState] = useState<ConnectionState>("connecting");
  const [connectionError, setConnectionError] = useState<string | null>(null);

  const metricsQuery = useQuery({
    queryKey: ["services", "metrics", serviceId, range],
    queryFn: () => ServicesService.metrics(serviceId, range),
  });

  useEffect(() => {
    if (metricsQuery.data) {
      setSamples(metricsQuery.data);
    }
  }, [metricsQuery.data]);

  useEffect(() => {
    if (!serviceId) {
      return;
    }

    const socket = new WebSocket(buildMetricsSocketUrl(serviceId, range, accessToken));

    setConnectionState("connecting");
    setConnectionError(null);

    socket.onopen = () => setConnectionState("live");
    socket.onmessage = (event) => {
      try {
        const sample = JSON.parse(String(event.data)) as ServiceMetricSample;
        startTransition(() => {
          setSamples((current) => {
            const next = [...current, sample];
            const deduped = next.filter(
              (item, index, all) => all.findIndex((candidate) => candidate.timestamp === item.timestamp) === index,
            );
            return deduped.slice(-240);
          });
        });
      } catch {
        setConnectionState("error");
        setConnectionError("Unable to parse live metrics sample.");
      }
    };
    socket.onerror = () => {
      setConnectionState("error");
      setConnectionError("The metrics websocket reported an error.");
    };
    socket.onclose = (event) => {
      if (!event.wasClean) {
        setConnectionState("error");
        setConnectionError(event.reason || "Live metrics connection closed unexpectedly.");
      } else {
        setConnectionState("closed");
      }
    };

    return () => {
      socket.close(1000, "cleanup");
    };
  }, [accessToken, range, serviceId]);

  return {
    samples,
    connectionState,
    connectionError,
    isLoading: metricsQuery.isLoading && !samples.length,
  };
}

function toNetworkRateSamples(samples: ServiceMetricSample[], key: "network_rx_bytes" | "network_tx_bytes"): SparklineSample[] {
  return samples.map((sample, index) => {
    if (index === 0) {
      return { timestamp: sample.timestamp, value: 0 };
    }
    const previous = samples[index - 1];
    const previousTime = new Date(previous.timestamp).getTime();
    const currentTime = new Date(sample.timestamp).getTime();
    const deltaSeconds = Math.max((currentTime - previousTime) / 1000, 1);
    const deltaBytes = Math.max(sample[key] - previous[key], 0);
    return {
      timestamp: sample.timestamp,
      value: deltaBytes / deltaSeconds,
    };
  });
}

function toDiskRateSamples(samples: ServiceMetricSample[]): SparklineSample[] {
  return samples.map((sample, index) => {
    if (index === 0) {
      return { timestamp: sample.timestamp, value: 0 };
    }
    const previous = samples[index - 1];
    const previousTime = new Date(previous.timestamp).getTime();
    const currentTime = new Date(sample.timestamp).getTime();
    const deltaSeconds = Math.max((currentTime - previousTime) / 1000, 1);
    const previousTotal = previous.block_read_bytes + previous.block_write_bytes;
    const currentTotal = sample.block_read_bytes + sample.block_write_bytes;
    return {
      timestamp: sample.timestamp,
      value: Math.max(currentTotal - previousTotal, 0) / deltaSeconds,
    };
  });
}

function metricCardTone(index: number) {
  return [
    "text-coral",
    "text-cyan",
    "text-moss",
    "text-slate",
  ][index] ?? "text-ink";
}

export function ServiceMetricsTab({ serviceId }: { serviceId: string }) {
  const [range, setRange] = useState<MetricsRange>("5m");
  const { samples, connectionState, connectionError, isLoading } = useLiveMetrics(serviceId, range);

  const cpuSeries = useMemo<SparklineSample[]>(
    () => samples.map((sample) => ({ timestamp: sample.timestamp, value: sample.cpu_percent })),
    [samples],
  );
  const memorySeries = useMemo<SparklineSample[]>(
    () => samples.map((sample) => ({ timestamp: sample.timestamp, value: sample.memory_percent })),
    [samples],
  );
  const rxSeries = useMemo(() => toNetworkRateSamples(samples, "network_rx_bytes"), [samples]);
  const diskSeries = useMemo(() => toDiskRateSamples(samples), [samples]);
  const latest = samples.length ? samples[samples.length - 1] : null;

  const summaryCards = [
    {
      label: "CPU",
      value: latest ? formatPercent(latest.cpu_percent) : "--",
      subtitle: "Live processor usage",
      icon: Activity,
      series: cpuSeries,
      strokeClassName: "text-coral",
    },
    {
      label: "Memory",
      value: latest ? formatPercent(latest.memory_percent) : "--",
      subtitle: latest ? `${formatBytes(latest.memory_usage_bytes)} used` : "Live memory pressure",
      icon: MemoryStick,
      series: memorySeries,
      strokeClassName: "text-cyan",
    },
    {
      label: "Ingress",
      value: latest && rxSeries.length ? `${formatBytes(rxSeries[rxSeries.length - 1].value)}/s` : "--",
      subtitle: "Recent receive rate",
      icon: ArrowDownToLine,
      series: rxSeries,
      strokeClassName: "text-moss",
    },
    {
      label: "Disk I/O",
      value: latest && diskSeries.length ? `${formatBytes(diskSeries[diskSeries.length - 1].value)}/s` : "--",
      subtitle: "Read + write throughput",
      icon: HardDrive,
      series: diskSeries,
      strokeClassName: "text-slate",
    },
  ];

  return (
    <div className="grid gap-6">
      <Card className="rounded-[32px]">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-sm uppercase tracking-[0.2em] text-ink/45">Metrics</p>
            <h4 className="mt-2 text-2xl font-semibold">Live performance charts</h4>
            <p className="mt-2 max-w-2xl text-sm text-ink/65">
              The detail view now holds live charts for CPU, memory, network, and disk I/O, and it keeps updating without a page refresh.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            {rangeOptions.map((option) => (
              <Button
                key={option}
                size="sm"
                variant={range === option ? "primary" : "secondary"}
                onClick={() => setRange(option)}
              >
                {option}
              </Button>
            ))}
            <div className="flex items-center gap-2 rounded-full bg-ink/5 px-4 py-2 text-sm text-ink/70">
              <Radio className="h-4 w-4" />
              {connectionState}
            </div>
          </div>
        </div>
        {connectionError ? (
          <p className="mt-4 rounded-2xl bg-coral/10 px-4 py-3 text-sm text-coral">{connectionError}</p>
        ) : null}
      </Card>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {summaryCards.map((card, index) => {
          const Icon = card.icon;
          return (
            <Card key={card.label} className="rounded-[28px]">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="text-xs uppercase tracking-[0.18em] text-ink/45">{card.label}</p>
                  <p className="mt-3 text-2xl font-semibold">{card.value}</p>
                  <p className="mt-2 text-sm text-ink/60">{card.subtitle}</p>
                </div>
                <div className={`rounded-2xl bg-ink/5 p-3 ${metricCardTone(index)}`}>
                  <Icon className="h-5 w-5" />
                </div>
              </div>
              <div className="mt-5">
                <Sparkline samples={card.series} strokeClassName={card.strokeClassName} />
              </div>
            </Card>
          );
        })}
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        <MetricChartCard
          title="CPU usage"
          subtitle="Percent across the selected range"
          latestValue={latest ? formatPercent(latest.cpu_percent) : "--"}
          samples={cpuSeries}
          strokeClassName="text-coral"
        />
        <MetricChartCard
          title="Memory pressure"
          subtitle="Percent of configured container memory"
          latestValue={latest ? formatPercent(latest.memory_percent) : "--"}
          samples={memorySeries}
          strokeClassName="text-cyan"
        />
        <MetricChartCard
          title="Network throughput"
          subtitle="Receive bytes per second"
          latestValue={latest && rxSeries.length ? `${formatBytes(rxSeries[rxSeries.length - 1].value)}/s` : "--"}
          samples={rxSeries}
          strokeClassName="text-moss"
        />
        <MetricChartCard
          title="Disk throughput"
          subtitle="Combined block read/write bytes per second"
          latestValue={latest && diskSeries.length ? `${formatBytes(diskSeries[diskSeries.length - 1].value)}/s` : "--"}
          samples={diskSeries}
          strokeClassName="text-slate"
        />
      </div>

      <Card className="rounded-[32px]">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <p className="text-sm uppercase tracking-[0.2em] text-ink/45">Recent samples</p>
            <h5 className="mt-2 text-xl font-semibold">Streaming metric feed</h5>
          </div>
          {latest ? (
            <Badge tone="info">Last sample: {formatDateTime(latest.timestamp)}</Badge>
          ) : null}
        </div>
        <div className="mt-5 space-y-3">
          {samples.slice(-10).reverse().map((sample) => (
            <div key={sample.timestamp} className="rounded-[24px] border border-ink/10 bg-mist/75 p-4 text-sm text-ink/70">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <p className="font-medium">{formatDateTime(sample.timestamp)}</p>
                <p>
                  {formatPercent(sample.cpu_percent)} CPU - {formatPercent(sample.memory_percent)} RAM
                </p>
              </div>
              <p className="mt-2">
                RX {formatBytes(sample.network_rx_bytes)} | TX {formatBytes(sample.network_tx_bytes)} | PIDs {sample.pids}
              </p>
            </div>
          ))}
          {!samples.length && !isLoading ? (
            <p className="text-sm text-ink/55">No metric samples are available yet for this service.</p>
          ) : null}
          {isLoading ? <p className="text-sm text-ink/55">Loading metric history...</p> : null}
        </div>
      </Card>
    </div>
  );
}

function MetricChartCard({
  title,
  subtitle,
  latestValue,
  samples,
  strokeClassName,
}: {
  title: string;
  subtitle: string;
  latestValue: string;
  samples: SparklineSample[];
  strokeClassName: string;
}) {
  return (
    <Card className="rounded-[32px]">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-sm uppercase tracking-[0.2em] text-ink/45">{title}</p>
          <h5 className="mt-2 text-2xl font-semibold">{latestValue}</h5>
          <p className="mt-2 text-sm text-ink/60">{subtitle}</p>
        </div>
      </div>
      <div className="mt-6 rounded-[24px] border border-ink/10 bg-white px-4 py-5">
        <Sparkline samples={samples} strokeClassName={strokeClassName} className="h-36" />
      </div>
    </Card>
  );
}
