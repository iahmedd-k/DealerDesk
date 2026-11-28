import React from "react";

interface DealerDeskLogoProps {
  variant?: "light" | "dark";
  subtitle?: string;
  size?: "sm" | "md";
}

export default function DealerDeskLogo({
  variant = "light",
  subtitle,
  size = "md",
}: DealerDeskLogoProps) {
  const isDark = variant === "dark";
  const boxSize = size === "sm" ? "h-7 w-7" : "h-8 w-8";
  const markBg = isDark ? "bg-white text-[#0f0f10]" : "bg-[#171717] text-white";
  const titleColor = isDark ? "text-white" : "text-[#171717]";
  const subColor = isDark ? "text-[#85858b]" : "text-[#737373]";

  return (
    <span className="inline-flex items-center gap-2.5 select-none">
      <span
        className={`flex ${boxSize} items-center justify-center rounded-lg ${markBg} shrink-0`}
        aria-hidden="true"
      >
        {/* Flat geometric automotive coupe roofline + showroom desk baseline */}
        <svg
          viewBox="0 0 24 24"
          fill="none"
          className="h-4 w-4"
          xmlns="http://www.w3.org/2000/svg"
        >
          <path
            d="M4.5 14.5L7.2 8.8C7.6 7.9 8.5 7.3 9.5 7.3H14.5C15.5 7.3 16.4 7.9 16.8 8.8L19.5 14.5"
            stroke="currentColor"
            strokeWidth="1.8"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          <path
            d="M3.5 14.5H20.5"
            stroke="currentColor"
            strokeWidth="1.8"
            strokeLinecap="round"
          />
          <circle cx="7.5" cy="14.5" r="1.5" fill="currentColor" />
          <circle cx="16.5" cy="14.5" r="1.5" fill="currentColor" />
          <path
            d="M6.5 18H17.5"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
            opacity="0.55"
          />
        </svg>
      </span>
      <span className="leading-tight">
        <span className={`block text-[15px] font-medium tracking-tight ${titleColor}`}>
          Dealer<span className={isDark ? "text-blue-300" : "text-blue-700"}>Desk</span>
        </span>
        {subtitle && (
          <span className={`block text-[11px] font-normal ${subColor}`}>
            {subtitle}
          </span>
        )}
      </span>
    </span>
  );
}
