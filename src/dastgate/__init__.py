"""dastgate — scheduled DAST (OWASP ZAP + Nuclei) that reimports into DefectDojo.

Phase 0 scaffold: this package is intentionally empty. dastgate will run scheduled
ZAP (Automation Framework) + Nuclei scans against deployed/staging environments and
reimport the results into DefectDojo over its REST API, mirroring chargate's
stdlib-``urllib`` uploader ethos.

Nothing here runs yet. The intended module layout is in ``docs/DESIGN.md`` (§5.1);
see the "Status: Planning (Phase 0)" note in ``README.md``.
"""

__version__ = "0.0.0"
