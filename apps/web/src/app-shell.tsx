import EditorialDeskPage from "@/app/page";
import BlindReviewPage from "@/app/blind-review/page";
import ComponentGalleryPage from "@/app/component-gallery/page";
import SettingsPage from "@/app/settings/page";
import TaskReviewPage from "@/app/tasks/[taskId]/page";
import ThemeGalleryPage from "@/app/theme-gallery/page";
import ThemeDetailPage from "@/app/theme-gallery/[themeId]/page";
import VariantReviewPage from "@/app/variant-review/page";
import Link, { usePathname } from "@/lib/router";

export default function AppShell() {
  const pathname = usePathname();
  if (pathname === "/") return <EditorialDeskPage />;
  if (pathname === "/settings") return <SettingsPage />;
  if (pathname === "/theme-gallery") return <ThemeGalleryPage />;
  if (/^\/theme-gallery\/[^/]+$/.test(pathname)) return <ThemeDetailPage />;
  if (/^\/tasks\/[^/]+$/.test(pathname)) return <TaskReviewPage />;
  if (pathname === "/blind-review") return <BlindReviewPage />;
  if (pathname === "/component-gallery") return <ComponentGalleryPage />;
  if (pathname === "/variant-review") return <VariantReviewPage />;
  return (
    <main className="desk-page">
      <section className="empty-state" style={{ margin: "12vh auto", maxWidth: 720 }}>
        <span>404</span>
        <h1>没有找到这个工作台页面</h1>
        <p>任务链接可能不完整，也可能已经被移动。</p>
        <Link className="primary-button" href="/">返回任务首页</Link>
      </section>
    </main>
  );
}
