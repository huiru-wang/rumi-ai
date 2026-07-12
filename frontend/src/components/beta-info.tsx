"use client";

import { Info } from "lucide-react";

const BETA_NOTICE =
  "当前产品处于 Beta 测试阶段，用户数据可能随版本更新被清理。重要产出请及时下载保存。";

export function BetaInfo() {
  return (
    <div className="group relative flex shrink-0">
      <button
        type="button"
        aria-label="查看 Beta 数据说明"
        className="rounded-full p-0.5 text-muted-foreground transition-colors hover:text-foreground focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <Info size={14} />
      </button>
      <div
        role="tooltip"
        className="pointer-events-none absolute left-1/2 top-full z-50 mt-2 hidden w-72 -translate-x-1/2 rounded-md border border-border bg-background px-3 py-2 text-[11px] font-normal leading-relaxed text-foreground shadow-xl group-hover:block group-focus-within:block"
      >
        {BETA_NOTICE}
      </div>
    </div>
  );
}
