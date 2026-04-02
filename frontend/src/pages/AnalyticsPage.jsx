import { useState, useEffect } from "react";

const API = import.meta.env.VITE_API_URL || "http://localhost:8000";

async function fetchJSON(path) {
  const res = await fetch(`${API}${path}`);
  return res.json();
}

export default function AnalyticsPage() {
  const [summary, setSummary] = useState(null);
  const [vendors, setVendors] = useState([]);
  const [monthly, setMonthly] = useState([]);
  const [currencies, setCurrencies] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      fetchJSON("/api/analytics/summary"),
      fetchJSON("/api/analytics/vendor-spend?limit=8"),
      fetchJSON("/api/analytics/monthly-trend?months=6"),
      fetchJSON("/api/analytics/currency-totals"),
    ]).then(([s, v, m, c]) => {
      setSummary(s);
      setVendors(v);
      setMonthly(m);
      setCurrencies(c);
      setLoading(false);
    });
  }, []);

  if (loading) return <div className="empty"><span className="spinner" /></div>;

  const maxVendorSpend = Math.max(...vendors.map((v) => v.total_spend), 1);
  const maxMonthSpend = Math.max(...monthly.map((m) => m.total_spend), 1);

  const fmt = (n) =>
    n >= 1_000_000
      ? `${(n / 1_000_000).toFixed(1)}M`
      : n >= 1_000
      ? `${(n / 1_000).toFixed(1)}K`
      : n.toFixed(0);

  return (
    <div>
      {/* Summary cards */}
      <div className="analytics-grid">
        <div className="stat-card">
          <div className="stat-label">Total Invoices</div>
          <div className="stat-value" style={{ color: "var(--accent)" }}>
            {summary?.total_invoices || 0}
          </div>
          <div className="stat-sub">{summary?.duplicate_count} duplicates detected</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Total Spend (USD)</div>
          <div className="stat-value" style={{ color: "var(--green)" }}>
            ${fmt(summary?.total_spend || 0)}
          </div>
          <div className="stat-sub">across all vendors</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Unique Vendors</div>
          <div className="stat-value" style={{ color: "var(--accent2)" }}>
            {summary?.unique_vendors || 0}
          </div>
          <div className="stat-sub">normalized vendor names</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Avg Confidence</div>
          <div className="stat-value" style={{ color: "var(--yellow)" }}>
            {((summary?.avg_confidence || 0) * 100).toFixed(0)}%
          </div>
          <div className="stat-sub">extraction accuracy</div>
        </div>
      </div>

      <div className="charts-row">
        {/* Vendor spend */}
        <div className="chart-card">
          <div className="chart-title">💰 Spend by Vendor</div>
          {vendors.length === 0 ? (
            <div className="empty" style={{ padding: 32 }}>No data yet</div>
          ) : (
            <div className="bar-chart">
              {vendors.map((v) => (
                <div className="bar-row" key={v.vendor}>
                  <div className="bar-label" title={v.vendor}>{v.vendor}</div>
                  <div className="bar-track">
                    <div
                      className="bar-fill"
                      style={{ width: `${(v.total_spend / maxVendorSpend) * 100}%` }}
                    />
                  </div>
                  <div className="bar-val">
                    {v.currency} {fmt(v.total_spend)}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Monthly trend */}
        <div className="chart-card">
          <div className="chart-title">📈 Monthly Spend Trend</div>
          {monthly.length === 0 ? (
            <div className="empty" style={{ padding: 32 }}>No data yet</div>
          ) : (
            <div className="monthly-chart">
              {monthly.map((m) => (
                <div className="month-bar" key={m.month_label} title={`${m.month_label}: $${fmt(m.total_spend)}`}>
                  <div
                    className="month-fill"
                    style={{ height: `${(m.total_spend / maxMonthSpend) * 100}%` }}
                  />
                  <div className="month-label">
                    {m.month_label.split(" ")[0]}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Currency totals */}
      <div className="chart-card" style={{ marginTop: 24 }}>
        <div className="chart-title">🌍 Currency-wise Totals</div>
        {currencies.length === 0 ? (
          <div className="empty" style={{ padding: 32 }}>No data yet</div>
        ) : (
          <div className="currency-pills">
            {currencies.map((c) => (
              <div className="currency-pill" key={c.currency}>
                <div className="currency-code">{c.currency}</div>
                <div className="currency-total">{fmt(c.total)}</div>
                <div style={{ fontSize: 11, color: "var(--muted)" }}>{c.count} invoices</div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
