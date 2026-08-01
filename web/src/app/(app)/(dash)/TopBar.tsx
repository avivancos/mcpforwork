import { Poll } from "@/components/Poll";
import { api } from "@/lib/api";
import { RefreshButton } from "./RefreshButton";
import styles from "./dash.module.css";

export async function TopBar({ title }: { title: string }) {
  const connection = await api.getConnection();
  return (
    <div className={styles.topBar}>
      <Poll seconds={60} />
      <div className={styles.topBarLeft}>
        <h1 className={styles.topBarTitle}>{title}</h1>
        {connection.connected && (
          <span className={`${styles.connChip} ${styles.connChipTop}`}>
            <span className="dot dot--ok" /> Connected · {connection.client}
          </span>
        )}
      </div>
      <div className={styles.topBarRight}>
        {/* -1 is the API's never-synced sentinel — say so, don't render it. */}
        <span>
          {connection.syncedMinAgo < 0
            ? "Never synced"
            : `Synced ${connection.syncedMinAgo} min ago`}
        </span>
        <RefreshButton />
      </div>
    </div>
  );
}
