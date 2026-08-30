# Neon Drift

A one-thumb Android arcade game. A dot travels a closed loop; a tap reverses its
direction. Obstacles move along the same loop, and the player survives by timing
reversals. Every ten levels the loop's shape changes.

Flutter + Flame, Android only, no backend, no accounts, no network calls.

## Done looks like

- An installable debug APK produced by CI on every push.
- Thirty levels, each verified completable by a headless bot before it ships.
- A cold start to playable in under two seconds on a mid-range device.
- A settings screen with sound and haptics toggles that persist.
- No crash across a full run of all thirty levels, driven headlessly.
- A store-ready icon, a feature graphic, and four screenshots.

## Constraints

- Package name `com.cybiqon.neondrift`.
- **`lib/engine/` may not import Flutter or Flame.** The engine is pure Dart, so
  the whole game can be played headlessly under `dart run` — that is what makes
  "every level is verified completable" a fact rather than a claim. Enforce it
  with a check in CI, not with discipline.
- Levels are data, not code. Adding a level must not require a new class.
- No ads and no analytics in this build.
- Assets must be either originally generated or permissively licensed, with
  provenance recorded in `assets/CREDITS.md`.

## Out of scope

Deliberately not in these fourteen days:

- Online leaderboards, accounts, or any backend.
- In-app purchases or a remove-ads product.
- iOS. The project is Android-only for now.
- Localisation beyond English.
- A tutorial. The first three levels teach the mechanic by design instead.

## Decisions I want to make myself

- The final palette and the app icon — propose options, do not pick.
- Anything that adds a runtime dependency beyond Flutter and Flame.
- The difficulty curve past level 20, once there is something to play.
