import { useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Copy, Crown, Mail, RefreshCw, Trash2, UserPlus } from "lucide-react";

import { InvitesService, ProjectsService } from "@/api/generated";
import type {
  InviteSummary,
  ProjectMemberEntry,
  ProjectSummary,
} from "@/api/generated";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { queryClient } from "@/lib/query-client";

const ROLE_OPTIONS: Array<{ value: "admin" | "member" | "viewer"; label: string; description: string }> = [
  { value: "admin", label: "Admin", description: "Manage members + deploy + edit env." },
  { value: "member", label: "Member", description: "Deploy + edit env. Cannot manage members." },
  { value: "viewer", label: "Viewer", description: "Read-only access. No mutations." },
];

function buildAcceptUrl(invite: InviteSummary): string {
  if (invite.accept_url && invite.accept_url.startsWith("http")) {
    return invite.accept_url;
  }
  if (typeof window === "undefined") {
    return invite.accept_url;
  }
  return `${window.location.origin}/accept-invite/${invite.token}`;
}

export function TeamPage() {
  const projectsQuery = useQuery({
    queryKey: ["projects", "list"],
    queryFn: ProjectsService.list,
  });

  const adminProjects = useMemo(
    () => (projectsQuery.data ?? []).filter((project) => project.role === "admin"),
    [projectsQuery.data],
  );

  return (
    <div className="grid gap-6">
      <Card className="rounded-[32px]">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-sm uppercase tracking-[0.2em] text-ink/45">Team</p>
            <h3 className="mt-2 text-2xl font-semibold">Projects, members, and invites</h3>
            <p className="mt-2 max-w-2xl text-sm text-ink/65">
              Each project has its own member list. Owners always count as admin. Issue an invite
              link to bring someone new in — they accept it to set their password and join with the
              role you chose.
            </p>
          </div>
          <Button variant="secondary" className="gap-2" onClick={() => projectsQuery.refetch()}>
            <RefreshCw className="h-4 w-4" /> Refresh
          </Button>
        </div>
        {projectsQuery.isError ? (
          <p className="mt-4 rounded-2xl bg-coral/10 px-4 py-3 text-sm text-coral">
            {projectsQuery.error instanceof Error
              ? projectsQuery.error.message
              : "Unable to load projects."}
          </p>
        ) : null}
      </Card>

      {(projectsQuery.data ?? []).map((project) => (
        <ProjectMembersBlock
          key={project.id}
          project={project}
          showInviteForm={project.role === "admin"}
        />
      ))}

      {adminProjects.length === 0 && projectsQuery.isFetched && !projectsQuery.isError ? (
        <Card className="rounded-[32px]">
          <p className="text-sm text-ink/55">
            You don&apos;t admin any projects yet. Ask the workspace owner to make you an admin or
            create a project for you.
          </p>
        </Card>
      ) : null}
    </div>
  );
}

function ProjectMembersBlock({
  project,
  showInviteForm,
}: {
  project: ProjectSummary;
  showInviteForm: boolean;
}) {
  const membersQuery = useQuery({
    queryKey: ["projects", "members", project.id],
    queryFn: () => ProjectsService.members(project.id),
  });
  const invitesQuery = useQuery({
    queryKey: ["invites", "list", project.id],
    queryFn: () => InvitesService.list(project.id),
    enabled: showInviteForm,
  });

  const removeMutation = useMutation({
    mutationFn: (userId: string) => ProjectsService.removeMember(project.id, userId),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["projects", "members", project.id] });
    },
  });

  const updateRoleMutation = useMutation({
    mutationFn: (variables: { userId: string; role: "admin" | "member" | "viewer" }) =>
      ProjectsService.updateMember(project.id, variables.userId, { role: variables.role }),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["projects", "members", project.id] });
    },
  });

  const removeError =
    removeMutation.error instanceof Error ? removeMutation.error.message : null;

  return (
    <Card className="rounded-[32px]">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h4 className="text-xl font-semibold">{project.name}</h4>
            <Badge tone={project.role === "admin" ? "info" : "neutral"}>{project.role}</Badge>
            <Badge tone="neutral">{project.service_count} services</Badge>
            <Badge tone="neutral">{project.member_count} members</Badge>
          </div>
          {project.description ? (
            <p className="mt-2 text-sm text-ink/65">{project.description}</p>
          ) : null}
          <p className="mt-1 text-xs text-ink/50">slug: {project.slug}</p>
        </div>
      </div>

      {removeError ? (
        <p className="mt-4 rounded-2xl bg-coral/10 px-4 py-3 text-sm text-coral">{removeError}</p>
      ) : null}

      <div className="mt-5 grid gap-3">
        {(membersQuery.data ?? []).map((member) => (
          <MemberRow
            key={member.user_id}
            member={member}
            canManage={showInviteForm && !member.is_owner}
            busy={
              (removeMutation.isPending && removeMutation.variables === member.user_id) ||
              (updateRoleMutation.isPending && updateRoleMutation.variables?.userId === member.user_id)
            }
            onRoleChange={(role) =>
              updateRoleMutation.mutate({ userId: member.user_id, role })
            }
            onRemove={() => removeMutation.mutate(member.user_id)}
          />
        ))}
        {!membersQuery.isLoading && !(membersQuery.data ?? []).length ? (
          <p className="text-sm text-ink/55">No members yet.</p>
        ) : null}
      </div>

      {showInviteForm ? (
        <InviteFormBlock project={project} invites={invitesQuery.data ?? []} />
      ) : null}
    </Card>
  );
}

function MemberRow({
  member,
  canManage,
  busy,
  onRoleChange,
  onRemove,
}: {
  member: ProjectMemberEntry;
  canManage: boolean;
  busy: boolean;
  onRoleChange: (role: "admin" | "member" | "viewer") => void;
  onRemove: () => void;
}) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-ink/10 bg-mist/70 p-4">
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <p className="truncate font-medium">{member.full_name}</p>
          {member.is_owner ? (
            <Badge tone="warning" className="gap-1">
              <Crown className="h-3 w-3" /> owner
            </Badge>
          ) : null}
        </div>
        <p className="mt-1 truncate text-sm text-ink/55">{member.email}</p>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        {canManage ? (
          <select
            value={member.role}
            onChange={(event) => onRoleChange(event.target.value as "admin" | "member" | "viewer")}
            disabled={busy}
            className="flex h-10 rounded-2xl border border-ink/10 bg-white px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-coral/40"
          >
            {ROLE_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        ) : (
          <Badge tone={member.role === "admin" ? "info" : "neutral"}>{member.role}</Badge>
        )}
        {canManage ? (
          <Button
            variant="ghost"
            size="sm"
            className="text-coral"
            disabled={busy}
            onClick={onRemove}
          >
            <Trash2 className="mr-2 h-4 w-4" /> Remove
          </Button>
        ) : null}
      </div>
    </div>
  );
}

function InviteFormBlock({
  project,
  invites,
}: {
  project: ProjectSummary;
  invites: InviteSummary[];
}) {
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<"admin" | "member" | "viewer">("member");
  const [fullName, setFullName] = useState("");
  const [lastIssued, setLastIssued] = useState<InviteSummary | null>(null);

  const inviteMutation = useMutation({
    mutationFn: () =>
      InvitesService.create({
        email: email.trim(),
        project_id: project.id,
        role,
        full_name_hint: fullName.trim() || null,
      }),
    onSuccess: (invite) => {
      setLastIssued(invite);
      setEmail("");
      setFullName("");
      queryClient.invalidateQueries({ queryKey: ["invites", "list", project.id] });
      queryClient.invalidateQueries({ queryKey: ["projects", "members", project.id] });
    },
  });
  const revokeMutation = useMutation({
    mutationFn: (inviteId: string) => InvitesService.revoke(inviteId),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["invites", "list", project.id] });
    },
  });

  const inviteError =
    inviteMutation.error instanceof Error ? inviteMutation.error.message : null;
  const revokeError =
    revokeMutation.error instanceof Error ? revokeMutation.error.message : null;

  const pendingInvites = invites.filter((invite) => !invite.accepted_at && !invite.revoked_at);
  const recentInvites = invites.filter((invite) => invite.accepted_at || invite.revoked_at).slice(0, 3);

  return (
    <div className="mt-6 grid gap-4 rounded-2xl border border-ink/10 bg-white/70 p-5">
      <div className="flex items-center gap-2">
        <UserPlus className="h-4 w-4 text-slate" />
        <p className="text-sm font-semibold">Invite a teammate</p>
      </div>
      <div className="grid gap-3 md:grid-cols-[2fr_2fr_1fr_auto]">
        <Input
          value={email}
          placeholder="teammate@example.com"
          onChange={(event) => setEmail(event.target.value)}
        />
        <Input
          value={fullName}
          placeholder="Full name (optional)"
          onChange={(event) => setFullName(event.target.value)}
        />
        <select
          value={role}
          onChange={(event) => setRole(event.target.value as "admin" | "member" | "viewer")}
          className="flex h-12 rounded-2xl border border-ink/10 bg-white px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-coral/40"
        >
          {ROLE_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
        <Button
          onClick={() => inviteMutation.mutate()}
          disabled={!email.trim() || inviteMutation.isPending}
          className="gap-2"
        >
          <Mail className="h-4 w-4" />
          {inviteMutation.isPending ? "Issuing..." : "Issue invite"}
        </Button>
      </div>
      <p className="text-xs text-ink/55">
        {ROLE_OPTIONS.find((option) => option.value === role)?.description}
      </p>

      {inviteError ? (
        <p className="rounded-2xl bg-coral/10 px-4 py-3 text-sm text-coral">{inviteError}</p>
      ) : null}
      {revokeError ? (
        <p className="rounded-2xl bg-coral/10 px-4 py-3 text-sm text-coral">{revokeError}</p>
      ) : null}

      {lastIssued ? <InviteSuccessBanner invite={lastIssued} /> : null}

      {pendingInvites.length ? (
        <div className="space-y-2">
          <p className="text-xs uppercase tracking-[0.18em] text-ink/45">Pending invites</p>
          <div className="space-y-2">
            {pendingInvites.map((invite) => (
              <InviteRow
                key={invite.id}
                invite={invite}
                canRevoke
                busy={revokeMutation.isPending && revokeMutation.variables === invite.id}
                onRevoke={() => revokeMutation.mutate(invite.id)}
              />
            ))}
          </div>
        </div>
      ) : null}

      {recentInvites.length ? (
        <div className="space-y-2">
          <p className="text-xs uppercase tracking-[0.18em] text-ink/45">Recent</p>
          <div className="space-y-2">
            {recentInvites.map((invite) => (
              <InviteRow key={invite.id} invite={invite} canRevoke={false} busy={false} onRevoke={() => undefined} />
            ))}
          </div>
        </div>
      ) : null}
    </div>
  );
}

function InviteSuccessBanner({ invite }: { invite: InviteSummary }) {
  const url = buildAcceptUrl(invite);
  const handleCopy = () => {
    if (typeof navigator !== "undefined" && navigator.clipboard) {
      void navigator.clipboard.writeText(url);
    }
  };
  return (
    <div className="rounded-2xl border border-moss/30 bg-moss/10 p-4">
      <p className="text-sm font-semibold text-slate">Invite link ready for {invite.email}</p>
      <p className="mt-1 text-xs text-ink/55">
        Send this URL to the invitee. It expires {new Date(invite.expires_at).toLocaleString()}.
      </p>
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <code className="flex-1 truncate rounded-2xl bg-white/80 px-3 py-2 text-xs">{url}</code>
        <Button variant="secondary" size="sm" onClick={handleCopy} className="gap-2">
          <Copy className="h-4 w-4" /> Copy
        </Button>
      </div>
    </div>
  );
}

function InviteRow({
  invite,
  canRevoke,
  busy,
  onRevoke,
}: {
  invite: InviteSummary;
  canRevoke: boolean;
  busy: boolean;
  onRevoke: () => void;
}) {
  const url = buildAcceptUrl(invite);
  const status = invite.revoked_at ? "revoked" : invite.accepted_at ? "accepted" : "pending";
  const tone: "success" | "warning" | "info" | "neutral" =
    status === "accepted" ? "success" : status === "revoked" ? "warning" : "info";
  const handleCopy = () => {
    if (typeof navigator !== "undefined" && navigator.clipboard) {
      void navigator.clipboard.writeText(url);
    }
  };
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-ink/10 bg-mist/70 p-3">
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <p className="truncate font-medium">{invite.email}</p>
          <Badge tone={tone}>{status}</Badge>
          <Badge tone="neutral">{invite.role}</Badge>
        </div>
        <p className="mt-1 text-xs text-ink/55">
          Expires {new Date(invite.expires_at).toLocaleString()}
        </p>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        {status === "pending" ? (
          <Button variant="secondary" size="sm" onClick={handleCopy} className="gap-2">
            <Copy className="h-4 w-4" /> Copy link
          </Button>
        ) : null}
        {canRevoke && status === "pending" ? (
          <Button
            variant="ghost"
            size="sm"
            className="text-coral"
            disabled={busy}
            onClick={onRevoke}
          >
            <Trash2 className="mr-2 h-4 w-4" /> Revoke
          </Button>
        ) : null}
      </div>
    </div>
  );
}

