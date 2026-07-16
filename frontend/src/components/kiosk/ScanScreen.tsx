import { useState, useRef, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import { ScanBarcode, Camera, PenLine, CheckCircle2, AlertTriangle, Loader2, ArrowRight } from "lucide-react";
import { lookupPart, createInspection } from "../../api/inspections";
import { OcrCaptureModal } from "./OcrCaptureModal";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";

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
    <div className="flex flex-col items-center justify-center min-h-[calc(100vh-3.5rem)] p-8">
      {!partInfo && !error && (
        <div className="flex flex-col items-center w-full max-w-md">
          {/* Animated scan icon */}
          <div className="relative mb-10">
            <div className="w-24 h-24 rounded-2xl bg-gradient-to-br from-primary/10 to-avip-info/10 flex items-center justify-center">
              <ScanBarcode className="w-12 h-12 text-primary" strokeWidth={1.5} />
            </div>
            <div className="absolute -top-1 -right-1 w-4 h-4 bg-lam-green rounded-full flex items-center justify-center shadow-glow">
              <span className="w-2 h-2 bg-white rounded-full" />
            </div>
          </div>

          <h1 className="text-2xl font-semibold text-foreground tracking-tight">Scan Part Barcode</h1>
          <p className="text-muted-foreground text-sm mt-2 mb-8">Position barcode under scanner or type part number</p>

          {/* Main input card */}
          <Card className="w-full border-0 shadow-elevated">
            <CardContent className="p-6 space-y-5">
              <div>
                <label className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider mb-2 block">
                  Part Number
                </label>
                <form onSubmit={handleSubmit}>
                  <Input
                    ref={inputRef}
                    type="text"
                    value={barcode}
                    onChange={(e) => setBarcode(e.target.value)}
                    placeholder="839-041322-001"
                    className="h-12 text-base text-center font-mono tracking-wider border-border/60 focus-visible:ring-2 focus-visible:ring-avip-info/20 focus-visible:border-avip-info"
                    autoComplete="off"
                  />
                </form>
              </div>
              <Button
                type="submit"
                disabled={!barcode.trim() || scanMutation.isPending}
                onClick={handleSubmit}
                className="w-full h-11 bg-primary hover:bg-lam-navy-light font-medium"
                size="lg"
              >
                {scanMutation.isPending ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Looking up...
                  </>
                ) : (
                  <>
                    Identify Part
                    <ArrowRight className="w-4 h-4 ml-1" />
                  </>
                )}
              </Button>
            </CardContent>
          </Card>

          {/* Secondary actions */}
          <div className="flex gap-3 mt-6">
            <Button
              variant="outline"
              onClick={() => setOcrOpen(true)}
              className="text-muted-foreground hover:text-foreground"
            >
              <Camera className="w-4 h-4 mr-1.5" />
              OCR Capture
            </Button>
            <Button
              variant="outline"
              className="text-muted-foreground hover:text-foreground"
            >
              <PenLine className="w-4 h-4 mr-1.5" />
              Manual Entry
            </Button>
          </div>
        </div>
      )}

      {partInfo && (
        <div className="flex flex-col items-center w-full max-w-md animate-in fade-in-0 zoom-in-95 duration-300">
          <div className="w-16 h-16 bg-avip-pass rounded-2xl flex items-center justify-center mb-6 shadow-lg">
            <CheckCircle2 className="w-8 h-8 text-white" />
          </div>
          <h2 className="text-xl font-semibold text-foreground mb-1">Part Identified</h2>
          <p className="text-muted-foreground text-sm mb-6">Loading inspection configuration...</p>

          <Card className="w-full">
            <CardContent className="pt-5 pb-5">
              <div className="space-y-3">
                {[
                  ["Part Number", partInfo.part_number, true],
                  ["Revision", partInfo.revision, false],
                  ["Description", partInfo.description, false],
                  ["Family", partInfo.family_name, false],
                  ["Material", partInfo.material, false],
                  ["Supplier", partInfo.supplier, false],
                ].map(([label, value, isMono]) => (
                  <div key={label as string} className="flex items-center justify-between py-1 border-b border-border/30 last:border-0">
                    <span className="text-muted-foreground text-sm">{label as string}</span>
                    <span className={`text-foreground text-sm font-medium ${isMono ? "font-mono" : ""}`}>
                      {value as string}
                    </span>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          <div className="mt-6 flex items-center gap-2.5 text-avip-info">
            <Loader2 className="w-4 h-4 animate-spin" />
            <span className="text-sm font-medium">Advancing to capture...</span>
          </div>
        </div>
      )}

      {error && (
        <div className="flex flex-col items-center animate-in fade-in-0 duration-200">
          <div className="w-16 h-16 bg-avip-review rounded-2xl flex items-center justify-center mb-6 shadow-lg">
            <AlertTriangle className="w-8 h-8 text-white" />
          </div>
          <h2 className="text-xl font-semibold text-foreground mb-2">Unidentified Part</h2>
          <p className="text-muted-foreground text-sm mb-8">{error}</p>

          <div className="flex gap-3">
            <Button
              size="lg"
              onClick={handleRouteToIQA}
              className="bg-avip-fail hover:bg-avip-fail/90 text-white shadow-sm"
            >
              Route to IQA
            </Button>
            <Button
              variant="outline"
              size="lg"
              onClick={() => { setError(null); setBarcode(""); inputRef.current?.focus(); }}
            >
              Try Again
            </Button>
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
