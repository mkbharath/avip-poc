import { useState, useEffect, useRef } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Check, X, Loader2 } from "lucide-react";
import { simulateCapture, runInspection, getInspection } from "../../api/inspections";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

type CameraState = "waiting" | "capturing" | "passed" | "failed";

interface CameraView {
  angle: string;
  label: string;
  state: CameraState;
  imageUrl?: string;
  failReason?: string;
}

// Map part families to demo image folders
const FAMILY_TO_FOLDER: Record<string, string> = {
  "Machined Aluminum Plate": "metal_plate",
  "Precision Screw Assembly": "screw",
  "PCB Sub-Assembly": "pcb",
  "Welded Stainless Component": "weldment",
  "Anodized Housing": "metal_plate",
  "Cable Assembly": "cable",
};

export function CaptureScreen() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [cameras, setCameras] = useState<CameraView[]>([
    { angle: "top", label: "Top", state: "waiting" },
    { angle: "north", label: "North", state: "waiting" },
    { angle: "south", label: "South", state: "waiting" },
    { angle: "east", label: "East", state: "waiting" },
    { angle: "west", label: "West", state: "waiting" },
  ]);
  const [step, setStep] = useState<"capturing" | "inspecting" | "done">("capturing");
  const [captureProgress, setCaptureProgress] = useState(0);

  // Fetch inspection to get the part family (for image folder lookup)
  const { data: inspection } = useQuery({
    queryKey: ["inspection", id],
    queryFn: () => getInspection(id!),
    enabled: !!id,
  });

  // Determine the image folder from the part family
  const familyName = (inspection as unknown as Record<string, unknown>)?.family_name as string || "";
  const imageFolder = FAMILY_TO_FOLDER[familyName] || "metal_plate";
  const imageFolderRef = useRef(imageFolder);
  imageFolderRef.current = imageFolder;

  const captureStarted = useRef(false);

  const captureMutation = useMutation({
    mutationFn: () => simulateCapture(id!),
    onSuccess: (data) => {
      // Update camera views with actual image URLs from the backend
      const apiImages = data.images || [];
      setCameras((prev) =>
        prev.map((cam) => {
          const match = apiImages.find((img: { camera_angle: string; file_url: string }) => img.camera_angle === cam.angle);
          if (match) {
            return { ...cam, state: "passed" as CameraState, imageUrl: match.file_url };
          }
          return cam;
        })
      );
      setStep("inspecting");
      inspectMutation.mutate();
    },
  });

  const inspectMutation = useMutation({
    mutationFn: () => runInspection(id!),
    onSuccess: () => {
      setStep("done");
      setTimeout(() => {
        navigate(`/kiosk/result/${id}`);
      }, 500);
    },
  });

  // Simulate sequential camera capture animation
  useEffect(() => {
    if (step !== "capturing") return;
    if (captureStarted.current) return;
    captureStarted.current = true;

    const captureSequence = async () => {
      for (let i = 0; i < cameras.length; i++) {
        setCameras((prev) =>
          prev.map((cam, idx) => (idx === i ? { ...cam, state: "capturing" } : cam))
        );
        await delay(600);

        const folder = imageFolderRef.current;
        setCameras((prev) =>
          prev.map((cam, idx) =>
            idx === i
              ? { ...cam, state: "passed", imageUrl: `/static/demo-images/${folder}/clean/${cam.angle}.jpg?v=${Date.now()}` }
              : cam
          )
        );
        setCaptureProgress(((i + 1) / cameras.length) * 100);
        await delay(300);
      }

      await delay(300);
      captureMutation.mutate();
    };

    captureSequence();
  }, [step]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="flex h-[calc(100vh-3rem)]">
      {/* Left: Camera Grid (dark canvas) */}
      <div className="flex-1 bg-gray-900 p-6 flex flex-col">
        <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
          <svg className="w-5 h-5 text-avip-info" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
              d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z" />
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 13a3 3 0 11-6 0 3 3 0 016 0z" />
          </svg>
          Multi-Angle Capture
        </h2>

        {/* Camera grid */}
        <div className="grid grid-cols-3 grid-rows-2 gap-3 flex-1">
          {cameras.map((cam) => (
            <div
              key={cam.angle}
              className={`relative rounded-xl border-2 flex items-center justify-center overflow-hidden transition-all duration-300 ${
                cam.state === "waiting"
                  ? "border-gray-700 bg-gray-800"
                  : cam.state === "capturing"
                  ? "border-avip-info bg-gray-800 animate-pulse"
                  : cam.state === "passed"
                  ? "border-avip-pass bg-gray-800"
                  : "border-avip-fail bg-gray-800"
              }`}
            >
              {cam.imageUrl && cam.state === "passed" ? (
                <img
                  src={cam.imageUrl}
                  alt={`${cam.label} capture`}
                  className="absolute inset-0 w-full h-full object-cover"
                />
              ) : (
                <div className="absolute inset-0 bg-gradient-to-br from-gray-700 to-gray-900 opacity-50" />
              )}

              <span className="absolute top-2 left-3 text-xs font-medium text-gray-300 bg-gray-900/80 px-2 py-0.5 rounded z-10">
                {cam.label}
              </span>

              <div className="relative z-10">
                {cam.state === "waiting" && (
                  <div className="w-12 h-12 rounded-full border-2 border-gray-600 flex items-center justify-center">
                    <span className="text-gray-500 text-xs">IDLE</span>
                  </div>
                )}
                {cam.state === "capturing" && (
                  <div className="w-12 h-12 rounded-full border-2 border-avip-info flex items-center justify-center animate-pulse-slow">
                    <div className="w-4 h-4 bg-avip-info rounded-full" />
                  </div>
                )}
                {cam.state === "passed" && !cam.imageUrl && (
                  <div className="w-12 h-12 rounded-full bg-avip-pass flex items-center justify-center">
                    <Check className="w-6 h-6 text-white" />
                  </div>
                )}
                {cam.state === "passed" && cam.imageUrl && (
                  <div className="w-8 h-8 rounded-full bg-avip-pass/90 flex items-center justify-center shadow-lg">
                    <Check className="w-4 h-4 text-white" />
                  </div>
                )}
                {cam.state === "failed" && (
                  <div className="flex flex-col items-center">
                    <div className="w-12 h-12 rounded-full bg-avip-fail flex items-center justify-center">
                      <X className="w-6 h-6 text-white" />
                    </div>
                    {cam.failReason && (
                      <span className="mt-2 text-xs text-avip-fail bg-avip-fail/10 px-2 py-1 rounded">
                        {cam.failReason}
                      </span>
                    )}
                  </div>
                )}
              </div>

              {cam.state === "passed" && cam.imageUrl && (
                <div className="absolute bottom-2 right-2 flex items-center gap-1 bg-gray-900/80 px-2 py-0.5 rounded text-[10px] text-avip-pass z-10">
                  <Check className="w-3 h-3" />
                  Quality OK
                </div>
              )}
            </div>
          ))}

          <div className="rounded-xl border border-gray-800 bg-gray-900/50 flex items-center justify-center">
            <span className="text-gray-600 text-xs">Reserved</span>
          </div>
        </div>
      </div>

      {/* Right: Part Info & Progress */}
      <div className="w-80 bg-background border-l p-6 flex flex-col">
        <Card size="sm" className="mb-6">
          <CardHeader>
            <CardTitle className="text-xs text-muted-foreground uppercase tracking-wide">Part Identified</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-foreground font-mono font-bold text-lg">839-041322-001</p>
            <p className="text-muted-foreground text-sm">Rev C • Machined Aluminum Plate</p>
          </CardContent>
        </Card>

        {/* Progress stepper */}
        <div className="flex-1">
          <h3 className="text-sm font-medium text-muted-foreground mb-4">Inspection Progress</h3>
          <div className="space-y-4">
            <StepItem label="Identify" state="complete" />
            <StepItem
              label="Capture"
              state={step === "capturing" ? "active" : "complete"}
              detail={step === "capturing" ? `${Math.round(captureProgress)}%` : undefined}
            />
            <StepItem
              label="Inspect"
              state={step === "inspecting" ? "active" : step === "done" ? "complete" : "pending"}
              detail={step === "inspecting" ? "Running AI pipeline..." : undefined}
            />
            <StepItem
              label="Result"
              state={step === "done" ? "active" : "pending"}
            />
          </div>
        </div>

        {/* Capture status summary */}
        <div className="mt-auto pt-4 border-t">
          <div className="flex justify-between text-sm">
            <span className="text-muted-foreground">Cameras</span>
            <span className="text-foreground">
              {cameras.filter((c) => c.state === "passed").length}/{cameras.length}
            </span>
          </div>
          <div className="flex justify-between text-sm mt-1">
            <span className="text-muted-foreground">Quality</span>
            <span className="text-avip-pass font-medium">All passed</span>
          </div>
        </div>
      </div>
    </div>
  );
}

function StepItem({ label, state, detail }: { label: string; state: "pending" | "active" | "complete"; detail?: string }) {
  return (
    <div className="flex items-center gap-3">
      <div
        className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${
          state === "complete"
            ? "bg-avip-pass"
            : state === "active"
            ? "bg-lam-navy animate-pulse"
            : "bg-muted"
        }`}
      >
        {state === "complete" ? (
          <Check className="w-4 h-4 text-white" />
        ) : state === "active" ? (
          <Loader2 className="w-3.5 h-3.5 text-white animate-spin" />
        ) : (
          <div className="w-2.5 h-2.5 bg-muted-foreground/40 rounded-full" />
        )}
      </div>
      <div>
        <span className={`text-sm font-medium ${state === "pending" ? "text-muted-foreground" : "text-foreground"}`}>
          {label}
        </span>
        {detail && <p className="text-xs text-muted-foreground">{detail}</p>}
      </div>
    </div>
  );
}

function delay(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
