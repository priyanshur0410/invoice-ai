import { useState, useEffect } from "react";

const API = import.meta.env.VITE_API_URL || "http://localhost:8000";

export default function InvoicesPage() {
  const [invoices, setInvoices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState(null);

  useEffect(() => {
    fetchInvoices();
  }, []);

  const fetchInvoices = async (vendor = "") => {
    setLoading(true);
    try {
      const params = vendor ? `?vendor=${encodeURIComponent(vendor)}` : "";
      const res = await fetch(`${API}/api/invoices/${params}`);
      const data = await res.json();
      setInvoices(data);
    } catch (e) {
      console.error(e);
    }
    setLoading(false);
  };

  const handleSearch = (e) => {
    setSearch(e.target.value);
    if (e.target.value.length === 0 || e.target.value.length > 2) {
      fetchInvoices(e.target.value);
    }
  };

  const confColor = (score) => {
    if (score >= 0.8) return "conf-high";
    if (score >= 0.5) return "conf-med";
    return "conf-low";
  };

  return (
    <div className="invoices-page">
      <div className="page-header">
        <div className="page-title">Invoices</div>
        <input
          className="search-bar"
          placeholder="Search by vendor..."
          value={search}
          onChange={handleSearch}
        />
      </div>

      {loading ? (
        <div className="empty"><span className="spinner" /></div>
      ) : invoices.length === 0 ? (
        <div className="empty">
          <div className="empty-icon">📭</div>
          <div>No invoices found</div>
        </div>
      ) : (
        <div style={{ overflowX: "auto" }}>
          <table className="invoice-table">
            <thead>
              <tr>
                <th>Invoice #</th>
                <th>Vendor</th>
                <th>Date</th>
                <th>Total</th>
                <th>Currency</th>
                <th>Confidence</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {invoices.map((inv) => (
                <tr
                  key={inv.id}
                  style={{ cursor: "pointer" }}
                  onClick={() => setSelected(selected?.id === inv.id ? null : inv)}
                >
                  <td style={{ fontFamily: "var(--mono)", fontSize: 13 }}>
                    {inv.invoice_number || <span style={{ color: "var(--muted)" }}>—</span>}
                  </td>
                  <td>
                    <div style={{ fontWeight: 600 }}>{inv.vendor_normalized || inv.vendor_name || "Unknown"}</div>
                    {inv.vendor_name && inv.vendor_normalized && inv.vendor_name !== inv.vendor_normalized && (
                      <div style={{ fontSize: 11, color: "var(--muted)" }}>{inv.vendor_name}</div>
                    )}
                  </td>
                  <td style={{ fontFamily: "var(--mono)", fontSize: 12, color: "var(--muted)" }}>
                    {inv.invoice_date ? inv.invoice_date.slice(0, 10) : "—"}
                  </td>
                  <td className="amount">
                    {inv.total?.toLocaleString("en-US", { minimumFractionDigits: 2 })}
                  </td>
                  <td>
                    <span style={{ fontFamily: "var(--mono)", fontSize: 12, background: "var(--bg3)", padding: "2px 8px", borderRadius: 4 }}>
                      {inv.currency}
                    </span>
                  </td>
                  <td>
                    <div className="confidence-bar">
                      <div className="conf-track">
                        <div
                          className={`conf-fill ${confColor(inv.confidence_score)}`}
                          style={{ width: `${(inv.confidence_score * 100).toFixed(0)}%` }}
                        />
                      </div>
                      <span className="conf-val">{(inv.confidence_score * 100).toFixed(0)}%</span>
                    </div>
                  </td>
                  <td>
                    {inv.is_duplicate && <span className="dup-tag">DUPLICATE</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Detail drawer */}
      {selected && (
        <div style={{
          background: "var(--card)", border: "1px solid var(--border)",
          borderRadius: "var(--radius)", padding: 24, marginTop: 16,
        }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
            <div style={{ fontWeight: 700, fontSize: 16 }}>
              Invoice Detail — {selected.invoice_number || selected.id.slice(0, 8)}
            </div>
            <button
              onClick={() => setSelected(null)}
              style={{ background: "none", border: "none", color: "var(--muted)", cursor: "pointer", fontSize: 20 }}
            >×</button>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 16 }}>
            {[
              ["Vendor", selected.vendor_normalized || selected.vendor_name],
              ["Invoice Date", selected.invoice_date?.slice(0, 10)],
              ["Due Date", selected.due_date?.slice(0, 10)],
              ["Subtotal", selected.currency + " " + selected.subtotal?.toFixed(2)],
              ["Tax", selected.currency + " " + selected.tax?.toFixed(2)],
              ["Total", selected.currency + " " + selected.total?.toFixed(2)],
              ["Payment Terms", selected.payment_terms],
              ["Confidence", (selected.confidence_score * 100).toFixed(0) + "%"],
              ["Duplicate", selected.is_duplicate ? "Yes ⚠️" : "No"],
            ].map(([label, val]) => (
              <div key={label}>
                <div style={{ fontSize: 11, color: "var(--muted)", textTransform: "uppercase", letterSpacing: 1, marginBottom: 4 }}>{label}</div>
                <div style={{ fontWeight: 600, fontFamily: "var(--mono)", fontSize: 13 }}>{val || "—"}</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
