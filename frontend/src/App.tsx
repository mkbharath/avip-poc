import { Routes, Route, Navigate } from "react-router-dom";
import { LoginScreen } from "./components/auth/LoginScreen";
import { AppLayout } from "./components/common/AppLayout";
import { ScanScreen } from "./components/kiosk/ScanScreen";
import { CaptureScreen } from "./components/kiosk/CaptureScreen";
import { ResultScreen } from "./components/kiosk/ResultScreen";
import { ReviewQueue } from "./components/review/ReviewQueue";
import { ReviewWorkbench } from "./components/review/ReviewWorkbench";
import { InspectionDashboard } from "./components/dashboard/InspectionDashboard";
import { DefectDashboard } from "./components/dashboard/DefectDashboard";
import { SupplierDashboard } from "./components/dashboard/SupplierDashboard";
import { AIPerformanceDashboard } from "./components/dashboard/AIPerformanceDashboard";
import { PresenterPanel } from "./components/demo/PresenterPanel";
import { AILab } from "./components/ai-lab/AILab";
import { SourceComparisonReview } from "./components/source-comparison/SourceComparisonReview";
import { SourceComparisonWorkbench } from "./components/source-comparison/SourceComparisonWorkbench";
import { DiscrepancyReport } from "./components/source-comparison/DiscrepancyReport";
import { IngestionMonitor } from "./components/source-comparison/IngestionMonitor";
import { ComparisonSettings } from "./components/source-comparison/ComparisonSettings";
import { TpiMonitor } from "./components/tpi/TpiMonitor";
import { TpiReviewList } from "./components/tpi/TpiReviewList";
import { TpiReviewWorkbench } from "./components/tpi/TpiReviewWorkbench";
import { TpiFinalList } from "./components/tpi/TpiFinalList";

function App() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/login" replace />} />
      <Route path="/login" element={<LoginScreen />} />

      {/* All app screens share the AppLayout (header + sidebar + content) */}
      <Route element={<AppLayout />}>
        <Route path="/kiosk" element={<ScanScreen />} />
        <Route path="/kiosk/capture/:id" element={<CaptureScreen />} />
        <Route path="/kiosk/result/:id" element={<ResultScreen />} />
        <Route path="/review" element={<ReviewQueue />} />
        <Route path="/review/:id" element={<ReviewWorkbench />} />
        <Route path="/dashboard/inspection" element={<InspectionDashboard />} />
        <Route path="/dashboard/defects" element={<DefectDashboard />} />
        <Route path="/dashboard/suppliers" element={<SupplierDashboard />} />
        <Route path="/dashboard/ai" element={<AIPerformanceDashboard />} />
        <Route path="/dashboard" element={<Navigate to="/dashboard/inspection" replace />} />
        <Route path="/demo" element={<PresenterPanel />} />
        <Route path="/ai-lab" element={<AILab />} />
        <Route path="/source-comparison/report" element={<DiscrepancyReport />} />
        <Route path="/source-comparison/review" element={<SourceComparisonReview />} />
        <Route path="/source-comparison/review/:id" element={<SourceComparisonWorkbench />} />
        <Route path="/source-comparison/monitor" element={<IngestionMonitor />} />
        <Route path="/source-comparison/settings" element={<ComparisonSettings />} />
        <Route path="/source-comparison" element={<Navigate to="/source-comparison/report" replace />} />
        <Route path="/tpi/monitor" element={<TpiMonitor />} />
        <Route path="/tpi/review" element={<TpiReviewList />} />
        <Route path="/tpi/review/:pcbaId" element={<TpiReviewWorkbench />} />
        <Route path="/tpi/final" element={<TpiFinalList />} />
        <Route path="/tpi" element={<Navigate to="/tpi/monitor" replace />} />
      </Route>
    </Routes>
  );
}

export default App;
