"use client";

import { useMemo, useState } from "react";
import { Send, Sparkles, X } from "lucide-react";

interface FormField {
  name: string;
  label: string;
  type: "select" | "multiselect";
  options?: string[];
  recommended?: string[];
  allow_custom?: boolean;
  required?: boolean;
}

interface ClarifyFormProps {
  title: string;
  description: string;
  fields: FormField[];
  onSubmit: (values: Record<string, string | string[]>) => void;
}

export function ClarifyForm({
  title,
  description,
  fields,
  onSubmit,
}: ClarifyFormProps) {
  // Auto-preselect from recommended values
  const initialValues = useMemo(() => {
    const init: Record<string, string | string[]> = {};
    for (const f of fields) {
      if (f.recommended && f.recommended.length > 0) {
        if (f.type === "select") {
          init[f.name] = f.recommended[0];
        } else if (f.type === "multiselect") {
          init[f.name] = [...f.recommended];
        }
      }
    }
    return init;
  }, [fields]);

  const [values, setValues] = useState<Record<string, string | string[]>>(initialValues);
  const [submitted, setSubmitted] = useState(false);
  const [cancelled, setCancelled] = useState(false);

  if (submitted) {
    return (
      <div className="rounded-xl border border-border bg-muted/30 px-4 py-3">
        <p className="text-xs text-muted-foreground">✓ 已提交表单: {title}</p>
      </div>
    );
  }

  if (cancelled) {
    return (
      <div className="rounded-xl border border-border bg-muted/30 px-4 py-3">
        <p className="text-xs text-muted-foreground">✗ 已取消: {title}</p>
      </div>
    );
  }

  const handleChange = (name: string, value: string | string[]) => {
    setValues((prev) => ({ ...prev, [name]: value }));
  };

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    setSubmitted(true);
    onSubmit(values);
  };

  const handleCancel = () => {
    setCancelled(true);
    onSubmit({ __cancelled__: "true" });
  };

  const isValid = fields
    .filter((field) => field.required !== false)
    .every((field) => {
      const fieldValue = values[field.name];
      if (Array.isArray(fieldValue)) return fieldValue.length > 0;
      return fieldValue && fieldValue.trim().length > 0;
    });

  return (
    <div className="rounded-xl border border-accent/30 bg-accent/5 p-4">
      <h4 className="mb-1 text-sm font-medium text-foreground">{title}</h4>
      <p className="mb-4 text-xs text-muted-foreground">{description}</p>

      <form onSubmit={handleSubmit} className="flex flex-col gap-3">
        {fields.map((field) => (
          <FormFieldComponent
            key={field.name}
            field={field}
            value={values[field.name]}
            onChange={(value) => handleChange(field.name, value)}
          />
        ))}

        <div className="mt-1 flex items-center justify-end gap-2">
          <button
            type="button"
            onClick={handleCancel}
            className="flex items-center justify-center gap-1.5 rounded-lg border border-border px-4 py-2 text-xs font-medium text-muted-foreground transition-colors hover:bg-muted/50"
          >
            <X size={12} />
            取消
          </button>
          <button
            type="submit"
            disabled={!isValid}
            className="flex items-center justify-center gap-1.5 rounded-lg bg-accent px-4 py-2 text-xs font-medium text-accent-foreground transition-colors hover:bg-accent/90 disabled:opacity-40"
          >
            <Send size={12} />
            提交
          </button>
        </div>
      </form>
    </div>
  );
}

interface FormFieldComponentProps {
  field: FormField;
  value: string | string[] | undefined;
  onChange: (value: string | string[]) => void;
}

function FormFieldComponent({
  field,
  value,
  onChange,
}: FormFieldComponentProps) {
  const [customInput, setCustomInput] = useState("");

  const labelElement = (
    <label className="mb-1 block text-xs font-medium text-foreground/80">
      {field.label}
      {field.required !== false && (
        <span className="ml-0.5 text-accent">*</span>
      )}
    </label>
  );

  // Use original options order; recommended only affects selection and badge
  const recommended = field.recommended ?? [];
  const options = field.options ?? [];

  if (field.type === "select") {
    const selectedValue = (value as string) ?? "";
    // Check if current value is a custom input (not in the options list)
    const optsSet = new Set(field.options ?? []);
    const isCustomSelected = selectedValue && !optsSet.has(selectedValue);

    return (
      <div>
        {labelElement}
        <div className="flex flex-wrap gap-1.5">
          {options.map((option) => {
            const isSelected = selectedValue === option;
            const isRecommended = recommended.includes(option);
            return (
              <button
                key={option}
                type="button"
                onClick={() => {
                  setCustomInput("");
                  onChange(option);
                }}
                className={`flex items-center gap-1 rounded-md border px-2.5 py-1 text-xs transition-colors ${
                  isSelected
                    ? "border-accent bg-accent/20 text-accent"
                    : "border-border bg-muted text-muted-foreground hover:border-accent/40"
                }`}
              >
                {option}
                {isRecommended && (
                  <Sparkles size={9} className="text-accent/70" />
                )}
              </button>
            );
          })}
        </div>
        {field.allow_custom && (
          <input
            value={isCustomSelected ? selectedValue : customInput}
            onChange={(e) => {
              setCustomInput(e.target.value);
              onChange(e.target.value.trim());
            }}
            className="mt-1.5 w-full rounded-lg border border-border bg-muted px-3 py-1.5 text-xs text-foreground placeholder:text-muted-foreground focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
            placeholder="或输入自定义内容..."
          />
        )}
      </div>
    );
  }

  if (field.type === "multiselect") {
    const selectedValues = (value as string[]) ?? [];
    return (
      <div>
        {labelElement}
        <div className="flex flex-wrap gap-1.5">
          {options.map((option) => {
            const isSelected = selectedValues.includes(option);
            const isRecommended = recommended.includes(option);
            return (
              <button
                key={option}
                type="button"
                onClick={() => {
                  const newValues = isSelected
                    ? selectedValues.filter((v) => v !== option)
                    : [...selectedValues, option];
                  onChange(newValues);
                }}
                className={`flex items-center gap-1 rounded-md border px-2.5 py-1 text-xs transition-colors ${
                  isSelected
                    ? "border-accent bg-accent/20 text-accent"
                    : "border-border bg-muted text-muted-foreground hover:border-accent/40"
                }`}
              >
                {option}
                {isRecommended && (
                  <Sparkles size={9} className="text-accent/70" />
                )}
              </button>
            );
          })}
        </div>
      </div>
    );
  }

  return null;
}
