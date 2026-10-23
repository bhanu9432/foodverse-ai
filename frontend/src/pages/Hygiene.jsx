import React, { useState } from 'react';
import { api } from '../api.js';
import { Busy, ErrorNote, FilePick, Pill, Ring, useObjectUrl, useTask } from '../components.jsx';

const STATUS = {
  compliant: ['good', 'Compliant'],
  violation: ['bad', 'Violation'],
  not_visible: ['', 'Not visible'],
};

export default function Hygiene() {
  const [video, setVideo] = useState(null);
  const [images, setImages] = useState([]);
  const [note, setNote] = useState('');
  const [res, setRes] = useState(null);
  const url = useObjectUrl(video);
  const task = useTask();

  async function submit(e) {
    e.preventDefault();
    if (!video && !images.length) {
      task.setError('Choose a kitchen video or up to 8 photos.');
      return;
    }
    const fd = new FormData();
    if (video) fd.append('video', video);
    images.slice(0, 8).forEach((f) => fd.append('images', f));
    fd.append('note', note);
    const out = await task.run(() => api.analyzeHygiene(fd));
    if (out) setRes(out);
  }

  const kind = res ? (res.grade === 'Good' ? 'good' : res.grade === 'Fair' ? 'warn' : 'bad') : '';

  return (
    <section>
      <h2>Kitchen Hygiene</h2>
      <p className="lede">
        Upload a short kitchen video. Eight frames are sampled and checked for gloves, hair caps, food handling and cleanliness.
        Anything the camera cannot see is marked Not visible, not guessed.
      </p>
      <div className="grid">
        <form className="card" onSubmit={submit}>
          <h3>Footage</h3>
          <div className="drop">
            {url ? <video className="pv" src={url} controls muted /> : <div className="pv empty">No video yet</div>}
            <div className="row">
              <FilePick id="hyg-video" accept="video/mp4,video/webm,video/quicktime" onFiles={(f) => setVideo(f[0])}>
                {video ? 'Change video' : 'Choose video'}
              </FilePick>
              <FilePick id="hyg-images" accept="image/*" multiple onFiles={(f) => setImages(f.slice(0, 8))}>
                Or add photos
              </FilePick>
            </div>
            <span className="muted small">
              {video ? video.name : 'MP4, WebM or MOV up to 60 MB.'} {images.length ? `${images.length} photo(s) added.` : ''}
            </span>
          </div>
          <label className="f" style={{ marginTop: 14 }}>
            Context (optional)
            <input type="text" value={note} maxLength={400} onChange={(e) => setNote(e.target.value)} placeholder="Salad prep station, evening shift" />
          </label>
          <div style={{ marginTop: 12 }}>
            <Busy loading={task.loading} label="Analysing footage…">
              Run hygiene check
            </Busy>
          </div>
          <ErrorNote text={task.error} />
          <p className="note">
            Only the sampled frames are sent to the AI service. The video is deleted from the server right after frames are taken. Get
            consent from staff before recording.
          </p>
        </form>

        <div className="card">
          {!res && <p className="muted">Results appear here.</p>}
          {res && (
            <>
              <div className="row" style={{ gap: 18 }}>
                <Ring value={res.score} label="of 100" kind={kind} />
                <div className="grow">
                  <Pill kind={kind}>{res.grade}</Pill>
                  <p className="small muted" style={{ margin: '8px 0 0' }}>
                    {res.frames_analysed} frames analysed
                  </p>
                </div>
              </div>
              {res.summary && <p>{res.summary}</p>}
              <div className="tablew">
                <table>
                  <thead>
                    <tr>
                      <th>Indicator</th>
                      <th>Status</th>
                      <th>Evidence</th>
                    </tr>
                  </thead>
                  <tbody>
                    {res.indicators.map((i) => (
                      <tr key={i.key}>
                        <td>{i.label}</td>
                        <td>
                          <Pill kind={STATUS[i.status][0]}>{STATUS[i.status][1]}</Pill>
                        </td>
                        <td className="small">
                          {i.evidence || '–'}
                          {i.frames.length > 0 && <span className="muted"> (frames {i.frames.join(', ')})</span>}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {res.recommendations.length > 0 && (
                <>
                  <h3 style={{ marginTop: 16 }}>Fix first</h3>
                  <ol className="plain">
                    {res.recommendations.map((r, k) => (
                      <li key={k}>{r}</li>
                    ))}
                  </ol>
                </>
              )}
            </>
          )}
        </div>
      </div>
    </section>
  );
}
