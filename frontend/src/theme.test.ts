import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { applyTheme, resolveInitialTheme, saveTheme, THEME_STORAGE_KEY } from './theme';

function mockSystemTheme(dark: boolean) {
  vi.stubGlobal('matchMedia',(query: string) => ({ matches: dark && query.includes('dark'), media: query }));
}

beforeEach(() => {
  localStorage.clear();
  document.documentElement.removeAttribute('data-theme');
});


afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('theme', () => {
  it('kayıt yoksa tarayıcının koyu tercihini kullanıyor', () => {
    mockSystemTheme(true);

    expect(resolveInitialTheme()).toBe('dark');
  });

  it('kayıt yoksa ve tarayıcı koyu istemiyorsa açık tema', () => {
    mockSystemTheme(false);

    expect(resolveInitialTheme()).toBe('light');
  });

  it('kullanıcının  kayıtlı seçimi sistem tercihinden önce geliyor', () => {
    mockSystemTheme (true);
    localStorage.setItem(THEME_STORAGE_KEY, 'light');

    expect(resolveInitialTheme()).toBe('light');
  });

  it('geçersiz kayıtlı değeri yok sayıp sistem tercihine düşüyor', () => {
    mockSystemTheme(true);
    localStorage.setItem(THEME_STORAGE_KEY, 'mor');

    expect(resolveInitialTheme()).toBe('dark');
  });

  it('localStorage okunamazsa sistem tercihine düşüyor', () => {
    mockSystemTheme(true);
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('erişim engelli');
    });

    expect(resolveInitialTheme()).toBe('dark');
  });

  it('localStorage yazılamazsa saveTheme hata fırlatmıyor', () => {
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('kota dolu');
    });

    expect(() => saveTheme('dark')).not.toThrow();
  });


  it('applyTheme data-theme özniteliğini ayarlıyor', () => {
    applyTheme('dark');

    expect(document.documentElement.getAttribute('data-theme')).toBe('dark');
  });

});