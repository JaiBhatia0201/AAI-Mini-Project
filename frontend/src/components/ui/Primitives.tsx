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
  if (origin === "live_web_search") {
    return <Badge tone="emerald">Live Internet Search</Badge>;
  }
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
      <div className="min-w-0 flex-1">
        {title && <span className="mr-2 font-semibold">{title}:</span>}
        <FormattedText text={message} inline />
      </div>
      {action}
    </div>
  );
}

function renderInlineMarkdown(text: string): ReactNode[] {
  const cleaned = text.replace(/\b(?:syl_[a-z0-9]+|gate_cse_[a-z0-9_]+)::/gi, "");
  const tokens = cleaned.split(/(\*\*[^*]+\*\*|`[^`]+`|\*[^*\n]+\*)/g);
  return tokens.map((tok, idx) => {
    if (tok.startsWith("**") && tok.endsWith("**") && tok.length > 4) {
      return (
        <strong key={idx} className="font-semibold text-slate-900">
          {tok.slice(2, -2)}
        </strong>
      );
    }
    if (tok.startsWith("`") && tok.endsWith("`") && tok.length > 2) {
      return (
        <code key={idx} className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-[0.9em] text-indigo-800">
          {tok.slice(1, -1)}
        </code>
      );
    }
    if (tok.startsWith("*") && tok.endsWith("*") && tok.length > 2) {
      return (
        <em key={idx} className="italic">
          {tok.slice(1, -1)}
        </em>
      );
    }
    return tok;
  });
}

export function FormattedText({
  text,
  className = "",
  inline = false,
}: {
  text: string;
  className?: string;
  inline?: boolean;
}) {
  if (!text) return null;
  if (inline) {
    return <span className={className}>{renderInlineMarkdown(text)}</span>;
  }

  const parts = text.split(/(```[\s\S]*?```)/g);
  const blocks: ReactNode[] = [];

  parts.forEach((part, pIdx) => {
    if (part.startsWith("```") && part.endsWith("```")) {
      const codeBody = part.replace(/^```[a-zA-Z0-9_-]*\n?/, "").replace(/\n?```$/, "");
      blocks.push(
        <pre
          key={`code-${pIdx}`}
          className="overflow-x-auto rounded-lg border border-slate-200 bg-slate-900 p-3 font-mono text-xs leading-relaxed text-slate-100"
        >
          <code>{codeBody}</code>
        </pre>,
      );
      return;
    }

    const lines = part.split(/\r?\n/);
    let listItems: string[] = [];
    let orderedList = false;

    const flushList = (keySuffix: string) => {
      if (listItems.length === 0) return;
      const Tag = orderedList ? "ol" : "ul";
      blocks.push(
        <Tag
          key={`list-${pIdx}-${keySuffix}`}
          className={cn(
            "space-y-1.5 pl-5 text-sm leading-relaxed text-slate-700",
            orderedList ? "list-decimal" : "list-disc",
          )}
        >
          {listItems.map((item, i) => (
            <li key={i}>{renderInlineMarkdown(item)}</li>
          ))}
        </Tag>,
      );
      listItems = [];
    };

    lines.forEach((rawLine, lIdx) => {
      const line = rawLine.trim();
      if (!line) {
        flushList(`blank-${lIdx}`);
        return;
      }

      const headingMatch = line.match(/^(#{1,4})\s+(.*)$/);
      if (headingMatch) {
        flushList(`h-${lIdx}`);
        blocks.push(
          <h4 key={`h-${pIdx}-${lIdx}`} className="pt-1 text-sm font-bold text-slate-900">
            {renderInlineMarkdown(headingMatch[2])}
          </h4>,
        );
        return;
      }

      const bulletMatch = line.match(/^[-*•]\s+(.*)$/);
      if (bulletMatch) {
        if (listItems.length > 0 && orderedList) flushList(`switch-u-${lIdx}`);
        orderedList = false;
        listItems.push(bulletMatch[1]);
        return;
      }

      const numMatch = line.match(/^\d+[.)]\s+(.*)$/);
      if (numMatch) {
        if (listItems.length > 0 && !orderedList) flushList(`switch-o-${lIdx}`);
        orderedList = true;
        listItems.push(numMatch[1]);
        return;
      }

      flushList(`p-${lIdx}`);
      blocks.push(
        <p key={`p-${pIdx}-${lIdx}`} className="text-sm leading-relaxed text-slate-700">
          {renderInlineMarkdown(line)}
        </p>,
      );
    });

    flushList("end");
  });

  return <div className={cn("space-y-2.5", className)}>{blocks}</div>;
}
