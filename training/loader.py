import logging
import os
from threading import Lock

from django.conf import settings

from training.models import Model

logger = logging.getLogger(__name__)

DEFAULT_GLINER_MODEL = "urchade/gliner_medium-v2.1"
_GLINER_LOCAL_NAME = (
    DEFAULT_GLINER_MODEL.replace("/", "_").replace("-", "_").replace(".", "_")
)
_GLINER_LOCAL_PATH = os.path.join(
    settings.BASE_DIR, "nlp_models", _GLINER_LOCAL_NAME
)


def _get_device():
    """Return the best available compute device.

    Priority: CUDA (NVIDIA) > MPS (Apple Silicon) > CPU.

    This import is intentionally deferred (called only from within the
    already-lazy load functions) to avoid pulling in torch at module
    import time, which would break freezegun in the test suite."""
    import torch

    if torch.cuda.is_available():
        return "cuda"
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def _load_gliner_model(path):
    """Lazy GLiNER import — deferred until first model load so that
    importing this module does not pull in transformers/pandas at startup
    (which would break freezegun in the test suite).

    Loads from the local nlp_models/ directory (downloaded once via
    `python manage.py download_model`). Falls back to fetching from
    HuggingFace if the local copy is not present.

    The model is moved to the best available device (CUDA, MPS, or CPU)."""
    from gliner import GLiNER

    if os.path.isdir(path):
        model = GLiNER.from_pretrained(path, local_files_only=True)
    else:
        model = GLiNER.from_pretrained(path)
    return model.to(_get_device())


def _load_spancat_model(path):
    """Lazy spaCy import — same reason as GLiNER: avoids freezegun crash.

    Calls spacy.prefer_gpu() before loading so the model runs on the GPU
    when CUDA is available. spaCy does not support MPS, so Apple Silicon
    machines fall back to CPU for SpanCat (GLiNER still benefits from MPS)."""
    import spacy

    if _get_device() == "cuda":
        spacy.prefer_gpu()
    return spacy.load(path)


class _ModelManagerBase:
    """Shared singleton machinery for model managers.

    Each concrete subclass automatically gets its own _instance and _lock
    via __init_subclass__, so subclasses never share state.
    """

    _instance = None
    _lock = Lock()

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        cls._instance = None
        cls._lock = Lock()

    def __init__(self):
        self.model = None
        self.model_name = None
        self.model_entry = None

    @classmethod
    def get_instance(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance


class GLiNERModelManager(_ModelManagerBase):
    """Manages the GLiNER model singleton.

    The model is not tracked in the DB and is loaded lazily on the first
    get_model() call rather than at singleton construction time.
    """

    def load_model(self, path, name=None):
        self.model = _load_gliner_model(path)
        self.model_name = name or path
        self.model_entry = Model.objects.filter(name=self.model_name).first()

    def get_model(self):
        if self.model is None:
            path = (
                _GLINER_LOCAL_PATH
                if os.path.isdir(_GLINER_LOCAL_PATH)
                else DEFAULT_GLINER_MODEL
            )
            self.model = _load_gliner_model(path)
            self.model_name = DEFAULT_GLINER_MODEL
        return self.model

    def get_model_entry(self):
        return self.model_entry

    def switch_model(self, model_name):
        model_entry = Model.objects.get(name=model_name)
        self.load_model(model_entry.path, model_entry.name)
        if not model_entry.is_active:
            model_entry.is_active = True
            model_entry.save(update_fields=["is_active"])


class SpanCatModelManager(_ModelManagerBase):
    """Manages the SpanCat model singleton.

    Attempts to load the active model from the DB at construction time.
    A DB failure at startup is caught and logged — the manager starts with
    model=None so the pipeline degrades gracefully to GLiNER+Presidio+Gemma.
    """

    def __init__(self):
        super().__init__()
        try:
            self._load_active_model()
        except Exception:
            logger.warning(
                "SpanCat model could not be loaded at startup — "
                "pipeline will run without SpanCat until next request.",
                exc_info=True,
            )

    def _load_active_model(self):
        active_model = Model.objects.filter(is_active=True).first()
        if active_model:
            self.model_entry = active_model
            self.load_model(active_model.path, active_model.name)

    def load_model(self, path, name=None):
        self.model = _load_spancat_model(path)
        self.model_name = name or path
        self.model_entry = Model.objects.filter(name=self.model_name).first()

    def get_model(self):
        """Return the active SpanCat model, or None if none has been trained yet."""
        if self.model is None:
            try:
                self._load_active_model()
            except Exception:
                logger.warning("SpanCat model reload failed.", exc_info=True)
        return self.model

    def get_model_entry(self):
        return self.model_entry

    def switch_model(self, model_name):
        model_entry = Model.objects.get(name=model_name)
        self.load_model(model_entry.path, model_entry.name)
        if not model_entry.is_active:
            model_entry.is_active = True
            model_entry.save(update_fields=["is_active"])
