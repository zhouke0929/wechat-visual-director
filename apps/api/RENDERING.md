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

**兼容策略。** 列表和逻辑路径保留原有试点的完整阅读规则；其他已有配方默认保留各自的有效样式，仅在维护者显式声明角色覆盖时采用新的值。结构接入、启用阅读规则、对外正式切换是三件事。不要通过更改全局默认值、启用所有开关或修改官网导出文件来掩盖迁移差异。静态装饰、某些没有独立文本容器的几何间距，不属于一个“改全站所有元素”的接口。

**验收方法。** `apps/api/tests/test_renderer_catalog_parity.py` 使用固定旧提交 `ab9e481` 的归档作为期望，而非用候选代码覆盖期望；对照三种开关状态下每套主题的 26 项样张和整篇。另用 `renderer_mobile_probe.py` 比较真实 Chromium 手机尺寸下的整篇像素。有意的视觉更新应该独立评审并留下新基线依据。结构比对之外，还要验证临时阅读覆盖确实能改到目标原文字段、不会改动装饰，以及工作台改稿、冻结、素材装配和各交付路径；离线通过不替代微信实测。

在仓库根目录使用项目 Python 环境执行：

```console
python -m pytest apps/api/tests/test_renderer_catalog_parity.py apps/api/tests/test_foundation_contract.py apps/api/tests/test_semantic_content_contract.py apps/api/tests/test_authored_reading.py
python apps/api/tests/renderer_mobile_probe.py
python apps/api/tests/render_catalog_review.py
```

第二条需要本机有 Chromium 和基线提交；第三条生成可离线打开的 `artifacts/render-component-contracts-review/index.html`，不更新官网。做可编辑工作台的浏览器验收时，`VISUAL_DIRECTOR_WEB_DIST` 必须指向与源码配套的前端构建，并启用 `WVD_REQUIRE_PILOT_BROWSER=1`、`WVD_REQUIRE_LIST_PILOT_BROWSER=1`，不能以缺少浏览器时的跳过作为通过。
