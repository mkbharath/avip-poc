import { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";

interface OcrLabel {
  filename: string;
  part_number: string | null;
  image_url: string;
  scenario_type: "success" | "error_unreadable" | "error_not_found";
}

interface OcrResult {
  method: string;
  extracted_part_number: string;
  confidence: number;
  extracted_text: string;
  part: {
    id: string;
    part_number: string;
    revision: string;
    description: string;
    material: string;
    supplier: string;
  };
}

interface OcrCaptureModalProps {
  isOpen: boolean;
  onClose: () => void;
  onPartIdentified: (partNumber: string) => void;
}

async function fetchOcrLabels(): Promise<{ data: OcrLabel[] }> {
  const res = await fetch("/api/v1/parts/ocr/labels");
  if (!res.ok) throw new Error("Failed to fetch labels");
  return res.json();
}

async function identifyByOcr(filename: string): Promise<OcrResult> {
  const res = await fetch(`/api/v1/parts/ocr/identify?filename=${encodeURIComponent(filename)}`, {
    method: "POST",
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "OCR failed" }));
    const detail = err.detail;
    const error = new Error(typeof detail === "string" ? detail : detail?.message || "OCR failed") as Error & { info?: Record<string, unknown> };
    if (typeof detail === "object") {
      error.info = detail;
    }
    throw error;
  }
  return res.json();
}

export function OcrCaptureModal({ isOpen, onClose, onPartIdentified }: OcrCaptureModalProps) {
  const [selectedLabel, setSelectedLabel] = useState<OcrLabel | null>(null);
  const [phase, setPhase] = useState<"select" | "scanning" | "result" | "error">("select");
  const [result, setResult] = useState<OcrResult | null>(null);
  const [errorInfo, setErrorInfo] = useState<{ message: string; suggestion: string; extractedText?: string } | null>(null);

  const { data: labelsData } = useQuery({
    queryKey: ["ocr-labels"],
    queryFn: fetchOcrLabels,
    enabled: isOpen,
  });

  const ocrMutation = useMutation({
    mutationFn: (filename: string) => identifyByOcr(filename),
    onSuccess: (data) => {
      setResult(data);
      setPhase("result");
      setErrorInfo(null);
    },
    onError: (err: Error & { info?: { message?: string; suggestion?: string; extracted_text?: string } }) => {
      setErrorInfo({
        message: err.info?.message || err.message || "OCR extraction failed",
        suggestion: err.info?.suggestion || "Try a different label or use manual entry",
        extractedText: err.info?.extracted_text,
      });
      setPhase("error");
    },
  });

  const handleCapture = () => {
    if (!selectedLabel) return;
    setPhase("scanning");
    // Simulate a brief processing delay for realism
    setTimeout(() => {
      ocrMutation.mutate(selectedLabel.filename);
    }, 1500);
  };

  const handleAccept = () => {
    if (result) {
      onPartIdentified(result.extracted_part_number);
      handleReset();
    }
  };

  const handleReset = () => {
    setSelectedLabel(null);
    setPhase("select");
    setResult(null);
    setErrorInfo(null);
  };

  const handleClose = () => {
    handleReset();
    onClose();
  };

  if (!isOpen) return null;

  const labels = labelsData?.data || [];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm">
      <div className="bg-gray-800 rounded-2xl w-full max-w-2xl mx-4 border border-gray-600 shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-700">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-avip-info/20 flex items-center justify-center">
              <svg className="w-5 h-5 text-avip-info" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z" />
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 13a3 3 0 11-6 0 3 3 0 016 0z" />
              </svg>
            </div>
            <div>
              <h2 className="text-lg font-bold text-white">OCR Label Capture</h2>
              <p className="text-xs text-gray-400">Position label under camera and capture</p>
            </div>
          </div>
          <button
            onClick={handleClose}
            className="p-2 text-gray-400 hover:text-white hover:bg-gray-700 rounded-lg transition-colors"
            aria-label="Close"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Body */}
        <div className="p-6">
          {/* Phase: Select label (simulated camera view) */}
          {phase === "select" && (
            <div>
              <div className="mb-4">
                <div className="relative bg-gray-900 rounded-xl border-2 border-dashed border-gray-600 aspect-video flex items-center justify-center overflow-hidden">
                  {selectedLabel ? (
                    <div className="relative w-full h-full">
                      <img
                        src={selectedLabel.image_url}
                        alt={`Label for ${selectedLabel.part_number}`}
                        className="w-full h-full object-contain p-4"
                      />
                      {/* Camera overlay corners */}
                      <div className="absolute top-3 left-3 w-6 h-6 border-t-2 border-l-2 border-avip-info" />
                      <div className="absolute top-3 right-3 w-6 h-6 border-t-2 border-r-2 border-avip-info" />
                      <div className="absolute bottom-3 left-3 w-6 h-6 border-b-2 border-l-2 border-avip-info" />
                      <div className="absolute bottom-3 right-3 w-6 h-6 border-b-2 border-r-2 border-avip-info" />
                      <div className="absolute top-3 right-3 flex items-center gap-1.5 bg-red-600/90 px-2 py-0.5 rounded text-xs text-white">
                        <span className="w-2 h-2 rounded-full bg-white animate-pulse" />
                        LIVE
                      </div>
                    </div>
                  ) : (
                    <div className="text-center text-gray-500">
                      <svg className="w-12 h-12 mx-auto mb-2 opacity-40" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                          d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z" />
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 13a3 3 0 11-6 0 3 3 0 016 0z" />
                      </svg>
                      <p className="text-sm">Select a label below to position in camera view</p>
                    </div>
                  )}
                </div>
              </div>

              {/* Label selection (simulates rotating parts under camera) */}
              <p className="text-xs text-gray-400 mb-2 font-medium uppercase tracking-wide">Available Labels</p>
              <div className="grid grid-cols-5 gap-2 mb-5">
                {labels.map((label) => (
                  <button
                    key={label.filename}
                    onClick={() => setSelectedLabel(label)}
                    className={`p-2 rounded-lg border text-center transition-all relative ${
                      selectedLabel?.filename === label.filename
                        ? "border-avip-info bg-avip-info/10 ring-1 ring-avip-info"
                        : "border-gray-600 bg-gray-700/50 hover:border-gray-500"
                    }`}
                  >
                    {label.scenario_type !== "success" && (
                      <span className={`absolute -top-1 -right-1 w-4 h-4 rounded-full flex items-center justify-center text-[8px] font-bold ${
                        label.scenario_type === "error_unreadable" ? "bg-avip-fail text-white" : "bg-avip-review text-white"
                      }`}>!</span>
                    )}
                    <img
                      src={label.image_url}
                      alt={label.part_number || "Damaged label"}
                      className="w-full aspect-[2/1] object-cover rounded mb-1"
                    />
                    <span className="text-[10px] text-gray-300 font-mono block truncate">
                      {label.scenario_type === "error_unreadable" ? "Damaged" :
                       label.scenario_type === "error_not_found" ? "Unknown" :
                       label.part_number}
                    </span>
                  </button>
                ))}
              </div>

              {/* Actions */}
              <div className="flex gap-3">
                <button
                  onClick={handleCapture}
                  disabled={!selectedLabel}
                  className="flex-1 py-3 bg-avip-info text-white font-medium rounded-xl hover:bg-avip-info/80 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  Capture & Extract
                </button>
                <button
                  onClick={handleClose}
                  className="px-6 py-3 bg-gray-700 text-gray-300 rounded-xl hover:bg-gray-600 transition-colors"
                >
                  Cancel
                </button>
              </div>
            </div>
          )}

          {/* Phase: Scanning animation */}
          {phase === "scanning" && (
            <div className="flex flex-col items-center py-12">
              <div className="relative w-48 h-32 mb-6">
                <img
                  src={selectedLabel?.image_url}
                  alt="Scanning"
                  className="w-full h-full object-contain rounded-lg"
                />
                {/* Scan line animation */}
                <div className="absolute inset-0 overflow-hidden rounded-lg">
                  <div className="absolute left-0 right-0 h-0.5 bg-avip-info shadow-[0_0_8px_rgba(59,130,246,0.8)] animate-[scanLine_1.5s_ease-in-out_infinite]" />
                </div>
              </div>
              <div className="flex items-center gap-2 text-avip-info">
                <svg className="w-5 h-5 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                <span className="font-medium">Extracting text via OCR...</span>
              </div>
              <p className="text-xs text-gray-500 mt-2">Identifying part number from label</p>
            </div>
          )}

          {/* Phase: Result */}
          {phase === "result" && result && (
            <div>
              <div className="flex items-center gap-3 mb-4">
                <div className="w-10 h-10 bg-avip-pass rounded-full flex items-center justify-center">
                  <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                  </svg>
                </div>
                <div>
                  <h3 className="text-white font-bold">Part Number Extracted</h3>
                  <p className="text-xs text-gray-400">OCR confidence: {(result.confidence * 100).toFixed(0)}%</p>
                </div>
              </div>

              <div className="bg-gray-900 rounded-xl p-4 mb-4 border border-gray-700">
                <p className="text-xs text-gray-500 mb-1 uppercase tracking-wide">Extracted Text</p>
                <p className="text-sm text-avip-info font-mono">{result.extracted_text}</p>
              </div>

              <div className="bg-gray-900 rounded-xl p-4 mb-5 border border-gray-700">
                <div className="grid grid-cols-2 gap-3 text-sm">
                  <div className="text-gray-400">Part Number</div>
                  <div className="text-white font-mono font-bold">{result.part.part_number}</div>
                  <div className="text-gray-400">Revision</div>
                  <div className="text-white">{result.part.revision}</div>
                  <div className="text-gray-400">Description</div>
                  <div className="text-white">{result.part.description}</div>
                  <div className="text-gray-400">Material</div>
                  <div className="text-white">{result.part.material}</div>
                  <div className="text-gray-400">Supplier</div>
                  <div className="text-white">{result.part.supplier}</div>
                </div>
              </div>

              <div className="flex gap-3">
                <button
                  onClick={handleAccept}
                  className="flex-1 py-3 bg-avip-pass text-white font-medium rounded-xl hover:bg-avip-pass/80 transition-colors"
                >
                  Accept & Start Inspection
                </button>
                <button
                  onClick={handleReset}
                  className="px-6 py-3 bg-gray-700 text-gray-300 rounded-xl hover:bg-gray-600 transition-colors"
                >
                  Re-scan
                </button>
              </div>
            </div>
          )}

          {/* Error state */}
          {phase === "error" && errorInfo && (
            <div className="flex flex-col items-center">
              <div className="w-14 h-14 bg-avip-fail rounded-full flex items-center justify-center mb-4">
                <svg className="w-7 h-7 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </div>
              <h3 className="text-lg font-bold text-white mb-1">OCR Extraction Failed</h3>
              <p className="text-sm text-gray-400 mb-4 text-center">{errorInfo.message}</p>

              {errorInfo.extractedText && (
                <div className="bg-gray-900 rounded-xl p-3 mb-4 border border-gray-700 w-full">
                  <p className="text-xs text-gray-500 mb-1 uppercase tracking-wide">Extracted Text</p>
                  <p className="text-sm text-avip-fail font-mono">{errorInfo.extractedText}</p>
                </div>
              )}

              <div className="bg-avip-review/10 border border-avip-review/30 rounded-xl p-3 mb-5 w-full">
                <p className="text-xs text-avip-review flex items-start gap-2">
                  <svg className="w-4 h-4 mt-0.5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  {errorInfo.suggestion}
                </p>
              </div>

              <div className="flex gap-3 w-full">
                <button
                  onClick={handleReset}
                  className="flex-1 py-3 bg-avip-info text-white font-medium rounded-xl hover:bg-avip-info/80 transition-colors"
                >
                  Try Another Label
                </button>
                <button
                  onClick={handleClose}
                  className="px-6 py-3 bg-gray-700 text-gray-300 rounded-xl hover:bg-gray-600 transition-colors"
                >
                  Use Manual Entry
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
