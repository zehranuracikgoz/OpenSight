import type { ReactNode } from 'react';
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
        <span className={styles.envBadge}>{environment}</span>
      </header>
      <main className={styles.content}>{children}</main>
    </div>
  );
}