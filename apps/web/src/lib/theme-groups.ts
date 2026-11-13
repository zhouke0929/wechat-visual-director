type ThemeGroupMetadata = {
  theme_group?: string;
  theme_group_order?: number;
};

export function themeGroupLabel(theme: ThemeGroupMetadata) {
  return theme.theme_group || "未分组";
}

export function groupThemes<T extends ThemeGroupMetadata>(themes: readonly T[]) {
  const groups = new Map<string, { label: string; order: number; options: T[] }>();
  for (const theme of themes) {
    const label = themeGroupLabel(theme);
    const order = theme.theme_group_order ?? Number.MAX_SAFE_INTEGER;
    const group = groups.get(label);
    if (group) {
      group.order = Math.min(group.order, order);
      group.options.push(theme);
    } else {
      groups.set(label, { label, order, options: [theme] });
    }
  }
  return [...groups.values()].sort((a, b) => a.order - b.order || a.label.localeCompare(b.label, "zh-CN"));
}
