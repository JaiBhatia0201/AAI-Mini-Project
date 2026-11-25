import { useMemo, useState } from "react";
import {
  Background,
  Controls,
  MarkerType,
  MiniMap,
  ReactFlow,
  type Edge,
  type Node,
} from "@xyflow/react";
import { Check, GitFork, Trash2 } from "lucide-react";
import { api, ApiError } from "../lib/api";
import { useApp } from "../context/AppContext";
import type { SyllabusTopicOut, TopicPrerequisiteOut } from "../types/api";
import { AlertBanner, Badge, Button, Card, ProvenanceBadge } from "../components/ui/Primitives";

function masteryTone(score: number, status: string): { bg: string; border: string; badge: "rose" | "amber" | "emerald" } {
  if (score < 60 || status === "weak") {
    return { bg: "#FFF1F2", border: "#E11D48", badge: "rose" };
  }
  if (score < 80) {
    return { bg: "#FFFBEB", border: "#D97706", badge: "amber" };
  }
  return { bg: "#ECFDF5", border: "#059669", badge: "emerald" };
}

export function KnowledgeGraphPage() {
  const { user, activeSyllabus, activeGraph, refreshWorkspace, setActiveTab, setSelectedTutorTopicId } = useApp();
  const [crucialOnly, setCrucialOnly] = useState(true);
  const [selectedTopic, setSelectedTopic] = useState<SyllabusTopicOut | null>(null);
  const [selectedEdge, setSelectedEdge] = useState<TopicPrerequisiteOut | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isStudent = user?.role === "student";

  const { nodes, edges, crucialCount, totalCount } = useMemo(() => {
    if (!activeGraph) {
      return { nodes: [] as Node[], edges: [] as Edge[], crucialCount: 0, totalCount: 0 };
    }
    const allTopics = activeGraph.topics;
    const allPrereqs = activeGraph.prerequisites;

    // Identify crucial topics: weak (<60%), fading retention (<0.65), weak prerequisite blockers (<65%),
    // and top high-weightage exam topics (capped to keep large 40-topic graphs clean and readable).
    const weakIds = new Set(
      allTopics.filter((t) => t.mastery_score < 60 || t.status === "weak").map((t) => t.id),
    );
    const topicById = Object.fromEntries(allTopics.map((t) => [t.id, t]));
    const blockerIds = new Set<string>();
    for (const e of allPrereqs) {
      if (weakIds.has(e.dependent_topic_id)) {
        const pre = topicById[e.prerequisite_topic_id];
        if (pre && pre.mastery_score < 65) {
          blockerIds.add(pre.id);
        }
      }
    }

    const scoredCrucial = allTopics
      .map((t) => {
        const isBlocker = blockerIds.has(t.id);
        const isWeak = weakIds.has(t.id);
        const isDecaying = t.retention_score < 0.65;
        const score =
          (isBlocker ? 100 : 0) +
          (isWeak ? 60 : 0) +
          (isDecaying ? 25 : 0) +
          t.exam_weightage * 5 +
          (100 - t.mastery_score) * 0.2;
        return { topic: t, isCrucial: isBlocker || isWeak || isDecaying || t.exam_weightage >= 4.0, score };
      })
      .sort((a, b) => b.score - a.score);

    const maxCrucial = Math.min(14, allTopics.length);
    const picked = scoredCrucial.filter((x) => x.isCrucial).slice(0, maxCrucial);
    const crucialSet = new Set(
      (picked.length >= 4 ? picked : scoredCrucial.slice(0, Math.min(8, allTopics.length))).map(
        (x) => x.topic.id,
      ),
    );

    const topics = crucialOnly && allTopics.length > 8
      ? allTopics.filter((t) => crucialSet.has(t.id))
      : allTopics;
    const visibleIds = new Set(topics.map((t) => t.id));
    const prereqs = allPrereqs.filter(
      (e) => visibleIds.has(e.prerequisite_topic_id) && visibleIds.has(e.dependent_topic_id),
    );

    // Group cleanly into columns by topological level derived from visible prerequisite edges
    const depth: Record<string, number> = {};
    for (const t of topics) depth[t.id] = 0;
    for (let iter = 0; iter < topics.length; iter += 1) {
      let changed = false;
      for (const e of prereqs) {
        const cand = (depth[e.prerequisite_topic_id] ?? 0) + 1;
        if (cand > (depth[e.dependent_topic_id] ?? 0)) {
          depth[e.dependent_topic_id] = cand;
          changed = true;
        }
      }
      if (!changed) break;
    }

    const rowCounts: Record<number, number> = {};
    const builtNodes: Node[] = topics.map((t) => {
      const col = depth[t.id] ?? 0;
      const row = rowCounts[col] ?? 0;
      rowCounts[col] = row + 1;
      const tone = masteryTone(t.mastery_score, t.status);
      return {
        id: t.id,
        position: { x: col * 275 + 24, y: row * 112 + 24 },
        data: {
          label: `${t.topic_code}: ${t.title} (${Math.round(t.mastery_score)}%)`,
        },
        style: {
          width: 230,
          borderRadius: 12,
          border: `2px solid ${tone.border}`,
          background: tone.bg,
          color: "#0f172a",
          fontSize: 12,
          fontWeight: 600,
          padding: 10,
        },
      };
    });

    const builtEdges: Edge[] = prereqs.map((e) => {
      const isUncertain = e.confidence_status === "needs_review";
      return {
        id: e.id,
        source: e.prerequisite_topic_id,
        target: e.dependent_topic_id,
        animated: isUncertain,
        markerEnd: { type: MarkerType.ArrowClosed, color: isUncertain ? "#D97706" : "#4F46E5" },
        label: isUncertain ? "needs_review" : undefined,
        style: {
          stroke: isUncertain ? "#D97706" : "#4F46E5",
          strokeWidth: 2,
          strokeDasharray: isUncertain ? "5 4" : undefined,
        },
      };
    });

    return {
      nodes: builtNodes,
      edges: builtEdges,
      crucialCount: crucialSet.size,
      totalCount: allTopics.length,
    };
  }, [activeGraph, crucialOnly]);

  if (!activeSyllabus || !activeGraph) {
    return (
      <Card className="p-8 text-center">
        <p className="text-sm text-slate-600">Select or upload a syllabus to view its Knowledge Graph.</p>
        {isStudent && (
          <Button className="mt-3" onClick={() => setActiveTab("onboarding")}>
            Onboard Syllabus
          </Button>
        )}
      </Card>
    );
  }

  const topicMap = Object.fromEntries(activeGraph.topics.map((t) => [t.id, t]));
  const reviewEdges = activeGraph.prerequisites.filter((e) => e.confidence_status === "needs_review");

  async function handleEdgeAction(edge: TopicPrerequisiteOut, action: "confirm" | "remove") {
    if (!activeSyllabus) return;
    setBusy(true);
    setError(null);
    try {
      await api.patchPrerequisites(activeSyllabus.id, [
        {
          prerequisite_topic_id: edge.prerequisite_topic_id,
          dependent_topic_id: edge.dependent_topic_id,
          action,
        },
      ]);
      setSelectedEdge(null);
      await refreshWorkspace(activeSyllabus.id);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to update prerequisite link.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
            <GitFork className="h-5 w-5 text-indigo-600" />
            <span>Interactive Knowledge Graph (DAG)</span>
          </h1>
          <p className="text-sm text-slate-600">
            Color-coded by live mastery: <span className="font-semibold text-rose-700">Red &lt; 60%</span>,{" "}
            <span className="font-semibold text-amber-700">Amber 60-79%</span>,{" "}
            <span className="font-semibold text-emerald-700">Green &ge; 80%</span>. Dashed amber links need student verification.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <div className="inline-flex rounded-lg border border-slate-200 bg-white p-0.5 text-xs font-semibold">
            <button
              type="button"
              onClick={() => setCrucialOnly(true)}
              className={`rounded-md px-2.5 py-1 transition cursor-pointer ${
                crucialOnly ? "bg-indigo-600 text-white" : "text-slate-600 hover:bg-slate-100"
              }`}
            >
              Crucial Only ({crucialCount})
            </button>
            <button
              type="button"
              onClick={() => setCrucialOnly(false)}
              className={`rounded-md px-2.5 py-1 transition cursor-pointer ${
                !crucialOnly ? "bg-indigo-600 text-white" : "text-slate-600 hover:bg-slate-100"
              }`}
            >
              All Topics ({totalCount})
            </button>
          </div>
          <Badge tone={reviewEdges.length > 0 ? "amber" : "teal"}>
            {reviewEdges.length} Edge(s) Need Review
          </Badge>
        </div>
      </div>

      {error && <AlertBanner tone="rose" title="DAG Update Error" message={error} />}

      <div className="grid gap-5 lg:grid-cols-12">
        <Card className="lg:col-span-8 p-2 overflow-hidden">
          <div className="h-[520px] w-full rounded-lg bg-slate-50">
            <ReactFlow
              key={`${activeSyllabus.id}-${crucialOnly ? "crucial" : "all"}`}
              nodes={nodes}
              edges={edges}
              fitView
              fitViewOptions={{ padding: 0.2 }}
              minZoom={0.25}
              onNodeClick={(_, node) => {
                setSelectedEdge(null);
                setSelectedTopic(topicMap[node.id] || null);
              }}
              onEdgeClick={(_, edge) => {
                setSelectedTopic(null);
                const found = activeGraph.prerequisites.find((p) => p.id === edge.id) || null;
                setSelectedEdge(found);
              }}
            >
              <Background color="#cbd5e1" gap={18} />
              <Controls />
              <MiniMap
                style={{ width: 120, height: 78 }}
                nodeStrokeWidth={3}
                zoomable
                pannable
              />
            </ReactFlow>
          </div>
        </Card>

        <div className="lg:col-span-4 space-y-4">
          <Card className="space-y-3">
            <h2 className="text-sm font-bold text-slate-900">Node & Edge Inspector</h2>
            {selectedTopic ? (
              <div className="space-y-2.5 text-xs">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <Badge tone={masteryTone(selectedTopic.mastery_score, selectedTopic.status).badge}>
                    {selectedTopic.mastery_score.toFixed(1)}% Mastery
                  </Badge>
                  <ProvenanceBadge origin={selectedTopic.source_origin} />
                </div>
                <div className="text-sm font-bold text-slate-900">
                  {selectedTopic.topic_code}: {selectedTopic.title}
                </div>
                <div className="text-slate-600">
                  <strong>Unit:</strong> {selectedTopic.unit} &middot; <strong>Retention:</strong>{" "}
                  {(selectedTopic.retention_score * 100).toFixed(0)}%
                </div>
                {selectedTopic.subtopics.length > 0 && (
                  <div>
                    <strong>Subtopics:</strong> {selectedTopic.subtopics.join(", ")}
                  </div>
                )}
                <div className="rounded-lg bg-slate-50 p-2.5 text-slate-700 border border-slate-200 max-h-36 overflow-y-auto">
                  {selectedTopic.raw_excerpt || "No PDF excerpt saved."}
                </div>
                {isStudent && (
                  <Button
                    className="w-full text-xs"
                    onClick={() => {
                      setSelectedTutorTopicId(selectedTopic.id);
                      setActiveTab("tutor");
                    }}
                  >
                    Open in AI Study Tutor
                  </Button>
                )}
              </div>
            ) : selectedEdge ? (
              <div className="space-y-3 text-xs">
                <Badge tone={selectedEdge.confidence_status === "needs_review" ? "amber" : "indigo"}>
                  {selectedEdge.confidence_status}
                </Badge>
                <p className="text-slate-700">
                  <strong>Prerequisite:</strong>{" "}
                  {topicMap[selectedEdge.prerequisite_topic_id]?.title || selectedEdge.prerequisite_topic_id}
                  <br />
                  <strong>Unlocks:</strong>{" "}
                  {topicMap[selectedEdge.dependent_topic_id]?.title || selectedEdge.dependent_topic_id}
                </p>
                {isStudent && (
                  <div className="flex gap-2">
                    <Button
                      className="flex-1 text-xs"
                      disabled={busy}
                      onClick={() => void handleEdgeAction(selectedEdge, "confirm")}
                    >
                      <Check className="h-3.5 w-3.5" />
                      <span>Confirm Link</span>
                    </Button>
                    <Button
                      variant="danger"
                      className="flex-1 text-xs"
                      disabled={busy}
                      onClick={() => void handleEdgeAction(selectedEdge, "remove")}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                      <span>Remove</span>
                    </Button>
                  </div>
                )}
              </div>
            ) : (
              <p className="text-xs text-slate-500">
                Click any topic node to inspect mastery & PDF excerpts, or click any dashed edge to verify uncertain prerequisites.
              </p>
            )}
          </Card>

          {reviewEdges.length > 0 && isStudent && (
            <Card className="space-y-2.5 border-amber-200 bg-amber-50/40">
              <div className="text-xs font-bold text-amber-900">
                Edges Pending Review ({reviewEdges.length})
              </div>
              <div className="space-y-2 max-h-48 overflow-y-auto">
                {reviewEdges.map((e) => (
                  <div key={e.id} className="rounded-lg border border-amber-200 bg-white p-2 text-xs">
                    <div className="truncate font-medium text-slate-800">
                      {topicMap[e.prerequisite_topic_id]?.topic_code} &rarr;{" "}
                      {topicMap[e.dependent_topic_id]?.topic_code}
                    </div>
                    <div className="mt-1.5 flex gap-2">
                      <button
                        type="button"
                        disabled={busy}
                        onClick={() => void handleEdgeAction(e, "confirm")}
                        className="text-indigo-700 font-semibold hover:underline cursor-pointer"
                      >
                        Confirm
                      </button>
                      <button
                        type="button"
                        disabled={busy}
                        onClick={() => void handleEdgeAction(e, "remove")}
                        className="text-rose-700 font-semibold hover:underline cursor-pointer"
                      >
                        Remove
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
