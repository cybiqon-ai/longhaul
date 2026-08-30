# Writing a project profile

A profile tells the DevOps role what "build", "test" and "does it run" mean for
one stack, so it never has to guess. Profiles are YAML data, not code — writing
one requires no Python, and it is the most useful contribution to this project.

Profiles live in `src/longhaul/profiles/*.yml`. See
[`flutter-android.yml`](../src/longhaul/profiles/flutter-android.yml) for a
complete worked example.

## Shape

```yaml
name: my-stack
description: One sentence a stranger can use to tell if this is their stack.

requires:          # binaries `longhaul doctor` checks for before day 1
  - node
  - npm

commands:
  install: npm ci
  lint: npm run lint
  test: npm test
  build: npm run build
  # Report a count, not a status. Longhaul reads this number, and a run that
  # tested nothing is a failure even when the exit code is 0.
  test_count: "npm test -- --reporter=json | jq '.numTotalTests'"

artifacts:
  bundle: dist/

proof:             # what "it actually runs" means here
  kind: browser_screenshot
  steps:
    - npm run preview &
    - npx playwright screenshot http://localhost:4173 {proof_dir}/screenshot.png

gates:
  coverage_ratchet: true
  test_count_ratchet: true
  cheat: true
  secrets: true
```

## The two rules

**Report a count.** Every profile must expose a way to ask *how many tests ran*.
An exit code of 0 has already meant "did nothing" too many times for it to be
trusted as a signal. If your test runner cannot produce a count, say so in the
profile and the ratchet gate will be disabled for that stack rather than lying.

**Proof must involve running the thing.** A screenshot of the app, a booted
container answering a health check, a headless bot completing a level — anything
that fails when the build is technically valid and functionally dead. A profile
whose proof step is "the tests passed" is not finished.

## Contributing one

Open a PR with the YAML and one line in this document. If you can, include the
`.longhaul/proof/` output from a real run against a real project — that is what
tells a reviewer the proof step actually works.
