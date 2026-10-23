import React, { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react';
import { api } from './api.js';

export const Caps = createContext({ ai_configured: true, server_audio: false });

export function useTask() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const run = useCallback(async (fn) => {
    setLoading(true);
    setError('');
    try {
      return await fn();
    } catch (e) {
      setError(e.message || 'Something went wrong.');
      return null;
    } finally {
      setLoading(false);
    }
  }, []);
  return { loading, error, run, setError };
}

export function useObjectUrl(file) {
  const [url, setUrl] = useState('');
  useEffect(() => {
    if (!file) {
      setUrl('');
      return undefined;
    }
    const u = URL.createObjectURL(file);
    setUrl(u);
    return () => URL.revokeObjectURL(u);
  }, [file]);
  return url;
}

export const fmt = (n) => Math.round(Number(n) || 0);
export const f1 = (n) => (Math.round((Number(n) || 0) * 10) / 10).toFixed(1);

export function ErrorNote({ text }) {
  return text ? (
    <p className="error" role="alert">
      {text}
    </p>
  ) : null;
}

export function Pill({ kind = '', children }) {
  return <span className={`pill ${kind}`}>{children}</span>;
}

export function Bar({ value, max = 100, kind = '' }) {
  const pct = Math.max(2, Math.min(100, (value / max) * 100));
  return (
    <div className={`bar ${kind}`}>
      <i style={{ width: `${pct}%` }} />
    </div>
  );
}

export function Ring({ value, label, kind = '' }) {
  const v = Math.max(0, Math.min(100, value ?? 0));
  return (
    <div className={`ring ${kind}`} style={{ '--p': v }}>
      <div>
        <span>
          {value == null ? '–' : fmt(value)}
          <small>{label}</small>
        </span>
      </div>
    </div>
  );
}

export function Stat({ value, label }) {
  return (
    <div className="stat">
      <b>{value}</b>
      <span>{label}</span>
    </div>
  );
}

export function FilePick({ accept, multiple, onFiles, children, id }) {
  return (
    <>
      <label className="btn ghost sm" htmlFor={id}>
        {children}
      </label>
      <input
        id={id}
        type="file"
        accept={accept}
        multiple={multiple}
        hidden
        onChange={(e) => {
          const files = [...e.target.files];
          if (files.length) onFiles(files);
          e.target.value = '';
        }}
      />
    </>
  );
}

export function Busy({ loading, children, label }) {
  return (
    <button className="btn" type="submit" disabled={loading}>
      {loading ? label || 'Working…' : children}
    </button>
  );
}

/* Voice note: server-side Whisper when the backend has it, otherwise the browser's own speech recognition. */
export function VoiceInput({ onText, lang = 'en-IN' }) {
  const caps = useContext(Caps);
  const [state, setState] = useState('idle');
  const [err, setErr] = useState('');
  const rec = useRef(null);
  const SR = typeof window !== 'undefined' && (window.SpeechRecognition || window.webkitSpeechRecognition);
  const server = caps.server_audio && typeof MediaRecorder !== 'undefined';

  if (!server && !SR) return <span className="muted small">Voice input is not supported in this browser.</span>;

  async function start() {
    setErr('');
    try {
      if (server) {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        const mr = new MediaRecorder(stream);
        const chunks = [];
        mr.ondataavailable = (e) => chunks.push(e.data);
        mr.onstop = async () => {
          stream.getTracks().forEach((t) => t.stop());
          setState('working');
          try {
            const { text } = await api.transcribe(new Blob(chunks, { type: mr.mimeType || 'audio/webm' }));
            onText(text);
          } catch (e) {
            setErr(e.message);
          }
          setState('idle');
        };
        rec.current = mr;
        mr.start();
      } else {
        const r = new SR();
        r.lang = lang;
        r.interimResults = false;
        r.onresult = (e) => onText(e.results[0][0].transcript);
        r.onerror = (e) => setErr(e.error === 'not-allowed' ? 'Microphone permission was denied.' : 'Voice input failed. Try again.');
        r.onend = () => setState('idle');
        rec.current = r;
        r.start();
      }
      setState('listening');
    } catch {
      setErr('Microphone permission was denied.');
      setState('idle');
    }
  }

  function stop() {
    const r = rec.current;
    if (!r) return;
    if (server) r.stop();
    else r.stop();
  }

  return (
    <span className="voice">
      <button
        type="button"
        className={`btn ghost sm ${state === 'listening' ? 'live' : ''}`}
        onClick={state === 'listening' ? stop : start}
        disabled={state === 'working'}
        aria-pressed={state === 'listening'}
      >
        {state === 'listening' ? 'Stop recording' : state === 'working' ? 'Transcribing…' : 'Speak'}
      </button>
      {err && <span className="error small"> {err}</span>}
    </span>
  );
}

function beep() {
  try {
    const A = window.AudioContext || window.webkitAudioContext;
    const a = new A();
    const o = a.createOscillator();
    const g = a.createGain();
    o.connect(g);
    g.connect(a.destination);
    o.frequency.value = 880;
    g.gain.value = 0.15;
    o.start();
    setTimeout(() => {
      o.stop();
      a.close();
    }, 500);
  } catch {
    /* sound is optional */
  }
}

export function StepTimer({ minutes }) {
  const total = Math.round(minutes * 60);
  const [left, setLeft] = useState(null);
  useEffect(() => {
    if (left == null) return undefined;
    if (left <= 0) {
      beep();
      return undefined;
    }
    const t = setTimeout(() => setLeft((l) => l - 1), 1000);
    return () => clearTimeout(t);
  }, [left]);
  if (!minutes) return null;
  const show = left == null ? total : Math.max(0, left);
  const label = left != null && left <= 0 ? 'Done' : `${Math.floor(show / 60)}:${String(show % 60).padStart(2, '0')}`;
  return (
    <button type="button" className="btn ghost sm num" onClick={() => setLeft(left == null || left <= 0 ? total : null)}>
      {label}
    </button>
  );
}
