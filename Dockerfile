# dastgate — OWASP ZAP + the dastgate CLI, for the scheduled DAST CronJob.
# (Nuclei is added in a later phase.) Build with the version as the image tag:
#   docker build -t ghcr.io/magmamoose/dastgate:0.1.0 .
FROM ghcr.io/zaproxy/zaproxy:stable

USER root
WORKDIR /opt/dastgate

COPY pyproject.toml README.md ./
COPY src/ ./src/
COPY automation/ /opt/dastgate/automation/

# Install into an isolated venv (avoids PEP 668 "externally-managed" on the base
# image's system Python) and expose the console script on PATH.
RUN python3 -m venv /opt/dastgate/venv \
    && /opt/dastgate/venv/bin/pip install --no-cache-dir . \
    && ln -sf /opt/dastgate/venv/bin/dastgate /usr/local/bin/dastgate \
    && chown -R zap:zap /opt/dastgate

ENV DASTGATE_AUTOMATION_DIR=/opt/dastgate/automation \
    DASTGATE_TARGETS_FILE=/etc/dastgate/targets.yaml

USER zap
ENTRYPOINT ["dastgate"]
CMD ["run", "--all"]
