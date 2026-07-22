"""dastgate — scheduled DAST (OWASP ZAP + Nuclei) that reimports into DefectDojo.

Phase 1: a nightly ZAP **baseline** (passive) scan against each configured target,
with the resulting report reimported into DefectDojo over its REST API — mirroring
chargate's stdlib-``urllib``, failure-isolated uploader. Nuclei and authenticated /
full-active scans are later phases; see ``docs/DESIGN.md``.
"""

__version__ = "0.1.0"
