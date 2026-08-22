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
# No HEALTHCHECK: this is a batch/CronJob image (runs `dastgate run` to
# completion), not a long-running service. Kubernetes ignores Docker HEALTHCHECK
# and tracks the Job's exit status instead, so a healthcheck would be meaningless.
# kics-scan disable=b03a748a-542d-44f4-bb86-9199ab4fd2d5

# Pinned by digest for reproducible, verifiable builds (this is the multi-arch
# manifest list for the :stable tag; buildx still selects the right arch).
FROM ghcr.io/zaproxy/zaproxy:stable@sha256:781a2bdaea47324e7bab583e2263f21d257b0aee61ed51521a5be45f5f5081ef

# Pin the Nuclei release. Override at build time: --build-arg NUCLEI_VERSION=x.y.z
ARG NUCLEI_VERSION=3.3.7
# TARGETARCH is injected by BuildKit per target platform — do NOT give it a
# default, or every build would fetch the amd64 binary (broken on arm64).
ARG TARGETARCH

USER root

# Install Nuclei from the pinned GitHub release. unzip ships in the base image;
# we don't purge it (that would remove a base tool).
RUN set -eux; \
    : "${TARGETARCH:?BuildKit must supply TARGETARCH}"; \
    curl -fsSL -o /tmp/nuclei.zip \
      "https://github.com/projectdiscovery/nuclei/releases/download/v${NUCLEI_VERSION}/nuclei_${NUCLEI_VERSION}_linux_${TARGETARCH}.zip"; \
    unzip -o /tmp/nuclei.zip -d /usr/local/bin nuclei; \
    chmod +x /usr/local/bin/nuclei; \
    rm -f /tmp/nuclei.zip; \
    nuclei -version

# Install the dastgate package.
COPY pyproject.toml README.md /src/
COPY src /src/src
# The root build steps above (pip, `nuclei -version`) run with HOME=/home/zap and
# leave root-owned dotdirs there (e.g. /home/zap/.config), which would stop uid
# 1000 from writing its config at runtime (Nuclei's config dir). Hand the home
# back to uid 1000.
RUN python3 -m pip install --no-cache-dir --break-system-packages /src \
    && rm -rf /src \
    && chown -R 1000:1000 /home/zap

# Ship the ZAP Automation Framework plans dastgate renders per target.
COPY automation /automation

# Numeric USER (uid 1000 = `zap`) so the kubelet can verify runAsNonRoot even
# without an explicit runAsUser in the pod spec.
USER 1000:1000
WORKDIR /zap/wrk

ENTRYPOINT ["dastgate"]
CMD ["run", "--all", "--config", "/config/targets.yaml", "--plans-dir", "/automation"]
