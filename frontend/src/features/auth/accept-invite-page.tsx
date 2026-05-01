import { useEffect, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { CheckCircle2, ShieldAlert } from "lucide-react";
import { useNavigate, useParams } from "react-router-dom";

import { AuthService, InvitesService } from "@/api/generated";
import type { TokenResponse } from "@/api/generated";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { useAuthStore } from "@/stores/auth-store";

export function AcceptInvitePage() {
  const params = useParams<{ token: string }>();
  const token = params.token ?? "";
  const navigate = useNavigate();
  const setTokens = useAuthStore((state) => state.setTokens);
  const setCurrentUser = useAuthStore((state) => state.setCurrentUser);

  const [fullName, setFullName] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [validationError, setValidationError] = useState<string | null>(null);

  const previewQuery = useQuery({
    queryKey: ["invites", "preview", token],
    queryFn: () => InvitesService.preview(token),
    enabled: Boolean(token),
    retry: false,
  });

  useEffect(() => {
    if (previewQuery.data?.full_name_hint) {
      setFullName((current) => current || previewQuery.data?.full_name_hint || "");
    }
  }, [previewQuery.data]);

  const acceptMutation = useMutation({
    mutationFn: () =>
      InvitesService.accept({ token, password, full_name: fullName.trim() }),
    onSuccess: async (response: TokenResponse) => {
      setTokens({ accessToken: response.access_token, refreshToken: response.refresh_token });
      try {
        const me = await AuthService.me();
        setCurrentUser(me);
      } catch {
        // best-effort; we still have the token
      }
      navigate("/services");
    },
  });

  if (!token) {
    return <ErrorCard title="Invalid invite link" message="The link is missing a token." />;
  }
  if (previewQuery.isLoading) {
    return (
      <Centered>
        <Card className="rounded-[32px] px-8 py-8">
          <p className="text-sm uppercase tracking-[0.2em] text-ink/45">Loading invite</p>
          <h1 className="mt-3 text-2xl font-semibold">Looking up the invitation...</h1>
        </Card>
      </Centered>
    );
  }
  if (previewQuery.isError || !previewQuery.data) {
    const message =
      previewQuery.error instanceof Error
        ? previewQuery.error.message
        : "We couldn't find that invite. It may have been revoked or expired.";
    return <ErrorCard title="Invite unavailable" message={message} />;
  }

  const preview = previewQuery.data;
  const expired = new Date(preview.expires_at).getTime() < Date.now();
  if (preview.revoked_at) {
    return <ErrorCard title="Invite revoked" message="The workspace owner revoked this invite." />;
  }
  if (preview.accepted_at) {
    return (
      <ErrorCard
        title="Already accepted"
        message="This invite has already been used. Sign in instead."
        ctaLabel="Go to login"
        onCta={() => navigate("/login")}
      />
    );
  }
  if (expired) {
    return <ErrorCard title="Invite expired" message="Ask the inviter to issue a new link." />;
  }

  const handleSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setValidationError(null);
    if (!fullName.trim()) {
      setValidationError("Please enter your full name.");
      return;
    }
    if (password.length < 8) {
      setValidationError("Password must be at least 8 characters.");
      return;
    }
    if (password !== confirmPassword) {
      setValidationError("Passwords do not match.");
      return;
    }
    acceptMutation.mutate();
  };

  const acceptError =
    acceptMutation.error instanceof Error ? acceptMutation.error.message : null;

  return (
    <Centered>
      <Card className="w-full max-w-lg rounded-[32px] px-8 py-8">
        <p className="text-sm uppercase tracking-[0.2em] text-ink/45">Invite</p>
        <h1 className="mt-2 text-2xl font-semibold">Join {preview.project_name}</h1>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <Badge tone="info">{preview.role}</Badge>
          <Badge tone="neutral">{preview.email}</Badge>
        </div>
        <p className="mt-3 text-sm text-ink/65">
          {preview.invited_by_name
            ? `${preview.invited_by_name} invited you to collaborate. `
            : ""}
          Set your password to accept and join the project.
        </p>

        <form onSubmit={handleSubmit} className="mt-6 grid gap-4">
          <label className="space-y-2 text-sm text-ink/70">
            <span>Full name</span>
            <Input
              value={fullName}
              onChange={(event) => setFullName(event.target.value)}
              placeholder="Ada Lovelace"
            />
          </label>
          <label className="space-y-2 text-sm text-ink/70">
            <span>Password</span>
            <Input
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              placeholder="At least 8 characters"
            />
          </label>
          <label className="space-y-2 text-sm text-ink/70">
            <span>Confirm password</span>
            <Input
              type="password"
              value={confirmPassword}
              onChange={(event) => setConfirmPassword(event.target.value)}
            />
          </label>

          {validationError ? (
            <p className="rounded-2xl bg-coral/10 px-4 py-3 text-sm text-coral">{validationError}</p>
          ) : null}
          {acceptError ? (
            <p className="rounded-2xl bg-coral/10 px-4 py-3 text-sm text-coral">{acceptError}</p>
          ) : null}

          <Button type="submit" disabled={acceptMutation.isPending} className="gap-2">
            <CheckCircle2 className="h-4 w-4" />
            {acceptMutation.isPending ? "Joining..." : "Accept invite"}
          </Button>
        </form>

        <p className="mt-4 text-xs text-ink/45">
          Expires {new Date(preview.expires_at).toLocaleString()}.
        </p>
      </Card>
    </Centered>
  );
}

function Centered({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-mist bg-grain p-6">
      {children}
    </div>
  );
}

function ErrorCard({
  title,
  message,
  ctaLabel,
  onCta,
}: {
  title: string;
  message: string;
  ctaLabel?: string;
  onCta?: () => void;
}) {
  return (
    <Centered>
      <Card className="w-full max-w-lg rounded-[32px] px-8 py-8">
        <div className="flex items-center gap-2 text-coral">
          <ShieldAlert className="h-5 w-5" />
          <p className="text-sm uppercase tracking-[0.2em]">Invite</p>
        </div>
        <h1 className="mt-2 text-2xl font-semibold">{title}</h1>
        <p className="mt-3 text-sm text-ink/65">{message}</p>
        {ctaLabel && onCta ? (
          <Button onClick={onCta} className="mt-5">
            {ctaLabel}
          </Button>
        ) : null}
      </Card>
    </Centered>
  );
}
