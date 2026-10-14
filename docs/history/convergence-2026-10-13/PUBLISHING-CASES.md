# Publishing cases：四种真实长文表达与 WSJ 深读的可验证假设

本研究的判断是：值得学习的不是四家的组件集合，而是文章在什么地方要求读者改变阅读方式。Al Jazeera 用一件物品贯穿人物与照片；WIRED 让技术的兴奋感逐步接受商业和安全约束；Guardian 用一天的时间骨架编织行业报道；FT 把两个容易混淆的指标放进同一证据画面。它们都依赖完整报道中的转折，不能用摘要模块替代。

## 范围、证据等级与访问限制

研究归档于 `convergence-2026-10-13`，浏览会话跨至 2026-10-14。仅使用出版方文章、出版方设计说明及 FT 官方 GitHub 资料。搜索结果只用于找链接，不作为正文结论的证据。没有复制全文，没有登录、购买订阅或绕过付费墙。

在主任务共享的 ego TaskSpace **77 / p2** 检查实际文章，未另建空间。桌面采用 **1440 × 1000 CSS px**；手机采用 CDP **390 × 844 CSS px**、`mobile: true`、DPR 1 的浏览器模拟。手机证据是响应式布局观察，不是真机触控或 Safari 验证。部分 `goto` 因广告未完成加载超时，但页面已提交；随后在同页观察可访问内容。正文位置截图通过定位已有段落或章节线完成，不改变页面内容。

- **HTML/text verified**：出版方 HTML 的 reader 提取能确认文字顺序、标题、图注、链接；不能据此断言视觉位置、交互成功或原版设计。
- **Live layout verified**：实际浏览器截图和 DOM 几何共同确认本次页面布局；证据仅覆盖记录的视口及文章位置。
- **[INFERENCE]**：研究者的阅读效果推断、未能看见的正文视觉，以及 WSJ 的应用建议。不是出版方声称、用户测试或已实施结果。

| 实际文章 | 代表性表达 | 本次验证与限制 |
|---|---|---|
| [Al Jazeera：The story of a book in Gaza: A treasured possession given new lease of life](https://www.aljazeera.com/features/2026/10/4/the-story-of-a-book-in-gaza-a-treasured-possession-given-new-lease-of-life)，Lina Ghassan Abu Zayed，2026-10-04 | 物品贯穿的现场报道；连续正文与纪实照片，无复杂数据模块 | HTML/text 全文；桌面/手机首屏及正文 live layout。广告和推荐阅读确实插入阅读环境。 |
| [WIRED：Inside Gravity’s daring mission to make jetpacks a reality](https://www.wired.com/story/gravity-jetpacks/)，Oliver Franklin-Wallis，2020-10-13 | 技术人物特写；从飞行体验走到可行性与商业边界 | Reader HTML/text 可读完整叙事；当前浏览器仅开放开头，显示订阅限制。桌面/手机标题和首段 live layout；中后段视觉均未验证。当前迁移后的归档页不能代表 2020 年原版排版。 |
| [Guardian：A day in the life of (almost) every vending machine in the world](https://www.theguardian.com/business/2022/apr/14/a-day-in-the-life-of-almost-every-vending-machine-in-the-world)，Tom Lamont，2022-04-14 | 一天的时间骨架、多人物与行业机制的编织式长文 | HTML/text 全文；桌面/手机正文首个章节转场 live layout。最初截图有隐私提示；后续章节截图无遮挡。 |
| [FT：Women still miss out on management in finance](https://ig.ft.com/managements-missing-women-data/)，Laura Noonan、Alan Smith、David Blood、Martin Stabe，2017-04-04 | 自有调查数据与行业访问结合；比较驱动的报道 | HTML/text 全文；桌面/手机图表及限制段落 live layout。核心图能加载；文末 `#table` 数据探索容器本次为空，只有 CSV 链接，未验证数据下载成功。 |

选取旧文章是为了深入可取得的正文和真实证据关系，不把四篇误称为最新设计。另尝试 [FT：How mega batteries are unlocking an energy revolution](https://ig.ft.com/mega-batteries/)，真实浏览器被转到订阅产品页；因此它**不是**本研究的已检查正文案例，不以搜索摘要推演其滚动图表设计。[访问证据](evidence/ft-mega-batteries-paywall.png)。尝试的 [WIRED：Take This Mandatory AI Workplace Training Right Now—or Else](https://www.wired.com/story/ai-or-die-trying/) 实际是课程/门户式互动，不适合作为普通长篇报道的替代样本，也未计入四例。

## 1. Al Jazeera：让一本书承担连接，不把每一个数字升格

**可定位的文字证据。** 开头先给十岁的 Aya 和手中的书，第二段用 “Before it reached Aya’s hands, it had a difficult journey.” 启动回溯。之后是教育破坏的总体背景、Saad 抢救书籍和建立帐篷图书馆、Hamad 的搜集与 Mikdad 的修复、Phoenix Library 的借阅，再回到 Aya。中段 “But the books Saad rescues still face other dangers.” 把抢救成功转成保存条件不足；结尾重新回到书被打开阅读的用途。这些转折和照片图注可在[原文](https://www.aljazeera.com/features/2026/10/4/the-story-of-a-book-in-gaza-a-treasured-possession-given-new-lease-of-life)按短句定位，HTML/text verified。

**首屏与正文的工作分配。** 当前桌面先有广告区、品牌导航、`Features | Gaza`、标题、斜体导语、听读/收藏/分享，随后是真实抢救现场照片；作者和时间位于照片之后。标题讲的是一本书，导语讲的是一群人的保护工作，照片给出破坏环境中的当事人，三者承担不同尺度的信息。1440 桌面报道栏为 770px，开头正文在首屏下方；390 手机正文宽 360px，抽样段落为 18px / 27px。手机把报道主线收进单栏，但不能据此把延后的首段证明为最优。[桌面首屏](evidence/aj-desktop-head.png)、[桌面正文](evidence/aj-desktop-body.png)、[手机首屏](evidence/aj-mobile-head.png)、[手机正文](evidence/aj-mobile-body.png)，live layout verified；文字角色参照[原文](https://www.aljazeera.com/features/2026/10/4/the-story-of-a-book-in-gaza-a-treasured-possession-given-new-lease-of-life)。

**段落、照片与过渡。** 没有为每个受访者造一个小标题，人物交接由普通段落完成；图库也没有独立替代报道。Saad 和儿子的整理照片靠近其藏书被毁与重建故事，帐篷内照片对应保存风险，Phoenix 创办人的照片靠近借阅用途。图注明确姓名、地点和记者来源。学校破坏比例、藏书量、抢救量、胶水价格、借阅押金都留在各自叙事上下文里；它们回答不同问题，并不构成一个可以同时相加或排名的“关键数字”面板。[原文正文及四处图注](https://www.aljazeera.com/features/2026/10/4/the-story-of-a-book-in-gaza-a-treasured-possession-given-new-lease-of-life)，HTML/text verified；正文起始位置见上述 live 截图。

**读者问题与判断。** [INFERENCE] 读者可能不清楚“毁坏之后如何重新让孩子读到书”。把搜集、修复、借阅和孩子连起来，提供的是可追踪的因果链。照片让人物劳动具体化；不需要额外摘录面板告诉读者“书很重要”。这种现场可核实性，比橙色标记更能说明新闻身份。出版方 2015 年[设计说明](https://www.aljazeera.com/news/2015/1/20/the-new-aljazeera-com)强调原始报道与跨设备访问；网络[发布公告](https://network.aljazeera.net/en/pressroom/new-aljazeeracom-launched)说明各屏幕保持一致但分别优化。这些是历史原则，不是这篇 2026 文章的专项设计意图。

**伤害和反例。** 实际原文在开头两段后插入 Recommended Stories，现场过程里出现广告；桌面还同时有 sponsored rail 和底部广告。本次首屏截图确实能看到它们。[原文](https://www.aljazeera.com/features/2026/10/4/the-story-of-a-book-in-gaza-a-treasured-possession-given-new-lease-of-life)、[首屏证据](evidence/aj-desktop-head.png)。[INFERENCE] 它们抢走“那本书后来怎样”的注意力，不能因来自成熟出版物就复制。另一个反例：若将胶水涨价制作成大数字，再把学校损毁比例和儿童人数并列，读者容易误以为都是同一范围、同一时间和同一种统计可靠性。

**对中文双语 WSJ 的适用性。** [INFERENCE] 对现场报道先检查贯穿物、场景和人物交接，保留原段落与原转折。真实照片在相关劳动或场景的段落边界出现，图注在中英模式都保持来源；不能用装饰图库占位。开头的短叙事组应能连续读完，不插“关键数字”或推荐阅读。无照片时，完整文字本身就是成立的表达。

## 2. WIRED：技术的精彩来自论证转向，正文可以完全不依赖复杂模块

**可定位的文字证据。** 首段从身体离地时的本能反应展开，以 “Latitude, longitude, altitude.” 收束。随后解释微型燃气涡轮、失败试验与第一次起飞；文章中间追溯早期火箭背包为什么没有成事，再进入记者到场的试飞、竞争者设计和风险。真正的论证转向是 “now that they’re here, what are jetpacks for?”；结尾回到 Browning 的家庭历史。这不是按性能参数排列的产品评测。[原文](https://www.wired.com/story/gravity-jetpacks/)，HTML/text verified。

**首屏和当前访问状态。** 本次页面采用 WIRED 导航、作者、`THE BIG STORY`、日期、明显的大标题与提问式导语；其后就是正文开头，没有从 reader 中的默认分享图制造一张文内照片。桌面首段抽样宽约 632.5px，19px / 28px；开头的几个英文词以大写区别于后文。当前浏览器紧接首段显示 “The Big Story is exclusive to subscribers.”，手机标题/开头也受到访问限制。[桌面首屏](evidence/wired-desktop-head.png)、[桌面标题至首段](evidence/wired-desktop-opening.png)、[手机开头](evidence/wired-mobile-opening.png)，live layout verified。Reader 能提取更长正文与 metadata 的 `free` 标记，**不能推导当前浏览器是免费全文**；以实见订阅门槛为准。[原文](https://www.wired.com/story/gravity-jetpacks/)。

**正文组织与图文关系的限度。** 当前 reader 正文没有可见的中间小标题、数据表或文内照片序列。技术解释直接接在发动机购买情节后；安全约束接在更新后的装备描述后；燃料、电池与商业模式进入文章后半部。图表缺席并不等于缺乏证据：每个解释都改变了前一段给人的可行性印象。[原文相关段落](https://www.wired.com/story/gravity-jetpacks/)，HTML/text verified。中后段的视觉层级、广告插入、当年摄影、原版章节处理均未看见，任何相关视觉判断必须标 **[INFERENCE]**，本研究不把 reader 的连续文字当成全篇视觉验证。

**读者问题与判断。** [INFERENCE] 读者容易把“已经飞起来”误读为“已经有可扩展市场”。这篇文章让场景、历史失败、工程限制与售价/用途相互校正，兴奋感和怀疑感都来自记者叙述。若提前把几个速度、推力、价格拉成规格卡，读者可能只记得酷炫设备，错过记者逐步缩窄的结论。WIRED 的科技气质在于这种问题推进，而不只是衬线大标题。其工程负责人在[2015 年改版说明的 Responsive and Mobile-First 部分](https://www.wired.com/2015/03/wired-dot-com-from-the-devs/)解释了跨设备网格与一个代码库；性能部分也谈减少冗余第三方请求。该说明支持跨设备阅读的一般方向，不证明 2026 当前文章页面沿用了 2015 的组件或技术栈。

**伤害和反例。** 本次 live 开头被付费提示终止，所以不能声称已验证 WIRED 全文的连续阅读舒适度。[开头证据](evidence/wired-desktop-opening.png)。[INFERENCE] 对内容设计而言，把创业者一句兴奋的直接引语拔成最醒目的元素，会压过安全、市场与失败背景；正文已经在完成“希望—限制”的工作，额外做主张/现实双栏会重新排列记者的揭示顺序。当前迁移页也不适合拿来证明“WIRED 长文必须有头图”。

**对中文双语 WSJ 的适用性。** [INFERENCE] 技术/企业特写先保住体验—原理—限制—用途的原文结构。数字可以在原段落中有清楚单位，不必组件化。长文不应因切换英文而截短或丢失人名、作者、时间；两种语言必须读到同一个论证终点。英文开头的大写可以作为观察对象，中文不要机械换成首字下沉，正文自然起笔即可。

## 3. Guardian：有章节感，不必把章节改写成导航标题

**可定位的文字证据。** 开头是记者午夜购买 Doritos，第二段才说明一天观察的目标；随后见经营者 Johnny Brod、公司控制室和销量数据。第一大段末尾用 “What happened next in the wider world of these machines?” 把采访扩展到全球。第一道章节线后的段落以 “At 12.45am” 起笔；后面的转场包括 “Lunchtime.”、“In Manchester it was mid-afternoon.”，最后返回接近午夜的购买，以及日本读者远行去买折纸的结尾。[原文](https://www.theguardian.com/business/2022/apr/14/a-day-in-the-life-of-almost-every-vending-machine-in-the-world)，HTML/text verified。

**首屏与出版身份。** 实际桌面首屏以宽幅多种自动售货机拼贴起势，Guardian 蓝色导航与品牌仍清楚；标题处有 `The long read` 身份及旧文日期提示，短导语提出机器人零食的吸引力问题。首屏图片把题材的多样性打开，不负责证明某一个运营商的数据。最初[桌面首屏](evidence/guardian-desktop-head.png)和[手机首屏](evidence/guardian-mobile-head.png)有隐私提示遮挡，不能拿它们评价无遮挡标题的精确屏占比。文章首图的拼贴与署名在[原文](https://www.theguardian.com/business/2022/apr/14/a-day-in-the-life-of-almost-every-vending-machine-in-the-world)也能确认，HTML/text + limited live layout verified。

**章节、段落和照片。** DOM 里报道有六个 `article hr`，形成七个叙事区段。第一道章节线是短横线、留白和红色英文首字下沉；没有附加“历史”“商业模式”等抽象小标题。它在桌面和 390 手机仍是同一条正文流：桌面抽样宽 620px；手机宽 370px；同一段的字号/行高均为 17px / 23.8px。手机截图仍能看见跨到新章节前的一整段，而不是被卡片分割。[桌面章节](evidence/guardian-desktop-chapter.png)、[手机章节](evidence/guardian-mobile-chapter.png)，live layout verified。行业人物、历史机器、东京街头和设备内部的照片随有关段落出现，各有独立署名；金额、利润、设备数和销售时点仍在叙事里。[原文照片与段落](https://www.theguardian.com/business/2022/apr/14/a-day-in-the-life-of-almost-every-vending-machine-in-the-world)，HTML/text verified。

**为什么是值得学的具体处理。** [INFERENCE] 一篇同时讲人物、全球销量、历史、维护和商业模式的长文，需要让读者知道“换了一个叙事阶段”，又不能把一天的经过拆成百科词条。章节线给出停顿，新的时间/地点句承担恢复方向的工作。它把数据编进过程，而不是把所有时间戳抽成一条长时间线。这些时间是用来观察全球一天的多线并行，并非事件升级史。

出版方[2026 年长文编辑与设计说明](https://www.theguardian.com/membership/2026/jul/24/every-sentence-will-be-put-under-pressure-how-we-make-our-long-reads-unputdownable)特别以这篇售货机报道为例：在线/报纸使用各地机器照片，夏季杂志版另委托插画；艺术总监强调 “large, punctuated moments, but never at the expense of the read”。因此不同版本可以换视觉表达，但不能因此拿杂志插画来证明本次网页的版式。该说明也把人物、起点终点、冲突和场景列为长文判断依据，HTML/text verified。

**伤害和反例。** 红色首字下沉是本次实见的英文处理；手机仍占去开头多行的一部分宽度。[手机章节](evidence/guardian-mobile-chapter.png)。[INFERENCE] 中文照搬会造成首字被切成装饰，且未解决方向恢复；应学习“章节位置和恢复句”，不是字母形态。另一个反例是给售货机所有数字配卡：37 个死亡案例、机器规模、收入和一包零食利润在原文是不同问题的证据，同等放大将制造错误的权重。隐私提示和穿插的相关稿链接也不是值得仿制的阅读节奏。[原文](https://www.theguardian.com/business/2022/apr/14/a-day-in-the-life-of-almost-every-vending-machine-in-the-world)、[初次正文截图](evidence/guardian-desktop-body.png)。

**对中文双语 WSJ 的适用性。** [INFERENCE] 可在原文已有的时空/论证换挡处保留有出处的章节边界，以少量空间变化帮助继续读；不要随意写新标题。中文章节开头保持正文，英文可保留各自排版特性，但切换应定位到相同语义段落，而不是相同像素距离。若正文没有时间骨架，就不应因为出现日期而生成时间线。

## 4. FT：画出“全员占比”和“高层占比”的关系，保留比较的限制

**可定位的文字证据。** 开头先给初级女性员工占多数、进入高层却只约四分之一的矛盾，然后交代收集 50 家机构、另有 15 家拒绝披露。图前段落给出 2014—2016 年高层占比变化和中层停滞；图后才分行业和地区展开。重要限制是 “Comparisons between institutions are imperfect with this data”，随后解释级别由企业自行定义，但各雇主的跨年比较有效。[原文](https://ig.ft.com/managements-missing-women-data/)，HTML/text verified。

**首屏角色。** 当前归档页有简明 FT 品牌、系列名、结论式标题、研究性质导语、日期与四位作者，然后是一幅署名 FT graphic 的插画和报道开头。它先告诉读者这篇为什么不是普通观点文章：结论来自 FT 收集的数据。暖色纸底在标题、正文、插画和数据图中持续，整体身份不会在进入图表时变成另一种产品。[桌面首屏](evidence/ft-desktop-head.png)、[手机首屏](evidence/ft-mobile-head.png)，live layout verified；调查范围参照[原文](https://ig.ft.com/managements-missing-women-data/)。

**关键图到底增添了什么。** 实见核心图用横轴表示女性全员占比，纵轴表示女性高层占比；50% 的参照位置让“雇用了很多女性”和“女性进入领导层”同时接受检查。行业用颜色区分，总员工规模用圆大小表示，若干公司直接标名。图标题明确说没有一家实现高层性别平等。它不是把文中 25.5%、23.7%、39% 做成三块大数字，而是呈现每家公司两种占比的关系及分布。图上还有 Citi 的高层口径与部分公司地区范围的脚注、Companies/FT research 来源。[桌面核心图](evidence/ft-desktop-chart.png)及[出版方原图](https://www.ft.com/__origami/service/image/v2/images/raw/ftcms%3A6374d1ae-1612-11e7-80f4-13e067d5072c?source=ig&width=800&height=900)，live layout verified。桌面图显示宽约 601px，邻近正文约 652px，不需要为图永久占出第二个阅读栏。

**手机不是只把桌面图压缩。** HTML 提供 320/600/800 宽的三套图；浏览器在桌面只显示 800 那套，另外两套宽度为零。390 手机展示更窄版本，仍将关键图放在趋势段落之后，限制段落仍属于正文流。[手机图](evidence/ft-mobile-chart.png)、[手机限制段](evidence/ft-mobile-caveat.png)，live layout verified；三套资源在[原文](https://ig.ft.com/managements-missing-women-data/)中可定位。图的细字、重叠圆和规模图例本身增加阅读负担，不能仅因加载成功就宣称人人看得懂。

**出版方解释与读者问题。** FT 官方[Visual Vocabulary README](https://github.com/Financial-Times/chart-doctor/tree/main/visual-vocabulary)明确说目标是识别图与文字共同工作的机会，并把本文列为 bubble chart 的实例；Correlation 部分提醒读者可能把相关性误认为因果，Bubble 部分解释尺寸是第三个变量。这里学习的是两种指标间的关系表达，不是从图形目录挑一种看起来高级的形式。[INFERENCE] 读者需要区分招聘结构与晋升结构，图确实增加正文单个平均数无法给出的分布视角；但四种视觉编码同时工作也容易使次要变量喧宾夺主。

**伤害和反例。** 文章明说各家公司级别定义不同，因此图中位置并不是完全可比的“最好/最差雇主排名”。重要限制没有全部埋到文末：图脚注说明具体口径，正文不远处解释跨机构比较的不完美。但手机看到图和随后读到完整限制仍需要滚动，存在先形成排名印象的风险。[原文](https://ig.ft.com/managements-missing-women-data/)、[图](evidence/ft-desktop-chart.png)、[限制段](evidence/ft-mobile-caveat.png)。本次文末 Explore the data 的 `#table` 容器为空，CSV 链接仍在，不能声称数据探索或筛选功能正常。这是归档交互脆弱性的直接观察，不是图表证据不存在。

**对中文双语 WSJ 的适用性。** [INFERENCE] 有真实原始图和数据时，保留图要回答的比较关系、单位、基准、口径、日期和来源；中文图注要让读者在第一次遇到图时知道限制，而不是仅贴“数据来源”。正文继续保持完整。若只有报道中的零散数字而没有共同口径，不应模拟该散点图；可留在原文，或在确有独立阅读需要时用可追溯的简单关系表。两种语言切换时图、图注和相关正文应保持同一位置关系。静态交付还应避免把理解结论所需的证据仅放在需要加载的探索控件中。

## 五个可行动假设：先用真实 WSJ 文章检验

这些是本研究提出的设计假设，不是四家出版物替 WSJ 作出的规则，也未在 WSJ 成品上验证。它们可以通过现有 Python/静态 renderer 和同一份 `final.json` 的编排变体评估，不需要新平台或另一个 renderer。

1. **先保护完整叙事组，再确定增强插入点。** 用一篇人物/现场稿标记开场、解释、转折和收束，只在这些原文边界考虑照片或注释。对照一版完全连续正文、一版带增强；判断读者能否解释场景如何进入证据、限制如何改变结论，以及增强是否迫使回读。以 [AJ 的书籍流转](https://www.aljazeera.com/features/2026/10/4/the-story-of-a-book-in-gaza-a-treasured-possession-given-new-lease-of-life)和 [WIRED 的用途问题](https://www.wired.com/story/gravity-jetpacks/)为依据。若增强仅重复已读句子，或插断人物同一轮行动，应拒绝它。
2. **把章节当成恢复方向的设施。** 对原文确有时空或论证换挡的长文，用其已有边界试做安静的章节间距/细线，继续保留原来的开头句；不要新写标题，不在中文做首字下沉。检验手机中断后返回时能否知道当前人物、地点或论证阶段。[Guardian 的实见章节](evidence/guardian-mobile-chapter.png)及[原文](https://www.theguardian.com/business/2022/apr/14/a-day-in-the-life-of-almost-every-vending-machine-in-the-world)是具体依据。若只是每隔固定段数变样，该处理没有成立。
3. **让图或表回答一个关系问题，并在第一次阅读处说明边界。** 选择有可用原图/共同口径数据的 WSJ 稿，先写内部问题，如“总体增长是否也发生在每个地区”，再决定保留原图或简化关系表。读者应能辨认单位、范围、时间、比较基准和不能推导的结论；同样在 390px 判断，而不是只测溢出。[FT 原文](https://ig.ft.com/managements-missing-women-data/)、[核心图](evidence/ft-desktop-chart.png)及[官方比较提醒](https://github.com/Financial-Times/chart-doctor/tree/main/visual-vocabulary)为依据。若数字不具可比性，不造总览。
4. **给每张照片一个可核对的报道职责。** 在计划中说明它对应哪个人物/场景/证据段落、图注来源和放置边界；首图可以引入环境，文中图应增加具体见证。用“移除后读者损失什么”检验，不用图片数量检验。[AJ 的人物与劳动图注](https://www.aljazeera.com/features/2026/10/4/the-story-of-a-book-in-gaza-a-treasured-possession-given-new-lease-of-life)、[Guardian 的线上/杂志不同处理说明](https://www.theguardian.com/membership/2026/jul/24/every-sentence-will-be-put-under-pressure-how-we-make-our-long-reads-unputdownable)为依据。没有真实可用照片时保持文字稿，不补装饰媒体。
5. **双语共享同一条报道路径，以完整性和位置关系证明出版身份。** 检查 CN/EN 是否保留相同文章终点、作者日期、源证据、图注和章节边界；切换以段落身份恢复阅读位置，不以像素比例定位。让现场稿、技术稿、比较稿在既有 AJ × WIRED 字体/网格/色彩内体现不同关系，而不是换“主题皮肤”。跨设备身份依据 [AJ 历史发布说明](https://network.aljazeera.net/en/pressroom/new-aljazeeracom-launched)、[WIRED 历史工程说明](https://www.wired.com/2015/03/wired-dot-com-from-the-devs/)；WSJ 的忠实与完整性约束依据本仓库 [FOUNDATION.md](../../../FOUNDATION.md)、[DESIGN.md](../../../DESIGN.md)。若英文截断或 metadata 丢失，这个假设的前提就没有满足。

## 本研究不能证明什么

四篇均为英文出版物，本研究没有中文母语读者测试，不能把其行宽、英文大写、首字下沉或字号比值直接设成中文默认。视觉观察不证明可访问性、长时间阅读疲劳、真实设备性能或理解提升。截图保存的是特定时刻的页面，广告、隐私提示和付费状态可能因会话变化；前期带遮挡的 Guardian 截图只用于说明限制，正式章节观察使用后续无遮挡截图。

WIRED 中后段只获得文字，不得把其视觉连续性写成已验证。FT 的 2017 页面只是一个可检查的证据驱动案例，不代表 FT 最新全部长文；2025 电池文章被付费墙挡住。AJ/WIRED 2015 设计说明与 Guardian 2026 的杂志说明各有年代和媒介边界，不能解释当前所有组件的具体决策。没有核查报道事实是否在发表后改变，也没有将新闻中的数字重新当成当下事实。报告关注原文如何组织证据和阅读。

本文件和 `evidence/` 是研究证据；没有编辑生产代码、复制全文、改写 `final.json`、运行构建/测试/格式化，或新增代理。浏览空间由主任务统一收尾。
