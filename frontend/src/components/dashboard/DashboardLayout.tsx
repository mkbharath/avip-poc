import { NavLink, Outlet, Link } from "react-router-dom";
import { LamResearchLogo, IdeyaLabsLogo } from "../common/Logo";

const tabs = [
  { label: "Inspection", to: "inspection" },
  { label: "Defects", to: "defects" },
  { label: "Suppliers", to: "suppliers" },
  { label: "AI Performance", to: "ai" },
];

export function DashboardLayout() {
  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-lam-navy px-6 py-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <LamResearchLogo variant="light" className="h-8" />
            <div className="w-px h-5 bg-white/20" />
            <div>
              <h1 className="text-sm font-bold text-white">AVIP Dashboards</h1>
              <p className="text-[11px] text-white/50">AI Vision Inspection Platform — Analytics</p>
            </div>
          </div>
          <div className="flex items-center gap-4">
            <Link to="/kiosk" className="text-sm text-white/50 hover:text-white">Station</Link>
            <Link to="/review" className="text-sm text-white/50 hover:text-white">Review</Link>
            <Link to="/demo" className="text-sm text-lam-green hover:text-lam-green-light">Demo</Link>
            <div className="w-px h-4 bg-white/10" />
            <div className="flex items-center gap-1.5">
              <span className="text-white/30 text-[10px]">Powered by</span>
              <IdeyaLabsLogo variant="light" className="h-4" />
            </div>
          </div>
        </div>
        <nav className="flex gap-1 mt-3">
          {tabs.map((tab) => (
            <NavLink
              key={tab.to}
              to={tab.to}
              className={({ isActive }) =>
                `px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                  isActive
                    ? "bg-white/15 text-white"
                    : "text-white/50 hover:text-white hover:bg-white/5"
                }`
              }
            >
              {tab.label}
            </NavLink>
          ))}
        </nav>
      </header>
      <main className="p-6">
        <Outlet />
      </main>
    </div>
  );
}
