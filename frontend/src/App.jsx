import { useState } from "react";
import UploadPage from "./pages/UploadPage";
import InvoicesPage from "./pages/InvoicesPage";
import AnalyticsPage from "./pages/AnalyticsPage";
import "./App.css";

export default function App() {
  const [tab, setTab] = useState("upload");

  return (
    <div className="app">
      <header className="header">
        <div className="header-inner">
          <div className="logo">
            <span className="logo-icon">⚡</span>
            <span className="logo-text">InvoiceAI</span>
          </div>
          <nav className="nav">
            {["upload", "invoices", "analytics"].map((t) => (
              <button
                key={t}
                className={`nav-btn ${tab === t ? "active" : ""}`}
                onClick={() => setTab(t)}
              >
                {t.charAt(0).toUpperCase() + t.slice(1)}
              </button>
            ))}
          </nav>
        </div>
      </header>
      <main className="main">
        {tab === "upload" && <UploadPage />}
        {tab === "invoices" && <InvoicesPage />}
        {tab === "analytics" && <AnalyticsPage />}
      </main>
    </div>
  );
}
