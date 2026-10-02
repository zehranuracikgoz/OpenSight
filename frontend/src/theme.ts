export type Theme = 'light' | 'dark';

// index.html deki scriptle aynı anahtar
export const THEME_STORAGE_KEY = 'opensight-theme';

function isTheme(value: unknown): value is Theme {
  return value === 'light' || value === 'dark';
}

// kayıtlı seçim yoksa tarayıcı tercihi
export function resolveInitialTheme(): Theme {
  try {
    const stored = localStorage.getItem(THEME_STORAGE_KEY);
    if (isTheme(stored)) return stored;
  } catch {
    //localStorage kapalıysa sistem tercihi
  }
  const prefersDark = typeof window.matchMedia === 'function' && window.matchMedia('(prefers-color-scheme: dark)').matches;
  return prefersDark ? 'dark' : 'light';
}

export function applyTheme(theme: Theme): void {
  document.documentElement.setAttribute('data-theme' , theme);
}

export function saveTheme(theme: Theme): void {
  try {
    localStorage.setItem(THEME_STORAGE_KEY, theme);
  } catch {
    // kayıt olmasa da tema değişiyor
  }
}