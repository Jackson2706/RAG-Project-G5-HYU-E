import { X } from "lucide-react";
import { useState } from "react";

import { Button, IconButton } from "@/components/ui/primitives";
import { api } from "@/services/api";

export const HELP_EXAMPLES = [
  "Which insurance rules apply to me?",
  "How do I book the international student counseling program?",
  "Can I work part time here?",
];

const REPLIES: [string, string][] = [
  ["Answer", "the official pages apply to you, so you get one direct answer."],
  ["Conditional answer", "the rule differs by student (for example Seoul vs ERICA); each case is listed."],
  ["Clarifying question", "one detail about you changes the answer, so you are asked for it first."],
  ["Please confirm", "a detail you gave earlier may be out of date."],
  ["Referred to the office", "the pages do not answer it; you are told which office to ask."],
];

/** First-visit help for a new user (dismissible; reopen it with the Help button). */
export function HelpPanel({ onClose, onExample, disabled }: { onClose: () => void; onExample: (q: string) => void; disabled: boolean }) {
  const [traceCount, setTraceCount] = useState<number | null>(null);
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  async function manageHistory(remove: boolean) {
    setPending(true);
    setMessage("");
    setError("");
    try {
      if (remove) {
        const { deleted } = await api.deleteTraces();
        setTraceCount(null);
        setMessage(`Deleted ${deleted} stored traces.`);
      } else {
        const { count } = await api.traceCount();
        setTraceCount(count);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setPending(false);
    }
  }

  return (
    <section aria-label="How to use HYU Compass" className="relative w-full rounded-xl border border-border bg-card p-4 text-left text-sm">
      <div className="absolute right-2 top-2"><IconButton label="Close help" onClick={onClose}><X className="h-4 w-4" /></IconButton></div>
      <h2 className="font-semibold">What HYU Compass is for</h2>
      <p className="mt-1 text-muted-foreground">
        Questions of new international students at Hanyang University (Seoul and ERICA campus), answered only from the official English
        pages of the international offices. Rules often differ by campus, degree, visa or TOPIK level, so tell it about yourself when you can.
      </p>
      <h3 className="mt-3 font-semibold">Try one</h3>
      <div className="mt-1 flex flex-wrap gap-1.5">
        {HELP_EXAMPLES.map((q) => (
          <button key={q} type="button" disabled={disabled} onClick={() => onExample(q)}
                  className="rounded-lg border border-border px-2.5 py-1 text-left hover:bg-muted disabled:opacity-50">{q}</button>
        ))}
      </div>
      <h3 className="mt-3 font-semibold">What the reply label means</h3>
      <ul className="mt-1 space-y-0.5 text-muted-foreground">
        {REPLIES.map(([name, text]) => <li key={name}><span className="font-medium text-foreground">{name}</span>: {text}</li>)}
      </ul>
      <p className="mt-3 text-muted-foreground">
        Every fact carries a source tag such as <span className="rounded bg-accent px-1 font-mono text-[11px] text-primary">E1</span>; click it to
        open the passage and the link to the official page. Details you mention (campus, degree, visa…) are remembered for this conversation
        only. <span className="font-medium text-foreground">Forget my details</span> or New conversation clears them.
      </p>
      <div className="mt-3 space-y-2">
        {traceCount === null ? (
          <Button size="sm" disabled={pending} onClick={() => void manageHistory(false)}>Delete stored history</Button>
        ) : (
          <div role="group" aria-label="Confirm deleting stored history" className="space-y-2 rounded-lg border border-border p-3">
            <p>Delete all {traceCount} stored request traces on this computer? This cannot be undone.</p>
            <div className="flex gap-2">
              <Button size="sm" disabled={pending} onClick={() => void manageHistory(true)}>Delete</Button>
              <Button size="sm" disabled={pending} onClick={() => { setTraceCount(null); setError(""); }}>Cancel</Button>
            </div>
          </div>
        )}
        {message && <p role="status">{message}</p>}
        {error && <p role="alert" className="text-danger">{error}</p>}
      </div>
      <p className="mt-3 rounded-lg bg-warning/10 px-3 py-2 font-medium">Not official advice; confirm with the OIA office.</p>
    </section>
  );
}
