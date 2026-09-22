import type { ReactNode } from 'react';
import { NavLink } from 'react-router-dom';
import styles from './Layout.module.css';

interface LayoutProps {
  children: ReactNode;
}

function DashboardIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <rect x="3" y="3" width="7" height="9" rx="1" />
      <rect x="14" y="3" width="7" height="5" rx="1" />
      <rect x="14" y="12" width="7" height="9" rx="1" />
      <rect x="3" y="16" width="7" height="5" rx="1" />
    </svg>
  );
}

function SettingsIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
      <line x1="4" y1="6" x2="20" y2="6" />
      <circle cx="14" cy="6" r="2" fill="currentColor" stroke="none" />
      <line x1="4" y1="12" x2="20" y2="12" />
      <circle cx="8" cy="12" r="2" fill="currentColor" stroke="none" />
      <line x1="4" y1="18" x2="20" y2="18" />
      <circle cx="16" cy="18" r="2" fill="currentColor" stroke="none" />
    </svg>
  );
}

// sol sidebar navigasyonu + üstte ince bir başlık çubuğu - zaman filtresi/servis durumu
// dashboard'a özgü olduğu için burada değil Dashboard.tsx'in kendi araç çubuğunda
export function Layout({ children }: LayoutProps) {
  const environment = import.meta.env.MODE;

  return (
    <div className={styles.shell}>
      <aside className={styles.sidebar}>
        <div className={styles.brand}>OpenSight</div>
        <nav className={styles.nav}>
          <NavLink
            to="/"
            end
            className={({ isActive }) => `${styles.navLink} ${isActive ? styles.navLinkActive : ''}`}
          >
            <DashboardIcon />
            <span>Dashboard</span>
          </NavLink>
          <NavLink
            to="/settings"
            className={({ isActive }) => `${styles.navLink} ${isActive ? styles.navLinkActive : ''}`}
          >
            <SettingsIcon />
            <span>Ayarlar</span>
          </NavLink>
        </nav>
      </aside>
      <div className={styles.mainArea}>
        <header className={styles.topBar}>
          <span className={styles.scope}>api-gateway/eu-west-1</span>
          <span className={styles.envBadge}>{environment.toUpperCase()}</span>
        </header>
        <main className={styles.content}>{children}</main>
      </div>
    </div>
  );
}