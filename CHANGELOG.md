# 更新日志

本项目遵循语义化版本。版本记录中的数字均可在仓库内用命令复现。

## v1.0.0 — 2026-09-10

首个版本：将上游开源项目 Mira 重构为**契约驱动的可移植工具链**。

**上游基线**：`byteseek/Mira` @ `adddce7c6f41be309855e3c7d047e309bbe58a3a`（635 文件 / 约 6.4 MB 的案例与方法论文档库）。

### 架构优化

- **契约层（新增）**：7 个 JSON Schema 契约（`schemas/`），含统一受控词表 `vocab.json`（33 个 token 集）；全部枚举以 `$ref` 引用词表，单一事实来源；落实上游约束——`research_action` 与 `decision_type` 共用同一 token 集。
- **零依赖校验器（新增）**：`jsonschema_lite.py`，自实现 JSON Schema draft-07 子集；本地 `$ref`（JSON Pointer）自动解析，跨文件引用由 resolver 加载。
- **CLI 工具链（新增）**：`mira init / validate / refresh / report` 四个子命令（另有 `python -m mira`）；`init` 脚手架"出生即绿"；`refresh` 生成人读/机读双份刷新报告，且生成物自身通过契约校验。
- **证据面契约**：`evidence-log.csv` v1.2（22 列、列序固定）；v1（15 列）/ v1.1（20 列）按 legacy 兼容读入；三层校验（结构层 / 业务层 / 语义层）。
- **仓库瘦身**：635 文件 / 约 6.4 MB → 不足 1 MB 的可移植仓库（契约 + 工具链 + 1 个端到端样例），移除了与工具链无关的案例与冗余文档。

### 质量

- 69 个离线测试（`pytest tests/ -q`），不需要网络与 API key。
- `python -m compileall src` 通过；`mira validate --all` 全绿（7/7 项 + schema 自检 0 问题）。
- 生成物核验：`refresh-report.json` 通过 `refresh` 契约校验；`mira init` 生成的骨架直接通过 `validate`。

### 文档

- 中英双语 README（`README.md` / `README_EN.md`）与 hero 图（`docs/assets/hero.svg`）。
- `docs/ARCHITECTURE.md` / `docs/WORKFLOW.md` / `docs/EVIDENCE-CONTRACT.md`（22 列定义与全部业务规则）。
- `examples/aapl-2026-04/` 端到端样例（由上游案例裁剪重构；历史案例，不构成投资建议）。

### 许可

- 沿用上游 Apache-2.0（`LICENSE`）；上游无 NOTICE 文件。
