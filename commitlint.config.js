/** @type {import('@commitlint/types').UserConfig} */
export default {
  extends: ["@commitlint/config-conventional"],
  rules: {
    // Allowed types
    "type-enum": [
      2,
      "always",
      [
        "feat",     // new feature
        "fix",      // bug fix
        "docs",     // documentation only
        "style",    // formatting, no logic change
        "refactor", // neither fix nor feature
        "perf",     // performance improvement
        "test",     // adding/fixing tests
        "build",    // build system or external deps
        "ci",       // CI/CD changes
        "chore",    // maintenance
        "revert",   // revert a commit
      ],
    ],
    // Allowed scopes (service names + shared)
    "scope-enum": [
      1,
      "always",
      [
        "auth",
        "farm",
        "market",
        "workers",
        "ml-crop",
        "ml-vision",
        "ai-chat",
        "dashboard",
        "go-shared",
        "ui",
        "types",
        "infra",
        "deps",
        "release",
      ],
    ],
    "subject-case": [2, "always", "lower-case"],
    "header-max-length": [2, "always", 100],
  },
};
