"""draventis — scheduled DAST (OWASP ZAP + Nuclei) that reimports into DefectDojo.

draventis runs scheduled ZAP (Automation Framework) and Nuclei scans against
already-deployed targets and reimports the results into DefectDojo over its REST
API. The DefectDojo client is stdlib ``urllib`` and failure-isolated: an upload
error never fails a scan.

Module map (see ``docs/architecture.md``):

- :mod:`draventis.model`      — typed config dataclasses (``Target``, ``ScanPolicy`` ...)
- :mod:`draventis.config`     — load/validate ``targets.yaml``
- :mod:`draventis.zap`        — pick + run the ZAP Automation Framework plan
- :mod:`draventis.nuclei`     — run Nuclei
- :mod:`draventis.defectdojo` — ``reimport-scan`` client (urllib, failure-isolated)
- :mod:`draventis.__main__`   — the ``draventis run`` CLI
"""

from __future__ import annotations

__version__ = "0.1.0"
