"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { apiPost, ApiError } from "@/lib/api";
import { ErrorNote } from "@/components/ui";

const DEFAULT_PURPOSE =
  "Assemble cited public evidence about this company for an investment review.";

/**
 * Companies House number-only intake. Name, website and jurisdiction are
 * optional confirmation fields; the number alone opens a research case.
 */
export function IntakeConsole({ onCreated }: { onCreated?: () => void }) {
  const router = useRouter();
  const [number, setNumber] = useState("");
  const [website, setWebsite] = useState("");
  const [purpose, setPurpose] = useState(DEFAULT_PURPOSE);
  const [classification, setClassification] = useState("public");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const created = await apiPost<{ company_id: string }>("company-intakes", {
        companies_house_number: number.trim(),
        website: website.trim() || null,
        purpose,
        classification,
      });
      onCreated?.();
      router.push(`/companies/${created.company_id}`);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "The intake could not be recorded.");
      setBusy(false);
    }
  }

  return (
    <form className="intake" onSubmit={submit}>
      <div className="intake-primary">
        <div className="field" style={{ flex: 1, minWidth: "13rem" }}>
          <label htmlFor="ch-number">Companies House number</label>
          <input
            id="ch-number"
            className="mono-input"
            value={number}
            onChange={(event) => setNumber(event.target.value.toUpperCase())}
            placeholder="09339981 or SC123456"
            autoComplete="off"
            spellCheck={false}
            required
            minLength={6}
            maxLength={12}
          />
        </div>
        <button className="btn" data-variant="primary" type="submit" disabled={busy || !number.trim()}>
          {busy ? "Recording…" : "New company"}
        </button>
      </div>
      <p className="field-hint">
        The number alone is enough. It is recorded as a submitted claim and stays held until a named
        reviewer accepts it — nothing merges on a name.
      </p>

      <button
        type="button"
        className="intake-toggle"
        onClick={() => setExpanded((value) => !value)}
        aria-expanded={expanded}
      >
        {expanded ? "Hide" : "Show"} optional intake fields
      </button>

      {expanded ? (
        <div className="intake-extra">
          <div className="field">
            <label htmlFor="ch-website">Company website (optional)</label>
            <input
              id="ch-website"
              value={website}
              onChange={(event) => setWebsite(event.target.value)}
              placeholder="https://example.com"
              autoComplete="off"
              spellCheck={false}
            />
            <span className="field-hint">Recorded as an unverified domain claim.</span>
          </div>
          <div className="field">
            <label htmlFor="ch-classification">Data classification</label>
            <select
              id="ch-classification"
              value={classification}
              onChange={(event) => setClassification(event.target.value)}
            >
              <option value="public">Public</option>
              <option value="synthetic">Synthetic</option>
              <option value="internal">Internal</option>
              <option value="restricted">Restricted</option>
            </select>
            <span className="field-hint">
              Only public and synthetic cases are eligible for external-model research.
            </span>
          </div>
          <div className="field" style={{ gridColumn: "1 / -1" }}>
            <label htmlFor="ch-purpose">Recorded purpose</label>
            <textarea
              id="ch-purpose"
              value={purpose}
              onChange={(event) => setPurpose(event.target.value)}
              minLength={10}
              maxLength={500}
              required
            />
          </div>
        </div>
      ) : null}

      {error ? <ErrorNote message={error} /> : null}
    </form>
  );
}
