import { readFileSync } from "node:fs"
import { resolve } from "node:path"
import { describe, expect, it } from "vitest"

const srcRoot = resolve(import.meta.dirname, "..")

describe("global styles", () => {
  it("loads the global overrides after page styles", () => {
    const main = readFileSync(resolve(srcRoot, "main.ts"), "utf8")
    const globalIndex = main.indexOf('./styles/global.css')

    expect(globalIndex).toBeGreaterThan(main.indexOf('./style.css'))
    expect(globalIndex).toBeGreaterThan(main.indexOf('./media.css'))
    expect(globalIndex).toBeGreaterThan(main.indexOf('./retry.css'))
  })

  it("keeps the shared radius in the global stylesheet", () => {
    const globalStyles = readFileSync(resolve(import.meta.dirname, "global.css"), "utf8")

    expect(globalStyles).toContain("--radius: 10px")
    expect(globalStyles).toContain(".ant-tag.ant-tag")
    expect(globalStyles).toContain(".history-action-btn.ant-btn")
    expect(globalStyles).toContain("border-radius: var(--radius) !important")
  })

  it("does not leave hard-coded non-zero radii in page styles", () => {
    const pageStyles = ["style.css", "media.css", "retry.css"]
      .map(file => readFileSync(resolve(srcRoot, file), "utf8"))
      .join("\n")
    const hardCodedRadius = /border(?:-[a-z-]+)?-radius:\s*(?!0(?:\s|;|!))\d+px/gi

    expect(pageStyles.match(hardCodedRadius)).toBeNull()
  })
})
