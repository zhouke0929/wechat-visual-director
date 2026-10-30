<div align="center">
  <p><img src="assets/identity/mascot.png" alt="公众号视觉主编的珊瑚色逗号图标" width="120" height="120"></p>
  <h1>公众号视觉主编</h1>
  <p><b>WeChat Visual Director</b></p>
  <p>开源公众号 AI 排版 Skill：<br>把稿件变成可编辑的公众号图文，支持自定义排版样式。</p>
  <p>
    <a href="https://github.com/zhouke0929/wechat-visual-director/releases"><img src="https://img.shields.io/github/v/release/zhouke0929/wechat-visual-director?include_prereleases&amp;label=release&amp;color=F26078" alt="Release"></a>
    <a href="https://github.com/zhouke0929/wechat-visual-director/actions/workflows/ci.yml"><img src="https://github.com/zhouke0929/wechat-visual-director/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
    <a href="LICENSE"><img src="https://img.shields.io/github/license/zhouke0929/wechat-visual-director?color=30223B" alt="License"></a>
    <a href="#系统要求"><img src="https://img.shields.io/badge/Windows-supported-0078D4" alt="Windows supported"></a>
    <a href="#系统要求"><img src="https://img.shields.io/badge/macOS-Technical_Preview-777777" alt="macOS Technical Preview"></a>
  </p>
  <p>
  <a href="#快速开始"><b>交给 Agent 安装</b></a>
  · <a href="https://zhouke0929.github.io/wechat-visual-director/"><b>查看成稿示例</b></a>
  · <a href="#给参考创作自己的整套主题"><b>自定义排版样式</b></a>
  · <a href="https://github.com/zhouke0929/wechat-visual-director/releases"><b>版本记录</b></a>
  </p>
</div>

## 48 秒，看看排版效果

[![播放 48 秒宣传片：一句话排版、整篇换风格、参考图定制主题与编辑预览](docs/assets/readme/product-demo-poster.png)](https://zhouke0929.github.io/wechat-visual-director/#product-film)

[▶ 前往官网播放](https://zhouke0929.github.io/wechat-visual-director/#product-film) · [下载 MP4](docs/assets/readme/product-demo.mp4)

一句话排版、整篇换风格、参考图定制主题、编辑与手机预览。画面包含真实工作台截图与流程动效演示，不是一次完整运行的录屏。

## 公众号成稿示例

教程、商业分析和品牌观点，同一套排版能力，不同的阅读气质。点击下方示例即可阅读完整推文，无需安装。

[![三篇公众号成稿：青春校园、温暖人文与波普海报的真实排版及 AI 配图](docs/assets/readme/product-showcase-articles.png)](https://zhouke0929.github.io/wechat-visual-director/)

<table>
  <tr>
    <td width="33%"><a href="https://zhouke0929.github.io/wechat-visual-director/articles/campus.html"><img src="site/assets/generated/campus-portfolio-steps.webp" alt="青春校园：课程作业改造为作品集的四步信息图"></a></td>
    <td width="33%"><a href="https://zhouke0929.github.io/wechat-visual-director/articles/coffee.html"><img src="site/assets/generated/coffee-repeat-scene.webp" alt="温暖人文：社区咖啡店的暖色场景配图"></a></td>
    <td width="33%"><a href="https://zhouke0929.github.io/wechat-visual-director/articles/pop-collaboration.html"><img src="site/assets/generated/pop-collaboration-memory.webp" alt="波普海报：品牌联名与视觉记忆的拼贴配图"></a></td>
  </tr>
  <tr>
    <td width="33%"><b>把课程作业变成作品集</b><br>教程步骤 · 青春校园<br><a href="https://zhouke0929.github.io/wechat-visual-director/articles/campus.html">阅读完整推文 →</a></td>
    <td width="33%"><b>社区咖啡店，如何让客人再来</b><br>本地商业 · 温暖人文<br><a href="https://zhouke0929.github.io/wechat-visual-director/articles/coffee.html">阅读完整推文 →</a></td>
    <td width="33%"><b>联名越做越多，为何反而记不住</b><br>品牌观点 · 波普海报<br><a href="https://zhouke0929.github.io/wechat-visual-director/articles/pop-collaboration.html">阅读完整推文 →</a></td>
  </tr>
</table>

示例为公开演示内容，不含公司内部稿件或运营数据；配图为 AI 生成并经人工选用。在线展示是静态样例，实际编辑在安装后的本地工作台进行。

## 快速开始

适合公众号运营、新媒体团队和内容创作者。先体验排版、编辑和导出，再按需配置配图与微信草稿交付。安装器会注册 Codex、通用 Agent Skill 目录与 OpenCode。

### 把这段话发给你的 Agent

```text
请为我安装或升级完整的 wechat-visual-director，并打开本地工作台。
请先完整阅读并执行下面的安装说明，按 main/VERSION 安装对应的已发布版本：
https://github.com/zhouke0929/wechat-visual-director/blob/main/INSTALL_FOR_AGENT.md

需要同时安装轻量 Skill 和工作台，运行 doctor --json 确认就绪；
Skill 目录只放轻量技能包，完整程序使用独立的安装目录。
完成后返回实际安装版本、工作台链接，以及不超过五行的上手说明和下一句使用示例。
如果受限未完成，请说明停在哪一步。不要读取或回显任何密钥。
```

**给安装 Agent：** 完整执行 [INSTALL_FOR_AGENT.md](INSTALL_FOR_AGENT.md)，不要只复制 Skill 文件；须返回实际安装版本、已就绪的工作台链接与简短上手说明。

可以从能操作本机的 **Codex 桌面端 / CLI 或 OpenCode** 开始。宿主需要能读取 Skill、执行本机命令，并已完成自身的模型配置、登录与额度准备；只有网页聊天的环境不能直接完成安装。

安装器会读取 [main/VERSION](https://raw.githubusercontent.com/zhouke0929/wechat-visual-director/main/VERSION)，下载对应的已发布 Release 包并校验 SHA-256；Windows 与 macOS 共用这一版本选择规则。若对应包尚未发布或下载失败，安装会停止并报告原因。日常“打开工作台”复用已有安装，升级时再获取新版本。

完整安装包含 **轻量 Skill、本地工作台及运行环境**，无需预装 Git、Python、Node.js、pnpm 或 Homebrew。需要自己执行命令时，见[安装与维护指南](docs/usage-guide.md#手动安装与升级)。

<details>
<summary>安装后，试着发出第一条需求</summary>

```text
请用 wechat-visual-director，帮我写一篇关于“社区咖啡店如何让客人愿意再来”的公众号文章。
先整理内容和结构、完成语义规划，再打开本机工作台让我编辑和审核。
不要虚构经营数据，暂时不要生成图片或创建公众号草稿。
```

已有文章可以这样说：

> 用 wechat-visual-director 帮我排版下面这篇文章。保留原意和事实，先整理结构、完成规划，再打开工作台让我确认。［粘贴文章或附上文件］

主题确认后，若 Agent 支持原生生图，再说：

> 按当前主题，为这篇文章的正文和封面生成候选，放回工作台让我审核。

工作台首页提供上手流程与可复制指令；“最近任务”可按标题关键词查找历史文章。也可以告诉 Agent“继续昨天那篇咖啡店文章”，让它查找已有任务；同名或不明确时再由你选择，不必自己找任务 ID。

</details>

## 让内容、排版和配图一起服务阅读

### 先理解信息关系，再安排版式

“这三点是并列观点，还是必须依次执行的步骤？”“这一段是证据，还是结论？”

Agent 先回答这些问题，再选择适合的呈现方式：让对比有边界、步骤有顺序、摘录有出处、重点容易被看见。现有 **12 类语义组件**，配合标题、正文、引用、列表与图文等基础样式，根据内容关系与信息密度组合，兼顾重点呈现和阅读节奏。

选题、资料、纯文本或 Markdown 都可以作为起点。Agent 整理内容并输出结构化规划，本地程序通过受控组件完成 Markdown 到微信兼容 HTML 的转换，形成统一、可编辑的文章版式。

### 12 套主题，换的是整篇文章的阅读气质

从轻盈阅读、温暖人文，到编辑对比、新中式雅集、未来科技；每套主题都有自己的标题、色彩、留白、章节节奏和组件样式。

可以在工作台整篇切换，正文与已有图片会保留。**切换主题本身不会重新调用图片模型**；如果希望图片也适配新风格，再主动生成新候选。

[![12 套真实主题的在线样本册](docs/assets/readme/product-showcase-themes.png)](https://zhouke0929.github.io/wechat-visual-director/#themes)

[打开在线主题样本册，比较同一篇文章的不同表达 →](https://zhouke0929.github.io/wechat-visual-director/#themes)

### 给参考，创作自己的整套主题

喜欢秀米、135 编辑器里的某个组件，或有自己想要的品牌气质？**推荐附上喜欢的组件截图**，交给已安装 Skill 的 Agent，更容易对齐你想要的风格。不需要准备整套参考，也不需要自己写 HTML。

Agent 会分析参考的构图与视觉语言，寻找相关组件参考、联想同方向元素，再延展整套标题、引用、列表、图文和重点组件；不是只给现有主题换色，也不是只优化少数部件。随后进行本地结构检查与视觉评审，用完整文章展示阅读效果。

```text
请用 wechat-visual-director，根据我附上的组件参考图，创作一整套新的主题。
寻找相关组件参考，联想关联元素，延展完整视觉语言；正文保持可编辑。
在样本册和一篇示例文章中让我查看效果，先不要创建公众号草稿。
```

没有参考图，也可以描述用途、气质和偏好，先探索方向；Agent 会寻找可查看的成品组件参考，把描述具体化。仅描述不保证与有参考图时同等的视觉稳定性，审美理解有明显分歧时会先与你确认方向。参考素材只用于研究与原创转译，不照搬他人整套设计。

完成后，主题出现在本机样本册的“我的主题”，可导出 `.vdtheme` 扩展包分享、导入另一台工作台，并用于后续文章。切换主题保留正文和已有图片；重新生成配图需要你主动确认。样本册可查看 **14 种基础样式与 12 类语义组件**，包括普通引用、列表、表格与来源说明，整篇样张只选用适量组件。

本地检查通过不代表微信已经验证。满意后，仍需保存公众号草稿、重新打开，并核对手机预览。[查看主题创作流程与指令 →](https://zhouke0929.github.io/wechat-visual-director/#custom-themes)

### 原文编辑与双端预览

内容校对页支持在正文位置编辑，自动保存；切到手机预览，就能检查修改后的阅读效果。主题、图片、封面与最近任务也都在同一个工作台里。

[![本地工作台真实截图：左侧审核正文配图，右侧直接编辑文章标题并查看排版效果](docs/assets/readme/article-review.png)](#快速开始)

[![手机预览模式的完整工作台：左侧审核正文配图，右侧在手机外观中查看同一篇文章的阅读效果](docs/assets/readme/article-mobile-review.png)](#快速开始)

*公开示例在当前工作台中的真实界面：桌面校对可直接编辑原文，手机预览用于检查阅读效果。图中配图为已导入素材。*

桌面校对与手机预览呈现同一篇文章在不同阅读场景下的效果。编辑标题和正文时，主题装饰与组件结构保持完整；图片和封面在对应的审核区选择、替换与调整。

微信版本、设备宽度和字体仍可能带来差异；最终发送前，建议再用公众号后台和手机预览核对。

### 正文配图与封面，共享一份美术方向

文章决定画什么，主题决定色彩、材质和构图气质。结构信息图解释步骤与关系，场景图承接叙事，视觉隐喻图表达抽象观点；封面与正文配图共享文章级视觉方向。

如果 Agent 本身支持可调用的原生生图工具，确认主题后可以直接让它生成正文与封面候选；也可以连接图片模型 API，或上传自己的图片。候选需要你审核后采用，封面显示区可以调整。

不知道怎么接着对话？正文配图和封面区域提供“也可以让 Agent 生成”的指令入口，自动带上当前任务链接，复制回对话即可。入口不会自己调用模型，也不会替你采用图片。

**生图不是必选项。** 没有生图工具或图片 Key，也能完成排版、编辑、预览和导出。AI 图中的文字、事实和细节仍需人工检查。

## 从一个选题，到一篇待发布的推文

1. **在 Agent 对话里开始。** 给一个选题、一组资料，或粘贴现成的纯文本 / Markdown。Agent 整理结构、完成语义规划，再返回本地任务链接。
2. **在工作台里定稿。** 切换主题、编辑原文、审核正文图片与封面，并通过桌面校对和手机预览检查阅读效果。
3. **选择交付方式。** 将正文与已采用的正文图片一起复制，下载交付包，或配置微信连接后创建公众号草稿。保存后核对手机预览，最终群发仍由你在微信中确认。

第一次可以只体验排版，满意后再开通图片和草稿交付能力，不必一上来配置所有服务。

## 需要配置什么？

| 你想做到哪一步 | 需要准备什么 |
|---|---|
| 整理内容、排版、编辑、预览、复制或导出 | 一个能使用本 Skill、执行本机命令的 Agent；项目无需额外文本模型 Key |
| 让宿主 Agent 生成正文图片与封面 | 宿主有可调用的生图工具及可用额度；不必另填项目图片 Key |
| 让工作台直连图片模型 | 在“本地设置”填写图片 Endpoint、模型和 API Key |
| 保存到微信公众号草稿箱 | 账号具有相应接口权限；在本地设置配置 AppID、AppSecret 和公网 IP 白名单，并通过连接检测 |

“无需额外 Key”不代表模型使用免费；Agent 订阅、模型与图片服务费用由对应服务商计收。上传自己的图片不需要图片 API。

**不接微信 API，也能复制图文。** 工作台会把已采用的正文图片和主题装饰随正文一起准备进富文本剪贴板；AI 配图和上传的正文图片都适用，不是只复制文字或本机图片链接。公众号封面、标题等发布信息仍需在后台设置。

需要浏览器支持图文剪贴板；大图较多时准备与粘贴可能变慢，超过本地大小保护上限会明确提示，不静默丢图。粘贴后请等图片处理完成，保存草稿并核对手机预览；失败时可下载交付包，已配置微信连接的用户也可改用 API 交付。[查看复制图文与排障说明 →](docs/usage-guide.md#复制图文不必先配置微信-api)

[查看图片连接、公众号配置与排障 →](docs/usage-guide.md)

## 本地优先，也保留必要的人工确认

- **数据保存在自己的电脑。** 程序版本与任务、图片、私有配置分开存放；正常升级保留数据，普通卸载也可保留数据。
- **本地不等于离线。** 提交给 Agent 的文章受宿主服务的数据政策约束；启用图片服务或微信交付时，相应内容会发送到对应服务。
- **凭据只填本地设置。** 不把 API Key、AppSecret、Cookie 或 Token 粘贴进 Agent 对话，也不提交到仓库。
- **草稿不等于发布。** 配图、封面与最终稿由你确认；创建草稿不自动群发。事实、图片文字与素材权利仍需发布者核对。

项目已用于真实公众号交付，但仍处于 Alpha 阶段。项目与腾讯、微信官方无隶属或背书关系。

## 系统要求

- **Windows：** Windows 10/11 x64，PowerShell 5.1 或更新版本，正式支持。
- **macOS：** Apple Silicon 与 Intel 提供自包含安装包，目前为 Technical Preview；两种架构的完整真机兼容性仍待验证。
- **宿主与网络：** Agent 能读取 Skill、执行本机命令；可访问 GitHub 下载入口，浏览器能打开本机 `127.0.0.1` 地址。暂不提供 Linux 便携安装包。

[安装版本与资产](https://github.com/zhouke0929/wechat-visual-director/releases) · [升级、排障与卸载](docs/usage-guide.md#升级卸载与数据保留) · [Agent 完整安装协议](INSTALL_FOR_AGENT.md)

## 开发与贡献

欢迎反馈实际公众号后台或手机端的兼容问题，也欢迎贡献主题、组件样式和图片风格。反馈时请附主题名、复现步骤与已脱敏截图；不要上传密钥、任务数据库或未公开稿件。开发新语义组件时，需要同步维护规划、渲染与验证逻辑。

如果你也希望把时间留给内容，而不是反复调格式，欢迎点一下仓库右上角的 **Star ⭐**。既方便下次找到，也让我知道这个方向值得继续打磨。用过后的一条真实反馈，同样很有帮助。

<details>
<summary>展开源码结构与开发验证</summary>

普通用户使用上面的 Release 安装流程；下面面向源码开发者。

- `skills/wechat-visual-director/`：可分发的轻量 Skill、首次使用脚本与协议参考。
- `apps/api/`：本地服务、规划校验、组件渲染、数据与草稿交付。
- `apps/web/`：工作台源码及预构建产物。
- `scripts/`：安装、启动、打包与验证脚本。
- `site/`：无需后端的公开产品页、主题样册和完整文章。
- `contracts/`、`samples/`、`docs/`：接口契约、中性样例与设计 / 发布记录。

准备好 Python 与 Node.js 开发环境并安装项目依赖后：

```powershell
python -m pip install -e "apps/api[dev]"
python -m pytest apps/api/tests -q
corepack pnpm@11.7.0 --dir apps/web install --frozen-lockfile
corepack pnpm@11.7.0 --dir apps/web typecheck
corepack pnpm@11.7.0 --dir apps/web build
python scripts/export_theme_gallery.py --check
```

自动化测试覆盖公开安装入口和版本选择规则。`docs/releases/` 保存各版本的发布记录与复现命令；首次安装以当前安装协议为准。

Windows 与 macOS 的 CI 执行核心测试和工作台构建；Release 流程构建三种平台包并进行隔离安装冒烟测试。

</details>

## License

[Apache License 2.0](LICENSE)。第三方依赖和外部服务分别受其自身许可证与条款约束。图标、宣传素材与字体来源见 [视觉资产说明](assets/identity/PROVENANCE.txt)。

---

**想先看看效果？** [打开在线样本册](https://zhouke0929.github.io/wechat-visual-director/#themes)。

**想用自己的文章试一遍？** [复制安装提示词](#快速开始)，把第一篇文章交给 Agent。
