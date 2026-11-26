import { forwardRef, useState, type InputHTMLAttributes } from "react";

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string;
  hint?: string;
  error?: string;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ label, hint, error, id, className = "", type, ...props }, ref) => {
    const [showPassword, setShowPassword] = useState(false);
    const isPassword = type === "password";
    const inputType = isPassword && showPassword ? "text" : type;

    return (
      <div className={`input-group ${error ? "input-group--error" : ""} ${className}`}>
        <label htmlFor={id} className="input-group__label">
          {label}
        </label>
        <div className="input-group__wrapper">
          <input
            ref={ref}
            id={id}
            type={inputType}
            className="input-group__field"
            aria-invalid={!!error}
            aria-describedby={
              error ? `${id}-error` : hint ? `${id}-hint` : undefined
            }
            {...props}
          />
          {isPassword && (
            <button
              type="button"
              className="input-group__toggle"
              onClick={() => setShowPassword((v) => !v)}
              aria-label={showPassword ? "Hide password" : "Show password"}
              tabIndex={-1}
            >
              {showPassword ? "Hide" : "Show"}
            </button>
          )}
        </div>
        {hint && !error && (
          <small id={`${id}-hint`} className="input-group__hint">
            {hint}
          </small>
        )}
        {error && (
          <small id={`${id}-error`} className="input-group__error" role="alert">
            {error}
          </small>
        )}
      </div>
    );
  }
);

Input.displayName = "Input";
