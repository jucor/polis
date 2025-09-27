# ---- Stage 1: Builder ----
  FROM python:3.12-slim AS builder

  # Define a build argument to signal if running in GitHub Actions
  ARG IS_GITHUB_ACTION=false
  ARG AWS_REGION

  ENV PYTHONDONTWRITEBYTECODE=1
  ENV PYTHONUNBUFFERED=1

  RUN apt-get update && \
      apt-get install -y --no-install-recommends \
          git \
          build-essential \
          cmake \
          gcc \
          g++ \
          gfortran \
          libopenblas-dev \
          curl \
      && apt-get clean && \
      rm -rf /var/lib/apt/lists/*

  WORKDIR /app

  # Copy files needed for package build (based on pyproject.toml includes)
  COPY pyproject.toml .
  COPY polismath/ ./polismath/
  COPY umap_narrative/ ./umap_narrative/
  COPY scripts/ ./scripts/
  # Copy top-level Python files referenced in pyproject.toml
  COPY *.py ./

  # Conditionally install PyTorch CPU versions if IS_GITHUB_ACTION is true
  RUN if [ "$IS_GITHUB_ACTION" = "true" ]; then \
          echo "IS_GITHUB_ACTION is true. Installing PyTorch CPU versions..."; \
          pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu \
              torch==2.8.0+cpu \
              torchvision==0.23.0+cpu \
              torchaudio==2.8.0+cpu; \
      else \
          echo "IS_GITHUB_ACTION is false or not set. Skipping explicit PyTorch CPU-specific installation."; \
          echo "PyTorch (if required) will be installed from pyproject.toml."; \
      fi

  # Install packages from pyproject.toml
  # If PyTorch was installed in the step above, pip should recognize it.
  # If IS_GITHUB_ACTION was false, PyTorch will be installed from pyproject.toml here.
  RUN pip install --no-cache-dir .

  RUN echo "--- PyTorch Check (after pyproject.toml installation) ---" && \
      pip show torch torchvision torchaudio && \
      python -c "import torch; print(f'Torch version: {torch.__version__}'); print(f'CUDA available: {torch.cuda.is_available()}')" && \
      echo "--- Looking for NVIDIA/CUDA libs ---" && \
      (ls -lhR /usr/local/lib/python3.12/site-packages/nvidia || echo "NVIDIA directory not found.") && \
      (ls -lhR /usr/local/lib/python3.12/site-packages/torch/lib/*cuda* || echo "No CUDA libs in torch/lib.")


  # EVōC will be installed via pyproject.toml dependencies
  # RUN git clone https://github.com/TutteInstitute/evoc && \
  #     cd evoc && \
  #     pip install --no-cache-dir .

  # EVōC verification
  RUN echo "--- EVōC Installation Check ---" && \
      python -c "import evoc; print(f'EVōC version: {getattr(evoc, \"__version__\", \"unknown\")}')" && \
      echo "--- EVōC imported successfully ---"

  # ---- Stage 2: Final ----
  FROM python:3.12-slim AS final

  ENV PYTHONDONTWRITEBYTECODE=1
  ENV PYTHONUNBUFFERED=1
  ENV NUMBA_DISABLE_JIT=${NUMBA_DISABLE_JIT:--1}
  ENV AWS_REGION=${AWS_REGION:-us-east-1}

  RUN apt-get update && \
      apt-get install -y --no-install-recommends \
          curl \
      && apt-get clean && \
      rm -rf /var/lib/apt/lists/*

  WORKDIR /app

  # Copy installed packages from builder stage
  COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
  COPY --from=builder /usr/local/bin /usr/local/bin

  # Copy source code from builder stage (already built into the package)
  COPY --from=builder /app/polismath/ ./polismath/
  COPY --from=builder /app/scripts/ ./scripts/
  COPY --from=builder /app/umap_narrative/ ./umap_narrative/
  COPY --from=builder /app/*.py ./

  RUN mkdir -p data
  EXPOSE 8080
  # PYTHONPATH not needed since packages are properly installed via pip

  # Make scripts executable
  RUN chmod +x run_delphi.py scripts/setup_ollama.sh

  CMD ["bash", "-c", "\
    echo 'Ensuring DynamoDB tables are set up (runs in all environments)...'; \
    python create_dynamodb_tables.py --region ${AWS_REGION} && \
    echo 'DynamoDB table setup script finished.'; \
    \
    if [ -n \"${DYNAMODB_ENDPOINT}\" ]; then \
      echo 'DYNAMODB_ENDPOINT is set, assuming local/dev environment. Running additional local setup scripts...'; \
      echo 'Setting up MinIO bucket...' && python setup_minio.py && \
      echo 'Setting up Ollama model (local script)...' && ./scripts/setup_ollama.sh && \
      echo 'Starting job poller without ddtrace...' && \
      python scripts/job_poller.py --interval=2; \
    else \
      echo 'DYNAMODB_ENDPOINT is not set, assuming production-like environment. Skipping local setup scripts.'; \
      if [ \"${AWS_REGION}\" = \"us-east-1\" ]; then \
        echo 'Starting job poller WITH ddtrace in us-east-1...' && \
        ddtrace-run python scripts/job_poller.py --interval=2 --region ${AWS_REGION}; \
      else \
        echo 'Starting job poller WITHOUT ddtrace in other regions...' && \
        python scripts/job_poller.py --interval=2 --region ${AWS_REGION}; \
      fi; \
    fi \
  "]
