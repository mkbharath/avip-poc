import { NavLink, Outlet, useLocation } from "react-router-dom";
import {
  Camera,
  ClipboardCheck,
  BarChart3,
  AlertTriangle,
  Building2,
  Cpu,
  Play,
  ChevronRight,
} from "lucide-react";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarInset,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarProvider,
  SidebarSeparator,
  SidebarTrigger,
} from "@/components/ui/sidebar";
import { Separator } from "@/components/ui/separator";
import { LamResearchLogo, IdeyaLabsLogo } from "./Logo";

const NAV_GROUPS = [
  {
    label: "Operations",
    items: [
      { label: "Station", to: "/kiosk", icon: Camera },
      { label: "Review Queue", to: "/review", icon: ClipboardCheck },
    ],
  },
  {
    label: "Analytics",
    items: [
      { label: "Inspections", to: "/dashboard/inspection", icon: BarChart3 },
      { label: "Defects", to: "/dashboard/defects", icon: AlertTriangle },
      { label: "Suppliers", to: "/dashboard/suppliers", icon: Building2 },
      { label: "AI Performance", to: "/dashboard/ai", icon: Cpu },
    ],
  },
  {
    label: "Tools",
    items: [
      { label: "Demo Panel", to: "/demo", icon: Play },
    ],
  },
];

export function AppLayout() {
  const location = useLocation();

  const userStr = localStorage.getItem("avip_user");
  const user = userStr ? JSON.parse(userStr) : { name: "Operator", role: "Operator" };

  return (
    <SidebarProvider>
      <Sidebar collapsible="icon" className="border-r-0 bg-sidebar-gradient">
        {/* Logo */}
        <SidebarHeader className="px-5 pt-6 pb-4">
          <div className="flex items-center gap-2 group-data-[collapsible=icon]:justify-center">
            <LamResearchLogo variant="light" className="h-8 group-data-[collapsible=icon]:hidden" />
            <div className="w-8 h-8 rounded-lg bg-lam-green/20 items-center justify-center hidden group-data-[collapsible=icon]:flex">
              <span className="text-lam-green font-bold text-sm">L</span>
            </div>
          </div>
          <div className="mt-3 group-data-[collapsible=icon]:hidden">
            <span className="inline-flex items-center gap-1.5 text-[10px] text-slate-500 font-medium uppercase tracking-[0.15em]">
              <span className="w-1.5 h-1.5 rounded-full bg-lam-green animate-pulse" />
              AI Vision Platform
            </span>
          </div>
        </SidebarHeader>

        {/* Navigation */}
        <SidebarContent className="px-3 pt-1">
          {NAV_GROUPS.map((group, groupIdx) => (
            <SidebarGroup key={group.label} className={groupIdx > 0 ? "pt-4" : ""}>
              <SidebarGroupLabel className="text-slate-500 text-[10px] uppercase tracking-[0.2em] font-semibold px-3 mb-1.5">
                {group.label}
              </SidebarGroupLabel>
              <SidebarGroupContent>
                <SidebarMenu>
                  {group.items.map((item) => {
                    const isActive =
                      location.pathname === item.to ||
                      location.pathname.startsWith(item.to + "/");
                    return (
                      <SidebarMenuItem key={item.to}>
                        <SidebarMenuButton
                          isActive={isActive}
                          tooltip={item.label}
                          className={
                            isActive
                              ? "bg-sidebar-accent text-white font-medium shadow-sm"
                              : "text-slate-400 hover:text-white hover:bg-sidebar-accent"
                          }
                          render={<NavLink to={item.to} />}
                        >
                          <item.icon className={`w-[18px] h-[18px] ${isActive ? "text-lam-green" : "text-slate-500"}`} strokeWidth={isActive ? 2 : 1.5} />
                          <span className="text-[13px]">{item.label}</span>
                          {isActive && (
                            <ChevronRight className="w-3.5 h-3.5 ml-auto opacity-50" />
                          )}
                        </SidebarMenuButton>
                      </SidebarMenuItem>
                    );
                  })}
                </SidebarMenu>
              </SidebarGroupContent>
            </SidebarGroup>
          ))}
        </SidebarContent>

        {/* Footer */}
        <SidebarFooter className="px-4 pb-5 pt-3">
          <SidebarSeparator className="opacity-30 mb-4" />
          <div className="flex items-center gap-3 group-data-[collapsible=icon]:justify-center">
            <div className="w-9 h-9 rounded-full bg-gradient-to-br from-lam-green to-lam-green-dark flex items-center justify-center flex-shrink-0 shadow-glow">
              <span className="text-white text-sm font-semibold">
                {user.name?.charAt(0) || "O"}
              </span>
            </div>
            <div className="group-data-[collapsible=icon]:hidden min-w-0">
              <p className="text-slate-200 text-[13px] font-medium leading-tight truncate">{user.name}</p>
              <p className="text-slate-500 text-[11px] leading-tight">{user.role}</p>
            </div>
          </div>
          <div className="flex items-center gap-2 mt-4 group-data-[collapsible=icon]:hidden">
            <span className="text-slate-600 text-[9px] uppercase tracking-widest">Powered by</span>
            <IdeyaLabsLogo variant="light" className="h-3 opacity-40" />
          </div>
        </SidebarFooter>
      </Sidebar>

      <SidebarInset>
        {/* Top bar */}
        <header className="sticky top-0 z-20 flex h-14 shrink-0 items-center gap-3 border-b border-border/50 bg-white/80 backdrop-blur-md px-6">
          <SidebarTrigger className="-ml-2" />
          <Separator orientation="vertical" className="h-5 bg-border/50" />
          <nav className="flex items-center gap-1.5 text-sm">
            <span className="font-medium text-foreground">{getPageTitle(location.pathname)}</span>
          </nav>
          {/* Right side — station indicator */}
          <div className="ml-auto flex items-center gap-2">
            <span className="inline-flex items-center gap-1.5 text-xs text-muted-foreground bg-muted px-2.5 py-1 rounded-md">
              <span className="w-2 h-2 rounded-full bg-lam-green" />
              STN-LIV-01
            </span>
          </div>
        </header>

        {/* Main content */}
        <main className="flex-1 overflow-y-auto">
          <Outlet />
        </main>
      </SidebarInset>
    </SidebarProvider>
  );
}

function getPageTitle(path: string): string {
  if (path.startsWith("/kiosk/capture")) return "Capture";
  if (path.startsWith("/kiosk/result")) return "Result";
  if (path === "/kiosk") return "Station";
  if (path.startsWith("/review/")) return "Review Workbench";
  if (path === "/review") return "Review Queue";
  if (path === "/dashboard/inspection") return "Inspections";
  if (path === "/dashboard/defects") return "Defects";
  if (path === "/dashboard/suppliers") return "Suppliers";
  if (path === "/dashboard/ai") return "AI Performance";
  if (path === "/demo") return "Demo Panel";
  return "AVIP";
}
