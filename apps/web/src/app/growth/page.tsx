import dynamic from "next/dynamic";

import { GrowthCenter } from "@/components/growth-center";
import { Reveal } from "@/components/motion/Reveal";

const GrowthCharts = dynamic(
  () => import("@/components/charts/GrowthCharts").then((m) => m.GrowthCharts),
  { loading: () => null },
);

export default function GrowthPage() {
  return (
    <Reveal>
      <GrowthCenter />
      <GrowthCharts />
    </Reveal>
  );
}
