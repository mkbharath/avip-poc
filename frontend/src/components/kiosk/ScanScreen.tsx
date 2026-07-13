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
    <div className="page-content flex flex-col items-center justify-center min-h-[calc(100vh-56px)]">
      {!partInfo && !error && (
        <div className="flex flex-col items-center">
          <div className="mb-8">
            <svg className="w-24 h-24 text-lam-navy" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                d="M3.75 4.875c0-.621.504-1.125 1.125-1.125h4.5c.621 0 1.125.504 1.125 1.125v4.5c0 .621-.504 1.125-1.125 1.125h-4.5A1.125 1.125 0 013.75 9.375v-4.5zM3.75 14.625c0-.621.504-1.125 1.125-1.125h4.5c.621 0 1.125.504 1.125 1.125v4.5c0 .621-.504 1.125-1.125 1.125h-4.5a1.125 1.125 0 01-1.125-1.125v-4.5zM13.5 4.875c0-.621.504-1.125 1.125-1.125h4.5c.621 0 1.125.504 1.125 1.125v4.5c0 .621-.504 1.125-1.125 1.125h-4.5A1.125 1.125 0 0113.5 9.375v-4.5z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                d="M6.75 6.75h.75v.75h-.75zM6.75 16.5h.75v.75h-.75zM16.5 6.75h.75v.75h-.75zM13.5 13.5h.75v.75h-.75zM13.5 19.5h.75v.75h-.75zM19.5 13.5h.75v.75h-.75zM19.5 19.5h.75v.75h-.75zM16.5 16.5h.75v.75h-.75z" />
            </svg>
          </div>

          <h1 className="text-3xl font-bold text-gray-900 mb-2">Scan Part Barcode</h1>
          <p className="text-gray-500 mb-8">Position barcode under scanner or type part number below</p>

          <form onSubmit={handleSubmit} className="w-full max-w-md">
            <input
              ref={inputRef}
              type="text"
              value={barcode}
              onChange={(e) => setBarcode(e.target.value)}
              placeholder="Part number (e.g., 839-041322-001)"
              className="w-full px-6 py-4 text-xl text-center bg-white border-2 border-gray-300
                         rounded-xl text-gray-900 placeholder:text-gray-400 focus:border-lam-navy
                         focus:ring-2 focus:ring-lam-navy/10 focus:outline-none transition-colors"
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

          <div className="flex gap-4 mt-8">
            <button
              onClick={() => setOcrOpen(true)}
              className="px-4 py-3 min-h-[48px] bg-white border border-gray-200 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors shadow-sm"
            >
              OCR Capture
            </button>
            <button className="px-4 py-3 min-h-[48px] bg-white border border-gray-200 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors shadow-sm">
              Manual Entry
            </button>
          </div>
        </div>
      )}

      {partInfo && (
        <div className="flex flex-col items-center">
          <div className="w-16 h-16 bg-avip-pass rounded-full flex items-center justify-center mb-6">
            <svg className="w-8 h-8 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
            </svg>
          </div>
          <h2 className="text-2xl font-bold text-gray-900 mb-1">Part Identified</h2>
          <p className="text-gray-500 mb-6">Loading inspection configuration...</p>

          <div className="bg-white rounded-xl p-6 w-full max-w-md border border-gray-200 shadow-sm">
            <div className="grid grid-cols-2 gap-3 text-sm">
              <div className="text-gray-500">Part Number</div>
              <div className="text-gray-900 font-mono font-bold">{partInfo.part_number}</div>
              <div className="text-gray-500">Revision</div>
              <div className="text-gray-900">{partInfo.revision}</div>
              <div className="text-gray-500">Description</div>
              <div className="text-gray-900">{partInfo.description}</div>
              <div className="text-gray-500">Family</div>
              <div className="text-gray-900">{partInfo.family_name}</div>
              <div className="text-gray-500">Material</div>
              <div className="text-gray-900">{partInfo.material}</div>
              <div className="text-gray-500">Supplier</div>
              <div className="text-gray-900">{partInfo.supplier}</div>
            </div>
          </div>

          <div className="mt-6 flex items-center gap-2 text-lam-navy">
            <svg className="w-5 h-5 animate-spin" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
            <span>Advancing to capture...</span>
          </div>
        </div>
      )}

      {error && (
        <div className="flex flex-col items-center">
          <div className="w-16 h-16 bg-avip-review rounded-full flex items-center justify-center mb-6">
            <svg className="w-8 h-8 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M12 9v2m0 4h.01M12 3l9.5 16.5H2.5L12 3z" />
            </svg>
          </div>
          <h2 className="text-2xl font-bold text-gray-900 mb-2">Unidentified Part</h2>
          <p className="text-gray-500 mb-6">{error}</p>

          <div className="flex gap-4">
            <button onClick={handleRouteToIQA} className="btn-fail text-lg">
              Route to IQA
            </button>
            <button
              onClick={() => { setError(null); setBarcode(""); inputRef.current?.focus(); }}
              className="px-6 py-3 bg-white border border-gray-200 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors shadow-sm"
            >
              Try Again
            </button>
          </div>
        </div>
      )}

      <OcrCaptureModal
        isOpen={ocrOpen}
        onClose={() => setOcrOpen(false)}
        onPartIdentified={handleOcrIdentified}
      />
    </div>
  );
}
