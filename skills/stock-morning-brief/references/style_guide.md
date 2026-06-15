# 早评格式规范

本文档定义早评报告的格式规范，供 AI 生成时参考。

---

## 一、选股评分体系（三层映射法70分 + 技术面30分）

### 综合评分公式

```
总分 = 三层映射法得分（满分70分）+ 技术面得分（满分30分）
满分 = 100 分
```

### A. 三层映射法得分（满分 70 分）

| 维度 | 权重 | 10分标准（满分） | 7分标准（良好） | 3分标准（较差） |
|------|------|-------------------|-------------------|------------------|
| 业务纯正度 | 10 | 主营业务占比 > 50% | 占比 30-50% | 占比 < 30% |
| 行业地位 | 10 | 行业龙头/国内第一 | 前三名/隐形冠军 | 有一定地位但非头部 |
| 涨价受益度 | 10 | 已发涨价函且提价>10% | 行业普遍涨价未单独确认 | 仅概念关联无实际提价 |
| 业绩验证 | 10 | 最近季报营收+利润双增 | 单增或微增 | 双降或大幅下滑 |
| 催化剂临近 | 10 | 1周内有明确催化事件 | 1个月内 | 远期/不确定 |
| 估值位置 | 10 | 历史30%分位以下（低估） | 30%-70%分位 | >70%分位（高估） |
| 特殊标签加分 | +0~10 | 标准制定者/+5 | 国产替代稀缺/+5 | 参投独角兽/+5（可叠加，封顶+10） |

### B. 短线技术面得分（满分 30 分）

| 指标 | 权重 | 多头信号（高分） | 中性信号（中间分） | 空头信号（低分） |
|------|------|------------------|-------------------|-----------------|
| MACD | 8 | 金叉/零轴上方发散 = 8 | 黏合待选方向 = 5 | 死叉/零轴下方 = 2 |
| KDJ | 7 | J值20-80区间向上 = 7 | J<20超卖可博反弹 = 5 | J>85超买 = 2 |
| 成交量趋势 | 6 | 量增价涨 = 6 | 量价背离 = 3 | 量缩价跌 = 2 |
| 均线系统 | 5 | 多头排列（短>中>长）= 5 | 黏合缠绕 = 3 | 空头排列 = 1 |
| 支撑压力位 | 4 | 回调至关键支撑不破 = 4 | 中间位置 = 2 | 接近前高压力 = 1 |

### C. 最终评级

| 总分区间 | 评级 | 星级 | 操作建议 |
|----------|------|------|----------|
| ≥ 85 | 强烈推荐 | ⭐⭐⭐⭐⭐ | 可重点参与 |
| 75 - 84 | 推荐 | ⭐⭐⭐⭐ | 积极关注，逢低布局 |
| 60 - 74 | 一般观察 | ⭐⭐⭐ | 轻仓跟踪或观望 |
| < 60 | 不建议 | ⭐⭐ | 暂不参与 |

---

## 二、选股卡片输出格式（v3样式）

每只个股生成一个 `.stock-card` div，严格按以下结构：

```html
<div class="stock-card">
  <!-- ① 头部：名称/代码/市场标签/总分 -->
  <div class="stock-header">
    <span class="stock-name">天赐材料</span>
    <span class="stock-code">002709</span>
    <span class="stock-market sz">深(00)</span>
    <div class="stock-total-score">
      <div class="score-val">78</div>
      <div class="score-label">总分 / 100</div>
      <div class="stock-stars">⭐⭐⭐⭐ 推荐</div>
    </div>
  </div>

  <!-- ② 评分条（12个指标，三列紧凑网格） -->
  <div class="score-bars">
    <div class="score-bar-row"><span class="score-bar-label">业务纯正度</span><div class="score-bar-track"><div class="score-bar-fill good" style="width:90%"></div></div><span class="score-bar-val good">9/10</span></div>
    <!-- ... 其余11个指标 ... -->
  </div>

  <!-- ③ 内联小计 -->
  <div class="score-summary">
    <div class="sum-item"><span class="sum-label">三层映射:</span><span class="sum-val-fund">55/70</span></div>
    <span class="sum-divider">|</span>
    <div class="sum-item"><span class="sum-label">技术面:</span><span class="sum-val-tech">23/30</span></div>
  </div>

  <!-- ④ 核心逻辑框 -->
  <div class="stock-logic">
    <span class="label">核心逻辑：</span>...<br>
    <span class="label">关键数据：</span>...<br>
    <span class="label">催化事件：</span>...<br>
    <span class="label" style="color:#ff5252;">风险提示：</span>...
  </div>
</div>
```

**评分条颜色规则：**
- 得分率 ≥ 70% → `good`（绿色渐变）
- 得分率 40%-69% → `mid`（黄色渐变）
- 得分率 < 40% → `bad`（红色渐变）

---

## 三、市场情绪色彩体系

情绪状态映射为CSS类，应用于心态管理模块（`.mentality-box`）的动态配色：

| 情绪阶段 | CSS类 | 色系 | 边框/背景 | 适用场景 |
|----------|-------|------|-----------|----------|
| 高涨（狂热） | `sentiment-hot` | 🔴 红色系 | 红→橙渐变 | 连续大涨、涨停潮、成交天量 |
| 温和（乐观） | `sentiment-warm` | 🟡 黄色系 | 金→橙渐变 | 温和上涨、板块轮动、信心修复 |
| 寒冷（恐慌） | `sentiment-cold` | 🟢 绿色系 | 绿→翠渐变 | 下跌调整、缩量、避险情绪 |
| 极寒（冰点） | `sentiment-frozen` | 🔵 蓝色系 | 蓝→深蓝渐变 | 暴跌、恐慌性抛售、流动性危机 |

**AI 生成规则：**
1. 分析市场数据后判断当前情绪阶段
2. 在 `ai_texts.json` 中输出 `SENTIMENT_CLASS` 字段
3. `MENTALITY_MANAGEMENT` 的 HTML 使用该类：`<div class="mentality-box sentiment-cold">`

---

## 四、AI 输出字段完整清单（v3 更新）

以下字段必须在 `ai_texts.json` 中全部提供，否则模板占位符不会被替换：

| 字段 | 说明 | 来源 |
|------|------|------|
| MARKET_TONE | 市场定调（1-2句话） | AI生成 |
| EMOTION_FEATURE | 情绪特征（1句话） | AI生成 |
| SIGNAL_MONITOR | 见底信号监控（HTML表格） | AI生成 |
| MENTALITY_MANAGEMENT | 心态管理模块（含情绪色彩类） | AI生成 |
| US_IMPACT_ON_A | 美股对A股影响判断 | AI生成 |
| GLOBAL_MARKET | 全球市场简析 | AI生成 |
| GLOBAL_MARKET_ANALYSIS | 全球市场对A股影响分析（1-2句） | AI生成 |
| EVENT_TIMELINE | 事件时间线（HTML） | AI生成 或 data驱动 |
| TODAY_PREDICTION | 今日预判分析 | AI生成 |
| SECTOR_DIRECTIONS | 板块方向表格（HTML） | AI生成 |
| RISK_WARNINGS | 风险提示（HTML） | AI生成 |
| OPERATION_STRATEGY | 操作策略（HTML列表） | AI生成 |
| OPERATION_DISCIPLINE | 操作纪律条目（4条`<li>`） | AI生成 |
| STOCK_SELECTION | 选股卡片（HTML，v3评分条样式） | AI生成 |
| STYLE_SUMMARY | 方法论沉淀（HTML列表） | AI生成 |
| DIRECTION_JUDGMENT | 方向判断文字 | 脚本推导 |
| DIRECTION_SIGNAL_CLASS | 方向信号 CSS 类 | 脚本推导 |
| SH_RANGE_LOW/HIGH | 上证区间 | 脚本推导 |
| POSITION_ADVICE | 仓位建议 | AI生成 |
| PARTICIPATION_PACE | 参与节奏 | AI生成 |
| YESTERDAY_REVIEW | 昨日回顾补充文本 | AI生成 |
| SENTIMENT_CLASS | 情绪色彩CSS类 | 脚本推导 |

**总计 22 个字段**（18个AI生成 + 4个脚本推导）

---

## 五、LLM 输出格式示例（llm_analysis.json）

```json
{
  "MARKET_TONE": "市场定调（1-2句话）",
  "EMOTION_FEATURE": "情绪特征（1句话）",
  "US_IMPACT_ON_A": "美股对A股影响（2-3句）",
  "GLOBAL_MARKET_ANALYSIS": "全球对A股影响（1-2句）",
  "TODAY_PREDICTION": "今日预判（3-4句）",
  "YESTERDAY_REVIEW": "昨日回顾（2-3句）",
  "POSITION_ADVICE": "5-6成仓位",
  "PARTICIPATION_PACE": "参与节奏",
  "MENTALITY_ADVICE": ["建议1", "建议2", "建议3"],
  "SIGNALS": [
    {"name": "信号名", "status": "状态描述", "score": 8, "max": 10}
  ],
  "SECTORS": [
    {"priority": 1, "name": "板块名", "stars": "⭐⭐⭐⭐⭐", "logic": "逻辑"}
  ],
  "RISKS": [
    {"title": "风险标题", "desc": "描述"}
  ],
  "STRATEGY": [
    {"title": "策略标题", "desc": "描述"}
  ],
  "DISCIPLINES": [
    {"title": "纪律标题", "desc": "描述"}
  ],
  "STYLE_SUMMARY": [
    {"icon": "💰", "title": "标题", "desc": "描述"}
  ],
  "STOCKS": [
    {
      "name": "股票名", "code": "601899", "market_tag": "沪(60)", "market_class": "sh",
      "fund_scores": {"业务纯正度": 9, "行业地位": 10},
      "tech_scores": {"MACD": 7, "KDJ": 5},
      "logic": {"core": "...", "data": "...", "catalyst": "...", "risk": "..."}
    }
  ]
}
```

---

## 六、异常处理与降级策略

| 异常场景 | 处理方式 | 示例 |
|----------|----------|------|
| 美股数据完全无法获取 | 标注"数据缺失"，基于A股自身技术面分析，降低置信度 | "因网络原因美股数据暂缺，以下策略主要基于A国内部因素..." |
| A股指数部分缺失 | 已有指数正常展示，缺失的显示"—"，AI 文本中注明 | "科创50数据暂缺，从创业板指走势推测..." |
| WebSearch 数据质量差 | 采用多个关键词交叉搜索，取可信度最高的数据源 | 中英文交叉验证关键数据 |
| yfinance 限流 | 增加请求间隔(0.5s)，自动降级到 WebSearch | 脚本内置 retry 机制 |
| 非交易日触发 | 提示今日非交易日，不执行完整流程 | 周末/节假日 → 输出周末特刊或跳过 |

---

## 七、质量自检 Checklist

### 数据完整性（4项）
- [ ] 美股三大指数点位和涨跌幅已获取
- [ ] 全球主要市场数据（至少亚太+汇率）已更新
- [ ] 当日/本周重磅事件已标注（带时间和影响分析）
- [ ] A股前一交易日行情数据准确（含沪深300）

### 策略质量（4项）
- [ ] 方向判断明确（偏多/偏空/震荡），不含糊其辞
- [ ] 板块方向每个都有明确的"为什么"（逻辑支撑）
- [ ] 至少提到一个具体的上证支撑/压力位
- [ ] 外部风险至少列出 2 项

### 报告格式（5项）
- [ ] 包含仓位建议和参与节奏
- [ ] 心态管理模块已填充（含情绪色彩类）
- [ ] 操作纪律条目已填充（4条结构化纪律）
- [ ] 全球市场分析段已填充（1-2句对A股影响分析）
- [ ] 见底信号监控为表格格式

### 美股去重规则
- [ ] 美股详细数据表格只含三大指数（道琼斯/标普500/纳斯达克）
- [ ] VIX/半导体/英伟达/特斯拉/原油/黄金 在扩展网格卡片中展示，不在表格中重复出现

---

## 八、其他格式规范

### 市场定调
- 字数：100-200字
- 内容：一句话概括昨日市场状态 + 一句话预判今日方向
- 格式：纯文本，无需 HTML 标签

### 隔夜美股影响
- 字数：100-150字
- 内容：美股三大指数表现 + 对A股影响判断
- 格式：纯文本

### 板块方向
- 格式：HTML 表格
- 内容：3-4个板块，每个包含优先级、板块名、星级、核心逻辑

### 风险提示
- 格式：HTML div 列表
- 数量：3-4条风险
- 每条包含标题和描述

### 操作策略
- 格式：HTML 列表
- 数量：4条策略

### 颜色规范（中国股市）
- 涨：红色 `#ff5252` / CSS类 `up`
- 跌：绿色 `#69f0ae` / CSS类 `down`
- 持平：灰色
