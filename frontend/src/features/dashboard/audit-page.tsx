import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ChevronDown, ChevronUp, Filter, RefreshCw } from "lucide-react";
import { Link } from "react-router-dom";

import { AuditService } from "@/api/generated";
import type { AuditEntry, AuditQuery } from "@/api/generated";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

const RESOURCE_TYPES = [
  { value: "", label: "All resources" },
  { value: "service", label: "Services" },
  { value: "deploy", label: "Deploys" },
  { value: "user", label: "Users" },
  { value: "project", label: "Projects" },
  { value: "system", label: "System" },
  { value: "volume", label: "Volumes" },
  { value: "network", label: "Networks" },
  { value: "image", label: "Images" },
];

const PAGE_SIZE_DEFAULT = 50;

function actionTone(action: string): "success" | "warning" | "info" | "neutral" {
  if (action.endsWith(".delete") || action.includes("kill") || action.includes("stop")) {
    return "warning";
  }
  if (action.endsWith(".create") || action.endsWith(".start") || action.endsWith(".restart")) {
    return "success";
  }
  if (action.includes("env") || action.includes("redeploy") || action.includes("rollout")) {
    return "info";
  }
  return "neutral";
}

function formatRelative(value: string) {
  const created = new Date(value).getTime();
  if (Number.isNaN(created)) return value;
  const deltaMs = Date.now() - created;
  if (deltaMs < 0) return "just now";
  const seconds = Math.floor(deltaMs / 1000);
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

function formatDateTime(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}

function buildResourceLink(entry: AuditEntry): string | null {
  if (entry.resource_type === "service" && entry.resource_id) {
    return `/services/${entry.resource_id}`;
  }
  return null;
}

export function AuditPage() {
  const [resourceType, setResourceType] = useState("");
  const [actionFilter, setActionFilter] = useState("");
  const [resourceId, setResourceId] = useState("");
  const [pageOffset, setPageOffset] = useState(0);
  const limit = PAGE_SIZE_DEFAULT;

  const query: AuditQuery = useMemo(
    () => ({
      limit,
      offset: pageOffset,
      resource_type: resourceType || undefined,
      action: actionFilter.trim() || undefined,
      resource_id: resourceId.trim() || undefined,
    }),
    [actionFilter, limit, pageOffset, resourceId, resourceType],
  );

  const auditQuery = useQuery({
    queryKey: ["audit", query],
    queryFn: () => AuditService.list(query),
    placeholderData: (previousData) => previousData,
  });

  const items = auditQuery.data?.items ?? [];
  const total = auditQuery.data?.total ?? 0;
  const hasNext = pageOffset + items.length < total;
  const hasPrev = pageOffset > 0;

  const resetFilters = () => {
    setResourceType("");
    setActionFilter("");
    setResourceId("");
    setPageOffset(0);
  };

  return (
    <div className="grid gap-6">
      <Card className="rounded-[32px]">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-sm uppercase tracking-[0.2em] text-ink/45">Audit log</p>
            <h3 className="mt-2 text-2xl font-semibold">Operator timeline</h3>
            <p className="mt-2 max-w-2xl text-sm text-ink/65">
              Every action that mutates a service, env, or system resource is logged with the actor,
              target, and payload. Owners see all activity; everyone else sees their own.
            </p>
          </div>
          <div className="flex flex-wrap gap-3">
            <Button variant="secondary" className="gap-2" onClick={() => auditQuery.refetch()}>
              <RefreshCw className="h-4 w-4" /> Refresh
            </Button>
            <Button variant="ghost" className="gap-2" onClick={resetFilters}>
              <Filter className="h-4 w-4" /> Clear filters
            </Button>
          </div>
        </div>

        <div className="mt-5 grid gap-3 md:grid-cols-3">
          <label className="space-y-2 text-sm text-ink/70">
            <span>Resource type</span>
            <select
              value={resourceType}
              onChange={(event) => {
                setResourceType(event.target.value);
                setPageOffset(0);
              }}
              className="flex h-12 w-full rounded-2xl border border-ink/10 bg-white px-4 text-sm text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-coral/40"
            >
              {RESOURCE_TYPES.map((option) => (
                <option key={option.value || "all"} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <label className="space-y-2 text-sm text-ink/70">
            <span>Action prefix</span>
            <Input
              value={actionFilter}
              placeholder="service.create, service.env.*"
              onChange={(event) => {
                setActionFilter(event.target.value);
                setPageOffset(0);
              }}
            />
          </label>
          <label className="space-y-2 text-sm text-ink/70">
            <span>Resource id</span>
            <Input
              value={resourceId}
              placeholder="UUID"
              onChange={(event) => {
                setResourceId(event.target.value);
                setPageOffset(0);
              }}
            />
          </label>
        </div>
      </Card>

      <Card className="rounded-[32px]">
        {auditQuery.isLoading ? (
          <p className="text-sm text-ink/55">Loading audit entries...</p>
        ) : null}
        {auditQuery.isError ? (
          <p className="rounded-2xl bg-coral/10 px-4 py-3 text-sm text-coral">
            {auditQuery.error instanceof Error ? auditQuery.error.message : "Unable to load audit log."}
          </p>
        ) : null}

        {!auditQuery.isLoading && !items.length ? (
          <p className="text-sm text-ink/55">No audit entries match the current filters.</p>
        ) : null}

        <ol className="space-y-3">
          {items.map((entry) => (
            <AuditRow key={entry.id} entry={entry} />
          ))}
        </ol>

        {items.length ? (
          <div className="mt-6 flex flex-wrap items-center justify-between gap-3 text-sm text-ink/65">
            <span>
              Showing {pageOffset + 1}-{pageOffset + items.length} of {total}
            </span>
            <div className="flex flex-wrap gap-2">
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setPageOffset(Math.max(0, pageOffset - limit))}
                disabled={!hasPrev}
              >
                Previous
              </Button>
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setPageOffset(pageOffset + limit)}
                disabled={!hasNext}
              >
                Next
              </Button>
            </div>
          </div>
        ) : null}
      </Card>
    </div>
  );
}

function AuditRow({ entry }: { entry: AuditEntry }) {
  const [expanded, setExpanded] = useState(false);
  const resourceLink = buildResourceLink(entry);
  const detailKeys = Object.keys(entry.details ?? {});
  const hasDetails = detailKeys.length > 0;

  return (
    <li className="rounded-[24px] border border-ink/10 bg-mist/70 p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone={actionTone(entry.action)}>{entry.action}</Badge>
            <Badge tone="neutral">{entry.resource_type}</Badge>
            {resourceLink ? (
              <Link to={resourceLink} className="text-sm text-ink hover:text-slate">
                #{entry.resource_id.slice(0, 8)}
              </Link>
            ) : (
              <span className="text-sm text-ink/65">#{entry.resource_id.slice(0, 8)}</span>
            )}
          </div>
          <p className="mt-2 text-sm text-ink/70">
            {entry.actor_name ? `${entry.actor_name}` : "System"}
            {entry.actor_email ? ` <${entry.actor_email}>` : ""}
          </p>
        </div>
        <div className="text-right">
          <p className="text-xs uppercase tracking-[0.18em] text-ink/45">{formatRelative(entry.created_at)}</p>
          <p className="mt-1 text-xs text-ink/55">{formatDateTime(entry.created_at)}</p>
        </div>
      </div>

      {hasDetails ? (
        <button
          type="button"
          onClick={() => setExpanded((current) => !current)}
          className="mt-3 inline-flex items-center gap-1 text-xs text-ink/55 hover:text-ink"
        >
          {expanded ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
          {expanded ? "Hide details" : `Show ${detailKeys.length} detail field${detailKeys.length === 1 ? "" : "s"}`}
        </button>
      ) : null}

      {expanded && hasDetails ? (
        <pre className="mt-3 overflow-x-auto rounded-2xl bg-white/75 p-3 text-xs text-ink/70">
          {JSON.stringify(entry.details, null, 2)}
        </pre>
      ) : null}
    </li>
  );
}
