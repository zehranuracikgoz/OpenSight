import type { ReactNode } from 'react';
import { NavLink } from 'react-router-dom';
import styles from './Layout.module.css';

interface LayoutProps {
  children: ReactNode;
}

export function Layout({ children }: LayoutProps) {
  const environment =import.meta.env.MODE;

  return (
    <div>
      <header className={styles.topBar}>
        <h1 className={styles.title}>OpenSight</h1>
        <nav className={styles.nav}>
          <NavLink
            to="/"
            end
            className={({ isActive })=> `${styles.navLink} ${isActive ? styles.navLinkActive : ''}`}
          >
            Dashboard
          </NavLink>
          <NavLink
            to="/settings"
            className = {({ isActive }) => `${styles.navLink} ${isActive ? styles.navLinkActive : ''}`}
          >
            Ayarlar
          </NavLink>
        </nav>
        <span className={styles.envBadge}>{environment}</span>
      </header>
      <main className={styles.content}>{children}</main>
    </div>
  );
}