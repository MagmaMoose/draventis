"""dastgate — scheduled DAST (OWASP ZAP + Nuclei) that reimports into DefectDojo.

dastgate runs scheduled ZAP (Automation Framework) and Nuclei scans against
already-deployed targets and reimports the results into DefectDojo over its REST
API. The DefectDojo client is stdlib ``urllib`` and failure-isolated: an upload
error never fails a scan.

Module map (see ``docs/architecture.md``):

- :mod:`dastgate.model`      — typed config dataclasses (``Target``, ``ScanPolicy`` ...)
- :mod:`dastgate.config`     — load/validate ``targets.yaml``
- :mod:`dastgate.zap`        — pick + run the ZAP Automation Framework plan
- :mod:`dastgate.nuclei`     — run Nuclei
- :mod:`dastgate.defectdojo` — ``reimport-scan`` client (urllib, failure-isolated)
- :mod:`dastgate.__main__`   — the ``dastgate run`` CLI
"""

from __future__ import annotations

__version__ = "0.1.0"
