import { ArrowUpRight, CircleDot } from "lucide-react";
import Link from "next/link";

import type { NewsItem } from "@/lib/api";

const categoryLabels: Record<NewsItem["category"], string> = {
  ai: "AI",
  career: "职业",
  technology: "科技",
  english: "英语",
  investment: "投资",
  international: "国际",
};

function relationship(item: NewsItem) {
  if (item.portfolio_related) return "与你的持仓直接相关";
  if (item.investment_related) return "与你关注的投资主题相关";
  return `与你的${categoryLabels[item.category]}关注相关`;
}

export function IntelligenceCard({
  featured = false,
  item,
}: {
  featured?: boolean;
  item: NewsItem;
}) {
  return (
    <article
      className={`cc-intelligence-card ${
        featured ? "cc-intelligence-featured" : ""
      }`}
    >
      <div className="cc-intelligence-meta">
        <span>{categoryLabels[item.category]}</span>
        <small>{item.source_name}</small>
      </div>
      <h3>{item.title}</h3>
      <div className="cc-intelligence-impact">
        <span>影响</span>
        <p>{item.analysis_text || item.summary || item.source_excerpt}</p>
      </div>
      <div className="cc-intelligence-relation">
        <CircleDot aria-hidden="true" />
        <span>{relationship(item)}</span>
      </div>
      <div className="cc-intelligence-action">
        <div>
          <span>建议行动</span>
          <p>{item.suggestion_text || "打开情报中心查看完整背景与行动建议。"}</p>
        </div>
        <Link aria-label="打开情报中心" href="/intelligence">
          <ArrowUpRight aria-hidden="true" />
        </Link>
      </div>
    </article>
  );
}
