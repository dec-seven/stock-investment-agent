# 股市分析方法论知识库

## 概述

这是一个持续更新的股市分析方法论知识库，用于存储和优化分析方法。

## 目录结构

```
stock-methodology/
├── stock_morning_brief_guide.md     # 早报分析方法论主文件
├── stock_morning_brief_templates.md # 早报模板、样例表述与参考格式
├── stock_selection_guide.md         # 选股方法论
├── manifest.json                    # 元数据与更新日志
└── README.md                        # 本文件
```

## 更新流程

### 自动更新（推荐）

使用 `methodology-updater` SKILL 自动更新方法论：

```
用户：这是一份今天的早评：[粘贴文本]
```

SKILL会自动：
1. 保存样例到 `stock-samples/` 目录
2. 提取分析方法
3. 择优录取并更新方法论文件
4. 记录更新日志

### 手动更新

如果需要手动更新方法论：

1. 编辑 `stock_morning_brief_guide.md`、`stock_morning_brief_templates.md` 或 `stock_selection_guide.md`
2. 在 `manifest.json` 的 `update_log` 数组中添加更新记录
3. 更新 `last_updated` 字段

## 方法论文件说明

### stock_morning_brief_guide.md

早报分析方法论主文件，保留规则、流程和决策标准，涵盖：
- 早报模块映射
- 市场定位层
- 信号判断层
- 情绪温度分类
- 事件时间线
- 逻辑挖掘层
- 外部关联层
- 操作策略层

### stock_morning_brief_templates.md

早报模板参考文件，承接从主方法论抽离出来的模板、样例表述和展开格式，涵盖：
- 市场定位输出模板
- 信号判断参考
- 板块逻辑模板
- 外部因素模板
- 操作策略模板
- 事件时间线模板
- 板块方向与风险预警模板

### stock_selection_guide.md

包含选股方法论，涵盖：
- 题材识别
- 催化逻辑
- 个股筛选
- 时机判断

## 更新历史

查看 `manifest.json` 中的 `update_log` 数组获取完整更新历史。
