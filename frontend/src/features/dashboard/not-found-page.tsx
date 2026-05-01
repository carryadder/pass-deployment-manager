import { Link } from "react-router-dom";

import { buttonVariants } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";

export function NotFoundPage() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-mist bg-grain p-6">
      <Card className="max-w-lg rounded-[32px] text-center">
        <p className="text-sm uppercase tracking-[0.24em] text-ink/45">404</p>
        <h1 className="mt-3 text-3xl font-semibold">This route has not been designed yet.</h1>
        <p className="mt-4 text-sm text-ink/65">
          Head back to the shell and keep building from the authenticated frontend bootstrap.
        </p>
        <Link to="/" className={cn(buttonVariants({}), "mt-6 inline-flex")}>
          Return home
        </Link>
      </Card>
    </div>
  );
}
