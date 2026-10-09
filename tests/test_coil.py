import numpy as np
from deltat_doctor.sim.coil import CP_W, CoilDesign, coil_duty, eps_counterflow, solve_flow


def test_effectiveness_bounds_and_limits():
    ntu = np.array([0.0, 0.5, 2.0, 20.0])
    for cr in (0.0, 0.5, 0.99, 1.0):
        e = eps_counterflow(ntu, cr)
        assert np.all(e >= 0) and np.all(e <= 1)
        assert np.all(np.diff(e) >= -1e-12)          # monotone in NTU
    assert abs(eps_counterflow(np.array([3.0]), np.array([0.0]))[0] - (1 - np.exp(-3.0))) < 1e-9
    assert abs(eps_counterflow(np.array([2.0]), np.array([1.0]))[0] - 2.0 / 3.0) < 1e-6


def test_design_point_is_met():
    d = CoilDesign([1000.0], [10.5])
    m_d = float(d.m_d[0])
    q = coil_duty(d, np.array([m_d]), np.array([1000.0 / 14.0]), 27.0, 6.0, np.array([0.0]))
    assert abs(q[0] - 1000.0) < 8.0                    # reproduces design duty


def test_duty_increases_with_flow():
    d = CoilDesign([800.0], [10.0])
    flows = np.linspace(0.05, 1.5, 12) * d.m_d[0]
    q = np.array([coil_duty(d, np.array([f]), np.array([60.0]), 27.0, 6.0, np.array([0.0]))[0] for f in flows])
    assert np.all(np.diff(q) > 0)


def test_solved_flow_meets_demand_and_conserves_energy():
    d = CoilDesign([1000.0], [10.5])
    lf = np.array([0.1, 0.4, 0.8])[:, None]
    q_dem = 1000.0 * lf
    c_air = q_dem / 14.0
    m, q = solve_flow(d, q_dem, c_air, 27.0, 6.0, np.array([0.0]))
    assert np.allclose(q, q_dem, rtol=1e-3)
    dt = q / (CP_W * m)
    assert np.all(dt > 0)


def test_fouling_needs_more_flow_and_lowers_delta_t():
    d = CoilDesign([1000.0], [10.5])
    q_dem = np.array([[700.0]]); c_air = q_dem / 14.0
    m0, q0 = solve_flow(d, q_dem, c_air, 27.0, 6.0, np.array([0.0]))
    m1, q1 = solve_flow(d, q_dem, c_air, 27.0, 6.0, np.array([0.6]))
    assert m1[0, 0] > m0[0, 0]
    assert q1[0, 0] / m1[0, 0] < q0[0, 0] / m0[0, 0]


def test_saturation_reports_unmet_load():
    d = CoilDesign([1000.0], [10.5])
    q_dem = np.array([[1000.0]]); c_air = q_dem / 14.0
    m, q = solve_flow(d, q_dem, c_air, 27.0, 6.0, np.array([3.0]))
    assert q[0, 0] < 1000.0 - 1.0
    assert abs(m[0, 0] - 1.6 * d.m_d[0]) < 1e-9
