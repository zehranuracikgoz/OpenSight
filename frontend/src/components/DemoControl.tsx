import { useCallback, useEffect, useRef, useState } from 'react';
import { checkApiAwake, getDemoStatus, startDemo } from '../api/client';
import type { DemoStatus } from '../api/types';
import styles from './DemoControl.module.css';

const FAST_POLL_MS = 3000;
const SLOW_POLL_MS = 15000;

const STATE_LABELS: Record<DemoStatus['state'], string> = {
  bosta: 'Canlı Demoyu Başlat',
  uyaniyor: 'Sistem uyanıyor (~1 dk)…',
  model_hazirlaniyor: 'Model hazırlanıyor…',
  calisiyor: 'Demo çalışıyor',
  bitti: 'Demo tamamlandı',
};

function formatRemaining(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, '0')}`;
}

// "Canlı Demoyu Başlat" kontrolü - API uykudaysa bildiriyor, /demo/status'u duruma göre hızlı/yavaş
// yokluyor; "bosta"/"bitti"'de yoklama duruyor ki demo bitince hiçbir şey servisleri uyanık tutmasın
export function DemoControl() {
  const [apiAwake, setApiAwake] = useState<boolean | null>(null);
  const [status, setStatus] = useState<DemoStatus | null>(null);
  const [starting, setStarting] = useState(false);
  const [startError, setStartError] = useState<string | null>(null);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const mountedRef = useRef(true);

  const poll = useCallback(async () => {
    try {
      const data = await getDemoStatus();
      if (!mountedRef.current) return;
      setStatus(data);
      if (data.state === 'calisiyor') {
        timeoutRef.current = setTimeout(poll, SLOW_POLL_MS);
      } else if (data.state === 'uyaniyor' || data.state === 'model_hazirlaniyor') {
        timeoutRef.current = setTimeout(poll, FAST_POLL_MS);
      }
    } catch {
      if (mountedRef.current) timeoutRef.current = setTimeout(poll, FAST_POLL_MS);
    }
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    checkApiAwake().then((awake) => {
      if (mountedRef.current) setApiAwake(awake);
    });
    poll();
    return () => {
      mountedRef.current = false;
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
    };
  }, [poll]);

  async function handleStart() {
    setStarting(true);
    setStartError(null);
    try {
      const data = await startDemo();
      setStatus(data);
      poll();
    } catch (err) {
      setStartError(err instanceof Error ? err.message : 'demo başlatılamadı');
    } finally {
      setStarting(false);
    }
  }

  const state = status?.state ?? 'bosta';
  const canStart = state === 'bosta' || state === 'bitti';

  return (
    <div className={styles.container}>
      {apiAwake === false && <span className={styles.waking}>Sistem uyanıyor (~1 dk)…</span>}
      {canStart ? (
        <button className={styles.button} onClick={handleStart} disabled={starting}>
          {starting ? 'Başlatılıyor…' : 'Canlı Demoyu Başlat'}
        </button>
      ) : (
        <span className={styles.statusText}>
          {STATE_LABELS[state]}
          {state === 'calisiyor' && status?.remaining_seconds != null && (
            <span className={styles.remaining}> – kalan süre: {formatRemaining(status.remaining_seconds)}</span>
          )}
        </span>
      )}
      {state === 'bitti' && <span className={styles.statusText}>{STATE_LABELS.bitti}</span>}
      {(startError ?? status?.error) && <span className={styles.error}>{startError ?? status?.error}</span>}
    </div>
  );
}
