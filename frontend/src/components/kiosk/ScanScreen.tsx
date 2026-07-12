import { useState, useRef, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import { lookupPart, createInspection } from "../../api/inspections";
import { OcrCaptureModal } from "./OcrCaptureModal";

export function ScanScreen() {
  const [barcode, setBarcode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [ocrOpen, setOcrOpen] = useState(false);
  const [partInfo, setPartInfo] = useState<{
    part_number: string;
    revision: string;
    description: string;
    material: string;
    surface_finish: string;
    family_name: string;
    supplier: string;
  } | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();

  // Auto-focus the input on mount
  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const scanMutation = useMutation({
    mutationFn: async (partNumber: string) => {
      const part = await lookupPart(partNumber);
      return part;
    },
    onSuccess: async (part) => {
      setError(null);
      setPartInfo({
        part_number: part.part_number,
        revision: part.revision,
        description: part.description,
        material: part.material,
        surface_finish: part.surface_finish,
        family_name: part.family.display_name,
        supplier: part.supplier,
      });

      // Create inspection and auto-advance after 2 seconds
      const inspection = await createInspection(part.part_number);
      setTimeout(() => {
        navigate(`/kiosk/capture/${inspection.id}`);
      }, 2000);
    },
    onError: () => {
      setError(`Part "${barcode}" not found in system`);
      setPartInfo(null);
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (barcode.trim()) {
      scanMutation.mutate(barcode.trim());
    }
  };

  const handleRouteToIQA = () => {
    setError(null);
    setBarcode("");
    inputRef.current?.focus();
  };

  const handleOcrIdentified = (partNumber: string) => {
    setOcrOpen(false);
    setBarcode(partNumber);
    scanMutation.mutate(partNumber);
  };

  return (
    <div className="min-h-screen bg-gray-900 flex flex-col items-center justify-center p-8 relative">
      {/* Status bar */}
      <div className="absolute top-0 left-0 right-0 flex items-center justify-between px-6 py-3 bg-gray-800">
        <div className="flex items-center gap-3">
          <span className="text-gray-400 text-sm font-medium">STN-LIV-01</span>
          <span className="badge bg-green-900 text-green-300">● Online</span>
        </div>
        <div className="flex items-center gap-3">
          <span className="badge bg-blue-900 text-blue-300">Calibrated</span>
          <a href="/dashboard" className="text-gray-500 hover:text-gray-300 text-sm">
            Dashboard →
          </a>
        </div>
      </div>

      {/* Main content */}
      {!partInfo && !error && (
        <div className="flex flex-col items-center animate-pulse-slow">
          {/* Barcode icon */}
          <div className="mb-8">
            <svg className="w-24 h-24 text-avip-info" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                d="M3.75 4.875c0-.621.504-1.125 1.125-1.125h4.5c.621 0 1.125.504 1.125 1.125v4.5c0 .621-.504 1.125-1.125 1.125h-4.5A1.125 1.125 0 013.75 9.375v-4.5zM3.75 14.625c0-.621.504-1.125 1.125-1.125h4.5c.621 0 1.125.504 1.125 1.125v4.5c0 .621-.504 1.125-1.125 1.125h-4.5a1.125 1.125 0 01-1.125-1.125v-4.5zM13.5 4.875c0-.621.504-1.125 1.125-1.125h4.5c.621 0 1.125.504 1.125 1.125v4.5c0 .621-.504 1.125-1.125 1.125h-4.5A1.125 1.125 0 0113.5 9.375v-4.5z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                d="M6.75 6.75h.75v.75h-.75zM6.75 16.5h.75v.75h-.75zM16.5 6.75h.75v.75h-.75zM13.5 13.5h.75v.75h-.75zM13.5 19.5h.75v.75h-.75zM19.5 13.5h.75v.75h-.75zM19.5 19.5h.75v.75h-.75zM16.5 16.5h.75v.75h-.75z" />
            </svg>
          </div>

          <h1 className="text-3xl font-bold text-white mb-2">Scan Part Barcode</h1>
          <p className="text-gray-400 mb-8">Position barcode under scanner or type part number below</p>

          <form onSubmit={handleSubmit} className="w-full max-w-md">
            <input
              ref={inputRef}
              type="text"
              value={barcode}
              onChange={(e) => setBarcode(e.target.value)}
              placeholder="Part number (e.g., 839-041322-001)"
              className="w-full px-6 py-4 text-xl text-center bg-gray-800 border-2 border-gray-600 
                         rounded-xl text-white placeholder-gray-500 focus:border-avip-info 
                         focus:outline-none transition-colors"
              autoComplete="off"
            />
            <button
              type="submit"
              disabled={!barcode.trim() || scanMutation.isPending}
              className="w-full mt-4 btn-primary text-lg disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {scanMutation.isPending ? "Looking up..." : "Identify Part"}
            </button>
          </form>

          {/* Fallback actions */}
          <div className="flex gap-4 mt-8">
            <button
              onClick={() => setOcrOpen(true)}
              className="px-4 py-3 min-h-[48px] bg-gray-700 text-gray-300 rounded-lg hover:bg-gray-600 transition-colors"
            >
              OCR Capture
            </button>
            <button className="px-4 py-3 min-h-[48px] bg-gray-700 text-gray-300 rounded-lg hover:bg-gray-600 transition-colors">
              Manual Entry
            </button>
          </div>
        </div>
      )}

      {/* Part identified - success state */}
      {partInfo && (
        <div className="flex flex-col items-center animate-fade-in">
          <div className="w-16 h-16 bg-avip-pass rounded-full flex items-center justify-center mb-6">
            <svg className="w-8 h-8 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
            </svg>
          </div>
          <h2 className="text-2xl font-bold text-white mb-1">Part Identified</h2>
          <p className="text-gray-400 mb-6">Loading inspection configuration...</p>

          <div className="bg-gray-800 rounded-xl p-6 w-full max-w-md border border-gray-700">
            <div className="grid grid-cols-2 gap-3 text-sm">
              <div className="text-gray-400">Part Number</div>
              <div className="text-white font-mono font-bold">{partInfo.part_number}</div>
              <div className="text-gray-400">Revision</div>
              <div className="text-white">{partInfo.revision}</div>
              <div className="text-gray-400">Description</div>
              <div className="text-white">{partInfo.description}</div>
              <div className="text-gray-400">Family</div>
              <div className="text-white">{partInfo.family_name}</div>
              <div className="text-gray-400">Material</div>
              <div className="text-white">{partInfo.material}</div>
              <div className="text-gray-400">Supplier</div>
              <div className="text-white">{partInfo.supplier}</div>
            </div>
          </div>

          <div className="mt-6 flex items-center gap-2 text-avip-info">
            <svg className="w-5 h-5 animate-spin" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
            <span>Advancing to capture...</span>
          </div>
        </div>
      )}

      {/* Error state - unidentified part */}
      {error && (
        <div className="flex flex-col items-center animate-fade-in">
          <div className="w-16 h-16 bg-avip-review rounded-full flex items-center justify-center mb-6">
            <svg className="w-8 h-8 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M12 9v2m0 4h.01M12 3l9.5 16.5H2.5L12 3z" />
            </svg>
          </div>
          <h2 className="text-2xl font-bold text-white mb-2">Unidentified Part</h2>
          <p className="text-gray-400 mb-6">{error}</p>

          <div className="flex gap-4">
            <button
              onClick={handleRouteToIQA}
              className="btn-fail text-lg"
            >
              Route to IQA
            </button>
            <button
              onClick={() => { setError(null); setBarcode(""); inputRef.current?.focus(); }}
              className="px-6 py-3 bg-gray-700 text-white rounded-lg hover:bg-gray-600 transition-colors"
            >
              Try Again
            </button>
          </div>
        </div>
      )}

      {/* OCR Capture Modal */}
      <OcrCaptureModal
        isOpen={ocrOpen}
        onClose={() => setOcrOpen(false)}
        onPartIdentified={handleOcrIdentified}
      />
    </div>
  );
}
