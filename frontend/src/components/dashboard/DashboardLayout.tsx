import { NavLink, Outlet, Link } from "react-router-dom";

const tabs = [
  { label: "Inspection", to: "inspection" },
  { label: "Defects", to: "defects" },
  { label: "Suppliers", to: "suppliers" },
  { label: "AI Performance", to: "ai" },
];

export function DashboardLayout() {
  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-gray-900">AVIP Dashboards</h1>
            <p className="text-xs text-gray-500 mt-0.5">AI Vision Inspection Platform — Analytics</p>
          </div>
          <div className="flex items-center gap-4">
            <Link to="/kiosk" className="text-sm text-gray-500 hover:text-gray-700">Station</Link>
            <Link to="/review" className="text-sm text-gray-500 hover:text-gray-700">Review</Link>
            <Link to="/demo" className="text-sm text-avip-info hover:underline">Demo</Link>
          </div>
        </div>
        <nav className="flex gap-1 mt-4">
          {tabs.map((tab) => (
            <NavLink
              key={tab.to}
              to={tab.to}
              className={({ isActive }) =>
                `px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                  isActive
                    ? "bg-avip-info text-white"
                    : "text-gray-600 hover:bg-gray-100"
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
