export function InvestmentHeader({
  onNewTransaction,
  onNewAsset,
}: {
  onNewTransaction: () => void;
  onNewAsset: () => void;
}) {
  return (
    <header className="investment-topbar">
      <div>
        <div className="eyebrow">MANUAL · LOCAL · AUDITABLE</div>
        <h1>
          Jarvis <span>投资助手</span>
        </h1>
        <p>手动记录真实交易，保留原始理由，让每次复盘都能回到事实。</p>
      </div>
      <div className="investment-header-actions">
        <button className="ghost-button" onClick={onNewTransaction} type="button">
          记录交易
        </button>
        <button className="primary-button" onClick={onNewAsset} type="button">
          + 添加资产
        </button>
      </div>
    </header>
  );
}
