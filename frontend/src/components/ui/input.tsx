import * as React from "react";

import { cn } from "@/lib/utils";

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {}

const Input = React.forwardRef<HTMLInputElement, InputProps>(({ className, ...props }, ref) => (
  <input
    ref={ref}
    className={cn(
      "flex h-12 w-full rounded-2xl border border-ink/10 bg-white px-4 text-sm text-ink placeholder:text-ink/45 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-coral/40",
      className,
    )}
    {...props}
  />
));

Input.displayName = "Input";

export { Input };
