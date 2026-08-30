# Vendored tooling

## `okf_validate.py`

Deterministic conformance checker for the Open Knowledge Format (OKF) v0.1,
used by CI to validate this repository's own `.okf/` knowledge bundle.

Vendored from [GoogleCloudPlatform/knowledge-catalog](https://github.com/GoogleCloudPlatform/knowledge-catalog)
at commit `ee67a5ca`, licensed **Apache-2.0** — see [`APACHE-2.0.txt`](APACHE-2.0.txt).

This file is **not** covered by the MIT license that applies to the rest of this
repository. It is vendored rather than depended upon so that CI has no network
requirement and no extra package to install beyond `pyyaml`.

```bash
python3 tools/okf_validate.py .okf --strict
```
