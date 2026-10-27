# Reference engine for qc2c-build. Pinned images and uv.lock make builds byte-identical
# across machines of the same architecture (linux/amd64 in CI).
FROM ghcr.io/astral-sh/uv:0.13.5@sha256:32a7bb39b496babbd997b0a39a4d66c126bdaf5661b302bf6f06abda8deca6ff AS uv

FROM python:3.12-slim@sha256:a0f57064cbdcd6285fa45f51237ab0b35ea8ebaed06a1f5973e89e19dfb86704
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH=/opt/venv/bin:$PATH \
    MPLCONFIGDIR=/tmp/matplotlib \
    QC2C_INPUT_DIR=/data/input \
    QC2C_OUTPUT_DIR=/data/output \
    QC2C_PACKAGES_DIR=/packages \
    QC2C_CONFIG=/app/qc2c.toml
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --all-extras --group dev
COPY src ./src
COPY qc2c.toml ./
RUN uv sync --frozen --all-extras --group dev --no-editable \
    && useradd --uid 1000 --create-home builder
USER 1000
ENTRYPOINT ["qc2c-build"]
