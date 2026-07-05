export const PPT_STYLE_CATEGORIES = [
  {
    id: "academic",
    label: "学术科研",
    description: "论文汇报、课题答辩、研究综述",
  },
  {
    id: "business",
    label: "商业汇报",
    description: "战略汇报、经营分析、项目复盘",
  },
  {
    id: "product",
    label: "产品方案",
    description: "产品介绍、功能发布、竞品分析",
  },
  {
    id: "report",
    label: "日报周报",
    description: "工作周报、阶段总结、团队同步",
  },
  {
    id: "data",
    label: "数据分析",
    description: "指标看板、数据洞察、增长分析",
  },
  {
    id: "creative",
    label: "创意展示",
    description: "品牌视觉、作品集、发布会展示",
  },
  {
    id: "custom",
    label: "我的模板",
    description: "通过 PPTX 风格提取保存的模板",
  },
] as const;

export type PptStyleCategoryId = (typeof PPT_STYLE_CATEGORIES)[number]["id"];

type StyleWithCategory = {
  category: string;
};

export function normalizePptStyleCategory(category: string): PptStyleCategoryId {
  return PPT_STYLE_CATEGORIES.some((item) => item.id === category)
    ? (category as PptStyleCategoryId)
    : "custom";
}

export function getPptStyleCategoryGroups<T extends StyleWithCategory>(styles: T[]) {
  return PPT_STYLE_CATEGORIES.map((category) => ({
    ...category,
    styles: styles.filter(
      (style) => normalizePptStyleCategory(style.category) === category.id,
    ),
  }));
}
