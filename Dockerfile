# Slim Python base image - small download, still has everything the
# standard library and our dependencies need (no C extensions requiring
# build tools beyond what's already in the image).
FROM python:3.12-slim

# Prevents Python from writing .pyc files and buffering stdout/stderr,
# which makes container logs show up immediately instead of being
# buffered and lost if the container crashes.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Copy only the requirements file first and install dependencies before
# copying the rest of the source code. Docker caches each layer, so if
# only application code changes (not dependencies), this pip install layer
# is reused from cache instead of re-running on every build.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Now copy the actual application code.
COPY app ./app

# Render (and most cloud providers) inject a PORT environment variable at
# runtime and expect the app to bind to it. We default to 8000 for local
# `docker run` convenience, but the CMD below reads $PORT if it's set.
ENV PORT=8000
EXPOSE 8000

# Run the database seed script, then start the API server. Using a shell
# form here (not exec form) specifically so that $PORT is expanded by the
# shell at container start time.
CMD python -m app.seed && uvicorn app.main:app --host 0.0.0.0 --port ${PORT}
