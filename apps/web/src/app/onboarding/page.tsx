import { OnboardingWizard } from "@/components/onboarding-wizard";
import { getProfile } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function OnboardingPage() {
  const profile = await getProfile().catch(() => null);
  return <OnboardingWizard initialProfile={profile} />;
}
