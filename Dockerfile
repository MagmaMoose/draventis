# dastgate scanner image.
#
# Built on the official ZAP image (ZAP + JRE + headless browsers for
# browser-based OIDC auth), plus the Nuclei binary and the `dastgate` Python
# package. Runs as the non-root `zap` user the base image provides.
#
#   docker build -t dastgate:local .
#   docker run --rm -e DEFECTDOJO_URL=... -e DEFECTDOJO_TOKEN=... \
#     -v "$PWD/targets.yaml:/config/targets.yaml:ro" \
#     dastgate:local run --all --config /config/targets.yaml
FROM ghcr.io/zaproxy/zaproxy:stable

# Pin the Nuclei release. Override at build time: --build-arg NUCLEI_VERSION=x.y.z
ARG NUCLEI_VERSION=3.3.7
ARG TARGETARCH=amd64

USER root

# Install Nuclei from the pinned GitHub release.
RUN set -eux; \
    apt-get update && apt-get install -y --no-install-recommends unzip ca-certificates; \
    curl -fsSL -o /tmp/nuclei.zip \
      "https://github.com/projectdiscovery/nuclei/releases/download/v${NUCLEI_VERSION}/nuclei_${NUCLEI_VERSION}_linux_${TARGETARCH}.zip"; \
    unzip -o /tmp/nuclei.zip -d /usr/local/bin nuclei; \
    chmod +x /usr/local/bin/nuclei; \
    rm -f /tmp/nuclei.zip; \
    apt-get purge -y unzip; apt-get autoremove -y; rm -rf /var/lib/apt/lists/*; \
    nuclei -version

# Install the dastgate package.
COPY pyproject.toml README.md /src/
COPY src /src/src
RUN python3 -m pip install --no-cache-dir --break-system-packages /src && rm -rf /src

# Ship the ZAP Automation Framework plans dastgate renders per target.
COPY automation /automation

USER zap
WORKDIR /zap/wrk

ENTRYPOINT ["dastgate"]
CMD ["run", "--all", "--config", "/config/targets.yaml", "--plans-dir", "/automation"]
