// @vitest-environment happy-dom

import { afterEach, describe, expect, it, vi } from "vitest"

import { api } from "./api"
import { createDefaultGenerationRequest } from "../stores/generation"

afterEach(() => {
  vi.unstubAllGlobals()
})

describe("API error handling", () => {
  it("formats FastAPI validation details instead of showing object text", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            detail: [
              {
                type: "string_too_short",
                loc: ["body", "controlnet", "model"],
                msg: "String should have at least 1 character",
                input: "",
              },
            ],
          }),
          { status: 422, headers: { "Content-Type": "application/json" } },
        ),
      ),
    )

    await expect(api.generate(createDefaultGenerationRequest())).rejects.toThrow(
      "ControlNet 模型不能为空",
    )
  })
})
