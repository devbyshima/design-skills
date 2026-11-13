<picture>
  <source media="(prefers-color-scheme: dark)" srcset=".github/assets/banner-dark.svg">
  <img width="480" alt="Skills for Designing with Agents" src=".github/assets/banner-light.svg">
</picture>

# Skills for Designing with Agents

[![skills.sh](https://skills.sh/b/devbyshima/design-skills)](https://skills.sh/devbyshima/design-skills)

Agent skills for things people look at, starting with slide decks.

Ask an agent for slides and you get bullet points on a template. These skills give it a style to follow, written down as sizes, colours and word counts, and a builder that checks the work and draws a preview, so the agent can see what it made and fix it before you do.

<p>
  <img src=".github/assets/slides/statement.png" width="49%" alt="A slide with one centred sentence: A vaccine is only as good as its last cold mile.">
  <img src=".github/assets/slides/number.png" width="49%" alt="A slide with one big yellow number, 1 in 4, over the line: doses spoil before they arrive.">
  <img src=".github/assets/slides/numbers.png" width="49%" alt="A slide with three numbers side by side, 10 days, 3 boxes and 0 doses lost, the last lit in yellow.">
  <img src=".github/assets/slides/closing.png" width="49%" alt="A closing slide: Thank you. Questions?">
</p>

Slides from the example deck in [one-idea-slides](./skills/slides/one-idea-slides/SKILL.md), as its builder previews them.

[Follow new skills](https://github.com/devbyshima/design-skills/releases)

## Install

```bash
npx skills@latest add devbyshima/design-skills
```

## Why use it?

Taste is hard to hand to an agent. "Make it clean" means nothing to it; "one sentence a slide, 96 px, one accent colour, a source on every number" is something it can follow and check. Each skill here is one taste turned into rules, an example, and a tool that says when the rules are broken.

For skills that keep an agent working for hours, see [devbyshima/skills](https://github.com/devbyshima/skills).

## Reference

- **[one-idea-slides](./skills/slides/one-idea-slides/SKILL.md)**: Write a talk as one JSON file and get a calm, one-idea-a-slide PowerPoint deck with its speaker notes.

[PolyForm Noncommercial 1.0.0](LICENSE): free for non-commercial use.
