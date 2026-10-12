const steps = [
  ["01", "Agent 规划", "梳理内容与结构"],
  ["02", "工作台编辑", "换主题、确认图与封面"],
  ["03", "预览与交付", "复制、导出或创建草稿"],
];

export function GettingStarted() {
  return (
    <section className="getting-started" aria-label="从规划到交付">
        <ol className="getting-started-steps">
          {steps.map(([number, title, description]) => (
            <li key={number}><span aria-hidden="true">{number}</span><h3>{title}</h3><p>{description}</p></li>
          ))}
        </ol>
        <div className="getting-started-notes">
          <p>想要自己的风格？给 Agent 参考图或描述，创作整套新主题，再到<a href="/theme-gallery">主题样本册</a>查看。</p>
          <p>宿主支持生图时，确认主题后可让它生成正文与封面候选。</p>
          <p>排版不用另配 Key；凭据仅在<a href="/settings">本地设置</a>填写，不自动群发。</p>
        </div>
    </section>
  );
}
