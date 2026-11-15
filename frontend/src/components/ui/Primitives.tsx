import type { ButtonHTMLAttributes, ReactNode } from "react";

export function cn(...classes: Array<string | false | null | undefined>): string {
  return classes.filter(Boolean).join(" ");
}

export function Card({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("rounded-xl border border-slate-200 bg-white p-5 shadow-xs", className)}>
      {children}
    </div>
  );
}

type BadgeTone = "indigo" | "teal" | "amber" | "rose" | "slate" | "emerald";

const BADGE_STYLES: Record<BadgeTone, string> = {
  indigo: "bg-indigo-50 text-indigo-700 border-indigo-200",
  teal: "bg-teal-50 text-teal-700 border-teal-200",
  amber: "bg-amber-50 text-amber-800 border-amber-200",
  rose: "bg-rose-50 text-rose-700 border-rose-200",
  slate: "bg-slate-100 text-slate-700 border-slate-200",
  emerald: "bg-emerald-50 text-emerald-700 border-emerald-200",
};

export function Badge({
  children,
  tone = "slate",
  className = "",
}: {
  children: ReactNode;
  tone?: BadgeTone;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-medium",
        BADGE_STYLES[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}

export function ProvenanceBadge({ origin }: { origin: string }) {
  if (origin === "llm_generated_summary") {
    return <Badge tone="indigo">LLM Synthesized</Badge>;
  }
  if (origin === "extracted_pdf_excerpt") {
    return <Badge tone="teal">Extracted PDF Excerpt</Badge>;
  }
  return <Badge tone="slate">Curated Dataset Note</Badge>;
}

export function Button({
  children,
  variant = "primary",
  className = "",
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost" | "danger";
}) {
  const styles = {
    primary: "bg-indigo-600 text-white hover:bg-indigo-700 shadow-xs disabled:bg-indigo-300",
    secondary: "bg-white text-slate-700 border border-slate-300 hover:bg-slate-50 disabled:opacity-50",
    ghost: "bg-transparent text-slate-600 hover:bg-slate-100 disabled:opacity-40",
    danger: "bg-rose-600 text-white hover:bg-rose-700 disabled:bg-rose-300",
  };
  return (
    <button
      {...rest}
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition-colors cursor-pointer disabled:cursor-not-allowed",
        styles[variant],
        className,
      )}
    >
      {children}
    </button>
  );
}

export function StatCard({
  label,
  value,
  hint,
  tone = "slate",
  icon,
}: {
  label: string;
  value: string | number;
  hint?: string;
  tone?: BadgeTone;
  icon?: ReactNode;
}) {
  const accentBar: Record<BadgeTone, string> = {
    indigo: "border-t-indigo-500",
    teal: "border-t-teal-500",
    amber: "border-t-amber-500",
    rose: "border-t-rose-500",
    slate: "border-t-slate-400",
    emerald: "border-t-emerald-500",
  };
  return (
    <div
      className={cn(
        "rounded-xl border border-slate-200 border-t-4 bg-white p-4 shadow-xs",
        accentBar[tone],
      )}
    >
      <div className="flex items-center justify-between text-xs font-medium text-slate-500">
        <span>{label}</span>
        {icon}
      </div>
      <div className="mt-2 text-2xl font-bold tracking-tight text-slate-900 tabular-nums">
        {value}
      </div>
      {hint && <p className="mt-1 text-xs text-slate-500">{hint}</p>}
    </div>
  );
}

export function AlertBanner({
  tone = "indigo",
  title,
  message,
  action,
}: {
  tone?: "indigo" | "amber" | "rose" | "teal";
  title?: string;
  message: string;
  action?: ReactNode;
}) {
  const styles = {
    indigo: "border-indigo-200 bg-indigo-50 text-indigo-900",
    amber: "border-amber-300 bg-amber-50 text-amber-950",
    rose: "border-rose-200 bg-rose-50 text-rose-900",
    teal: "border-teal-200 bg-teal-50 text-teal-900",
  };
  return (
    <div className={cn("flex flex-wrap items-center justify-between gap-3 rounded-xl border px-4 py-3 text-sm", styles[tone])}>
      <div>
        {title && <span className="mr-2 font-semibold">{title}:</span>}
        <span>{message}</span>
      </div>
      {action}
    </div>
  );
}
