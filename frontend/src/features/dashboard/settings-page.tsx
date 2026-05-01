import { Card } from "@/components/ui/card";
import { useAuthStore } from "@/stores/auth-store";

export function SettingsPage() {
  const user = useAuthStore((state) => state.currentUser);

  return (
    <Card className="rounded-[32px]">
      <p className="text-sm uppercase tracking-[0.2em] text-ink/45">Settings</p>
      <h3 className="mt-2 text-2xl font-semibold">Session details</h3>
      <div className="mt-6 grid gap-4 sm:grid-cols-2">
        <div className="rounded-[24px] bg-mist p-5">
          <p className="text-xs uppercase tracking-[0.18em] text-ink/45">Current user</p>
          <p className="mt-3 text-lg font-semibold">{user?.full_name ?? "Unknown"}</p>
          <p className="text-sm text-ink/65">{user?.email ?? "No email"}</p>
        </div>
        <div className="rounded-[24px] bg-mist p-5">
          <p className="text-xs uppercase tracking-[0.18em] text-ink/45">Owner access</p>
          <p className="mt-3 text-lg font-semibold">{user?.is_owner ? "Owner" : "Standard user"}</p>
          <p className="text-sm text-ink/65">
            This panel will expand into real workspace settings in the next frontend days.
          </p>
        </div>
      </div>
    </Card>
  );
}
