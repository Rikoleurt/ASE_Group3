import os

# The app warms its models in a background thread at startup; tests start the
# app many times and mock the models, so they skip it.
os.environ.setdefault("PRELOAD_MODELS", "0")
