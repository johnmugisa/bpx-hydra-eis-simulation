from __future__ import annotations

from pathlib import Path
import copy
import json

import numpy as np
import pybamm
import pybop


FARADAY = float(pybamm.constants.F.value)
GAS_CONSTANT = float(pybamm.constants.R.value)


def fnum(value, default=None) -> float:
    if value is None:
        if default is None:
            raise ValueError("Expected a number but got None.")
        return float(default)
    return float(value)


def load_bpx(bpx_file):
    bpx_file = Path(bpx_file)
    with open(bpx_file, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _pybamm_interpolant(x, y, child, name):
    try:
        return pybamm.Interpolant(x, y, child, interpolator="linear", name=name, extrapolate=True)
    except TypeError:
        return pybamm.Interpolant(x, y, [child], interpolator="linear", name=name, extrapolate=True)


def table_fun_1arg(table, name):
    x = np.asarray(table["x"], dtype=float)
    y = np.asarray(table["y"], dtype=float)
    order = np.argsort(x)
    x = x[order]
    y = y[order]

    def fun(z):
        if isinstance(z, pybamm.Symbol):
            return _pybamm_interpolant(x, y, z, name)
        return np.interp(z, x, y)

    return fun


def table_fun_ce(table, name):
    x = np.asarray(table["x"], dtype=float)
    y = np.asarray(table["y"], dtype=float)
    order = np.argsort(x)
    x = x[order]
    y = y[order]

    def fun(c_e, T=None):
        if isinstance(c_e, pybamm.Symbol):
            return _pybamm_interpolant(x, y, c_e, name)
        return np.interp(c_e, x, y)

    return fun


def interp_table_at(table, x0) -> float:
    xs = np.asarray(table["x"], dtype=float)
    ys = np.asarray(table["y"], dtype=float)
    order = np.argsort(xs)
    return float(np.interp(float(x0), xs[order], ys[order]))


def bruggeman_from_transport_efficiency(eps, transport_efficiency, default=1.5) -> float:
    try:
        eps = float(eps)
        transport_efficiency = float(transport_efficiency)
        if 0 < eps < 1 and transport_efficiency > 0:
            return float(np.log(transport_efficiency) / np.log(eps))
    except Exception:
        pass
    return float(default)


def state_initial_conditions(bpx):
    state = bpx.get("State", {})
    if not state:
        state = bpx.get("Parameterisation", {}).get("State", {})
    return state.get("InitialConditions", {}) or state.get("Initial conditions", {}) or {}


def state_thermal(bpx):
    state = bpx.get("State", {})
    if not state:
        state = bpx.get("Parameterisation", {}).get("State", {})
    return state.get("ThermalState", {}) or state.get("Thermal state", {}) or {}


def constant_exchange_current_density(j0_ref):
    j0_ref = float(j0_ref)

    def j0(c_e, c_s_surf, c_s_max, T):
        if any(isinstance(v, pybamm.Symbol) for v in [c_e, c_s_surf, c_s_max, T]):
            return pybamm.Scalar(j0_ref)
        return j0_ref

    return j0


def make_parameter_values(params):
    return pybamm.ParameterValues(values=dict(params))


def clean_parameter_dict_for_pybamm(params):
    clean = {}
    for key, value in params.items():
        if key.startswith("_"):
            continue
        if isinstance(value, str):
            continue
        if isinstance(value, dict):
            continue
        clean[key] = value
    return clean


def apply_capacitive_nyquist_convention(Z):
    Z = np.asarray(Z, dtype=complex)
    if np.nanmedian(-np.imag(Z)) < 0:
        Z = np.conjugate(Z)
    return Z


def capacity_scale(Z, capacity_Ah, unit):
    unit = unit.lower()
    if unit == "ohm":
        return Z, r"$\Omega$", "Ohm"
    if unit == "mohm":
        return 1000 * Z, r"m$\Omega$", "mOhm"
    if unit == "mohm_ah":
        return 1000 * Z * capacity_Ah, r"m$\Omega$ Ah", "mOhm_Ah"
    raise ValueError("unit must be 'ohm', 'mohm', or 'mohm_Ah'.")


def make_physical_params_from_bpx(bpx_or_file, soc=0.5, contact_resistance_ohm=0.0):
    if isinstance(bpx_or_file, (str, Path)):
        bpx = load_bpx(bpx_or_file)
    else:
        bpx = bpx_or_file

    P = bpx["Parameterisation"]
    cell = P["Cell"]
    elyte = P["Electrolyte"]
    neg = P["Negative electrode"]
    pos = P["Positive electrode"]
    sep = P["Separator"]
    user = P.get("User-defined", {})

    ic = state_initial_conditions(bpx)
    thermal = state_thermal(bpx)

    area_one_pair = fnum(cell["Electrode area [m2]"])
    n_parallel = fnum(cell.get("Number of electrode pairs connected in parallel to make a cell", 1.0))
    side = float(np.sqrt(area_one_pair))
    effective_area = area_one_pair * n_parallel

    c_n_max = fnum(neg["Maximum concentration [mol.m-3]"])
    c_p_max = fnum(pos["Maximum concentration [mol.m-3]"])

    x_n_min = fnum(neg.get("Minimum stoichiometry", 0.0))
    x_n_max = fnum(neg.get("Maximum stoichiometry", 1.0))
    x_p_min = fnum(pos.get("Minimum stoichiometry", 0.0))
    x_p_max = fnum(pos.get("Maximum stoichiometry", 1.0))

    x_n0 = x_n_min + soc * (x_n_max - x_n_min)
    x_p0 = x_p_max - soc * (x_p_max - x_p_min)

    c_e0 = fnum(
        ic.get(
            "Initial electrolyte concentration [mol.m-3]",
            ic.get("Initial concentration in electrolyte [mol.m-3]", 1200.0),
        )
    )

    T0 = fnum(ic.get("Initial temperature [K]", cell.get("Reference temperature [K]", 298.15)))
    T_amb = fnum(thermal.get("Ambient temperature [K]", T0))

    k_n = fnum(neg.get("Reaction rate constant [mol.m-2.s-1]", 1e-6))
    k_p = fnum(pos.get("Reaction rate constant [mol.m-2.s-1]", 1e-6))
    j0_n_ref = FARADAY * k_n
    j0_p_ref = FARADAY * k_p

    eps_n = fnum(neg["Porosity"])
    eps_p = fnum(pos["Porosity"])
    eps_s = fnum(sep["Porosity"])

    alpha_n = fnum(user.get("Negative electrode active material volume fraction", 1 - eps_n))
    alpha_p = fnum(user.get("Positive electrode active material volume fraction", 1 - eps_p))

    b_n_e = bruggeman_from_transport_efficiency(eps_n, neg.get("Transport efficiency"))
    b_p_e = bruggeman_from_transport_efficiency(eps_p, pos.get("Transport efficiency"))
    b_s_e = bruggeman_from_transport_efficiency(eps_s, sep.get("Transport efficiency"))

    params = {
        "chemistry": "lithium_ion",
        "Electrode height [m]": side,
        "Electrode width [m]": side,
        "Cell volume [m3]": fnum(
            cell.get(
                "Volume [m3]",
                effective_area * (fnum(neg["Thickness [m]"]) + fnum(sep["Thickness [m]"]) + fnum(pos["Thickness [m]"])),
            )
        ),
        "Number of electrodes connected in parallel to make a cell": n_parallel,
        "Number of electrode pairs connected in parallel to make a cell": n_parallel,
        "Number of cells connected in series to make a battery": 1.0,
        "Nominal cell capacity [A.h]": fnum(cell.get("Nominal cell capacity [A.h]", 1.0)),
        "Current function [A]": 0.0,
        "Initial SoC": float(soc),
        "Contact resistance [Ohm]": float(contact_resistance_ohm),
        "Negative electrode thickness [m]": fnum(neg["Thickness [m]"]),
        "Separator thickness [m]": fnum(sep["Thickness [m]"]),
        "Positive electrode thickness [m]": fnum(pos["Thickness [m]"]),
        "Negative current collector thickness [m]": 1.0e-5,
        "Positive current collector thickness [m]": 1.0e-5,
        "Maximum concentration in negative electrode [mol.m-3]": c_n_max,
        "Initial concentration in negative electrode [mol.m-3]": x_n0 * c_n_max,
        "Negative particle radius [m]": fnum(neg["Particle radius [m]"]),
        "Negative particle diffusivity [m2.s-1]": fnum(neg["Diffusivity [m2.s-1]"]),
        "Negative electrode OCP [V]": table_fun_1arg(neg["OCP [V]"], "Negative electrode OCP [V]"),
        "Negative electrode exchange-current density [A.m-2]": constant_exchange_current_density(j0_n_ref),
        "Negative electrode exchange-current density reference [A.m-2]": j0_n_ref,
        "Negative electrode conductivity [S.m-1]": fnum(neg.get("Conductivity [S.m-1]", 100.0)),
        "Negative electrode porosity": eps_n,
        "Negative electrode active material volume fraction": alpha_n,
        "Negative electrode Bruggeman coefficient (electrolyte)": b_n_e,
        "Negative electrode Bruggeman coefficient (electrode)": 1.5,
        "Negative electrode double-layer capacity [F.m-2]": 0.02,
        "Negative electrode OCP entropic change [V.K-1]": fnum(neg.get("Entropic change coefficient [V.K-1]", 0.0)),
        "Maximum concentration in positive electrode [mol.m-3]": c_p_max,
        "Initial concentration in positive electrode [mol.m-3]": x_p0 * c_p_max,
        "Positive particle radius [m]": fnum(pos["Particle radius [m]"]),
        "Positive particle diffusivity [m2.s-1]": fnum(pos["Diffusivity [m2.s-1]"]),
        "Positive electrode OCP [V]": table_fun_1arg(pos["OCP [V]"], "Positive electrode OCP [V]"),
        "Positive electrode exchange-current density [A.m-2]": constant_exchange_current_density(j0_p_ref),
        "Positive electrode exchange-current density reference [A.m-2]": j0_p_ref,
        "Positive electrode conductivity [S.m-1]": fnum(pos.get("Conductivity [S.m-1]", 10.0)),
        "Positive electrode porosity": eps_p,
        "Positive electrode active material volume fraction": alpha_p,
        "Positive electrode Bruggeman coefficient (electrolyte)": b_p_e,
        "Positive electrode Bruggeman coefficient (electrode)": 1.5,
        "Positive electrode double-layer capacity [F.m-2]": 0.092,
        "Positive electrode OCP entropic change [V.K-1]": fnum(pos.get("Entropic change coefficient [V.K-1]", 0.0)),
        "Separator porosity": eps_s,
        "Separator Bruggeman coefficient (electrolyte)": b_s_e,
        "Initial concentration in electrolyte [mol.m-3]": c_e0,
        "Electrolyte diffusivity [m2.s-1]": table_fun_ce(elyte["Diffusivity [m2.s-1]"], "Electrolyte diffusivity [m2.s-1]"),
        "Electrolyte conductivity [S.m-1]": table_fun_ce(elyte["Conductivity [S.m-1]"], "Electrolyte conductivity [S.m-1]"),
        "Cation transference number": fnum(elyte["Cation transference number"]),
        "Thermodynamic factor": fnum(elyte.get("Thermodynamic factor", 1.0)),
        "Reference temperature [K]": fnum(cell.get("Reference temperature [K]", T0)),
        "Ambient temperature [K]": T_amb,
        "Initial temperature [K]": T0,
        "Lower voltage cut-off [V]": fnum(cell["Lower voltage cut-off [V]"]),
        "Upper voltage cut-off [V]": fnum(cell["Upper voltage cut-off [V]"]),
        "Open-circuit voltage at 0% SOC [V]": fnum(user.get("Open-circuit voltage at 0% SOC [V]", cell["Lower voltage cut-off [V]"])),
        "Open-circuit voltage at 100% SOC [V]": fnum(user.get("Open-circuit voltage at 100% SOC [V]", cell["Upper voltage cut-off [V]"])),
        "Negative current collector conductivity [S.m-1]": 5.96e7,
        "Positive current collector conductivity [S.m-1]": 3.55e7,
        "Negative current collector density [kg.m-3]": 8960.0,
        "Positive current collector density [kg.m-3]": 2700.0,
        "Negative current collector specific heat capacity [J.kg-1.K-1]": 385.0,
        "Positive current collector specific heat capacity [J.kg-1.K-1]": 897.0,
        "Negative current collector thermal conductivity [W.m-1.K-1]": 401.0,
        "Positive current collector thermal conductivity [W.m-1.K-1]": 237.0,
    }

    diagnostics = {
        "area_one_pair_m2": area_one_pair,
        "n_parallel": n_parallel,
        "effective_area_m2": effective_area,
        "height_times_width_m2": side * side,
        "c_e0_mol_m3": c_e0,
        "electrolyte_diffusivity_at_ce0_m2_s": interp_table_at(elyte["Diffusivity [m2.s-1]"], c_e0),
        "electrolyte_conductivity_at_ce0_S_m": interp_table_at(elyte["Conductivity [S.m-1]"], c_e0),
        "negative_j0_ref_A_m2": j0_n_ref,
        "positive_j0_ref_A_m2": j0_p_ref,
    }

    scalar_grouping_overrides = {
        "Electrolyte diffusivity [m2.s-1]": diagnostics["electrolyte_diffusivity_at_ce0_m2_s"],
        "Electrolyte conductivity [S.m-1]": diagnostics["electrolyte_conductivity_at_ce0_S_m"],
    }

    return params, diagnostics, scalar_grouping_overrides


def _tau_ct_from_j0_reference(params, electrode: str) -> float:
    if electrode.lower().startswith("p"):
        domain = "Positive"
    elif electrode.lower().startswith("n"):
        domain = "Negative"
    else:
        raise ValueError("electrode must be 'positive' or 'negative'")

    lower = domain.lower()
    cmax = float(params[f"Maximum concentration in {lower} electrode [mol.m-3]"])
    cs0 = float(params[f"Initial concentration in {lower} electrode [mol.m-3]"])
    radius = float(params[f"{domain} particle radius [m]"])
    j0_ref = float(params[f"{domain} electrode exchange-current density reference [A.m-2]"])
    theta0 = np.clip(cs0 / cmax, 1e-9, 1 - 1e-9)

    return float(FARADAY * cmax * radius * np.sqrt(theta0 * (1 - theta0)) / j0_ref)


def _prepare_grouping_params(params, scalar_grouping_overrides, use_total_area_for_grouping=True):
    grouping_params = copy.deepcopy(params)

    if use_total_area_for_grouping:
        area_one_pair = float(params["Electrode height [m]"]) * float(params["Electrode width [m]"])
        n_parallel = float(params.get("Number of electrodes connected in parallel to make a cell", 1.0))
        area_total = area_one_pair * n_parallel
        side_total = float(np.sqrt(area_total))

        grouping_params["Electrode height [m]"] = side_total
        grouping_params["Electrode width [m]"] = side_total
        grouping_params["Number of electrodes connected in parallel to make a cell"] = 1.0
        grouping_params["Number of electrode pairs connected in parallel to make a cell"] = 1.0

    grouping_params.update(scalar_grouping_overrides)
    grouping_params["Faraday constant [C.mol-1]"] = FARADAY
    grouping_params["Ideal gas constant [J.K-1.mol-1]"] = GAS_CONSTANT

    return grouping_params


def make_grouped_params_from_physical(
    params,
    scalar_grouping_overrides,
    tau_ct_mode="from_bpx_j0",
    tau_ct_multiplier=1.0,
    use_total_area_for_grouping=True,
    force_nominal_capacity=True,
):
    """
    Return:
        grouped_params, grouped_metadata

    grouped_params contains only numeric/callable model parameters.
    grouped_metadata contains labels/strings and is not passed to PyBaMM.
    """
    grouping_params = _prepare_grouping_params(
        params,
        scalar_grouping_overrides,
        use_total_area_for_grouping=use_total_area_for_grouping,
    )

    parameter_values_for_grouping = pybamm.ParameterValues(values=grouping_params)

    from pybop.models.lithium_ion.basic_SPMe import convert_physical_to_grouped_parameters

    try:
        grouped = convert_physical_to_grouped_parameters(
            parameter_values_for_grouping,
            measured_cell_capacity_as=params["Nominal cell capacity [A.h]"] * 3600,
            check_full_cell_capacity=False,
        )
    except TypeError:
        grouped = convert_physical_to_grouped_parameters(parameter_values_for_grouping)

    grouped["Negative electrode OCP [V]"] = params["Negative electrode OCP [V]"]
    grouped["Positive electrode OCP [V]"] = params["Positive electrode OCP [V]"]
    grouped["Initial SoC"] = float(params.get("Initial SoC", 0.5))
    grouped["Measured cell capacity from grouping [A.s]"] = float(grouped["Measured cell capacity [A.s]"])

    if force_nominal_capacity:
        grouped["Measured cell capacity [A.s]"] = float(params["Nominal cell capacity [A.h]"]) * 3600

    tau_ct_mode_label = tau_ct_mode

    if tau_ct_mode == "from_bpx_j0":
        grouped["Negative electrode charge transfer time scale [s]"] = _tau_ct_from_j0_reference(params, "negative")
        grouped["Positive electrode charge transfer time scale [s]"] = _tau_ct_from_j0_reference(params, "positive")
    elif tau_ct_mode == "multiplier":
        grouped["Negative electrode charge transfer time scale [s]"] = (
            float(grouped["Negative electrode charge transfer time scale [s]"]) * float(tau_ct_multiplier)
        )
        grouped["Positive electrode charge transfer time scale [s]"] = (
            float(grouped["Positive electrode charge transfer time scale [s]"]) * float(tau_ct_multiplier)
        )
        tau_ct_mode_label = f"multiplier_{tau_ct_multiplier}"
    elif tau_ct_mode == "converter":
        pass
    else:
        raise ValueError("tau_ct_mode must be 'from_bpx_j0', 'multiplier', or 'converter'.")

    grouped = clean_parameter_dict_for_pybamm(grouped)

    metadata = {
        "tau_ct_mode": tau_ct_mode_label,
        "tau_ct_multiplier": float(tau_ct_multiplier),
        "use_total_area_for_grouping": bool(use_total_area_for_grouping),
        "force_nominal_capacity": bool(force_nominal_capacity),
    }

    return grouped, metadata


def print_parameter_summary(params, diagnostics, grouped=None, grouped_metadata=None):
    print("\n" + "=" * 90)
    print("ALIGNED BPX PARAMETER SUMMARY")
    print("=" * 90)
    print("Nominal capacity [Ah]:", params["Nominal cell capacity [A.h]"])
    print("Electrode one-pair area [m2]:", diagnostics["area_one_pair_m2"])
    print("Number parallel:", diagnostics["n_parallel"])
    print("Effective area [m2]:", diagnostics["effective_area_m2"])
    print("Initial SoC:", params["Initial SoC"])
    print("Contact resistance [Ohm]:", params["Contact resistance [Ohm]"])
    print("c_e0 [mol m-3]:", diagnostics["c_e0_mol_m3"])
    print("D_e(c_e0) [m2 s-1]:", diagnostics["electrolyte_diffusivity_at_ce0_m2_s"])
    print("kappa_e(c_e0) [S m-1]:", diagnostics["electrolyte_conductivity_at_ce0_S_m"])
    print("Negative j0_ref [A m-2]:", diagnostics["negative_j0_ref_A_m2"])
    print("Positive j0_ref [A m-2]:", diagnostics["positive_j0_ref_A_m2"])

    if grouped is not None:
        print("\nGrouped parameters:")
        for key in [
            "Series resistance [Ohm]",
            "Negative electrode charge transfer time scale [s]",
            "Positive electrode charge transfer time scale [s]",
            "Negative particle diffusion time scale [s]",
            "Positive particle diffusion time scale [s]",
            "Reference electrolyte capacity [A.s]",
            "Measured cell capacity [A.s]",
            "Measured cell capacity from grouping [A.s]",
        ]:
            print(f"{key}: {grouped.get(key)}")

    if grouped_metadata is not None:
        print("Grouped metadata:", grouped_metadata)

    print("=" * 90)


def run_native_pybamm_spme_eis(params, frequencies, soc, model_options=None):
    if model_options is None:
        model_options = {"surface form": "differential", "contact resistance": "true"}

    parameter_values = make_parameter_values(params)
    model = pybamm.lithium_ion.SPMe(options=model_options)
    sim = pybamm.EISSimulation(model, parameter_values=parameter_values)
    result = sim.solve(frequencies, initial_soc=soc)

    try:
        Z = np.asarray(result["Impedance [Ohm]"], dtype=complex)
    except Exception:
        Z = np.asarray(result["Impedance"], dtype=complex)

    return apply_capacitive_nyquist_convention(Z)


def run_pybop_spme_eis(params, frequencies, model_options=None, var_pts=None, solver=None):
    if model_options is None:
        model_options = {"surface form": "differential", "contact resistance": "true"}
    if solver is None:
        solver = pybamm.CasadiSolver()

    parameter_values = make_parameter_values(params)
    model = pybop.lithium_ion.SPMe(
        parameter_set=parameter_values,
        options=model_options,
        eis=True,
        var_pts=var_pts,
        solver=solver,
    )
    simulation = model.simulateEIS(inputs=None, f_eval=frequencies)
    return apply_capacitive_nyquist_convention(simulation["Impedance"])


def run_grouped_spme_eis(grouped_params, frequencies, model_options=None, var_pts=None, solver=None):
    if model_options is None:
        model_options = {"surface form": "differential", "contact resistance": "true"}
    if solver is None:
        solver = pybamm.CasadiSolver()

    grouped_clean = clean_parameter_dict_for_pybamm(copy.deepcopy(grouped_params))
    model = pybop.lithium_ion.GroupedSPMe(
        parameter_set=grouped_clean,
        eis=True,
        options=model_options,
        var_pts=var_pts,
        solver=solver,
    )
    simulation = model.simulateEIS(inputs=None, f_eval=frequencies)
    return apply_capacitive_nyquist_convention(simulation["Impedance"])
