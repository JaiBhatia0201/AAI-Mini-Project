import { useEffect, useState, type FormEvent } from "react";
import { Library, Search, Sparkles } from "lucide-react";
import { api, ApiError } from "../lib/api";
import { useApp } from "../context/AppContext";
import type { LearningResourceOut, RetrievalSearchHit } from "../types/api";
import { AlertBanner, Badge, Button, Card, ProvenanceBadge } from "../components/ui/Primitives";

export function ResourcesPage() {
  const { user, activeSyllabus } = useApp();
  const [resources, setResources] = useState<LearningResourceOut[]>([]);
  const [modality, setModality] = useState<string>("all");
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<RetrievalSearchHit[]>([]);
  const [retrievalMode, setRetrievalMode] = useState<string>("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!activeSyllabus) return;
    api
      .listResources(activeSyllabus.id)
      .then((rows) => {
        setResources(rows);
        setHits([]);
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : "Unable to load resources."));
  }, [activeSyllabus]);

  if (!activeSyllabus) {
    return (
      <Card className="p-8 text-center text-sm text-slate-600">
        Select or upload a syllabus to browse multi-modal resources.
      </Card>
    );
  }

  async function handleSearch(e?: FormEvent) {
    e?.preventDefault();
    if (!activeSyllabus) return;
    setBusy(true);
    setError(null);
    try {
      const res = await api.discoverResources({
        syllabus_id: activeSyllabus.id,
        query: query.trim(),
        top_k: 5,
      });
      setResources(res.resources);
      setHits(res.hits);
      setRetrievalMode(res.retrieval_mode);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Resource search failed.");
    } finally {
      setBusy(false);
    }
  }

  const visible = resources.filter((r) => modality === "all" || r.modality === modality);

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
            <Library className="h-5 w-5 text-indigo-600" />
            <span>Multi-Modal Learning Resources</span>
          </h1>
          <p className="text-sm text-slate-600">
            Strictly scoped to <strong>{activeSyllabus.title}</strong> with transparent provenance and retrieval mode labels.
          </p>
        </div>
        {retrievalMode && (
          <Badge tone={retrievalMode === "api_faiss" ? "indigo" : "teal"}>
            Search Engine: {retrievalMode}
          </Badge>
        )}
      </div>

      {error && <AlertBanner tone="rose" title="Resource Error" message={error} />}

      {user?.role === "student" && (
        <Card>
          <form onSubmit={(e) => void handleSearch(e)} className="flex flex-wrap gap-3">
            <div className="relative flex-1 min-w-[220px]">
              <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
              <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search concepts inside this syllabus only (or leave blank to synthesize missing notes)..."
                className="w-full rounded-lg border border-slate-300 pl-9 pr-3 py-2 text-sm"
              />
            </div>
            <Button type="submit" disabled={busy}>
              <Sparkles className="h-4 w-4" />
              <span>{busy ? "Searching..." : query.trim() ? "Search Syllabus Index" : "Synthesize Missing Notes"}</span>
            </Button>
          </form>

          {hits.length > 0 && (
            <div className="mt-4 space-y-2 border-t border-slate-200 pt-3">
              <div className="text-xs font-bold text-slate-700">
                Top Per-Syllabus Retrieval Matches ({retrievalMode})
              </div>
              {hits.map((h) => (
                <div key={h.doc_id} className="rounded-lg border border-indigo-200 bg-indigo-50/40 p-2.5 text-xs">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="font-semibold text-indigo-950">{h.title}</span>
                    <div className="flex items-center gap-1.5">
                      <Badge tone="indigo">Score {h.score.toFixed(3)}</Badge>
                      <ProvenanceBadge origin={h.source_origin} />
                    </div>
                  </div>
                  <p className="mt-1 text-slate-700">{h.snippet}</p>
                </div>
              ))}
            </div>
          )}
        </Card>
      )}

      <div className="flex flex-wrap gap-1.5">
        {["all", "notes", "flashcard", "video", "textbook", "search_query"].map((m) => (
          <button
            key={m}
            type="button"
            onClick={() => setModality(m)}
            className={`rounded-full border px-3 py-1 text-xs font-semibold capitalize cursor-pointer ${
              modality === m
                ? "border-indigo-600 bg-indigo-600 text-white"
                : "border-slate-200 bg-white text-slate-600 hover:bg-slate-50"
            }`}
          >
            {m.replace("_", " ")}
          </button>
        ))}
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        {visible.map((res) => (
          <Card key={res.id} className="space-y-2.5">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <Badge tone="indigo" className="capitalize">{res.modality.replace("_", " ")}</Badge>
              <ProvenanceBadge origin={res.source_origin} />
            </div>
            <h3 className="text-sm font-bold text-slate-900">{res.title}</h3>
            <p className="text-xs text-slate-600 leading-relaxed">{res.summary || res.url_or_content}</p>
            <div className="flex items-center justify-between pt-1 text-[11px] text-slate-500">
              <span>Source: {res.source_ref || "Syllabus Unit"}</span>
              <span>By {res.created_by_agent}</span>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}
