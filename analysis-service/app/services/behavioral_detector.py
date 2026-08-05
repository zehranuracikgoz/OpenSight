"""
BehavioralAnomalyDetector: client bazlı özellik vektörleri üzerinde Isolation Forest
ile davranışsal anomali tespiti - model yalnızca 'normal' baseline verisiyle ilk kez
eğitiliyor, sonrasında periyodik yeniden eğitiliyor (cold start)
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sklearn.ensemble import IsolationForest


@dataclass
class BehavioralScoreResult:
    anomaly_score: float   # 0 (normal) .. 1 (çok anormal) aralığına
    is_anomaly: bool


class BehavioralAnomalyDetector:
    """
    özellik vektörü: [istek_orani, endpoint_cesitliligi, ortalama_gecikme]
    - istek_orani: son pencerede saniyedeki istek sayısı
    - endpoint_cesitliligi: benzersiz endpoint sayısı / toplam istek (düşük = tekdüze/şüpheli)
    - ortalama_gecikme: son pencerede ortalama gecikme (ms)
    """

    FEATURE_NAMES = ["istek_orani", "endpoint_cesitliligi", "ortalama_gecikme"]

    def __init__(self, contamination: float = 0.05, random_state: int = 42):
        self.contamination = contamination
        self.random_state = random_state
        self._model: IsolationForest | None = None
        self._is_fitted = False

    def fit(self, baseline_features: list[list[float]]) -> None:
        """cold start sonrası toplanan 'sadece normal' veriyle ilk eğitim"""
        X = np.array(baseline_features)
        self._model = IsolationForest(contamination=self.contamination, random_state=self.random_state)
        self._model.fit(X)
        self._is_fitted = True

    def retrain(self, recent_features: list[list[float]]) -> None:
        """periyodik yeniden eğitim"""
        self.fit(recent_features)

    def score(self, feature_vector: list[float]) -> BehavioralScoreResult:
        if not self._is_fitted or self._model is None:
            # model henüz eğitilmedi, cold start sırasında anomali işaretlenmiyor
            return BehavioralScoreResult(anomaly_score=0.0, is_anomaly=False)

        X = np.array([feature_vector])
        raw_score = self._model.decision_function(X)[0]   # yüksek = normal, düşük/negatif = anormal
        prediction = self._model.predict(X)[0]             # 1 = normal, -1 = anomali

        # decision_function'ı [0,1] aralığına çevir (0 = normal, 1 = çok anormal)
        normalized = max(0.0, min(1.0, 0.5 - raw_score))
        return BehavioralScoreResult(anomaly_score=round(float(normalized), 3), is_anomaly=bool(prediction == -1))

    def set_contamination(self, contamination: float) -> None:
        self.contamination = contamination