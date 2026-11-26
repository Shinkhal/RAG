interface AlertProps {
  type?: "error" | "info" | "success";
  children: React.ReactNode;
  className?: string;
}

export function Alert({ type = "error", children, className = "" }: AlertProps) {
  return (
    <p className={`alert alert--${type} ${className}`} role="alert">
      {children}
    </p>
  );
}
