import { Database, Loader2, RefreshCw } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { Badge, Button, Dialog } from "@/components/ui/primitives";
import type { PipelineConfigState } from "@/hooks/usePipelineConfig";
import type { SystemState } from "@/hooks/useSystem";
import { offlineConfig } from "@/lib/config";
import { api } from "@/services/api";
import type { DocumentSummary } from "@/types/api";

interface Report {
  status: string;
  revision_id: string | null;
  doc_count: number;
  chunk_count: number;
  vectors_computed: number;
  vectors_reused: number;
  error: string | null;
  verification?: { ok: boolean; errors: string[]; warnings: string[] };
  documents: { source_uri: string; status: string; chunks: number; error: string | null }[];
  load_issues: { path: string; error: string }[];
}

export function IndexDialog({ open, onOpenChange, cfg, system }: { open: boolean; onOpenChange: (o: boolean) => void; cfg: PipelineConfigState; system: SystemState }) {
  const [docs, setDocs] = useState<DocumentSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [running, setRunning] = useState<string | null>(null);
  const [report, setReport] = useState<Report | null>(null);
  const active = system.health?.active_index;

  const load = useCallback(async () => {
    setError(null);
    try {
      setDocs((await api.documents()).documents);
    } catch (err) {
      setDocs([]);
      setError((err as Error).message);
    }
  }, []);

  useEffect(() => {
    if (open) void load();
  }, [open, load]);

  const rebuild = async (path: string) => {
    if (!cfg.registry || !cfg.draft) return;
    setRunning(path);
    setReport(null);
    try {
      setReport((await api.ingestLocal(path, offlineConfig(cfg.registry, cfg.draft))) as unknown as Report);
      await Promise.all([load(), system.refreshHealth(), cfg.reload()]);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setRunning(null);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange} title="Index & Documents" description="Active index revision, indexed documents and rebuilds">
      <div className="space-y-4 p-5 text-sm">
        <section className="rounded-xl border border-border bg-surface p-3">
          <h3 className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground"><Database className="h-3.5 w-3.5" /> Active index</h3>
          {active ? (
            <div className="flex flex-wrap gap-1.5">
              <Badge tone="primary">revision {active.revision_id}</Badge>
              <Badge>{active.doc_count} documents</Badge>
              <Badge>{active.chunk_count} chunks</Badge>
              <Badge>{active.embedding_model} · {active.dimension}-d</Badge>
              <Badge>Qdrant {system.health?.qdrant.mode}</Badge>
            </div>
          ) : (
            <p className="text-xs text-muted-foreground">No active index. Rebuild from a corpus folder below.</p>
          )}
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <Button size="sm" variant="primary" disabled={!!running || !cfg.validation?.valid} onClick={() => rebuild("raw")}>
              {running === "raw" ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />} Rebuild from data/raw
            </Button>
            <Button size="sm" variant="outline" disabled={!!running || !cfg.validation?.valid} onClick={() => rebuild("samples")}>
              {running === "samples" ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />} Rebuild from data/samples (synthetic)
            </Button>
          </div>
          <p className="mt-1.5 text-[11px] text-muted-foreground">
            Uses the offline-stage settings from the Configuration tab. A new revision is built and verified before the active alias moves; on failure the current index keeps serving.
          </p>
        </section>

        {report && (
          <section className="rounded-xl border border-border p-3 text-xs" role="status">
            <p className="font-medium">
              Rebuild {report.status} · revision {report.revision_id} · {report.doc_count} docs · {report.chunk_count} chunks · {report.vectors_computed} embedded · {report.vectors_reused} reused
            </p>
            {report.error && <p className="mt-1 text-danger">{report.error}</p>}
            {report.verification && <p className="mt-1">Verification: {report.verification.ok ? "passed" : "failed"} {[...report.verification.errors, ...report.verification.warnings].join("; ")}</p>}
            {report.documents.filter((d) => d.error).map((d) => <p key={d.source_uri} className="text-danger">{d.source_uri}: {d.error}</p>)}
            {report.load_issues.map((i) => <p key={i.path} className="text-warning">{i.path}: {i.error}</p>)}
          </section>
        )}

        {error && <p className="text-xs text-danger" role="alert">{error}</p>}

        <section>
          <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Documents in the active index</h3>
          {docs === null ? (
            <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" aria-label="Loading documents" />
          ) : docs.length === 0 ? (
            <p className="text-xs text-muted-foreground">No documents.</p>
          ) : (
            <ul className="space-y-1.5">
              {docs.map((d) => (
                <li key={d.doc_id} className="rounded-lg border border-border p-2.5">
                  <div className="flex flex-wrap items-center gap-1.5">
                    <span className="font-medium">{d.title ?? d.source_uri}</span>
                    <Badge>{d.media_type}</Badge>
                  </div>
                  <p className="font-mono text-[11px] text-muted-foreground">{d.source_uri} · version {d.version_id}</p>
                  <div className="mt-1 flex flex-wrap gap-1">
                    {(["campus", "document_type", "academic_year"] as const).map((k) => (
                      <Badge key={k} tone={d[k] ? "neutral" : "warning"}>{k}: {d[k] ?? "unknown"}{d[k] && d.metadata_provenance[k] === "rule" ? " (rule)" : ""}</Badge>
                    ))}
                    <Badge tone={d.audience.length ? "neutral" : "warning"}>audience: {d.audience.join(", ") || "unknown"}</Badge>
                    {d.topics.length > 0 && <Badge>topics: {d.topics.join(", ")}{d.metadata_provenance.topics === "rule" ? " (rule)" : ""}</Badge>}
                  </div>
                  {d.parse_warnings.map((w) => <p key={w} className="mt-1 text-[11px] text-warning">{w}</p>)}
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </Dialog>
  );
}
