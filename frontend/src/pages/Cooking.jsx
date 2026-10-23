import React, { useState } from 'react';
import { api } from '../api.js';
import { Busy, ErrorNote, Pill, StepTimer, VoiceInput, fmt, useTask } from '../components.jsx';

const splitIngredients = (s) =>
  s
    .split(/,|\band\b|\n/i)
    .map((x) => x.trim().replace(/[.]+$/, ''))
    .filter(Boolean);

export default function Cooking() {
  const [ings, setIngs] = useState(['dal', 'onion', 'tomato', 'spinach']);
  const [draft, setDraft] = useState('');
  const [opts, setOpts] = useState({ diet: 'any', allergies: '', max_minutes: 45, servings: 2 });
  const [recipes, setRecipes] = useState([]);
  const [sel, setSel] = useState(0);
  const [chat, setChat] = useState([]);
  const [q, setQ] = useState('');
  const suggest = useTask();
  const ask = useTask();

  const addIngs = (text) => setIngs((cur) => [...new Set([...cur, ...splitIngredients(text).map((x) => x.toLowerCase())])].slice(0, 40));

  async function submit(e) {
    e.preventDefault();
    if (!ings.length) {
      suggest.setError('Add at least one ingredient.');
      return;
    }
    const out = await suggest.run(() => api.suggestRecipes({ ingredients: ings, ...opts, max_minutes: Number(opts.max_minutes), servings: Number(opts.servings) }));
    if (out) {
      setRecipes(out.recipes);
      setSel(0);
      setChat([]);
    }
  }

  async function send(e) {
    e.preventDefault();
    const text = q.trim();
    if (!text) return;
    const msgs = [...chat, { role: 'user', content: text }];
    setChat(msgs);
    setQ('');
    const out = await ask.run(() => api.cookingChat({ messages: msgs, recipe: recipes[sel] || null }));
    if (out) setChat([...msgs, { role: 'assistant', content: out.reply }]);
  }

  const r = recipes[sel];

  return (
    <section>
      <h2>Smart Cooking</h2>
      <p className="lede">Tell the assistant what is in your kitchen, by typing or speaking. It suggests recipes with steps, timers and safe temperatures, then answers questions while you cook.</p>
      <div className="grid">
        <form className="card" onSubmit={submit} style={{ alignSelf: 'start' }}>
          <h3>In my kitchen</h3>
          <div className="chips">
            {ings.map((i) => (
              <button type="button" key={i} className="chip" aria-label={`Remove ${i}`} onClick={() => setIngs(ings.filter((x) => x !== i))}>
                {i} ×
              </button>
            ))}
          </div>
          <div className="row" style={{ marginTop: 10 }}>
            <input
              type="text"
              className="grow"
              value={draft}
              placeholder="Add: paneer, rice, curd"
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault();
                  addIngs(draft);
                  setDraft('');
                }
              }}
            />
            <button type="button" className="btn ghost sm" onClick={() => { addIngs(draft); setDraft(''); }}>
              Add
            </button>
            <VoiceInput onText={addIngs} />
          </div>
          <div className="form" style={{ marginTop: 14 }}>
            <label className="f">
              Diet
              <select value={opts.diet} onChange={(e) => setOpts({ ...opts, diet: e.target.value })}>
                <option value="any">Anything</option>
                <option value="vegetarian">Vegetarian</option>
                <option value="eggetarian">Vegetarian plus eggs</option>
                <option value="vegan">Vegan</option>
              </select>
            </label>
            <label className="f">
              Max minutes
              <input type="number" min="5" max="240" value={opts.max_minutes} onChange={(e) => setOpts({ ...opts, max_minutes: e.target.value })} />
            </label>
            <label className="f">
              Servings
              <input type="number" min="1" max="12" value={opts.servings} onChange={(e) => setOpts({ ...opts, servings: e.target.value })} />
            </label>
            <label className="f">
              Allergies
              <input type="text" maxLength={200} value={opts.allergies} onChange={(e) => setOpts({ ...opts, allergies: e.target.value })} placeholder="Peanuts, dairy" />
            </label>
          </div>
          <div style={{ marginTop: 12 }}>
            <Busy loading={suggest.loading} label="Finding recipes…">
              Suggest recipes
            </Busy>
          </div>
          <ErrorNote text={suggest.error} />
        </form>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 16, minWidth: 0 }}>
          <div className="card">
            {!r && <p className="muted">Recipes appear here.</p>}
            {r && (
              <>
                <div className="dayrow" role="tablist" aria-label="Recipes">
                  {recipes.map((x, i) => (
                    <button key={x.name} className="chip" aria-pressed={i === sel} onClick={() => { setSel(i); setChat([]); }}>
                      {x.name}
                    </button>
                  ))}
                </div>
                <div className="row between">
                  <h3 style={{ margin: 0 }}>{r.name}</h3>
                  <span className="row">
                    <Pill>{fmt(r.time_minutes)} min</Pill>
                    <Pill>{r.difficulty}</Pill>
                  </span>
                </div>
                <p className="muted small">
                  {r.cuisine} · serves {fmt(r.servings)} · {fmt(r.nutrition_per_serving.calories)} kcal and {fmt(r.nutrition_per_serving.protein_g)} g protein per serving
                </p>
                <h3>Ingredients</h3>
                <ul className="list small">
                  {r.ingredients.map((i, k) => (
                    <li key={k}>
                      <span>
                        {i.item} <span className="muted">{i.quantity}</span>
                      </span>
                      <Pill kind={i.have ? 'good' : 'warn'}>{i.have ? 'have' : 'need'}</Pill>
                    </li>
                  ))}
                </ul>
                <h3 style={{ marginTop: 14 }}>Steps</h3>
                <ol className="steps">
                  {r.steps.map((s, k) => (
                    <li key={k}>
                      <span>{s.text}</span>
                      <StepTimer minutes={s.minutes} />
                    </li>
                  ))}
                </ol>
                {r.safety_temp_c && <p className="note">Safe doneness: the thickest part must reach {fmt(r.safety_temp_c)} C. Use a probe thermometer.</p>}
                {r.tips.length > 0 && <p className="muted small">Tip: {r.tips.join(' ')}</p>}
              </>
            )}
          </div>

          <div className="card">
            <h3>Ask while you cook</h3>
            <div className="chat" aria-live="polite">
              {chat.length === 0 && <p className="muted small">Ask about substitutions, timing, or a fix: "the curry is too sour".</p>}
              {chat.map((m, i) => (
                <p key={i} className={`bubble ${m.role}`}>
                  {m.content}
                </p>
              ))}
            </div>
            <ErrorNote text={ask.error} />
            <form className="row" onSubmit={send} style={{ marginTop: 8 }}>
              <input type="text" className="grow" value={q} maxLength={600} onChange={(e) => setQ(e.target.value)} placeholder="Ask a cooking question" aria-label="Cooking question" />
              <VoiceInput onText={setQ} />
              <Busy loading={ask.loading} label="…">
                Send
              </Busy>
            </form>
          </div>
        </div>
      </div>
    </section>
  );
}
