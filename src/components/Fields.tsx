import { useEffect, useState, type ReactNode } from "react";
export function Field({
  label,
  value,
  onChange,
  unit,
  min,
  max,
  nullable = false,
}: {
  label: string;
  value: number | null | undefined;
  onChange: (value: number | null) => void;
  unit?: string;
  min?: number;
  max?: number;
  nullable?: boolean;
}) {
  const [draft, setDraft] = useState(
    value == null ? "" : String(value).replace(".", ","),
  );
  const [invalid, setInvalid] = useState(false);
  useEffect(() => {
    setDraft(value == null ? "" : String(value).replace(".", ","));
    setInvalid(false);
  }, [value]);
  return (
    <label className="field">
      <span>{label}</span>
      <div className={`number-wrap ${invalid ? "invalid" : ""}`}>
        <input
          aria-label={label}
          aria-invalid={invalid}
          inputMode="decimal"
          value={draft}
          placeholder={nullable ? "Automático" : ""}
          onChange={(e) => {
            const text = e.target.value;
            setDraft(text);
            const val = Number(text.trim().replace(",", "."));
            const ok =
              text.trim() !== "" &&
              Number.isFinite(val) &&
              (min == null || val >= min) &&
              (max == null || val <= max);
            setInvalid(!ok && !(nullable && text === ""));
          }}
          onBlur={() => {
            const val = Number(draft.trim().replace(",", "."));
            if (!draft.trim() && nullable) {
              onChange(null);
              setInvalid(false);
            } else if (
              draft.trim() &&
              Number.isFinite(val) &&
              (min == null || val >= min) &&
              (max == null || val <= max)
            ) {
              onChange(val);
              setInvalid(false);
            } else {
              setDraft(value == null ? "" : String(value).replace(".", ","));
              setInvalid(false);
            }
          }}
          onKeyDown={(e) => {
            if (e.key === "Enter") e.currentTarget.blur();
          }}
        />
        {unit && <small>{unit}</small>}
      </div>
    </label>
  );
}
export function TextField({
  label,
  value,
  onChange,
  max = 120,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  max?: number;
}) {
  return (
    <label className="field">
      <span>{label}</span>
      <input
        aria-label={label}
        value={value}
        maxLength={max}
        onChange={(e) => onChange(e.target.value)}
      />
    </label>
  );
}
export function Select({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  options: [string, string][];
}) {
  return (
    <label className="field">
      <span>{label}</span>
      <select
        aria-label={label}
        value={value}
        onChange={(e) => onChange(e.target.value)}
      >
        {options.map(([v, t]) => (
          <option key={v} value={v}>
            {t}
          </option>
        ))}
      </select>
    </label>
  );
}
export function Toggle({
  label,
  checked,
  onChange,
}: {
  label: string;
  checked: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <label className="toggle">
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
      />
      <span>{label}</span>
    </label>
  );
}
export function Section({
  title,
  children,
  open = true,
}: {
  title: string;
  children: ReactNode;
  open?: boolean;
}) {
  return (
    <details className="property-section" open={open}>
      <summary>{title}</summary>
      <div>{children}</div>
    </details>
  );
}
