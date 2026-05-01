import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { ArrowRight, LockKeyhole, Server } from "lucide-react";
import { useNavigate } from "react-router-dom";

import { AuthService } from "@/api/generated";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { queryClient } from "@/lib/query-client";
import { useAuthStore } from "@/stores/auth-store";

export function LoginPage() {
  const navigate = useNavigate();
  const setTokens = useAuthStore((state) => state.setTokens);
  const setCurrentUser = useAuthStore((state) => state.setCurrentUser);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const loginMutation = useMutation({
    mutationFn: AuthService.login,
    onSuccess: async (tokens) => {
      setTokens({
        accessToken: tokens.access_token,
        refreshToken: tokens.refresh_token,
      });
      const me = await AuthService.me();
      setCurrentUser(me);
      queryClient.setQueryData(["auth", "me", tokens.access_token], me);
      navigate("/", { replace: true });
    },
  });

  return (
    <div className="relative flex min-h-screen overflow-hidden bg-mist bg-grain">
      <div className="absolute inset-0 opacity-60">
        <div className="absolute left-[-10%] top-[-5%] h-64 w-64 rounded-full bg-coral/25 blur-3xl" />
        <div className="absolute bottom-[-10%] right-[-5%] h-72 w-72 rounded-full bg-cyan/25 blur-3xl" />
      </div>
      <div className="relative z-10 mx-auto grid min-h-screen w-full max-w-6xl gap-10 px-6 py-10 lg:grid-cols-[1.2fr_0.8fr] lg:px-10">
        <section className="flex flex-col justify-between rounded-[36px] border border-ink/10 bg-ink px-8 py-10 text-mist shadow-panel">
          <div className="space-y-5">
            <div className="inline-flex items-center gap-3 rounded-full bg-white/10 px-4 py-2 text-xs uppercase tracking-[0.28em] text-mist/80">
              <Server className="h-4 w-4" />
              Deployment Manager
            </div>
            <div className="max-w-2xl space-y-4">
              <h1 className="font-serif text-4xl leading-tight sm:text-5xl">
                Ship, observe, and recover services from one bright control room.
              </h1>
              <p className="max-w-xl text-base text-mist/75 sm:text-lg">
                The first frontend slice is focused on fast operator access: sign in, confirm the
                current user, and step into a protected shell with the system inventory already
                wired up.
              </p>
            </div>
          </div>
          <div className="grid gap-4 sm:grid-cols-3">
            {[
              ["Live inventory", "Containers, volumes, and networks are ready to browse."],
              ["Protected shell", "Session state is stored locally and hydrated on reload."],
              ["API-ready", "The scaffold includes an OpenAPI generation path for later refreshes."],
            ].map(([title, copy]) => (
              <div key={title} className="rounded-3xl border border-white/10 bg-white/5 p-5">
                <p className="text-sm font-semibold uppercase tracking-[0.2em] text-mist/70">{title}</p>
                <p className="mt-3 text-sm text-mist/70">{copy}</p>
              </div>
            ))}
          </div>
        </section>

        <section className="flex items-center">
          <Card className="w-full rounded-[32px] p-8 sm:p-10">
            <div className="mb-8 space-y-3">
              <div className="inline-flex items-center gap-2 rounded-full bg-coral/10 px-3 py-1 text-xs font-semibold uppercase tracking-[0.2em] text-coral">
                <LockKeyhole className="h-4 w-4" />
                Secure Entry
              </div>
              <h2 className="text-3xl font-semibold tracking-tight">Log in to your workspace</h2>
              <p className="text-sm text-ink/65">
                Use the backend owner account from Day 5 or your bootstrap admin credentials.
              </p>
            </div>

            <form
              className="space-y-5"
              onSubmit={(event) => {
                event.preventDefault();
                loginMutation.mutate({ email, password });
              }}
            >
              <div className="space-y-2">
                <label className="text-sm font-medium text-ink/70" htmlFor="email">
                  Email
                </label>
                <Input
                  id="email"
                  type="email"
                  autoComplete="email"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  placeholder="owner@example.com"
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium text-ink/70" htmlFor="password">
                  Password
                </label>
                <Input
                  id="password"
                  type="password"
                  autoComplete="current-password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  placeholder="********"
                />
              </div>
              {loginMutation.isError ? (
                <p className="rounded-2xl bg-coral/10 px-4 py-3 text-sm text-coral">
                  {loginMutation.error instanceof Error
                    ? loginMutation.error.message
                    : "Unable to log in."}
                </p>
              ) : null}
              <Button className="w-full gap-2" size="lg" type="submit" disabled={loginMutation.isPending}>
                {loginMutation.isPending ? "Signing in..." : "Open dashboard"}
                <ArrowRight className="h-4 w-4" />
              </Button>
            </form>
          </Card>
        </section>
      </div>
    </div>
  );
}
