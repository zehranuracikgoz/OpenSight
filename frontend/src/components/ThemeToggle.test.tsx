import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { THEME_STORAGE_KEY } from '../theme';
import { ThemeToggle } from './ThemeToggle' ;

beforeEach(() => {
  localStorage.clear();
  document.documentElement.setAttribute('data-theme', 'light');
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('ThemeToggle', () => {
  it('açık temadayken koyu temaya geçiş etiketini gösteriyor', () => {
    render(<ThemeToggle />);

    expect(screen.getByRole('button', { name: 'Koyu temaya geç' })).toBeInTheDocument();
  });

  it('tıklayınca temayı değiştirip seçimi kaydediyor', async () => {
    render(<ThemeToggle />);

    await userEvent.click(screen.getByRole('button', { name: 'Koyu temaya geç' }));

    expect(document.documentElement.getAttribute('data-theme')).toBe('dark');
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe('dark');
    expect(screen.getByRole('button', { name: 'Açık temaya geç' })).toBeInTheDocument();
  });

  it('tekrar tıklayınca açık temaya dönüyor',async () => {
    render(<ThemeToggle />);

    await userEvent.click(screen.getByRole('button', { name: 'Koyu temaya geç' }));
    await userEvent.click(screen.getByRole('button', { name: 'Açık temaya geç' }));

    expect(document.documentElement.getAttribute('data-theme')).toBe('light');
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe('light');
  });

  it('sayfa koyu tema ile açılmışsa (inline script) koyuyla başlıyor', () => {
    document.documentElement.setAttribute('data-theme', 'dark');
    render(<ThemeToggle />);

    expect(screen.getByRole('button', { name: 'Açık temaya geç' })).toBeInTheDocument();
  });

  it('localStorage yazılamasa bile tema değişiyor', async () => {
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(()=> {
      throw new Error('kota dolu');
    });
    render(<ThemeToggle />);

    await userEvent.click(screen.getByRole('button', { name: 'Koyu temaya geç' }));

    expect(document.documentElement.getAttribute('data-theme')).toBe('dark');
  });

});