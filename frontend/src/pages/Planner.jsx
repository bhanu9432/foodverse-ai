import React, { useEffect, useState } from 'react';
import { api } from '../api.js';
import { Bar, Busy, ErrorNote, Pill, Stat, fmt, useTask } from '../components.jsx';

const DEFAULT = {
  sex: 'male', age: 28, height_cm: 172, weight_kg: 68,
  activity: 'moderate', goal: 'maintain', diet: 'veg',
  allergies: '', dislikes: '', cuisine: 'Indian',
};

export default function Planner() {
  const [p, setP] = useState(DEFAULT);
  const [saved, setSaved] = useState(false);
  const [adjust, setAdjust] = useState('');
  const [plan, setPlan] = useState(null);
  const [day, setDay] = useState(0);
  const task = useTask();

  useEffect(() => {
    api.getProfile().then((r) => {
      if (r.profile) {
        setP({ ...DEFAULT, ...r.profile });
        setSaved(true);
      }
    }).catch(() => {});
  }, []);

  const set = (k, v) => setP((cur) => ({ ...cur, [k]: v }));
  const num = (k) => (e) => set(k, e.target.value === '' ? '' : Number(e.target.value));

  async function submit(e) {
    e.preventDefault();
    const body = { ...p, age: Number(p.age), height_cm: Number(p.height_cm), weight_kg: Number(p.weight_kg) };
    const out = await task.run(() => api.generatePlan({ profile: body, adjust }));
    if (out) {
      setPlan(out);
      setDay(0);
      setSaved(true);
    }
  }

  const d = plan && plan.days[day];

  return (
    <section>
      <h2>Meal Planner</h2>
      <p className="lede">
        Daily targets are calculated from your body and goal. The AI proposes a 7-day plan, the server checks each day against your target and
        scales portions that miss it. Recent meal scans feed into the next plan.
      </p>
      <div className="grid">
        <form className="card" onSubmit={submit} style={{ alignSelf: 'start' }}>
          <h3>Your profile {saved && <Pill kind="good">saved</Pill>}</h3>
          <div className="form">
            <label className="f">Sex
              <select value={p.sex} onChange={(e) => set('sex', e.target.value)}>
                <option value="male">Male</option>
                <option value="female">Female</option>
              </select>
            </label>
            <label className="f">Age
              <input type="number" min="14" max="90" value={p.age} onChange={num('age')} required />
            </label>
            <label className="f">Height (cm)
              <input type="number" min="120" max="220" value={p.height_cm} onChange={num('height_cm')} required />
            </label>
            <label className="f">Weight (kg)
              <input type="number" min="35" max="200" value={p.weight_kg} onChange={num('weight_kg')} required />
            </label>
            <label className="f">Activity
              <select value={p.activity} onChange={(e) => set('activity', e.target.value)}>
                <option value="sedentary">Desk job, little exercise</option>
                <option value="light">Light, 1-3 days a week</option>
                <option value="moderate">Moderate, 3-5 days</option>
                <option value="high">Hard, 6-7 days</option>
              </select>
            </label>
            <label className="f">Goal
              <select value={p.goal} onChange={(e) => set('goal', e.target.value)}>
                <option value="lose">Lose weight gradually</option>
                <option value="maintain">Maintain weight</option>
                <option value="gain">Build muscle</option>
              </select>
            </label>
            <label className="f">Diet
              <select value={p.diet} onChange={(e) => set('diet', e.target.value)}>
                <option value="veg">Vegetarian</option>
                <option value="egg">Vegetarian plus eggs</option>
                <option value="nonveg">Non-vegetarian</option>
              </select>
            </label>
            <label className="f">Cuisine
              <input type="text" maxLength={60} value={p.cuisine} onChange={(e) => set('cuisine', e.target.value)} />
            </label>
            <label className="f">Allergies
              <input type="text" maxLength={200} value={p.allergies} onChange={(e) => set('allergies', e.target.value)} placeholder="Peanuts, shellfish" />
            </label>
            <label className="f">Dislikes
              <input type="text" maxLength={200} value={p.dislikes} onChange={(e) => set('dislikes', e.target.value)} placeholder="Bitter gourd" />
            </label>
          </div>
          <label className="f" style={{ marginTop: 12 }}>
            Adjust the plan (optional)
            <input type="text" maxLength={400} value={adjust} onChange={(e) => setAdjust(e.target.value)} placeholder="More protein at breakfast, lighter dinners" />
          </label>
          <div style={{ marginTop: 12 }}>
            <Busy loading={task.loading} label="Building your week… this takes up to a minute">
              {plan ? 'Regenerate plan' : 'Generate plan'}
            </Busy>
          </div>
          <ErrorNote text={task.error} />
          <p className="note">General guidance, not medical advice. If you are pregnant or have a medical condition, ask a dietitian.</p>
        </form>

        <div className="card">
          {!plan && <p className="muted">Your plan appears here.</p>}
          {plan && (
            <>
              <div className="stats">
                <Stat value={plan.targets.calories} label="kcal per day" />
                <Stat value={plan.targets.protein_g} label="protein g" />
                <Stat value={plan.targets.carbs_g} label="carbs g" />
                <Stat value={plan.targets.fat_g} label="fat g" />
              </div>
              <p className="muted small">Resting energy {plan.targets.bmr} kcal, daily burn {plan.targets.tdee} kcal (Mifflin-St Jeor).</p>
              {plan.rationale && <p>{plan.rationale}</p>}
              {plan.adaptive_note && <p className="note">{plan.adaptive_note}</p>}
              <div className="dayrow" role="tablist" aria-label="Day">
                {plan.days.map((x, i) => (
                  <button key={x.day} className="chip" aria-pressed={i === day} onClick={() => setDay(i)}>
                    {x.day.slice(0, 3)}
                  </button>
                ))}
              </div>
              <div className="tablew">
                <table>
                  <thead>
                    <tr>
                      <th>Meal</th>
                      <th>Dish</th>
                      <th className="n">kcal</th>
                      <th className="n">Protein</th>
                    </tr>
                  </thead>
                  <tbody>
                    {d.meals.map((m, i) => (
                      <tr key={i}>
                        <td>{m.slot}</td>
                        <td>
                          {m.name}
                          {m.portion && <div className="muted small">{m.portion}</div>}
                        </td>
                        <td className="n">{fmt(m.calories)}</td>
                        <td className="n">{fmt(m.protein_g)} g</td>
                      </tr>
                    ))}
                    <tr>
                      <td colSpan="2"><b>Day total</b></td>
                      <td className="n"><b>{d.totals.calories}</b></td>
                      <td className="n"><b>{d.totals.protein_g} g</b></td>
                    </tr>
                  </tbody>
                </table>
              </div>
              <div style={{ marginTop: 12 }}>
                <div className="row between">
                  <span className="small muted">Day vs target {d.scaled ? '(portions scaled to fit)' : ''}</span>
                  <span className="num small">{d.target_gap_pct > 0 ? '+' : ''}{d.target_gap_pct}%</span>
                </div>
                <Bar value={d.totals.calories} max={plan.targets.calories * 1.1} kind={Math.abs(d.target_gap_pct) <= 6 ? 'good' : 'warn'} />
              </div>
            </>
          )}
        </div>
      </div>
    </section>
  );
}
