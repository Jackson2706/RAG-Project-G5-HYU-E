// Small reusable building blocks (styled with Tailwind; Radix provides accessible behaviour).
import { Slider as RSlider, Tabs as RTabs, Tooltip as RTooltip } from "radix-ui";
import { Check, Copy } from "lucide-react";
import { useState, type ButtonHTMLAttributes, type ComponentProps, type ReactNode } from "react";

import { cn, copyText } from "@/lib/utils";

const variants = {
  primary: "bg-primary text-primary-foreground hover:opacity-90",
  ghost: "text-muted-foreground hover:bg-muted hover:text-foreground",
  outline: "border border-border bg-card hover:bg-muted",
};
const sizes = { sm: "h-8 px-2.5 text-xs gap-1.5", md: "h-9 px-3.5 text-sm gap-2", icon: "h-8 w-8 justify-center" };

export function Button({ className, variant = "outline", size = "md", type = "button", ...props }:
  ButtonHTMLAttributes<HTMLButtonElement> & { variant?: keyof typeof variants; size?: keyof typeof sizes }) {
  return (
    <button type={type} className={cn("inline-flex shrink-0 items-center rounded-lg font-medium transition-colors disabled:opacity-50", variants[variant], sizes[size], className)} {...props} />
  );
}

export function Tooltip({ content, children }: { content: ReactNode; children: ReactNode }) {
  return (
    <RTooltip.Root delayDuration={300}>
      <RTooltip.Trigger asChild>{children}</RTooltip.Trigger>
      <RTooltip.Portal>
        <RTooltip.Content sideOffset={6} className="z-50 max-w-xs rounded-md bg-foreground px-2.5 py-1.5 text-xs text-background shadow-md">{content}</RTooltip.Content>
      </RTooltip.Portal>
    </RTooltip.Root>
  );
}

export const TooltipProvider = RTooltip.Provider;

/** Icon-only button: always has a label for screen readers and a tooltip. */
export function IconButton({ label, children, ...props }: { label: string; children: ReactNode } & ComponentProps<typeof Button>) {
  return (
    <Tooltip content={label}>
      <Button variant="ghost" size="icon" aria-label={label} {...props}>{children}</Button>
    </Tooltip>
  );
}

const tones = {
  neutral: "bg-muted text-muted-foreground",
  success: "bg-success/12 text-success",
  warning: "bg-warning/12 text-warning",
  danger: "bg-danger/12 text-danger",
  info: "bg-info/12 text-info",
};

export function Badge({ tone = "neutral", className, children }: { tone?: keyof typeof tones; className?: string; children: ReactNode }) {
  return <span className={cn("inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[11px] font-medium", tones[tone], className)}>{children}</span>;
}

export function Slider({ value, min, max, step, onChange, label }: { value: number; min: number; max: number; step: number; onChange: (v: number) => void; label: string }) {
  return (
    <RSlider.Root value={[value]} min={min} max={max} step={step} onValueChange={(v) => onChange(v[0])} className="relative flex h-5 w-full touch-none select-none items-center">
      <RSlider.Track className="relative h-1.5 grow rounded-full bg-muted">
        <RSlider.Range className="absolute h-full rounded-full bg-primary" />
      </RSlider.Track>
      <RSlider.Thumb aria-label={label} className="block h-4 w-4 rounded-full border-2 border-primary bg-card shadow" />
    </RSlider.Root>
  );
}

export const Tabs = RTabs.Root;
export const TabsContent = RTabs.Content;

export function TabsList({ className, ...props }: ComponentProps<typeof RTabs.List>) {
  return <RTabs.List className={cn("inline-flex items-center gap-1 rounded-lg bg-muted p-1", className)} {...props} />;
}

export function TabsTrigger({ className, ...props }: ComponentProps<typeof RTabs.Trigger>) {
  return (
    <RTabs.Trigger className={cn("rounded-md px-3 py-1 text-xs font-medium text-muted-foreground transition-colors data-[state=active]:bg-card data-[state=active]:text-foreground data-[state=active]:shadow-sm", className)} {...props} />
  );
}

export function CopyButton({ text, label = "Copy" }: { text: string; label?: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <IconButton label={copied ? "Copied" : label} onClick={async () => {
      if (await copyText(text)) {
        setCopied(true);
        setTimeout(() => setCopied(false), 1500);
      }
    }}>
      {copied ? <Check className="h-3.5 w-3.5 text-success" /> : <Copy className="h-3.5 w-3.5" />}
    </IconButton>
  );
}
