import { NavLink, Outlet, useLocation } from "react-router-dom";
import { LamResearchLogo, IdeyaLabsLogo } from "./Logo";

const NAV_ITEMS = [
  {
    label: "Station",
    to: "/kiosk",
    icon: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
          d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z" />
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 13a3 3 0 11-6 0 3 3 0 016 0z" />
      </svg>
    ),
  },
  {
    label: "Review Queue",
    to: "/review",
    icon: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
          d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" />
      </svg>
    ),
  },
  { type: "divider" as const },
  {
    label: "Inspections",
    to: "/dashboard/inspection",
    icon: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
          d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
      </svg>
    ),
  },
  {
    label: "Defects",
    to: "/dashboard/defects",
    icon: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
          d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
      </svg>
    ),
  },
  {
    label: "Suppliers",
    to: "/dashboard/suppliers",
    icon: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
          d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
      </svg>
    ),
  },
  {
    label: "AI Performance",
    to: "/dashboard/ai",
    icon: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
          d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
      </svg>
    ),
  },
  { type: "divider" as const },
  {
    label: "Demo Panel",
    to: "/demo",
    icon: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
          d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
    ),
  },
];

export function AppLayout() {
  const location = useLocation();

  // Get current user from localStorage
  const userStr = localStorage.getItem("avip_user");
  const user = userStr ? JSON.parse(userStr) : { name: "Operator", role: "Operator" };

  return (
    <div className="min-h-screen flex flex-col bg-gray-50">
      {/* Top header bar */}
      <header className="h-14 bg-lam-navy flex items-center justify-between px-4 flex-shrink-0 z-20">
        <div className="flex items-center gap-3">
          <LamResearchLogo variant="light" className="h-8" />
          <div className="w-px h-6 bg-white/20" />
          <span className="text-white/70 text-sm font-medium hidden sm:block">
            AI Vision Inspection Platform
          </span>
        </div>
        <div className="flex items-center gap-4">
          <span className="text-white/50 text-xs hidden md:block">STN-LIV-01 • Online</span>
          <div className="w-px h-5 bg-white/20" />
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-full bg-lam-green/20 flex items-center justify-center">
              <span className="text-lam-green text-xs font-bold">
                {user.name?.charAt(0) || "O"}
              </span>
            </div>
            <span className="text-white/70 text-xs hidden md:block">{user.name}</span>
          </div>
        </div>
      </header>

      <div className="flex flex-1 overflow-hidden">
        {/* Left sidebar */}
        <aside className="w-56 bg-white border-r border-gray-200 flex flex-col flex-shrink-0">
          <nav className="flex-1 py-4 px-3 space-y-1 overflow-y-auto">
            {NAV_ITEMS.map((item, idx) => {
              if ("type" in item && item.type === "divider") {
                return <div key={idx} className="my-3 border-t border-gray-100" />;
              }
              const navItem = item as { label: string; to: string; icon: React.ReactNode };
              const isActive = location.pathname === navItem.to ||
                location.pathname.startsWith(navItem.to + "/");
              return (
                <NavLink
                  key={navItem.to}
                  to={navItem.to}
                  className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                    isActive
                      ? "bg-lam-navy/10 text-lam-navy border-l-3 border-lam-navy"
                      : "text-gray-600 hover:bg-gray-100 hover:text-gray-900"
                  }`}
                >
                  <span className={isActive ? "text-lam-navy" : "text-gray-400"}>
                    {navItem.icon}
                  </span>
                  {navItem.label}
                </NavLink>
              );
            })}
          </nav>

          {/* Powered by footer */}
          <div className="p-4 border-t border-gray-100">
            <div className="flex items-center gap-2">
              <span className="text-gray-400 text-[10px]">Powered by</span>
              <IdeyaLabsLogo variant="dark" className="h-4" />
            </div>
          </div>
        </aside>

        {/* Main content area */}
        <main className="flex-1 overflow-y-auto bg-gray-50">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
