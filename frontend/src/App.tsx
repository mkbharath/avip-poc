import { Routes, Route, Navigate } from "react-router-dom";
import { LoginScreen } from "./components/auth/LoginScreen";
import { ScanScreen } from "./components/kiosk/ScanScreen";
import { CaptureScreen } from "./components/kiosk/CaptureScreen";
import { ResultScreen } from "./components/kiosk/ResultScreen";
import { ReviewQueue } from "./components/review/ReviewQueue";
import { ReviewWorkbench } from "./components/review/ReviewWorkbench";
import { DashboardLayout } from "./components/dashboard/DashboardLayout";
import { InspectionDashboard } from "./components/dashboard/InspectionDashboard";
import { DefectDashboard } from "./components/dashboard/DefectDashboard";
import { SupplierDashboard } from "./components/dashboard/SupplierDashboard";
import { AIPerformanceDashboard } from "./components/dashboard/AIPerformanceDashboard";
import { PresenterPanel } from "./components/demo/PresenterPanel";

function App() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/login" replace />} />
      <Route path="/login" element={<LoginScreen />} />
      <Route path="/kiosk" element={<ScanScreen />} />
      <Route path="/kiosk/capture/:id" element={<CaptureScreen />} />
      <Route path="/kiosk/result/:id" element={<ResultScreen />} />
      <Route path="/review" element={<ReviewQueue />} />
      <Route path="/review/:id" element={<ReviewWorkbench />} />
      <Route path="/dashboard" element={<DashboardLayout />}>
        <Route index element={<InspectionDashboard />} />
        <Route path="inspection" element={<InspectionDashboard />} />
        <Route path="defects" element={<DefectDashboard />} />
        <Route path="suppliers" element={<SupplierDashboard />} />
        <Route path="ai" element={<AIPerformanceDashboard />} />
      </Route>
      <Route path="/demo" element={<PresenterPanel />} />
    </Routes>
  );
}

export default App;
