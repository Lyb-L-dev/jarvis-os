import type { InvestmentOverview } from "@/lib/api";

export function InvestmentStats({
  overview,
}: {
  overview: InvestmentOverview | null;
}) {
  return (
    <section className="investment-stats">
      <article>
        <span>当前持仓</span>
        <strong>{overview?.active_positions ?? 0}</strong>
        <small>{overview?.asset_count ?? 0} 个资产档案</small>
      </article>
      <article>
        <span>交易记录</span>
        <strong>{overview?.transaction_count ?? 0}</strong>
        <small>可修改并从头重算</small>
      </article>
      <article>
        <span>当前投资理由</span>
        <strong>{overview?.current_theses ?? 0}</strong>
        <small>保留历史版本</small>
      </article>
      <article>
        <span>关联情报</span>
        <strong>{overview?.linked_news ?? 0}</strong>
        <small>只用于研究与复盘</small>
      </article>
    </section>
  );
}
