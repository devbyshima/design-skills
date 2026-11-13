# Changelog

Every change people using these skills would notice, newest first. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Installs read the repository at `HEAD`, so a version marks a snapshot rather than what gets installed. The plugin's `version` in `.claude-plugin/plugin.json` matches the latest one. How to cut a release is in [CONTRIBUTING.md](CONTRIBUTING.md#releasing).

## [Unreleased]

### Added

- Four slides from the example deck at the top of the README, as the builder previews them.

## [0.1.0] - 2026-11-13

The first release.

### Added

- one-idea-slides: write a talk as one JSON file and get a calm, one-idea-a-slide PowerPoint deck in a keynote style, with big numbers in one accent colour, a source on every claim, and the whole script with timings in the presenter notes. A Python builder lays out every slide, checks it, writes the `.pptx` and draws a PNG preview of each slide, so the agent can see what it made and fix it. A slide's label sits above a full-slide film or picture.
- A GitHub Release for each `v*` tag, after the skills' tests pass.

[Unreleased]: https://github.com/devbyshima/design-skills/compare/v0.1.0...main
[0.1.0]: https://github.com/devbyshima/design-skills/releases/tag/v0.1.0
