import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { ProfileBadge } from './ProfileBadge';

describe('ProfileBadge', () => {
  it.each([
    ['normal', 'normal'],
    ['yogun', 'yoğun'],
    ['supheli', 'şüpheli'],
  ])('%s profilini Türkçe etiketle gösteriyor', (profile, label) => {
    render(<ProfileBadge profile={profile} />);

    expect (screen.getByText(label)).toHaveAttribute('title' , expect.stringContaining('Simülatör etiketi'));
  });

  it('bilinmeyen ya da boş profilde hiçbir şey çizmiyor', () => {
    const { container } =render(
      <>
        <ProfileBadge />
        <ProfileBadge profile="baska" />
      </>,
    );
    expect(container).toBeEmptyDOMElement();
  });
});