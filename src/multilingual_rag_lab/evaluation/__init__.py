"""Offline, dataset-driven evaluation primitives."""

from .dataset import load_dataset
from .runner import ExperimentalRetriever, run_retrieval_evaluation

__all__ = ["ExperimentalRetriever", "load_dataset", "run_retrieval_evaluation"]
