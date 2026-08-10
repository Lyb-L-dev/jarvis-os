import { ShieldCheck } from "lucide-react";

import { ApprovalCenter } from "@/components/approval-center";
import styles from "@/components/v3-convergence.module.css";

export default function ApprovalsPage() {
  return (
    <main className={`dashboard approval-page ${styles.approvalInbox}`}>
      <header className={styles.approvalLead}>
        <div>
          <h1>决定收件箱</h1>
          <p>所有授权都有明确范围、到期时间和下一步。</p>
        </div>
        <div className={styles.safetyPromise}>
          <ShieldCheck aria-hidden="true" />
          <span>
            <strong>你始终拥有最后决定权</strong>
            <small>批准不等于执行</small>
          </span>
        </div>
      </header>
      <ApprovalCenter />
    </main>
  );
}
