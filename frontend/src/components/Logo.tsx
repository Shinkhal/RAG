interface LogoProps {
  size?: "sm" | "md" | "lg";
  showText?: boolean;
}

export function Logo({ size = "md", showText = true }: LogoProps) {
  const sizeMap = { sm: 28, md: 34, lg: 44 };
  const dim = sizeMap[size];

  return (
    <span className={`logo logo--${size}`}>
      <span
        className="logo__mark"
        aria-hidden="true"
        style={{ width: dim, height: dim }}
      >
        <svg width={dim * 0.6} height={dim * 0.6} viewBox="0 0 24 24" fill="none">
          <path
            d="M4 4h7v7H4V4Zm9 0h7v7h-7V4ZM4 13h7v7H4v-7Zm12 0a3.5 3.5 0 1 0 0 7 3.5 3.5 0 0 0 0-7Z"
            fill="currentColor"
          />
        </svg>
      </span>
      {showText && <span className="logo__text">RAG Workspace</span>}
    </span>
  );
}
