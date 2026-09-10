# 工作流

## 四条环

Mira 工作流是一个闭环，四环各解决一个问题：

| 环 | 解决什么 | 载体 | 命令 |
| --- | --- | --- | --- |
| ① 立项 | 这次研究要回答什么、什么算证伪 | `thesis-card` + `refresh.yaml`（计划） | `mira init` → 手填 |
| ② 证据 | 每条结论的证据是哪里来的、可信到什么程度 | `evidence-log.csv` | 人工/代理填写 |
| ③ 校验 | 产物是否满足契约、证据是否过期 | 校验与刷新报告 | `mira validate` / `mira refresh` |
| ④ 监控 | 什么条件下必须回来重看 | `monitoring.json` + `refresh-report` | `mira report` 审阅 |

## 标准操作序列

### 新建 case

```bash
mira init my-case-2026-09 --title "My Case（草稿）" --object "MSFT" --market "US equity"
mira validate my-case-2026-09          # 出生即绿：init 生成的骨架直接通过校验
```

### 日常：填完内容后校验

```bash
mira validate examples/aapl-2026-04        # 单目录
mira validate --all                        # 全部样例 + schema 自检
mira validate path/to/x.yaml --schema thesis-card   # 强制按指定契约校验
mira validate --all --json > out.json      # 机器可读结果
```

### 定期：刷新检查

```bash
mira refresh examples/aapl-2026-04 --as-of 2026-09-10            # 只出报告（stdout）
mira refresh examples/aapl-2026-04 --as-of 2026-09-10 --write    # 写回 case 目录
mira refresh examples/aapl-2026-04 --format json                 # 机器可读
```

刷新引擎按 `as_of` 判定每个时间边界与触发条件，输出四态：`fresh` / `due_soon` / `expired` / `unknown`（判定口径见下）。

### 发布前：读出研究包

```bash
mira report examples/aapl-2026-04 -o /tmp/report.md
```

## 状态口径

### 时间状态（refresh）

以 `as_of` 为观察点，`stale_after` 为时间边界，`due_soon_days`（默认 30）为预警窗：

| 状态 | 条件 | 含义 |
| --- | --- | --- |
| `fresh` | `as_of < stale_after - due_soon_days` | 可直接复用 |
| `due_soon` | 落在 `stale_after` 前的预警窗内 | 应尽快安排刷新 |
| `expired` | `as_of > stale_after` | 复用前必须刷新 |
| `unknown` | 缺 `stale_after` 或不可解析 | 视为待办 |

### 论点状态（thesis-state）

`draft` → `watch` / `active` → （`upgrade_watch` / `downgrade_watch` / `narrative_watch`）→ `stale` →（刷新后回到 `active`）或 `retired`（核心假设被证伪）。

维护纪律：
- 升级为 `active` 的前提：证据链完整、刷新条件与证伪路径都已写明；
- 越过时间边界或事件边界，必须显式标 `stale`，复用前先刷新；
- 被证伪的论点标 `retired` 并在证据日志回写反证行，不允许静默删除。

### 触发条件（triggers）

| 类型 | 含义 | 例 |
| --- | --- | --- |
| `time` | 时间触发 | 越过 `stale_after` |
| `filing` | 披露触发 | 下一份财报/10-Q |
| `event` | 事件触发 | 产品发布、监管裁定 |
| `price` | 价格触发 | 跌破关键位 |
| `macro` | 宏观触发 | 利率路径变化 |
| `custom` | 自定义 | 任何需要写明的条件 |

触发状态：`pending`（挂着）→ `fired`（已触发，必须处理）→ `cleared`（已消化）；不可解析时 `unknown`。

## 术语表

| 术语 | 含义 |
| --- | --- |
| thesis card | 论点卡：一句话核心结论 + 关键变量 + 证伪路径 |
| evidence log | 证据日志：case 级 `evidence-log.csv`，见 `docs/EVIDENCE-CONTRACT.md` |
| authority level | 来源层级：L1 一手披露 → L6 派生合成 |
| freshness | 证据新鲜度：历史行情类用 `acceptable_for_period`，快照类过期即 `stale` |
| readiness impact | 该证据允许支撑到什么程度（从"支撑耐久结论"到"阻断行动性"） |
| treatment | 处理方式：正常使用 / 归因 / 敏感性 / 打折 / 记为缺口 / 监控 / 排除 |
| research_action | 研究动作（**不是交易指令**），与 decision_type 共用同一 token 集 |
| stale_after | 时间边界：越过即 `expired` |
| due_soon | 预警窗：距边界 `due_soon_days` 以内 |

## 纪律（写进工作流的硬规则）

1. **先记来源，再下结论**：任何结论句都必须能对应到证据日志中的 `source_id`；
2. **派生必须可追溯**：`derived_calculation` / L6 行必须列出上游来源 id；
3. **弱信号不背重结论**：`rumor_signal` / `weak_signal` 不得支撑耐久结论，只进监控；
4. **过期就降级**：过期证据要么刷新、要么在 reports 里显式降级，不允许"沉默地继续用"；
5. **研究动作 ≠ 交易指令**：`research_action` 只表达研究优先级与条件，不构成买卖建议。
