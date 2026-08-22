import React from "react"
import { cn } from "@/lib/utils"

export interface BrandLogoProps {
  variant?: "full" | "icon" | "horizontal"
  theme?: "dark" | "light" | "auto"
  size?: "xs" | "sm" | "md" | "lg" | "xl"
  showTagline?: boolean
  className?: string
  imgClassName?: string
  usePng?: boolean
}

export const BrandLogo: React.FC<BrandLogoProps> = ({
  variant = "full",
  theme = "dark",
  size = "md",
  className,
  imgClassName,
  usePng = false,
}) => {
  // Balanced height presets tailored for proportional 4.5:1 ratio
  const sizeMap = {
    xs: "h-5",
    sm: "h-7",
    md: "h-9",
    lg: "h-12",
    xl: "h-16",
  }

  const isDark = theme === "dark"

  if (variant === "icon") {
    const iconSrc = usePng ? "/logo-icon.png" : "/logo-icon.svg"
    return (
      <div className={cn("inline-flex items-center justify-center shrink-0", className)}>
        <img
          src={iconSrc}
          alt="ControlCheck AI Icon"
          className={cn(
            "w-auto object-contain transition-transform duration-200 hover:scale-105",
            sizeMap[size],
            imgClassName
          )}
        />
      </div>
    )
  }

  // Full horizontal logo
  const logoSrc = isDark
    ? (usePng ? "/logo-dark.png" : "/logo-dark.svg")
    : (usePng ? "/logo-light.png" : "/logo-light.svg")

  return (
    <div className={cn("inline-flex items-center justify-start shrink-0 overflow-hidden", className)}>
      <img
        src={logoSrc}
        alt="ControlCheck AI Logo"
        className={cn(
          "w-auto max-w-full object-contain transition-opacity duration-200 select-none",
          sizeMap[size],
          imgClassName
        )}
      />
    </div>
  )
}

export default BrandLogo
