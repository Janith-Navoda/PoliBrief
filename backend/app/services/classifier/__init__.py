"""
PoliBrief Backend — Classifier Service Package
"""
from backend.app.services.classifier.rules import classify_article, CATEGORY_RULES, CONFIDENCE_THRESHOLD

__all__ = ["classify_article", "CATEGORY_RULES", "CONFIDENCE_THRESHOLD"]
