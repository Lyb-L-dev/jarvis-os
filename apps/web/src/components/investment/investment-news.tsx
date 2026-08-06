import type {
  InvestmentAsset,
  RelatedInvestmentNews,
} from "@/lib/api";

export function InvestmentNews({
  assets,
  news,
  newsAssetId,
  busy,
  onAssetChange,
  onToggle,
}: {
  assets: InvestmentAsset[];
  news: RelatedInvestmentNews[];
  newsAssetId: string;
  busy: boolean;
  onAssetChange: (assetId: string) => void;
  onToggle: (item: RelatedInvestmentNews) => void;
}) {
  return (
    <section className="investment-section">
      <div className="investment-section-head news-section-head">
        <div>
          <div className="eyebrow">INTELLIGENCE LINK</div>
          <h2>资产与情报关联</h2>
        </div>
        <label>
          查看资产
          <select
            onChange={(event) => onAssetChange(event.target.value)}
            value={newsAssetId}
          >
            {assets.map((asset) => (
              <option key={asset.id} value={asset.id}>
                {asset.name} · {asset.symbol}
              </option>
            ))}
          </select>
        </label>
      </div>
      {!assets.length ? (
        <div className="investment-empty compact">
          <strong>请先添加资产</strong>
          <p>有了资产后，才能把相关情报纳入投资复盘。</p>
        </div>
      ) : news.length === 0 ? (
        <div className="investment-empty compact">
          <strong>还没有可关联的投资情报</strong>
          <p>情报中心出现投资类内容后，会在这里显示候选项。</p>
        </div>
      ) : (
        <div className="investment-news-list">
          {news.map((item) => (
            <article className={item.linked ? "linked" : ""} key={item.id}>
              <div>
                <span>
                  {item.source_name} ·{" "}
                  {item.published_at
                    ? new Date(item.published_at).toLocaleDateString("zh-CN")
                    : "日期未知"}
                </span>
                <h3>{item.title}</h3>
                <p>{item.summary}</p>
                {item.relationship_note ? (
                  <small>关联说明：{item.relationship_note}</small>
                ) : null}
              </div>
              <div>
                <a href={item.url} rel="noreferrer" target="_blank">
                  查看来源
                </a>
                <button
                  className={item.linked ? "linked-button" : ""}
                  disabled={busy}
                  onClick={() => void onToggle(item)}
                  type="button"
                >
                  {item.linked ? "✓ 已关联" : "+ 关联资产"}
                </button>
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
