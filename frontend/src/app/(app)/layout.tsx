import { DemoBanner } from "@/features/demo/demo-banner";
import { AppShell } from "@/features/shell/app-shell";

export default function AppLayout({ children }: LayoutProps<"/">) {
  return (
    <AppShell>
      <DemoBanner />
      {children}
    </AppShell>
  );
}
