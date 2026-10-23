import React, { useState } from 'react';
import { api } from '../api.js';
import { Bar, Busy, ErrorNote, FilePick, Pill, Ring, Stat, VoiceInput, f1, fmt, useObjectUrl, useTask } from '../components.jsx';

const FACTORS = {
  protein: 'Protein share of calories',
  fiber: 'Fibre per 100 kcal',
  added_sugar: 'Sugar share of calories',
  saturated_fat: 'Saturated fat share',
  sodium: 'Sodium per 100 kcal',
  energy_density: 'Energy density',
};

export default function FoodScan() {
  const [file, setFile] = useState(null);
  const [note, setNote] = useState('');
  const [res, setRes] = useState(null);
  const preview = useObjectUrl(file);
  const task = useTask();

  async function submit(e) {
    e.preventDefault();
    const fd = new FormData();
    if (file) fd.append('image', file);
    fd.append('note', note);
    const out = await task.run(() => api.analyzeFood(fd));
    if (out) setRes(out);
  }

  const kind = res && res.health ? (res.health.score >= 65 ? 'good' : res.health.score >= 50 ? 'warn' : 'bad') : '';

  return (
    <section>
      <h2>Food Scan</h2>
      <p className="lede">
        Photograph a meal, say or type what it is, and get the dishes, estimated portions, nutrition and a health score.
        Photo and voice or text are combined, so a note like "made with half the oil" changes the result.
      </p>
      <div className="grid">
        <form className="card" onSubmit={submit}>
          <h3>Meal</h3>
          <div className="drop">
            {preview ? <img className="pv" src={preview} alt="Your meal" /> : <div className="pv empty">No photo yet</div>}
            <div className="row">
              <FilePick id="food-file" accept="image/*" onFiles={(f) => setFile(f[0])}>
                {file ? 'Change photo' : 'Choose photo'}
              </FilePick>
              {file && (
                <button type="button" className="btn ghost sm" onClick={() => setFile(null)}>
                  Remove
                </button>
              )}
            </div>
          </div>
          <label className="f" style={{ marginTop: 14 }}>
            Note (optional if you add a photo)
            <textarea
              rows={3}
              value={note}
              maxLength={600}
              onChange={(e) => setNote(e.target.value)}
              placeholder="Two rotis, dal tadka with one spoon of ghee, no sugar in the tea"
            />
          </label>
          <div className="row" style={{ marginTop: 10 }}>
            <VoiceInput onText={(t) => setNote((n) => (n ? `${n} ${t}` : t))} />
            <Busy loading={task.loading} label="Analysing…">
              Analyse meal
            </Busy>
          </div>
          <ErrorNote text={task.error} />
          <p className="note">Photos are sent to the AI service for analysis and are not stored on the server. Estimates can be off by 20% or more.</p>
        </form>

        <div className="card">
          {!res && <p className="muted">Results appear here.</p>}
          {res && res.no_food && <p>No food was found in that photo or note. Try a clearer photo.</p>}
          {res && !res.no_food && (
            <>
              <div className="row" style={{ gap: 18 }}>
                <Ring value={res.health.score} label={res.health.label} kind={kind} />
                <div className="stats grow">
                  <Stat value={fmt(res.totals.calories)} label="kcal" />
                  <Stat value={f1(res.totals.protein_g)} label="protein g" />
                  <Stat value={f1(res.totals.carbs_g)} label="carbs g" />
                  <Stat value={f1(res.totals.fat_g)} label="fat g" />
                </div>
              </div>
              <div className="tablew" style={{ marginTop: 14 }}>
                <table>
                  <thead>
                    <tr>
                      <th>Item</th>
                      <th className="n">Grams</th>
                      <th className="n">kcal</th>
                      <th className="n">Sure</th>
                    </tr>
                  </thead>
                  <tbody>
                    {res.items.map((i, k) => (
                      <tr key={k}>
                        <td>{i.name}</td>
                        <td className="n">{fmt(i.grams)}</td>
                        <td className="n">{fmt(i.calories)}</td>
                        <td className="n">
                          <Pill kind={i.confidence >= 0.75 ? 'good' : i.confidence >= 0.5 ? 'warn' : 'bad'}>{fmt(i.confidence * 100)}%</Pill>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <h3 style={{ marginTop: 16 }}>Why this score</h3>
              {Object.entries(res.health.breakdown).map(([k, v]) => (
                <div className="macro" key={k}>
                  <span className="small">{FACTORS[k] || k}</span>
                  <Bar value={Math.abs(v)} max={20} kind={v >= 0 ? 'good' : 'bad'} />
                  <span className="num small">{v > 0 ? '+' : ''}{v}</span>
                </div>
              ))}
              <p className="muted small">Starts at 60. Protein and fibre add points; sugar, saturated fat, sodium and energy density subtract.</p>
              {res.notes && <p className="note">{res.notes}</p>}
            </>
          )}
        </div>
      </div>
    </section>
  );
}
