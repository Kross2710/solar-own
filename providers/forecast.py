"""Dự báo SẢN LƯỢNG ngày bằng mô hình hồi quy huấn luyện trên lịch sử.

Ý tưởng: sản lượng PV ≈ hàm của bức xạ (shortwave radiation) + nhiệt độ (suy giảm
hiệu suất khi nóng) + mưa/mây + góc mặt trời theo mùa. Lấy thời tiết ngày từ
open-meteo và ghép với `daily.kwh`. Nguồn thời tiết:
  - LỊCH SỬ (huấn luyện): archive-api (ERA5) — phủ toàn bộ lịch sử, không giới hạn
    92 ngày, nhất quán một nguồn cho cả tập huấn luyện.
  - TƯƠNG LAI (phục vụ): forecast-api cho 7 ngày tới (+ lấp khe vài ngày archive
    còn trễ ~5 ngày). Vậy điểm CV đo trên bức xạ ERA5 còn lúc phục vụ dùng bức xạ
    dự báo: có lệch nguồn, nhưng (a) chỉ dùng biến có ở CẢ hai nguồn (bỏ uv/rain_prob),
    (b) hệ bị cắt đỉnh nên trọng số bức xạ rất nhỏ -> ảnh hưởng số không đáng kể.
    `quality["source"]` ghi rõ điều này. Rồi:

  1. Tạo đặc trưng vật lý (bức xạ, bức xạ², giờ nắng, độ trong, nhiệt độ, mưa, mùa).
  2. CHẠY ĐUA nhiều mô hình: Ridge (numpy, luôn có) + Gradient Boosting (sklearn,
     tuỳ chọn) + các baseline (khí hậu TB, quán tính, heuristic cũ avg×rad/refRad).
  3. Chấm điểm bằng WALK-FORWARD CV theo thời gian (train [0..i], dự báo i; bước
     tiến) — KHÔNG leakage, mô phỏng đúng cách dùng thật.
  4. Chọn mô hình có sai số (MAE) thấp nhất, huấn luyện lại trên toàn bộ để phục vụ.

Mẫu hiện nhỏ (~vài chục ngày, một mùa) nên Ridge thường thắng; nhưng bake-off để
ngỏ cho GBM khi dữ liệu nhiều lên. Điểm báo cáo là điểm CV TRUNG THỰC, kèm "skill"
so với baseline để biết mô hình có thật sự hơn cách đoán ngây thơ không.
"""
from __future__ import annotations

import math
from datetime import date, datetime, timedelta
from typing import Callable, Optional

try:
    import numpy as np
    _HAS_NUMPY = True
except Exception:  # pragma: no cover - service vẫn chạy, chỉ tắt dự báo ML
    _HAS_NUMPY = False

try:
    from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestClassifier
    _HAS_SKLEARN = True
except Exception:
    _HAS_SKLEARN = False

# Cột thời tiết open-meteo (daily) ta lấy về. Thứ tự khớp _parse_daily.
OM_DAILY = [
    "shortwave_radiation_sum", "sunshine_duration", "daylight_duration",
    "temperature_2m_max", "temperature_2m_mean", "temperature_2m_min",
    "precipitation_sum", "precipitation_hours", "et0_fao_evapotranspiration",
    "uv_index_max", "weather_code", "precipitation_probability_max",
]
# map -> tên cột trong bảng weather_daily
_OM_TO_COL = {
    "shortwave_radiation_sum": "rad", "sunshine_duration": "sun",
    "daylight_duration": "daylight", "temperature_2m_max": "tmax",
    "temperature_2m_mean": "tmean", "temperature_2m_min": "tmin",
    "precipitation_sum": "precip", "precipitation_hours": "precip_h",
    "et0_fao_evapotranspiration": "et0", "uv_index_max": "uv",
    "weather_code": "wcode", "precipitation_probability_max": "rain_prob",
}

# Tên đặc trưng đưa vào mô hình (thứ tự cố định).
# CHỈ dùng biến có ở CẢ archive-api LẪN forecast-api (uv/rain_prob chỉ có ở forecast
# -> loại khỏi feature để train(archive) và serve(forecast) không lệch phân phối).
# (2026-06-24: đã thử thêm 3 đặc trưng tự hồi quy kwh_lag1/ma3/ma7 -> KHÔNG vượt climatology
#  trong walk-forward [MAE 4.18->4.16, skill -0.047->-0.041, đều trong nhiễu; cv_best vẫn là
#  climatology_flat], nên revert để giữ mô hình gọn. Hệ này climatology-limited do curtailment,
#  không phải feature-limited. Xem [[Decisions]].)
FEATURES = [
    "rad", "rad2", "sun_h", "clearness", "tmax", "tspread",
    "precip", "precip_h", "wet", "et0", "doy_sin", "doy_cos",
]

# Biến daily có sẵn ở archive-api (ERA5) — phủ toàn bộ lịch sử (không giới hạn 92 ngày).
OM_DAILY_ARCHIVE = [
    "shortwave_radiation_sum", "sunshine_duration", "daylight_duration",
    "temperature_2m_max", "temperature_2m_mean", "temperature_2m_min",
    "precipitation_sum", "precipitation_hours", "et0_fao_evapotranspiration",
    "weather_code",
]


# ----------------------------- lấy thời tiết -----------------------------
async def fetch_daily_weather(lat: float, lon: float, today: str,
                              past_days: int = 92, forecast_days: int = 7,
                              client=None) -> dict:
    """open-meteo daily -> {'YYYY-MM-DD': {col: val, 'is_fcst': 0/1}}.

    Endpoint forecast (past_days<=92 + forecast_days). Hiện chủ yếu dùng cho TƯƠNG
    LAI (và lấp vài ngày archive còn trễ); lịch sử huấn luyện lấy từ archive-api.
    `today` (ISO) phân định ngày nào là dự báo (is_fcst=1).
    """
    import httpx
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        f"&daily={','.join(OM_DAILY)}"
        f"&timezone=auto&past_days={int(past_days)}&forecast_days={int(forecast_days)}"
    )
    owns = client is None
    if owns:
        client = httpx.AsyncClient(timeout=20)
    try:
        r = await client.get(url)
        r.raise_for_status()
        j = r.json()
    finally:
        if owns:
            await client.aclose()
    return _parse_daily(j.get("daily") or {}, today)


# ERA5 công bố trễ ~5 ngày; archive-api trả 400 Bad Request nếu end_date lấn vào
# vùng chưa có dữ liệu (trước kia trả null — đổi hành vi phía Open-Meteo ~2026-07).
ARCHIVE_LAG_DAYS = 5


def archive_safe_end(end: str, today: Optional[str] = None,
                     lag_days: int = ARCHIVE_LAG_DAYS) -> str:
    """Kẹp end_date của archive-api lùi về (today - lag_days) nếu nó gần hơn.

    `today` (ISO) chỉ để test tất định; mặc định lấy ngày hệ thống.
    So sánh chuỗi ISO YYYY-MM-DD == so sánh ngày, nên min() là đủ.
    """
    t = date.fromisoformat(today) if today else date.today()
    cap = (t - timedelta(days=lag_days)).isoformat()
    return min(end, cap)


async def fetch_archive_weather(lat: float, lon: float, start: str, end: str,
                                client=None) -> dict:
    """archive-api (ERA5) cho [start, end] -> {day: {col: val, 'is_fcst': 0}}.

    Phủ toàn bộ lịch sử (không bị giới hạn 92 ngày như past_days). Dùng để nạp
    nền cho những ngày đã có sản lượng nhưng chưa có thời tiết trong cache.
    end_date tự kẹp lùi ARCHIVE_LAG_DAYS ngày (ERA5 trễ); đuôi gần hiện tại do
    forecast-api past_days lấp (xem _refresh_forecast trong server.py).
    """
    import httpx
    end = archive_safe_end(end)
    if start > end:            # lịch sử quá ngắn, cả khoảng nằm trong vùng ERA5 chưa có
        return {}
    url = (
        "https://archive-api.open-meteo.com/v1/archive"
        f"?latitude={lat}&longitude={lon}&start_date={start}&end_date={end}"
        f"&daily={','.join(OM_DAILY_ARCHIVE)}&timezone=auto"
    )
    owns = client is None
    if owns:
        client = httpx.AsyncClient(timeout=30)
    try:
        r = await client.get(url)
        r.raise_for_status()
        j = r.json()
    finally:
        if owns:
            await client.aclose()
    # archive luôn là quá khứ -> is_fcst=0 (truyền today rất tương lai để mọi ngày=0)
    return _parse_daily(j.get("daily") or {}, "9999-12-31")


def _parse_daily(d: dict, today: str) -> dict:
    days = d.get("time") or []
    out: dict = {}
    for i, day in enumerate(days):
        row: dict = {}
        for om in OM_DAILY:
            arr = d.get(om) or []
            row[_OM_TO_COL[om]] = arr[i] if i < len(arr) else None
        row["is_fcst"] = 1 if str(day) > str(today) else 0
        out[str(day)[:10]] = row
    return out


# --------------------------- feature engineering ---------------------------
def _doy(day: str) -> int:
    y, m, d = (int(x) for x in str(day)[:10].split("-"))
    return date(y, m, d).timetuple().tm_yday


def feature_row(day: str, w: dict) -> list:
    """weather row -> vector đặc trưng (FEATURES). None cho giá trị thiếu (impute sau)."""
    def g(k):
        v = w.get(k)
        return None if v is None else float(v)

    rad = g("rad")
    sun = g("sun")
    daylight = g("daylight")
    tmax = g("tmax")
    tmin = g("tmin")
    precip = g("precip")
    precip_h = g("precip_h")
    et0 = g("et0")

    sun_h = None if sun is None else sun / 3600.0
    daylight_h = None if daylight is None else daylight / 3600.0
    # độ "trong" của trời: bức xạ trên mỗi giờ ban ngày (cao = trời quang)
    clearness = None
    if rad is not None and daylight_h:
        clearness = rad / max(1.0, daylight_h)
    rad2 = None if rad is None else rad * rad  # bão hoà/cắt đỉnh khi nắng gắt
    tspread = None if (tmax is None or tmin is None) else (tmax - tmin)
    wet = None if precip is None else (1.0 if precip >= 1.0 else 0.0)
    doy = _doy(day)
    ang = 2.0 * math.pi * doy / 365.25
    return [rad, rad2, sun_h, clearness, tmax, tspread,
            precip, precip_h, wet, et0, math.sin(ang), math.cos(ang)]


def build_matrix(rows: list):
    """rows=[{day,kwh,rad,...}] (đã ghép) -> (dates, X, y) numpy."""
    dates, X, y = [], [], []
    for r in rows:
        if r.get("kwh") is None or r.get("rad") is None:
            continue
        dates.append(r["day"])
        X.append(feature_row(r["day"], r))
        y.append(float(r["kwh"]))
    X = np.array([[np.nan if v is None else v for v in row] for row in X], dtype=float)
    return dates, X, np.array(y, dtype=float)


# ------------------------------- mô hình -------------------------------
class Ridge:
    """Hồi quy tuyến tính có chính quy hoá L2 (numpy thuần, dạng đóng).

    Tự impute NaN bằng trung bình cột (train) + chuẩn hoá -> alpha so sánh được
    giữa các đặc trưng. KHÔNG phạt hệ số chặn (tách riêng qua trung bình y).
    """

    def __init__(self, alpha: float = 10.0):
        self.alpha = float(alpha)

    def fit(self, X, y):
        self.mu_ = np.nanmean(X, axis=0)
        self.mu_ = np.where(np.isfinite(self.mu_), self.mu_, 0.0)
        Xi = self._impute(X)
        self.xmean_ = Xi.mean(axis=0)
        self.xstd_ = Xi.std(axis=0)
        self.xstd_[self.xstd_ < 1e-9] = 1.0
        Xs = (Xi - self.xmean_) / self.xstd_
        self.ymean_ = float(y.mean())
        yc = y - self.ymean_
        p = Xs.shape[1]
        A = Xs.T @ Xs + self.alpha * np.eye(p)
        self.beta_ = np.linalg.solve(A, Xs.T @ yc)
        return self

    def _impute(self, X):
        Xi = np.array(X, dtype=float, copy=True)
        idx = np.where(~np.isfinite(Xi))
        if idx[0].size:
            Xi[idx] = np.take(self.mu_, idx[1])
        return Xi

    def predict(self, X):
        Xs = (self._impute(X) - self.xmean_) / self.xstd_
        return self.ymean_ + Xs @ self.beta_


class MeanModel:
    """Khí hậu học: luôn dự báo TRUNG BÌNH sản lượng (có giảm trọng số ngày cũ).

    Là ứng viên hạng nhất, KHÔNG phải chỉ baseline: với hệ bị cắt đỉnh + dữ liệu
    một mùa, đặc trưng thời tiết thường không thắng nổi trung bình -> để bake-off
    tự chọn. Khi tích đủ dữ liệu nhiều mùa, mô hình thời tiết sẽ vượt lên và được
    chọn thay. `half_life` cho ngày gần đây nặng hơn (thích nghi dần theo mùa).
    """

    def __init__(self, half_life: Optional[float] = 45.0):
        self.half_life = half_life

    def fit(self, X, y):
        n = len(y)
        if self.half_life and n > 1:
            age = np.arange(n - 1, -1, -1.0)            # ngày mới nhất = 0
            w = 0.5 ** (age / float(self.half_life))
            self.value_ = float(np.sum(w * y) / np.sum(w))
        else:
            self.value_ = float(np.mean(y))
        return self

    def predict(self, X):
        return np.full(len(X), self.value_)


# ----- Hướng C: phân loại CHẤT LƯỢNG NGÀY (nắng tốt/vừa/ít) thay vì hồi quy kWh chính xác -----
# Dự báo kWh chính xác bất khả thi vì curtailment cắt trần (xem [[Decisions]] A/B đều thua
# climatology). Nhưng phân loại 3 mức thì DỄ HƠN và đủ cho "Chiến lược pin": chỉ cần biết mai
# có đáng xả pin không. Đo bằng walk-forward (macro-F1 + confusion matrix, đúng kiểu bài tập ML).
QUAL_LABELS = ["ít", "vừa", "tốt"]  # 0/1/2 theo tercile sản lượng


class DayQualityClassifier:
    """RandomForest 3 lớp (ít/vừa/tốt) từ đặc trưng thời tiết. Impute NaN nội bộ (cây bất biến
    theo scale nên không cần chuẩn hoá). Chỉ chạy khi có sklearn."""

    def fit(self, X, lab):
        self.mu_ = np.nanmean(X, axis=0)
        self.mu_ = np.where(np.isfinite(self.mu_), self.mu_, 0.0)
        self.clf_ = RandomForestClassifier(
            n_estimators=200, max_depth=4, class_weight="balanced",
            random_state=0, n_jobs=1).fit(self._imp(X), lab)
        return self

    def _imp(self, X):
        Xi = np.array(X, dtype=float, copy=True)
        idx = np.where(~np.isfinite(Xi))
        if idx[0].size:
            Xi[idx] = np.take(self.mu_, idx[1])
        return Xi

    def predict(self, X):
        return self.clf_.predict(self._imp(X))


def _qual_label(y, thresholds):
    return np.digitize(y, thresholds)  # 0=ít, 1=vừa, 2=tốt


def _macro_f1(t, p):
    fs = []
    for c in (0, 1, 2):
        tp = int(((p == c) & (t == c)).sum())
        fp = int(((p == c) & (t != c)).sum())
        fn = int(((p != c) & (t == c)).sum())
        pr = tp / (tp + fp) if tp + fp else 0.0
        rc = tp / (tp + fn) if tp + fn else 0.0
        fs.append(2 * pr * rc / (pr + rc) if pr + rc else 0.0)
    return float(np.mean(fs))


def classify_eval(X, y, warmup: int) -> Optional[dict]:
    """Walk-forward phân loại chất lượng ngày: trả confusion matrix + macro-F1 + baseline.

    Ngưỡng tercile tính từ y[:i] (quá khứ) mỗi bước -> không leakage. So với baseline 'đoán lớp
    đông nhất'. None nếu không có sklearn hoặc quá ít dữ liệu.
    """
    if not _HAS_SKLEARN or len(y) - warmup < 12:
        return None
    T, P, Tb, Pb = [], [], [], []
    for i in range(warmup, len(y)):
        th = np.quantile(y[:i], [1.0 / 3, 2.0 / 3])
        lab = _qual_label(y[:i + 1], th)
        clf = DayQualityClassifier().fit(X[:i], lab[:i])
        P.append(int(clf.predict(X[i:i + 1])[0]))
        T.append(int(lab[i]))
        vals, cnts = np.unique(lab[:i], return_counts=True)
        Pb.append(int(vals[cnts.argmax()]))
        Tb.append(int(lab[i]))
    T, P, Tb, Pb = (np.array(a) for a in (T, P, Tb, Pb))
    cm = [[int(((T == a) & (P == b)).sum()) for b in (0, 1, 2)] for a in (0, 1, 2)]
    return {
        "labels": QUAL_LABELS,
        "cm": cm,                                          # hàng=thực, cột=dự
        "macro_f1": round(_macro_f1(T, P), 3),
        "acc": round(float((T == P).mean()), 3),
        "baseline_f1": round(_macro_f1(Tb, Pb), 3),
        "baseline_acc": round(float((Tb == Pb).mean()), 3),
        "extreme": int(cm[0][2] + cm[2][0]),               # lỗi nguy hiểm: ít<->tốt
        "n": int(len(T)),
    }


def _make_hgb():
    return HistGradientBoostingRegressor(
        max_iter=300, learning_rate=0.05, max_depth=3,
        min_samples_leaf=8, l2_regularization=1.0,
        early_stopping=False, random_state=0,
    )


# ------------------------------ đánh giá ------------------------------
def metrics(y_true, y_pred) -> dict:
    e = y_pred - y_true
    mae = float(np.mean(np.abs(e)))
    rmse = float(np.sqrt(np.mean(e * e)))
    denom = np.maximum(np.abs(y_true), 1.0)
    mape = float(np.mean(np.abs(e) / denom) * 100.0)
    ss_res = float(np.sum(e * e))
    ss_tot = float(np.sum((y_true - y_true.mean()) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 1e-9 else 0.0
    n = len(y_true)
    se = float(np.std(np.abs(e)) / math.sqrt(n)) if n else 0.0  # sai số chuẩn của MAE
    return {"mae": mae, "rmse": rmse, "mape": mape, "r2": r2,
            "bias": float(np.mean(e)), "se": se, "n": int(n)}


def walk_forward(X, y, make_model: Callable, warmup: int = 30) -> tuple:
    """train trên [0..i), dự báo i, bước tiến. Trả (y_true, y_pred) đã căn."""
    yt, yp = [], []
    for i in range(warmup, len(y)):
        m = make_model()
        m.fit(X[:i], y[:i])
        yp.append(float(m.predict(X[i:i + 1])[0]))
        yt.append(float(y[i]))
    return np.array(yt), np.array(yp)


def _wf_climatology(y, warmup):
    yt, yp = [], []
    for i in range(warmup, len(y)):
        yp.append(float(y[:i].mean()))
        yt.append(float(y[i]))
    return np.array(yt), np.array(yp)


def _wf_persistence(y, warmup):
    yt, yp = [], []
    for i in range(warmup, len(y)):
        yp.append(float(y[i - 1]))
        yt.append(float(y[i]))
    return np.array(yt), np.array(yp)


# Lưới mô hình tham gia chạy đua. name -> (factory, độ-phản-ứng-thời-tiết 0..1).
# Độ phản ứng cao = dự báo bám theo thời tiết nhiều (hữu ích cho kế hoạch ngày mai);
# 0 = phẳng (khí hậu). Dùng để chọn mô hình hữu ích nhất TRONG vùng sai số tương đương.
def _candidates() -> dict:
    c = {f"ridge(a={a})": (lambda a=a: Ridge(alpha=a), 1.0 / math.sqrt(a))
         for a in (3.0, 10.0, 30.0, 100.0, 300.0)}
    c["climatology"] = (lambda: MeanModel(half_life=45.0), 0.0)
    c["climatology_flat"] = (lambda: MeanModel(half_life=None), 0.0)
    # (2026-06-24: đã thử mô hình bão hoà/censored min(tiềm năng, trần) -> MAE 4.30 > climatology
    #  4.00; có giảm bias ngày cực (−4.5→−3.4) nhưng phá tercile giữa (MAE 1.4→3.5) nên revert.
    #  Bias curtailment KHÔNG vá được bằng thời tiết — cần tải+SOC pin. Xem [[Decisions]].)
    if _HAS_SKLEARN:
        c["hist_gbm"] = (_make_hgb, 0.6)
    return c


def bake_off(dates, X, y, warmup: int = 30) -> dict:
    """Chạy đua mọi mô hình + baseline, chọn cái MAE thấp nhất. Trả scoreboard + lựa chọn."""
    board = []
    # baselines
    for name, (yt, yp) in (
        ("baseline:climatology", _wf_climatology(y, warmup)),
        ("baseline:persistence", _wf_persistence(y, warmup)),
    ):
        board.append({"name": name, "kind": "baseline", **metrics(yt, yp)})
    # heuristic cũ (cần rad gốc = X[:,0])
    radcol = X[:, FEATURES.index("rad")]
    yt_h, yp_h = [], []
    for i in range(warmup, len(y)):
        last = slice(max(0, i - 30), i)
        avg = float(np.nanmean(y[last]))
        ref = float(np.nanmean(radcol[last]))
        best = float(np.nanmax(y[:i]))
        ri = radcol[i]
        if not np.isfinite(ri) or ref <= 0:
            est = avg
        else:
            est = min(avg * min(1.45, max(0.35, ri / ref)), best * 1.05)
        yp_h.append(est)
        yt_h.append(float(y[i]))
    board.append({"name": "baseline:heuristic", "kind": "baseline",
                  **metrics(np.array(yt_h), np.array(yp_h))})

    # mô hình thật (có thể phục vụ): ridge / GBM / climatology
    cands = _candidates()
    for name, (make, resp) in cands.items():
        try:
            yt, yp = walk_forward(X, y, make, warmup)
            board.append({"name": name, "kind": "model", "resp": resp, **metrics(yt, yp)})
        except Exception as e:  # pragma: no cover
            board.append({"name": name, "kind": "model", "resp": resp, "error": str(e)})

    board.sort(key=lambda r: r.get("mae", float("inf")))
    models = [r for r in board if r.get("kind") == "model" and "mae" in r]
    best = models[0] if models else None
    chosen = best
    if best:
        # Vùng "hoà về thống kê": MAE trong best_MAE + 0.5·SE(best). Trong vùng đó,
        # ưu tiên mô hình PHẢN ỨNG THỜI TIẾT mạnh nhất (hữu ích hơn mà chính xác ~ngang).
        tol = best["mae"] + 0.5 * best.get("se", 0.0)
        eligible = [r for r in models if r["mae"] <= tol]
        chosen = max(eligible, key=lambda r: (r.get("resp", 0.0), -r["mae"]))
    return {"board": board, "best": best, "chosen": chosen,
            "warmup": warmup, "n": int(len(y))}


# ------------------------------ Forecaster ------------------------------
class SolarForecaster:
    """Giữ mô hình tốt nhất đã chọn + chấm điểm; dự báo sản lượng cho ngày tới."""

    def __init__(self):
        self.ready = False
        self.model = None
        self.model_name = None
        self.quality: dict = {}
        self.cap = None        # trần kẹp dự báo (best quan sát × 1.1)
        self.n_train = 0
        self.updated_at = None
        # Chuỗi chấm điểm walk-forward của mô hình ĐƯỢC CHỌN (cho overlay "Độ chính xác").
        # [{day, actual, pred}] — pred là dự báo train-trên-quá-khứ (không leakage), cùng
        # dữ liệu dùng tính điểm CV. Rỗng cho tới khi fit() chạy xong.
        self.backtest: list = []
        # Hướng C: phân loại chất lượng ngày (nắng tốt/vừa/ít).
        self.clf_quality = None    # confusion matrix + macro-F1 (walk-forward) cho tab dev
        self.day_clf = None        # classifier huấn luyện trên TOÀN bộ -> phân loại ngày tới
        self.qual_th = None        # [P33, P67] sản lượng -> ngưỡng phân lớp
        # State của lần fit gần nhất cho backtest_for() (trang "Độ chính xác": chọn model xem
        # thử). Gói TẤT CẢ vào MỘT tuple gán nguyên khối trong fit() -> backtest_for() đọc đúng
        # 1 lần là có snapshot nhất quán, KHÔNG cần khoá (xem docstring backtest_for).
        # (dates, X, y, warmup, cap, cache) — cache: name -> kết quả, dùng chung 1 thế hệ fit.
        self._bt_state = None

    @property
    def available(self) -> bool:
        return _HAS_NUMPY

    def fit(self, training_rows: list, today: Optional[str] = None) -> bool:
        if not _HAS_NUMPY:
            self.ready = False
            return False
        # Bỏ NGÀY HÔM NAY (và mọi ngày >= hôm nay): kwh hôm nay còn dở dang (ngày chưa
        # kết thúc) -> nhãn sai, sẽ làm lệch cả huấn luyện lẫn điểm số.
        if today:
            training_rows = [r for r in training_rows
                             if r.get("day") and r["day"] < today]
        if len(training_rows) < 20:
            self.ready = False
            return False
        dates, X, y = build_matrix(training_rows)
        if len(y) < 20:
            self.ready = False
            return False
        warmup = max(14, min(30, len(y) // 3))
        res = bake_off(dates, X, y, warmup=warmup)
        chosen = res["chosen"] or res["best"]
        cands = _candidates()
        entry = cands.get(chosen["name"]) if chosen else None
        make = entry[0] if entry else (lambda: Ridge(alpha=30.0))
        if not chosen:
            chosen = {"name": "ridge(a=30.0)"}
        self.model = make().fit(X, y)         # huấn luyện lại mô hình ĐƯỢC CHỌN trên TOÀN bộ
        self.model_name = chosen["name"]
        self.cap = float(np.nanmax(y)) * 1.10
        self.n_train = int(len(y))
        self.updated_at = today or date.today().isoformat()
        # Gán NGUYÊN KHỐI (một phép gán) -> backtest_for() không bao giờ thấy nửa cũ nửa mới.
        self._bt_state = (dates, X, y, res["warmup"], self.cap, {})

        # Chuỗi dự báo-vs-thực-tế cho overlay (walk-forward của CHÍNH mô hình được chọn,
        # train trên [0..i) -> dự báo i: không leakage). bake_off đã chạy walk_forward cho
        # mọi ứng viên nhưng vứt mảng đi; chạy lại đúng 1 lượt cho mô hình được chọn rẻ hơn
        # là đổi hợp đồng trả về của bake_off. Chỉ chạy 12h/lần trong backfill_loop.
        try:
            yt, yp = walk_forward(X, y, make, res["warmup"])
            bdates = dates[res["warmup"]:]
            self.backtest = [
                {"day": bdates[i],
                 "actual": round(float(yt[i]), 1),
                 "pred": round(min(max(float(yp[i]), 0.0), self.cap), 1)}
                for i in range(len(yt))
            ]
        except Exception:
            self.backtest = []

        # Hướng C: phân loại chất lượng ngày (nắng tốt/vừa/ít). Chấm walk-forward (cho tab dev)
        # + huấn luyện classifier trên TOÀN bộ để phân loại các ngày tới. Lỗi không làm hỏng
        # dự báo hồi quy (đã có).
        try:
            self.clf_quality = classify_eval(X, y, res["warmup"])
            if _HAS_SKLEARN and self.clf_quality:
                th = np.quantile(y, [1.0 / 3, 2.0 / 3])
                self.day_clf = DayQualityClassifier().fit(X, _qual_label(y, th))
                self.qual_th = [round(float(th[0]), 1), round(float(th[1]), 1)]
            else:
                self.day_clf = None
        except Exception:
            self.clf_quality = None
            self.day_clf = None

        climo = next((r for r in res["board"] if r["name"] == "baseline:climatology"), {})
        heur = next((r for r in res["board"] if r["name"] == "baseline:heuristic"), {})
        bm = next((r for r in res["board"] if r["name"] == chosen["name"]), {})
        best = res["best"] or bm

        def skill(ref):
            rm = ref.get("mae")
            return None if not rm else round(1.0 - bm.get("mae", rm) / rm, 3)

        self.quality = {
            "model": chosen["name"],
            "cv": "walk-forward",
            "n_train": int(len(y)),
            "warmup": res["warmup"],
            "mae": round(bm.get("mae", 0.0), 2),
            "rmse": round(bm.get("rmse", 0.0), 2),
            "mape": round(bm.get("mape", 0.0), 1),
            "r2": round(bm.get("r2", 0.0), 3),
            "bias": round(bm.get("bias", 0.0), 2),
            "cv_best_model": best.get("name"),
            "cv_best_mae": round(best.get("mae", 0.0), 2),
            "weather_responsive": (chosen.get("resp", 0.0) or 0.0) > 0,
            "skill_vs_climatology": skill(climo),
            "skill_vs_heuristic": skill(heur),
            # Điểm CV đo trên bức xạ ERA5 (archive); lúc phục vụ dùng bức xạ dự báo
            # -> điểm thật khi triển khai có thể nhỉnh hơn chút (xem docstring đầu file).
            "source": "train=archive(ERA5)·serve=forecast",
            "board": res["board"],
        }
        self.ready = True
        return True

    def backtest_for(self, name: str) -> Optional[dict]:
        """Walk-forward THEO YÊU CẦU cho một ứng viên trong _candidates() — trang "Độ chính
        xác" chọn model xem thử. Dùng đúng ma trận + warmup của lần fit gần nhất nên điểm số
        so sánh được với scoreboard. Kết quả cache tới lần fit sau (12h). None = chưa sẵn
        sàng / tên model lạ. CPU-bound (GBM ~vài giây) -> caller chạy trong executor.

        KHÔNG khoá, CỐ Ý (2026-07-17: bản đầu bọc `_forecast_lock` -> mỗi cú bấm model trên
        trang xếp hàng sau backfill 12h/lần, đo thật trên host 10,7s cho một model tính mất
        vài ms). An toàn nhờ đọc `_bt_state` đúng MỘT lần: fit() thay nguyên tuple chứ không
        sửa tại chỗ, nên ta luôn có snapshot nhất quán (ma trận + cap + cache cùng một thế hệ).
        Nếu fit() chen giữa chừng: kết quả tính trên ma trận cũ và ghi vào cache cũ (bị bỏ,
        GC dọn) — số trả về vẫn đúng với thế hệ đã đọc, không lẫn cũ/mới."""
        state = self._bt_state          # <- đọc 1 lần; mọi thứ dưới đây dùng snapshot này
        if not self.ready or state is None:
            return None
        dates, X, y, warmup, cap, cache = state
        hit = cache.get(name)
        if hit is not None:
            return hit
        entry = _candidates().get(name)
        if entry is None:
            return None
        yt, yp = walk_forward(X, y, entry[0], warmup)
        bdates = dates[warmup:]
        cap = cap or float("inf")
        m = metrics(yt, yp)
        out = {
            "model": name,
            "mae": round(m["mae"], 2), "rmse": round(m["rmse"], 2),
            "mape": round(m["mape"], 1), "r2": round(m["r2"], 3),
            "bias": round(m["bias"], 2),
            "points": [
                {"day": bdates[i],
                 "actual": round(float(yt[i]), 1),
                 "pred": round(min(max(float(yp[i]), 0.0), cap), 1)}
                for i in range(len(yt))
            ],
        }
        cache[name] = out               # cache của ĐÚNG thế hệ đã đọc (không đụng self)
        return out

    def predict_one(self, day: str, weather: dict) -> Optional[float]:
        if not self.ready or self.model is None:
            return None
        x = np.array([[np.nan if v is None else v for v in feature_row(day, weather)]],
                     dtype=float)
        val = float(self.model.predict(x)[0])
        val = max(0.0, val)
        if self.cap:
            val = min(val, self.cap)
        return val

    def predict_days(self, weather_by_day: dict, days: list) -> list:
        out = []
        rmse = self.quality.get("rmse")
        for day in days:
            w = weather_by_day.get(day)
            kwh = self.predict_one(day, w) if w else None
            item = {"date": day, "kwh": None if kwh is None else round(kwh, 1)}
            if kwh is not None and rmse:
                item["lo"] = round(max(0.0, kwh - rmse), 1)
                item["hi"] = round(kwh + rmse, 1)
            if w:
                item["wcode"] = w.get("wcode")
                item["tmax"] = w.get("tmax")
                item["tmin"] = w.get("tmin")
                item["rain_prob"] = w.get("rain_prob")
                # Hướng C: phân loại chất lượng ngày (nắng tốt/vừa/ít) — robust hơn số kWh
                if self.day_clf is not None:
                    try:
                        xc = np.array([[np.nan if v is None else v
                                        for v in feature_row(day, w)]], dtype=float)
                        item["qual"] = QUAL_LABELS[int(self.day_clf.predict(xc)[0])]
                    except Exception:
                        pass
            out.append(item)
        return out
