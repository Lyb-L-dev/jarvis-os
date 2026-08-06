import dynamic from "next/dynamic";

import { InvestmentCenter } from "@/components/investment-center";
import { Reveal } from "@/components/motion/Reveal";

const InvestmentCharts = dynamic(
  () =>
    import("@/components/charts/InvestmentCharts").then(
      (m) => m.InvestmentCharts,
    ),
  { loading: () => null },
);

export default function InvestmentPage() {
  return (
    <Reveal>
      <InvestmentCenter />
      <InvestmentCharts />
    </Reveal>
  );
}
