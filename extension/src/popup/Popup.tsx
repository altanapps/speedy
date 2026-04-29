import { useEffect, useState } from 'react';

const BACKEND_URL = 'http://localhost:8000';

type Health = 'checking' | 'ok' | 'unreachable';

export function Popup() {
  const [health, setHealth] = useState<Health>('checking');

  useEffect(() => {
    let cancelled = false;
    fetch(`${BACKEND_URL}/health`, { signal: AbortSignal.timeout(2000) })
      .then((r) => (r.ok ? 'ok' : 'unreachable'))
      .catch(() => 'unreachable' as const)
      .then((s) => {
        if (!cancelled) setHealth(s);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="popup">
      <header>
        <h1>Speedy</h1>
        <span className="version">v0.1.0</span>
      </header>
      <p className="tagline">Trade where you read.</p>
      <dl className="status">
        <dt>Backend</dt>
        <dd className={`status-${health}`}>
          {health === 'checking' ? '…' : health === 'ok' ? 'reachable' : 'unreachable'}
        </dd>
        <dt>URL</dt>
        <dd className="mono">{BACKEND_URL}</dd>
      </dl>
      {health === 'unreachable' && (
        <p className="hint">
          Start the backend with <code>make serve</code> in <code>backend/</code>.
        </p>
      )}
    </div>
  );
}
