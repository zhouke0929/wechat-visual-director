import { NextResponse } from "next/server";

const APPLICATION = "wechat_visual_director_workbench";

export const dynamic = "force-dynamic";

export function GET() {
  return NextResponse.json({
    status: "ok",
    application: APPLICATION,
    application_version:
      process.env.VISUAL_DIRECTOR_APPLICATION_VERSION ?? "development",
  });
}
