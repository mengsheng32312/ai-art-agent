# 模型内容筛选与新手选模实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在生成参数页按人物、风景等内容分类推荐模型，并允许用户在模型管理中修正内容标签。

**Architecture:** 内容标签归属于现有 `ModelCapabilityProfile`，后端负责默认值、关键词推断和持久化；前端纯函数负责按创作任务与内容标签筛选排序；生成表单和模型管理只消费这些接口。内容分类不进入生成请求，不改变 ComfyUI 工作流。

**Tech Stack:** FastAPI、Pydantic、Vue 3、TypeScript、Ant Design Vue、pytest、Vitest

## Global Constraints

- 第一版内容分类固定为：人物、风景、动漫、产品/静物、建筑/室内、通用。
- “新手选模”默认开启；开启时展示精准匹配和通用模型，精准匹配优先。
- 关闭时只按现有创作任务筛选。
- 只筛选 checkpoint，不影响 LoRA、VAE、ControlNet 和运动模型。
- 现有能力档案缺少 `content_tags` 时必须兼容加载。
- 只验证本次涉及模块，不执行完整回归或重新打包。

---

### Task 1: 后端内容标签档案与推断

**Files:**
- Modify: `backend/app/schemas.py`
- Modify: `backend/app/capabilities.py`
- Test: `backend/tests/test_capabilities.py`

**Interfaces:**
- Produces: `ContentTag` 类型、`ModelCapabilityProfile.content_tags`、`infer_content_tags(item: ModelItem) -> list[ContentTag]`
- Consumes: 现有 `ModelItem.name`、`filename`、`description` 与 `CapabilityStore`

- [ ] **Step 1: 写入失败测试**

```python
def test_model_content_tags_are_inferred_from_name_and_description() -> None:
    assert infer_model_capability(model("portrait-realistic.safetensors")).content_tags == ["portrait"]


def test_unknown_model_defaults_to_general_content_tag() -> None:
    assert infer_model_capability(model("v1-5-pruned-emaonly.safetensors")).content_tags == ["general"]


def test_capability_store_persists_content_tags(tmp_path: Path) -> None:
    profile = ModelCapabilityProfile(content_tags=["landscape"], confirmed=True)
    store = CapabilityStore(tmp_path / "model-capabilities.json")
    store.save("scenery.safetensors", profile)
    assert store.load("scenery.safetensors").content_tags == ["landscape"]
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `cd backend && .\.venv\Scripts\python.exe -m pytest tests\test_capabilities.py -q`

Expected: FAIL，提示 `content_tags` 或推断结果不存在。

- [ ] **Step 3: 实现最小后端支持**

```python
ContentTag = Literal["portrait", "landscape", "anime", "product", "architecture", "general"]

class ModelCapabilityProfile(BaseModel):
    content_tags: list[ContentTag] = Field(default_factory=lambda: ["general"])
```

在 `capabilities.py` 增加互不重叠的中英文关键词表，按 `name + filename + description` 小写匹配；命中时返回全部去重标签，未命中返回 `['general']`。所有内置能力档案显式使用该推断结果，用户保存档案继续优先于自动推断。

- [ ] **Step 4: 运行相关后端测试**

Run: `cd backend && .\.venv\Scripts\python.exe -m pytest tests\test_capabilities.py -q`

Expected: PASS。

- [ ] **Step 5: 提交**

```powershell
git add backend/app/schemas.py backend/app/capabilities.py backend/tests/test_capabilities.py
git commit -m "feat: classify model content tags"
```

### Task 2: 前端内容筛选纯函数与生成表单

**Files:**
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/lib/modelCapabilities.ts`
- Modify: `frontend/src/lib/modelCapabilities.test.ts`
- Modify: `frontend/src/components/GenerationForm.vue`
- Modify: `frontend/src/components/GenerationForm.test.ts`

**Interfaces:**
- Consumes: `ModelCapabilityProfile.content_tags`
- Produces: `ContentTag`、`contentTagLabels`、`filterModelsForContent(models, creationType, contentTag, beginnerMode)`

- [ ] **Step 1: 写入失败的筛选测试**

```ts
it("新手模式保留精准与通用模型并优先精准匹配", () => {
  const result = filterModelsForContent(models, "text_to_image", "portrait", true)
  expect(result.map(item => item.filename)).toEqual(["portrait.safetensors", "general.safetensors"])
})

it("关闭新手模式后显示全部创作任务兼容模型", () => {
  const result = filterModelsForContent(models, "text_to_image", "portrait", false)
  expect(result.map(item => item.filename)).toEqual([
    "portrait.safetensors", "landscape.safetensors", "general.safetensors",
  ])
})
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `cd frontend && npm.cmd test -- --run src/lib/modelCapabilities.test.ts`

Expected: FAIL，提示 `filterModelsForContent` 不存在。

- [ ] **Step 3: 实现筛选函数**

```ts
export function filterModelsForContent(
  models: ModelItem[],
  creationType: CreationType,
  contentTag: ContentTag,
  beginnerMode: boolean,
): ModelItem[] {
  const compatible = filterModelsForCreationType(models, creationType)
  if (!beginnerMode) return compatible
  return compatible
    .filter(item => item.capability_profile.content_tags.includes(contentTag)
      || item.capability_profile.content_tags.includes("general"))
    .sort((a, b) => Number(b.capability_profile.content_tags.includes(contentTag))
      - Number(a.capability_profile.content_tags.includes(contentTag)))
}
```

- [ ] **Step 4: 写入失败的生成表单交互测试**

验证表单存在“想生成的内容”和默认开启的“新手选模”；选择“人物”只出现人物与通用模型；关闭开关后出现全部任务兼容模型；切换分类后清空不匹配的当前模型；无匹配项时出现约定提示。

- [ ] **Step 5: 实现生成表单交互**

在 `GenerationForm.vue` 内保存页面级 `selectedContentTag` 与 `beginnerMode`，使用 `computed` 得到过滤模型，模型选择项展示中文内容标签。分类使用 Ant Design Vue `Select`，新手模式使用 `Switch`；筛选变化时仅在当前模型不可见时清空 `form.checkpoint`。

- [ ] **Step 6: 运行前端相关测试**

Run: `cd frontend && npm.cmd test -- --run src/lib/modelCapabilities.test.ts src/components/GenerationForm.test.ts`

Expected: PASS。

- [ ] **Step 7: 提交**

```powershell
git add frontend/src/lib/api.ts frontend/src/lib/modelCapabilities.ts frontend/src/lib/modelCapabilities.test.ts frontend/src/components/GenerationForm.vue frontend/src/components/GenerationForm.test.ts
git commit -m "feat: guide model selection by content"
```

### Task 3: 模型管理内容标签编辑

**Files:**
- Modify: `frontend/src/views/ModelsView.vue`
- Modify: `frontend/src/views/ModelsView.test.ts`

**Interfaces:**
- Consumes: `ContentTag`、`contentTagLabels`、`ModelCapabilityProfile.content_tags`
- Produces: 模型能力设置对话框中的内容标签编辑与现有 `saveCapabilities` 事件负载

- [ ] **Step 1: 写入失败测试**

```ts
test("模型能力设置可以保存内容标签", async () => {
  // 打开能力设置，选择人物与动漫，点击保存。
  expect(wrapper.emitted("saveCapabilities")?.[0]?.[0]).toMatchObject({
    filename: "model.safetensors",
    content_tags: ["portrait", "anime"],
  })
})
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `cd frontend && npm.cmd test -- --run src/views/ModelsView.test.ts`

Expected: FAIL，保存负载没有 `content_tags`。

- [ ] **Step 3: 实现内容标签编辑**

增加 `editingContentTags` 状态。打开设置时复制当前档案标签；对话框用 Ant Design Vue 多选 `Select` 展示六个中文分类；至少保留一个标签；保存时把 `content_tags` 放入现有 `ModelCapabilityUpdate`。

- [ ] **Step 4: 运行模型管理测试**

Run: `cd frontend && npm.cmd test -- --run src/views/ModelsView.test.ts`

Expected: PASS。

- [ ] **Step 5: 运行接口两端相关测试**

Run: `cd backend && .\.venv\Scripts\python.exe -m pytest tests\test_capabilities.py -q`

Run: `cd frontend && npm.cmd test -- --run src/lib/modelCapabilities.test.ts src/components/GenerationForm.test.ts src/views/ModelsView.test.ts`

Expected: 全部 PASS。

- [ ] **Step 6: 提交并推送当前功能分支**

```powershell
git add frontend/src/views/ModelsView.vue frontend/src/views/ModelsView.test.ts
git commit -m "feat: edit model content tags"
git push origin codex/complete-mvp
```

### Task 4: 重启项目

**Files:**
- No file changes.

**Interfaces:**
- Consumes: 根目录 `启动项目.bat`
- Produces: 已加载最新前后端代码的开发实例

- [ ] **Step 1: 停止当前项目的前端、后端和桌面开发进程**

只停止属于 `D:\Project\ai-art-agent\.worktrees\complete-mvp` 的进程，保留 Codex 自身进程。

- [ ] **Step 2: 启动项目**

Run: `Start-Process -FilePath "D:\Project\ai-art-agent\启动项目.bat" -WorkingDirectory "D:\Project\ai-art-agent" -WindowStyle Minimized`

- [ ] **Step 3: 验证启动端点**

检查 `http://127.0.0.1:1420/` 返回 200，`http://127.0.0.1:8000/api/health` 可访问。
