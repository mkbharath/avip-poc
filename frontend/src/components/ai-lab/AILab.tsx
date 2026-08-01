import { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import {
  FlaskConical,
  Zap,
  ImageIcon,
  CheckCircle2,
  XCircle,
  Loader2,
  Upload,
  Eye,
  Brain,
} from "lucide-react";
import { api } from "../../api/client";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";

interface VisionLLMStatus {
  enabled: boolean;
  ready: boolean;
  model: string;
  reference_images_loaded: number;
  api_key_configured: boolean;
}

interface Classification {
  defect_class: string;
  confidence: number;
  severity: string;
  description: string;
  bbox: { x: number; y: number; width: number; height: number } | null;
}

interface ClassifyResult {
  scenario_id?: string;
  filename?: string;
  classification: Classification;
  error?: string | null;
  raw_response?: string | null;
}

interface AllScenariosResult {
  results: {
    scenario_id: string;
    defect_class: string;
    confidence: number;
    severity?: string;
    description?: string;
    error?: string;
  }[];
  total: number;
}

const SCENARIO_NAMES: Record<string, string> = {
  "scenario-01": "Clean Machined Plate",
  "scenario-02": "Scratched Plate",
  "scenario-03": "Dented Housing",
  "scenario-04": "Missing Fastener",
  "scenario-05": "Contamination",
  "scenario-06": "Borderline Anomaly",
  "scenario-07": "Wrong Label",
  "scenario-08": "Missing Label",
  "scenario-09": "Multi-Defect",
  "scenario-10": "Clean Housing",
  "scenario-11": "Cracked Connector",
  "scenario-12": "Chipped Edge",
  "scenario-13": "Material Porosity",
  "scenario-14": "Tool Marks",
  "scenario-15": "Coating Stain",
  "scenario-16": "Label Mismatch",
  "scenario-17": "Machining Burr",
  "scenario-18": "Paint Peel-Off",
};

export function AILab() {
  const [selectedScenario, setSelectedScenario] = useState<string>("scenario-13");
  const [classifyResult, setClassifyResult] = useState<ClassifyResult | null>(null);
  const [allResults, setAllResults] = useState<AllScenariosResult | null>(null);
  const [uploadResult, setUploadResult] = useState<ClassifyResult | null>(null);

  // Status query
  const { data: status, isLoading: statusLoading } = useQuery<VisionLLMStatus>({
    queryKey: ["vision-llm", "status"],
    queryFn: () => api.get("/ai/vision-llm/status"),
    refetchInterval: 10000,
  });

  // Classify single scenario
  const classifyMutation = useMutation({
    mutationFn: (scenarioId: string) =>
      api.post<ClassifyResult>(`/ai/vision-llm/classify/scenario/${scenarioId}`),
    onSuccess: (data) => setClassifyResult(data),
  });

  // Classify all scenarios
  const classifyAllMutation = useMutation({
    mutationFn: () => api.post<AllScenariosResult>("/ai/vision-llm/classify/all-scenarios"),
    onSuccess: (data) => setAllResults(data),
  });

  // Upload file classify
  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await fetch("/api/v1/ai/vision-llm/classify/upload", {
        method: "POST",
        body: formData,
      });
      const data: ClassifyResult = await res.json();
      setUploadResult(data);
    } catch (err) {
      console.error("Upload classify failed:", err);
    }
  };

  const isReady = status?.enabled && status?.ready;

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-foreground tracking-tight flex items-center gap-2">
            <FlaskConical className="w-5 h-5 text-purple-600" />
            AI Lab — Vision LLM
          </h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            Test GPT-4 Vision few-shot defect classification on inspection images
          </p>
        </div>
      </div>

      {/* Status Card */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base flex items-center gap-2">
            <Brain className="w-4 h-4" />
            Service Status
          </CardTitle>
        </CardHeader>
        <CardContent>
          {statusLoading ? (
            <div className="flex items-center gap-2 text-muted-foreground">
              <Loader2 className="w-4 h-4 animate-spin" />
              Checking status...
            </div>
          ) : (
            <div className="flex flex-wrap items-center gap-4">
              <StatusPill
                ok={status?.enabled ?? false}
                label="Feature Toggle"
                detail={status?.enabled ? "AVIP_VISION_LLM=true" : "Disabled"}
              />
              <StatusPill
                ok={status?.api_key_configured ?? false}
                label="API Key"
                detail={status?.api_key_configured ? "Configured" : "Missing OPENAI_API_KEY"}
              />
              <StatusPill
                ok={(status?.reference_images_loaded ?? 0) > 0}
                label="Reference Images"
                detail={`${status?.reference_images_loaded ?? 0} loaded`}
              />
              <StatusPill
                ok={status?.ready ?? false}
                label="Ready"
                detail={status?.ready ? status.model : "Not ready"}
              />
            </div>
          )}
          {!isReady && !statusLoading && (
            <div className="mt-3 p-3 rounded-lg bg-amber-50 border border-amber-200 text-sm text-amber-800">
              <strong>Setup required:</strong> Set environment variables{" "}
              <code className="bg-amber-100 px-1 rounded">AVIP_VISION_LLM=true</code> and{" "}
              <code className="bg-amber-100 px-1 rounded">OPENAI_API_KEY=sk-...</code> then restart the backend.
            </div>
          )}
        </CardContent>
      </Card>

      {/* Main Content — Two columns */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Left: Scenario Classification */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <Eye className="w-4 h-4" />
              Classify Scenario
            </CardTitle>
            <CardDescription>
              Pick a demo scenario and run GPT-4 Vision classification
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Scenario Picker */}
            <div className="space-y-2">
              <label className="text-sm font-medium text-foreground">Select Scenario</label>
              <select
                value={selectedScenario}
                onChange={(e) => setSelectedScenario(e.target.value)}
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              >
                {Object.entries(SCENARIO_NAMES).map(([id, name]) => (
                  <option key={id} value={id}>
                    {id.replace("scenario-", "#")} — {name}
                  </option>
                ))}
              </select>
            </div>

            {/* Image Preview with Bounding Box Overlay */}
            <div className="rounded-lg border bg-muted/30 overflow-hidden relative">
              <div className="relative">
                <img
                  src={`/static/demo-images/scenarios/${selectedScenario}/top.jpg?v=2`}
                  alt={SCENARIO_NAMES[selectedScenario]}
                  className="w-full h-64 object-contain bg-black/5"
                />
                {/* Bounding Box Overlay */}
                {classifyResult?.classification?.bbox && classifyResult.classification.defect_class !== "no_defect" && (
                  <BoundingBoxOverlay
                    bbox={classifyResult.classification.bbox}
                    label={classifyResult.classification.defect_class}
                    confidence={classifyResult.classification.confidence}
                  />
                )}
              </div>
            </div>

            {/* Classify Button */}
            <Button
              onClick={() => classifyMutation.mutate(selectedScenario)}
              disabled={!isReady || classifyMutation.isPending}
              className="w-full"
            >
              {classifyMutation.isPending ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  Analyzing with GPT-4 Vision...
                </>
              ) : (
                <>
                  <Zap className="w-4 h-4 mr-2" />
                  Classify with Vision LLM
                </>
              )}
            </Button>

            {/* Result */}
            {classifyResult && (
              <>
                <ClassificationResultCard result={classifyResult.classification} />
                {classifyResult.error && (
                  <div className="p-3 rounded-lg bg-red-50 border border-red-200 text-sm text-red-700">
                    <strong>Error:</strong> {classifyResult.error}
                  </div>
                )}
              </>
            )}
          </CardContent>
        </Card>

        {/* Right: Upload + Batch */}
        <div className="space-y-6">
          {/* Upload */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-2">
                <Upload className="w-4 h-4" />
                Upload Image
              </CardTitle>
              <CardDescription>
                Upload any image for Vision LLM classification
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <label className="flex flex-col items-center justify-center w-full h-32 border-2 border-dashed rounded-lg cursor-pointer hover:bg-muted/50 transition-colors">
                <div className="flex flex-col items-center justify-center pt-5 pb-6">
                  <ImageIcon className="w-8 h-8 text-muted-foreground mb-2" />
                  <p className="text-sm text-muted-foreground">
                    Click to upload an inspection image
                  </p>
                </div>
                <input
                  type="file"
                  className="hidden"
                  accept="image/*"
                  onChange={handleFileUpload}
                  disabled={!isReady}
                />
              </label>

              {uploadResult && (
                <ClassificationResultCard result={uploadResult.classification} />
              )}
            </CardContent>
          </Card>

          {/* Batch — All Scenarios */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-2">
                <FlaskConical className="w-4 h-4" />
                Batch Classification
              </CardTitle>
              <CardDescription>
                Run Vision LLM on all 18 scenarios to evaluate accuracy
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <Button
                onClick={() => classifyAllMutation.mutate()}
                disabled={!isReady || classifyAllMutation.isPending}
                variant="outline"
                className="w-full"
              >
                {classifyAllMutation.isPending ? (
                  <>
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    Classifying all scenarios...
                  </>
                ) : (
                  <>
                    <Zap className="w-4 h-4 mr-2" />
                    Classify All 18 Scenarios
                  </>
                )}
              </Button>

              {allResults && (
                <div className="space-y-2 max-h-72 overflow-y-auto">
                  {allResults.results.map((r) => (
                    <div
                      key={r.scenario_id}
                      className="flex items-center justify-between p-2 rounded-md bg-muted/30 text-sm"
                    >
                      <span className="font-medium text-foreground truncate max-w-[140px]">
                        {SCENARIO_NAMES[r.scenario_id] || r.scenario_id}
                      </span>
                      <div className="flex items-center gap-2">
                        <Badge
                          variant={r.defect_class === "no_defect" ? "secondary" : "destructive"}
                          className="text-xs"
                        >
                          {r.defect_class}
                        </Badge>
                        <span className="text-xs text-muted-foreground w-10 text-right">
                          {(r.confidence * 100).toFixed(0)}%
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}

function StatusPill({ ok, label, detail }: { ok: boolean; label: string; detail: string }) {
  return (
    <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-muted/50 border">
      {ok ? (
        <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />
      ) : (
        <XCircle className="w-3.5 h-3.5 text-red-400" />
      )}
      <span className="text-xs font-medium text-foreground">{label}</span>
      <span className="text-xs text-muted-foreground">{detail}</span>
    </div>
  );
}

function ClassificationResultCard({ result }: { result: Classification }) {
  const isDefect = result.defect_class !== "no_defect";

  return (
    <div
      className={`rounded-lg border p-4 space-y-2 ${
        isDefect
          ? "bg-red-50/50 border-red-200"
          : "bg-emerald-50/50 border-emerald-200"
      }`}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          {isDefect ? (
            <XCircle className="w-4 h-4 text-red-500" />
          ) : (
            <CheckCircle2 className="w-4 h-4 text-emerald-500" />
          )}
          <span className="font-semibold text-sm">
            {result.defect_class.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant={isDefect ? "destructive" : "secondary"} className="text-xs">
            {result.severity}
          </Badge>
          <span className="text-sm font-mono font-medium">
            {(result.confidence * 100).toFixed(0)}%
          </span>
        </div>
      </div>
      <p className="text-sm text-muted-foreground">{result.description}</p>
      {result.bbox && (
        <p className="text-xs text-muted-foreground font-mono">
          bbox: ({result.bbox.x.toFixed(0)}, {result.bbox.y.toFixed(0)},{" "}
          {result.bbox.width.toFixed(0)}x{result.bbox.height.toFixed(0)})
        </p>
      )}
    </div>
  );
}

function BoundingBoxOverlay({
  bbox,
  label,
  confidence,
}: {
  bbox: { x: number; y: number; width: number; height: number };
  label: string;
  confidence: number;
}) {
  // bbox is in 640x480 pixel space, convert to percentage
  const left = (bbox.x / 640) * 100;
  const top = (bbox.y / 480) * 100;
  const width = (bbox.width / 640) * 100;
  const height = (bbox.height / 480) * 100;

  return (
    <div className="absolute inset-0 pointer-events-none">
      {/* Bounding box */}
      <div
        className="absolute border-2 border-red-500 rounded-sm"
        style={{
          left: `${left}%`,
          top: `${top}%`,
          width: `${width}%`,
          height: `${height}%`,
        }}
      >
        {/* Label tag above the box */}
        <div className="absolute -top-6 left-0 flex items-center gap-1 bg-red-500 text-white text-[10px] font-bold px-1.5 py-0.5 rounded-sm whitespace-nowrap">
          {label.replace(/_/g, " ")} {(confidence * 100).toFixed(0)}%
        </div>
        {/* Corner markers */}
        <div className="absolute -top-0.5 -left-0.5 w-2.5 h-2.5 border-t-2 border-l-2 border-red-500" />
        <div className="absolute -top-0.5 -right-0.5 w-2.5 h-2.5 border-t-2 border-r-2 border-red-500" />
        <div className="absolute -bottom-0.5 -left-0.5 w-2.5 h-2.5 border-b-2 border-l-2 border-red-500" />
        <div className="absolute -bottom-0.5 -right-0.5 w-2.5 h-2.5 border-b-2 border-r-2 border-red-500" />
      </div>
    </div>
  );
}
