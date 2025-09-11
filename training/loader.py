# nlp/loader.py
import spacy
from threading import Lock
from training.models import Model as SpacyModel


class SpacyModelManager:
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
        self.model = spacy.load(path)
        self.model_name = name or path
        self.model_entry = SpacyModel.objects.filter(
            name=self.model_name).first()

    def load_active_model(self):
        active_model = SpacyModel.objects.filter(is_active=True).first()
        if active_model:
            self.model_entry = active_model
            self.load_model(active_model.path, active_model.name)

    def get_model(self):
        if self.model is None:
            self.load_active_model()
        return self.model

    def get_model_entry(self):
        return self.model_entry

    def switch_model(self, model_name):
        model_entry = SpacyModel.objects.get(name=model_name)
        self.load_model(model_entry.path, model_entry.name)

        # Set as active
        if not model_entry.is_active:
            model_entry.is_active = True
            model_entry.save(update_fields=['is_active'])
