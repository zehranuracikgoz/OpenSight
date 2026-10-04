"""
Kaggle Credit Card Fraud (creditcard.csv) üzerinde Isolation Forest denemesi, OpenSight uygulamasından bağımsız

iki senaryo: (a) tüm eğitim verisiyle, (b) yalnızca normal işlemlerle (projedeki temiz baseline yaklaşımı)
etiketler eğitimde hedef olarak kullanılmıyor, sadece değerlendirmede, (b)'de de yalnızca normal satırları seçmek için

hold-out bölmesi sabit (split-seed), tek tohumlu sonuçların yanında modelin tohumu değiştirilerek ortalama ± sapma da çıkıyor

kullanım:
    pip install -r requirements.txt
    python evaluate_isolation_forest.py
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.metrics import average_precision_score, precision_recall_fscore_support
from sklearn.model_selection import train_test_split

HERE = Path(__file__).parent
DEFAULT_CONTAMINATIONS = [0.001, 0.0017, 0.005, 0.01]
DEFAULT_MODEL_SEEDS = [0, 1, 2, 42, 123]
LABEL_COLUMN = "Class"
METRICS = ["precision", "recall", "f1", "pr_auc"]
METRIC_LABELS = {"precision": "Precision", "recall": "Recall", "f1": "F1", "pr_auc": "PR-AUC"}

SCENARIOS = {
    "a_tum_veri": "tüm eğitim verisiyle (fraud dahil, etiketsiz)",
    "b_sadece_normal": "yalnızca normal işlemlerle (temiz baseline)",
}


def load_dataset(csv_path: Path) -> tuple[np.ndarray, np.ndarray, list[str]]:
    df = pd.read_csv(csv_path)
    features = [c for c in df.columns if c != LABEL_COLUMN]
    return df[features].to_numpy(dtype=float), df[LABEL_COLUMN].to_numpy(dtype=int), features


def split_data(
    X: np.ndarray, y: np.ndarray, test_size: float, seed: int
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """X_train, X_eval, y_train, y_eval döndürüyor, test_size 0 ise ikisi de aynı veri"""
    if test_size <= 0:
        return X, X, y, y
    return train_test_split(X, y, test_size=test_size, stratify=y, random_state=seed)


def evaluate_run(
    X_train: np.ndarray, X_eval: np.ndarray, y_eval: np.ndarray, contamination: float, seed: int, n_estimators: int
) -> dict:
    model = IsolationForest(n_estimators=n_estimators, contamination=contamination, random_state=seed, n_jobs=-1)
    model.fit(X_train)

    predicted = (model.predict(X_eval) == -1).astype(int)
    precision, recall, f1, _ = precision_recall_fscore_support(y_eval, predicted, average="binary", zero_division=0)
    # yüksek skor = daha anormal, PR-AUC eşikten bağımsız
    pr_auc = average_precision_score(y_eval, -model.decision_function(X_eval))

    tp = int(((predicted == 1) & (y_eval == 1)).sum())
    fp = int(((predicted == 1) & (y_eval == 0)).sum())
    fn = int(((predicted == 0) & (y_eval == 1)).sum())
    return {
        "contamination": contamination,
        "precision": float(precision),
        "recall": float(recall),
        "f1": float(f1),
        "pr_auc": float(pr_auc),
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "flagged": int(predicted.sum()),
    }


def aggregate_runs(runs: list[dict]) -> dict:
    """aynı senaryo ve contamination için tohumlar arası ortalama ve örneklem standart sapması (ddof=1)"""
    aggregated = {"contamination": runs[0]["contamination"]}
    for metric in METRICS:
        values = np.array([r[metric] for r in runs])
        aggregated[f"{metric}_mean"] = float(values.mean())
        aggregated[f"{metric}_std"] = float(values.std(ddof=1)) if len(values) > 1 else 0.0
    return aggregated


def compare_scenarios(a_rows: list[dict], b_rows: list[dict]) -> list[dict]:
    """(b - a) farkı iki senaryonun sapmaları toplamından büyükse sapmanın dışında sayılıyor"""
    comparison = []
    for a, b in zip(a_rows, b_rows):
        for metric in METRICS:
            diff = b[f"{metric}_mean"] - a[f"{metric}_mean"]
            spread = a[f"{metric}_std"] + b[f"{metric}_std"]
            comparison.append(
                {
                    "contamination": a["contamination"],
                    "metric": metric,
                    "diff": float(diff),
                    "spread": float(spread),
                    "outside_spread": bool(abs(diff) > spread),
                }
            )
    return comparison


def run_experiment(
    X: np.ndarray,
    y: np.ndarray,
    contaminations: list[float],
    test_size: float,
    seed: int,
    n_estimators: int,
    model_seeds: list[int],
    split_seed: int,
) -> dict:
    X_train, X_eval, y_train, y_eval = split_data(X, y, test_size, split_seed)

    training_sets = {
        "a_tum_veri": X_train,
        "b_sadece_normal": X_train[y_train == 0],  # etiket yalnızca normal satırları seçmek için
    }
    all_seeds = sorted(set(model_seeds) | {seed})
    runs = {
        name: {
            s: [evaluate_run(data, X_eval, y_eval, c, s, n_estimators) for c in contaminations] for s in all_seeds
        }
        for name, data in training_sets.items()
    }

    multi_seed = {
        name: [aggregate_runs([runs[name][s][i] for s in model_seeds]) for i in range(len(contaminations))]
        for name in training_sets
    }
    return {
        "dataset": {
            "rows": int(len(y)),
            "fraud": int(y.sum()),
            "fraud_rate": float(y.mean()),
            "features": int(X.shape[1]),
        },
        "evaluation": {
            "test_size": test_size,
            "eval_rows": int(len(y_eval)),
            "eval_fraud": int(y_eval.sum()),
            "eval_fraud_rate": float(y_eval.mean()),
        },
        "training_rows": {name: int(len(data)) for name, data in training_sets.items()},
        "params": {
            "seed": seed,
            "split_seed": split_seed,
            "n_estimators": n_estimators,
            "contaminations": contaminations,
            "model_seeds": model_seeds,
        },
        "results": {name: runs[name][seed] for name in training_sets},
        "multi_seed": {
            "per_seed": {name: {str(s): rows for s, rows in runs[name].items() if s in model_seeds} for name in runs},
            "summary": multi_seed,
            "comparison": compare_scenarios(multi_seed["a_tum_veri"], multi_seed["b_sadece_normal"]),
        },
    }


def _fmt(value: float) -> str:
    return f"{value:.3f}"


def _pm(mean: float, std: float) -> str:
    return f"{mean:.3f} ± {std:.3f}"


def _single_seed_section(report: dict) -> list[str]:
    e = report["evaluation"]
    lines = [
        "## Sonuçlar (tek tohum)",
        "",
        "Accuracy ana metrik değil: her şeye \"normal\" diyen model bile "
        f"%{(1 - e['eval_fraud_rate']) * 100:.2f} accuracy alır. "
        f"PR-AUC için rastgele referans fraud oranıdır (≈{e['eval_fraud_rate']:.4f}). "
        "PR-AUC eşikten bağımsızdır, bu yüzden aynı senaryoda contamination'a göre değişmez.",
        "",
    ]
    for name, rows in report["results"].items():
        lines += [
            f"### Senaryo {name[0]}: {SCENARIOS[name]}",
            "",
            "| Contamination | Precision | Recall | F1 | PR-AUC | TP | FP | FN | İşaretlenen |",
            "|---|---|---|---|---|---|---|---|---|",
        ]
        for r in rows:
            lines.append(
                f"| {r['contamination']} | {_fmt(r['precision'])} | {_fmt(r['recall'])} | {_fmt(r['f1'])} | "
                f"{_fmt(r['pr_auc'])} | {r['tp']} | {r['fp']} | {r['fn']} | {r['flagged']} |"
            )
        lines.append("")
    return lines


def _comparison_comment(comparison: list[dict]) -> list[str]:
    outside = [c for c in comparison if c["outside_spread"]]
    lines = [
        "### Senaryo (a) ile (b) arasındaki fark sapmanın içinde mi?",
        "",
        "Kural: |ortalama(b) − ortalama(a)|, iki senaryonun standart sapmaları toplamından büyükse fark sapmanın "
        "dışında sayılıyor. Fark = (b − a).",
        "",
        "| Contamination | " + " | ".join(METRIC_LABELS[m] for m in METRICS) + " |",
        "|---|" + "---|" * len(METRICS),
    ]
    for contamination in dict.fromkeys(c["contamination"] for c in comparison):
        cells = []
        for metric in METRICS:
            c = next(x for x in comparison if x["contamination"] == contamination and x["metric"] == metric)
            where = "dışında" if c["outside_spread"] else "içinde"
            cells.append(f"{c['diff']:+.3f} ({where})")
        lines.append(f"| {contamination} | " + " | ".join(cells) + " |")
    lines += [
        "",
        f"**Yorum:** {len(comparison)} karşılaştırmanın {len(outside)}'inde fark sapmanın dışında, "
        f"{len(comparison) - len(outside)}'inde içinde.",
    ]
    for metric in METRICS:
        higher_b = [c["contamination"] for c in outside if c["metric"] == metric and c["diff"] > 0]
        higher_a = [c["contamination"] for c in outside if c["metric"] == metric and c["diff"] < 0]
        inside = [c["contamination"] for c in comparison if c["metric"] == metric and not c["outside_spread"]]
        parts = []
        if higher_b:
            parts.append(f"(b) belirgin yüksek: {', '.join(map(str, higher_b))}")
        if higher_a:
            parts.append(f"(a) belirgin yüksek: {', '.join(map(str, higher_a))}")
        if inside:
            parts.append(f"sapma içinde: {', '.join(map(str, inside))}")
        lines.append(f"- {METRIC_LABELS[metric]}: " + "; ".join(parts))
    a_leads = sum(1 for c in outside if c["diff"] < 0)
    b_leads = len(outside) - a_leads
    lines += [
        "",
        f"Sapmanın dışındaki farkların {a_leads}'i (a) lehine, {b_leads}'i (b) lehine. "
        + (
            "Bu veri setinde temiz baseline (b) bir avantaj sağlamıyor. Olası bir neden, fraud oranı çok düşük "
            "olduğu için eğitim kümesindeki az sayıda fraud'un (a)'nın modelini bozmaması, ama bu varsayım ayrıca denenmedi."
            if a_leads > b_leads
            else "Temiz baseline (b) bu veri setinde (a)'ya göre ölçülebilir bir iyileşme sağlıyor."
            if b_leads > a_leads
            else "Belirgin bir yön yok."
        ),
        "",
        "Sınırlar: 5 tohum küçük bir örneklem, sapma kaba bir kestirim. Hold-out bölmesi sabit olduğu için bu sapma "
        "yalnızca modelin rastgeleliğini yansıtıyor, veri bölmesinin değişkenliğini içermiyor. "
        "Değerlendirme kümesinde fraud sayısı az olduğundan tek bir yakalama bile metrikleri oynatır.",
        "",
    ]
    return lines


def _multi_seed_section(report: dict) -> list[str]:
    p, multi = report["params"], report["multi_seed"]
    lines = [
        "## Çoklu tohum (ortalama ± standart sapma)",
        "",
        f"- Isolation Forest random_state değerleri: {', '.join(map(str, p['model_seeds']))}",
        f"- Hold-out bölmesi tüm tohumlarda aynı (split random_state={p['split_seed']}), fark yalnızca modelin rastgeleliğinden",
        "- Standart sapma örneklem sapması (n−1)",
        "- PR-AUC eşikten bağımsız olduğu için aynı senaryoda her contamination satırında aynı değer çıkar",
        "",
    ]
    for name, rows in multi["summary"].items():
        lines += [
            f"### Senaryo {name[0]}: {SCENARIOS[name]}",
            "",
            "| Contamination | Precision | Recall | F1 | PR-AUC |",
            "|---|---|---|---|---|",
        ]
        for r in rows:
            cells = " | ".join(_pm(r[f"{m}_mean"], r[f"{m}_std"]) for m in METRICS)
            lines.append(f"| {r['contamination']} | {cells} |")
        lines.append("")
    return lines + _comparison_comment(multi["comparison"])


def render_markdown(report: dict, generated_at: str) -> str:
    d, e, p = report["dataset"], report["evaluation"], report["params"]
    where = (
        f"hold-out: verinin %{e['test_size'] * 100:.0f}'i ({e['eval_rows']:,} işlem, {e['eval_fraud']} fraud) "
        "değerlendirme için ayrıldı, model geri kalanıyla eğitildi"
        if e["test_size"] > 0
        else f"değerlendirme eğitimle aynı veri üzerinde ({e['eval_rows']:,} işlem, {e['eval_fraud']} fraud)"
    )
    lines = [
        "# Isolation Forest — Kaggle Credit Card Fraud doğrulaması",
        "",
        f"_Üretim zamanı: {generated_at}_",
        "",
        "## Bu deney neyi gösteriyor, neyi göstermiyor",
        "",
        "- V1–V28 PCA ile anonimleştirilmiş özelliklerdir; ne anlama geldikleri bilinmiyor",
        "- Bu deney, Isolation Forest'ın standart bir dolandırıcılık veri setinde nasıl davrandığını göstermek içindir",
        "- OpenSight'ın istemci-davranışı feature'larıyla (istek oranı, en sık endpoint payı, ortalama gecikme) "
        "doğrudan karşılaştırılamaz; veri, birim ve sınıf dengesi farklıdır",
        "- Uygulamaya dokunmayan, ayrı bir deneydir",
        "",
        "## Veri seti ve kurulum",
        "",
        f"- {d['rows']:,} işlem, {d['fraud']} fraud (%{d['fraud_rate'] * 100:.3f}), {d['features']} özellik "
        "(Time, V1–V28, Amount)",
        "- Isolation Forest denetimsiz çalışıyor, etiketler eğitimde hedef olarak kullanılmıyor, yalnızca değerlendirmede",
        f"- Değerlendirme: {where}",
        f"- Model: {p['n_estimators']} ağaç, tek tohumlu bölümde random_state={p['seed']}",
        "- Senaryo (a): eğitim verisinin tamamı, fraud dahil, etiketsiz",
        f"- Senaryo (b): yalnızca normal işlemler ({report['training_rows']['b_sadece_normal']:,} satır), "
        "OpenSight'taki temiz baseline yaklaşımına benzer; etiket sadece normal satırları seçmek için kullanılıyor",
        "- Contamination, eğitim skorlarında eşiğin nereden çekileceğini belirliyor (işaretlenen oran)",
        "",
    ]
    lines += _single_seed_section(report)
    lines += _multi_seed_section(report)
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Kaggle creditcard.csv üzerinde Isolation Forest değerlendirmesi")
    parser.add_argument("--csv", default=str(HERE / "creditcard.csv"))
    parser.add_argument("--output-dir", default=str(HERE / "results"))
    parser.add_argument("--contaminations", type=float, nargs="+", default=DEFAULT_CONTAMINATIONS)
    parser.add_argument("--test-size", type=float, default=0.3, help="0 verilirse eğitim verisi üzerinde değerlendirir")
    parser.add_argument("--n-estimators", type=int, default=100)
    parser.add_argument("--seed", type=int, default=42, help="tek tohumlu bölümdeki model tohumu")
    parser.add_argument("--split-seed", type=int, default=42, help="hold-out bölmesi, tüm tohumlarda sabit")
    parser.add_argument("--model-seeds", type=int, nargs="+", default=DEFAULT_MODEL_SEEDS)
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")  # Windows konsolu cp1254'te – ve ≈ basılamıyor

    csv_path = Path(args.csv)
    if not csv_path.exists():
        raise SystemExit(f"veri seti bulunamadı: {csv_path}")

    X, y, _ = load_dataset(csv_path)
    report = run_experiment(
        X, y, args.contaminations, args.test_size, args.seed, args.n_estimators, args.model_seeds, args.split_seed
    )

    now = datetime.now()
    stamp = now.strftime("%Y%m%d_%H%M%S")
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"kaggle_if_{stamp}.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    markdown = render_markdown(report, now.strftime("%Y-%m-%d %H:%M:%S"))
    (out_dir / f"kaggle_if_{stamp}.md").write_text(markdown, encoding="utf-8")
    print(markdown)
    print(f"\nsonuçlar yazıldı: {out_dir}")


if __name__ == "__main__":
    main()
