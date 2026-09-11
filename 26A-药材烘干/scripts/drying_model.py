"""圆柱形药材热风烘干的热湿耦合求解器。

模型（半径 R，径向坐标 r，轴向均匀）：

    质量：dC/dt = (1/r) * d/dr ( D(C,T) * r * dC/dr )
    热量：dT/dt = (1/r) * d/dr ( alpha(C) * r * dT/dr ),  alpha = k(C) / (rho(C)*cp(C))

边界条件：

    r = R :  -D dC/dr = h_m (C - C_air(t)),  -alpha dT/dr = h/(rho*cp) * (T - T_air(t))
    r = 0 :  dC/dr = 0,  dT/dr = 0

数值方法：节点中心有限体积，隐式（后向 Euler）时间推进，系数取上一时刻值做线性化。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import numpy as np
from scipy.linalg import solve_banded


@dataclass
class Properties:
    """物性与扩散系数：全部以 (C, T) 为自变量，T 为摄氏温度。"""

    rho: Callable[[np.ndarray, np.ndarray], np.ndarray]
    cp: Callable[[np.ndarray, np.ndarray], np.ndarray]
    k: Callable[[np.ndarray, np.ndarray], np.ndarray]
    d: Callable[[np.ndarray, np.ndarray], np.ndarray]


@dataclass
class SolveResult:
    times: np.ndarray
    radii: np.ndarray
    temperature: np.ndarray
    moisture: np.ndarray
    meta: dict = field(default_factory=dict)


def _tridiagonal(lower: np.ndarray, diag: np.ndarray, upper: np.ndarray, rhs: np.ndarray) -> np.ndarray:
    ab = np.zeros((3, diag.size), dtype=float)
    ab[0, 1:] = upper[:-1]
    ab[1, :] = diag
    ab[2, :-1] = lower[1:]
    return solve_banded((1, 1), ab, rhs, check_finite=False)


def _mass_matrix(d_eff: np.ndarray, r: np.ndarray, dr: float, hm_eff: float, radius: float, dt: float) -> tuple:
    """组装质量扩散的隐式三对角系统（固定半径）。

    r_face[k] 表示节点 k 与 k+1 之间的界面半径，d_face[k] 为该界面上的扩散系数。
    """
    n = r.size
    lower = np.zeros(n)
    diag = np.zeros(n)
    upper = np.zeros(n)
    r_face = r[:-1] + dr / 2.0
    d_face = 0.5 * (d_eff[:-1] + d_eff[1:])

    diag[0] = 1.0 / dt + 4.0 * d_face[0] / dr**2
    upper[0] = -4.0 * d_face[0] / dr**2

    denom = r[1:-1] * dr**2
    coef_up = r_face[1:] * d_face[1:] / denom
    coef_low = r_face[:-1] * d_face[:-1] / denom
    lower[1:-1] = -coef_low
    upper[1:-1] = -coef_up
    diag[1:-1] = 1.0 / dt + coef_low + coef_up

    half = radius - dr / 2.0
    volume = (radius**2 - half**2) / 2.0
    a_in = half * d_face[-1] / dr
    lower[-1] = -a_in / volume
    diag[-1] = 1.0 / dt + (a_in + radius * hm_eff) / volume
    return lower, diag, upper, radius * hm_eff / volume


def solve_cylinder(
    props: Properties,
    radius: float,
    t_end: float,
    dt: float,
    n_cells: int,
    t_initial: float,
    c_initial: float,
    t_air: Callable[[float], float],
    c_air: Callable[[float], float],
    h: float,
    h_m: float,
    record_every: int = 1,
    stop_moisture: float | None = None,
    max_steps: int | None = None,
    keep_index: np.ndarray | None = None,
) -> SolveResult:
    """固定半径圆柱的隐式有限体积求解。"""
    dr = radius / n_cells
    r = np.linspace(0.0, radius, n_cells + 1)
    n = r.size
    temperature = np.full(n, float(t_initial))
    moisture = np.full(n, float(c_initial))

    keep = np.arange(n) if keep_index is None else np.asarray(keep_index, dtype=int)
    times: list[float] = [0.0]
    temp_hist: list[np.ndarray] = [temperature[keep].copy()]
    moist_hist: list[np.ndarray] = [moisture[keep].copy()]

    total = int(round(t_end / dt))
    if max_steps is not None:
        total = min(total, int(max_steps))
    stop_index = None
    for step in range(1, total + 1):
        t_now = step * dt
        rho = props.rho(moisture, temperature)
        cp = props.cp(moisture, temperature)
        k = props.k(moisture, temperature)
        diff = props.d(moisture, temperature)
        alpha = k / (rho * cp)

        lower, diag, upper, src = _mass_matrix(diff, r, dr, h_m, radius, dt)
        rhs = moisture / dt
        rhs[-1] += src * float(c_air(t_now))
        moisture = _tridiagonal(lower, diag, upper, rhs)

        lower, diag, upper, src = _mass_matrix(alpha, r, dr, h / (rho[-1] * cp[-1]), radius, dt)
        rhs = temperature / dt
        rhs[-1] += src * float(t_air(t_now))
        temperature = _tridiagonal(lower, diag, upper, rhs)

        stopped = stop_moisture is not None and float(moisture.max()) < stop_moisture
        if stopped or step % max(int(record_every), 1) == 0:
            times.append(t_now)
            temp_hist.append(temperature[keep].copy())
            moist_hist.append(moisture[keep].copy())
        if stopped:
            stop_index = step
            break

    return SolveResult(
        times=np.array(times),
        radii=r[keep],
        temperature=np.array(temp_hist),
        moisture=np.array(moist_hist),
        meta={
            "dr_cm": dr * 100.0,
            "dt_s": dt,
            "steps": len(times) - 1,
            "stop_index": stop_index,
            "stop_time_s": times[-1] if stop_index is not None else None,
            "radius_cm": radius * 100.0,
        },
    )


def solve_shrinking(
    props: Properties,
    radius_of: Callable[[float], float],
    rate_of: Callable[[float], float],
    t_end: float,
    dt: float,
    n_cells: int,
    t_initial: float,
    c_initial: float,
    t_air: Callable[[float], float],
    c_air: Callable[[float], float],
    h: float,
    h_m: float,
    record_every: int = 1,
    stop_moisture: float | None = None,
    max_steps: int | None = None,
) -> SolveResult:
    """收缩圆柱（移动边界）在固定坐标 xi = r / R(t) 上的求解。

    xi 空间控制方程：

        dC/dt|_xi = (D/(xi R^2)) * d/dxi ( xi dC/dxi ) + xi * (Rdot/R) * dC/dxi

    其中 Rdot = dR/dt <= 0 表示收缩。对流项用中心差分，扩散项用隐式有限体积。
    """
    dr = 1.0 / n_cells
    xi = np.linspace(0.0, 1.0, n_cells + 1)
    n = xi.size
    temperature = np.full(n, float(t_initial))
    moisture = np.full(n, float(c_initial))

    times: list[float] = [0.0]
    temp_hist: list[np.ndarray] = [temperature.copy()]
    moist_hist: list[np.ndarray] = [moisture.copy()]
    radius_hist: list[float] = [float(radius_of(0.0))]

    total = int(round(t_end / dt))
    if max_steps is not None:
        total = min(total, int(max_steps))
    stop_index = None
    xi_face = xi[:-1] + dr / 2.0
    weight = ((xi + dr / 2.0) ** 3 - (xi - dr / 2.0) ** 3) / 3.0

    for step in range(1, total + 1):
        t_now = step * dt
        radius = float(radius_of(t_now))
        rdot = float(rate_of(t_now))
        adv = rdot / radius

        rho = props.rho(moisture, temperature)
        cp = props.cp(moisture, temperature)
        k = props.k(moisture, temperature)
        diff = props.d(moisture, temperature)
        alpha = k / (rho * cp)

        moisture = _shrink_step(
            moisture, diff, xi, xi_face, weight, dr, radius, adv,
            h_m / radius, float(c_air(t_now)), dt,
        )
        temperature = _shrink_step(
            temperature, alpha, xi, xi_face, weight, dr, radius, adv,
            h / (rho[-1] * cp[-1] * radius), float(t_air(t_now)), dt,
        )

        stopped = stop_moisture is not None and float(moisture.max()) < stop_moisture
        if stopped or step % max(int(record_every), 1) == 0:
            times.append(t_now)
            temp_hist.append(temperature.copy())
            moist_hist.append(moisture.copy())
            radius_hist.append(radius)
        if stopped:
            stop_index = step
            break
    return SolveResult(
        times=np.array(times),
        radii=xi * radius_hist[-1],
        temperature=np.array(temp_hist),
        moisture=np.array(moist_hist),
        meta={
            "dt_s": dt,
            "steps": len(times) - 1,
            "stop_index": stop_index,
            "stop_time_s": times[-1] if stop_index is not None else None,
            "radius_hist_cm": [value * 100.0 for value in radius_hist],
        },
    )


def _shrink_step(u, d_eff, xi, xi_face, weight, dxi, radius, adv, hm_eff, ambient, dt):
    n = xi.size
    lower = np.zeros(n)
    diag = np.zeros(n)
    upper = np.zeros(n)
    scale = d_eff / radius**2
    d_face = 0.5 * (scale[:-1] + scale[1:])

    diag[0] = 1.0 / dt + 4.0 * d_face[0] / dxi**2
    upper[0] = -4.0 * d_face[0] / dxi**2

    denom = xi[1:-1] * dxi**2
    coef_up = xi_face[1:] * d_face[1:] / denom
    coef_low = xi_face[:-1] * d_face[:-1] / denom
    lower[1:-1] = -coef_low
    upper[1:-1] = -coef_up
    diag[1:-1] = 1.0 / dt + coef_low + coef_up

    volume = (1.0 - (1.0 - dxi / 2.0) ** 2) / 2.0
    a_in = (1.0 - dxi / 2.0) * d_face[-1] / dxi
    lower[-1] = -a_in / volume
    diag[-1] = 1.0 / dt + (a_in + hm_eff) / volume
    src = hm_eff / volume

    rhs = u / dt
    rhs[-1] += src * ambient

    if adv != 0.0:
        coef_adv = adv * weight / (2.0 * dxi)
        rhs[1:-1] += coef_adv[1:-1] * (u[2:] - u[:-2])
        rhs[0] += 0.0
        rhs[-1] += adv * weight[-1] * (u[-1] - u[-2]) / dxi
    return _tridiagonal(lower, diag, upper, rhs)


def properties_from_appendix2() -> Properties:
    """附录 2：常数物性 + 水分浓度相关的扩散系数（问题 1）。"""

    def rho(c, t):
        return np.full_like(c, 820.0)

    def cp(c, t):
        return np.full_like(c, 2600.0)

    def k(c, t):
        return np.full_like(c, 0.36)

    def d(c, t):
        return 7e-9 * np.exp(-0.89 / np.maximum(c, 1e-6))

    return Properties(rho=rho, cp=cp, k=k, d=d)


def properties_from_appendix3() -> Properties:
    """附录 3：随水分浓度变化的物性（问题 2、3）。"""

    def rho(c, t):
        return 650.0 + 128.0 * c

    def cp(c, t):
        return 1450.0 + 2736.0 * c / (c + 1.0)

    def k(c, t):
        return 0.21 + 0.38 * c / (c + 1.0)

    def d(c, t):
        tk = t + 273.15
        return 2.4e-3 * np.exp(-0.45 / np.maximum(c, 1e-6)) * np.exp(-3850.0 / tk)

    return Properties(rho=rho, cp=cp, k=k, d=d)


def properties_from_appendix4() -> Properties:
    """附录 4：随水分浓度变化的物性（问题 4，含收缩）。"""

    def rho(c, t):
        return 760.0 + 90.0 * c

    def cp(c, t):
        return 1850.0 + 2150.0 * c / (c + 1.0)

    def k(c, t):
        return 0.12 + 0.20 * c / (c + 1.0)

    def d(c, t):
        tk = t + 273.15
        return 4.2e-4 * np.exp(-0.30 / np.maximum(c, 1e-6)) * np.exp(-3850.0 / tk)

    return Properties(rho=rho, cp=cp, k=k, d=d)
