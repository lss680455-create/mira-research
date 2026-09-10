# 证据面契约（evidence-log.csv）

> 硬约束：**没有进证据日志的东西，不算证据；进了日志但已过期的证据，必须在刷新报告里显式降级。**

canonical 载体是每个 case 目录下的 `evidence-log.csv`。文件名与列语义都是契约的一部分：`mira validate` 逐行校验，`mira refresh` 逐行判定新鲜度，`mira report` 按列统计。

## 1. 版本与列序

| 版本 | 列数 | 状态 |
| --- | --- | --- |
| v1.2 | 22 列（canonical） | 新 case 必须使用 |
| v1.1 | 前 20 列 | legacy，可读入，校验时 warn |
| v1 | 前 15 列 | legacy，可读入，校验时 warn |

迁移规则：**纯追加**——版本演进只允许在尾部追加列，不改变既有列的顺序与语义。列序是契约的一部分，不允许重排。

## 2. 22 列定义（v1.2）

枚举列的取值一律引用 `schemas/vocab.json`（下表括号内为 token 数）。

| # | 列名 | 必填 | 说明 |
| --- | --- | --- | --- |
| 1 | `source_id` | ✅ | 行级唯一 id；被 `upstream_sources` 引用 |
| 2 | `claim_area` | ✅ | 分析面：business_model / financial_quality / valuation_context / … |
| 3 | `claim_type` | ✅ | 声明类型 · claim_type（14）：fact / reported_metric / company_claim / guidance / target / commitment / forecast / assumption / interpretation / opinion / market_pricing / sentiment / rumor_signal / derived_calculation |
| 4 | `claim_text` | ✅ | 声明文本（原文或忠实摘要；双语来源保留口径） |
| 5 | `source_speaker` | ✅ | 来源主体（文件 / 机构 / 人） |
| 6 | `verification_status` | ✅ | 验证状态 · verification_status（7）：verified / disclosed / claimed / estimated / modeled / unverified / contradicted |
| 7 | `authority_level` | ✅ | 来源层级 · authority_level（6）：L1 一手披露 → L3 二手可核 → L5 传闻 → L6 派生合成 |
| 8 | `source_date` | ✅ | 来源发布日，`YYYY-MM-DD` |
| 9 | `as_of_date` | ✅ | 观察日（引用该证据时点），`YYYY-MM-DD` |
| 10 | `url_or_path` | ✅ | 链接或仓库内路径 |
| 11 | `used_by_agent` | ✅ | 消费该行的研究角色 |
| 12 | `used_by_skill` | ✅ | 消费该行的技能 / 工作流 |
| 13 | `confidence` | ✅ | 记录者置信度 · confidence（3）：high / medium / low |
| 14 | `upstream_sources` | ✅ | 上游 `source_id` 列表（分号分隔）；派生行必填 |
| 15 | `notes` | ✅ | 备注：降级控制、`original_excerpt=` 原文片段等 |
| 16 | `evidence_category` | ✅ | 证据姿态 · evidence_category（12）：verified_fact / reported_fact / company_statement / management_guidance / market_pricing / assumption / inference / estimate / weak_signal / stale / contradicted / unknown |
| 17 | `freshness_status` | ✅ | 新鲜度 · freshness_status（5）：current / acceptable_for_period / preliminary / stale / unknown |
| 18 | `conflict_status` | ✅ | 冲突状态 · conflict_status（4）：none / unresolved / contradicted / not_checked |
| 19 | `treatment` | ✅ | 处理方式 · treatment（8）：use_normally / attribute / sensitize / haircut / source_gap / monitor / exclude / open_item |
| 20 | `readiness_impact` | ✅ | 可支撑程度 · readiness_impact（6）：supports_durable_conclusion / supports_working_view / monitoring_only / blocks_actionability / blocks_publication / not_material |
| 21 | `source_language` | ✅ | 来源语言 · source_language（5）：zh-CN / en / ja / ko / not_applicable 【v1.2 新增】 |
| 22 | `translation_basis` | ✅ | 翻译依据 · translation_basis（6）：not_translated / mira_translation / provider_translation / official_translation / bilingual_source / not_applicable 【v1.2 新增】 |

> 必填口径：canonical 表要求 22 列全列非空；无值请填写显式占位（如 `not_applicable`），不要留空。legacy 表缺列由版本检查统一提示。

## 3. 校验分层

1. **结构层**：表头识别与列序、必填非空、11 个枚举列（9 + v1.2 的 `source_language` / `translation_basis`）、日期格式；
2. **业务层**：跨字段规则（见下）；
3. **语义层**：每行可转换为 `evidence.schema.json` 记录（`rows_as_records`），由 `mira validate` 串联执行。

## 4. 业务规则一览

| # | 触发条件 | 判定 | 结果 |
| --- | --- | --- | --- |
| 1 | `claim_type=derived_calculation` 或 `authority_level=L6` | `upstream_sources` 为空或 `not_applicable` | **error**：派生必须可追溯 |
| 2 | `claim_type=rumor_signal` | `confidence=high` | **error**：传闻不得高置信 |
| 3 | `evidence_category=verified_fact` | `verification_status=unverified` | **error**：姿态矛盾 |
| 4 | `readiness_impact=supports_durable_conclusion` 且姿态 ∈ {unknown, weak_signal, stale, contradicted} | `notes` 为空 | **error**：弱姿态不得无说明背重结论 |
| 5 | 同上，但 `notes` 已记录降级控制 | — | **warn**：已按 notes 降级处理 |
| 6 | 判断性 claim（guidance / company_claim / commitment / target）使用 mira/provider 翻译且 `notes` 缺 `original_excerpt=` | — | **warn**：建议保留原文片段 |
| 7 | 表头为 v1 / v1.1 | — | **warn**：建议迁移到 v1.2 |

## 5. 与 vocab.json 的关系

11 个枚举列全部通过 `$ref` 引用统一词表；`mira validate --all` 会对词表自身与全部引用做自检。**不要在 CSV 之外另建词表副本**——词表只有一个来源。

## 6. 常见操作

- **新增证据行**：22 列填全；派生行必须给上游 id；传闻行 `confidence` 最高 medium；
- **历史行情类证据**：`freshness_status=acceptable_for_period`（按期间可接受），而不是 `stale`；
- **快照类证据**（当前价、估值倍数）：越期即 `stale`，使用前必须刷新；
- **冲突证据**：`conflict_status=unresolved` + `treatment=monitor` 或 `open_item`，不允许静默丢一边；
- **翻译来源**：非中英文来源用 `source_language` 标注原文语言，翻译行的 `notes` 里保留 `original_excerpt=`。
