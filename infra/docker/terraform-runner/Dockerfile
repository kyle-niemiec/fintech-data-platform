FROM docker.io/redpandadata/redpanda:v24.2.18 AS redpanda_tools

FROM hashicorp/terraform:1.6.6
COPY --from=redpanda_tools /opt/redpanda/libexec/rpk /usr/local/bin/rpk

WORKDIR /workspace
