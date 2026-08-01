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
      </Route>
    </Routes>
  );
}

export default App;
