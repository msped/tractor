from threading import Lock

from training.models import Model

DEFAULT_GLINER_MODEL = "urchade/gliner_medium-v2.1"


def _load_gliner_model(path):
    """Lazy GLiNER import — deferred until first model load so that
    importing this module does not pull in transformers/pandas at startup
    (which would break freezegun in the test suite).

    path is always a local directory under nlp_models/ — downloaded once
    via `python manage.py download_model` and never fetched from the network
    during normal operation."""
    from gliner import GLiNER

    return GLiNER.from_pretrained(path, local_files_only=True)


def _load_spancat_model(path):
    """Lazy spaCy import — same reason as GLiNER: avoids freezegun crash."""
    import spacy

    return spacy.load(path)


class GLiNERModelManager:
    _instance = None
    _lock = Lock()

    def __init__(self):
        self.model = None
        self.model_name = None
        self.model_entry = None
        self.load_active_model()

    @classmethod
    def get_instance(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def load_model(self, path, name=None):
        self.model = _load_gliner_model(path)
        self.model_name = name or path
        self.model_entry = Model.objects.filter(name=self.model_name).first()

    def load_active_model(self):
        pass  # GLiNER is not tracked in the DB; always falls back to DEFAULT_GLINER_MODEL

    def get_model(self):
        if self.model is None:
            self.load_active_model()
            if self.model is None:
                self.model = _load_gliner_model(DEFAULT_GLINER_MODEL)
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


class SpanCatModelManager:
    _instance = None
    _lock = Lock()

    def __init__(self):
        self.model = None
        self.model_name = None
        self.model_entry = None
        self.load_active_model()

    @classmethod
    def get_instance(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def load_model(self, path, name=None):
        self.model = _load_spancat_model(path)
        self.model_name = name or path
        self.model_entry = Model.objects.filter(name=self.model_name).first()

    def load_active_model(self):
        active_model = Model.objects.filter(is_active=True).first()
        if active_model:
            self.model_entry = active_model
            self.load_model(active_model.path, active_model.name)

    def get_model(self):
        """Return the active SpanCat model, or None if none has been trained yet."""
        if self.model is None:
            self.load_active_model()
        return self.model

    def get_model_entry(self):
        return self.model_entry

    def switch_model(self, model_name):
        model_entry = Model.objects.get(name=model_name)
        self.load_model(model_entry.path, model_entry.name)

        if not model_entry.is_active:
            model_entry.is_active = True
            model_entry.save(update_fields=["is_active"])
