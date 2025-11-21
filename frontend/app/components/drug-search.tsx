import { useEffect, useMemo, useRef, useState } from "react";
import {
  Activity,
  ChevronDown,
  ChevronRight,
  Cpu,
  Database,
  Loader2,
  Pill,
  Search,
  Sparkles,
} from "lucide-react";

import { Input } from "~/components/ui/input";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "~/components/ui/card";
import { Badge } from "~/components/ui/badge";

const API_BASE_URL =
  import.meta.env.VITE_SEARCH_API_URL ??
  "https://9yb31qmdfa.execute-api.us-east-1.amazonaws.com";

const SAMPLE_QUERIES = [
  "insulin",
  "metformin",
  "ozempic",
  "type 2 diabetes",
  "cholesterol",
] as const;

type SearchMetrics = {
  total_latency_ms?: number;
  claude?: {
    latency_ms?: number;
    input_tokens?: number;
    output_tokens?: number;
    model?: string;
    cost_estimate?: number;
  };
  embedding?: {
    latency_ms?: number;
    model?: string;
    dimensions?: number;
  };
  redis?: {
    latency_ms?: number;
    results_count?: number;
  };
};

type ApiVariant = {
  ndc?: string;
  label?: string;
  dosage_form?: string;
  strength?: string;
  manufacturer?: string;
  is_generic?: boolean | string;
  similarity_score?: number;
  dea_schedule?: string;
};

type ManufacturerGroup = {
  manufacturer: string;
  variants: ApiVariant[];
};

type ApiGroupedResult = {
  group_id?: string;
  display_name?: string;
  brand_name?: string;
  generic_name?: string;
  is_generic?: boolean;
  gcn_seqno?: string;
  indication?: string;
  drug_class?: string;
  dosage_forms?: string[];
  match_type?: string;
  match_reason?: string;
  best_similarity?: number;
  variants?: ApiVariant[];
  manufacturer_groups?: ManufacturerGroup[];
};

type QueryInfo = {
  original?: string;
  expanded?: string;
  search_terms?: string[];
  filters?: {
    user?: Record<string, unknown>;
    claude?: Record<string, unknown>;
    merged?: Record<string, unknown>;
  };
  claude?: {
    corrections?: string[];
    confidence?: number;
    raw_output?: string;
  };
  message?: string;
  redis_query?: string;
};

type Variant = {
  ndc?: string;
  label?: string;
  dosageForm?: string;
  strength?: string;
  manufacturer?: string;
  isGeneric?: boolean;
  similarityScore?: number;
  deaSchedule?: string;
};

type ManufacturerGroupResult = {
  manufacturer: string;
  variants: Variant[];
};

type GroupedDrugResult = {
  groupId: string;
  title: string;
  brandName?: string;
  genericName?: string;
  isGeneric: boolean;
  gcn?: string;
  indication?: string;
  drugClass?: string;
  dosageForms: string[];
  matchType?: string;
  matchReason?: string;
  bestSimilarity?: number;
  variants: Variant[];
  manufacturerGroups?: ManufacturerGroupResult[];
};

type ApiResponse = {
  success?: boolean;
  results?: ApiGroupedResult[];
  raw_results?: ApiVariant[];
  metrics?: SearchMetrics;
  query_info?: QueryInfo;
  message?: string;
  error?: string;
};

export function DrugSearch() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<GroupedDrugResult[]>([]);
  const [metrics, setMetrics] = useState<SearchMetrics | null>(null);
  const [queryInfo, setQueryInfo] = useState<QueryInfo | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [noResultsMessage, setNoResultsMessage] = useState<string | null>(null);
  const [expandedGroupId, setExpandedGroupId] = useState<string | null>(null);
  const [expandedManufacturers, setExpandedManufacturers] = useState<Set<string>>(new Set());
  const [showRawJson, setShowRawJson] = useState(false);
  const abortController = useRef<AbortController | null>(null);

  const handleKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "Enter" && query.trim()) {
      runSearch(query.trim());
    }
  };

  const resetResults = () => {
    setResults([]);
    setMetrics(null);
    setQueryInfo(null);
    setLastUpdated(null);
    setError(null);
    setNoResultsMessage(null);
    setExpandedGroupId(null);
    setExpandedManufacturers(new Set());
  };

  const runSearch = async (term: string) => {
    abortController.current?.abort();
    const controller = new AbortController();
    abortController.current = controller;

    setIsLoading(true);
    setError(null);

    try {
      const response = await fetch(`${API_BASE_URL}/search`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          query: term,
          max_results: 20,
        }),
        signal: controller.signal,
      });

      const payload = (await response.json()) as ApiResponse;

      if (!response.ok || payload.success === false) {
        throw new Error(payload.error ?? "Search failed");
      }

      const normalized = (payload.results ?? []).map(mapResult);
      setResults(normalized);
      setMetrics(payload.metrics ?? null);
      setQueryInfo(payload.query_info ?? null);
      setNoResultsMessage(payload.message ?? payload.query_info?.message ?? null);
      setLastUpdated(new Date());
      setShowRawJson(false);
    } catch (err) {
      if ((err as Error).name === "AbortError") return;
      setError(err instanceof Error ? err.message : "An unexpected error occurred");
      setResults([]);
      setMetrics(null);
      setQueryInfo(null);
      setNoResultsMessage(null);
      setShowRawJson(false);
    } finally {
      setIsLoading(false);
    }
  };

  const mapResult = (group: ApiGroupedResult): GroupedDrugResult => {
    // Use brand_name first to keep titles uppercase (matches customer system)
    const title =
      group.brand_name ??
      group.display_name ??
      group.generic_name ??
      group.group_id ??
      "Medication";

    const normalizeBool = (value?: boolean | string): boolean => {
      if (typeof value === "boolean") return value;
      if (typeof value === "string") return value.toLowerCase() === "true";
      return false;
    };

    return {
      groupId: group.group_id ?? title,
      title,
      brandName: group.brand_name,
      genericName: group.generic_name,
      isGeneric: normalizeBool(group.is_generic),
      gcn: group.gcn_seqno,
      indication: group.indication,
      drugClass: group.drug_class,
      dosageForms: group.dosage_forms ?? [],
      matchType: group.match_type,
      matchReason: group.match_reason,
      bestSimilarity: group.best_similarity,
      variants: (group.variants ?? []).map((variant) => ({
        ndc: variant.ndc,
        label: variant.label ?? variant.ndc,
        dosageForm: variant.dosage_form,
        strength: variant.strength,
        manufacturer: variant.manufacturer,
        isGeneric: normalizeBool(variant.is_generic),
        similarityScore: variant.similarity_score,
        deaSchedule: variant.dea_schedule,
      })),
      manufacturerGroups: (group.manufacturer_groups ?? []).map((mfgGroup) => ({
        manufacturer: mfgGroup.manufacturer,
        variants: mfgGroup.variants.map((variant) => ({
          ndc: variant.ndc,
          label: variant.label ?? variant.ndc,
          dosageForm: variant.dosage_form,
          strength: variant.strength,
          manufacturer: variant.manufacturer,
          isGeneric: normalizeBool(variant.is_generic),
          similarityScore: variant.similarity_score,
          deaSchedule: variant.dea_schedule,
        })),
      })),
    };
  };

  const metricsSummary = useMemo(() => {
    if (!metrics) return null;
    return [
      {
        label: "LLM",
        icon: Sparkles,
        value: metrics.llm?.latency_ms
          ? `${metrics.llm.latency_ms.toFixed(0)} ms`
          : "—",
        hint: metrics.llm?.model ?? "N/A",
      },
      {
        label: "Embeddings",
        icon: Cpu,
        value: metrics.embedding?.latency_ms
          ? `${metrics.embedding.latency_ms.toFixed(0)} ms`
          : "—",
        hint: metrics.embedding?.model ?? "Titan",
      },
      {
        label: "Redis",
        icon: Database,
        value: metrics.redis?.latency_ms
          ? `${metrics.redis.latency_ms.toFixed(0)} ms`
          : "—",
        hint: metrics.redis?.results_count ? `${metrics.redis.results_count} hits` : undefined,
      },
      {
        label: "Total",
        icon: Activity,
        value: metrics.total_latency_ms ? `${metrics.total_latency_ms.toFixed(0)} ms` : "—",
        hint: "End-to-end",
      },
    ];
  }, [metrics]);

  const handleToggleGroup = (groupId: string) => {
    setExpandedGroupId((prev) => (prev === groupId ? null : groupId));
    // Reset manufacturer expansions when collapsing a group
    if (expandedGroupId === groupId) {
      setExpandedManufacturers(new Set());
    }
  };

  const handleToggleManufacturer = (mfgKey: string) => {
    setExpandedManufacturers((prev) => {
      const newSet = new Set(prev);
      if (newSet.has(mfgKey)) {
        newSet.delete(mfgKey);
      } else {
        newSet.add(mfgKey);
      }
      return newSet;
    });
  };

  const formatPercent = (value?: number) => {
    if (typeof value !== "number") return "—";
    return `${value.toFixed(2)}%`;
  };

  const formatRawJson = (jsonText: string) => {
    try {
      return JSON.stringify(JSON.parse(jsonText), null, 2);
    } catch {
      return jsonText;
    }
  };

  return (
    <div className="space-y-8">
      <div className="space-y-3">
      <div className="relative">
        <Search className="text-muted-foreground absolute left-4 top-1/2 -translate-y-1/2 h-5 w-5" />
        <Input
          type="text"
          placeholder="Search medications... (Press Enter)"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          onKeyDown={handleKeyDown}
          className="h-14 bg-card pl-12 pr-4 text-base shadow-sm focus-visible:ring-medical"
          autoComplete="off"
        />
        {isLoading && (
          <Loader2 className="text-muted-foreground absolute right-4 top-1/2 -translate-y-1/2 h-5 w-5 animate-spin" />
        )}
      </div>
        <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
          <span>Try:</span>
          {SAMPLE_QUERIES.map((sample) => (
            <button
              key={sample}
              type="button"
              onClick={() => setQuery(sample)}
              className="rounded-full border border-border px-3 py-1 text-xs font-medium text-foreground transition hover:border-medical/70 hover:text-medical"
            >
              {sample}
            </button>
          ))}
        </div>
      </div>

      {metricsSummary && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-lg">Pipeline performance</CardTitle>
            <CardDescription>
              Latency telemetry returned by the live `/search` invocation.
            </CardDescription>
          </CardHeader>
          <CardContent className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
            {metricsSummary.map(({ label, icon: Icon, value, hint }) => (
              <div key={label} className="rounded-lg border border-border/60 bg-muted/30 p-4 text-left">
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <Icon className="h-4 w-4 text-medical" />
                  {label}
                </div>
                <p className="mt-2 text-2xl font-semibold text-foreground">{value}</p>
                {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {queryInfo && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">Query interpretation</CardTitle>
            <CardDescription>
              LLM → Titan → Redis parameters driving this search.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4 text-sm text-muted-foreground">
            <div className="flex items-center justify-between">
              <div className="text-xs uppercase tracking-wide text-muted-foreground/80">
                LLM output
              </div>
              <button
                type="button"
                onClick={() => setShowRawJson((prev) => !prev)}
                className="text-xs font-semibold text-medical hover:text-medical/80"
              >
                {showRawJson ? "Hide raw JSON" : "Show raw JSON"}
              </button>
            </div>
            {showRawJson && queryInfo.claude?.raw_output && (
              <pre className="max-h-60 overflow-auto rounded-md border border-border/60 bg-muted/40 p-3 text-left text-xs leading-relaxed text-muted-foreground">
                {formatRawJson(queryInfo.claude.raw_output)}
              </pre>
            )}
            {queryInfo.expanded && (
              <div>
                <p className="mb-2 font-medium text-foreground">Embedding text</p>
                <pre className="max-h-40 overflow-auto rounded-md bg-muted/60 p-3 text-left text-xs leading-relaxed text-muted-foreground">
                  {queryInfo.expanded}
                </pre>
              </div>
            )}

            {queryInfo.search_terms && queryInfo.search_terms.length > 0 && (
              <div className="space-y-2">
                <p className="font-medium text-foreground">Lexical terms</p>
                <div className="flex flex-wrap gap-2">
                  {queryInfo.search_terms.map((term) => (
                    <Badge key={term} variant="secondary" className="text-xs">
                      {term}
                    </Badge>
                  ))}
                </div>
              </div>
            )}

            {queryInfo.filters?.merged && Object.keys(queryInfo.filters.merged).length > 0 && (
              <div className="space-y-1">
                <p className="font-medium text-foreground">Applied filters</p>
                <div className="grid gap-1 text-xs">
                  {Object.entries(queryInfo.filters.merged).map(([key, value]) => (
                    <div key={key} className="flex justify-between rounded border border-border/60 bg-muted/30 px-3 py-2">
                      <span className="uppercase tracking-wide text-muted-foreground">{key}</span>
                      <span className="text-foreground">
                        {Array.isArray(value) ? value.join(", ") : String(value)}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {queryInfo.claude?.corrections && queryInfo.claude.corrections.length > 0 && (
              <div className="space-y-1">
                <p className="font-medium text-foreground">Corrections</p>
                <ul className="list-disc pl-5 text-xs">
                  {queryInfo.claude.corrections.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </div>
            )}

            {queryInfo.message && (
              <p className="text-xs text-muted-foreground/90">{queryInfo.message}</p>
            )}
          </CardContent>
        </Card>
      )}

      {error && (
        <Card className="border-destructive/50 bg-destructive/5">
          <CardContent className="pt-6 text-sm text-destructive">{error}</CardContent>
        </Card>
      )}

      {query && !isLoading && results.length === 0 && !error && (
        <Card className="border-dashed">
          <CardContent className="py-10 text-center">
            <Pill className="mx-auto mb-4 h-12 w-12 text-muted-foreground" />
            <p className="text-muted-foreground">
              {noResultsMessage ?? `No matches for “${query}”. Try a generic name, indication, or NDC.`}
            </p>
          </CardContent>
        </Card>
      )}

      {results.length > 0 && (
        <div className="space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-3 text-sm text-muted-foreground">
            <p>
              Showing {results.length} result{results.length === 1 ? "" : "s"}
              {queryInfo?.original && ` for “${queryInfo.original}”`}
            </p>
            {lastUpdated && (
              <span>Updated {lastUpdated.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</span>
            )}
          </div>

          <div className="space-y-4">
            {results.map((group) => {
              const isExpanded = expandedGroupId === group.groupId;
              const matchLabel =
                group.matchType === "exact"
                  ? "Vector Search"
                  : group.matchType === "pharmacologic"
                  ? "Pharmacological Match"
                  : group.matchType === "therapeutic_alternative"
                  ? "Therapeutic Alternative"
                  : "Related";

              return (
                <Card
                  key={group.groupId}
                  className="transition-all hover:border-medical/50 hover:shadow-md"
                >
                <CardHeader className="pb-3">
                  <div className="flex flex-wrap items-start justify-between gap-4">
                    <div className="flex-1 space-y-1">
                        <CardTitle className="text-xl text-balance">{group.title}</CardTitle>
                        {group.genericName && (
                          <CardDescription className="text-sm">
                            Generic: <span className="text-foreground">{group.genericName}</span>
                          </CardDescription>
                        )}
                        <div className="text-xs text-muted-foreground">
                          {group.indication && <span>Indication: {group.indication} · </span>}
                          {group.drugClass && <span>Class: {group.drugClass}</span>}
                        </div>
                    </div>
                    <div className="flex flex-wrap gap-2">
                        <Badge 
                          variant={group.matchType === "exact" ? "default" : "secondary"}
                          className={
                            group.matchType === "therapeutic_alternative"
                              ? "bg-cyan-500 hover:bg-cyan-600 text-primary-foreground"
                              : group.matchType === "pharmacologic"
                              ? "bg-medical hover:bg-medical/90 text-primary-foreground"
                              : ""
                          }
                        >
                          {matchLabel}
                        </Badge>
                        <Badge 
                          variant="outline" 
                          className={`capitalize ${group.isGeneric ? "" : "bg-pink-500 border-pink-500 text-primary-foreground hover:bg-pink-600"}`}
                        >
                          {group.isGeneric ? "Generic" : "Brand"}
                        </Badge>
                        {typeof group.bestSimilarity === "number" && (
                          <Badge variant="outline">Match {formatPercent(group.bestSimilarity)}</Badge>
                        )}
                    </div>
                  </div>
                </CardHeader>
                <CardContent className="space-y-3 text-sm text-muted-foreground">
                    {group.gcn && (
                      <div className="flex flex-wrap gap-3 text-xs font-medium uppercase tracking-wide text-muted-foreground/80">
                        <span>
                          GCN: <span className="text-foreground">{group.gcn}</span>
                        </span>
                      </div>
                    )}

                    <button
                      type="button"
                      onClick={() => handleToggleGroup(group.groupId)}
                      className="mt-2 inline-flex items-center gap-2 rounded-md border border-border/60 px-4 py-2 text-xs font-semibold text-foreground transition hover:border-medical/60 hover:text-medical"
                    >
                      {isExpanded ? "Hide formats" : "View formats"} ({group.variants.length})
                    </button>

                    {isExpanded && (
                      <div className="space-y-3 pt-2">
                        {group.manufacturerGroups && group.manufacturerGroups.length > 0 ? (
                          // Display grouped by manufacturer
                          group.manufacturerGroups.map((mfgGroup) => {
                            const mfgKey = `${group.groupId}:${mfgGroup.manufacturer}`;
                            const isMfgExpanded = expandedManufacturers.has(mfgKey);
                            return (
                            <div key={mfgGroup.manufacturer} className="space-y-2">
                              <button
                                type="button"
                                onClick={() => handleToggleManufacturer(mfgKey)}
                                className="flex w-full items-center gap-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground/90 hover:text-foreground transition-colors"
                              >
                                {isMfgExpanded ? (
                                  <ChevronDown className="h-3 w-3" />
                                ) : (
                                  <ChevronRight className="h-3 w-3" />
                                )}
                                <span>{mfgGroup.manufacturer}</span>
                                <span className="text-xs font-normal text-muted-foreground/70">
                                  ({mfgGroup.variants.length})
                                </span>
                              </button>
                              {isMfgExpanded && (
                              <div className="space-y-2 pl-5">
                                {mfgGroup.variants.map((variant) => (
                                  <div
                                    key={variant.ndc ?? variant.label}
                                    className="flex flex-wrap items-center justify-between gap-3 rounded border border-border/60 bg-muted/30 p-3 text-xs"
                                  >
                                    <div className="space-y-1">
                                      <p className="font-semibold text-foreground">
                                        {variant.label ?? variant.ndc}
                                      </p>
                                      <div className="flex flex-wrap gap-3 text-muted-foreground/80">
                                        {variant.ndc && (
                                          <span>
                                            NDC: <span className="text-foreground">{variant.ndc}</span>
                                          </span>
                                        )}
                                        {variant.strength && (
                                          <span>
                                            Strength: <span className="text-foreground">{variant.strength}</span>
                                          </span>
                                        )}
                                        {variant.dosageForm && (
                                          <span>
                                            Form: <span className="text-foreground">{variant.dosageForm}</span>
                                          </span>
                                        )}
                                        {typeof variant.similarityScore === "number" && (
                                          <span>
                                            Match{" "}
                                            <span className="text-foreground">
                                              {formatPercent(variant.similarityScore)}
                                            </span>
                                          </span>
                                        )}
                                        {variant.deaSchedule && (
                                          <span>DEA {variant.deaSchedule}</span>
                                        )}
                                      </div>
                                    </div>
                                    <button
                                      type="button"
                                      className="rounded-md bg-cyan-500 px-4 py-2 text-xs font-semibold text-white shadow hover:bg-cyan-600"
                                    >
                                      Select
                                    </button>
                                  </div>
                                ))}
                              </div>
                              )}
                            </div>
                            );
                          })
                        ) : (
                          // Fallback: flat variants list if no manufacturer groups
                          group.variants.map((variant) => (
                            <div
                              key={variant.ndc ?? variant.label}
                              className="flex flex-wrap items-center justify-between gap-3 rounded border border-border/60 bg-muted/30 p-3 text-xs"
                            >
                              <div className="space-y-1">
                                <p className="font-semibold text-foreground">
                                  {variant.label ?? variant.ndc}
                                </p>
                                <div className="flex flex-wrap gap-3 text-muted-foreground/80">
                                  {variant.ndc && (
                                    <span>
                                      NDC: <span className="text-foreground">{variant.ndc}</span>
                                    </span>
                                  )}
                                  {variant.strength && (
                                    <span>
                                      Strength: <span className="text-foreground">{variant.strength}</span>
                                    </span>
                                  )}
                                  {variant.dosageForm && (
                                    <span>
                                      Form: <span className="text-foreground">{variant.dosageForm}</span>
                                    </span>
                                  )}
                                  {variant.manufacturer && (
                                    <span>
                                      Mfr: <span className="text-foreground">{variant.manufacturer}</span>
                                    </span>
                                  )}
                                  {typeof variant.similarityScore === "number" && (
                                    <span>
                                      Match{" "}
                                      <span className="text-foreground">
                                        {formatPercent(variant.similarityScore)}
                                      </span>
                                    </span>
                                  )}
                                  {variant.deaSchedule && (
                                    <span>DEA {variant.deaSchedule}</span>
                                  )}
                                </div>
                              </div>
                              <button
                                type="button"
                                className="rounded-md bg-cyan-500 px-4 py-2 text-xs font-semibold text-white shadow hover:bg-cyan-600"
                              >
                                Select
                              </button>
                            </div>
                          ))
                        )}
                      </div>
                    )}
                  </CardContent>
                </Card>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
