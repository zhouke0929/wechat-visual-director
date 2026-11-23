# 渲染器维护：改一个组件，应该从哪里改？

本文描述开发分支的组件接入，不是 v1 主题包协议，也不代表已经上线。14 项基础角色和 12 类语义组件是**内容**的分类；26 套官方主题是同一份内容的不同**外观**。

```text
已解析文章 + 已保存的排版计划（切换外观不重新做 AI 规划）
   ├─ 标题、正文、原图等 → FoundationRenderer：基础角色与原文位置
   └─ 步骤、前后对照等   → SemanticSource：计划字段与原文位置
                        ↓
         用同一份字段 + 阅读规则绘制所选主题
            原生样式 / Python 套件 / 声明式 JSON
                        ↓
           正文 HTML（保留编辑定位及图片占位）
              工作台预览 / 样张 / 冻结与交付
```

| 想改什么 | 修改入口 | 边界 |
| --- | --- | --- |
| 普通内容属于哪个角色 | `foundation_content.bind_foundation_block` | 顶部标题、品牌页尾是文章级输入，不依赖某个 Markdown 段落。分隔线没有文本角色。 |
| 一个基础角色如何画 | `foundation_renderer` 的分派及对应的 `foundation_*` 模块 | 复用其文本角色，不按主题在文章主循环里开分支。 |
| 语义组件引用哪段原文、哪一项、传给外观什么字段 | `semantic_content.SemanticSource`、`BoundSemanticContent` | 不从渲染后的 HTML 猜标题，不让单独的主题再查文章。新增语义类型还应登记规划/校验协议、默认外观和样张；渲染器内部注册并不会自动扩大旧 v1 包的公开能力。 |
| 正文字号、字重、行距、字距 | `reading_rules` 的阅读角色、`reading_theme_overrides` 的受限覆盖 | 普通来源文字与装饰标签分开；只有拥有实际文本容器的布局才调整其内外间距，不能在每处文字外强加边框或间距。暂不提供用户设置界面。 |
| 卡片上下或左右、表格外观、图框装饰 | 相应的主题配方或受控布局节点 | “共用内容规则”不等于把时间线、表格等做成一种外形。复制、API 不单独设计第二套组件。 |
| 图片确定后才展示的原稿图注 | `foundation_media` 快照 → `image_caption_render` → `publication` | 只记录明确覆盖的有限数值；无覆盖不新增属性。装配旧占位时不去查询今天的主题设置。 |

**兼容策略。** 所有组件（包括无序列表、有序列表、逻辑路径）的默认视觉基线都是已发布的 v1.0.0。接入统一接口、开启编辑定位，都不构成改字号、字重或间距的理由。阅读配置里的参考值不是要覆盖主题的 CSS；只有显式声明的属性才覆盖，其余沿用主题自己的配方。分层显示标题和说明也是单独的可选能力。静态装饰、没有独立文本容器的几何间距，不属于一个“改全站所有元素”的接口。

**验收方法。** `apps/api/tests/test_renderer_catalog_parity.py` 以 v1.0.0 发布提交 `10e5661` 为视觉基准，不使用试点结果替发布版作证。固定输入和计划，对照三种开关状态下每套主题的 26 项样张和整篇；编辑锚点不参与样式比对，其功能单独验证。另用 `renderer_mobile_probe.py` 比较真实 Chromium 手机尺寸下的整篇像素。改渲染配方与改输入解析、规划不是一回事：解析或选出的组件不同，不能把最终文章差异一概归咎于 CSS。除外观外还需验证临时阅读覆盖能到达目标文字，以及改稿、冻结、素材装配和各交付路径。

在仓库根目录使用项目 Python 环境执行：

```console
python -m pytest apps/api/tests/test_renderer_catalog_parity.py apps/api/tests/test_foundation_contract.py apps/api/tests/test_semantic_content_contract.py apps/api/tests/test_authored_reading.py
python apps/api/tests/renderer_mobile_probe.py
python apps/api/tests/render_catalog_review.py
```

第二条需要本机有 Chromium 和基线提交；第三条生成可离线打开的 `artifacts/render-component-contracts-review/index.html`，不更新官网。做可编辑工作台的浏览器验收时，`VISUAL_DIRECTOR_WEB_DIST` 必须指向与源码配套的前端构建，并启用 `WVD_REQUIRE_PILOT_BROWSER=1`、`WVD_REQUIRE_LIST_PILOT_BROWSER=1`，不能以缺少浏览器时的跳过作为通过。

### 三种实际改法

1. **只调一个组件，不改整套主题。** 例如只改折扇时间线第一段正文的字号和整组的外距，在 `official_component_recipes.OFFICIAL_COMPONENT_RECIPES` 登记下面这项即可。它不改第二段、字重、行高比例或卡片内边距；相邻块最终的可见间距仍遵循浏览器的外边距折叠规则。这里的 left/right 是内容字段（之前/之后），即使纵排也不交换。正式配置为空，以下数字只用于验收。

   ```python
   {"folded_fan_detail": {"before_after_timeline": {
       "field_sizes_px": {"left": 19.5}, "outer_before_px": 13, "outer_after_px": 31,
   }}}
   ```

2. **只换现有构图，不改原文绑定。** 在同一项加 `"layout": "split_page_flip"` 表示左右翻页，`"stacked_before_after"` 表示上下对照。不填则保留原主题画法。它们复用同一份时间线实现，而不是让三个后端分别重画。维护者只指定布局；系统在选择主题时记录该组件的默认变体，若稿件用的是其他变体，不用主题默认布局把它盖回去。

3. **改步骤如何分层，不在每套主题里猜一遍。** 逻辑路径在绑定原文时通过 `interpret_step` 一次得到原文和可选的标题/说明，外观层只决定如何显示。区分“真的有步骤标题”“正文里有强调”“只有一句正文”；无标题不补造，单纯加粗也不自动另起一行。可编辑锚点与标题分层是两项能力。

**选择范围。** 要改一个主题的一类文字角色（例如所有普通列表项）用 `reading_theme_overrides`，要改一个组件的某个字段才用组件配方。两者都是在选择主题时拷入排版计划，之后重放该计划不读取最新登记表；选择另一个主题时使用新主题的配置。继承官方主题的普通 v1 扩展包不会暗中继承这两张私有登记表。组件级配置目前仅登记时间线的两个实际文字字段、外距和上述两种布局，不是任意组件通用 CSS。要支持一个新组件，先确定它的真实字段和外层容器，再登记、验证。

维护演练（不修改主题配置或创建工作台任务）：

```console
python -m pytest apps/api/tests/test_component_spacing_contract.py apps/api/tests/test_timeline_recipe_contract.py apps/api/tests/test_official_recipe_snapshot.py apps/api/tests/test_official_step_hierarchy.py
python apps/api/tests/test_timeline_recipe_contract.py
```

第二条需项目 Python 导入路径含 `apps/api/src`、本机已安装 Playwright Chromium；实际检查两种手机宽度的方向、长文换行与横向溢出，不只是对照 HTML 字符串。
