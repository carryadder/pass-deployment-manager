import { useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  Activity,
  Database,
  HardDrive,
  Layers,
  Mail,
  RefreshCw,
  Rocket,
  Search,
  Workflow,
  Zap,
} from "lucide-react";
import { useNavigate } from "react-router-dom";

import { TemplatesService } from "@/api/generated";
import type {
  TemplateDeployResponse,
  TemplateEnvField,
  TemplateSummary,
} from "@/api/generated";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { queryClient } from "@/lib/query-client";
import { cn } from "@/lib/utils";

const ICONS: Record<string, typeof Database> = {
  database: Database,
  zap: Zap,
  "hard-drive": HardDrive,
  workflow: Workflow,
  activity: Activity,
  layers: Layers,
  mail: Mail,
};

const CATEGORY_TONE: Record<string, "info" | "warning" | "success" | "neutral"> = {
  database: "info",
  storage: "warning",
  automation: "success",
  monitoring: "info",
  tooling: "neutral",
};

function pickIcon(name: string): typeof Database {
  return ICONS[name] ?? Layers;
}

export function TemplatesPage() {
  const [search, setSearch] = useState("");
  const [activeTemplate, setActiveTemplate] = useState<TemplateSummary | null>(null);

  const templatesQuery = useQuery({
    queryKey: ["templates", "list"],
    queryFn: TemplatesService.list,
  });

  const filtered = useMemo(() => {
    const data = templatesQuery.data ?? [];
    const term = search.trim().toLowerCase();
    if (!term) return data;
    return data.filter((template) =>
      [template.name, template.description, template.category, template.image]
        .join(" ")
        .toLowerCase()
        .includes(term),
    );
  }, [search, templatesQuery.data]);

  return (
    <div className="grid gap-6">
      {activeTemplate ? (
        <DeployModal
          template={activeTemplate}
          onClose={() => setActiveTemplate(null)}
        />
      ) : null}

      <Card className="rounded-[32px]">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-sm uppercase tracking-[0.2em] text-ink/45">Templates</p>
            <h3 className="mt-2 text-2xl font-semibold">One-click deploys</h3>
            <p className="mt-2 max-w-2xl text-sm text-ink/65">
              Pre-tuned services with persistent volumes, healthchecks, and auto-generated
              passwords stored as Fernet-encrypted secrets. Click a card, name it, and ship.
            </p>
          </div>
          <div className="flex flex-wrap gap-3">
            <div className="relative min-w-[240px]">
              <Search className="pointer-events-none absolute left-4 top-3.5 h-4 w-4 text-ink/35" />
              <Input
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Search by name, image, category..."
                className="pl-10"
              />
            </div>
            <Button variant="secondary" className="gap-2" onClick={() => templatesQuery.refetch()}>
              <RefreshCw className="h-4 w-4" /> Refresh
            </Button>
          </div>
        </div>

        {templatesQuery.isError ? (
          <p className="mt-4 rounded-2xl bg-coral/10 px-4 py-3 text-sm text-coral">
            {templatesQuery.error instanceof Error
              ? templatesQuery.error.message
              : "Unable to load templates."}
          </p>
        ) : null}

        <div className="mt-6 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {filtered.map((template) => (
            <TemplateCard
              key={template.id}
              template={template}
              onSelect={() => setActiveTemplate(template)}
            />
          ))}
          {!templatesQuery.isLoading && !filtered.length ? (
            <p className="text-sm text-ink/55">No templates match the current filter.</p>
          ) : null}
        </div>
      </Card>
    </div>
  );
}

function TemplateCard({
  template,
  onSelect,
}: {
  template: TemplateSummary;
  onSelect: () => void;
}) {
  const Icon = pickIcon(template.icon);
  const tone = CATEGORY_TONE[template.category] ?? "neutral";
  const autoSecretCount = template.env.filter((env) => env.auto_secret).length;
  const volumeCount = template.volumes.length;
  return (
    <div className="flex flex-col gap-4 rounded-[24px] border border-ink/10 bg-mist/70 p-5">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <div className="rounded-2xl bg-cyan/20 p-3 text-slate">
            <Icon className="h-5 w-5" />
          </div>
          <div>
            <p className="text-lg font-semibold">{template.name}</p>
            <p className="text-xs text-ink/55">{template.image}</p>
          </div>
        </div>
        <Badge tone={tone}>{template.category}</Badge>
      </div>
      <p className="text-sm text-ink/65">{template.description}</p>
      <div className="flex flex-wrap gap-2 text-xs text-ink/60">
        <span className="rounded-full bg-white/70 px-3 py-1 ring-1 ring-ink/5">
          {template.default_resources.cpus} CPU
        </span>
        <span className="rounded-full bg-white/70 px-3 py-1 ring-1 ring-ink/5">
          {template.default_resources.memory_mb} MB
        </span>
        {volumeCount ? (
          <span className="rounded-full bg-white/70 px-3 py-1 ring-1 ring-ink/5">
            {volumeCount} volume{volumeCount === 1 ? "" : "s"}
          </span>
        ) : null}
        {autoSecretCount ? (
          <span className="rounded-full bg-coral/10 px-3 py-1 ring-1 ring-coral/30 text-coral">
            {autoSecretCount} auto secret{autoSecretCount === 1 ? "" : "s"}
          </span>
        ) : null}
      </div>
      <Button onClick={onSelect} className="gap-2 self-start">
        <Rocket className="h-4 w-4" /> Add {template.name}
      </Button>
    </div>
  );
}

function DeployModal({
  template,
  onClose,
}: {
  template: TemplateSummary;
  onClose: () => void;
}) {
  const navigate = useNavigate();
  const [name, setName] = useState(`${template.id}-${Math.random().toString(36).slice(2, 6)}`);
  const [cpus, setCpus] = useState(template.default_resources.cpus);
  const [memoryMb, setMemoryMb] = useState(template.default_resources.memory_mb);
  const [domain, setDomain] = useState("");
  const [overrides, setOverrides] = useState<Record<string, string>>(() => {
    const initial: Record<string, string> = {};
    for (const env of template.env) {
      if (!env.auto_secret && env.value != null) {
        initial[env.key] = env.value;
      }
    }
    return initial;
  });

  const deployMutation = useMutation({
    mutationFn: (payload: { id: string; body: Parameters<typeof TemplatesService.deploy>[1] }) =>
      TemplatesService.deploy(payload.id, payload.body),
    onSuccess: (response: TemplateDeployResponse) => {
      queryClient.invalidateQueries({ queryKey: ["services", "list"] });
      // small delay so the success message can render before navigation
      setTimeout(() => navigate(`/services/${response.service_id}`), 600);
    },
  });

  const error =
    deployMutation.error instanceof Error ? deployMutation.error.message : null;

  const handleSubmit = () => {
    deployMutation.mutate({
      id: template.id,
      body: {
        name: name.trim(),
        cpus,
        memory_mb: memoryMb,
        domain: domain.trim() || null,
        env_overrides: overrides,
      },
    });
  };

  const autoSecretFields = template.env.filter((env) => env.auto_secret);
  const editableFields = template.env.filter((env) => !env.auto_secret);

  return (
    <div className="fixed inset-0 z-40 flex items-start justify-center overflow-y-auto bg-ink/45 px-4 py-10 backdrop-blur">
      <Card className="relative w-full max-w-3xl rounded-[32px]">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-sm uppercase tracking-[0.2em] text-ink/45">Deploy template</p>
            <h3 className="mt-2 text-2xl font-semibold">{template.name}</h3>
            <p className="mt-1 text-sm text-ink/65">{template.image}</p>
          </div>
          <Button variant="ghost" onClick={onClose} disabled={deployMutation.isPending}>
            Close
          </Button>
        </div>

        <p className="mt-4 text-sm text-ink/65">{template.description}</p>

        <div className="mt-6 grid gap-4 md:grid-cols-2">
          <label className="space-y-2 text-sm text-ink/70">
            <span>Service name</span>
            <Input
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder={`${template.id}-prod`}
            />
          </label>
          <label className="space-y-2 text-sm text-ink/70">
            <span>Domain (optional)</span>
            <Input
              value={domain}
              onChange={(event) => setDomain(event.target.value)}
              placeholder="db.example.com"
            />
          </label>
          <label className="space-y-2 text-sm text-ink/70">
            <span>CPU cores</span>
            <Input
              type="number"
              min={0.1}
              step={0.1}
              value={cpus}
              onChange={(event) => setCpus(Number(event.target.value || 0))}
            />
          </label>
          <label className="space-y-2 text-sm text-ink/70">
            <span>Memory (MB)</span>
            <Input
              type="number"
              min={32}
              step={32}
              value={memoryMb}
              onChange={(event) => setMemoryMb(Number(event.target.value || 0))}
            />
          </label>
        </div>

        {editableFields.length ? (
          <div className="mt-6">
            <p className="text-sm font-semibold">Environment defaults</p>
            <p className="mt-1 text-xs text-ink/55">
              Override any value before deploying. Leave a field unchanged to use the template default.
            </p>
            <div className="mt-3 space-y-3">
              {editableFields.map((field) => (
                <EnvOverrideRow
                  key={field.key}
                  field={field}
                  value={overrides[field.key] ?? field.value ?? ""}
                  onChange={(value) =>
                    setOverrides((current) => ({ ...current, [field.key]: value }))
                  }
                />
              ))}
            </div>
          </div>
        ) : null}

        {autoSecretFields.length ? (
          <div className="mt-6 rounded-2xl border border-coral/30 bg-coral/5 p-4">
            <p className="text-sm font-semibold text-coral">Auto-generated secrets</p>
            <p className="mt-1 text-xs text-ink/65">
              These are created on deploy and stored encrypted. View them under the service&apos;s
              Env tab.
            </p>
            <ul className="mt-3 space-y-1 text-sm text-ink/70">
              {autoSecretFields.map((field) => (
                <li key={field.key} className="flex items-center justify-between">
                  <span className="font-mono text-xs">{field.key}</span>
                  <Badge tone="warning">auto</Badge>
                </li>
              ))}
            </ul>
          </div>
        ) : null}

        {template.volumes.length ? (
          <div className="mt-6 rounded-2xl border border-ink/10 bg-mist/70 p-4">
            <p className="text-sm font-semibold">Persistent volumes</p>
            <ul className="mt-2 space-y-1 text-sm text-ink/70">
              {template.volumes.map((volume) => (
                <li key={volume.target} className="flex items-center justify-between">
                  <span className="font-mono text-xs">
                    {volume.source.replace("{slug}", "(your-slug)")}
                  </span>
                  <span className="text-xs text-ink/55">{volume.target}</span>
                </li>
              ))}
            </ul>
          </div>
        ) : null}

        {error ? (
          <p className="mt-4 rounded-2xl bg-coral/10 px-4 py-3 text-sm text-coral">{error}</p>
        ) : null}
        {deployMutation.isSuccess ? (
          <p className="mt-4 rounded-2xl bg-moss/15 px-4 py-3 text-sm text-slate">
            Service running. Opening detail page...
          </p>
        ) : null}

        <div className="mt-6 flex flex-wrap items-center justify-end gap-3">
          <Button variant="ghost" onClick={onClose} disabled={deployMutation.isPending}>
            Cancel
          </Button>
          <Button
            onClick={handleSubmit}
            disabled={!name.trim() || deployMutation.isPending}
            className={cn("gap-2")}
          >
            <Rocket className="h-4 w-4" />
            {deployMutation.isPending ? "Deploying..." : "Deploy"}
          </Button>
        </div>
      </Card>
    </div>
  );
}

function EnvOverrideRow({
  field,
  value,
  onChange,
}: {
  field: TemplateEnvField;
  value: string;
  onChange: (next: string) => void;
}) {
  return (
    <div className="grid grid-cols-[1fr_2fr] gap-3 rounded-2xl border border-ink/10 bg-white px-3 py-2">
      <div className="min-w-0">
        <p className="truncate font-mono text-xs">{field.key}</p>
        {field.description ? (
          <p className="mt-1 truncate text-[11px] text-ink/55">{field.description}</p>
        ) : null}
      </div>
      <Input
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={field.value ?? ""}
      />
    </div>
  );
}
