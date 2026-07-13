/**
 * Lam Research and ideyaLabs logo components.
 * Rendered as inline SVG for reliable cross-browser display.
 */

interface LogoProps {
  variant?: "dark" | "light";
  className?: string;
}

export function LamResearchLogo({ variant = "dark", className = "" }: LogoProps) {
  const fill = variant === "light" ? "#FFFFFF" : "#1B2A4A";
  return (
    <svg viewBox="0 0 200 50" fill="none" xmlns="http://www.w3.org/2000/svg" className={`h-10 ${className}`}>
      {/* Mountain/triangle mark */}
      <path d="M5 45 L28 8 L51 45 Z" fill={fill} opacity="0.9"/>
      {/* Streaks inside the mountain */}
      <path d="M15 40 L28 18 L32 25 L22 40 Z" fill={variant === "light" ? "#1B2A4A" : "#FFFFFF"} opacity="0.3"/>
      <line x1="18" y1="38" x2="28" y2="22" stroke={variant === "light" ? "#1B2A4A" : "#FFFFFF"} strokeWidth="0.8" opacity="0.4"/>
      <line x1="20" y1="40" x2="30" y2="24" stroke={variant === "light" ? "#1B2A4A" : "#FFFFFF"} strokeWidth="0.8" opacity="0.35"/>
      <line x1="22" y1="42" x2="32" y2="26" stroke={variant === "light" ? "#1B2A4A" : "#FFFFFF"} strokeWidth="0.8" opacity="0.3"/>
      <line x1="24" y1="44" x2="34" y2="28" stroke={variant === "light" ? "#1B2A4A" : "#FFFFFF"} strokeWidth="0.8" opacity="0.25"/>
      {/* "Lam" text - bold serif */}
      <text x="56" y="32" fontFamily="Georgia, 'Times New Roman', serif" fontSize="26" fontWeight="700" fill={fill} letterSpacing="-1">Lam</text>
      {/* Registration mark */}
      <text x="108" y="18" fontFamily="Georgia, serif" fontSize="8" fill={fill}>®</text>
      {/* "RESEARCH" text - spaced capitals */}
      <text x="56" y="46" fontFamily="Inter, Arial, sans-serif" fontSize="13" fontWeight="400" fill={fill} letterSpacing="3.5">RESEARCH</text>
    </svg>
  );
}

export function IdeyaLabsLogo({ variant = "dark", className = "" }: LogoProps) {
  const src = variant === "light" ? "/ideyalabs-logo-white.png" : "/ideyalabs-logo-dark.png";
  return (
    <img
      src={src}
      alt="ideyaLabs"
      className={`h-6 ${className}`}
    />
  );
}

export function AvipBadge({ variant = "dark", className = "" }: LogoProps) {
  const borderColor = variant === "light" ? "border-white/20" : "border-lam-gray-200";
  const textColor = variant === "light" ? "text-white/60" : "text-lam-gray-500";
  return (
    <span className={`text-[10px] font-medium px-2 py-0.5 rounded border ${borderColor} ${textColor} ${className}`}>
      AVIP
    </span>
  );
}
