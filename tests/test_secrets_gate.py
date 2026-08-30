"""Push is the point of no return, so this gate is the last thing between an
agent and a public git history.

**No fixture here contains a complete credential literal.** Every value is built
by concatenation at runtime. A test file full of realistic-looking tokens gets
blocked by GitHub push protection and trips every scanner downstream — which is
exactly what happened the first time this file was written.
"""

import pytest

from longhaul.gates.secrets import SecretsGate

# Shape-valid, value-nonsense, and never present as a whole string in the source.
GH = "ghp_" + "A" * 36
GH_PAT = "github_" + "pat_" + "B" * 30
ANTHROPIC = "sk-" + "ant-" + "api03-" + "C" * 30
AWS = "AKIA" + "I" * 16
SLACK = "xox" + "b-" + "1" * 12 + "-" + "d" * 16
STRIPE = "sk_" + "live_" + "e" * 24
GOOGLE = "AIza" + "F" * 35
TELEGRAM = "1234567890" + ":" + "G" * 35


def check(body, path="src/app.py"):
    header = f"--- a/{path}\n+++ b/{path}\n@@ -0,0 +1,1 @@\n"
    return SecretsGate().check(header + body)


def blocking(result):
    return [f for f in result.findings if f.severity == "block"]


@pytest.mark.parametrize(
    "value",
    [GH, GH_PAT, ANTHROPIC, AWS, SLACK, STRIPE, GOOGLE, TELEGRAM],
    ids=["github", "github-pat", "anthropic", "aws", "slack", "stripe", "google", "telegram"],
)
def test_blocks_known_credential_shapes(value):
    assert blocking(check(f"+SECRET_VALUE = '{value}'"))


def test_blocks_a_private_key_header():
    header = "-----BEGIN " + "RSA PRIVATE KEY" + "-----"
    assert blocking(check(f"+{header}"))


def test_an_allow_pragma_suppresses_the_block_but_warns():
    """Fixtures and docs need an escape hatch — but never a silent one."""
    line = f"+SECRET_VALUE = '{GH}'  # longhaul: allow-secret (test fixture)"
    result = check(line)
    assert not blocking(result)
    assert [f.severity for f in result.findings] == ["warn"]


def test_an_interpolation_hole_is_not_a_secret():
    assert not blocking(check("+TOKEN = '{fake_token}'"))


def test_blocks_a_credential_embedded_in_a_git_remote():
    """The shape of a PAT found sitting in a real .git/config during this project.

    That token was pasted verbatim into this file on the first attempt and
    GitHub push protection rejected the push. Hence: no literals here.
    """
    line = f"+\turl = https://someuser:{GH}@github.com/owner/repo.git"
    assert blocking(check(line, path=".git/config"))


def test_blocks_a_generic_secret_assignment():
    assert blocking(check("+password = 'c0rrectH0rseBattery'"))


@pytest.mark.parametrize(
    "line",
    [
        "+api_key = 'your-key-here'",
        "+token = '<YOUR_TOKEN>'",
        "+password = 'xxxxxxxx'",
        "+secret = '${SECRET}'",
        "+api_key = 'changeme'",
        "+token = 'REDACTED'",
    ],
)
def test_allows_placeholders_so_docs_and_examples_still_work(line):
    assert not blocking(check(line)), line


def test_allows_reading_a_secret_from_the_environment():
    assert not blocking(check("+token = os.environ['ANTHROPIC_API_KEY']"))


def test_blocks_a_committed_env_file():
    assert blocking(check("+FOO=bar", path=".env"))
    assert blocking(check("+FOO=bar", path="config/.env.production"))


def test_allows_an_env_example():
    assert not blocking(check("+FOO=your-value", path=".env.example"))


def test_ordinary_code_passes():
    assert not blocking(check("+    return hashlib.sha256(data).hexdigest()"))


def test_reports_a_count():
    assert check("+x = 1").checked == 1


def test_the_pragma_covers_the_line_after_it():
    """A credential is often inside an expression the comment cannot share a
    line with, so a preceding-line pragma has to work."""
    diff = (
        "--- a/tests/fixtures.py\n+++ b/tests/fixtures.py\n@@ -0,0 +1,2 @@\n"
        "+    # longhaul: allow-secret — synthetic fixture\n"
        f"+    url = 'https://user:{GH}@example.com/a/b.git'\n"
    )
    result = SecretsGate().check(diff)
    assert not blocking(result)
    assert [f.severity for f in result.findings] == ["warn"]


def test_the_pragma_does_not_cover_two_lines_later():
    """One line of cover, not a blanket."""
    diff = (
        "--- a/tests/fixtures.py\n+++ b/tests/fixtures.py\n@@ -0,0 +1,3 @@\n"
        "+    # longhaul: allow-secret\n"
        "+    unrelated = 1\n"
        f"+    url = 'https://user:{GH}@example.com/a/b.git'\n"
    )
    assert blocking(SecretsGate().check(diff))
