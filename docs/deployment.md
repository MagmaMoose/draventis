# Deployment

dastgate installs on any Kubernetes cluster with Helm. It has no hard dependency
on any particular secret store, ingress, or GitOps tool.

## Quick start

```bash
helm install dastgate ./charts/dastgate \
  --namespace security --create-namespace \
  --set defectDojo.url=https://defectdojo.example.com \
  --set secret.defectDojoToken=$DEFECTDOJO_TOKEN \
  --set targets[0].name=my-site \
  --set targets[0].url=https://my-site.example.com \
  --set targets[0].policy=baseline \
  --set targets[0].schedule=nightly
```

For anything beyond one target, use a values file instead of `--set`:

```yaml
# my-values.yaml
defectDojo:
  url: https://defectdojo.example.com
  productType: MyOrg
nuclei:
  enabled: true
targets:
  - name: my-site
    url: https://my-site.example.com
    policy: baseline
    schedule: nightly
  - name: app-staging
    url: https://app.staging.example.com
    product: myorg/app
    policy: full            # active, staging only
    schedule: weekly
schedules:
  weekly:
    enabled: true
```

```bash
helm install dastgate ./charts/dastgate -n security --create-namespace \
  -f my-values.yaml \
  --set secret.defectDojoToken=$DEFECTDOJO_TOKEN
```

!!! warning "Keep secrets out of your values file"
    Pass `secret.defectDojoToken` (and any scan credentials) via `--set`,
    `--set-file`, `helm secrets`, or an ExternalSecret. Never commit them.

## What gets created

| Object | Purpose |
|---|---|
| `CronJob` (one per enabled schedule) | Runs `dastgate run --schedule <name>` |
| `ConfigMap` | The rendered `targets.yaml`, mounted at `/config` |
| `Secret` *or* `ExternalSecret` | DefectDojo token + scan credentials (`envFrom`) |
| `ServiceAccount` | No RBAC, token not mounted; dastgate needs no cluster API |

## The image

The chart defaults to the published upstream image
(`ghcr.io/magmamoose/dastgate`, tag = chart `appVersion`). To run your own build,
push it and override:

```bash
--set image.repository=registry.example.com/dastgate --set image.tag=1.2.3
```

## Secrets: plain Secret (default) vs External Secrets Operator

**Plain Secret (default)**: works on any cluster, no extra operators. The chart
creates a `Secret` from `secret.defectDojoToken` and `secret.env`.

**External Secrets Operator**: if you run [ESO](https://external-secrets.io/),
have it materialise the Secret from your store (Vault, AWS/GCP/Azure/OCI, …):

```yaml
externalSecret:
  enabled: true
  secretStoreRef:
    name: cluster-secret-store
    kind: ClusterSecretStore
  data:
    - secretKey: DEFECTDOJO_TOKEN
      remoteRef:
        key: dastgate-defectdojo-token
    - secretKey: ZAP_USER
      remoteRef:
        key: dastgate-scan-user
    - secretKey: ZAP_PASS
      remoteRef:
        key: dastgate-scan-pass
```

When `externalSecret.enabled=true` the chart emits an `ExternalSecret` (named the
same as the plain Secret would be) and does not template the `secret` values, so
the CronJob is unchanged.

## Trigger a scan on demand

CronJobs only fire on schedule. To run one immediately:

```bash
kubectl -n security create job --from=cronjob/dastgate-nightly dastgate-manual
kubectl -n security logs -f job/dastgate-manual
```

## Verify the rendered config

```bash
helm template dastgate ./charts/dastgate -f my-values.yaml \
  --show-only templates/configmap.yaml
```

## GitOps

The chart is a plain Helm chart. Reference it from Argo CD, Flux
`HelmRelease`, or `helm install` in CI. Nothing in the chart assumes a specific
GitOps controller.

## Operational notes

- `concurrencyPolicy: Forbid` + `activeDeadlineSeconds` stop a hung scan from
  piling up or running forever.
- Heavy active scans can be pinned to specific nodes via `nodeSelector` /
  `tolerations` / `affinity`.
- An upload failure never fails the scan. Check CronJob logs for
  `[dastgate] upload failed (non-fatal)`.
