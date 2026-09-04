import type { ReactNode } from "react";

interface FormFieldProps {
  id: string;
  label: string;
  required?: boolean;
  helpText?: string;
  error?: string;
  children: ReactNode;
}

export default function FormField({
  id,
  label,
  required = false,
  helpText,
  error,
  children,
}: FormFieldProps) {
  return (
    <div>
      <label htmlFor={id} className="form-label fw-semibold">
        {label}

        {required && (
          <span className="text-danger ms-1" aria-hidden="true">
            *
          </span>
        )}
      </label>

      {children}

      {helpText && !error && (
        <div id={`${id}-help`} className="form-text">
          {helpText}
        </div>
      )}

      {error && (
        <div id={`${id}-error`} className="invalid-feedback d-block">
          {error}
        </div>
      )}
    </div>
  );
}
