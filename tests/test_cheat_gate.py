"""The cheat detector must block the moves it exists to block.

Each test is a crafted diff of one specific way an agent can make a gate pass
without making the code work.
"""

from longhaul.gates.cheat import CheatGate


def check(diff: str):
    return CheatGate().check(diff)


def blocking(result):
    return [f for f in result.findings if f.severity == "block"]


def test_blocks_pytest_skip_marker():
    diff = """--- a/tests/test_auth.py
+++ b/tests/test_auth.py
@@ -1,3 +1,4 @@
+@pytest.mark.skip(reason="flaky")
 def test_token_expiry():
     assert expired(token) is True
"""
    assert blocking(check(diff)), "an added skip marker must block"


def test_blocks_jest_only_and_skip():
    diff = """--- a/src/__tests__/cart.test.ts
+++ b/src/__tests__/cart.test.ts
@@ -1,2 +1,3 @@
+it.skip("applies the discount", () => {
 it("totals the cart", () => {
"""
    assert blocking(check(diff))


def test_blocks_deleted_test():
    diff = """--- a/tests/test_billing.py
+++ b/tests/test_billing.py
@@ -1,6 +1,2 @@
-def test_refund_is_idempotent():
-    assert refund(order) == refund(order)
-
 def test_charge():
     assert charge(order).ok
"""
    result = check(diff)
    assert blocking(result)
    assert "more test(s) removed than added" in blocking(result)[0].message


def test_blocks_workflow_edit():
    diff = """--- a/.github/workflows/ci.yml
+++ b/.github/workflows/ci.yml
@@ -10,3 +10,3 @@
-      - run: pytest
+      - run: pytest || true
"""
    assert blocking(check(diff)), "CI workflow edits must escalate to a human"


def test_blocks_swallowed_exception():
    diff = """--- a/src/sync.py
+++ b/src/sync.py
@@ -4,2 +4,4 @@
     try:
         push()
+    except Exception:
+        pass
"""
    assert blocking(check(diff))


def test_blocks_continue_on_error():
    diff = """--- a/.github/workflows/build.yml
+++ b/.github/workflows/build.yml
@@ -1,2 +1,3 @@
+    continue-on-error: true
"""
    assert blocking(check(diff))


def test_warns_on_lint_config_change():
    diff = """--- a/analysis_options.yaml
+++ b/analysis_options.yaml
@@ -1,3 +1,2 @@
-    strict-casts: true
 include: package:flutter_lints/flutter.yaml
"""
    result = check(diff)
    assert any(f.severity == "warn" for f in result.findings)


def test_allows_an_honest_change():
    diff = """--- a/src/game/loop.dart
+++ b/src/game/loop.dart
@@ -12,3 +12,4 @@
   void tick(double dt) {
+    direction *= reversed ? -1 : 1;
     position += velocity * dt;
   }
"""
    result = check(diff)
    assert not blocking(result), [str(f) for f in result.findings]


def test_reports_a_count_even_when_clean():
    diff = """--- a/README.md
+++ b/README.md
@@ -1 +1,2 @@
+A line.
"""
    assert check(diff).checked == 1


def test_allows_an_exception_handler_that_actually_handles():
    diff = """--- a/src/sync.py
+++ b/src/sync.py
@@ -4,2 +4,5 @@
     try:
         push()
+    except HTTPError as exc:
+        log.warning("push failed: %s", exc)
+        raise
"""
    assert not blocking(check(diff)), "handling an error is not swallowing it"


def test_blocks_a_comment_where_handling_should_be():
    diff = """--- a/src/sync.py
+++ b/src/sync.py
@@ -4,2 +4,4 @@
     try:
         push()
+    except Exception:
+        # TODO: handle this later
"""
    assert blocking(check(diff))


def test_creating_a_ci_workflow_is_allowed():
    """A task whose acceptance criteria say "CI ships an APK" must be able to
    write one. Adding a check is building the gate, not lowering it."""
    diff = """--- /dev/null
+++ b/.github/workflows/ci.yml
@@ -0,0 +1,4 @@
+name: CI
+on: [push]
+jobs:
+  test: {runs-on: ubuntu-latest}
"""
    assert not blocking(check(diff)), [str(f) for f in check(diff).findings]


def test_modifying_an_existing_ci_workflow_still_blocks():
    diff = """--- a/.github/workflows/ci.yml
+++ b/.github/workflows/ci.yml
@@ -10,3 +10,3 @@
-      - run: pytest
+      - run: pytest || true
"""
    assert blocking(check(diff))


def test_a_new_workflow_that_disables_itself_is_still_caught():
    """Creating is allowed; creating something already toothless is not."""
    diff = """--- /dev/null
+++ b/.github/workflows/ci.yml
@@ -0,0 +1,3 @@
+name: CI
+jobs:
+    continue-on-error: true
"""
    assert blocking(check(diff))


def test_rewriting_tests_is_allowed_when_the_count_does_not_drop():
    """Blocking a net-positive rewrite teaches the agent never to touch tests,
    which is the opposite of what this gate wants."""
    diff = """--- a/tests/test_auth.py
+++ b/tests/test_auth.py
@@ -1,4 +1,6 @@
-def test_login_old():
-    assert login()
+def test_login_rejects_a_bad_password():
+    assert not login("wrong")
+def test_login_accepts_a_good_one():
+    assert login("right")
"""
    assert not blocking(check(diff)), [str(f) for f in check(diff).findings]


def test_a_net_reduction_still_blocks():
    diff = """--- a/tests/test_auth.py
+++ b/tests/test_auth.py
@@ -1,6 +1,2 @@
-def test_a():
-    assert 1
-def test_b():
-    assert 2
+def test_a():
+    assert 1
"""
    assert blocking(check(diff))


def test_a_comment_inside_a_handler_is_not_a_swallowed_error():
    """Flagging this taught nothing except to stop writing comments. What
    matters is the first line that actually does something."""
    diff = """--- a/src/server.py
+++ b/src/server.py
@@ -1,2 +1,5 @@
     try:
         serve()
+    except PortInUse as exc:
+        # 4321 is also Astro's default, so this is normal rather than a crash
+        print(f"cannot start: {exc}")
+        return 1
"""
    assert not blocking(check(diff)), [str(f) for f in check(diff).findings]


def test_a_comment_standing_in_for_handling_is_still_caught():
    diff = """--- a/src/server.py
+++ b/src/server.py
@@ -1,2 +1,4 @@
     try:
         serve()
+    except Exception:
+        # TODO: deal with this later
+        pass
"""
    assert blocking(check(diff))
