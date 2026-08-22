# docker-bake.hcl — build definition for the draventis scanner image.
#
# Consumed by the Diatreme release workflow (docker buildx bake ... default),
# which sets REGISTRY / IMAGE_NAME / VERSION from the environment and passes
# --push. Also usable locally: `docker buildx bake` or `docker buildx bake
# --set default.tags=draventis:local`.

variable "REGISTRY" {
  default = "ghcr.io"
}

variable "IMAGE_NAME" {
  default = "magmamoose/draventis"
}

variable "VERSION" {
  default = "dev"
}

# Comma-separated build platforms. amd64-only by default (fast, no emulation);
# override to "linux/amd64,linux/arm64" for a multi-arch release image.
variable "PLATFORMS" {
  default = "linux/amd64"
}

target "default" {
  context    = "."
  dockerfile = "Dockerfile"
  platforms  = split(",", PLATFORMS)
  tags = [
    "${REGISTRY}/${IMAGE_NAME}:${VERSION}",
  ]
}
