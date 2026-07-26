import random

from app.services.behavioral_detector import BehavioralAnomalyDetector


def _baseline_features(n=200, seed=0):
    rng = random.Random(seed)
    return [[rng.uniform(0.2, 1.0), rng.uniform(0.4, 1.0), rng.uniform(20, 60)] for _ in range(n)]


def test_unfitted_model_never_flags_anomaly():
    det = BehavioralAnomalyDetector()
    result = det.score([100.0, 0.01, 500.0])
    assert result.is_anomaly is False
    assert result.anomaly_score == 0.0


def test_normal_vector_scores_low_after_fit():
    det = BehavioralAnomalyDetector(contamination=0.05)
    det.fit(_baseline_features())
    result = det.score([0.6, 0.7, 40])
    assert result.is_anomaly is False


def test_suspicious_vector_flagged_after_fit():
    """yüksek istek oranı + dar endpoint çeşitliliği davranışsal anomali olarak işaretleniyor"""
    det = BehavioralAnomalyDetector(contamination=0.05)
    det.fit(_baseline_features())
    result = det.score([18.0, 0.05, 45])
    assert result.is_anomaly is True