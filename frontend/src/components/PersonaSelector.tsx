import { useEffect, useId, useRef, useState } from "react";
import { Check, ChevronDown, Sparkles, X } from "lucide-react";
import type { Persona, PersonaSelection } from "../api";

interface PersonaSelectorProps {
  personas: Persona[];
  value: PersonaSelection | null;
  onChange: (value: PersonaSelection | null) => void;
  disabled?: boolean;
}

export function PersonaSelector({ personas, value, onChange, disabled = false }: PersonaSelectorProps) {
  const id = useId();
  const root = useRef<HTMLDivElement>(null);
  const [open, setOpen] = useState(false);
  const selected = personas.find(persona => persona.persona_id === value?.persona_id);

  useEffect(() => {
    if (!open) return;
    function onPointerDown(event: MouseEvent) {
      if (!root.current?.contains(event.target as Node)) setOpen(false);
    }
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  function choose(persona: Persona | null) {
    if (!persona) {
      onChange(null);
      setOpen(false);
      return;
    }
    onChange({ persona_id: persona.persona_id, intensity: persona.intensity });
    setOpen(true);
  }

  const label = selected ? selected.name : "Persona";

  return (
    <div className="persona-picker" ref={root}>
      <button
        type="button"
        className={`persona-trigger ${selected ? "is-active" : ""}`}
        aria-haspopup="dialog"
        aria-expanded={open}
        disabled={disabled || personas.length === 0}
        title={personas.length ? "Choose an answer persona" : "No personas are available yet"}
        onClick={() => setOpen(value => !value)}
      >
        <Sparkles size={14} aria-hidden="true" />
        <span>{label}</span>
        <ChevronDown size={13} aria-hidden="true" />
      </button>
      {open && (
        <div className="persona-menu" role="dialog" aria-label="Answer persona">
          <div className="persona-menu__head">
            <div>
              <strong>Answer style</strong>
              <small>Choose how the assistant writes.</small>
            </div>
            <button type="button" className="icon-button icon-button--sm" aria-label="Close persona menu" onClick={() => setOpen(false)}>
              <X size={14} aria-hidden="true" />
            </button>
          </div>
          <div className="persona-options">
            <button type="button" className={`persona-option ${!value ? "is-selected" : ""}`} onClick={() => choose(null)}>
              <span className="persona-option__body">
                <strong>Default</strong>
                <small>Clear, neutral answers grounded in your sources.</small>
              </span>
              {!value && <Check size={15} aria-hidden="true" />}
            </button>
            {personas.map(persona => {
              const active = value?.persona_id === persona.persona_id;
              return (
                <button
                  key={persona.persona_id}
                  type="button"
                  className={`persona-option ${active ? "is-selected" : ""}`}
                  onClick={() => choose(persona)}
                >
                  <span className="persona-option__body">
                    <strong>{persona.name}</strong>
                    {persona.description && <small>{persona.description}</small>}
                  </span>
                  {active && <Check size={15} aria-hidden="true" />}
                </button>
              );
            })}
          </div>
          {selected && value && (
            <div className="persona-intensity">
              <label htmlFor={`${id}-intensity`}>
                <span>Intensity</span>
                <span>{Math.round(value.intensity * 100)}%</span>
              </label>
              <input
                id={`${id}-intensity`}
                type="range"
                min={0}
                max={100}
                step={5}
                value={Math.round(value.intensity * 100)}
                onChange={event => onChange({ ...value, intensity: Number(event.target.value) / 100 })}
              />
            </div>
          )}
        </div>
      )}
    </div>
  );
}
