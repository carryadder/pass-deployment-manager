import { cn } from "@/lib/utils";

export type SparklineSample = {
  timestamp: string;
  value: number;
};

export function formatPercent(value?: number | null) {
  return value == null ? "--" : `${value.toFixed(1)}%`;
}

export function formatBytes(value?: number | null) {
  if (value == null) {
    return "--";
  }
  const units = ["B", "KB", "MB", "GB", "TB"];
  let current = value;
  let unitIndex = 0;
  while (current >= 1024 && unitIndex < units.length - 1) {
    current /= 1024;
    unitIndex += 1;
  }
  return `${current.toFixed(current >= 10 ? 0 : 1)} ${units[unitIndex]}`;
}

export function formatDateTime(value: string) {
  return new Date(value).toLocaleString();
}

export function buildSparklinePoints(values: number[], width: number, height: number) {
  if (!values.length) {
    return "";
  }
  if (values.length === 1) {
    const midpoint = height / 2;
    return `0,${midpoint} ${width},${midpoint}`;
  }

  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;

  return values
    .map((value, index) => {
      const x = (index / (values.length - 1)) * width;
      const y = height - ((value - min) / range) * height;
      return `${x},${y}`;
    })
    .join(" ");
}

export function Sparkline({
  samples,
  strokeClassName,
  fillClassName,
  className,
}: {
  samples: SparklineSample[];
  strokeClassName?: string;
  fillClassName?: string;
  className?: string;
}) {
  const values = samples.map((sample) => sample.value);
  const points = buildSparklinePoints(values, 100, 32);

  if (!points) {
    return <div className={cn("h-9 rounded-xl bg-ink/6", className)} />;
  }

  return (
    <svg viewBox="0 0 100 32" preserveAspectRatio="none" className={cn("h-9 w-full", className)}>
      {fillClassName ? (
        <polyline
          fill="none"
          stroke="transparent"
          points={points}
          className={fillClassName}
        />
      ) : null}
      <polyline
        fill="none"
        strokeWidth="2.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        points={points}
        className={cn("stroke-current", strokeClassName)}
      />
    </svg>
  );
}
