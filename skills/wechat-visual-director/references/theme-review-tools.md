# 主题复核工具

设计完成、需要生产渲染检查或局部复测时读取。评审标准见 [主题创作流程](theme-design-review.md)，交付状态见 [主题交付检查](theme-visual-checks.md)；这里仅维护命令与证据口径。

### 换文章复核，而不只看组件总览

支持 `theme review` 的核心可离线生成检查材料，无需启动服务或安装主题：

```powershell
& "{launcher}" theme review --file "<theme.json-or-vdtheme>" --output "<新的检查目录>" --image "<可安全使用的本地测试图片>" --reference-image "<实际查看的参考截图>" --json
```

`--reference-image` 可重复或省略；图片只在本地检查材料中使用，不进入主题包。命令采用正式渲染器生成 21 个角色的短文与长文（分隔线无长文，共 164 项），并另测带/不带原文编号的标题。`theme_review.v2` 从工作台共用的配置生成四组档位：

| 档位 | 视口宽度 | 正文净宽 | 用途 |
| --- | ---: | ---: | --- |
| mobile | 405px | 357px | 手机主验收 |
| proof | 648px | 600px | 校对主验收，同步工作台 1.06 倍内联字号调整 |
| narrow | 368px | 320px | 补充窄屏适配 |
| legacy | 438px | 390px | 历史净宽补充适配，不代表当前手机视口 |

每侧留白 24px；检查页的 `content_width` 与 `viewport_width` 分开记录，不能互换。输出 `index.html`、八个检查页及 `manifest.json`，遗漏角色会列出而非偷偷使用兜底冒充完成。输出目录必须是新的，保留修订前证据；工具生成成功不表示浏览器、审美或微信验收通过。纯继承主题不适用。

宿主已有 Python + Playwright 时，可选运行 `{baseDir}/scripts/check-theme-review.py --review <检查目录> --output <新的截图目录> [--browser <Chromium或Edge路径>] [--previous-output <上一轮截图目录>] [--article <正式渲染的正常文章HTML>]`。它逐项截图并输出 `browser-report.json`，检查越界、图片加载、长正文净宽，以及多行标题旁装饰列的无效空白；`narrow_text_review_count`、`title_sidecar_review_count` 和 `single_cjk_title_review_count` 是待复核提示，不是美观评分或一刀切禁令。字段记录实际 `rendered_lines`，末行单字不触发自动失败或标题改写。`visual-comparison.html` 汇集参考及相同档位、字号、角色的修前修后；`component-overview.html`、`component-overview-*.png` 将当前不同角色按阅读任务并排，保留手机主验收的 357px 净宽与自然高度。HTML 的灰度图只辅助观察，两种材料都不自动评判风格。

`--article` 在新检查中生成四个档位的全篇与首中尾截图、`article-browser-report.json`，记录来源 HTML 哈希、实际正文宽度、图像与字段换行；主验收优先看 mobile/proof，补充档位问题不能误报为工作台同样失效。它不改原稿、不安装主题或调用微信，也不自动证明给定 HTML 使用了当前主题：须核对正式渲染时的主题/渲染版本。正常文章未用到的角色仍由试样覆盖。修复标题时复核原稿所有同类标题，不为某一个标题硬插换行或调几像素；若仅在补充宽度出现末行单字，按阅读影响说明，不自动阻断或声称主尺寸有问题。

局部修订中可在当前版本新生成的检查材料上加 `--roles hero heading`（角色名按实际影响选择），只截图所选角色的长短文和全部档位；例如这两个角色为16项，而不是164项。报告增加 `check_scope`、`checked_roles`、`unchecked_roles`、`expected_case_count` 和 `full_bundle_case_count`；`geometry=pass` 仅针对本轮所选范围，局部报告的 `full_bundle_geometry=not_verified`，总览与对照页也标明局部。`missing_roles` 仍指布局声明缺失，不等于未截图角色；旧版未改角色的截图不会混入新版本通过报告。`--article` 仍检查整篇文章四档位，补看同类标题与周围节奏。全局令牌、共享绘图或渲染器修改需扩大范围；定版时省略 `--roles`，重跑当前版本的一次全量浏览器回归。参数试验不反复调用独立评审；选定修订版后再按创作流程做受影响范围复核。

已有截图时，运行 `{baseDir}/scripts/check-theme-review.py --review <匹配的检查目录> --reuse-report <已有截图目录/browser-report.json> --output <新的总览目录>`，只生成总览与 `component-overview.json`，不重测或改写旧报告。主题哈希、渲染器版本与预览配置须匹配；源图必须为档位声明的原生净宽，不能拉伸其他宽度。旧 `theme_review.v1` 的 390px 总览保留历史标注，不与新 mobile 档位直接作同尺度对照。无 Python + Playwright 时由宿主用已有检查页并排查看并记录范围，不要求普通用户安装开发环境。正常文章和参考仍须实际查看；`geometry=pass` 不表示视觉通过，旧核心或工具缺失时明确能力差异。

复用局部报告只能生成相同局部总览，不能与 `--roles` 合用重选范围，也不变成全主题验收。局部截图能力缺失时用对应HTML人工核对并记录范围，不为省成本漏掉定版全量检查。

生成材料后按主题交付检查完成逐角色与正常文章复核。`fixed_label_review` 只标出待查节点；固定标签的实际含义、设计感和阅读舒适度仍需要判断，不能从程序字段自动得出通过结论。
