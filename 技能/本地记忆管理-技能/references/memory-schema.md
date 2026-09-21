# 记忆元数据 Schema

本文件是正式结构化记忆 frontmatter 的公共字段权威来源。元数据服务于路由、追溯、时效和冲突处理，不能替代正文事实源。

## 适用范围

- 新建的正式事实、经验、知识、判断和项目状态使用本 Schema。
- 既有文件在实质修改正文、结构或元数据时迁移；机械修链接或排序不触发批量迁移。
- README、任务路由、模板、原始附件、代码和生成物不强制使用完整 Schema。

## 最小公共字段

| 字段 | 约束 |
| --- | --- |
| `id` | 库内唯一且稳定；文件移动或重命名时不改变 |
| `type` | 使用稳定记录类型，不随目录名造同义值 |
| `status` | 当前生命周期状态，不与置信度混用 |
| `recorded_at` | 首次进入记忆库的 ISO 日期/时间 |
| `source_refs` | 至少一项；优先库根相对路径或稳定 URL |
| `scope` | 主适用范围，如 `global`、`personal`、`project/<项目名>` |
| `confidence` | `confirmed`、`verified`、`inferred` 或 `unknown` |
| `sensitivity` | `public`、`internal` 或 `restricted`；秘密值仍禁止写入 |
| `supersedes` | 明确取代的旧记录 ID；没有则写 `[]` |

按需增加 `updated_at`、`last_verified` 和 `review_after`。只有真实回源核验过易变信息时才写 `last_verified`；不使用文件 mtime 冒充业务时间。

## 常用类型

| `type` | 常用扩展 | `status` 示例 |
| --- | --- | --- |
| `daily-note` | 必需 `event_date` | `active` / `superseded` / `archived` |
| `project-state` | 必需 `updated_at` | `active` / `paused` / `completed` / `archived` |
| `knowledge` | `source_date`、`topics` | `candidate` / `verified` / `superseded` |
| `lesson` | `incident_date`、`topics` | `active` / `superseded` / `archived` |
| `judgment` | `observed_at`、`topics` | `候选` / `已认可` / `已验证` / `已固化` / `已取代` |
| `profile`、`tool-state`、`skill-state`、`prompt` | 按需增加时效和关联字段 | 由各目录定义 |

## 冲突与迁移

1. 先回源确认事实和时间；不能确认时使用 `confidence: unknown`。
2. 新记录取代旧记录时写 `supersedes`，旧记录保留并改为相应的 superseded 状态。
3. 路径变化只更新 `source_refs` 和回链，不改变稳定 ID。
4. 只迁移当前任务触碰的文件；需要扩散到大量历史文件时另立维护任务。
