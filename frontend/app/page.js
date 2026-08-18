'use client';

import { useState } from 'react';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:7071/api';

export default function Home() {
  const [question, setQuestion] = useState('Show top 5 products by revenue in Florida for the last 90 days');
  const [loading, setLoading] = useState(false);
  const [answer, setAnswer] = useState('Ask a business question to update the dashboard.');
  const [data, setData] = useState(null);
  const [action, setAction] = useState(null);

  async function ask() {
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question }),
      });
      const body = await response.json();
      if (!response.ok) throw new Error(body.error || 'Request failed');
      setAnswer(body.answer || 'Completed.');
      setData(body.data || null);
      setAction(body.dashboardAction || null);
    } catch (error) {
      setAnswer(`API error: ${error.message}`);
      setData(null);
      setAction(null);
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="shell">
      <aside className="sidebar">
        <div className="brand">InsightFlow AI</div>
        <div className="subbrand">Conversational BI on Azure</div>
        <nav>
          <span className="active">AI Analyst</span>
          <span>Sales Overview</span>
          <span>Products</span>
          <span>Regions</span>
          <span>Customers</span>
        </nav>
        <div className="stack">
          <small>Azure architecture</small>
          <p>Static Web Apps</p>
          <p>Azure Functions</p>
          <p>Microsoft Foundry</p>
          <p>Azure SQL</p>
          <p>Power BI Embedded</p>
        </div>
      </aside>

      <section className="workspace">
        <header>
          <div>
            <h1>Business Intelligence Copilot</h1>
            <p>Ask questions in natural language and drive the analytics experience.</p>
          </div>
          <div className="status">Azure connected</div>
        </header>

        <div className="grid">
          <section className="card chatCard">
            <div className="sectionTitle">Ask InsightFlow</div>
            <textarea value={question} onChange={(e) => setQuestion(e.target.value)} />
            <button onClick={ask} disabled={loading}>{loading ? 'Analyzing…' : 'Analyze'}</button>
            <div className="answer">
              <strong>AI response</strong>
              <p>{answer}</p>
            </div>
          </section>

          <section className="card dashboardCard">
            <div className="sectionTitle">Dashboard Preview</div>
            <div className="dashboardHeader">
              <div>
                <small>Target Power BI page</small>
                <h2>{action?.page || 'Sales Overview'}</h2>
              </div>
              <div className="pill">Live data layer</div>
            </div>

            {Array.isArray(data) && data.length > 0 ? (
              <div className="bars">
                {data.map((row, index) => {
                  const max = Math.max(...data.map((x) => Number(x.TotalRevenue || 0)), 1);
                  const width = Math.max(8, (Number(row.TotalRevenue || 0) / max) * 100);
                  return (
                    <div className="barRow" key={index}>
                      <div className="barLabel">{row.ProductName}</div>
                      <div className="barTrack"><div className="barFill" style={{ width: `${width}%` }} /></div>
                      <div className="barValue">${Number(row.TotalRevenue || 0).toLocaleString()}</div>
                    </div>
                  );
                })}
              </div>
            ) : data && !Array.isArray(data) ? (
              <div className="kpis">
                {Object.entries(data).map(([key, value]) => (
                  <div className="kpi" key={key}>
                    <small>{key}</small>
                    <strong>{typeof value === 'number' ? value.toLocaleString() : String(value ?? '-')}</strong>
                  </div>
                ))}
              </div>
            ) : (
              <div className="placeholder">Power BI embed will replace this preview in the next phase.</div>
            )}
          </section>
        </div>
      </section>
    </main>
  );
}
