import { readFileSync } from "node:fs"
import { dirname, join } from "node:path"
import { fileURLToPath } from "node:url"
import { Plugin, Skill } from "@opencode/plugin"

// Resolve the skill that ships beside this plugin, so the scripts stay in their
// package directory and paths inside SKILL.md keep working after installation.
const PACKAGE_DIR = dirname(fileURLToPath(import.meta.url))
const SKILL_FILE = join(PACKAGE_DIR, "skills", "ios-simulator-skill", "SKILL.md")

/**
 * Split SKILL.md into its YAML frontmatter and Markdown body.
 *
 * OpenCode stores the body as the skill content and shows the description in
 * the model's skill list, so both are read from the same file the other agents
 * use instead of being duplicated here.
 */
function parseSkill(markdown: string): { description?: string; body: string } {
  const match = /^---\r?\n([\s\S]*?)\r?\n---[ \t]*(?:\r?\n|$)/.exec(markdown)
  if (!match) {
    return { body: markdown }
  }

  const description = match[1]
    .split(/\r?\n/)
    .find((line) => line.startsWith("description:"))
    ?.slice("description:".length)
    .trim()

  return {
    description: description || undefined,
    body: markdown.slice(match[0].length),
  }
}

export default Plugin.define({
  id: "ios-simulator-skill",
  async setup(ctx) {
    const { description, body } = parseSkill(readFileSync(SKILL_FILE, "utf8"))

    await ctx.skill.transform((editor) => {
      editor.add({
        id: Skill.ID.make("ios-simulator-skill"),
        name: Skill.Name.make("iOS Simulator"),
        description,
        path: Skill.Info.fields.path.make(SKILL_FILE),
        content: body,
      })
    })
  },
})
