import { useEffect, useState } from 'react';
import { applyTheme, resolveInitialTheme, saveTheme, type Theme } from '../theme';
import styles from './ThemeToggle.module.css';

function currentTheme(): Theme {
  const attr = document.documentElement.getAttribute('data-theme');
  return attr === 'light' || attr === 'dark' ? attr : resolveInitialTheme();
}

function MoonIcon() {
  return(
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8Z" />
    </svg>
  );
}

function SunIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
      <circle cx="12" cy="12" r="4" />
      <path d ="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
    </svg>
  );
}

// ay/güneş anahtarı, seçimi localStoragea yazıyor
export function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>(currentTheme);

  useEffect(() => {
    applyTheme(theme);
  }, [theme]);

  function handleToggle() {
    const next: Theme = theme === 'dark' ? 'light' : 'dark';
    setTheme(next) ;
    saveTheme(next);
  }

  return (
    <button
      type="button"
      className={styles.toggle}
      onClick={handleToggle}
      aria-label={theme === 'dark' ? 'Açık temaya geç' : 'Koyu temaya geç'}
      title={theme === 'dark' ? 'Açık tema' : 'Koyu tema'}
    >
      {theme === 'dark' ? <SunIcon /> : <MoonIcon />}
    </button>
  );

}