import styles from './ProfileBadge.module.css';

const PROFILES: Record<string, { label: string; className: string }> = {
  normal: { label : 'normal', className: styles.normal },
  yogun: { label: 'yoğun', className: styles.yogun },
  supheli: { label: 'şüpheli', className: styles.supheli },
};

// simülatör etiketi, sistemin tespiti değil
export function ProfileBadge({ profile }:{ profile?: string }) {
  const known = profile ? PROFILES[profile] : undefined;
  if (!known) return null;
  return (
    <span
      className={`${styles.badge} ${known.className}`}
      title="Simülatör etiketi: istemcinin gerçek profili, sistemin tespiti değil"
    >
      {known.label}
    </span>
  );
}