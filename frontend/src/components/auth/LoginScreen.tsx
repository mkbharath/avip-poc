import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { LamResearchLogo, IdeyaLabsLogo } from "../common/Logo";

// Demo user accounts for the PoC
const DEMO_USERS = [
  { id: "operator", name: "Alex Chen", role: "Operator", station: "STN-LIV-01" },
  { id: "inspector", name: "Maria Santos", role: "IQA Inspector", station: "IQA-LIV" },
  { id: "engineer", name: "David Kim", role: "Quality Engineer", station: "QE-CORP" },
  { id: "admin", name: "Sarah Johnson", role: "Admin", station: "ADMIN" },
];

export function LoginScreen() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setIsLoading(true);

    // Simulate authentication delay
    setTimeout(() => {
      // Accept any non-empty credentials for the PoC
      if (email && password) {
        const user = DEMO_USERS.find((u) => email.toLowerCase().includes(u.id)) || DEMO_USERS[0];
        localStorage.setItem("avip_user", JSON.stringify(user));
        navigate("/kiosk");
      } else {
        setError("Please enter your credentials");
      }
      setIsLoading(false);
    }, 800);
  };

  const handleQuickLogin = (userId: string) => {
    const user = DEMO_USERS.find((u) => u.id === userId)!;
    localStorage.setItem("avip_user", JSON.stringify(user));
    navigate(userId === "inspector" ? "/review" : userId === "engineer" ? "/dashboard" : "/kiosk");
  };

  return (
    <div className="min-h-screen flex">
      {/* Left panel - Branding hero */}
      <div className="hidden lg:flex lg:w-1/2 bg-lam-navy relative overflow-hidden flex-col justify-between p-12">
        {/* Background pattern */}
        <div className="absolute inset-0 opacity-10">
          <div className="absolute top-20 -left-20 w-96 h-96 rounded-full border border-white/20" />
          <div className="absolute top-40 left-40 w-64 h-64 rounded-full border border-white/10" />
          <div className="absolute -bottom-20 -right-20 w-80 h-80 rounded-full border border-white/15" />
          <div className="absolute bottom-40 right-20 w-48 h-48 rounded-full bg-lam-green/5" />
        </div>

        {/* Logo */}
        <div className="relative z-10">
          <LamResearchLogo variant="light" className="scale-125 origin-left" />
        </div>

        {/* Hero content */}
        <div className="relative z-10 flex-1 flex flex-col justify-center">
          <h1 className="text-4xl font-bold text-white leading-tight mb-4">
            AI Vision Inspection
            <br />
            <span className="text-lam-green">Platform</span>
          </h1>
          <p className="text-lg text-white/70 max-w-md leading-relaxed">
            100% automated cosmetic inspection of precision manufacturing parts.
            AI-powered defect detection with full traceability.
          </p>
          <div className="mt-8 flex items-center gap-6">
            <div className="text-center">
              <p className="text-2xl font-bold text-white">99%</p>
              <p className="text-xs text-white/50 mt-1">Accuracy</p>
            </div>
            <div className="w-px h-10 bg-white/20" />
            <div className="text-center">
              <p className="text-2xl font-bold text-white">&lt;60s</p>
              <p className="text-xs text-white/50 mt-1">Cycle Time</p>
            </div>
            <div className="w-px h-10 bg-white/20" />
            <div className="text-center">
              <p className="text-2xl font-bold text-white">100%</p>
              <p className="text-xs text-white/50 mt-1">Traceability</p>
            </div>
          </div>
        </div>

        {/* Powered by */}
        <div className="relative z-10 flex items-center gap-2">
          <span className="text-white/40 text-xs">Powered by</span>
          <IdeyaLabsLogo variant="light" className="h-6" />
        </div>
      </div>

      {/* Right panel - Login form */}
      <div className="flex-1 flex flex-col justify-center px-8 sm:px-16 lg:px-20 bg-white">
        {/* Mobile logo (shown on small screens) */}
        <div className="lg:hidden mb-10">
          <LamResearchLogo variant="dark" />
        </div>

        <div className="w-full max-w-sm mx-auto">
          <h2 className="text-2xl font-bold text-lam-navy mb-1">Welcome back</h2>
          <p className="text-lam-gray-500 text-sm mb-8">Sign in to the AI Vision Inspection Platform</p>

          <form onSubmit={handleSubmit} className="space-y-5">
            <div>
              <label htmlFor="email" className="block text-sm font-medium text-lam-gray-700 mb-1.5">
                Email or Username
              </label>
              <input
                id="email"
                type="text"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="operator@lamresearch.com"
                className="w-full px-4 py-3 border border-lam-gray-300 rounded-lg text-sm
                         focus:border-lam-green focus:ring-2 focus:ring-lam-green/20 focus:outline-none
                         transition-colors placeholder:text-lam-gray-400"
                autoComplete="username"
              />
            </div>

            <div>
              <label htmlFor="password" className="block text-sm font-medium text-lam-gray-700 mb-1.5">
                Password
              </label>
              <input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Enter your password"
                className="w-full px-4 py-3 border border-lam-gray-300 rounded-lg text-sm
                         focus:border-lam-green focus:ring-2 focus:ring-lam-green/20 focus:outline-none
                         transition-colors placeholder:text-lam-gray-400"
                autoComplete="current-password"
              />
            </div>

            {error && (
              <div className="p-3 bg-avip-fail-light rounded-lg">
                <p className="text-sm text-avip-fail">{error}</p>
              </div>
            )}

            <button
              type="submit"
              disabled={isLoading}
              className="w-full py-3 bg-lam-navy text-white font-medium rounded-lg
                       hover:bg-lam-navy-light active:scale-[0.98] transition-all
                       disabled:opacity-60 disabled:cursor-not-allowed min-h-[48px]"
            >
              {isLoading ? (
                <span className="flex items-center justify-center gap-2">
                  <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                  Signing in...
                </span>
              ) : (
                "Sign In"
              )}
            </button>
          </form>

          {/* SSO hint */}
          <div className="mt-6 text-center">
            <p className="text-xs text-lam-gray-400">
              Production uses Lam SSO (SAML/OIDC)
            </p>
          </div>

          {/* Quick access for demo */}
          <div className="mt-10 pt-6 border-t border-lam-gray-200">
            <p className="text-xs font-medium text-lam-gray-500 uppercase tracking-wide mb-3">
              Demo Quick Access
            </p>
            <div className="grid grid-cols-2 gap-2">
              {DEMO_USERS.map((user) => (
                <button
                  key={user.id}
                  onClick={() => handleQuickLogin(user.id)}
                  className="px-3 py-2.5 text-left border border-lam-gray-200 rounded-lg
                           hover:border-lam-green hover:bg-lam-green/5 transition-colors"
                >
                  <p className="text-xs font-medium text-lam-navy">{user.name}</p>
                  <p className="text-[10px] text-lam-gray-400">{user.role}</p>
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
