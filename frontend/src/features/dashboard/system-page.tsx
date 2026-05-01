import { useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Cpu, Database, HardDrive, ImageIcon, Layers3, RefreshCw, Server, Trash2 } from "lucide-react";
import { Link } from "react-router-dom";

import { SystemService } from "@/api/generated";
import type { HostSummary, ImageSummary, PruneTarget } from "@/api/generated";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { queryClient } from "@/lib/query-client";

const PRUNE_TARGETS: { id: PruneTarget; label: string; description: string }[] = [
  { id: "containers", label: "Stopped containers", description: "Remove all stopped containers." },
  { id: "images", label: "Dangling images", description: "Remove untagged images." },
  { id: "volumes", label: "Unused volumes", description: "Remove volumes not referenced by containers." },
  { id: "builder", label: "Builder cache", description: "Remove BuildKit caches." },
];

function formatBytes(value?: number | null) {
  if (value == null) {
    return "--";
  }
  const units = ["B", "KB", "MB", "GB", "TB"];
  let current = Math.max(value, 0);
  let unitIndex = 0;
  while (current >= 1024 && unitIndex < units.length - 1) {
    current /= 1024;
    unitIndex += 1;
  }
  return `${current.toFixed(current >= 10 ? 0 : 1)} ${units[unitIndex]}`;
}

function formatDateTime(value: string | null | undefined) {
  if (!value) return "--";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}

export function SystemPage() {
  const hostQuery = useQuery({ queryKey: ["system", "host"], queryFn: SystemService.host });
  const imagesQuery = useQuery({ queryKey: ["system", "images"], queryFn: SystemService.images });
  const volumesQuery = useQuery({ queryKey: ["inventory", "volumes"], queryFn: SystemService.volumes });
  const networksQuery = useQuery({ queryKey: ["inventory", "networks"], queryFn: SystemService.networks });

  const [pruneSelection, setPruneSelection] = useState<Set<PruneTarget>>(
    () => new Set<PruneTarget>(["containers", "images", "builder"]),
  );
  const [imageFilter, setImageFilter] = useState("");

  const pruneMutation = useMutation({
    mutationFn: (targets: PruneTarget[]) => SystemService.prune({ targets }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["system", "host"] });
      queryClient.invalidateQueries({ queryKey: ["system", "images"] });
      queryClient.invalidateQueries({ queryKey: ["inventory", "volumes"] });
      queryClient.invalidateQueries({ queryKey: ["inventory", "networks"] });
    },
  });

  const deleteImageMutation = useMutation({
    mutationFn: (variables: { imageId: string; force: boolean }) =>
      SystemService.deleteImage(variables.imageId, variables.force),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["system", "images"] });
    },
  });

  const togglePruneTarget = (target: PruneTarget) => {
    setPruneSelection((current) => {
      const next = new Set(current);
      if (next.has(target)) {
        next.delete(target);
      } else {
        next.add(target);
      }
      return next;
    });
  };

  const filteredImages = useMemo(() => {
    const term = imageFilter.trim().toLowerCase();
    const data = imagesQuery.data ?? [];
    if (!term) return data;
    return data.filter((image) => {
      const haystack = [image.short_id, ...(image.tags ?? [])].join(" ").toLowerCase();
      return haystack.includes(term);
    });
  }, [imageFilter, imagesQuery.data]);

  const pruneError =
    pruneMutation.error instanceof Error ? pruneMutation.error.message : null;
  const deleteError =
    deleteImageMutation.error instanceof Error ? deleteImageMutation.error.message : null;

  return (
    <div className="grid gap-6">
      <HostInfoCard host={hostQuery.data} isLoading={hostQuery.isLoading} onRefresh={() => hostQuery.refetch()} />

      <Card className="rounded-[32px]">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-sm uppercase tracking-[0.2em] text-ink/45">System maintenance</p>
            <h3 className="mt-2 text-2xl font-semibold">Reclaim disk space</h3>
            <p className="mt-2 max-w-2xl text-sm text-ink/65">
              Pick what to prune. The Docker daemon only deletes objects that aren&apos;t in use, so
              running services are safe.
            </p>
          </div>
          <Button
            onClick={() => pruneMutation.mutate(Array.from(pruneSelection))}
            disabled={pruneSelection.size === 0 || pruneMutation.isPending}
            className="gap-2"
          >
            {pruneMutation.isPending ? "Pruning..." : "Run prune"}
          </Button>
        </div>

        <div className="mt-5 grid gap-3 md:grid-cols-2">
          {PRUNE_TARGETS.map((target) => {
            const checked = pruneSelection.has(target.id);
            return (
              <label
                key={target.id}
                className="flex cursor-pointer items-start gap-3 rounded-2xl border border-ink/10 bg-mist/70 p-4"
              >
                <input
                  type="checkbox"
                  checked={checked}
                  onChange={() => togglePruneTarget(target.id)}
                  className="mt-1 h-4 w-4 accent-ink"
                />
                <div>
                  <p className="text-sm font-semibold">{target.label}</p>
                  <p className="text-xs text-ink/55">{target.description}</p>
                </div>
              </label>
            );
          })}
        </div>

        {pruneError ? (
          <p className="mt-4 rounded-2xl bg-coral/10 px-4 py-3 text-sm text-coral">{pruneError}</p>
        ) : null}

        {pruneMutation.data ? <PruneResult result={pruneMutation.data} /> : null}
      </Card>

      <Card className="rounded-[32px]">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-sm uppercase tracking-[0.2em] text-ink/45">Images</p>
            <h3 className="mt-2 text-2xl font-semibold">Local image inventory</h3>
            <p className="mt-2 max-w-xl text-sm text-ink/65">
              Force-delete is required when an image is currently used by a container. Tagged
              service images are listed first.
            </p>
          </div>
          <div className="flex flex-wrap gap-3">
            <Input
              value={imageFilter}
              onChange={(event) => setImageFilter(event.target.value)}
              placeholder="Filter tag or id..."
              className="w-[260px]"
            />
            <Button variant="secondary" className="gap-2" onClick={() => imagesQuery.refetch()}>
              <RefreshCw className="h-4 w-4" /> Refresh
            </Button>
          </div>
        </div>

        {deleteError ? (
          <p className="mt-4 rounded-2xl bg-coral/10 px-4 py-3 text-sm text-coral">{deleteError}</p>
        ) : null}

        <div className="mt-6 overflow-hidden rounded-[28px] border border-ink/10">
          <table className="min-w-full divide-y divide-ink/10 text-left text-sm">
            <thead className="bg-ink/5 text-ink/60">
              <tr>
                <th className="px-4 py-3 font-medium">Tags / id</th>
                <th className="px-4 py-3 font-medium">Size</th>
                <th className="px-4 py-3 font-medium">Created</th>
                <th className="px-4 py-3 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-ink/10 bg-white">
              {filteredImages.map((image) => (
                <ImageRow
                  key={image.id}
                  image={image}
                  onDelete={(force) => deleteImageMutation.mutate({ imageId: image.id, force })}
                  busy={
                    deleteImageMutation.isPending && deleteImageMutation.variables?.imageId === image.id
                  }
                />
              ))}
              {!imagesQuery.isLoading && !filteredImages.length ? (
                <tr>
                  <td colSpan={4} className="px-4 py-8 text-center text-ink/55">
                    No images match the current filter.
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </Card>

      <div className="grid gap-6 xl:grid-cols-2">
        <InventorySummary
          title="Volumes"
          icon={Database}
          count={volumesQuery.data?.length ?? 0}
          link="/volumes"
          rows={(volumesQuery.data ?? []).slice(0, 5).map((volume) => ({
            primary: volume.name,
            secondary: `${volume.driver} - ${volume.mountpoint}`,
            badge: volume.ref_count != null ? `${volume.ref_count} ref` : undefined,
          }))}
          isLoading={volumesQuery.isLoading}
        />
        <InventorySummary
          title="Networks"
          icon={Layers3}
          count={networksQuery.data?.length ?? 0}
          link="/networks"
          rows={(networksQuery.data ?? []).slice(0, 5).map((network) => ({
            primary: network.name,
            secondary: `${network.driver} - ${network.scope}`,
            badge: `${network.containers} svc`,
          }))}
          isLoading={networksQuery.isLoading}
        />
      </div>
    </div>
  );
}

function HostInfoCard({
  host,
  isLoading,
  onRefresh,
}: {
  host: HostSummary | undefined;
  isLoading: boolean;
  onRefresh: () => void;
}) {
  return (
    <Card className="rounded-[32px]">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="text-sm uppercase tracking-[0.2em] text-ink/45">Host</p>
          <h3 className="mt-2 text-2xl font-semibold">{host?.name ?? "Docker host"}</h3>
          <p className="mt-1 text-sm text-ink/65">
            {host?.operating_system ?? (isLoading ? "Loading..." : "Unknown OS")}
            {host?.architecture ? ` (${host.architecture})` : ""}
          </p>
        </div>
        <Button variant="secondary" onClick={onRefresh} className="gap-2">
          <RefreshCw className="h-4 w-4" /> Refresh
        </Button>
      </div>

      <div className="mt-6 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <Stat
          icon={Cpu}
          label="CPU cores"
          value={host?.cpu_count != null ? String(host.cpu_count) : "--"}
        />
        <Stat
          icon={Layers3}
          label="Memory"
          value={formatBytes(host?.memory_total_bytes)}
        />
        <Stat
          icon={HardDrive}
          label="Disk free"
          value={
            host?.disk
              ? `${formatBytes(host.disk.free_bytes)} / ${formatBytes(host.disk.total_bytes)}`
              : "--"
          }
          hint={host?.disk?.mountpoint}
        />
        <Stat
          icon={Server}
          label="Engine"
          value={host?.docker_version ?? "--"}
          hint={host?.kernel_version ?? undefined}
        />
      </div>

      <div className="mt-6 grid gap-3 md:grid-cols-4">
        <CountPill label="Containers" value={host?.containers_total} tone="info" />
        <CountPill label="Running" value={host?.containers_running} tone="success" />
        <CountPill label="Stopped" value={host?.containers_stopped} tone="neutral" />
        <CountPill label="Images" value={host?.images_total} tone="warning" />
      </div>
    </Card>
  );
}

function Stat({
  icon: Icon,
  label,
  value,
  hint,
}: {
  icon: typeof Cpu;
  label: string;
  value: string;
  hint?: string;
}) {
  return (
    <div className="rounded-[24px] border border-ink/10 bg-mist/70 p-4">
      <div className="flex items-center gap-3">
        <div className="rounded-2xl bg-cyan/20 p-2 text-slate">
          <Icon className="h-4 w-4" />
        </div>
        <p className="text-xs uppercase tracking-[0.18em] text-ink/45">{label}</p>
      </div>
      <p className="mt-3 text-lg font-semibold">{value}</p>
      {hint ? <p className="mt-1 text-xs text-ink/55">{hint}</p> : null}
    </div>
  );
}

function CountPill({
  label,
  value,
  tone,
}: {
  label: string;
  value: number | null | undefined;
  tone: "success" | "warning" | "info" | "neutral";
}) {
  return (
    <div className="rounded-2xl border border-ink/10 bg-mist/70 p-4">
      <div className="flex items-center justify-between">
        <p className="text-xs uppercase tracking-[0.18em] text-ink/45">{label}</p>
        <Badge tone={tone}>{value ?? 0}</Badge>
      </div>
    </div>
  );
}

function ImageRow({
  image,
  onDelete,
  busy,
}: {
  image: ImageSummary;
  onDelete: (force: boolean) => void;
  busy: boolean;
}) {
  return (
    <tr>
      <td className="px-4 py-4">
        {image.tags.length ? (
          <div className="flex flex-wrap gap-2">
            {image.tags.map((tag) => (
              <Badge key={tag} tone="info">
                {tag}
              </Badge>
            ))}
          </div>
        ) : (
          <Badge tone="neutral">{image.short_id}</Badge>
        )}
        <p className="mt-1 text-xs text-ink/45">{image.short_id}</p>
      </td>
      <td className="px-4 py-4 text-ink/70">{formatBytes(image.size)}</td>
      <td className="px-4 py-4 text-ink/70">{formatDateTime(image.created)}</td>
      <td className="px-4 py-4">
        <div className="flex flex-wrap gap-2">
          <Button size="sm" variant="ghost" disabled={busy} onClick={() => onDelete(false)}>
            <Trash2 className="mr-2 h-4 w-4" />
            Remove
          </Button>
          <Button size="sm" variant="ghost" className="text-coral" disabled={busy} onClick={() => onDelete(true)}>
            Force
          </Button>
        </div>
      </td>
    </tr>
  );
}

function PruneResult({ result }: { result: Record<string, unknown> }) {
  const sections: { label: string; reclaimed: number | undefined; deleted: number }[] = [];
  const containers = result.containers as { ContainersDeleted?: string[] | null; SpaceReclaimed?: number } | undefined;
  if (containers) {
    sections.push({
      label: "Containers",
      reclaimed: containers.SpaceReclaimed,
      deleted: containers.ContainersDeleted?.length ?? 0,
    });
  }
  const images = result.images as { ImagesDeleted?: unknown[] | null; SpaceReclaimed?: number } | undefined;
  if (images) {
    sections.push({
      label: "Images",
      reclaimed: images.SpaceReclaimed,
      deleted: images.ImagesDeleted?.length ?? 0,
    });
  }
  const volumes = result.volumes as { VolumesDeleted?: string[] | null; SpaceReclaimed?: number } | undefined;
  if (volumes) {
    sections.push({
      label: "Volumes",
      reclaimed: volumes.SpaceReclaimed,
      deleted: volumes.VolumesDeleted?.length ?? 0,
    });
  }
  const builder = result.builder_cache as
    | { CachesDeleted?: string[] | null; SpaceReclaimed?: number; warning?: string }
    | undefined;
  if (builder) {
    sections.push({
      label: "Builder cache",
      reclaimed: builder.SpaceReclaimed,
      deleted: builder.CachesDeleted?.length ?? 0,
    });
  }

  return (
    <div className="mt-5 rounded-2xl border border-moss/30 bg-moss/10 p-4">
      <p className="text-sm font-semibold text-slate">Prune complete</p>
      <div className="mt-2 grid gap-2 md:grid-cols-2">
        {sections.map((section) => (
          <div key={section.label} className="text-sm text-ink/70">
            <span className="font-medium">{section.label}:</span> {section.deleted} removed,{" "}
            {formatBytes(section.reclaimed ?? 0)} reclaimed
          </div>
        ))}
      </div>
    </div>
  );
}

function InventorySummary({
  title,
  icon: Icon,
  count,
  link,
  rows,
  isLoading,
}: {
  title: string;
  icon: typeof ImageIcon;
  count: number;
  link: string;
  rows: { primary: string; secondary: string; badge?: string }[];
  isLoading: boolean;
}) {
  return (
    <Card className="rounded-[32px]">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="rounded-2xl bg-cyan/20 p-2 text-slate">
            <Icon className="h-4 w-4" />
          </div>
          <div>
            <p className="text-sm uppercase tracking-[0.2em] text-ink/45">{title}</p>
            <h3 className="mt-1 text-xl font-semibold">{count} total</h3>
          </div>
        </div>
        <Link to={link}>
          <Button variant="secondary" size="sm">
            Manage
          </Button>
        </Link>
      </div>
      <div className="mt-4 space-y-2">
        {isLoading ? <p className="text-sm text-ink/55">Loading...</p> : null}
        {!isLoading && !rows.length ? (
          <p className="text-sm text-ink/55">Nothing to show yet.</p>
        ) : null}
        {rows.map((row) => (
          <div
            key={row.primary}
            className="flex items-center justify-between gap-3 rounded-2xl border border-ink/10 bg-mist/70 px-4 py-3"
          >
            <div className="min-w-0">
              <p className="truncate text-sm font-semibold">{row.primary}</p>
              <p className="truncate text-xs text-ink/55">{row.secondary}</p>
            </div>
            {row.badge ? <Badge tone="neutral">{row.badge}</Badge> : null}
          </div>
        ))}
      </div>
    </Card>
  );
}
