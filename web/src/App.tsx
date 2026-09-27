import { useEffect, useState } from "react";

// The Two Switches live above the fold (S6 rule 1). M0: controls only; wiring lands in M2/M3.
const JURISDICTIONS = ["IN", "US", "EU", "WIPO-track"] as const;

export default function App() {
  const [jurisdiction, setJurisdiction] = useState<string>("IN");
  const [asOf, setAsOf] = useState<string>(new Date().toISOString().slice(0, 10));
  const [health, setHealth] = useState<string>("checking…");

  useEffect(() => {
    fetch("/health")
      .then((r) => r.json())
      .then((b) => setHealth(`${b.status} · ${b.mode}`))
      .catch(() => setHealth("offline"));
  }, []);

  return (
    <main className="min-h-screen bg-stone-50 text-stone-900">
      <header className="border-b border-stone-200 bg-white px-6 py-4">
        <h1 className="text-xl font-semibold">IP-SAKTI Sahayak</h1>
        <p className="text-sm text-stone-600">Ayurveda IP and regulatory guidance, as of a date.</p>
        <div className="mt-4 flex flex-wrap gap-6" aria-label="The Two Switches">
          <label className="flex flex-col text-sm">
            Jurisdiction
            <select
              className="mt-1 rounded border border-stone-300 px-2 py-1"
              value={jurisdiction}
              onChange={(e) => setJurisdiction(e.target.value)}
            >
              {JURISDICTIONS.map((j) => (
                <option key={j}>{j}</option>
              ))}
            </select>
          </label>
          <label className="flex flex-col text-sm">
            As-of date
            <input
              type="date"
              className="mt-1 rounded border border-stone-300 px-2 py-1"
              value={asOf}
              onChange={(e) => setAsOf(e.target.value)}
            />
          </label>
        </div>
      </header>
      <section className="px-6 py-8 text-sm text-stone-600">
        <p>Early scaffold. Answering arrives in a later milestone.</p>
        <p className="mt-2">API: {health}</p>
        <p className="mt-6 text-xs">Guidance with sources, not legal advice.</p>
      </section>
    </main>
  );
}
