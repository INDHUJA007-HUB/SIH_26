# syntax=docker/dockerfile:1.7

FROM mwader/static-ffmpeg@sha256:35a513d9b673367ef50bd4e880ac6b701d3fa2964b58bb0b2064d8d99892b9d9 AS media_tools
FROM python:3.12-slim@sha256:a0f57064cbdcd6285fa45f51237ab0b35ea8ebaed06a1f5973e89e19dfb86704 AS backend_builder
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app/backend
RUN pip install --no-cache-dir uv==0.13.4
COPY backend/pyproject.toml backend/uv.lock ./
COPY backend/tools/fetch_locked_wheels.py /tmp/fetch_locked_wheels.py
RUN uv export --quiet --frozen --no-dev --no-default-groups --no-emit-project --format requirements-txt --output-file /tmp/requirements.txt && uv export --quiet --frozen --only-group build --no-emit-project --format requirements-txt --output-file /tmp/build-requirements.txt && uv export --quiet --frozen --no-dev --no-default-groups --group build --no-emit-project --no-hashes --format requirements-txt --output-file /tmp/package-list.txt
RUN --mount=type=cache,target=/wheels python /tmp/fetch_locked_wheels.py /app/backend /tmp/package-list.txt /wheels && python -m venv .venv && .venv/bin/python -m pip install --quiet --no-index --find-links /wheels --require-hashes -r /tmp/requirements.txt && python -m venv .buildvenv && .buildvenv/bin/python -m pip install --quiet --no-index --find-links /wheels --require-hashes -r /tmp/build-requirements.txt
COPY backend/src ./src
COPY backend/migrations ./migrations
COPY backend/fixtures ./fixtures
COPY backend/alembic.ini ./
COPY output/AICTE_PS26261_Rule_Evidence_Register.json /app/output/AICTE_PS26261_Rule_Evidence_Register.json
RUN .buildvenv/bin/hatchling build -t wheel -d /tmp/dist && .venv/bin/python -m pip install --quiet --no-deps /tmp/dist/*.whl && rm -rf .buildvenv && .venv/bin/python -m pip uninstall -y pip && pip uninstall -y uv pip

FROM gcr.io/distroless/cc-debian13:nonroot@sha256:3ee00291cf386ec52a552e6a858d555debd74776eb4bfa53fa3df2cd6677515e AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 LD_LIBRARY_PATH=/usr/local/lib PATH="/app/backend/.venv/bin:/usr/local/bin" WB_PROJECT_ROOT=/app
WORKDIR /app/backend
COPY --from=backend_builder /usr/local/bin/python* /usr/local/bin/
COPY --from=backend_builder /usr/local/lib/libpython3.12.so* /usr/local/lib/
COPY --from=backend_builder /usr/local/lib/python3.12 /usr/local/lib/python3.12
COPY --from=backend_builder /usr/lib/x86_64-linux-gnu/libffi.so.8* /usr/lib/x86_64-linux-gnu/
COPY --from=backend_builder /usr/lib/x86_64-linux-gnu/libbz2.so.1.0* /usr/lib/x86_64-linux-gnu/
COPY --from=backend_builder /usr/lib/x86_64-linux-gnu/liblzma.so.5* /usr/lib/x86_64-linux-gnu/
COPY --from=backend_builder /usr/lib/x86_64-linux-gnu/libsqlite3.so.0* /usr/lib/x86_64-linux-gnu/
COPY --from=backend_builder /usr/lib/x86_64-linux-gnu/libexpat.so.1* /usr/lib/x86_64-linux-gnu/
COPY --from=backend_builder /usr/lib/x86_64-linux-gnu/libssl.so.3* /usr/lib/x86_64-linux-gnu/
COPY --from=backend_builder /usr/lib/x86_64-linux-gnu/libcrypto.so.3* /usr/lib/x86_64-linux-gnu/
COPY --from=backend_builder /usr/lib/x86_64-linux-gnu/libz.so.1* /usr/lib/x86_64-linux-gnu/
COPY --from=backend_builder --chown=65532:65532 /app /app
USER 65532:65532
ENTRYPOINT []
EXPOSE 8000
CMD ["uvicorn", "workbench.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]

FROM runtime AS parser
COPY --from=media_tools /ffprobe /usr/local/bin/ffprobe
CMD ["python", "-m", "workbench.processing.parser_runner"]

