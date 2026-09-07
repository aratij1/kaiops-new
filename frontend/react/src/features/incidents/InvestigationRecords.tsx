import { useState } from "react";

type Evidence = Record<string, unknown>;
const display = (value: unknown) => String(value ?? "Not recorded");
const SIZE = 8;

export function InvestigationRecords({ evidence, requirements }: { evidence: Evidence[]; requirements: Evidence[] }) {
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("all");
  const [page, setPage] = useState(0);
  const categories = [...new Set(evidence.map(item => display(item.category)))].sort();
  const filtered = evidence.filter(item => (category === "all" || display(item.category) === category)
    && [item.category, item.connector, item.source_id, item.citation, item.evidence_id].some(value => display(value).toLowerCase().includes(query.toLowerCase())));
  const pages = Math.max(1, Math.ceil(filtered.length / SIZE));
  const current = Math.min(page, pages - 1);
  return <section className="ic-section ic-investigation-records">
    <header><div><span>Investigation records</span><h3>Evidence library</h3></div><span className="ic-record-count">{evidence.length} records</span></header>
    <p className="ic-library-summary">{evidence.filter(item => item.accepted_for_rca === true).length} accepted for RCA. Attached context remains available for review.</p>
    {requirements.length > 0 && <div className="ic-open-requirements"><h4>Evidence still required ({requirements.length})</h4><ul>{requirements.map((item, index) => <li key={display(item.requirement_id ?? index)}><strong>{display(item.category)}</strong><span>{display(item.question ?? item.reason)}</span><em>{display(item.status)}</em></li>)}</ul></div>}
    <details className="ic-evidence-browser"><summary>Browse evidence ({evidence.length})</summary>
      <div className="ic-evidence-filters"><label>Search evidence<input value={query} placeholder="Source, citation, or evidence ID" onChange={event => { setQuery(event.target.value); setPage(0); }} /></label><label>Category<select value={category} onChange={event => { setCategory(event.target.value); setPage(0); }}><option value="all">All categories</option>{categories.map(value => <option key={value}>{value}</option>)}</select></label></div>
      <ul className="ic-attached-records">{filtered.slice(current * SIZE, (current + 1) * SIZE).map((item, index) => <li key={`${display(item.evidence_id)}-${current * SIZE + index}`}><div><strong>{display(item.category)}</strong><span>{display(item.connector ?? item.source_id)}</span></div><p>{display(item.citation)}</p><small>{item.accepted_for_rca === true ? "Accepted for RCA" : "Attached context"} / {display(item.freshness)}<br />{display(item.evidence_id)}</small></li>)}</ul>
      {!filtered.length && <p>No evidence matches these filters.</p>}
      <nav className="ic-evidence-pagination" aria-label="Evidence pages"><button type="button" disabled={current === 0} onClick={() => setPage(current - 1)}>Previous evidence</button><span>{filtered.length ? current * SIZE + 1 : 0}-{Math.min((current + 1) * SIZE, filtered.length)} of {filtered.length}</span><button type="button" disabled={current + 1 >= pages} onClick={() => setPage(current + 1)}>Next evidence</button></nav>
    </details>
  </section>;
}
