import React, { useCallback, useEffect, useState } from 'react';
import { api } from '../api.js';
import { Bar, ErrorNote, Pill, Ring, Stat, fmt, useTask } from '../components.jsx';

const dayName = (iso) => new Date(`${iso}T00:00:00`).toLocaleDateString(undefined, { weekday: 'short' });

function recordTitle(r) {
  const d = r.data;
  if (r.kind === 'food') return `${d.items.map((i) => i.name).join(', ')} · ${fmt(d.totals.calories)} kcal · score ${d.health.score}`;
  if (r.kind === 'freshness') return `${d.item}: ${d.classification}`;
  if (r.kind === 'hygiene') return `Kitchen check: ${d.score == null ? 'not enough visible' : `${d.score}/100`} (${d.grade})`;
  return r.kind;
}

export default function Dashboard({ go }) {
  const [data, setData] = useState(null);
  const [recs, setRecs] = useState([]);
  const [summary, setSummary] = useState('');
  const load = useTask();
  const sum = useTask();

  const refresh = useCallback(async () => {
    const out = await load.run(async () => Promise.all([api.insights(), api.records(12)]));
    if (out) {
      setData(out[0]);
      setRecs(out[1].records);
    }
  }, [load.run]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  async function remove(id) {
    await load.run(() => api.deleteRecord(id));
    refresh();
  }

  async function makeSummary() {
    const out = await sum.run(api.summary);
    if (out) setSummary(out.summary);
  }

  if (!data) {
    return (
      <section>
        <h2>Dashboard</h2>
        <ErrorNote text={load.error} />
        {!load.error && <p className="muted">Loading your day…</p>}
      </section>
    );
  }

  const t = data.targets;
  const max = Math.max(1, ...data.week.map((d) => d.calories), t ? t.calories : 0);
  const hyg = data.hygiene_trend[data.hygiene_trend.length - 1];

  return (
    <section>
      <h2>Dashboard</h2>
      <p className="lede">Your day against your targets, with alerts that need a decision.</p>
      <ErrorNote text={load.error} />

      {data.alerts.length > 0 ? (
        <div className="stack" aria-label="Alerts">
          {data.alerts.map((a, i) => (
            <p key={i} className={`banner ${a.level === 'critical' ? 'bad' : a.level === 'warn' ? 'warn' : 'info'}`}>
              {a.text}
            </p>
          ))}
        </div>
      ) : (
        <p className="banner good">No alerts. Scan a meal, check produce or run a kitchen check to see insights here.</p>
      )}

      {!t && (
        <p className="banner info">
          Set your profile in the Meal Planner to see daily targets.{' '}
          <button className="link" onClick={() => go('planner')}>
            Open Meal Planner
          </button>
        </p>
      )}

      <div className="grid">
        <div className="card">
          <h3>Today</h3>
          <div className="row" style={{ gap: 18 }}>
            <Ring value={t ? Math.min(100, (data.today.calories / t.calories) * 100) : null} label={t ? `of ${t.calories} kcal` : 'kcal'} />
            <div className="grow">
              <div className="stats">
                <Stat value={data.today.calories} label="kcal" />
                <Stat value={`${data.today.protein_g} g`} label={t ? `protein of ${t.protein_g}` : 'protein'} />
                <Stat value={data.today.meals} label="meals scanned" />
              </div>
            </div>
          </div>
        </div>

        <div className="card">
          <h3>Quality</h3>
          <div className="stats">
            <Stat value={data.avg_health_score == null ? '–' : data.avg_health_score} label="avg meal health score, 7 days" />
            <Stat value={hyg && hyg.score != null ? hyg.score : '–'} label="latest kitchen hygiene" />
            <Stat value={data.meals_this_week} label="meals this week" />
          </div>
        </div>
      </div>

      <div className="card" style={{ marginTop: 16 }}>
        <h3>Calories, last 7 days</h3>
        <div className="chart" role="img" aria-label="Calories per day for the last seven days">
          {t && <div className="target-line" style={{ bottom: `${(t.calories / max) * 100}%` }} title={`Target ${t.calories} kcal`} />}
          {data.week.map((d) => (
            <div className="col" key={d.date}>
              <span className="num small">{d.calories || ''}</span>
              <div className="colbar" style={{ height: `${Math.max(2, (d.calories / max) * 100)}%` }} />
              <span className="small muted">{dayName(d.date)}</span>
            </div>
          ))}
        </div>
        {t && <p className="muted small" style={{ margin: '8px 0 0' }}>Dashed line: your target of {t.calories} kcal.</p>}
      </div>

      <div className="grid" style={{ marginTop: 16 }}>
        <div className="card">
          <div className="row between">
            <h3 style={{ margin: 0 }}>AI summary</h3>
            <button className="btn sm" onClick={makeSummary} disabled={sum.loading}>
              {sum.loading ? 'Writing…' : 'Write summary'}
            </button>
          </div>
          <ErrorNote text={sum.error} />
          <p className="pre">{summary || 'Get a short summary and action items based on your scans this week.'}</p>
        </div>

        <div className="card">
          <h3>Recent scans</h3>
          {recs.length === 0 ? (
            <p className="muted">Nothing yet. Start with a Food Scan.</p>
          ) : (
            <ul className="list">
              {recs.map((r) => (
                <li key={r.id}>
                  <span className="grow">
                    <Pill>{r.kind}</Pill> <span className="small">{recordTitle(r)}</span>
                  </span>
                  <button className="btn ghost sm" onClick={() => remove(r.id)} aria-label="Delete this record">
                    Delete
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </section>
  );
}
