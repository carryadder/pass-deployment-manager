import { useMemo, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { CheckCircle2, FileCode2, GitBranch, Layers, Rocket, ShieldAlert } from "lucide-react";
import { useNavigate } from "react-router-dom";

import { ComposeService } from "@/api/generated";
import type {
  ComposeImportResponse,
  ComposePreviewResponse,
  ComposePreviewService,
} from "@/api/generated";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { queryClient } from "@/lib/query-client";

const SAMPLE_COMPOSE = `services:
  web:
    image: nginx:latest
    ports:
      - "8080:80"
    deploy:
      resources:
        limits:
          cpus: "0.5"
          memory: 256M
    volumes:
      - webdata:/var/cache/nginx
    restart: unless-stopped
  redis:
    image: redis:7-alpine
    deploy:
      resources:
        limits:
          memory: 128M
volumes:
  webdata:
`;

type SourceMode = "yaml" | "repo";

export function ComposeImportPage() {
  const navigate = useNavigate();
  const [sourceMode, setSourceMode] = useState<SourceMode>("yaml");
  const [yamlText, setYamlText] = useState(SAMPLE_COMPOSE);
  const [gitUrl, setGitUrl] = useState("");
  const [gitBranch, setGitBranch] = useState("");
  const [gitCommit, setGitCommit] = useState("");
  const [composePath, setComposePath] = useState("");
  const [namePrefix, setNamePrefix] = useState("");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [preview, setPreview] = useState<ComposePreviewResponse | null>(null);
  const [importResult, setImportResult] = useState<ComposeImportResponse | null>(null);

  const previewMutation = useMutation({
    mutationFn: () =>
      sourceMode === "yaml"
        ? ComposeService.preview({ yaml: yamlText, name_prefix: namePrefix.trim() })
        : ComposeService.previewRepo({
            git_url: gitUrl.trim(),
            branch: gitBranch.trim() || null,
            commit: gitCommit.trim() || null,
            compose_path: composePath.trim() || null,
            name_prefix: namePrefix.trim(),
          }),
    onSuccess: (data) => {
      setPreview(data);
      setSelected(new Set(data.services.map((service) => service.name)));
      setImportResult(null);
    },
  });

  const importMutation = useMutation({
    mutationFn: () =>
      sourceMode === "yaml"
        ? ComposeService.import({
            yaml: yamlText,
            name_prefix: namePrefix.trim(),
            only: Array.from(selected),
          })
        : ComposeService.importRepo({
            git_url: gitUrl.trim(),
            branch: gitBranch.trim() || null,
            commit: gitCommit.trim() || null,
            compose_path: composePath.trim() || null,
            name_prefix: namePrefix.trim(),
            only: Array.from(selected),
          }),
    onSuccess: (data) => {
      setImportResult(data);
      queryClient.invalidateQueries({ queryKey: ["services", "list"] });
    },
  });

  const previewError =
    previewMutation.error instanceof Error ? previewMutation.error.message : null;
  const importError =
    importMutation.error instanceof Error ? importMutation.error.message : null;

  const previewServices = preview?.services ?? [];
  const allSelected = previewServices.length > 0 && selected.size === previewServices.length;
  const noneSelected = selected.size === 0;
  const canPreview = sourceMode === "yaml" ? Boolean(yamlText.trim()) : Boolean(gitUrl.trim());

  const toggleService = (name: string) => {
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      return next;
    });
  };

  const sharedWarnings = useMemo(() => {
    if (!preview) return [];
    const collected = [...preview.document_warnings];
    for (const service of preview.services) {
      for (const warning of service.warnings) {
        collected.push(`${service.name}: ${warning}`);
      }
    }
    return collected;
  }, [preview]);

  return (
    <div className="grid gap-6">
      <Card className="rounded-[32px]">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-sm uppercase tracking-[0.2em] text-ink/45">Compose</p>
            <h3 className="mt-2 text-2xl font-semibold">Import from YAML or Git</h3>
            <p className="mt-2 max-w-2xl text-sm text-ink/65">
              Paste a compose document or point us at a Git repository that contains one. We preview
              each service, keep the supported CPU and memory limits, then create one deployment
              service per top-level compose entry.
            </p>
          </div>
        </div>

        <div className="mt-5 flex flex-wrap gap-2">
          <Button
            variant={sourceMode === "yaml" ? "primary" : "secondary"}
            size="sm"
            className="gap-2"
            onClick={() => {
              setSourceMode("yaml");
              setPreview(null);
              setImportResult(null);
            }}
          >
            <FileCode2 className="h-4 w-4" />
            Paste YAML
          </Button>
          <Button
            variant={sourceMode === "repo" ? "primary" : "secondary"}
            size="sm"
            className="gap-2"
            onClick={() => {
              setSourceMode("repo");
              setPreview(null);
              setImportResult(null);
            }}
          >
            <GitBranch className="h-4 w-4" />
            Git repo
          </Button>
        </div>

        <div className="mt-5 grid gap-4 md:grid-cols-[1fr_auto] md:items-end">
          <label className="space-y-2 text-sm text-ink/70">
            <span>Service name prefix (optional)</span>
            <Input
              value={namePrefix}
              onChange={(event) => setNamePrefix(event.target.value)}
              placeholder="staging"
            />
          </label>
          <Button
            onClick={() => previewMutation.mutate()}
            disabled={!canPreview || previewMutation.isPending}
            className="gap-2"
          >
            {sourceMode === "yaml" ? <FileCode2 className="h-4 w-4" /> : <GitBranch className="h-4 w-4" />}
            {previewMutation.isPending ? "Parsing..." : "Preview"}
          </Button>
        </div>

        {sourceMode === "yaml" ? (
          <div className="mt-5">
            <textarea
              value={yamlText}
              onChange={(event) => setYamlText(event.target.value)}
              spellCheck={false}
              className="h-[280px] w-full rounded-[24px] border border-ink/10 bg-ink p-4 font-mono text-xs text-mist focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-coral/40"
            />
          </div>
        ) : (
          <div className="mt-5 grid gap-4 md:grid-cols-2">
            <label className="space-y-2 text-sm text-ink/70 md:col-span-2">
              <span>Git repository URL</span>
              <Input
                value={gitUrl}
                onChange={(event) => setGitUrl(event.target.value)}
                placeholder="https://github.com/owner/repo.git"
              />
            </label>
            <label className="space-y-2 text-sm text-ink/70">
              <span>Branch (optional)</span>
              <Input
                value={gitBranch}
                onChange={(event) => setGitBranch(event.target.value)}
                placeholder="main"
              />
            </label>
            <label className="space-y-2 text-sm text-ink/70">
              <span>Commit (optional)</span>
              <Input
                value={gitCommit}
                onChange={(event) => setGitCommit(event.target.value)}
                placeholder="f3c2a1b"
              />
            </label>
            <label className="space-y-2 text-sm text-ink/70 md:col-span-2">
              <span>Compose file path (optional)</span>
              <Input
                value={composePath}
                onChange={(event) => setComposePath(event.target.value)}
                placeholder="docker-compose.yml or deploy/compose.yaml"
              />
            </label>
          </div>
        )}

        {previewError ? (
          <p className="mt-4 rounded-2xl bg-coral/10 px-4 py-3 text-sm text-coral">{previewError}</p>
        ) : null}
      </Card>

      {preview ? (
        <Card className="rounded-[32px]">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <p className="text-sm uppercase tracking-[0.2em] text-ink/45">Preview</p>
              <h3 className="mt-2 text-2xl font-semibold">
                {previewServices.length} service{previewServices.length === 1 ? "" : "s"} ready
              </h3>
              <p className="mt-1 text-sm text-ink/65">
                Volumes declared: {preview.declared_volumes.length || "none"} · Networks declared:{" "}
                {preview.declared_networks.length || "none"}
              </p>
              {preview.compose_path ? (
                <p className="mt-1 text-xs text-ink/55">Compose file: {preview.compose_path}</p>
              ) : null}
            </div>
            <div className="flex flex-wrap gap-2">
              <Button
                variant="secondary"
                size="sm"
                onClick={() =>
                  setSelected(new Set(previewServices.map((service) => service.name)))
                }
                disabled={allSelected}
              >
                Select all
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setSelected(new Set())}
                disabled={noneSelected}
              >
                Clear
              </Button>
              <Button
                onClick={() => importMutation.mutate()}
                disabled={noneSelected || importMutation.isPending}
                className="gap-2"
              >
                <Rocket className="h-4 w-4" />
                {importMutation.isPending ? "Importing..." : `Import ${selected.size}`}
              </Button>
            </div>
          </div>

          {sharedWarnings.length ? (
            <div className="mt-5 rounded-2xl border border-coral/30 bg-coral/5 p-4">
              <div className="flex items-center gap-2">
                <ShieldAlert className="h-4 w-4 text-coral" />
                <p className="text-sm font-semibold text-coral">
                  {sharedWarnings.length} warning{sharedWarnings.length === 1 ? "" : "s"}
                </p>
              </div>
              <ul className="mt-2 list-disc space-y-1 pl-6 text-sm text-ink/70">
                {sharedWarnings.map((warning) => (
                  <li key={warning}>{warning}</li>
                ))}
              </ul>
            </div>
          ) : null}

          {importError ? (
            <p className="mt-4 rounded-2xl bg-coral/10 px-4 py-3 text-sm text-coral">{importError}</p>
          ) : null}

          <div className="mt-6 grid gap-3">
            {previewServices.map((service) => (
              <PreviewRow
                key={service.name}
                service={service}
                checked={selected.has(service.name)}
                onToggle={() => toggleService(service.name)}
              />
            ))}
            {!previewServices.length ? (
              <p className="text-sm text-ink/55">No services were detected in this document.</p>
            ) : null}
          </div>
        </Card>
      ) : null}

      {importResult ? (
        <Card className="rounded-[32px]">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="h-5 w-5 text-slate" />
            <p className="text-sm uppercase tracking-[0.2em] text-ink/45">Import result</p>
          </div>
          <h3 className="mt-2 text-xl font-semibold">
            {importResult.imported.length} imported · {importResult.skipped.length} skipped
          </h3>
          {importResult.compose_path ? (
            <p className="mt-1 text-sm text-ink/55">Imported from {importResult.compose_path}</p>
          ) : null}

          <div className="mt-5 grid gap-3 md:grid-cols-2">
            <div className="rounded-2xl border border-moss/30 bg-moss/10 p-4">
              <p className="text-sm font-semibold text-slate">Imported</p>
              <ul className="mt-2 space-y-2 text-sm text-ink/70">
                {importResult.imported.map((entry) => (
                  <li key={entry.service_id} className="flex items-center justify-between gap-3">
                    <button
                      type="button"
                      onClick={() => navigate(`/services/${entry.service_id}`)}
                      className="text-left font-medium text-ink hover:text-slate"
                    >
                      {entry.service_name}
                    </button>
                    <Badge tone="success">{entry.status}</Badge>
                  </li>
                ))}
                {!importResult.imported.length ? (
                  <li className="text-xs text-ink/55">Nothing was created.</li>
                ) : null}
              </ul>
            </div>
            <div className="rounded-2xl border border-coral/30 bg-coral/5 p-4">
              <p className="text-sm font-semibold text-coral">Skipped</p>
              <ul className="mt-2 space-y-2 text-sm text-ink/70">
                {importResult.skipped.map((entry) => (
                  <li key={entry.compose_name}>
                    <span className="font-medium">{entry.compose_name}</span>
                    <p className="text-xs text-ink/55">{entry.reason}</p>
                  </li>
                ))}
                {!importResult.skipped.length ? (
                  <li className="text-xs text-ink/55">All selected services were imported.</li>
                ) : null}
              </ul>
            </div>
          </div>
        </Card>
      ) : null}
    </div>
  );
}

function PreviewRow({
  service,
  checked,
  onToggle,
}: {
  service: ComposePreviewService;
  checked: boolean;
  onToggle: () => void;
}) {
  return (
    <label className="flex cursor-pointer items-start gap-3 rounded-[24px] border border-ink/10 bg-mist/70 p-4">
      <input
        type="checkbox"
        checked={checked}
        onChange={onToggle}
        className="mt-1 h-4 w-4 accent-ink"
      />
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <p className="font-semibold">{service.name}</p>
          <Badge tone="info">{service.image}</Badge>
          {service.healthcheck ? <Badge tone="success">healthcheck</Badge> : null}
          {service.network ? <Badge tone="neutral">net: {service.network}</Badge> : null}
        </div>
        <div className="mt-2 flex flex-wrap gap-2 text-xs text-ink/60">
          <span className="rounded-full bg-white/70 px-3 py-1 ring-1 ring-ink/5">{service.cpus} CPU</span>
          <span className="rounded-full bg-white/70 px-3 py-1 ring-1 ring-ink/5">{service.memory_mb} MB</span>
          <span className="rounded-full bg-white/70 px-3 py-1 ring-1 ring-ink/5">
            {service.port_count} port{service.port_count === 1 ? "" : "s"}
          </span>
          <span className="rounded-full bg-white/70 px-3 py-1 ring-1 ring-ink/5">
            {service.volume_count} volume{service.volume_count === 1 ? "" : "s"}
          </span>
          <span className="rounded-full bg-white/70 px-3 py-1 ring-1 ring-ink/5">
            restart: {service.restart_policy}
          </span>
          {service.env_keys.length ? (
            <span className="rounded-full bg-white/70 px-3 py-1 ring-1 ring-ink/5">
              {service.env_keys.length} env
            </span>
          ) : null}
        </div>
        {service.warnings.length ? (
          <div className="mt-2 flex items-start gap-2 rounded-2xl border border-coral/30 bg-coral/5 px-3 py-2 text-xs text-ink/70">
            <Layers className="mt-0.5 h-3 w-3 text-coral" />
            <ul className="space-y-1">
              {service.warnings.map((warning) => (
                <li key={warning}>{warning}</li>
              ))}
            </ul>
          </div>
        ) : null}
      </div>
    </label>
  );
}
