import numpy as np
import pandas as pd
from deltat_doctor.penalty import ContractTerms, KW_PER_RT, monthly_table, saving_from_gain, window_penalty


def test_no_surcharge_at_or_above_minimum():
    t = ContractTerms(8.9, 0.10, 1.0)
    assert window_penalty(8.9, 1000, t)["surcharge_aed"] == 0
    assert window_penalty(11.0, 1000, t)["surcharge_aed"] == 0


def test_ten_percent_per_degree():
    t = ContractTerms(8.9, 0.10, 2.0)
    p = window_penalty(6.9, 1000, t)          # 2 C short
    assert abs(p["surcharge_pct"] - 20.0) < 1e-9
    assert abs(p["surcharge_aed"] - 1000 * 2.0 * 0.20) < 1e-9


def test_saving_is_capped_at_reaching_minimum():
    t = ContractTerms(8.9, 0.10, 1.0)
    full = saving_from_gain(7.9, 1.0, 1000, t)       # reaches 8.9
    over = saving_from_gain(7.9, 5.0, 1000, t)       # beyond minimum saves no more
    assert abs(full - over) < 1e-9
    assert saving_from_gain(7.9, 0.0, 1000, t) == 0
    assert saving_from_gain(9.5, 1.0, 1000, t) == 0


def test_monthly_table_flow_weighted():
    ts = pd.date_range("2025-06-01", periods=48, freq="h")
    flow = np.full(48, 10.0)
    heat = 4.186 * flow * 7.0
    h = pd.DataFrame({"timestamp": ts, "flow_kgs": flow, "heat_kw": heat, "dt_c": 7.0, "t_outdoor_c": np.nan})
    tab = monthly_table(h, ContractTerms(8.9, 0.10, 1.0))
    assert len(tab) == 1
    assert abs(tab.loc[0, "delta_t_c"] - 7.0) < 1e-9
    assert abs(tab.loc[0, "rt_hr"] - heat.sum() / KW_PER_RT) < 1e-6
