import React, { useState } from 'react';
import { api } from '../api.js';
import { Busy, ErrorNote, FilePick, Pill, useObjectUrl, useTask } from '../components.jsx';

const KIND = { Fresh: 'good', 'Moderately Fresh': 'warn', Spoiled: 'bad' };

export default function Freshness() {
  const [file, setFile] = useState(null);
  const [hint, setHint] = useState('');
  const [storage, setStorage] = useState('room');
  const [days, setDays] = useState(1);
  const [flags, setFlags] = useState({ mould: false, sour_smell: false, slimy: false });
  const [res, setRes] = useState(null);
  const preview = useObjectUrl(file);
  const task = useTask();

  async function submit(e) {
    e.preventDefault();
    if (!file) {
      task.setError('Choose a photo first.');
      return;
    }
    const fd = new FormData();
    fd.append('image', file);
    fd.append('item_hint', hint);
    fd.append('storage', storage);
    fd.append('days_held', String(days));
    Object.entries(flags).forEach(([k, v]) => fd.append(k, String(v)));
    const out = await task.run(() => api.analyzeFreshness(fd));
    if (out) setRes(out);
  }

  const flag = (k, label) => (
    <label className="check">
      <input type="checkbox" checked={flags[k]} onChange={(e) => setFlags({ ...flags, [k]: e.target.checked })} />
      <span>{label}</span>
    </label>
  );

  return (
    <section>
      <h2>Freshness and Spoilage</h2>
      <p className="lede">
        The AI reads colour, texture, discolouration and surface patterns, then classifies the food as Fresh, Moderately Fresh or Spoiled.
        What you can smell or feel overrides the photo.
      </p>
      <div className="grid">
        <form className="card" onSubmit={submit}>
          <h3>Photo</h3>
          <div className="drop">
            {preview ? <img className="pv" src={preview} alt="Food to check" /> : <div className="pv empty">No photo yet</div>}
            <FilePick id="fresh-file" accept="image/*" onFiles={(f) => setFile(f[0])}>
              {file ? 'Change photo' : 'Choose photo'}
            </FilePick>
          </div>
          <div className="form" style={{ marginTop: 14 }}>
            <label className="f">
              What is it? (optional)
              <input type="text" value={hint} maxLength={80} onChange={(e) => setHint(e.target.value)} placeholder="Spinach, cooked rice…" />
            </label>
            <label className="f">
              Stored
              <select value={storage} onChange={(e) => setStorage(e.target.value)}>
                <option value="room">Room temperature</option>
                <option value="fridge">Fridge</option>
                <option value="freezer">Freezer</option>
                <option value="unknown">Not sure</option>
              </select>
            </label>
            <label className="f">
              Days held
              <input type="number" min="0" max="365" step="0.5" value={days} onChange={(e) => setDays(Math.max(0, Number(e.target.value) || 0))} />
            </label>
          </div>
          <h3 style={{ marginTop: 14 }}>Smell and touch</h3>
          {flag('mould', 'Visible mould or fuzzy growth')}
          {flag('sour_smell', 'Sour, fermented or off smell')}
          {flag('slimy', 'Slimy surface')}
          <div style={{ marginTop: 12 }}>
            <Busy loading={task.loading} label="Checking…">
              Check freshness
            </Busy>
          </div>
          <ErrorNote text={task.error} />
        </form>

        <div className="card">
          {!res && <p className="muted">Results appear here.</p>}
          {res && (
            <>
              <div className="row between">
                <h3 style={{ margin: 0 }}>{res.item}</h3>
                <Pill kind={KIND[res.classification]}>{res.classification}</Pill>
              </div>
              <p className="muted small">Model confidence {Math.round(res.confidence * 100)}%. Estimated safe time left: {res.shelf_life_days} day(s).</p>
              {res.overridden_by_user_report && <p className="banner bad">Marked Spoiled because of what you reported.</p>}
              <dl className="defs">
                <dt>Colour</dt>
                <dd>{res.visual_signs.color || '–'}</dd>
                <dt>Texture</dt>
                <dd>{res.visual_signs.texture || '–'}</dd>
                <dt>Discolouration</dt>
                <dd>{res.visual_signs.discoloration || '–'}</dd>
                <dt>Surface patterns</dt>
                <dd>{res.visual_signs.surface_patterns || '–'}</dd>
              </dl>
              <p>{res.advice}</p>
              <p className="note">{res.disclaimer}</p>
            </>
          )}
        </div>
      </div>
    </section>
  );
}
