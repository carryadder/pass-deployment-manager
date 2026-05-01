import { useMemo, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Check, ChevronLeft, ChevronRight, GitBranch, Layers, Plus, Trash2, X } from "lucide-react";
import { useNavigate } from "react-router-dom";

import { ServicesService } from "@/api/generated";
import type {
  CreateServiceRequest,
  CreateServiceResponse,
  ServiceDeployRequest,
} from "@/api/generated";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { queryClient } from "@/lib/query-client";
import { cn } from "@/lib/utils";

type SourceKind = "image" | "git" | "compose";

interface PortRow {
  container_port: string;
  host_port: string;
}

interface VolumeRow {
  source: string;
  target: string;
  mode: "ro" | "rw";
}

interface EnvRow {
  key: string;
  value: string;
  is_secret: boolean;
}

interface WizardState {
  source_kind: SourceKind;
  // shared
  name: string;
  image: string;
  // git
  git_url: string;
  git_branch: string;
  dockerfile_path: string;
  build_args: EnvRow[];
  // resources
  cpus: number;
  memory_mb: number;
  disk_mb: string; // optional, kept as text for empty support
  pids_limit: number;
  restart_policy: "no" | "always" | "unless-stopped" | "on-failure";
  // networking
  domain: string;
  network: string;
  ports: PortRow[];
  volumes: VolumeRow[];
  // env
  env: EnvRow[];
}

const STEPS = [
  { id: "source", title: "Source", description: "Where the image comes from" },
  { id: "resources", title: "Resources", description: "CPU, memory, disk" },
  { id: "networking", title: "Networking", description: "Domain, ports, volumes" },
  { id: "env", title: "Env / Secrets", description: "Configuration values" },
  { id: "review", title: "Review", description: "Confirm and deploy" },
] as const;

type StepId = (typeof STEPS)[number]["id"];

const RESTART_POLICIES: WizardState["restart_policy"][] = [
  "unless-stopped",
  "always",
  "on-failure",
  "no",
];

const initialState: WizardState = {
  source_kind: "image",
  name: "",
  image: "nginx:latest",
  git_url: "",
  git_branch: "main",
  dockerfile_path: "Dockerfile",
  build_args: [],
  cpus: 0.5,
  memory_mb: 256,
  disk_mb: "",
  pids_limit: 256,
  restart_policy: "unless-stopped",
  domain: "",
  network: "",
  ports: [{ container_port: "80", host_port: "8080" }],
  volumes: [],
  env: [],
};

const NAME_PATTERN = /^[a-z0-9][a-z0-9-_]*$/i;
const DOMAIN_PATTERN = /^([a-z0-9]([a-z0-9-]*[a-z0-9])?\.)+[a-z0-9]([a-z0-9-]*[a-z0-9])?$|^[a-z0-9-]+\.localhost$/i;
const ENV_KEY_PATTERN = /^[A-Z_][A-Z0-9_]*$/;
const GIT_URL_PATTERN = /^(https?:\/\/|git@)[^\s]+\.git$|^(https?:\/\/)[^\s]+$/i;
const IMAGE_PATTERN = /^[a-z0-9]([a-z0-9._\/-]*[a-z0-9])?(:[\w][\w.-]{0,127})?$/i;

function validateStep(state: WizardState, step: StepId): Record<string, string> {
  const errors: Record<string, string> = {};
  if (step === "source") {
    if (!state.name.trim()) {
      errors.name = "Name is required.";
    } else if (!NAME_PATTERN.test(state.name.trim())) {
      errors.name = "Use letters, numbers, hyphen, or underscore.";
    }
    if (state.source_kind === "image") {
      if (!state.image.trim()) {
        errors.image = "Image is required (e.g. nginx:latest).";
      } else if (!IMAGE_PATTERN.test(state.image.trim())) {
        errors.image = "Image must look like name[:tag].";
      }
    } else if (state.source_kind === "git") {
      if (!state.git_url.trim()) {
        errors.git_url = "Git URL is required.";
      } else if (!GIT_URL_PATTERN.test(state.git_url.trim())) {
        errors.git_url = "URL must be http(s) or git@ form.";
      }
      if (!state.image.trim()) {
        errors.image = "A runtime base image is required while the build runs.";
      } else if (!IMAGE_PATTERN.test(state.image.trim())) {
        errors.image = "Runtime image must look like name[:tag].";
      }
      if (!state.dockerfile_path.trim()) {
        errors.dockerfile_path = "Dockerfile path is required.";
      }
    } else if (state.source_kind === "compose") {
      errors.source_kind = "Compose import lands on Day 24 — pick image or git for now.";
    }
  }
  if (step === "resources") {
    if (state.cpus <= 0 || state.cpus > 16) {
      errors.cpus = "CPU must be between 0.1 and 16.";
    }
    if (state.memory_mb < 32 || state.memory_mb > 65536) {
      errors.memory_mb = "Memory must be between 32 MB and 64 GB.";
    }
    if (state.disk_mb && (Number.isNaN(Number(state.disk_mb)) || Number(state.disk_mb) <= 0)) {
      errors.disk_mb = "Disk must be a positive number of MB or empty.";
    }
    if (state.pids_limit <= 0 || state.pids_limit > 100_000) {
      errors.pids_limit = "PIDs must be between 1 and 100000.";
    }
  }
  if (step === "networking") {
    if (state.domain.trim() && !DOMAIN_PATTERN.test(state.domain.trim())) {
      errors.domain = "Domain must look like host.example.com or *.localhost.";
    }
    state.ports.forEach((port, index) => {
      const cp = Number(port.container_port);
      if (!port.container_port || Number.isNaN(cp) || cp < 1 || cp > 65535) {
        errors[`port_container_${index}`] = "Container port must be 1-65535.";
      }
      if (port.host_port) {
        const hp = Number(port.host_port);
        if (Number.isNaN(hp) || hp < 1 || hp > 65535) {
          errors[`port_host_${index}`] = "Host port must be 1-65535 or empty.";
        }
      }
    });
    state.volumes.forEach((volume, index) => {
      if (!volume.source.trim()) {
        errors[`volume_source_${index}`] = "Volume source is required.";
      }
      if (!volume.target.trim() || !volume.target.startsWith("/")) {
        errors[`volume_target_${index}`] = "Mount target must be an absolute path.";
      }
    });
  }
  if (step === "env") {
    state.env.forEach((entry, index) => {
      if (!entry.key.trim()) {
        errors[`env_key_${index}`] = "Key is required.";
      } else if (!ENV_KEY_PATTERN.test(entry.key.trim())) {
        errors[`env_key_${index}`] = "Use UPPER_SNAKE_CASE.";
      }
    });
    const seen = new Set<string>();
    state.env.forEach((entry, index) => {
      const key = entry.key.trim();
      if (key) {
        if (seen.has(key)) {
          errors[`env_key_${index}`] = "Duplicate key.";
        }
        seen.add(key);
      }
    });
  }
  return errors;
}

function buildCreatePayload(state: WizardState): CreateServiceRequest {
  const plainEnv: Record<string, string> = {};
  for (const entry of state.env) {
    if (!entry.is_secret && entry.key.trim()) {
      plainEnv[entry.key.trim()] = entry.value;
    }
  }
  const ports = state.ports
    .filter((port) => port.container_port)
    .map((port) => ({
      container_port: Number(port.container_port),
      host_port: port.host_port ? Number(port.host_port) : null,
    }));
  const volumes = state.volumes
    .filter((volume) => volume.source.trim() && volume.target.trim())
    .map((volume) => ({ source: volume.source.trim(), target: volume.target.trim(), mode: volume.mode }));
  return {
    name: state.name.trim(),
    image: state.image.trim(),
    cpus: state.cpus,
    memory_mb: state.memory_mb,
    disk_mb: state.disk_mb ? Number(state.disk_mb) : null,
    env: plainEnv,
    ports,
    volumes,
    network: state.network.trim() || null,
    domain: state.domain.trim() || null,
    restart_policy: state.restart_policy,
    pids_limit: state.pids_limit,
  };
}

function buildDeployPayload(state: WizardState): ServiceDeployRequest {
  const buildArgs: Record<string, string> = {};
  for (const entry of state.build_args) {
    if (entry.key.trim()) {
      buildArgs[entry.key.trim()] = entry.value;
    }
  }
  return {
    git_url: state.git_url.trim(),
    branch: state.git_branch.trim() || null,
    commit: null,
    dockerfile_path: state.dockerfile_path.trim() || null,
    build_args: buildArgs,
  };
}

interface WizardSubmitOutcome {
  service_id: string;
  applied_secrets: number;
  triggered_git_build: boolean;
}

async function submitWizard(state: WizardState): Promise<WizardSubmitOutcome> {
  const created: CreateServiceResponse = await ServicesService.create(buildCreatePayload(state));
  const secrets = state.env.filter((entry) => entry.is_secret && entry.key.trim());
  for (let i = 0; i < secrets.length; i += 1) {
    const entry = secrets[i];
    await ServicesService.upsertEnv(created.service_id, {
      key: entry.key.trim(),
      value: entry.value,
      is_secret: true,
      apply: i === secrets.length - 1, // only apply on the final secret to batch redeploys
    });
  }
  let triggeredGit = false;
  if (state.source_kind === "git") {
    await ServicesService.deployFromGit(created.service_id, buildDeployPayload(state));
    triggeredGit = true;
  }
  return {
    service_id: created.service_id,
    applied_secrets: secrets.length,
    triggered_git_build: triggeredGit,
  };
}

export interface ServiceCreateWizardProps {
  onClose: () => void;
}

export function ServiceCreateWizard({ onClose }: ServiceCreateWizardProps) {
  const [state, setState] = useState<WizardState>(initialState);
  const [activeStepIndex, setActiveStepIndex] = useState(0);
  const [submitMessage, setSubmitMessage] = useState<string | null>(null);
  const navigate = useNavigate();

  const activeStep = STEPS[activeStepIndex];
  const stepErrors = useMemo(() => validateStep(state, activeStep.id), [state, activeStep.id]);

  const submitMutation = useMutation({
    mutationFn: submitWizard,
    onSuccess: (outcome) => {
      queryClient.invalidateQueries({ queryKey: ["services", "list"] });
      const tail = outcome.triggered_git_build
        ? "Build queued — watch the deploys tab for progress."
        : "Container running — opening detail page.";
      setSubmitMessage(tail);
      setTimeout(() => navigate(`/services/${outcome.service_id}`), 600);
    },
  });

  const goNext = () => {
    if (Object.keys(stepErrors).length) {
      return;
    }
    if (activeStepIndex < STEPS.length - 1) {
      setActiveStepIndex((index) => index + 1);
    }
  };

  const goBack = () => {
    setSubmitMessage(null);
    if (activeStepIndex > 0) {
      setActiveStepIndex((index) => index - 1);
    }
  };

  const handleSubmit = () => {
    const allErrors: Record<string, string> = {};
    for (const step of STEPS) {
      Object.assign(allErrors, validateStep(state, step.id));
    }
    if (Object.keys(allErrors).length) {
      // jump back to the first step with an error
      for (let i = 0; i < STEPS.length; i += 1) {
        if (Object.keys(validateStep(state, STEPS[i].id)).length) {
          setActiveStepIndex(i);
          break;
        }
      }
      return;
    }
    submitMutation.mutate(state);
  };

  const submitError =
    submitMutation.error instanceof Error ? submitMutation.error.message : null;

  return (
    <Card className="rounded-[32px]">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <p className="text-sm uppercase tracking-[0.2em] text-ink/45">Create service</p>
          <h3 className="mt-2 text-2xl font-semibold">Multi-step deploy wizard</h3>
          <p className="mt-2 max-w-2xl text-sm text-ink/65">
            Source -&gt; resources -&gt; networking -&gt; env -&gt; review. Validation runs at every
            step; the server validates again on submit.
          </p>
        </div>
        <Button variant="ghost" onClick={onClose} className="self-start gap-2">
          <X className="h-4 w-4" /> Cancel
        </Button>
      </div>

      <Stepper activeIndex={activeStepIndex} />

      <div className="mt-6 grid gap-6">
        {activeStep.id === "source" ? (
          <SourceStep state={state} setState={setState} errors={stepErrors} />
        ) : null}
        {activeStep.id === "resources" ? (
          <ResourcesStep state={state} setState={setState} errors={stepErrors} />
        ) : null}
        {activeStep.id === "networking" ? (
          <NetworkingStep state={state} setState={setState} errors={stepErrors} />
        ) : null}
        {activeStep.id === "env" ? (
          <EnvStep state={state} setState={setState} errors={stepErrors} />
        ) : null}
        {activeStep.id === "review" ? <ReviewStep state={state} /> : null}
      </div>

      {submitError ? (
        <p className="mt-6 rounded-2xl bg-coral/10 px-4 py-3 text-sm text-coral">{submitError}</p>
      ) : null}
      {submitMessage ? (
        <p className="mt-6 rounded-2xl bg-moss/15 px-4 py-3 text-sm text-slate">{submitMessage}</p>
      ) : null}

      <div className="mt-8 flex flex-wrap items-center justify-between gap-3">
        <Button
          variant="ghost"
          onClick={goBack}
          disabled={activeStepIndex === 0 || submitMutation.isPending}
          className="gap-2"
        >
          <ChevronLeft className="h-4 w-4" /> Back
        </Button>
        <div className="flex flex-wrap gap-3">
          {activeStep.id !== "review" ? (
            <Button
              onClick={goNext}
              disabled={Object.keys(stepErrors).length > 0}
              className="gap-2"
            >
              Next <ChevronRight className="h-4 w-4" />
            </Button>
          ) : (
            <Button onClick={handleSubmit} disabled={submitMutation.isPending} className="gap-2">
              {submitMutation.isPending ? "Deploying..." : "Create service"}
              <Check className="h-4 w-4" />
            </Button>
          )}
        </div>
      </div>
    </Card>
  );
}

function Stepper({ activeIndex }: { activeIndex: number }) {
  return (
    <ol className="mt-6 grid gap-3 lg:grid-cols-5">
      {STEPS.map((step, index) => {
        const isActive = index === activeIndex;
        const isComplete = index < activeIndex;
        return (
          <li
            key={step.id}
            className={cn(
              "rounded-2xl border px-4 py-3 transition",
              isActive
                ? "border-ink/40 bg-white shadow-panel"
                : isComplete
                  ? "border-moss/40 bg-moss/10"
                  : "border-ink/10 bg-mist/60",
            )}
          >
            <div className="flex items-center gap-3">
              <span
                className={cn(
                  "flex h-7 w-7 items-center justify-center rounded-full text-xs font-semibold",
                  isComplete ? "bg-moss/30 text-slate" : isActive ? "bg-ink text-mist" : "bg-ink/10 text-ink/60",
                )}
              >
                {isComplete ? <Check className="h-3.5 w-3.5" /> : index + 1}
              </span>
              <div>
                <p className="text-sm font-semibold">{step.title}</p>
                <p className="text-xs text-ink/55">{step.description}</p>
              </div>
            </div>
          </li>
        );
      })}
    </ol>
  );
}

interface StepProps {
  state: WizardState;
  setState: React.Dispatch<React.SetStateAction<WizardState>>;
  errors: Record<string, string>;
}

function FieldError({ message }: { message?: string }) {
  if (!message) {
    return null;
  }
  return <p className="mt-1 text-xs text-coral">{message}</p>;
}

function SourceStep({ state, setState, errors }: StepProps) {
  return (
    <div className="grid gap-5">
      <div className="grid gap-3 md:grid-cols-3">
        {(
          [
            { id: "image", title: "Docker image", description: "Pull from a registry", icon: Layers },
            { id: "git", title: "Git repo", description: "Build a Dockerfile", icon: GitBranch },
            { id: "compose", title: "docker-compose", description: "Day 24 import", icon: Layers },
          ] as const
        ).map((option) => {
          const isActive = state.source_kind === option.id;
          const isDisabled = option.id === "compose";
          return (
            <button
              key={option.id}
              type="button"
              onClick={() => !isDisabled && setState((current) => ({ ...current, source_kind: option.id }))}
              className={cn(
                "rounded-2xl border p-4 text-left transition",
                isActive ? "border-ink/40 bg-white shadow-panel" : "border-ink/10 bg-mist/70 hover:bg-white",
                isDisabled && "opacity-50 cursor-not-allowed",
              )}
              disabled={isDisabled}
            >
              <div className="flex items-center gap-3">
                <div className="rounded-xl bg-cyan/20 p-2 text-slate">
                  <option.icon className="h-4 w-4" />
                </div>
                <div>
                  <p className="font-semibold">{option.title}</p>
                  <p className="text-xs text-ink/55">{option.description}</p>
                </div>
              </div>
              {isDisabled ? (
                <Badge tone="warning" className="mt-3">Coming soon</Badge>
              ) : null}
            </button>
          );
        })}
      </div>

      {errors.source_kind ? <FieldError message={errors.source_kind} /> : null}

      <div className="grid gap-4 md:grid-cols-2">
        <label className="space-y-2 text-sm text-ink/70">
          <span>Service name</span>
          <Input
            value={state.name}
            onChange={(event) => setState((current) => ({ ...current, name: event.target.value }))}
            placeholder="hello-web"
          />
          <FieldError message={errors.name} />
        </label>
        <label className="space-y-2 text-sm text-ink/70">
          <span>{state.source_kind === "git" ? "Runtime / base image" : "Image"}</span>
          <Input
            value={state.image}
            onChange={(event) => setState((current) => ({ ...current, image: event.target.value }))}
            placeholder="nginx:latest"
          />
          <FieldError message={errors.image} />
          {state.source_kind === "git" ? (
            <p className="text-xs text-ink/50">
              The container starts with this image while the git build runs, then swaps when ready.
            </p>
          ) : null}
        </label>
      </div>

      {state.source_kind === "git" ? (
        <div className="grid gap-4 rounded-2xl border border-ink/10 bg-mist/60 p-4">
          <p className="text-sm font-semibold">Git source</p>
          <div className="grid gap-4 md:grid-cols-2">
            <label className="space-y-2 text-sm text-ink/70 md:col-span-2">
              <span>Repository URL</span>
              <Input
                value={state.git_url}
                onChange={(event) => setState((current) => ({ ...current, git_url: event.target.value }))}
                placeholder="https://github.com/user/repo.git"
              />
              <FieldError message={errors.git_url} />
            </label>
            <label className="space-y-2 text-sm text-ink/70">
              <span>Branch</span>
              <Input
                value={state.git_branch}
                onChange={(event) => setState((current) => ({ ...current, git_branch: event.target.value }))}
                placeholder="main"
              />
            </label>
            <label className="space-y-2 text-sm text-ink/70">
              <span>Dockerfile path</span>
              <Input
                value={state.dockerfile_path}
                onChange={(event) => setState((current) => ({ ...current, dockerfile_path: event.target.value }))}
                placeholder="Dockerfile"
              />
              <FieldError message={errors.dockerfile_path} />
            </label>
          </div>

          <KeyValueList
            label="Build args"
            entries={state.build_args}
            onChange={(next) => setState((current) => ({ ...current, build_args: next }))}
            allowSecretToggle={false}
          />
        </div>
      ) : null}
    </div>
  );
}

function ResourcesStep({ state, setState, errors }: StepProps) {
  return (
    <div className="grid gap-5">
      <div className="grid gap-4 md:grid-cols-2">
        <SliderField
          label="CPU cores"
          min={0.1}
          max={8}
          step={0.1}
          value={state.cpus}
          onChange={(value) => setState((current) => ({ ...current, cpus: value }))}
          formatValue={(value) => `${value.toFixed(1)} core${value === 1 ? "" : "s"}`}
          error={errors.cpus}
        />
        <SliderField
          label="Memory"
          min={64}
          max={8192}
          step={64}
          value={state.memory_mb}
          onChange={(value) => setState((current) => ({ ...current, memory_mb: value }))}
          formatValue={(value) =>
            value >= 1024 ? `${(value / 1024).toFixed(1)} GB` : `${value} MB`
          }
          error={errors.memory_mb}
        />
      </div>
      <div className="grid gap-4 md:grid-cols-3">
        <label className="space-y-2 text-sm text-ink/70">
          <span>Disk soft limit (MB)</span>
          <Input
            value={state.disk_mb}
            placeholder="optional"
            onChange={(event) => setState((current) => ({ ...current, disk_mb: event.target.value }))}
          />
          <FieldError message={errors.disk_mb} />
          <p className="text-xs text-ink/50">
            Real disk quotas need overlay2 + xfs project quotas; this is a soft alert threshold.
          </p>
        </label>
        <label className="space-y-2 text-sm text-ink/70">
          <span>PIDs limit</span>
          <Input
            type="number"
            value={state.pids_limit}
            min={1}
            onChange={(event) =>
              setState((current) => ({
                ...current,
                pids_limit: Number(event.target.value || 256),
              }))
            }
          />
          <FieldError message={errors.pids_limit} />
        </label>
        <label className="space-y-2 text-sm text-ink/70">
          <span>Restart policy</span>
          <select
            value={state.restart_policy}
            onChange={(event) =>
              setState((current) => ({
                ...current,
                restart_policy: event.target.value as WizardState["restart_policy"],
              }))
            }
            className="flex h-12 w-full rounded-2xl border border-ink/10 bg-white px-4 text-sm text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-coral/40"
          >
            {RESTART_POLICIES.map((policy) => (
              <option key={policy} value={policy}>
                {policy}
              </option>
            ))}
          </select>
        </label>
      </div>
    </div>
  );
}

function NetworkingStep({ state, setState, errors }: StepProps) {
  const updatePort = (index: number, patch: Partial<PortRow>) => {
    setState((current) => ({
      ...current,
      ports: current.ports.map((port, i) => (i === index ? { ...port, ...patch } : port)),
    }));
  };
  const removePort = (index: number) => {
    setState((current) => ({
      ...current,
      ports: current.ports.filter((_, i) => i !== index),
    }));
  };
  const addPort = () => {
    setState((current) => ({
      ...current,
      ports: [...current.ports, { container_port: "", host_port: "" }],
    }));
  };

  const updateVolume = (index: number, patch: Partial<VolumeRow>) => {
    setState((current) => ({
      ...current,
      volumes: current.volumes.map((volume, i) => (i === index ? { ...volume, ...patch } : volume)),
    }));
  };
  const removeVolume = (index: number) => {
    setState((current) => ({
      ...current,
      volumes: current.volumes.filter((_, i) => i !== index),
    }));
  };
  const addVolume = () => {
    setState((current) => ({
      ...current,
      volumes: [...current.volumes, { source: "", target: "/data", mode: "rw" }],
    }));
  };

  return (
    <div className="grid gap-5">
      <div className="grid gap-4 md:grid-cols-2">
        <label className="space-y-2 text-sm text-ink/70">
          <span>Domain</span>
          <Input
            value={state.domain}
            placeholder="hello.example.com"
            onChange={(event) => setState((current) => ({ ...current, domain: event.target.value }))}
          />
          <FieldError message={errors.domain} />
          <p className="text-xs text-ink/50">Leave empty to use the auto-generated slug subdomain.</p>
        </label>
        <label className="space-y-2 text-sm text-ink/70">
          <span>Network</span>
          <Input
            value={state.network}
            placeholder="bridge / dmgr-default"
            onChange={(event) => setState((current) => ({ ...current, network: event.target.value }))}
          />
        </label>
      </div>

      <div className="rounded-2xl border border-ink/10 bg-mist/60 p-4">
        <div className="flex items-center justify-between">
          <p className="text-sm font-semibold">Port mappings</p>
          <Button variant="secondary" size="sm" onClick={addPort} className="gap-2">
            <Plus className="h-4 w-4" /> Add port
          </Button>
        </div>
        <div className="mt-3 space-y-3">
          {state.ports.map((port, index) => (
            <div key={index} className="grid grid-cols-[1fr_1fr_auto] gap-3">
              <div>
                <Input
                  type="number"
                  value={port.container_port}
                  placeholder="container"
                  onChange={(event) => updatePort(index, { container_port: event.target.value })}
                />
                <FieldError message={errors[`port_container_${index}`]} />
              </div>
              <div>
                <Input
                  type="number"
                  value={port.host_port}
                  placeholder="host (optional)"
                  onChange={(event) => updatePort(index, { host_port: event.target.value })}
                />
                <FieldError message={errors[`port_host_${index}`]} />
              </div>
              <Button variant="ghost" size="sm" onClick={() => removePort(index)} className="text-coral">
                <Trash2 className="h-4 w-4" />
              </Button>
            </div>
          ))}
          {!state.ports.length ? (
            <p className="text-xs text-ink/50">No port bindings — service stays on the internal network.</p>
          ) : null}
        </div>
      </div>

      <div className="rounded-2xl border border-ink/10 bg-mist/60 p-4">
        <div className="flex items-center justify-between">
          <p className="text-sm font-semibold">Volumes</p>
          <Button variant="secondary" size="sm" onClick={addVolume} className="gap-2">
            <Plus className="h-4 w-4" /> Add volume
          </Button>
        </div>
        <div className="mt-3 space-y-3">
          {state.volumes.map((volume, index) => (
            <div key={index} className="grid grid-cols-[1fr_1fr_auto_auto] gap-3">
              <div>
                <Input
                  value={volume.source}
                  placeholder="volume name"
                  onChange={(event) => updateVolume(index, { source: event.target.value })}
                />
                <FieldError message={errors[`volume_source_${index}`]} />
              </div>
              <div>
                <Input
                  value={volume.target}
                  placeholder="/data"
                  onChange={(event) => updateVolume(index, { target: event.target.value })}
                />
                <FieldError message={errors[`volume_target_${index}`]} />
              </div>
              <select
                value={volume.mode}
                onChange={(event) => updateVolume(index, { mode: event.target.value as "ro" | "rw" })}
                className="flex h-12 rounded-2xl border border-ink/10 bg-white px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-coral/40"
              >
                <option value="rw">rw</option>
                <option value="ro">ro</option>
              </select>
              <Button variant="ghost" size="sm" onClick={() => removeVolume(index)} className="text-coral">
                <Trash2 className="h-4 w-4" />
              </Button>
            </div>
          ))}
          {!state.volumes.length ? (
            <p className="text-xs text-ink/50">No volume mounts attached.</p>
          ) : null}
        </div>
      </div>
    </div>
  );
}

function EnvStep({ state, setState, errors }: StepProps) {
  return (
    <KeyValueList
      label="Environment variables"
      entries={state.env}
      onChange={(next) => setState((current) => ({ ...current, env: next }))}
      errors={errors}
      allowSecretToggle
    />
  );
}

function ReviewStep({ state }: { state: WizardState }) {
  const portSummary = state.ports
    .filter((port) => port.container_port)
    .map((port) => (port.host_port ? `${port.host_port}:${port.container_port}` : `${port.container_port}`));
  const volumeSummary = state.volumes
    .filter((volume) => volume.source && volume.target)
    .map((volume) => `${volume.source} -> ${volume.target} (${volume.mode})`);
  const envCount = state.env.length;
  const secretCount = state.env.filter((entry) => entry.is_secret).length;
  return (
    <div className="grid gap-4">
      <div className="rounded-2xl border border-ink/10 bg-mist/60 p-4">
        <p className="text-sm font-semibold">Source</p>
        <p className="text-sm text-ink/70">
          {state.source_kind === "git"
            ? `Git: ${state.git_url} @ ${state.git_branch || "default"} (${state.dockerfile_path})`
            : `Image: ${state.image}`}
        </p>
        <p className="text-sm text-ink/70">Service name: {state.name}</p>
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        <div className="rounded-2xl border border-ink/10 bg-mist/60 p-4">
          <p className="text-sm font-semibold">Resources</p>
          <p className="text-sm text-ink/70">CPU: {state.cpus} cores</p>
          <p className="text-sm text-ink/70">
            Memory: {state.memory_mb >= 1024 ? `${(state.memory_mb / 1024).toFixed(1)} GB` : `${state.memory_mb} MB`}
          </p>
          {state.disk_mb ? <p className="text-sm text-ink/70">Disk soft limit: {state.disk_mb} MB</p> : null}
          <p className="text-sm text-ink/70">PIDs: {state.pids_limit}</p>
          <p className="text-sm text-ink/70">Restart: {state.restart_policy}</p>
        </div>
        <div className="rounded-2xl border border-ink/10 bg-mist/60 p-4">
          <p className="text-sm font-semibold">Networking</p>
          <p className="text-sm text-ink/70">Domain: {state.domain || "auto-slug subdomain"}</p>
          <p className="text-sm text-ink/70">Network: {state.network || "default"}</p>
          <p className="text-sm text-ink/70">Ports: {portSummary.length ? portSummary.join(", ") : "none"}</p>
          <p className="text-sm text-ink/70">
            Volumes: {volumeSummary.length ? volumeSummary.join("; ") : "none"}
          </p>
        </div>
      </div>
      <div className="rounded-2xl border border-ink/10 bg-mist/60 p-4">
        <p className="text-sm font-semibold">Env / secrets</p>
        <p className="text-sm text-ink/70">
          {envCount === 0
            ? "No environment variables."
            : `${envCount} variable${envCount === 1 ? "" : "s"} - ${secretCount} marked as secret.`}
        </p>
        {secretCount > 0 ? (
          <p className="mt-1 text-xs text-ink/50">
            Secrets are encrypted with Fernet and applied via a single redeploy after creation.
          </p>
        ) : null}
      </div>
    </div>
  );
}

function SliderField({
  label,
  min,
  max,
  step,
  value,
  onChange,
  formatValue,
  error,
}: {
  label: string;
  min: number;
  max: number;
  step: number;
  value: number;
  onChange: (value: number) => void;
  formatValue: (value: number) => string;
  error?: string;
}) {
  return (
    <div className="space-y-2 text-sm text-ink/70">
      <div className="flex items-center justify-between">
        <span>{label}</span>
        <span className="text-ink">{formatValue(value)}</span>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(event) => onChange(Number(event.target.value))}
        className="w-full accent-ink"
      />
      <Input
        type="number"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(event) => {
          const next = Number(event.target.value);
          if (!Number.isNaN(next)) {
            onChange(next);
          }
        }}
      />
      <FieldError message={error} />
    </div>
  );
}

function KeyValueList({
  label,
  entries,
  onChange,
  errors,
  allowSecretToggle,
}: {
  label: string;
  entries: EnvRow[];
  onChange: (next: EnvRow[]) => void;
  errors?: Record<string, string>;
  allowSecretToggle: boolean;
}) {
  const update = (index: number, patch: Partial<EnvRow>) => {
    onChange(entries.map((entry, i) => (i === index ? { ...entry, ...patch } : entry)));
  };
  const remove = (index: number) => {
    onChange(entries.filter((_, i) => i !== index));
  };
  const add = () => {
    onChange([...entries, { key: "", value: "", is_secret: false }]);
  };
  return (
    <div className="rounded-2xl border border-ink/10 bg-mist/60 p-4">
      <div className="flex items-center justify-between">
        <p className="text-sm font-semibold">{label}</p>
        <Button variant="secondary" size="sm" onClick={add} className="gap-2">
          <Plus className="h-4 w-4" /> Add entry
        </Button>
      </div>
      <div className="mt-3 space-y-3">
        {entries.map((entry, index) => (
          <div
            key={index}
            className={cn(
              "grid gap-3",
              allowSecretToggle ? "grid-cols-[1fr_1fr_auto_auto]" : "grid-cols-[1fr_1fr_auto]",
            )}
          >
            <div>
              <Input
                value={entry.key}
                placeholder="KEY"
                onChange={(event) => update(index, { key: event.target.value.toUpperCase() })}
              />
              <FieldError message={errors?.[`env_key_${index}`]} />
            </div>
            <Input
              value={entry.value}
              placeholder={entry.is_secret ? "secret value" : "value"}
              type={entry.is_secret ? "password" : "text"}
              onChange={(event) => update(index, { value: event.target.value })}
            />
            {allowSecretToggle ? (
              <button
                type="button"
                onClick={() => update(index, { is_secret: !entry.is_secret })}
                className={cn(
                  "flex h-12 items-center justify-center gap-2 rounded-2xl border px-3 text-xs uppercase tracking-[0.16em]",
                  entry.is_secret ? "border-coral/40 bg-coral/10 text-coral" : "border-ink/10 bg-white text-ink/60",
                )}
              >
                {entry.is_secret ? "Secret" : "Plain"}
              </button>
            ) : null}
            <Button variant="ghost" size="sm" onClick={() => remove(index)} className="text-coral">
              <Trash2 className="h-4 w-4" />
            </Button>
          </div>
        ))}
        {!entries.length ? (
          <p className="text-xs text-ink/50">No entries yet.</p>
        ) : null}
      </div>
    </div>
  );
}
