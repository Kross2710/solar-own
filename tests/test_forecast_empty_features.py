"""Empty feature columns must be handled deliberately, not through a numpy warning.

Regression tests for #35: `np.nanmean` over an all-NaN column raised
`RuntimeWarning: Mean of empty slice` and the column was silently imputed with 0,
so a weather feature without data disabled itself invisibly.
"""
import asyncio
import contextlib
import io
import warnings
from datetime import date, timedelta
from unittest.mock import patch

import numpy as np

from providers.forecast import (
    FEATURES,
    DayQualityClassifier,
    Ridge,
    SolarForecaster,
    build_matrix,
    column_means,
    empty_feature_columns,
    _HAS_SKLEARN,
    _qual_label,
)
from backend.services import forecast as forecast_service
from tests.test_optimization import FakeRuntime, FakeStore, _weather

END = date(2026, 2, 11)


def _rows(n_days: int, *, blank_column: str | None = None) -> list[dict]:
    rows = []
    for i in range(n_days):
        day = (END - timedelta(days=n_days - i)).isoformat()
        row = {"day": day, "kwh": 20.0 + (i % 5), "rad": 18.0 + (i % 4),
               "sun": 30000.0 + i, "daylight": 42000.0, "tmax": 32.0, "tmin": 24.0,
               "precip": 1.0, "precip_h": 2.0, "et0": 4.0}
        if blank_column:
            row[blank_column] = None
        rows.append(row)
    return rows


def _no_runtime_warning(value):
    """Fail the test if evaluating `value` emits any RuntimeWarning."""
    with warnings.catch_warnings():
        warnings.simplefilter("error", RuntimeWarning)
        return value()


class TestBuildMatrix:
    def test_no_rows_keeps_a_two_dimensional_matrix(self):
        dates, X, y = build_matrix([])
        assert dates == []
        assert X.shape == (0, len(FEATURES))
        assert y.shape == (0,)

    def test_row_count_matches_feature_count(self):
        _, X, y = build_matrix(_rows(10))
        assert X.shape == (10, len(FEATURES))
        assert len(y) == 10


class TestColumnMeans:
    def test_all_nan_column_returns_zero_without_warning(self):
        _, X, _ = build_matrix(_rows(10, blank_column="et0"))
        means = _no_runtime_warning(lambda: column_means(X))
        assert means[FEATURES.index("et0")] == 0.0
        assert np.isfinite(means).all()

    def test_empty_matrix_returns_zero_per_feature(self):
        _, X, _ = build_matrix([])
        means = _no_runtime_warning(lambda: column_means(X))
        assert means.shape == (len(FEATURES),)
        assert (means == 0.0).all()

    def test_partial_column_average_ignores_nan(self):
        X = np.array([[1.0, np.nan], [3.0, np.nan], [5.0, 2.0]])
        means = _no_runtime_warning(lambda: column_means(X))
        assert means.tolist() == [3.0, 2.0]

    def test_matches_nanmean_when_every_column_has_data(self):
        _, X, _ = build_matrix(_rows(12))
        means = _no_runtime_warning(lambda: column_means(X))
        assert np.allclose(means, np.nanmean(X, axis=0))


class TestEmptyFeatureColumns:
    def test_reports_only_the_column_without_data(self):
        _, X, _ = build_matrix(_rows(10, blank_column="precip_h"))
        assert empty_feature_columns(X) == [FEATURES.index("precip_h")]

    def test_no_columns_reported_when_every_feature_has_data(self):
        _, X, _ = build_matrix(_rows(10))
        assert empty_feature_columns(X) == []

    def test_every_column_reported_for_an_empty_matrix(self):
        _, X, _ = build_matrix([])
        assert len(empty_feature_columns(X)) == len(FEATURES)


class TestModelsStayWarningFree:
    def test_ridge_fit_on_all_nan_column(self):
        _, X, y = build_matrix(_rows(12, blank_column="et0"))
        model = _no_runtime_warning(lambda: Ridge(alpha=10.0).fit(X, y))
        assert np.isfinite(model.beta_).all()
        # The disabled feature is imputed to 0 and therefore centres to 0.
        assert model.xmean_[FEATURES.index("et0")] == 0.0

    def test_ridge_fit_on_empty_matrix_only_needs_column_means(self):
        # fit() is never reached with <20 rows (SolarForecaster.fit guards that), but the
        # column step must not warn or index a 1-dimensional matrix.
        _, X, _ = build_matrix([])
        means = _no_runtime_warning(lambda: column_means(X))
        assert means.shape == (len(FEATURES),)
        assert np.isfinite(means).all()

    def test_day_quality_classifier_fit_on_all_nan_column(self):
        if not _HAS_SKLEARN:
            return
        _, X, y = build_matrix(_rows(30, blank_column="et0"))
        thresholds = np.quantile(y, [1.0 / 3, 2.0 / 3])
        labels = _qual_label(y, thresholds)
        _no_runtime_warning(lambda: DayQualityClassifier().fit(X, labels))


class TestForecasterReportsDisabledFeatures:
    def test_quality_lists_the_feature_without_data(self):
        forecaster = SolarForecaster()
        assert forecaster.fit(_rows(40, blank_column="et0"), END.isoformat())
        assert forecaster.empty_features == ["et0"]
        assert forecaster.quality["empty_features"] == ["et0"]

    def test_quality_is_empty_when_every_feature_has_data(self):
        forecaster = SolarForecaster()
        assert forecaster.fit(_rows(40), END.isoformat())
        assert forecaster.empty_features == []
        assert forecaster.quality["empty_features"] == []

    def test_training_still_forecasts_with_a_disabled_feature(self):
        forecaster = SolarForecaster()
        assert forecaster.fit(_rows(40, blank_column="et0"), END.isoformat())
        day = (END + timedelta(days=1)).isoformat()
        weather = {day: {"rad": 20.0, "sun": 32000.0, "daylight": 42000.0,
                         "tmax": 33.0, "tmin": 25.0, "precip": 0.0, "precip_h": 0.0,
                         "et0": None}}
        prediction = forecaster.predict_days(weather, [day])[0]
        assert prediction["kwh"] is not None


class TestAccuracyEndpointReportsDisabledFeatures:
    """#35 asks for the dropped features in the `quality` block of /api/forecast/accuracy."""

    def test_backtest_result_lists_the_feature_without_data(self):
        forecaster = SolarForecaster()
        assert forecaster.fit(_rows(40, blank_column="et0"), END.isoformat())
        result = forecaster.backtest_for(forecaster.model_name)
        assert result is not None
        assert result["empty_features"] == ["et0"]

    def test_backtest_result_is_empty_when_every_feature_has_data(self):
        forecaster = SolarForecaster()
        assert forecaster.fit(_rows(40), END.isoformat())
        result = forecaster.backtest_for("baseline:climatology")
        assert result is not None
        assert result["empty_features"] == []

    def test_forecast_payload_carries_the_quality_block(self):
        runtime = FakeRuntime(FakeStore())
        forecaster = runtime.forecaster
        assert forecaster.fit(_rows(40, blank_column="et0"), END.isoformat())
        payload = asyncio.run(forecast_service.build_forecast(runtime))  # type: ignore[arg-type]
        assert payload["ready"] is True
        assert payload["quality"]["empty_features"] == ["et0"]


class TestRefreshLogsDisabledFeatures:
    """The defect was invisible in the journal; a disabled feature must be logged."""

    def test_refresh_prints_a_warning_naming_the_feature(self):
        runtime = FakeRuntime(FakeStore())

        async def blank_weather(*_args, **_kwargs):
            return {row["day"]: {**_weather(row["day"], 18.0), "et0": None}
                    for row in runtime.store.daily_full(4000)}

        with patch.object(forecast_service.fc_mod, "fetch_archive_weather", blank_weather), \
                patch.object(forecast_service.fc_mod, "fetch_daily_weather", blank_weather):
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                assert asyncio.run(forecast_service.refresh_forecast(runtime)) is True  # type: ignore[arg-type]
        logged = output.getvalue()
        assert "WARNING" in logged
        assert "et0" in logged
