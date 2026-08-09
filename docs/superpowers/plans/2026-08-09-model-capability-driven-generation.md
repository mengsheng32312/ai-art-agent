# 模型能力驱动生成实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让用户先选择五类创作任务，再由模型能力档案筛选模型、展示必需输入，并由后端显式选择对应的 ComfyUI 工作流。

**Architecture:** 后端以 `creation_type` 作为生成请求的唯一任务语义，模型目录附加可持久化的能力档案，提交前完成能力和输入校验，再路由到五个独立工作流入口。前端保留图片/视频两页，通过统一能力字段筛选模型并动态切换表单。

**Tech Stack:** Vue 3、TypeScript、Pinia、Ant Design Vue、Vitest；FastAPI、Pydantic、pytest；ComfyUI API。

## Global Constraints

- 保留现有图片生成和视频生成两个页面。
- 只实现已确认的五种任务：文生图、图生图、文生视频、图生视频、视频生视频。
- 未确认能力的模型默认不可用于生成，用户可在模型管理中修正并保存。
- 保留旧请求字段仅用于兼容已有历史数据，新生成逻辑只依据 `creation_type`。
- 每个任务按测试先行完成，只运行相关模块测试；全部相关测试通过后提交并推送当前功能分支。

---

### Task 1：建立模型能力档案与持久化接口

**Files:**
- Create: `backend/app/capabilities.py`
- Modify: `backend/app/schemas.py`
- Modify: `backend/app/models.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_capabilities.py`
- Modify: `backend/tests/test_models.py`

- [x] 先写能力推断、未知模型禁用、用户覆盖保存/读取的失败测试。
- [x] 增加五类 `CreationType`、能力要求、模型能力档案和更新请求结构。
- [x] 为当前已支持的标准图片检查点、AnimateDiff 和 Wan 工作流建立最小内置规则。
- [x] 将能力档案附加到模型目录，新增本地能力覆盖的读写接口。
- [x] 运行 `pytest backend/tests/test_capabilities.py backend/tests/test_models.py -q`。

### Task 2：按明确任务路由五种工作流

**Files:**
- Modify: `backend/app/comfy/workflow.py`
- Modify: `backend/app/main.py`
- Modify: `backend/tests/test_workflow.py`
- Modify: `backend/tests/test_generation.py`

- [x] 先写五类任务分别进入正确构建器、缺少参考输入被拒绝的失败测试。
- [x] 增加统一 `build_workflow` 路由及五个独立任务构建入口。
- [x] 后端提交前校验模型能力、参考输入和必需组件，返回中文错误。
- [x] 生成接口不再根据参考文件是否存在反推任务类型。
- [x] 运行 `pytest backend/tests/test_workflow.py backend/tests/test_generation.py -q`。

### Task 3：前端接入任务类型与模型筛选

**Files:**
- Modify: `frontend/src/lib/api.ts`
- Create: `frontend/src/lib/modelCapabilities.ts`
- Create: `frontend/src/lib/modelCapabilities.test.ts`
- Modify: `frontend/src/stores/generation.ts`
- Modify: `frontend/src/stores/generation.test.ts`
- Modify: `frontend/src/App.vue`

- [x] 先写五类任务筛选、未知能力禁用、任务切换清理旧值的失败测试。
- [x] 补齐前端能力档案和 `creation_type` 类型。
- [x] 用能力档案筛选当前任务可选模型，并在切换任务时清理不兼容模型和参考输入。
- [x] 将前端必填校验改为依据 `creation_type`。
- [x] 运行对应 Vitest 文件。

### Task 4：调整图片/视频动态生成表单

**Files:**
- Modify: `frontend/src/components/GenerationForm.vue`
- Modify: `frontend/src/views/GenerateView.vue`
- Modify: `frontend/src/views/VideoView.vue`
- Create: `frontend/src/components/GenerationForm.test.ts`

- [x] 先写图片两类、视频三类切换与参考媒体必填显示的失败测试。
- [x] 图片页增加文生图/图生图选择，视频页保留三类选择并改用明确任务值。
- [x] 根据任务显示参考图或参考视频，并只展示兼容模型。
- [x] 选中模型后展示中文用途、支持能力、必需组件和推荐参数。
- [x] 运行 GenerationForm 组件测试及相关 store 测试。

### Task 5：增加模型能力设置并完善工作流导入

**Files:**
- Modify: `frontend/src/views/ModelsView.vue`
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/lib/workflow.ts`
- Modify: `frontend/src/lib/workflow.test.ts`
- Create: `frontend/src/views/ModelsView.test.ts`

- [x] 先写能力设置保存/刷新和导入工作流识别任务类型的失败测试。
- [x] 在模型管理页增加能力状态、能力标签和 Ant Design Vue 设置弹窗。
- [x] 保存用户修正并刷新模型目录。
- [x] 导入工作流时根据节点补全五类任务及模型能力线索。
- [x] 运行 ModelsView 与 workflow 相关测试。

### Task 6：阶段收口

**Files:**
- Modify: `docs/superpowers/plans/2026-08-09-model-capability-driven-generation.md`

- [x] 运行上述相关后端测试和前端测试，不执行无关全项目回归。
- [x] 标记完成项，检查工作区只包含本功能改动。
- [x] 提交并推送 `codex/complete-mvp`。
