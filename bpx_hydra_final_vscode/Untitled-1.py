# %%
from pathlib import Path

import pandas as pd
import matplotlib.pyplot as plt


# -------------------------------------------------------------------------
# File path
# -------------------------------------------------------------------------
file_path = Path(
    r"C:\Users\mugi_jo\Documents\DLR_PROJECTS\data_cg50\N21700-BAK-CG50-DLR-anode-02-GITT-data-delithiation_selected_columns.csv"
)


# -------------------------------------------------------------------------
# Load CSV
# -------------------------------------------------------------------------
# sep=None lets pandas detect comma, semicolon, tab, etc.
# engine="python" is required for automatic separator detection.
df = pd.read_csv(file_path, sep=None, engine="python")

# Clean possible hidden spaces in column names
df.columns = df.columns.str.strip()

print("Available columns:")
print(df.columns.tolist())

# -------------------------------------------------------------------------
# Select columns
# -------------------------------------------------------------------------
time_col = "Test Time / h"
voltage_col = "Voltage / V"

if time_col not in df.columns:
    raise KeyError(f"Column not found: {time_col}")

if voltage_col not in df.columns:
    raise KeyError(f"Column not found: {voltage_col}")

# Convert to numeric in case values were read as strings
df[time_col] = pd.to_numeric(df[time_col], errors="coerce")
df[voltage_col] = pd.to_numeric(df[voltage_col], errors="coerce")

# Remove invalid rows
df_plot = df[[time_col, voltage_col]].dropna()

# -------------------------------------------------------------------------
# Plot
# -------------------------------------------------------------------------
plt.figure(figsize=(7, 4))

plt.plot(
    df_plot[time_col],
    df_plot[voltage_col],
    "-",
    linewidth=1.5,
)

plt.xlabel("Test Time / h")
plt.ylabel("Voltage / V")
plt.title("N21700-BAK-CG50-DLR anode-02 GITT delithiation")
plt.grid(True)
plt.tight_layout()
plt.show()

# %%
from pathlib import Path

import pandas as pd


# -------------------------------------------------------------------------
# File path
# -------------------------------------------------------------------------
file_path = Path(
    r"C:\Users\mugi_jo\Documents\DLR_PROJECTS\data_cg50\N21700-BAK-CG50-DLR-anode-02-GITT-data-delithiation_selected_columns.csv"
)

# New output file
output_path = file_path.with_name(
    file_path.stem + "_selected_columns.csv"
)


# -------------------------------------------------------------------------
# Load CSV
# -------------------------------------------------------------------------
df = pd.read_csv(file_path, sep=None, engine="python")

# Clean possible hidden spaces in column names
df.columns = df.columns.str.strip()

print("Available columns:")
print(df.columns.tolist())


# -------------------------------------------------------------------------
# Columns to extract
# -------------------------------------------------------------------------
columns_to_keep = [
    "Test Time / h",
    "Line",
    "Voltage / V",
    "Current / A",
    "ah-step",
    "Set Capacity / Ah",
    "Ambient Temperature / degC",
    "Cycle Count",
    "State",
]


# -------------------------------------------------------------------------
# Check that all required columns exist
# -------------------------------------------------------------------------
missing_columns = [col for col in columns_to_keep if col not in df.columns]

if missing_columns:
    raise KeyError(
        "The following required columns were not found in the CSV file:\n"
        + "\n".join(missing_columns)
    )


# -------------------------------------------------------------------------
# Extract selected columns
# -------------------------------------------------------------------------
df_selected = df[columns_to_keep].copy()


# -------------------------------------------------------------------------
# Optional: convert numeric columns to numeric values
# -------------------------------------------------------------------------
numeric_columns = [
    "Test Time / h",
    "Voltage / V",
    "Current / A",
    "ah-step",
    "Set Capacity / Ah",
    "Ambient Temperature / degC",
    "Cycle Count",
]

for col in numeric_columns:
    df_selected[col] = pd.to_numeric(df_selected[col], errors="coerce")


# -------------------------------------------------------------------------
# Save new file
# -------------------------------------------------------------------------
df_selected.to_csv(output_path, index=False)

print("\nSelected columns saved to:")
print(output_path)

print("\nPreview of saved data:")
print(df_selected.head())

# %%
# The problem was a version mismatch between your BPX JSON file, the bpx parser, and PyBaMM’s BPX converter.

# Your BPX file was created using an older BPX-style layout. In that layout, some state-related parameters were stored inside sections such as:

# Parameterisation → Cell
# Parameterisation → Electrolyte

# For example:

# Cell["Initial temperature [K]"]
# Cell["Ambient temperature [K]"]
# Electrolyte["Initial concentration [mol.m-3]"]

# But your installed bpx parser expects the newer BPX schema, where these quantities must be placed in a top-level State section:

# State → Initial conditions
# State → Thermal environment

# So the first error happened because the parser rejected the old locations of those parameters.

# After we moved them to the new State section, the BPX file passed validation, but then PyBaMM itself produced another error. That happened because PyBaMM’s BPX conversion code still expected the electrolyte concentration under the older PyBaMM parameter name:

# Initial concentration in electrolyte [mol.m-3]

# However, after the BPX schema migration, that value was now stored as:

# State → Initial conditions → Initial electrolyte concentration [mol.m-3]

# So PyBaMM could not find it when constructing the exchange-current-density functions.

# In simple terms:

# The BPX parser wanted the new BPX format,
# but PyBaMM’s converter still needed one value in the old PyBaMM-style location.

# We fixed it in two steps:

# 1. Migrated the old BPX JSON structure to the newer BPX schema.
# 2. Added a temporary PyBaMM converter patch so PyBaMM could read the electrolyte concentration from the new State section.

# After that, the BPX file loaded successfully, giving:

# BPX parameter set loaded successfully.
# Number of PyBaMM parameters: 113

# and PyBaMM correctly found important parameters such as cell capacity, voltage limits, electrode thicknesses, electrolyte concentration, and both electrode exchange-current-density functions.

# %%
from pathlib import Path
import json
import copy
import inspect

import pybamm
import matplotlib.pyplot as plt


# -------------------------------------------------------------------------
# Path to original BPX JSON file
# -------------------------------------------------------------------------
bpx_file = Path(
    r"C:\Users\mugi_jo\Downloads\hydr0_graphite-lnmo_schmitt-2026_validation.bpx_1.json"
)

target_soc = 0.5


# -------------------------------------------------------------------------
# Migrate old BPX layout to current BPX schema
# -------------------------------------------------------------------------
def migrate_legacy_bpx_to_current_schema(bpx_obj, target_soc=0.5):
    fixed = copy.deepcopy(bpx_obj)

    if "Parameterisation" not in fixed:
        raise KeyError("Could not find top-level 'Parameterisation' section.")

    parameterisation = fixed["Parameterisation"]
    cell = parameterisation.setdefault("Cell", {})
    electrolyte = parameterisation.setdefault("Electrolyte", {})

    # Read old values from old locations
    initial_temperature = cell.pop(
        "Initial temperature [K]",
        cell.get("Reference temperature [K]", 298.15),
    )

    ambient_temperature = cell.pop(
        "Ambient temperature [K]",
        initial_temperature,
    )

    initial_electrolyte_concentration = electrolyte.pop(
        "Initial concentration [mol.m-3]",
        1000.0,
    )

    # New BPX top-level State section
    fixed["State"] = {
        "Initial conditions": {
            "Initial state-of-charge": float(target_soc),
            "Initial temperature [K]": float(initial_temperature),
            "Initial electrolyte concentration [mol.m-3]": float(
                initial_electrolyte_concentration
            ),
            "Initial hysteresis state: Positive electrode": 0.0,
            "Initial hysteresis state: Negative electrode": 0.0,
        },
        "Thermal environment": {
            "Ambient temperature [K]": float(ambient_temperature),
            "Heat transfer coefficient [W.m-2.K-1]": 10.0,
        },
    }

    return fixed


# -------------------------------------------------------------------------
# Temporary PyBaMM converter patch
# -------------------------------------------------------------------------
def patch_pybamm_bpx_converter_for_state_concentration():
    """
    Patch PyBaMM's bpx_to_param_dict in the current Python session.

    Problem:
        Current BPX puts initial electrolyte concentration in:
            bpx.state.initial_conditions.initial_electrolyte_concentration

        Some PyBaMM versions still expect:
            pybamm_dict["Initial concentration in electrolyte [mol.m-3]"]

    This patch inserts the missing PyBaMM key from the BPX State section.
    """
    import pybamm.parameters.bpx as pybamm_bpx
    import pybamm.parameters.parameter_values as parameter_values_module

    source = inspect.getsource(pybamm_bpx.bpx_to_param_dict)

    old_line = '    c_e = pybamm_dict["Initial concentration in electrolyte [mol.m-3]"]'

    new_block = '''
    if "Initial concentration in electrolyte [mol.m-3]" not in pybamm_dict:
        try:
            pybamm_dict["Initial concentration in electrolyte [mol.m-3]"] = (
                bpx.state.initial_conditions.initial_electrolyte_concentration
            )
        except Exception as err:
            raise KeyError(
                "Could not find initial electrolyte concentration. "
                "Expected it either as PyBaMM parameter "
                "'Initial concentration in electrolyte [mol.m-3]' or in BPX "
                "State -> Initial conditions -> "
                "'Initial electrolyte concentration [mol.m-3]'."
            ) from err

    c_e = pybamm_dict["Initial concentration in electrolyte [mol.m-3]"]
'''

    if old_line not in source:
        print("Patch not applied: expected source line was not found.")
        print("Your PyBaMM version may already differ from the expected converter.")
        return

    patched_source = source.replace(old_line, new_block)

    namespace = dict(pybamm_bpx.__dict__)
    exec(patched_source, namespace)

    patched_function = namespace["bpx_to_param_dict"]

    # Patch both places:
    # 1. pybamm.parameters.bpx.bpx_to_param_dict
    # 2. the name imported inside pybamm.parameters.parameter_values
    pybamm_bpx.bpx_to_param_dict = patched_function
    parameter_values_module.bpx_to_param_dict = patched_function

    print("Applied temporary PyBaMM BPX converter patch.")


# -------------------------------------------------------------------------
# Load, migrate, patch, and convert to PyBaMM ParameterValues
# -------------------------------------------------------------------------
if not bpx_file.exists():
    raise FileNotFoundError(f"BPX file not found:\n{bpx_file}")

with open(bpx_file, "r", encoding="utf-8") as f:
    bpx_obj = json.load(f)

bpx_fixed = migrate_legacy_bpx_to_current_schema(
    bpx_obj,
    target_soc=target_soc,
)

patched_bpx_file = bpx_file.with_name(
    bpx_file.stem + "_patched_current_schema.json"
)

with open(patched_bpx_file, "w", encoding="utf-8") as f:
    json.dump(bpx_fixed, f, indent=2)

print("Patched BPX file saved to:")
print(patched_bpx_file)

# Apply temporary PyBaMM converter patch
patch_pybamm_bpx_converter_for_state_concentration()

# Now load into PyBaMM
parameter_values = pybamm.ParameterValues.create_from_bpx_obj(
    bpx_fixed,
    target_soc=target_soc,
)

# Add/overwrite the state quantities explicitly in the final PyBaMM parameter set
state_ic = bpx_fixed["State"]["Initial conditions"]
thermal_env = bpx_fixed["State"]["Thermal environment"]

parameter_values.update(
    {
        "Initial concentration in electrolyte [mol.m-3]": state_ic[
            "Initial electrolyte concentration [mol.m-3]"
        ],
        "Initial temperature [K]": state_ic["Initial temperature [K]"],
        "Ambient temperature [K]": thermal_env["Ambient temperature [K]"],
        "Total heat transfer coefficient [W.m-2.K-1]": thermal_env[
            "Heat transfer coefficient [W.m-2.K-1]"
        ],
    },
    check_already_exists=False,
)

print("\nBPX parameter set loaded successfully.")
print("Number of PyBaMM parameters:", len(parameter_values.keys()))


# -------------------------------------------------------------------------
# Check important parameters
# -------------------------------------------------------------------------
keys_to_check = [
    "Nominal cell capacity [A.h]",
    "Lower voltage cut-off [V]",
    "Upper voltage cut-off [V]",
    "Initial concentration in electrolyte [mol.m-3]",
    "Initial temperature [K]",
    "Ambient temperature [K]",
    "Reference temperature [K]",
    "Negative electrode thickness [m]",
    "Separator thickness [m]",
    "Positive electrode thickness [m]",
    "Maximum concentration in negative electrode [mol.m-3]",
    "Maximum concentration in positive electrode [mol.m-3]",
    "Negative electrode exchange-current density [A.m-2]",
    "Positive electrode exchange-current density [A.m-2]",
]

print("\nImportant PyBaMM parameters:")
for key in keys_to_check:
    try:
        print(f"✅ {key}: {parameter_values[key]}")
    except KeyError:
        print(f"❌ Missing: {key}")


# -------------------------------------------------------------------------
# Build and run DFN model
# -------------------------------------------------------------------------
model = pybamm.lithium_ion.DFN()

experiment = pybamm.Experiment(
    [
        "Discharge at C/10 until 3.5 V",
    ]
)

sim = pybamm.Simulation(
    model,
    parameter_values=parameter_values,
    experiment=experiment,
)

solution = sim.solve()


# -------------------------------------------------------------------------
# Plot voltage
# -------------------------------------------------------------------------
t_h = solution["Time [h]"].entries
V = solution["Voltage [V]"].entries

plt.figure(figsize=(7, 4))
plt.plot(t_h, V, "-", linewidth=2)
plt.xlabel("Time [h]")
plt.ylabel("Voltage [V]")
plt.title("HYDRA graphite/LNMO DFN simulation from patched BPX")
plt.grid(True)
plt.tight_layout()
plt.show()



# %%
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import pybamm
from pathlib import Path


# =============================================================================
# SETTINGS
# =============================================================================

output_dir = Path("bpx_dfn_eis_simulation")
output_dir.mkdir(exist_ok=True)

frequencies = np.logspace(-4, 6, 100)

model_options = {
    "surface form": "differential",
}

model = pybamm.lithium_ion.SPMe(options=model_options)



# =============================================================================
# PATCH EIS-REQUIRED PARAMETERS AFTER BPX -> PYBAMM CONVERSION
# =============================================================================

eis_required_parameters = {
    "Negative electrode double-layer capacity [F.m-2]": 0.02,
    "Positive electrode double-layer capacity [F.m-2]": 0.092,

    "Negative electrode OCP entropic change [V.K-1]": 0.0,
    "Positive electrode OCP entropic change [V.K-1]": 0.0,

    "Negative electrode Bruggeman coefficient (electrolyte)": 3.5,
    "Positive electrode Bruggeman coefficient (electrolyte)": 3.5,
    "Separator Bruggeman coefficient (electrolyte)": 1.5,

    "Negative electrode Bruggeman coefficient (electrode)": 1.5,
    "Positive electrode Bruggeman coefficient (electrode)": 1.5,

    "Thermodynamic factor": 1.0,
}

missing_updates = {}

for key, value in eis_required_parameters.items():
    if key not in parameter_values:
        missing_updates[key] = value

if missing_updates:
    print("\n" + "=" * 100)
    print("ADDING PARAMETERS REQUIRED FOR EIS")
    print("=" * 100)

    for key, value in missing_updates.items():
        print(f"{key}: {value}")

    parameter_values.update(
        missing_updates,
        check_already_exists=False,
    )
else:
    print("No EIS-required parameters were missing.")
# =============================================================================
# OPTIONAL: CHECK IMPORTANT PARAMETERS
# =============================================================================

important_parameters = [
    "Negative electrode thickness [m]",
    "Separator thickness [m]",
    "Positive electrode thickness [m]",
    "Electrode height [m]",
    "Electrode width [m]",
    "Nominal cell capacity [A.h]",
    "Current function [A]",
    "Initial concentration in electrolyte [mol.m-3]",
    "Positive electrode conductivity [S.m-1]",
    "Negative electrode conductivity [S.m-1]",
    "Positive particle radius [m]",
    "Negative particle radius [m]",
    "Positive particle diffusivity [m2.s-1]",
    "Negative particle diffusivity [m2.s-1]",
    "Positive electrode exchange-current density [A.m-2]",
    "Negative electrode exchange-current density [A.m-2]",
]

print("\n" + "=" * 100)
print("IMPORTANT PARAMETERS USED FOR EIS")
print("=" * 100)

for name in important_parameters:
    if name in parameter_values:
        print(f"{name}: {parameter_values[name]}")
    else:
        print(f"{name}: NOT FOUND")


# =============================================================================
# EIS SIMULATION USING BPX-CONVERTED PARAMETER VALUES
# =============================================================================

print("\nFrequencies [Hz]:")
print(frequencies)

eis_sim = pybamm.EISSimulation(
    model,
    parameter_values=parameter_values,
)

result = eis_sim.solve(frequencies)


# =============================================================================
# EXTRACT IMPEDANCE ROBUSTLY
# =============================================================================

def extract_impedance(result):
    """
    Robustly extract frequency and impedance from PyBaMM EIS result.
    """
    try:
        f = np.asarray(result["Frequency [Hz]"], dtype=float)
    except Exception:
        f = frequencies

    for key in ["Impedance [Ohm]", "Impedance"]:
        try:
            Z = np.asarray(result[key], dtype=complex)
            return f, Z
        except Exception:
            pass

    try:
        Z_re = np.asarray(result["Z_re [Ohm]"], dtype=float)
        Z_im = np.asarray(result["Z_im [Ohm]"], dtype=float)
        Z = Z_re + 1j * Z_im
        return f, Z
    except Exception as err:
        raise KeyError("Could not extract impedance from EIS result.") from err


f, Z = extract_impedance(result)


# =============================================================================
# SAVE RESULTS
# =============================================================================

df_eis = pd.DataFrame(
    {
        "Frequency [Hz]": f,
        "Z_real [Ohm]": np.real(Z),
        "Z_imag [Ohm]": np.imag(Z),
        "-Z_imag [Ohm]": -np.imag(Z),
        "Z_abs [Ohm]": np.abs(Z),
        "Phase [deg]": np.angle(Z, deg=True),
    }
)

csv_path = output_dir / "DFN_BPX_EIS_results.csv"
df_eis.to_csv(csv_path, index=False)

print("\nSaved EIS results to:")
print(csv_path)


# =============================================================================
# NYQUIST PLOT
# =============================================================================

plt.figure(figsize=(6, 5))
plt.plot(
    np.real(Z),
    -np.imag(Z),
    "-o",
    markersize=4,
    linewidth=1.5,
    label="DFN EIS using BPX parameters",
)

plt.xlabel(r"$Z_\mathrm{real}$ [$\Omega$]")
plt.ylabel(r"$-Z_\mathrm{imag}$ [$\Omega$]")
plt.title("DFN impedance simulation using BPX parameters")
plt.grid(True)
plt.axis("equal")
plt.legend()
plt.tight_layout()

plot_path = output_dir / "DFN_BPX_EIS_nyquist.png"
plt.savefig(plot_path, dpi=300)
plt.show()

print("Saved Nyquist plot to:")
print(plot_path)


# =============================================================================
# OPTIONAL: PYBAMM BUILT-IN NYQUIST PLOT
# =============================================================================

try:
    eis_sim.nyquist_plot()
except Exception as err:
    print("\nPyBaMM built-in nyquist_plot() failed, but manual plot was saved.")
    print(f"Reason: {err}")

# %%
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import pybamm
from pathlib import Path


# =============================================================================
# USER SETTINGS
# =============================================================================

output_dir = Path("bpx_dfn_eis_simulation")
output_dir.mkdir(exist_ok=True)

# Frequency range from your example
frequencies = np.logspace(-4, 5, 50)

# PyBaMM model options
model_options = {
    "surface form": "differential",
}

# If True, missing parameters needed by EIS are patched automatically
PATCH_MISSING_PARAMETERS = True


# =============================================================================
# PATCH MISSING PARAMETERS REQUIRED FOR DFN EIS
# =============================================================================
# Your error showed that this parameter is missing:
# "Negative electrode double-layer capacity [F.m-2]"
#
# This is required because you use:
# options={"surface form": "differential"}

if PATCH_MISSING_PARAMETERS:
    default_missing_parameters = {
        # Required for differential surface formulation / impedance
        "Negative electrode double-layer capacity [F.m-2]": 0.02,
        "Positive electrode double-layer capacity [F.m-2]": 0.092,

        # Often needed if not present in BPX conversion
        "Negative electrode OCP entropic change [V.K-1]": 0.0,
        "Positive electrode OCP entropic change [V.K-1]": 0.0,

        # Sometimes missing depending on BPX file
        "Negative electrode Bruggeman coefficient (electrolyte)": 3.5,
        "Positive electrode Bruggeman coefficient (electrolyte)": 3.5,
        "Separator Bruggeman coefficient (electrolyte)": 1.5,

        "Negative electrode Bruggeman coefficient (electrode)": 1.5,
        "Positive electrode Bruggeman coefficient (electrode)": 1.5,
    }

    patch_dict = {}

    for key, value in default_missing_parameters.items():
        if key not in parameter_values:
            patch_dict[key] = value

    if patch_dict:
        print("\n" + "=" * 100)
        print("PATCHING MISSING PARAMETERS")
        print("=" * 100)

        for key, value in patch_dict.items():
            print(f"{key}: {value}")

        parameter_values.update(
            patch_dict,
            check_already_exists=False,
        )
    else:
        print("\nNo missing default parameters needed to be patched.")


# =============================================================================
# PRINT IMPORTANT PARAMETERS USED FOR EIS
# =============================================================================

important_parameters = [
    "Negative electrode thickness [m]",
    "Separator thickness [m]",
    "Positive electrode thickness [m]",
    "Electrode height [m]",
    "Electrode width [m]",
    "Nominal cell capacity [A.h]",
    "Current function [A]",
    "Initial concentration in electrolyte [mol.m-3]",
    "Negative electrode porosity",
    "Separator porosity",
    "Positive electrode porosity",
    "Negative electrode active material volume fraction",
    "Positive electrode active material volume fraction",
    "Negative electrode conductivity [S.m-1]",
    "Positive electrode conductivity [S.m-1]",
    "Electrolyte conductivity [S.m-1]",
    "Negative particle radius [m]",
    "Positive particle radius [m]",
    "Negative particle diffusivity [m2.s-1]",
    "Positive particle diffusivity [m2.s-1]",
    "Negative electrode exchange-current density [A.m-2]",
    "Positive electrode exchange-current density [A.m-2]",
    "Negative electrode double-layer capacity [F.m-2]",
    "Positive electrode double-layer capacity [F.m-2]",
]

print("\n" + "=" * 100)
print("IMPORTANT PARAMETERS USED FOR DFN EIS")
print("=" * 100)

for name in important_parameters:
    if name in parameter_values:
        print(f"{name}: {parameter_values[name]}")
    else:
        print(f"{name}: NOT FOUND")


# =============================================================================
# BUILD DFN MODEL
# =============================================================================

model = pybamm.lithium_ion.SPMe(
    options=model_options
)


# =============================================================================
# RUN EIS SIMULATION USING BPX-CONVERTED PARAMETERS
# =============================================================================

print("\n" + "=" * 100)
print("RUNNING DFN EIS SIMULATION")
print("=" * 100)

print("\nFrequencies [Hz]:")
print(frequencies)

eis_sim = pybamm.EISSimulation(
    model,
    parameter_values=parameter_values,
)

result = eis_sim.solve(frequencies)


# =============================================================================
# ROBUST IMPEDANCE EXTRACTION
# =============================================================================

def extract_impedance(result, fallback_frequencies):
    """
    Extract frequency and impedance from PyBaMM EIS result.
    Works across different PyBaMM versions.
    """

    try:
        f = np.asarray(result["Frequency [Hz]"], dtype=float)
    except Exception:
        f = np.asarray(fallback_frequencies, dtype=float)

    for key in ["Impedance [Ohm]", "Impedance"]:
        try:
            Z = np.asarray(result[key], dtype=complex)
            return f, Z
        except Exception:
            pass

    try:
        Z_re = np.asarray(result["Z_re [Ohm]"], dtype=float)
        Z_im = np.asarray(result["Z_im [Ohm]"], dtype=float)
        Z = Z_re + 1j * Z_im
        return f, Z
    except Exception as err:
        raise KeyError(
            "Could not extract impedance from PyBaMM EIS result."
        ) from err


f, Z = extract_impedance(result, frequencies)


# =============================================================================
# OPTIONAL SIGN CORRECTION FOR CAPACITIVE NYQUIST CONVENTION
# =============================================================================
# In the usual Nyquist plot, capacitive arcs appear with -Zimag > 0.
# If the arc appears below the x-axis, this flips the complex conjugate.

if np.nanmedian(-np.imag(Z)) < 0:
    print("\nApplying capacitive convention correction: Z -> conjugate(Z)")
    Z = np.conjugate(Z)


# =============================================================================
# SAVE EIS RESULTS
# =============================================================================

df_eis = pd.DataFrame(
    {
        "Frequency [Hz]": f,
        "Z_real [Ohm]": np.real(Z),
        "Z_imag [Ohm]": np.imag(Z),
        "-Z_imag [Ohm]": -np.imag(Z),
        "Z_abs [Ohm]": np.abs(Z),
        "Phase [deg]": np.angle(Z, deg=True),
    }
)

csv_path = output_dir / "DFN_BPX_EIS_results.csv"
df_eis.to_csv(csv_path, index=False)

print("\nSaved EIS results to:")
print(csv_path)


# =============================================================================
# SAVE PARAMETER SUMMARY USED IN THIS RUN
# =============================================================================

parameter_summary_rows = []

for key in sorted(parameter_values.keys()):
    value = parameter_values[key]

    try:
        value_text = repr(value)
    except Exception:
        value_text = str(type(value))

    if len(value_text) > 500:
        value_text = value_text[:500] + " ... [truncated]"

    parameter_summary_rows.append(
        {
            "PyBaMM parameter": key,
            "Type": type(value).__name__,
            "Value": value_text,
        }
    )

df_parameters = pd.DataFrame(parameter_summary_rows)

parameter_csv_path = output_dir / "DFN_BPX_parameters_used.csv"
df_parameters.to_csv(parameter_csv_path, index=False)

print("\nSaved parameter summary to:")
print(parameter_csv_path)


# =============================================================================
# MANUAL NYQUIST PLOT
# =============================================================================

plt.figure(figsize=(6, 5))

plt.plot(
    np.real(Z),
    -np.imag(Z),
    "-o",
    markersize=4,
    linewidth=1.5,
    label="DFN EIS using BPX parameters",
)

plt.xlabel(r"$Z_\mathrm{real}$ [$\Omega$]")
plt.ylabel(r"$-Z_\mathrm{imag}$ [$\Omega$]")
plt.title("DFN impedance simulation using BPX parameters")
plt.grid(True)
plt.axis("equal")
plt.legend()
plt.tight_layout()

plot_path = output_dir / "DFN_BPX_EIS_nyquist.png"
plt.savefig(plot_path, dpi=300)
plt.show()

print("\nSaved Nyquist plot to:")
print(plot_path)


# =============================================================================
# BODE PLOTS
# =============================================================================

plt.figure(figsize=(7, 4))

plt.loglog(
    f,
    np.abs(Z),
    "-o",
    markersize=4,
    linewidth=1.5,
)

plt.xlabel("Frequency [Hz]")
plt.ylabel(r"$|Z|$ [$\Omega$]")
plt.title("DFN EIS magnitude using BPX parameters")
plt.grid(True, which="both")
plt.tight_layout()

bode_mag_path = output_dir / "DFN_BPX_EIS_bode_magnitude.png"
plt.savefig(bode_mag_path, dpi=300)
plt.show()

print("Saved Bode magnitude plot to:")
print(bode_mag_path)


plt.figure(figsize=(7, 4))

plt.semilogx(
    f,
    np.angle(Z, deg=True),
    "-o",
    markersize=4,
    linewidth=1.5,
)

plt.xlabel("Frequency [Hz]")
plt.ylabel("Phase [deg]")
plt.title("DFN EIS phase using BPX parameters")
plt.grid(True, which="both")
plt.tight_layout()

bode_phase_path = output_dir / "DFN_BPX_EIS_bode_phase.png"
plt.savefig(bode_phase_path, dpi=300)
plt.show()

print("Saved Bode phase plot to:")
print(bode_phase_path)


# =============================================================================
# OPTIONAL PYBAMM BUILT-IN NYQUIST PLOT
# =============================================================================

try:
    eis_sim.nyquist_plot()
except Exception as err:
    print("\nPyBaMM built-in nyquist_plot() failed, but manual plots were saved.")
    print(f"Reason: {err}")


# =============================================================================
# FINAL SUMMARY
# =============================================================================

print("\n" + "=" * 100)
print("DFN BPX EIS SIMULATION COMPLETE")
print("=" * 100)

print(f"Number of frequencies: {len(f)}")
print(f"Frequency range: {np.min(f):.3e} to {np.max(f):.3e} Hz")
print(f"Minimum Z_real: {np.min(np.real(Z)):.6e} Ohm")
print(f"Maximum Z_real: {np.max(np.real(Z)):.6e} Ohm")
print(f"Maximum -Z_imag: {np.max(-np.imag(Z)):.6e} Ohm")
print(f"Output directory: {output_dir.resolve()}")

# %%
import json
import math
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pybamm
import pybop
from scipy.io import savemat

# =============================================================================
# USER SETTINGS
# =============================================================================
BPX_FILE = Path(
    r"C:\Users\mugi_jo\Downloads\hydr0_graphite-lnmo_schmitt-2026_validation.bpx_1_patched_for_current_bpx.json"
)
OUT = Path("bpx_grouped_spme_precise")
OUT.mkdir(exist_ok=True)

SOC = 0.5
PARAMETER_NAME = "Negative electrode relative porosity"
FACTOR = 2
NPARAMS = 11
FREQ = np.logspace(np.log10(2e-4), np.log10(1e5), 100)
VAR_PTS = {"x_n": 20, "x_s": 10, "x_p": 20, "r_n": 20, "r_p": 20}
MODEL_OPTIONS = {"surface form": "differential", "contact resistance": "true"}

# Supplemental EIS constants not present in the BPX schema
C_DL_N = 0.2       # F m-2
C_DL_P = 0.92      # F m-2
CONTACT_R = 0.0     # Ohm
I_DC = 0.0          # A, equilibrium EIS

F = 96485.33212
M_P = 3.42e-6       # PyBOP grouped-SPMe convention
M_N = 6.48e-7       # PyBOP grouped-SPMe convention


# =============================================================================
# SMALL HELPERS
# =============================================================================
def fnum(x):
    return float(x)


def interp_table(tab, x):
    xs = np.asarray(tab["x"], dtype=float)
    ys = np.asarray(tab["y"], dtype=float)
    order = np.argsort(xs)
    return float(np.interp(float(x), xs[order], ys[order]))


def bruggeman(eps, transport_efficiency):
    return float(math.log(float(transport_efficiency)) / math.log(float(eps)))


def state_initial_conditions(bpx):
    state = bpx.get("State", {})
    return state.get("Initial conditions") or state.get("InitialConditions") or {}


def ocp_fun(tab, name):
    xs = np.asarray(tab["x"], dtype=float)
    ys = np.asarray(tab["y"], dtype=float)
    order = np.argsort(xs)
    xs, ys = xs[order], ys[order]

    def ocp(sto):
        if isinstance(sto, pybamm.Symbol):
            return pybamm.Interpolant(xs, ys, sto, name=name, extrapolate=True)
        return np.interp(sto, xs, ys)

    return ocp


# =============================================================================
# DIRECT BPX JSON -> GROUPED-SPMe PARAMETERS
# =============================================================================
def grouped_from_bpx(path, soc=0.5):
    with open(path, "r", encoding="utf-8") as f:
        bpx = json.load(f)

    p = bpx["Parameterisation"]
    cell, elyte = p["Cell"], p["Electrolyte"]
    neg, pos, sep = p["Negative electrode"], p["Positive electrode"], p["Separator"]
    user = p.get("User-defined", {})
    ic = state_initial_conditions(bpx)

    # Geometry
    A = fnum(cell["Electrode area [m2]"]) * fnum(
        cell.get("Number of electrode pairs connected in parallel to make a cell", 1)
    )
    Ln, Ls, Lp = fnum(neg["Thickness [m]"]), fnum(sep["Thickness [m]"]), fnum(pos["Thickness [m]"])
    Ltot = Ln + Ls + Lp

    # Main scalar BPX values
    eps_n, eps_s, eps_p = fnum(neg["Porosity"]), fnum(sep["Porosity"]), fnum(pos["Porosity"])
    alpha_n = fnum(user.get("Negative electrode active material volume fraction", 1 - eps_n))
    alpha_p = fnum(user.get("Positive electrode active material volume fraction", 1 - eps_p))
    cmax_n, cmax_p = fnum(neg["Maximum concentration [mol.m-3]"]), fnum(pos["Maximum concentration [mol.m-3]"])
    Rn, Rp = fnum(neg["Particle radius [m]"]), fnum(pos["Particle radius [m]"])
    Dn, Dp = fnum(neg["Diffusivity [m2.s-1]"]), fnum(pos["Diffusivity [m2.s-1]"])
    sig_n, sig_p = fnum(neg["Conductivity [S.m-1]"]), fnum(pos["Conductivity [S.m-1]"])

    ce0 = fnum(ic.get("Initial electrolyte concentration [mol.m-3]", 1000.0))
    T0 = fnum(ic.get("Initial temperature [K]", cell.get("Reference temperature [K]", 298.15)))
    De = interp_table(elyte["Diffusivity [m2.s-1]"], ce0)
    ke = interp_table(elyte["Conductivity [S.m-1]"], ce0)
    tplus = fnum(elyte["Cation transference number"])

    bn = bruggeman(eps_n, neg["Transport efficiency"])
    bp = bruggeman(eps_p, pos["Transport efficiency"])
    bs = bruggeman(eps_s, sep["Transport efficiency"])

    x0 = fnum(neg["Minimum stoichiometry"])
    x100 = fnum(neg["Maximum stoichiometry"])
    y100 = fnum(pos["Minimum stoichiometry"])
    y0 = fnum(pos["Maximum stoichiometry"])

    # Grouped-SPMe quantities
    Qp = F * alpha_p * cmax_p * Lp * A
    Qn = F * alpha_n * cmax_n * Ln * A
    Qmeas = fnum(cell["Nominal cell capacity [A.h]"]) * 3600
    Qe = F * eps_s * ce0 * Ltot * A

    Re_area = (Lp / (3 * eps_p**bp) + Ls / (eps_s**bs) + Ln / (3 * eps_n**bn)) / ke
    Rs_area = (Lp / sig_p + Ln / sig_n) / 3
    Rseries = (Re_area + Rs_area) / A + CONTACT_R

    return {
        "Nominal cell capacity [A.h]": fnum(cell["Nominal cell capacity [A.h]"]),
        "Current function [A]": I_DC,
        "Initial temperature [K]": T0,
        "Initial SoC": soc,
        "Lower voltage cut-off [V]": fnum(cell["Lower voltage cut-off [V]"]),
        "Upper voltage cut-off [V]": fnum(cell["Upper voltage cut-off [V]"]),
        "Minimum negative stoichiometry": x0,
        "Maximum negative stoichiometry": x100,
        "Minimum positive stoichiometry": y100,
        "Maximum positive stoichiometry": y0,
        "Negative electrode OCP [V]": ocp_fun(neg["OCP [V]"], "U_n"),
        "Positive electrode OCP [V]": ocp_fun(pos["OCP [V]"], "U_p"),
        "Measured cell capacity [A.s]": Qmeas,
        "Reference electrolyte capacity [A.s]": Qe,
        "Negative electrode relative porosity": eps_n / eps_s,
        "Positive electrode relative porosity": eps_p / eps_s,
        "Negative particle diffusion time scale [s]": Rn**2 / Dn,
        "Positive particle diffusion time scale [s]": Rp**2 / Dp,
        "Negative electrode electrolyte diffusion time scale [s]": eps_s * Ltot**2 / (eps_n**bn * De),
        "Positive electrode electrolyte diffusion time scale [s]": eps_s * Ltot**2 / (eps_p**bp * De),
        "Separator electrolyte diffusion time scale [s]": eps_s * Ltot**2 / (eps_s**bs * De),
        "Negative electrode charge transfer time scale [s]": F * Rn / (M_N * np.sqrt(ce0)),
        "Positive electrode charge transfer time scale [s]": F * Rp / (M_P * np.sqrt(ce0)),
        "Negative electrode capacitance [F]": 3 * alpha_n * C_DL_N * Ln * A / Rn,
        "Positive electrode capacitance [F]": 3 * alpha_p * C_DL_P * Lp * A / Rp,
        "Cation transference number": tplus,
        "Negative electrode relative thickness": Ln / Ltot,
        "Positive electrode relative thickness": Lp / Ltot,
        "Positive theoretical electrode capacity [As]": Qp,
        "Negative theoretical electrode capacity [As]": Qn,
        "Series resistance [Ohm]": Rseries,
    }


# =============================================================================
# RUN SENSITIVITY
# =============================================================================
grouped = grouped_from_bpx(BPX_FILE, SOC)
base = float(grouped[PARAMETER_NAME])
values = np.logspace(np.log10(base / FACTOR), np.log10(base * FACTOR), NPARAMS)
Zall = np.zeros((len(FREQ), NPARAMS), dtype=complex)

for j, value in enumerate(values):
    print(f"{j + 1}/{NPARAMS}: {PARAMETER_NAME} = {value:.4e}")
    pars = dict(grouped)
    pars[PARAMETER_NAME] = float(value)

    model = pybop.lithium_ion.GroupedSPMe(
        parameter_set=pars,
        eis=True,
        options=MODEL_OPTIONS,
        var_pts=VAR_PTS,
    )
    model.build(initial_state={"Initial SoC": SOC})
    Z = np.asarray(model.simulateEIS(inputs=None, f_eval=FREQ)["Impedance"], dtype=complex)
    if np.nanmedian(-np.imag(Z)) < 0:
        Z = np.conjugate(Z)
    Zall[:, j] = Z


# =============================================================================
# SAVE AND PLOT
# =============================================================================
rows = []
for j, value in enumerate(values):
    for f, Z in zip(FREQ, Zall[:, j]):
        rows.append({
            "Parameter": PARAMETER_NAME,
            "Parameter value": value,
            "Frequency [Hz]": f,
            "Z_real [Ohm]": Z.real,
            "Z_imag [Ohm]": Z.imag,
            "-Z_imag [Ohm]": -Z.imag,
            "Z_abs [Ohm]": abs(Z),
            "Phase [deg]": np.angle(Z, deg=True),
        })

pd.DataFrame(rows).to_csv(OUT / "grouped_spme_bpx_sensitivity.csv", index=False)
savemat(OUT / "grouped_spme_bpx_sensitivity.mat", {"Z": Zall, "f": FREQ, "params": values, "name": PARAMETER_NAME})

plt.figure(figsize=(6, 6))
for j, value in enumerate(values):
    plt.plot(Zall[:, j].real, -Zall[:, j].imag, label=f"{value:.2e}")
plt.xlabel(r"$Z_r(\omega)$ [$\Omega$]")
plt.ylabel(r"$-Z_j(\omega)$ [$\Omega$]")
plt.title(f"GroupedSPMe sensitivity: {PARAMETER_NAME}")
plt.grid(True)
plt.axis("equal")
plt.legend(fontsize=7)
plt.tight_layout()
plt.savefig(OUT / "grouped_spme_bpx_sensitivity.png", dpi=300)
plt.show()

print("Done. Results saved in:", OUT.resolve())


# %%
import pybamm
import pybop


print("PyBop:", pybop.__version__)
print("PyBaMM:", pybamm.__version__)

# %%
import sys
!{sys.executable} -m pip install cloudpickle

# %%
import json
import math
import shutil
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pybamm
import pybop
from scipy.io import savemat

# =============================================================================
# USER SETTINGS
# =============================================================================
BPX_FILE = Path(
    r"C:\Users\mugi_jo\Downloads\hydr0_graphite-lnmo_schmitt-2026_validation.bpx_1_patched_for_current_bpx.json"
)
OUT = Path("bpx_grouped_spme_flexible")
PARAM_OUT = OUT / "flexible_parameter_set"
OUT.mkdir(exist_ok=True)
PARAM_OUT.mkdir(exist_ok=True)

SOC = 0.5
PARAMETER_NAME = "Negative electrode relative porosity"
FACTOR = 2
NPARAMS = 11
FREQ = np.logspace(np.log10(2e-4), np.log10(1e3), 60)
VAR_PTS = {"x_n": 20, "x_s": 10, "x_p": 20, "r_n": 20, "r_p": 20}
MODEL_OPTIONS = {"surface form": "differential", "contact resistance": "true"}

# Supplemental constants not contained in the BPX schema
C_DL_N = 0.02       # F m-2
C_DL_P = 0.092      # F m-2
CONTACT_R = 0.0     # Ohm
I_DC = 0.0          # A, equilibrium EIS

FARADAY = 96485.33212
M_P = 3.42e-6       # PyBOP grouped-SPMe convention
M_N = 6.48e-7       # PyBOP grouped-SPMe convention


# =============================================================================
# HELPERS
# =============================================================================
def fnum(x):
    return float(x)


def json_safe(x):
    if isinstance(x, (np.integer, int)):
        return int(x)
    if isinstance(x, (np.floating, float)):
        x = float(x)
        return x if math.isfinite(x) else None
    if isinstance(x, np.ndarray):
        return [json_safe(v) for v in x.tolist()]
    if isinstance(x, (list, tuple)):
        return [json_safe(v) for v in x]
    if isinstance(x, dict):
        return {str(k): json_safe(v) for k, v in x.items()}
    return x


def interp_table(tab, x):
    xs = np.asarray(tab["x"], dtype=float)
    ys = np.asarray(tab["y"], dtype=float)
    order = np.argsort(xs)
    return float(np.interp(float(x), xs[order], ys[order]))


def bruggeman(eps, transport_efficiency):
    return float(math.log(float(transport_efficiency)) / math.log(float(eps)))


def state_initial_conditions(bpx):
    state = bpx.get("State", {})
    return state.get("Initial conditions") or state.get("InitialConditions") or {}


def ocp_fun(tab, name):
    xs = np.asarray(tab["x"], dtype=float)
    ys = np.asarray(tab["y"], dtype=float)
    order = np.argsort(xs)
    xs, ys = xs[order], ys[order]

    def ocp(sto):
        if hasattr(pybamm, "Symbol") and isinstance(sto, pybamm.Symbol):
            return pybamm.Interpolant(xs, ys, sto, name=name, extrapolate=True)
        return np.interp(sto, xs, ys)

    return ocp


# =============================================================================
# DIRECT BPX JSON -> GROUPED-SPMe PARAMETERS
# =============================================================================
def grouped_from_bpx(path, soc=0.5):
    with open(path, "r", encoding="utf-8") as f:
        bpx = json.load(f)

    p = bpx["Parameterisation"]
    cell, elyte = p["Cell"], p["Electrolyte"]
    neg, pos, sep = p["Negative electrode"], p["Positive electrode"], p["Separator"]
    user = p.get("User-defined", {})
    ic = state_initial_conditions(bpx)

    # Geometry
    n_parallel = fnum(cell.get("Number of electrode pairs connected in parallel to make a cell", 1))
    A = fnum(cell["Electrode area [m2]"]) * n_parallel
    Ln, Ls, Lp = fnum(neg["Thickness [m]"]), fnum(sep["Thickness [m]"]), fnum(pos["Thickness [m]"])
    Ltot = Ln + Ls + Lp

    # Phase fractions and transport
    eps_n, eps_s, eps_p = fnum(neg["Porosity"]), fnum(sep["Porosity"]), fnum(pos["Porosity"])
    alpha_n = fnum(user.get("Negative electrode active material volume fraction", 1 - eps_n))
    alpha_p = fnum(user.get("Positive electrode active material volume fraction", 1 - eps_p))
    bn = bruggeman(eps_n, neg["Transport efficiency"])
    bs = bruggeman(eps_s, sep["Transport efficiency"])
    bp = bruggeman(eps_p, pos["Transport efficiency"])

    # Material properties
    cmax_n, cmax_p = fnum(neg["Maximum concentration [mol.m-3]"]), fnum(pos["Maximum concentration [mol.m-3]"])
    Rn, Rp = fnum(neg["Particle radius [m]"]), fnum(pos["Particle radius [m]"])
    Dn, Dp = fnum(neg["Diffusivity [m2.s-1]"]), fnum(pos["Diffusivity [m2.s-1]"])
    sig_n, sig_p = fnum(neg["Conductivity [S.m-1]"]), fnum(pos["Conductivity [S.m-1]"])

    ce0 = fnum(ic.get("Initial electrolyte concentration [mol.m-3]", 1000.0))
    T0 = fnum(ic.get("Initial temperature [K]", cell.get("Reference temperature [K]", 298.15)))
    De = interp_table(elyte["Diffusivity [m2.s-1]"], ce0)
    ke = interp_table(elyte["Conductivity [S.m-1]"], ce0)
    tplus = fnum(elyte["Cation transference number"])

    # Stoichiometry limits
    x0 = fnum(neg["Minimum stoichiometry"])
    x100 = fnum(neg["Maximum stoichiometry"])
    y100 = fnum(pos["Minimum stoichiometry"])
    y0 = fnum(pos["Maximum stoichiometry"])

    # Grouped-SPMe quantities
    Qp = FARADAY * alpha_p * cmax_p * Lp * A
    Qn = FARADAY * alpha_n * cmax_n * Ln * A
    Qmeas = fnum(cell["Nominal cell capacity [A.h]"]) * 3600.0
    Qe = FARADAY * eps_s * ce0 * Ltot * A

    Re_area = (Lp / (3 * eps_p**bp) + Ls / (eps_s**bs) + Ln / (3 * eps_n**bn)) / ke
    Rs_area = (Lp / sig_p + Ln / sig_n) / 3
    Rseries = (Re_area + Rs_area) / A + CONTACT_R

    scalars = {
        "Nominal cell capacity [A.h]": fnum(cell["Nominal cell capacity [A.h]"]),
        "Current function [A]": I_DC,
        "Initial temperature [K]": T0,
        "Initial SoC": soc,
        "Lower voltage cut-off [V]": fnum(cell["Lower voltage cut-off [V]"]),
        "Upper voltage cut-off [V]": fnum(cell["Upper voltage cut-off [V]"]),
        "Minimum negative stoichiometry": x0,
        "Maximum negative stoichiometry": x100,
        "Minimum positive stoichiometry": y100,
        "Maximum positive stoichiometry": y0,
        "Measured cell capacity [A.s]": Qmeas,
        "Reference electrolyte capacity [A.s]": Qe,
        "Negative electrode relative porosity": eps_n / eps_s,
        "Positive electrode relative porosity": eps_p / eps_s,
        "Negative particle diffusion time scale [s]": Rn**2 / Dn,
        "Positive particle diffusion time scale [s]": Rp**2 / Dp,
        "Negative electrode electrolyte diffusion time scale [s]": eps_s * Ltot**2 / (eps_n**bn * De),
        "Positive electrode electrolyte diffusion time scale [s]": eps_s * Ltot**2 / (eps_p**bp * De),
        "Separator electrolyte diffusion time scale [s]": eps_s * Ltot**2 / (eps_s**bs * De),
        "Negative electrode charge transfer time scale [s]": FARADAY * Rn / (M_N * np.sqrt(ce0)),
        "Positive electrode charge transfer time scale [s]": FARADAY * Rp / (M_P * np.sqrt(ce0)),
        "Negative electrode capacitance [F]": 3 * alpha_n * C_DL_N * Ln * A / Rn,
        "Positive electrode capacitance [F]": 3 * alpha_p * C_DL_P * Lp * A / Rp,
        "Cation transference number": tplus,
        "Negative electrode relative thickness": Ln / Ltot,
        "Positive electrode relative thickness": Lp / Ltot,
        "Positive theoretical electrode capacity [As]": Qp,
        "Negative theoretical electrode capacity [As]": Qn,
        "Series resistance [Ohm]": Rseries,
    }

    ocp_tables = {
        "Negative electrode OCP [V]": {"name": "U_n", "x": neg["OCP [V]"]["x"], "y": neg["OCP [V]"]["y"]},
        "Positive electrode OCP [V]": {"name": "U_p", "x": pos["OCP [V]"]["x"], "y": pos["OCP [V]"]["y"]},
    }

    grouped = dict(scalars)
    grouped["Negative electrode OCP [V]"] = ocp_fun(ocp_tables["Negative electrode OCP [V]"], "U_n")
    grouped["Positive electrode OCP [V]"] = ocp_fun(ocp_tables["Positive electrode OCP [V]"], "U_p")

    metadata = {
        "format": "flexible-bpx-grouped-spme-v1",
        "source_bpx_file": str(path),
        "note": "Plain JSON parameters plus OCP tables. The loader reconstructs PyBaMM Interpolant functions at runtime.",
        "constants": {
            "C_DL_N [F.m-2]": C_DL_N,
            "C_DL_P [F.m-2]": C_DL_P,
            "CONTACT_R [Ohm]": CONTACT_R,
            "I_DC [A]": I_DC,
            "FARADAY [C.mol-1]": FARADAY,
            "M_N": M_N,
            "M_P": M_P,
            "effective_total_electrode_area [m2]": A,
            "initial_electrolyte_concentration [mol.m-3]": ce0,
        },
    }
    return grouped, scalars, ocp_tables, metadata


# =============================================================================
# FLEXIBLE EXPORT / IMPORT
# =============================================================================
def save_flexible_parameter_set(scalars, ocp_tables, metadata, folder):
    folder = Path(folder)
    folder.mkdir(exist_ok=True)

    package = {
        **metadata,
        "grouped_spme_scalar_parameters": json_safe(scalars),
        "ocp_tables": json_safe(ocp_tables),
    }

    json_path = folder / "grouped_spme_parameters_flexible.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(package, f, indent=2)

    pd.DataFrame(
        [{"Parameter": k, "Value": v} for k, v in sorted(scalars.items())]
    ).to_csv(folder / "grouped_spme_scalar_parameters.csv", index=False)

    # Keep a copy of the source BPX schema too. This is optional but useful.
    try:
        shutil.copy2(BPX_FILE, folder / "source_bpx_schema_copy.json")
    except Exception:
        pass

    loader_code = r'''"""
Flexible loader for a BPX-derived PyBOP GroupedSPMe parameter set.

This loader avoids pickle/cloudpickle and PyBaMM/BPX schema validation.
It loads plain JSON scalars and reconstructs the two OCP functions at runtime.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import numpy as np
import pybamm

THIS_DIR = Path(__file__).parent
PARAM_FILE = THIS_DIR / "grouped_spme_parameters_flexible.json"


def _ocp_fun(table, default_name):
    xs = np.asarray(table["x"], dtype=float)
    ys = np.asarray(table["y"], dtype=float)
    order = np.argsort(xs)
    xs, ys = xs[order], ys[order]
    name = table.get("name", default_name)

    def ocp(sto):
        if hasattr(pybamm, "Symbol") and isinstance(sto, pybamm.Symbol):
            return pybamm.Interpolant(xs, ys, sto, name=name, extrapolate=True)
        return np.interp(sto, xs, ys)

    return ocp


def load_package():
    with open(PARAM_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def get_grouped_parameters(copy_parameters=True):
    package = load_package()
    params = dict(package["grouped_spme_scalar_parameters"])
    params["Negative electrode OCP [V]"] = _ocp_fun(
        package["ocp_tables"]["Negative electrode OCP [V]"], "U_n"
    )
    params["Positive electrode OCP [V]"] = _ocp_fun(
        package["ocp_tables"]["Positive electrode OCP [V]"], "U_p"
    )
    return copy.deepcopy(params) if copy_parameters else params


def get_scalar_parameters_only():
    return dict(load_package()["grouped_spme_scalar_parameters"])


def list_parameter_names():
    return sorted(get_grouped_parameters(copy_parameters=False).keys())
'''
    (folder / "FlexibleBPXGroupedSPMe.py").write_text(loader_code, encoding="utf-8")

    usage = f"""
Usage in another PyBOP/PyBaMM environment
========================================

Copy this whole folder:
    {folder.resolve()}

Then run:

import sys
import numpy as np
import pybop

sys.path.insert(0, r"{folder.resolve()}")
from FlexibleBPXGroupedSPMe import get_grouped_parameters

grouped_parameters = get_grouped_parameters()

model = pybop.lithium_ion.GroupedSPMe(
    parameter_set=grouped_parameters,
    eis=True,
    options={{"surface form": "differential", "contact resistance": "true"}},
    var_pts={{"x_n": 20, "x_s": 10, "x_p": 20, "r_n": 20, "r_p": 20}},
)
model.build(initial_state={{"Initial SoC": 0.5}})
Z = model.simulateEIS(inputs=None, f_eval=np.logspace(np.log10(2e-4), np.log10(1e3), 30))["Impedance"]
"""
    (folder / "README_usage.txt").write_text(usage, encoding="utf-8")
    return json_path


def load_flexible_parameter_set(folder):
    # Same behaviour as the saved external loader, useful for testing in this script.
    with open(Path(folder) / "grouped_spme_parameters_flexible.json", "r", encoding="utf-8") as f:
        package = json.load(f)
    params = dict(package["grouped_spme_scalar_parameters"])
    params["Negative electrode OCP [V]"] = ocp_fun(package["ocp_tables"]["Negative electrode OCP [V]"], "U_n")
    params["Positive electrode OCP [V]"] = ocp_fun(package["ocp_tables"]["Positive electrode OCP [V]"], "U_p")
    return params


# =============================================================================
# BUILD, EXPORT, AND RELOAD PARAMETERS
# =============================================================================
grouped, scalar_params, ocp_tables, metadata = grouped_from_bpx(BPX_FILE, SOC)
json_path = save_flexible_parameter_set(scalar_params, ocp_tables, metadata, PARAM_OUT)
print("Saved flexible parameter set to:", PARAM_OUT.resolve())
print("Main JSON:", json_path)

# Use the saved flexible form for the actual simulation, to verify portability.
grouped = load_flexible_parameter_set(PARAM_OUT)


# =============================================================================
# RUN SENSITIVITY
# =============================================================================
base = float(grouped[PARAMETER_NAME])
values = np.logspace(np.log10(base / FACTOR), np.log10(base * FACTOR), NPARAMS)
Zall = np.zeros((len(FREQ), NPARAMS), dtype=complex)

for j, value in enumerate(values):
    print(f"{j + 1}/{NPARAMS}: {PARAMETER_NAME} = {value:.4e}")
    pars = dict(grouped)
    pars[PARAMETER_NAME] = float(value)

    model = pybop.lithium_ion.GroupedSPMe(
        parameter_set=pars,
        eis=True,
        options=MODEL_OPTIONS,
        var_pts=VAR_PTS,
    )
    model.build(initial_state={"Initial SoC": SOC})
    Z = np.asarray(model.simulateEIS(inputs=None, f_eval=FREQ)["Impedance"], dtype=complex)
    if np.nanmedian(-np.imag(Z)) < 0:
        Z = np.conjugate(Z)
    Zall[:, j] = Z


# =============================================================================
# SAVE RESULTS AND PLOT
# =============================================================================
rows = []
for j, value in enumerate(values):
    for f, Z in zip(FREQ, Zall[:, j]):
        rows.append({
            "Parameter": PARAMETER_NAME,
            "Parameter value": value,
            "Frequency [Hz]": f,
            "Z_real [Ohm]": Z.real,
            "Z_imag [Ohm]": Z.imag,
            "-Z_imag [Ohm]": -Z.imag,
            "Z_abs [Ohm]": abs(Z),
            "Phase [deg]": np.angle(Z, deg=True),
        })

pd.DataFrame(rows).to_csv(OUT / "grouped_spme_bpx_sensitivity.csv", index=False)
savemat(OUT / "grouped_spme_bpx_sensitivity.mat", {"Z": Zall, "f": FREQ, "params": values, "name": PARAMETER_NAME})

plt.figure(figsize=(6, 6))
for j, value in enumerate(values):
    plt.plot(Zall[:, j].real, -Zall[:, j].imag, label=f"{value:.2e}")
plt.xlabel(r"$Z_r(\omega)$ [$\Omega$]")
plt.ylabel(r"$-Z_j(\omega)$ [$\Omega$]")
plt.title(f"GroupedSPMe sensitivity: {PARAMETER_NAME}")
plt.grid(True)
plt.axis("equal")
plt.legend(fontsize=7)
plt.tight_layout()
plt.savefig(OUT / "grouped_spme_bpx_sensitivity.png", dpi=300)
plt.show()

print("Done. Results saved in:", OUT.resolve())
print("Portable parameters saved in:", PARAM_OUT.resolve())


# %%
# =============================================================================
# CONTINUE: RUN GROUPED-SPMe EIS SIMULATION AND MAKE PLOT
# =============================================================================

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
from scipy.io import savemat
import pybop


# =============================================================================
# SIMULATION SETTINGS
# =============================================================================

output_dir = Path("bpx_grouped_spme_flexible")
output_dir.mkdir(exist_ok=True)

SOC = 0.5

fmin = 2e-4
fmax = 1e5
Nfreq = 100
frequencies = np.logspace(np.log10(fmin), np.log10(fmax), Nfreq)

model_options = {
    "surface form": "differential",
    "contact resistance": "true",
}


var_pts = {"x_n": 100, "x_s": 20, "x_p": 100, "r_n": 100, "r_p": 100}

# =============================================================================
# LOAD GROUPED PARAMETERS IF THEY ARE NOT ALREADY IN MEMORY
# =============================================================================

if "grouped_parameters" not in globals():
    import sys

    flexible_parameter_dir = output_dir / "flexible_parameter_set"

    sys.path.insert(
        0,
        str(flexible_parameter_dir.resolve()),
    )

    from FlexibleBPXGroupedSPMe import get_grouped_parameters

    grouped_parameters = get_grouped_parameters()

print("Grouped parameters loaded.")
print("Number of grouped parameters:", len(grouped_parameters))


# =============================================================================
# SINGLE EIS SIMULATION
# =============================================================================

model = pybop.lithium_ion.GroupedSPMe(
    parameter_set=grouped_parameters,
    eis=True,
    options=model_options,
    var_pts=var_pts,
)

model.build(
    initial_state={"Initial SoC": SOC},
)

simulation = model.simulateEIS(
    inputs=None,
    f_eval=frequencies,
)

Z = np.asarray(simulation["Impedance"], dtype=complex)

# Use normal capacitive Nyquist convention
if np.nanmedian(-np.imag(Z)) < 0:
    Z = np.conjugate(Z)


# =============================================================================
# SAVE SIMULATION DATA
# =============================================================================

df_eis = pd.DataFrame(
    {
        "Frequency [Hz]": frequencies,
        "Z_real [Ohm]": np.real(Z),
        "Z_imag [Ohm]": np.imag(Z),
        "-Z_imag [Ohm]": -np.imag(Z),
        "Z_abs [Ohm]": np.abs(Z),
        "Phase [deg]": np.angle(Z, deg=True),
        "SOC": SOC,
    }
)

csv_path = output_dir / "grouped_spme_single_eis.csv"
df_eis.to_csv(csv_path, index=False)

mat_path = output_dir / "grouped_spme_single_eis.mat"
savemat(
    mat_path,
    {
        "Z": Z,
        "f": frequencies,
        "SOC": SOC,
    },
)

print("Saved EIS CSV to:", csv_path)
print("Saved EIS MAT to:", mat_path)


# =============================================================================
# NYQUIST PLOT
# =============================================================================

fig, ax = plt.subplots(figsize=(6.5, 6.5))

ax.plot(
    np.real(Z),
    -np.imag(Z),
    "-o",
    markersize=4,
    linewidth=1.8,
)

ax.set_xlabel(r"$Z_r(\omega)$ [$\Omega$]")
ax.set_ylabel(r"$-Z_j(\omega)$ [$\Omega$]")
ax.set_title(f"Grouped-SPMe EIS from BPX parameters\nSOC = {SOC:.2f}")
ax.grid(True)
ax.set_aspect("equal")

fig.tight_layout()

plot_path = output_dir / "grouped_spme_single_eis_nyquist.png"
fig.savefig(plot_path, dpi=300)
plt.show()

print("Saved Nyquist plot to:", plot_path)




print("\nDONE")
print("Output directory:", output_dir.resolve())

# %%
# =============================================================================
# RUN GROUPED-SPMe EIS SIMULATION AND PLOT
# =============================================================================

import sys
import importlib
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.io import savemat

import pybop


# =============================================================================
# SETTINGS
# =============================================================================

output_dir = Path(
    r"C:\Users\mugi_jo\Documents\DLR_PROJECTS\bpx_grouped_spme_flexible"
)
output_dir.mkdir(exist_ok=True)

flexible_parameter_dir = output_dir / "flexible_parameter_set"

SOC = 0.5

frequencies = np.logspace(-4, 5, 100)

model_options = {
    "surface form": "differential",
    "contact resistance": "true",
}

var_pts = {
    "x_n": 100,
    "x_s": 20,
    "x_p": 100,
    "r_n": 100,
    "r_p": 100,
}


# =============================================================================
# FORCE RELOAD GROUPED PARAMETERS
# =============================================================================

sys.path.insert(0, str(flexible_parameter_dir.resolve()))

if "FlexibleBPXGroupedSPMe" in sys.modules:
    del sys.modules["FlexibleBPXGroupedSPMe"]

from FlexibleBPXGroupedSPMe import get_grouped_parameters

grouped_parameters = get_grouped_parameters()

print("Grouped parameters reloaded from:")
print(flexible_parameter_dir)
print("Number of grouped parameters:", len(grouped_parameters))


# =============================================================================
# OPTIONAL: PRINT IMPORTANT GROUPED PARAMETERS
# =============================================================================

important_keys = [
    "Series resistance [Ohm]",
    "Negative electrode relative porosity",
    "Positive electrode relative porosity",
    "Negative electrode charge transfer time scale [s]",
    "Positive electrode charge transfer time scale [s]",
    "Negative particle diffusion time scale [s]",
    "Positive particle diffusion time scale [s]",
    "Reference electrolyte capacity [A.s]",
    "Measured cell capacity [A.s]",
]

print("\nImportant grouped parameters:")
for key in important_keys:
    if key in grouped_parameters:
        print(f"{key}: {grouped_parameters[key]}")
    else:
        print(f"{key}: NOT FOUND")


# =============================================================================
# OPTIONAL SERIES RESISTANCE CHECK
# =============================================================================
# For comparison with PyBaMM, you may temporarily remove/adjust series resistance.
# Keep this False for normal grouped-parameter simulation.

OVERRIDE_SERIES_RESISTANCE = False
SERIES_RESISTANCE_VALUE = 0.0

if OVERRIDE_SERIES_RESISTANCE:
    grouped_parameters["Series resistance [Ohm]"] = SERIES_RESISTANCE_VALUE
    print(f"\nOverriding Series resistance [Ohm] = {SERIES_RESISTANCE_VALUE}")


# =============================================================================
# BUILD PYBOP GROUPED-SPMe MODEL
# =============================================================================

model = pybop.lithium_ion.GroupedSPMe(
    parameter_set=grouped_parameters,
    eis=True,
    options=model_options,
    var_pts=var_pts,
)

model.build(
    initial_state={"Initial SoC": SOC},
)


# =============================================================================
# RUN EIS
# =============================================================================

simulation = model.simulateEIS(
    inputs=None,
    f_eval=frequencies,
)

Z = np.asarray(simulation["Impedance"], dtype=complex)

# Capacitive Nyquist convention
if np.nanmedian(-np.imag(Z)) < 0:
    Z = np.conjugate(Z)


# =============================================================================
# PRINT IMPEDANCE SCALE
# =============================================================================

print("\nImpedance scale:")
print("min Re(Z):", np.min(np.real(Z)))
print("max Re(Z):", np.max(np.real(Z)))
print("max -Im(Z):", np.max(-np.imag(Z)))
print("high-frequency Re(Z):", np.real(Z[-1]))
print("low-frequency Re(Z):", np.real(Z[0]))


# =============================================================================
# SAVE DATA
# =============================================================================

df_eis = pd.DataFrame(
    {
        "Frequency [Hz]": frequencies,
        "Z_real [Ohm]": np.real(Z),
        "Z_imag [Ohm]": np.imag(Z),
        "-Z_imag [Ohm]": -np.imag(Z),
        "Z_abs [Ohm]": np.abs(Z),
        "Phase [deg]": np.angle(Z, deg=True),
        "SOC": SOC,
    }
)

csv_path = output_dir / "grouped_spme_single_eis.csv"
df_eis.to_csv(csv_path, index=False)

mat_path = output_dir / "grouped_spme_single_eis.mat"
savemat(
    mat_path,
    {
        "Z": Z,
        "f": frequencies,
        "SOC": SOC,
    },
)

print("\nSaved EIS CSV to:", csv_path)
print("Saved EIS MAT to:", mat_path)


# =============================================================================
# NYQUIST PLOT
# =============================================================================

fig, ax = plt.subplots(figsize=(6.5, 6.5))

ax.plot(
    np.real(Z),
    -np.imag(Z),
    "-o",
    markersize=4,
    linewidth=1.8,
)

ax.set_xlabel(r"$Z_r(\omega)$ [$\Omega$]")
ax.set_ylabel(r"$-Z_j(\omega)$ [$\Omega$]")
ax.set_title(f"PyBOP Grouped-SPMe EIS from BPX grouped parameters\nSOC = {SOC:.2f}")
ax.grid(True)
ax.set_aspect("equal", adjustable="box")

fig.tight_layout()

plot_path = output_dir / "grouped_spme_single_eis_nyquist.png"
fig.savefig(plot_path, dpi=300)
plt.show()
plt.close(fig)

print("Saved Nyquist plot to:", plot_path)


print("\nDONE")
print("Output directory:", output_dir.resolve())

# %%
###correction

# %%
"""
Export BPX JSON parameters to a portable PyBOP GroupedSPMe parameter set.

This version uses the same grouped-parameter combinations as PyBOP's
GroupedSPMe.apply_parameter_grouping(), but reads the BPX JSON directly.
It avoids pybamm.ParameterValues.create_from_bpx(), so it also avoids BPX
schema validation conflicts.
"""

import json
import math
import shutil
from pathlib import Path

import numpy as np
import pandas as pd

# =============================================================================
# USER SETTINGS
# =============================================================================

BPX_FILE = Path(
    r"C:\Users\mugi_jo\Downloads\hydr0_graphite-lnmo_schmitt-2026_validation.bpx_1_patched_for_current_bpx.json"
)

OUT = Path(r"C:\Users\mugi_jo\Documents\DLR_PROJECTS\bpx_grouped_spme_flexible")
PARAM_OUT = OUT / "flexible_parameter_set"
OUT.mkdir(parents=True, exist_ok=True)
PARAM_OUT.mkdir(parents=True, exist_ok=True)

SOC = 0.5

# BPX gives area per electrode pair and number of parallel pairs. For a full-cell
# capacity/resistance comparable to the BPX nominal cell, use total area.
USE_TOTAL_PARALLEL_AREA = True

# Supplemental values not normally present in your BPX schema
C_DL_N = 0.02        # F m-2
C_DL_P = 0.092       # F m-2
CONTACT_R = 0.0      # Ohm
I_DC = 0.0           # A, equilibrium EIS
B_SOLID_N = 1.5      # solid-phase Bruggeman coefficient, if BPX does not provide it
B_SOLID_P = 1.5

# PyBOP GroupedSPMe constants used in apply_parameter_grouping()
FARADAY = 96485.33212
M_P = 3.42e-6        # (A/m2)(m3/mol)**1.5
M_N = 6.48e-7        # (A/m2)(m3/mol)**1.5


# =============================================================================
# HELPERS
# =============================================================================

def fnum(x):
    return float(x)


def json_safe(x):
    if isinstance(x, (np.integer, int)):
        return int(x)
    if isinstance(x, (np.floating, float)):
        x = float(x)
        return x if math.isfinite(x) else None
    if isinstance(x, np.ndarray):
        return [json_safe(v) for v in x.tolist()]
    if isinstance(x, (list, tuple)):
        return [json_safe(v) for v in x]
    if isinstance(x, dict):
        return {str(k): json_safe(v) for k, v in x.items()}
    return x


def interp_table(table, x):
    xs = np.asarray(table["x"], dtype=float)
    ys = np.asarray(table["y"], dtype=float)
    order = np.argsort(xs)
    return float(np.interp(float(x), xs[order], ys[order]))


def bruggeman_from_transport_efficiency(eps, transport_efficiency, default=1.5):
    eps = float(eps)
    tau = float(transport_efficiency)
    if eps <= 0 or eps >= 1 or tau <= 0:
        return float(default)
    return float(math.log(tau) / math.log(eps))


def state_initial_conditions(bpx):
    state = bpx.get("State", {})
    return state.get("Initial conditions") or state.get("InitialConditions") or {}


# =============================================================================
# BPX JSON -> GROUPED-SPMe PARAMETERS USING PYBOP FORMULAS
# =============================================================================

def grouped_from_bpx_using_pybop_formula(path, soc=0.5):
    with open(path, "r", encoding="utf-8") as f:
        bpx = json.load(f)

    p = bpx["Parameterisation"]
    cell = p["Cell"]
    elyte = p["Electrolyte"]
    neg = p["Negative electrode"]
    pos = p["Positive electrode"]
    sep = p["Separator"]
    user = p.get("User-defined", {})
    ic = state_initial_conditions(bpx)

    # -------------------------------------------------------------------------
    # Geometry and area
    # PyBOP formula uses A = electrode height * electrode width. For BPX, the
    # equivalent total cell area is electrode area times parallel electrode pairs.
    # -------------------------------------------------------------------------
    A_pair = fnum(cell["Electrode area [m2]"])
    n_parallel = fnum(cell.get("Number of electrode pairs connected in parallel to make a cell", 1))
    A = A_pair * n_parallel if USE_TOTAL_PARALLEL_AREA else A_pair

    L_n = fnum(neg["Thickness [m]"])
    L_s = fnum(sep["Thickness [m]"])
    L_p = fnum(pos["Thickness [m]"])
    L = L_n + L_s + L_p

    # -------------------------------------------------------------------------
    # Phase fractions and Bruggeman coefficients
    # -------------------------------------------------------------------------
    eps_n = fnum(neg["Porosity"])
    eps_s = fnum(sep["Porosity"])
    eps_p = fnum(pos["Porosity"])

    alpha_n = fnum(user.get("Negative electrode active material volume fraction", 1 - eps_n))
    alpha_p = fnum(user.get("Positive electrode active material volume fraction", 1 - eps_p))

    b_n = bruggeman_from_transport_efficiency(eps_n, neg.get("Transport efficiency", eps_n**1.5))
    b_s = bruggeman_from_transport_efficiency(eps_s, sep.get("Transport efficiency", eps_s**1.5))
    b_p = bruggeman_from_transport_efficiency(eps_p, pos.get("Transport efficiency", eps_p**1.5))

    # Effective solid conductivities, same form as PyBOP apply_parameter_grouping()
    sigma_n = fnum(neg["Conductivity [S.m-1]"]) * alpha_n**B_SOLID_N
    sigma_p = fnum(pos["Conductivity [S.m-1]"]) * alpha_p**B_SOLID_P

    # -------------------------------------------------------------------------
    # Material and electrolyte properties
    # -------------------------------------------------------------------------
    cmax_n = fnum(neg["Maximum concentration [mol.m-3]"])
    cmax_p = fnum(pos["Maximum concentration [mol.m-3]"])
    R_n = fnum(neg["Particle radius [m]"])
    R_p = fnum(pos["Particle radius [m]"])
    D_n = fnum(neg["Diffusivity [m2.s-1]"])
    D_p = fnum(pos["Diffusivity [m2.s-1]"])

    ce0 = fnum(ic.get("Initial electrolyte concentration [mol.m-3]", 1000.0))
    T0 = fnum(ic.get("Initial temperature [K]", cell.get("Reference temperature [K]", 298.15)))
    D_e = interp_table(elyte["Diffusivity [m2.s-1]"], ce0)
    sigma_e = interp_table(elyte["Conductivity [S.m-1]"], ce0)
    t_plus = fnum(elyte["Cation transference number"])

    # -------------------------------------------------------------------------
    # Stoichiometry limits
    # These replace PyBOP's get_min_max_stoichiometries(parameter_set)
    # because the BPX validator is not used here.
    # -------------------------------------------------------------------------
    x_0 = fnum(neg["Minimum stoichiometry"])
    x_100 = fnum(neg["Maximum stoichiometry"])
    y_100 = fnum(pos["Minimum stoichiometry"])
    y_0 = fnum(pos["Maximum stoichiometry"])

    # -------------------------------------------------------------------------
    # PyBOP grouped combinations
    # Same formulas as GroupedSPMe.apply_parameter_grouping()
    # -------------------------------------------------------------------------
    Q_th_p = FARADAY * alpha_p * cmax_p * L_p * A
    Q_th_n = FARADAY * alpha_n * cmax_n * L_n * A
    Q_meas_p = (y_0 - y_100) * Q_th_p
    Q_meas_n = (x_100 - x_0) * Q_th_n
    Q_meas = 0.5 * (Q_meas_p + Q_meas_n)

    Q_e = FARADAY * eps_s * ce0 * L * A

    zeta_p = eps_p / eps_s
    zeta_n = eps_n / eps_s

    tau_d_p = R_p**2 / D_p
    tau_d_n = R_n**2 / D_n

    tau_e_p = eps_s * L**2 / (eps_p**b_p * D_e)
    tau_e_n = eps_s * L**2 / (eps_n**b_n * D_e)
    tau_e_s = eps_s * L**2 / (eps_s**b_s * D_e)

    tau_ct_p = FARADAY * R_p / (M_P * np.sqrt(ce0))
    tau_ct_n = FARADAY * R_n / (M_N * np.sqrt(ce0))

    C_p = 3 * alpha_p * C_DL_P * L_p * A / R_p
    C_n = 3 * alpha_n * C_DL_N * L_n * A / R_n

    l_p = L_p / L
    l_n = L_n / L

    R_e = (
        L_p / (3 * eps_p**b_p)
        + L_s / (eps_s**b_s)
        + L_n / (3 * eps_n**b_n)
    ) / (sigma_e * A)
    R_s = (L_p / sigma_p + L_n / sigma_n) / (3 * A)
    R_0 = R_e + R_s + CONTACT_R

    scalar_params = {
        "Nominal cell capacity [A.h]": fnum(cell["Nominal cell capacity [A.h]"]),
        "Current function [A]": I_DC,
        "Initial temperature [K]": T0,
        "Initial SoC": soc,
        "Minimum negative stoichiometry": x_0,
        "Maximum negative stoichiometry": x_100,
        "Minimum positive stoichiometry": y_100,
        "Maximum positive stoichiometry": y_0,
        "Lower voltage cut-off [V]": fnum(cell["Lower voltage cut-off [V]"]),
        "Upper voltage cut-off [V]": fnum(cell["Upper voltage cut-off [V]"]),
        "Measured cell capacity [A.s]": Q_meas,
        "Reference electrolyte capacity [A.s]": Q_e,
        "Positive electrode relative porosity": zeta_p,
        "Negative electrode relative porosity": zeta_n,
        "Positive particle diffusion time scale [s]": tau_d_p,
        "Negative particle diffusion time scale [s]": tau_d_n,
        "Positive electrode electrolyte diffusion time scale [s]": tau_e_p,
        "Negative electrode electrolyte diffusion time scale [s]": tau_e_n,
        "Separator electrolyte diffusion time scale [s]": tau_e_s,
        "Positive electrode charge transfer time scale [s]": tau_ct_p,
        "Negative electrode charge transfer time scale [s]": tau_ct_n,
        "Positive electrode capacitance [F]": C_p,
        "Negative electrode capacitance [F]": C_n,
        "Cation transference number": t_plus,
        "Positive electrode relative thickness": l_p,
        "Negative electrode relative thickness": l_n,
        "Series resistance [Ohm]": R_0,
    }

    ocp_tables = {
        "Negative electrode OCP [V]": {
            "name": "U_n",
            "x": neg["OCP [V]"]["x"],
            "y": neg["OCP [V]"]["y"],
        },
        "Positive electrode OCP [V]": {
            "name": "U_p",
            "x": pos["OCP [V]"]["x"],
            "y": pos["OCP [V]"]["y"],
        },
    }

    metadata = {
        "format": "flexible-bpx-grouped-spme-pybop-formula-v2",
        "source_bpx_file": str(path),
        "note": "Grouped parameters use the same combinations as PyBOP GroupedSPMe.apply_parameter_grouping(). OCP tables are saved as JSON and reconstructed by the loader.",
        "capacity_check": {
            "Q_meas_positive [A.s]": Q_meas_p,
            "Q_meas_negative [A.s]": Q_meas_n,
            "Q_meas_saved_average [A.s]": Q_meas,
            "nominal_capacity_from_bpx [A.s]": fnum(cell["Nominal cell capacity [A.h]"]) * 3600.0,
            "relative_difference_negative_vs_positive": abs(Q_meas_n / Q_meas_p - 1.0),
        },
        "series_resistance_breakdown": {
            "electrolyte_resistance [Ohm]": R_e,
            "solid_resistance [Ohm]": R_s,
            "contact_resistance [Ohm]": CONTACT_R,
            "total_series_resistance [Ohm]": R_0,
        },
        "constants": {
            "C_DL_N [F.m-2]": C_DL_N,
            "C_DL_P [F.m-2]": C_DL_P,
            "CONTACT_R [Ohm]": CONTACT_R,
            "I_DC [A]": I_DC,
            "FARADAY [C.mol-1]": FARADAY,
            "M_N": M_N,
            "M_P": M_P,
            "B_SOLID_N": B_SOLID_N,
            "B_SOLID_P": B_SOLID_P,
            "area_per_pair [m2]": A_pair,
            "number_parallel_pairs": n_parallel,
            "effective_total_area [m2]": A,
            "initial_electrolyte_concentration [mol.m-3]": ce0,
            "electrolyte_diffusivity_at_ce0 [m2.s-1]": D_e,
            "electrolyte_conductivity_at_ce0 [S.m-1]": sigma_e,
        },
    }

    return scalar_params, ocp_tables, metadata


# =============================================================================
# FLEXIBLE EXPORT
# =============================================================================

def save_flexible_parameter_set(scalars, ocp_tables, metadata, folder):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)

    package = {
        **metadata,
        "grouped_spme_scalar_parameters": json_safe(scalars),
        "ocp_tables": json_safe(ocp_tables),
    }

    json_path = folder / "grouped_spme_parameters_flexible.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(package, f, indent=2)

    pd.DataFrame(
        [{"Parameter": k, "Value": v} for k, v in sorted(scalars.items())]
    ).to_csv(folder / "grouped_spme_scalar_parameters.csv", index=False)

    with open(folder / "metadata.json", "w", encoding="utf-8") as f:
        json.dump(json_safe(metadata), f, indent=2)

    try:
        shutil.copy2(BPX_FILE, folder / "source_bpx_schema_copy.json")
    except Exception:
        pass

    loader_code = r'''"""
Flexible loader for a BPX-derived PyBOP GroupedSPMe parameter set.

No pickle/cloudpickle. No BPX validation. It loads JSON scalars and recreates
OCP functions as PyBaMM Interpolants.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import numpy as np
import pybamm

THIS_DIR = Path(__file__).parent
PARAM_FILE = THIS_DIR / "grouped_spme_parameters_flexible.json"


def _ocp_fun(table, default_name):
    xs = np.asarray(table["x"], dtype=float)
    ys = np.asarray(table["y"], dtype=float)
    order = np.argsort(xs)
    xs = xs[order]
    ys = ys[order]
    name = table.get("name", default_name)

    def ocp(sto):
        if isinstance(sto, pybamm.Symbol):
            return pybamm.Interpolant(xs, ys, sto, name=name, extrapolate=True)
        return np.interp(sto, xs, ys)

    return ocp


def load_package():
    with open(PARAM_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def get_grouped_parameters(copy_parameters=True):
    package = load_package()
    params = dict(package["grouped_spme_scalar_parameters"])
    params["Negative electrode OCP [V]"] = _ocp_fun(
        package["ocp_tables"]["Negative electrode OCP [V]"], "U_n"
    )
    params["Positive electrode OCP [V]"] = _ocp_fun(
        package["ocp_tables"]["Positive electrode OCP [V]"], "U_p"
    )
    return copy.deepcopy(params) if copy_parameters else params


def get_scalar_parameters_only():
    return dict(load_package()["grouped_spme_scalar_parameters"])


def list_parameter_names():
    return sorted(get_grouped_parameters(copy_parameters=False).keys())
'''
    (folder / "FlexibleBPXGroupedSPMe.py").write_text(loader_code, encoding="utf-8")

    usage = f"""
Usage
=====

import sys
import numpy as np
import pybop

sys.path.insert(0, r"{folder.resolve()}")
from FlexibleBPXGroupedSPMe import get_grouped_parameters

grouped_parameters = get_grouped_parameters()

model = pybop.lithium_ion.GroupedSPMe(
    parameter_set=grouped_parameters,
    eis=True,
    options={{"surface form": "differential", "contact resistance": "true"}},
    var_pts={{"x_n": 20, "x_s": 10, "x_p": 20, "r_n": 20, "r_p": 20}},
)
model.build(initial_state={{"Initial SoC": 0.5}})
Z = model.simulateEIS(inputs=None, f_eval=np.logspace(-4, 5, 100))["Impedance"]
"""
    (folder / "README_usage.txt").write_text(usage, encoding="utf-8")

    return json_path


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    scalars, ocp_tables, metadata = grouped_from_bpx_using_pybop_formula(BPX_FILE, SOC)
    json_path = save_flexible_parameter_set(scalars, ocp_tables, metadata, PARAM_OUT)

    print("\nSaved portable grouped-SPMe parameter set to:")
    print(PARAM_OUT.resolve())
    print("Main JSON:", json_path)

    print("\nImportant grouped parameters:")
    for key in [
        "Series resistance [Ohm]",
        "Measured cell capacity [A.s]",
        "Reference electrolyte capacity [A.s]",
        "Negative electrode charge transfer time scale [s]",
        "Positive electrode charge transfer time scale [s]",
        "Negative particle diffusion time scale [s]",
        "Positive particle diffusion time scale [s]",
    ]:
        print(f"{key}: {scalars[key]}")

    print("\nCapacity check:")
    for k, v in metadata["capacity_check"].items():
        print(f"{k}: {v}")


# %%
"""
Load the portable BPX-derived PyBOP GroupedSPMe parameter set and run one EIS simulation.
"""

import importlib
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pybop
from scipy.io import savemat

# =============================================================================
# SETTINGS
# =============================================================================

OUT = Path(r"C:\Users\mugi_jo\Documents\DLR_PROJECTS\bpx_grouped_spme_flexible")
PARAM_OUT = OUT / "flexible_parameter_set"
OUT.mkdir(parents=True, exist_ok=True)

SOC = 0.5
FREQUENCIES = np.logspace(-4, 5, 100)

MODEL_OPTIONS = {
    "surface form": "differential",
    "contact resistance": "true",
}

VAR_PTS = {
    "x_n": 100,
    "x_s": 20,
    "x_p": 100,
    "r_n": 100,
    "r_p": 100,
}

# =============================================================================
# LOAD PARAMETERS, FORCE RELOAD TO AVOID STALE NOTEBOOK VALUES
# =============================================================================

sys.path.insert(0, str(PARAM_OUT.resolve()))

if "FlexibleBPXGroupedSPMe" in sys.modules:
    del sys.modules["FlexibleBPXGroupedSPMe"]

import FlexibleBPXGroupedSPMe
importlib.reload(FlexibleBPXGroupedSPMe)

grouped_parameters = FlexibleBPXGroupedSPMe.get_grouped_parameters()

print("Grouped parameters loaded from:")
print(PARAM_OUT.resolve())
print("Number of grouped parameters:", len(grouped_parameters))

print("\nImportant grouped parameters:")
for key in [
    "Series resistance [Ohm]",
    "Measured cell capacity [A.s]",
    "Reference electrolyte capacity [A.s]",
    "Negative electrode charge transfer time scale [s]",
    "Positive electrode charge transfer time scale [s]",
    "Negative particle diffusion time scale [s]",
    "Positive particle diffusion time scale [s]",
    "Negative electrode relative porosity",
    "Positive electrode relative porosity",
]:
    print(f"{key}: {grouped_parameters.get(key, 'NOT FOUND')}")

# =============================================================================
# BUILD MODEL AND RUN EIS
# =============================================================================

model = pybop.lithium_ion.GroupedSPMe(
    parameter_set=grouped_parameters,
    eis=True,
    options=MODEL_OPTIONS,
    var_pts=VAR_PTS,
)
model.build(initial_state={"Initial SoC": SOC})

simulation = model.simulateEIS(inputs=None, f_eval=FREQUENCIES)
Z = np.asarray(simulation["Impedance"], dtype=complex)

# Capacitive Nyquist convention
if np.nanmedian(-np.imag(Z)) < 0:
    Z = np.conjugate(Z)

# =============================================================================
# SAVE RESULTS
# =============================================================================

df = pd.DataFrame(
    {
        "Frequency [Hz]": FREQUENCIES,
        "Z_real [Ohm]": np.real(Z),
        "Z_imag [Ohm]": np.imag(Z),
        "-Z_imag [Ohm]": -np.imag(Z),
        "Z_abs [Ohm]": np.abs(Z),
        "Phase [deg]": np.angle(Z, deg=True),
        "SOC": SOC,
    }
)

csv_path = OUT / "grouped_spme_single_eis.csv"
mat_path = OUT / "grouped_spme_single_eis.mat"
plot_path = OUT / "grouped_spme_single_eis_nyquist.png"

df.to_csv(csv_path, index=False)
savemat(mat_path, {"Z": Z, "f": FREQUENCIES, "SOC": SOC})

print("\nImpedance scale:")
print("min Re(Z):", np.min(np.real(Z)))
print("max Re(Z):", np.max(np.real(Z)))
print("max -Im(Z):", np.max(-np.imag(Z)))

# =============================================================================
# PLOT
# =============================================================================

fig, ax = plt.subplots(figsize=(6.5, 6.5))
ax.plot(np.real(Z), -np.imag(Z), "-o", markersize=4, linewidth=1.8)
ax.set_xlabel(r"$Z_r(\omega)$ [$\Omega$]")
ax.set_ylabel(r"$-Z_j(\omega)$ [$\Omega$]")
ax.set_title(f"PyBOP Grouped-SPMe EIS from BPX parameters\nSOC = {SOC:.2f}")
ax.grid(True)
ax.set_aspect("equal", adjustable="box")
fig.tight_layout()
fig.savefig(plot_path, dpi=300)
plt.show()
plt.close(fig)

print("\nSaved EIS CSV to:", csv_path)
print("Saved EIS MAT to:", mat_path)
print("Saved Nyquist plot to:", plot_path)
print("Output directory:", OUT.resolve())


# %%


# %%
"""
01_export_physical_parameters_then_apply_grouping.py

Purpose
-------
1. Read the BPX JSON directly, without pybamm.ParameterValues.create_from_bpx().
2. Save the BPX-derived physical PyBaMM parameters individually as a portable
   JSON parameter set.
3. Rebuild a pybamm.ParameterValues object from that portable parameter set.
4. Group the parameters using PyBOP's own apply_parameter_grouping() function.
5. Save the grouped-SPMe parameters as a second portable JSON parameter set.

V4 fix: adds both electrode OCP entropic-change parameters required by PyBaMM ElectrodeSOH during PyBOP grouping.

This avoids pickle/cloudpickle and avoids BPX validator/schema issues.
"""

from __future__ import annotations

import copy
import json
import math
import shutil
from pathlib import Path

import numpy as np
import pandas as pd
import pybamm
import pybop


# =============================================================================
# USER SETTINGS
# =============================================================================

BPX_FILE = Path(
    r"C:\Users\mugi_jo\Downloads\hydr0_graphite-lnmo_schmitt-2026_validation.bpx_1_patched_for_current_bpx.json"
)

OUT = Path("bpx_grouped_spme_apply_grouping")
PHYSICAL_DIR = OUT / "physical_parameter_set"
GROUPED_DIR = OUT / "grouped_parameter_set"

OUT.mkdir(exist_ok=True)
PHYSICAL_DIR.mkdir(exist_ok=True)
GROUPED_DIR.mkdir(exist_ok=True)

SOC = 0.5

# Supplemental values not present in your BPX schema but required by PyBOP grouping.
C_DL_N = 0.02       # F m-2
C_DL_P = 0.092      # F m-2
CONTACT_R = 0.0     # Ohm
I_DC = 0.0          # A, equilibrium EIS

FARADAY = 96485.33212
GAS_CONSTANT = 8.31446261815324

# If PyBOP raises because Q_meas_n and Q_meas_p differ slightly, rebalance the
# positive active-material volume fraction so apply_parameter_grouping can run.
BALANCE_CAPACITY_FOR_PYBOP_GROUPING = True


# =============================================================================
# SMALL HELPERS
# =============================================================================

def fnum(x, default=None):
    if x is None:
        if default is None:
            raise ValueError("Missing required numeric value")
        return float(default)
    return float(x)


def json_safe(x):
    if isinstance(x, (np.integer, int)):
        return int(x)
    if isinstance(x, (np.floating, float)):
        x = float(x)
        return x if math.isfinite(x) else None
    if isinstance(x, np.ndarray):
        return [json_safe(v) for v in x.tolist()]
    if isinstance(x, (list, tuple)):
        return [json_safe(v) for v in x]
    if isinstance(x, dict):
        return {str(k): json_safe(v) for k, v in x.items()}
    return x


def interp_table(table, x):
    xs = np.asarray(table["x"], dtype=float)
    ys = np.asarray(table["y"], dtype=float)
    order = np.argsort(xs)
    return float(np.interp(float(x), xs[order], ys[order]))


def bruggeman_from_transport_efficiency(eps, transport_efficiency):
    eps = float(eps)
    transport_efficiency = float(transport_efficiency)
    return float(math.log(transport_efficiency) / math.log(eps))


def state_initial_conditions(bpx):
    state = bpx.get("State", {})
    return (
        state.get("Initial conditions")
        or state.get("InitialConditions")
        or state.get("InitialConditions", {})
        or {}
    )


def ocp_fun_from_table(table, name):
    xs = np.asarray(table["x"], dtype=float)
    ys = np.asarray(table["y"], dtype=float)
    order = np.argsort(xs)
    xs = xs[order]
    ys = ys[order]

    def ocp(sto):
        if hasattr(pybamm, "Symbol") and isinstance(sto, pybamm.Symbol):
            return pybamm.Interpolant(xs, ys, sto, name=name, extrapolate=True)
        return np.interp(sto, xs, ys)

    return ocp


def make_parameter_values(scalars, ocp_tables):
    """Build pybamm.ParameterValues from saved scalar parameters + OCP tables."""
    params = dict(scalars)
    params["Negative electrode OCP [V]"] = ocp_fun_from_table(
        ocp_tables["Negative electrode OCP [V]"], "U_n"
    )
    params["Positive electrode OCP [V]"] = ocp_fun_from_table(
        ocp_tables["Positive electrode OCP [V]"], "U_p"
    )
    return pybamm.ParameterValues(values=params)


def save_table(d, path, key_name="Parameter"):
    rows = []
    for key, value in sorted(d.items()):
        rows.append({key_name: key, "Type": type(value).__name__, "Value": repr(value)[:500]})
    pd.DataFrame(rows).to_csv(path, index=False)


# =============================================================================
# BPX JSON -> INDIVIDUAL PHYSICAL PYBAMM PARAMETERS
# =============================================================================

def physical_parameter_set_from_bpx(path, soc=0.5):
    with open(path, "r", encoding="utf-8") as f:
        bpx = json.load(f)

    p = bpx["Parameterisation"]
    cell = p["Cell"]
    elyte = p["Electrolyte"]
    neg = p["Negative electrode"]
    pos = p["Positive electrode"]
    sep = p["Separator"]
    user = p.get("User-defined", {})
    ic = state_initial_conditions(bpx)

    # Effective total electrode area used by PyBOP grouping:
    # A = Electrode height [m] * Electrode width [m]
    n_parallel = fnum(cell.get("Number of electrode pairs connected in parallel to make a cell", 1.0))
    area_single_pair = fnum(cell["Electrode area [m2]"])
    area_total = area_single_pair * n_parallel

    # Store the effective area as height * width, because PyBOP grouping expects these two names.
    electrode_height = area_total
    electrode_width = 1.0

    # Geometry and fractions
    L_n = fnum(neg["Thickness [m]"])
    L_s = fnum(sep["Thickness [m]"])
    L_p = fnum(pos["Thickness [m]"])

    eps_n = fnum(neg["Porosity"])
    eps_s = fnum(sep["Porosity"])
    eps_p = fnum(pos["Porosity"])

    alpha_n = fnum(user.get("Negative electrode active material volume fraction", 1.0 - eps_n))
    alpha_p = fnum(user.get("Positive electrode active material volume fraction", 1.0 - eps_p))

    b_n = bruggeman_from_transport_efficiency(eps_n, neg["Transport efficiency"])
    b_s = bruggeman_from_transport_efficiency(eps_s, sep["Transport efficiency"])
    b_p = bruggeman_from_transport_efficiency(eps_p, pos["Transport efficiency"])

    # Initial conditions
    ce0 = fnum(
        ic.get("Initial electrolyte concentration [mol.m-3]")
        or ic.get("Initial concentration in electrolyte [mol.m-3]")
        or ic.get("Electrolyte initial concentration [mol.m-3]"),
        default=1000.0,
    )
    T0 = fnum(
        ic.get("Initial temperature [K]")
        or cell.get("Reference temperature [K]"),
        default=298.15,
    )

    # Electrolyte tables are scalarised at ce0, because PyBOP grouping expects scalar De and kappa_e.
    De = interp_table(elyte["Diffusivity [m2.s-1]"], ce0)
    kappa_e = interp_table(elyte["Conductivity [S.m-1]"], ce0)

    # Stoichiometries and initial concentrations
    x0 = fnum(neg["Minimum stoichiometry"])
    x100 = fnum(neg["Maximum stoichiometry"])
    y100 = fnum(pos["Minimum stoichiometry"])
    y0 = fnum(pos["Maximum stoichiometry"])

    cmax_n = fnum(neg["Maximum concentration [mol.m-3]"])
    cmax_p = fnum(pos["Maximum concentration [mol.m-3]"])

    x_init = x0 + (x100 - x0) * soc
    y_init = y0 + (y100 - y0) * soc

    scalars = {
        # Constants
        "Faraday constant [C.mol-1]": FARADAY,
        "Ideal gas constant [J.K-1.mol-1]": GAS_CONSTANT,
        # Cell-level values
        "Nominal cell capacity [A.h]": fnum(cell["Nominal cell capacity [A.h]"]),
        "Current function [A]": I_DC,
        "Lower voltage cut-off [V]": fnum(cell["Lower voltage cut-off [V]"]),
        "Upper voltage cut-off [V]": fnum(cell["Upper voltage cut-off [V]"]),
        # Required by PyBaMM ElectrodeSOH inside PyBOP grouping
        "Open-circuit voltage at 0% SOC [V]": fnum(
            user.get("Open-circuit voltage at 0% SOC [V]", cell["Lower voltage cut-off [V]"])
        ),
        "Open-circuit voltage at 100% SOC [V]": fnum(
            user.get("Open-circuit voltage at 100% SOC [V]", cell["Upper voltage cut-off [V]"])
        ),
        "Reference temperature [K]": T0,
        "Ambient temperature [K]": T0,
        "Initial temperature [K]": T0,
        "Initial SoC": soc,
        # Stored for bookkeeping; PyBOP grouping also computes stoichiometry limits
        # using the OCP limits above.
        "Minimum negative stoichiometry": x0,
        "Maximum negative stoichiometry": x100,
        "Minimum positive stoichiometry": y100,
        "Maximum positive stoichiometry": y0,
        "Contact resistance [Ohm]": CONTACT_R,
        "Electrode height [m]": electrode_height,
        "Electrode width [m]": electrode_width,
        # Electrolyte
        "Initial concentration in electrolyte [mol.m-3]": ce0,
        "Electrolyte diffusivity [m2.s-1]": De,
        "Electrolyte conductivity [S.m-1]": kappa_e,
        "Cation transference number": fnum(elyte["Cation transference number"]),
        # Negative electrode
        "Negative electrode thickness [m]": L_n,
        "Negative electrode porosity": eps_n,
        "Negative electrode active material volume fraction": alpha_n,
        "Negative electrode Bruggeman coefficient (electrolyte)": b_n,
        "Negative electrode Bruggeman coefficient (electrode)": 1.5,
        "Negative electrode conductivity [S.m-1]": fnum(neg["Conductivity [S.m-1]"]),
        "Negative particle radius [m]": fnum(neg["Particle radius [m]"]),
        "Negative particle diffusivity [m2.s-1]": fnum(neg["Diffusivity [m2.s-1]"]),
        "Maximum concentration in negative electrode [mol.m-3]": cmax_n,
        "Initial concentration in negative electrode [mol.m-3]": x_init * cmax_n,
        "Negative electrode double-layer capacity [F.m-2]": C_DL_N,
        "Negative electrode OCP entropic change [V.K-1]": fnum(
            neg.get("Entropic change coefficient [V.K-1]", 0.0)
        ),
        # Positive electrode
        "Positive electrode thickness [m]": L_p,
        "Positive electrode porosity": eps_p,
        "Positive electrode active material volume fraction": alpha_p,
        "Positive electrode Bruggeman coefficient (electrolyte)": b_p,
        "Positive electrode Bruggeman coefficient (electrode)": 1.5,
        "Positive electrode conductivity [S.m-1]": fnum(pos["Conductivity [S.m-1]"]),
        "Positive particle radius [m]": fnum(pos["Particle radius [m]"]),
        "Positive particle diffusivity [m2.s-1]": fnum(pos["Diffusivity [m2.s-1]"]),
        "Maximum concentration in positive electrode [mol.m-3]": cmax_p,
        "Initial concentration in positive electrode [mol.m-3]": y_init * cmax_p,
        "Positive electrode double-layer capacity [F.m-2]": C_DL_P,
        "Positive electrode OCP entropic change [V.K-1]": fnum(
            pos.get("Entropic change coefficient [V.K-1]", 0.0)
        ),
        # Separator
        "Separator thickness [m]": L_s,
        "Separator porosity": eps_s,
        "Separator Bruggeman coefficient (electrolyte)": b_s,
    }

    ocp_tables = {
        "Negative electrode OCP [V]": {
            "name": "U_n",
            "x": neg["OCP [V]"]["x"],
            "y": neg["OCP [V]"]["y"],
        },
        "Positive electrode OCP [V]": {
            "name": "U_p",
            "x": pos["OCP [V]"]["x"],
            "y": pos["OCP [V]"]["y"],
        },
    }

    metadata = {
        "format": "bpx-derived-physical-parameter-set-v1",
        "source_bpx_file": str(path),
        "SOC_used_to_set_initial_concentrations": soc,
        "effective_total_electrode_area [m2]": area_total,
        "single_pair_electrode_area [m2]": area_single_pair,
        "parallel_electrode_pairs": n_parallel,
        "note": (
            "This folder stores physical PyBaMM-style scalar parameters individually, "
            "plus OCP tables. A loader reconstructs pybamm.ParameterValues without pickle."
        ),
    }

    return scalars, ocp_tables, metadata


# =============================================================================
# SAVE / LOAD PHYSICAL PARAMETER SET
# =============================================================================

def save_physical_parameter_set(scalars, ocp_tables, metadata, folder):
    folder = Path(folder)
    folder.mkdir(exist_ok=True)

    package = {
        **metadata,
        "physical_scalar_parameters": json_safe(scalars),
        "ocp_tables": json_safe(ocp_tables),
    }

    json_path = folder / "physical_parameters_flexible.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(package, f, indent=2)

    save_table(scalars, folder / "physical_scalar_parameters.csv")

    try:
        shutil.copy2(BPX_FILE, folder / "source_bpx_schema_copy.json")
    except Exception:
        pass

    loader_code = r'''"""
Portable loader for BPX-derived physical PyBaMM parameters.
It avoids pickle/cloudpickle and avoids pybamm.ParameterValues.create_from_bpx().
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import numpy as np
import pybamm

THIS_DIR = Path(__file__).parent
PARAM_FILE = THIS_DIR / "physical_parameters_flexible.json"


def _ocp_fun(table, default_name):
    xs = np.asarray(table["x"], dtype=float)
    ys = np.asarray(table["y"], dtype=float)
    order = np.argsort(xs)
    xs = xs[order]
    ys = ys[order]
    name = table.get("name", default_name)

    def ocp(sto):
        if hasattr(pybamm, "Symbol") and isinstance(sto, pybamm.Symbol):
            return pybamm.Interpolant(xs, ys, sto, name=name, extrapolate=True)
        return np.interp(sto, xs, ys)

    return ocp


def load_package():
    with open(PARAM_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def get_parameter_dict(copy_parameters=True):
    package = load_package()
    params = dict(package["physical_scalar_parameters"])
    params["Negative electrode OCP [V]"] = _ocp_fun(
        package["ocp_tables"]["Negative electrode OCP [V]"], "U_n"
    )
    params["Positive electrode OCP [V]"] = _ocp_fun(
        package["ocp_tables"]["Positive electrode OCP [V]"], "U_p"
    )
    return copy.deepcopy(params) if copy_parameters else params


def get_parameter_values():
    return pybamm.ParameterValues(values=get_parameter_dict(copy_parameters=True))


def list_parameter_names():
    return sorted(get_parameter_dict(copy_parameters=False).keys())
'''
    (folder / "BPXPhysicalParameterSet.py").write_text(loader_code, encoding="utf-8")

    return json_path


def load_physical_parameter_values(folder):
    with open(Path(folder) / "physical_parameters_flexible.json", "r", encoding="utf-8") as f:
        package = json.load(f)
    return make_parameter_values(
        package["physical_scalar_parameters"],
        package["ocp_tables"],
    )


# =============================================================================
# GROUP USING PYBOP apply_parameter_grouping
# =============================================================================

def apply_pybop_grouping(parameter_values):
    """
    Call PyBOP's own grouping function.

    Important:
    - Do not hide KeyError/ValueError from the grouping call.
    - Only fall back when a function is genuinely not present.
    """

    # Preferred PyBOP 25.3 route
    fn = getattr(pybop.lithium_ion.GroupedSPMe, "apply_parameter_grouping", None)
    if fn is not None:
        print("Grouping with pybop.lithium_ion.GroupedSPMe.apply_parameter_grouping(...)")
        return fn(parameter_values)

    # Alternative import route, depending on PyBOP package layout
    try:
        from pybop.models.lithium_ion.basic_SPMe import GroupedSPMe
        fn = getattr(GroupedSPMe, "apply_parameter_grouping", None)
        if fn is not None:
            print("Grouping with basic_SPMe.GroupedSPMe.apply_parameter_grouping(...)")
            return fn(parameter_values)
    except ImportError:
        pass

    # Last fallback used by some PyBOP versions
    from pybop.models.lithium_ion.basic_SPMe import convert_physical_to_grouped_parameters
    print("Grouping with convert_physical_to_grouped_parameters(...)")
    return convert_physical_to_grouped_parameters(parameter_values)

def capacity_balance_positive_electrode(scalars, ocp_tables):
    """
    Adjust positive active material volume fraction only if PyBOP's strict
    measured-capacity equality check fails.
    """
    try:
        from pybamm.models.full_battery_models.lithium_ion.electrode_soh import (
            get_min_max_stoichiometries,
        )

        pv = make_parameter_values(scalars, ocp_tables)
        x0, x100, y100, y0 = get_min_max_stoichiometries(pv)
    except Exception:
        # Fallback to the initial-concentration implied range if min/max calculation fails.
        raise

    F = scalars["Faraday constant [C.mol-1]"]
    A = scalars["Electrode height [m]"] * scalars["Electrode width [m]"]

    alpha_n = scalars["Negative electrode active material volume fraction"]
    cmax_n = scalars["Maximum concentration in negative electrode [mol.m-3]"]
    L_n = scalars["Negative electrode thickness [m]"]

    cmax_p = scalars["Maximum concentration in positive electrode [mol.m-3]"]
    L_p = scalars["Positive electrode thickness [m]"]

    Q_meas_n = (x100 - x0) * F * alpha_n * cmax_n * L_n * A
    alpha_p_new = Q_meas_n / ((y0 - y100) * F * cmax_p * L_p * A)

    scalars = dict(scalars)
    old_alpha_p = scalars["Positive electrode active material volume fraction"]
    scalars["Positive electrode active material volume fraction"] = float(alpha_p_new)

    return scalars, {
        "balanced": True,
        "old_positive_active_material_volume_fraction": old_alpha_p,
        "new_positive_active_material_volume_fraction": float(alpha_p_new),
        "x0": float(x0),
        "x100": float(x100),
        "y100": float(y100),
        "y0": float(y0),
        "reason": "Adjusted so PyBOP apply_parameter_grouping capacity equality check can pass.",
    }


def save_grouped_parameter_set(grouped, ocp_tables, metadata, folder):
    folder = Path(folder)
    folder.mkdir(exist_ok=True)

    scalar_grouped = {
        key: value
        for key, value in grouped.items()
        if key not in ["Negative electrode OCP [V]", "Positive electrode OCP [V]"]
    }

    package = {
        **metadata,
        "grouped_spme_scalar_parameters": json_safe(scalar_grouped),
        "ocp_tables": json_safe(ocp_tables),
    }

    json_path = folder / "grouped_parameters_from_apply_grouping.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(package, f, indent=2)

    save_table(scalar_grouped, folder / "grouped_spme_scalar_parameters.csv")

    loader_code = r'''"""
Portable loader for grouped-SPMe parameters produced by PyBOP apply_parameter_grouping().
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import numpy as np
import pybamm

THIS_DIR = Path(__file__).parent
PARAM_FILE = THIS_DIR / "grouped_parameters_from_apply_grouping.json"


def _ocp_fun(table, default_name):
    xs = np.asarray(table["x"], dtype=float)
    ys = np.asarray(table["y"], dtype=float)
    order = np.argsort(xs)
    xs = xs[order]
    ys = ys[order]
    name = table.get("name", default_name)

    def ocp(sto):
        if hasattr(pybamm, "Symbol") and isinstance(sto, pybamm.Symbol):
            return pybamm.Interpolant(xs, ys, sto, name=name, extrapolate=True)
        return np.interp(sto, xs, ys)

    return ocp


def load_package():
    with open(PARAM_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def get_grouped_parameters(copy_parameters=True):
    package = load_package()
    params = dict(package["grouped_spme_scalar_parameters"])
    params["Negative electrode OCP [V]"] = _ocp_fun(
        package["ocp_tables"]["Negative electrode OCP [V]"], "U_n"
    )
    params["Positive electrode OCP [V]"] = _ocp_fun(
        package["ocp_tables"]["Positive electrode OCP [V]"], "U_p"
    )
    return copy.deepcopy(params) if copy_parameters else params


def get_scalar_parameters_only():
    return dict(load_package()["grouped_spme_scalar_parameters"])


def list_parameter_names():
    return sorted(get_grouped_parameters(copy_parameters=False).keys())
'''
    (folder / "BPXGroupedParameterSet.py").write_text(loader_code, encoding="utf-8")

    usage = f"""
Usage
=====

import sys
sys.path.insert(0, r"{folder.resolve()}")
from BPXGroupedParameterSet import get_grouped_parameters

grouped_parameters = get_grouped_parameters()
"""
    (folder / "README_usage.txt").write_text(usage, encoding="utf-8")

    return json_path


# =============================================================================
# MAIN
# =============================================================================

physical_scalars, ocp_tables, metadata = physical_parameter_set_from_bpx(BPX_FILE, SOC)

# First save the individual physical parameters.
physical_json = save_physical_parameter_set(
    physical_scalars,
    ocp_tables,
    metadata,
    PHYSICAL_DIR,
)

# Reload the saved physical ParameterValues and use PyBOP's own grouping function.
physical_pv = load_physical_parameter_values(PHYSICAL_DIR)

# Required by PyBaMM ElectrodeSOH called inside PyBOP grouping.
# Keep them explicit in case an older saved parameter folder is being reused.
for _key in [
    "Negative electrode OCP entropic change [V.K-1]",
    "Positive electrode OCP entropic change [V.K-1]",
]:
    if _key not in physical_pv:
        physical_pv.update({_key: 0.0}, check_already_exists=False)

balance_report = {"balanced": False}
try:
    grouped_parameters = apply_pybop_grouping(physical_pv)
except ValueError as err:
    if not BALANCE_CAPACITY_FOR_PYBOP_GROUPING or "measured capacity" not in str(err):
        raise

    print("PyBOP capacity equality check failed; applying positive-electrode balance.")
    physical_scalars, balance_report = capacity_balance_positive_electrode(
        physical_scalars,
        ocp_tables,
    )

    physical_json = save_physical_parameter_set(
        physical_scalars,
        ocp_tables,
        {**metadata, "capacity_balance_report": balance_report},
        PHYSICAL_DIR,
    )
    physical_pv = load_physical_parameter_values(PHYSICAL_DIR)
    for _key in [
        "Negative electrode OCP entropic change [V.K-1]",
        "Positive electrode OCP entropic change [V.K-1]",
    ]:
        if _key not in physical_pv:
            physical_pv.update({_key: 0.0}, check_already_exists=False)
    grouped_parameters = apply_pybop_grouping(physical_pv)

# Use the same OCP tables from the physical parameter set for portable grouped export.
grouped_json = save_grouped_parameter_set(
    grouped_parameters,
    ocp_tables,
    {
        "format": "grouped-spme-parameters-produced-by-pybop-apply-parameter-grouping-v1",
        "source_physical_parameter_set": str(PHYSICAL_DIR.resolve()),
        "source_bpx_file": str(BPX_FILE),
        "SOC": SOC,
        "capacity_balance_report": balance_report,
        "note": "Grouped parameters were created by PyBOP apply_parameter_grouping from a pybamm.ParameterValues object.",
    },
    GROUPED_DIR,
)

save_table(
    {k: v for k, v in grouped_parameters.items() if not callable(v)},
    GROUPED_DIR / "grouped_parameters_preview.csv",
    key_name="Grouped parameter",
)

print("\nDONE")
print("Physical parameter set saved to:", PHYSICAL_DIR.resolve())
print("Physical JSON:", physical_json)
print("Grouped parameter set saved to:", GROUPED_DIR.resolve())
print("Grouped JSON:", grouped_json)
print("Capacity balance report:", balance_report)


# %%
"""
02_run_grouped_spme_eis_from_apply_grouped_parameters.py

Loads the grouped-SPMe parameter set created by:
    01_export_physical_parameters_then_apply_grouping.py
and runs a single PyBOP GroupedSPMe EIS simulation.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pybop
from scipy.io import savemat


# =============================================================================
# SETTINGS
# =============================================================================

OUT = Path("bpx_grouped_spme_apply_grouping")
GROUPED_DIR = OUT / "grouped_parameter_set"
OUT.mkdir(exist_ok=True)

SOC = 0.5
FREQ = np.logspace(np.log10(2e-4), np.log10(1e5), 100)

MODEL_OPTIONS = {
    "surface form": "differential",
    "contact resistance": "true",
}

VAR_PTS = {
    "x_n": 100,
    "x_s": 20,
    "x_p": 100,
    "r_n": 100,
    "r_p": 100,
}


# =============================================================================
# FORCE-LOAD SAVED GROUPED PARAMETERS
# =============================================================================

if not GROUPED_DIR.exists():
    raise FileNotFoundError(
        "Grouped parameter set not found. Run "
        "01_export_physical_parameters_then_apply_grouping.py first.\n"
        f"Missing folder: {GROUPED_DIR.resolve()}"
    )

sys.path.insert(0, str(GROUPED_DIR.resolve()))

if "BPXGroupedParameterSet" in sys.modules:
    del sys.modules["BPXGroupedParameterSet"]

from BPXGroupedParameterSet import get_grouped_parameters, get_scalar_parameters_only

grouped_parameters = get_grouped_parameters()
scalar_parameters = get_scalar_parameters_only()

print("Loaded grouped parameters from:", GROUPED_DIR.resolve())
print("Number of grouped parameters:", len(grouped_parameters))

print("\nImportant grouped parameters:")
for key in [
    "Series resistance [Ohm]",
    "Measured cell capacity [A.s]",
    "Reference electrolyte capacity [A.s]",
    "Negative electrode charge transfer time scale [s]",
    "Positive electrode charge transfer time scale [s]",
    "Negative particle diffusion time scale [s]",
    "Positive particle diffusion time scale [s]",
    "Negative electrode relative porosity",
    "Positive electrode relative porosity",
]:
    print(f"{key}: {scalar_parameters.get(key, 'NOT FOUND')}")


# =============================================================================
# RUN GROUPED-SPMe EIS
# =============================================================================

model = pybop.lithium_ion.GroupedSPMe(
    parameter_set=grouped_parameters,
    eis=True,
    options=MODEL_OPTIONS,
    var_pts=VAR_PTS,
)
model.build(initial_state={"Initial SoC": SOC})

sim = model.simulateEIS(inputs=None, f_eval=FREQ)
Z = np.asarray(sim["Impedance"], dtype=complex)

# Capacitive Nyquist convention
if np.nanmedian(-np.imag(Z)) < 0:
    Z = np.conjugate(Z)


# =============================================================================
# SAVE RESULTS
# =============================================================================

df = pd.DataFrame(
    {
        "Frequency [Hz]": FREQ,
        "Z_real [Ohm]": Z.real,
        "Z_imag [Ohm]": Z.imag,
        "-Z_imag [Ohm]": -Z.imag,
        "Z_abs [Ohm]": np.abs(Z),
        "Phase [deg]": np.angle(Z, deg=True),
        "SOC": SOC,
    }
)

csv_path = OUT / "grouped_spme_eis_from_apply_grouping.csv"
mat_path = OUT / "grouped_spme_eis_from_apply_grouping.mat"
plot_path = OUT / "grouped_spme_eis_from_apply_grouping_nyquist.png"

df.to_csv(csv_path, index=False)
savemat(mat_path, {"Z": Z, "f": FREQ, "SOC": SOC})


# =============================================================================
# PLOT
# =============================================================================

fig, ax = plt.subplots(figsize=(6.5, 6.5))
ax.plot(Z.real, -Z.imag, "-o", markersize=4, linewidth=1.8)
ax.set_xlabel(r"$Z_r(\omega)$ [$\Omega$]")
ax.set_ylabel(r"$-Z_j(\omega)$ [$\Omega$]")
ax.set_title(f"Grouped-SPMe EIS from PyBOP apply_parameter_grouping\nSOC = {SOC:.2f}")
ax.grid(True)
ax.set_aspect("equal", adjustable="box")
fig.tight_layout()
fig.savefig(plot_path, dpi=300)
plt.show()
plt.close(fig)

print("\nDONE")
print("Saved CSV:", csv_path)
print("Saved MAT:", mat_path)
print("Saved plot:", plot_path)


# %%
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pybamm
from scipy.io import savemat

import pybop

SOC = 0.2

factor = 2
Nparams = 11
Nfreq = 60
fmin = 2e-4
fmax = 1e3

# Get grouped parameters
R0 = 0.01

parameter_set = pybop.ParameterSet.pybamm("Chen2020")
parameter_set["Electrolyte diffusivity [m2.s-1]"] = 1.769e-10
parameter_set["Electrolyte conductivity [S.m-1]"] = 1e16
parameter_set["Negative electrode conductivity [S.m-1]"] = 1e16
parameter_set["Positive electrode conductivity [S.m-1]"] = 1e16

# grouped_parameters = pybop.lithium_ion.GroupedSPMe.apply_parameter_grouping(
#     parameter_set
# )

from pybop.models.lithium_ion.basic_SPMe import convert_physical_to_grouped_parameters
grouped_parameters = convert_physical_to_grouped_parameters(parameter_set)

grouped_parameters["Series resistance [Ohm]"] = R0
model_options = {"surface form": "differential", "contact resistance": "true"}
var_pts = {"x_n": 100, "x_s": 20, "x_p": 100, "r_n": 100, "r_p": 100}

## Change parameters
parameter_name = "Negative particle diffusion time scale [s]"
param0 = grouped_parameters[parameter_name]
params = np.logspace(np.log10(param0 / factor), np.log10(param0 * factor), Nparams)

# Simulate impedance at these parameter values
frequencies = np.logspace(np.log10(fmin), np.log10(fmax), Nfreq)

impedances = 1j * np.zeros((Nfreq, Nparams))
for ii, param in enumerate(params):
    grouped_parameters[parameter_name] = param
    model = pybop.lithium_ion.GroupedSPMe(
        parameter_set=grouped_parameters,
        eis=True,
        options=model_options,
        var_pts=var_pts,
        solver=pybamm.CasadiSolver(),
    )
    model.build(
        initial_state={"Initial SoC": SOC},
    )
    simulation = model.simulateEIS(inputs=None, f_eval=frequencies)
    impedances[:, ii] = simulation["Impedance"]

fig, ax = plt.subplots()
for ii in range(Nparams):
    ax.plot(
        np.real(impedances[:, ii]),
        -np.imag(impedances[:, ii]),
    )
ax.set(xlabel=r"$Z_r(\omega)$ [$\Omega$]", ylabel=r"$-Z_j(\omega)$ [$\Omega$]")
ax.grid()
ax.set_aspect("equal", "box")
plt.show()

# mdic = {"Z": impedances, "f": frequencies, "name": parameter_name}
# current_dir = Path(__file__).parent
# save_path = current_dir / "Data" / "Z_SPMegrouped_taudn_20.mat"
# savemat(save_path, mdic)


# %%
from pathlib import Path
import sys
import importlib

import matplotlib.pyplot as plt
import numpy as np
import pybamm
import pybop
from scipy.io import savemat


# =============================================================================
# SETTINGS
# =============================================================================

SOC = 0.2

factor = 2
Nparams = 11
Nfreq = 60
fmin = 2e-4
fmax = 1e3

parameter_name = "Negative particle diffusion time scale [s]"

model_options = {
    "surface form": "differential",
    "contact resistance": "true",
}

var_pts = {
    "x_n": 100,
    "x_s": 20,
    "x_p": 100,
    "r_n": 100,
    "r_p": 100,
}

output_dir = Path(
    r"C:\Users\mugi_jo\Documents\DLR_PROJECTS\bpx_grouped_spme_apply_grouping"
)

grouped_parameter_dir = output_dir / "grouped_parameter_set"


# =============================================================================
# LOAD BPX-DERIVED GROUPED PARAMETERS
# =============================================================================

if not grouped_parameter_dir.exists():
    raise FileNotFoundError(
        "Grouped parameter folder not found:\n"
        f"{grouped_parameter_dir}\n\n"
        "Run the exporter first:\n"
        "01_export_physical_parameters_then_apply_grouping_v4_entropic_fix.py"
    )

sys.path.insert(0, str(grouped_parameter_dir.resolve()))

# Force reload to avoid stale notebook parameters
if "BPXGroupedParameterSet" in sys.modules:
    del sys.modules["BPXGroupedParameterSet"]

from BPXGroupedParameterSet import get_grouped_parameters

grouped_parameters_base = get_grouped_parameters()

print("Loaded BPX-derived grouped parameters from:")
print(grouped_parameter_dir)
print("Number of parameters:", len(grouped_parameters_base))


# =============================================================================
# CHECK PARAMETER TO VARY
# =============================================================================

if parameter_name not in grouped_parameters_base:
    print("\nAvailable grouped parameters:")
    for key in sorted(grouped_parameters_base.keys()):
        print("  ", key)

    raise KeyError(f"Parameter not found: {parameter_name}")

param0 = float(grouped_parameters_base[parameter_name])

params = np.logspace(
    np.log10(param0 / factor),
    np.log10(param0 * factor),
    Nparams,
)

frequencies = np.logspace(
    np.log10(fmin),
    np.log10(fmax),
    Nfreq,
)

print("\nParameter varied:")
print(parameter_name)
print("Base value:", param0)


# =============================================================================
# SIMULATE IMPEDANCE AT THESE PARAMETER VALUES
# =============================================================================

impedances = np.zeros((Nfreq, Nparams), dtype=complex)

for ii, param in enumerate(params):
    print(f"{ii + 1}/{Nparams}: {parameter_name} = {param:.6e}")

    grouped_parameters = dict(grouped_parameters_base)
    grouped_parameters[parameter_name] = float(param)

    model = pybop.lithium_ion.GroupedSPMe(
        parameter_set=grouped_parameters,
        eis=True,
        options=model_options,
        var_pts=var_pts,
        solver=pybamm.CasadiSolver(),
    )

    model.build(
        initial_state={"Initial SoC": SOC},
    )

    simulation = model.simulateEIS(
        inputs=None,
        f_eval=frequencies,
    )

    Z = np.asarray(simulation["Impedance"], dtype=complex)

    # Capacitive Nyquist convention
    if np.nanmedian(-np.imag(Z)) < 0:
        Z = np.conjugate(Z)

    impedances[:, ii] = Z


# =============================================================================
# PLOT NYQUIST
# =============================================================================

fig, ax = plt.subplots(figsize=(6.5, 6.5))

for ii, param in enumerate(params):
    ax.plot(
        np.real(impedances[:, ii]),
        -np.imag(impedances[:, ii]),
        linewidth=1.6,
        label=f"{param:.2e}",
    )

ax.set_xlabel(r"$Z_r(\omega)$ [$\Omega$]")
ax.set_ylabel(r"$-Z_j(\omega)$ [$\Omega$]")
ax.set_title(f"BPX GroupedSPMe sensitivity\n{parameter_name}, SOC = {SOC}")
ax.grid(True)
ax.set_aspect("equal", adjustable="box")
ax.legend(fontsize=7)

fig.tight_layout()
plt.show()


# =============================================================================
# SAVE RESULTS
# =============================================================================

# save_dir = output_dir / "sensitivity_results"
# save_dir.mkdir(exist_ok=True)

# mdic = {
#     "Z": impedances,
#     "f": frequencies,
#     "params": params,
#     "name": parameter_name,
#     "SOC": SOC,
# }

# save_path = save_dir / "Z_SPMegrouped_taudn_20_BPX.mat"
# savemat(save_path, mdic)

# fig_path = save_dir / "Z_SPMegrouped_taudn_20_BPX.png"
# fig.savefig(fig_path, dpi=300)

# print("\nSaved MAT file to:")
# print(save_path)

# print("Saved figure to:")
# print(fig_path)

# %%
"""
01_export_physical_parameters_then_apply_grouping.py

Purpose
-------
1. Read the BPX JSON directly, without pybamm.ParameterValues.create_from_bpx().
2. Save the BPX-derived physical PyBaMM parameters individually as a portable
   JSON parameter set.
3. Rebuild a pybamm.ParameterValues object from that portable parameter set.
4. Group the parameters using PyBOP's own apply_parameter_grouping() function.
5. Save the grouped-SPMe parameters as a second portable JSON parameter set.

V7 fix: adds Thermodynamic factor plus BPX-derived exchange-current-density functions required by PyBOP/PyBaMM SPM, SPMe and DFN.

This avoids pickle/cloudpickle and avoids BPX validator/schema issues.
"""

from __future__ import annotations

import copy
import json
import math
import shutil
from pathlib import Path

import numpy as np
import pandas as pd
import pybamm
import pybop


# =============================================================================
# USER SETTINGS
# =============================================================================

BPX_FILE = Path(
    r"C:\Users\mugi_jo\Downloads\hydr0_graphite-lnmo_schmitt-2026_validation.bpx_1_patched_for_current_bpx.json"
)

OUT = Path("bpx_grouped_spme_apply_grouping")
PHYSICAL_DIR = OUT / "physical_parameter_set"
GROUPED_DIR = OUT / "grouped_parameter_set"

OUT.mkdir(exist_ok=True)
PHYSICAL_DIR.mkdir(exist_ok=True)
GROUPED_DIR.mkdir(exist_ok=True)

SOC = 0.5

# Supplemental values not present in your BPX schema but required by PyBOP grouping.
C_DL_N = 0.02       # F m-2
C_DL_P = 0.092      # F m-2
CONTACT_R = 0.0     # Ohm
I_DC = 0.0          # A, equilibrium EIS

FARADAY = 96485.33212
GAS_CONSTANT = 8.31446261815324

# If PyBOP raises because Q_meas_n and Q_meas_p differ slightly, rebalance the
# positive active-material volume fraction so apply_parameter_grouping can run.
BALANCE_CAPACITY_FOR_PYBOP_GROUPING = True


# =============================================================================
# SMALL HELPERS
# =============================================================================

def fnum(x, default=None):
    if x is None:
        if default is None:
            raise ValueError("Missing required numeric value")
        return float(default)
    return float(x)


def json_safe(x):
    if isinstance(x, (np.integer, int)):
        return int(x)
    if isinstance(x, (np.floating, float)):
        x = float(x)
        return x if math.isfinite(x) else None
    if isinstance(x, np.ndarray):
        return [json_safe(v) for v in x.tolist()]
    if isinstance(x, (list, tuple)):
        return [json_safe(v) for v in x]
    if isinstance(x, dict):
        return {str(k): json_safe(v) for k, v in x.items()}
    return x


def interp_table(table, x):
    xs = np.asarray(table["x"], dtype=float)
    ys = np.asarray(table["y"], dtype=float)
    order = np.argsort(xs)
    return float(np.interp(float(x), xs[order], ys[order]))


def bruggeman_from_transport_efficiency(eps, transport_efficiency):
    eps = float(eps)
    transport_efficiency = float(transport_efficiency)
    return float(math.log(transport_efficiency) / math.log(eps))


def state_initial_conditions(bpx):
    state = bpx.get("State", {})
    return (
        state.get("Initial conditions")
        or state.get("InitialConditions")
        or state.get("InitialConditions", {})
        or {}
    )


def ocp_fun_from_table(table, name):
    xs = np.asarray(table["x"], dtype=float)
    ys = np.asarray(table["y"], dtype=float)
    order = np.argsort(xs)
    xs = xs[order]
    ys = ys[order]

    def ocp(sto):
        if hasattr(pybamm, "Symbol") and isinstance(sto, pybamm.Symbol):
            return pybamm.Interpolant(xs, ys, sto, name=name, extrapolate=True)
        return np.interp(sto, xs, ys)

    return ocp


def constant_exchange_current_density(value):
    """Return a PyBaMM-compatible constant j0(c_e, c_s_surf, c_s_max, T)."""
    value = float(value)

    def j0(c_e, c_s_surf, c_s_max, T):
        if any(hasattr(pybamm, "Symbol") and isinstance(v, pybamm.Symbol) for v in [c_e, c_s_surf, c_s_max, T]):
            return pybamm.Scalar(value)
        return value

    return j0


def make_parameter_values(scalars, ocp_tables):
    """Build pybamm.ParameterValues from saved scalar parameters + OCP tables + j0 functions."""
    params = dict(scalars)
    params["Negative electrode OCP [V]"] = ocp_fun_from_table(
        ocp_tables["Negative electrode OCP [V]"], "U_n"
    )
    params["Positive electrode OCP [V]"] = ocp_fun_from_table(
        ocp_tables["Positive electrode OCP [V]"], "U_p"
    )

    # PyBaMM SPM/SPMe/DFN require Thermodynamic factor in electrolyte-potential terms.
    params.setdefault("Thermodynamic factor", 1.0)

    # PyBOP/PyBaMM SPM, SPMe and DFN require exchange-current-density functions.
    # BPX stores reaction-rate constants, so here we use the robust constant-j0
    # mapping j0_ref = F * k_BPX used for the BPX-derived physical model.
    if "Negative electrode exchange-current density [A.m-2]" not in params:
        params["Negative electrode exchange-current density [A.m-2]"] = constant_exchange_current_density(
            params["Negative electrode exchange-current density reference [A.m-2]"]
        )
    if "Positive electrode exchange-current density [A.m-2]" not in params:
        params["Positive electrode exchange-current density [A.m-2]"] = constant_exchange_current_density(
            params["Positive electrode exchange-current density reference [A.m-2]"]
        )

    return pybamm.ParameterValues(values=params)


def save_table(d, path, key_name="Parameter"):
    rows = []
    for key, value in sorted(d.items()):
        rows.append({key_name: key, "Type": type(value).__name__, "Value": repr(value)[:500]})
    pd.DataFrame(rows).to_csv(path, index=False)


# =============================================================================
# BPX JSON -> INDIVIDUAL PHYSICAL PYBAMM PARAMETERS
# =============================================================================

def physical_parameter_set_from_bpx(path, soc=0.5):
    with open(path, "r", encoding="utf-8") as f:
        bpx = json.load(f)

    p = bpx["Parameterisation"]
    cell = p["Cell"]
    elyte = p["Electrolyte"]
    neg = p["Negative electrode"]
    pos = p["Positive electrode"]
    sep = p["Separator"]
    user = p.get("User-defined", {})
    ic = state_initial_conditions(bpx)

    # Effective total electrode area used by PyBOP grouping:
    # A = Electrode height [m] * Electrode width [m]
    n_parallel = fnum(cell.get("Number of electrode pairs connected in parallel to make a cell", 1.0))
    area_single_pair = fnum(cell["Electrode area [m2]"])
    area_total = area_single_pair * n_parallel

    # Store the effective area as height * width, because PyBOP grouping expects these two names.
    electrode_height = area_total
    electrode_width = 1.0

    # Geometry and fractions
    L_n = fnum(neg["Thickness [m]"])
    L_s = fnum(sep["Thickness [m]"])
    L_p = fnum(pos["Thickness [m]"])

    eps_n = fnum(neg["Porosity"])
    eps_s = fnum(sep["Porosity"])
    eps_p = fnum(pos["Porosity"])

    alpha_n = fnum(user.get("Negative electrode active material volume fraction", 1.0 - eps_n))
    alpha_p = fnum(user.get("Positive electrode active material volume fraction", 1.0 - eps_p))

    b_n = bruggeman_from_transport_efficiency(eps_n, neg["Transport efficiency"])
    b_s = bruggeman_from_transport_efficiency(eps_s, sep["Transport efficiency"])
    b_p = bruggeman_from_transport_efficiency(eps_p, pos["Transport efficiency"])

    # Initial conditions
    ce0 = fnum(
        ic.get("Initial electrolyte concentration [mol.m-3]")
        or ic.get("Initial concentration in electrolyte [mol.m-3]")
        or ic.get("Electrolyte initial concentration [mol.m-3]"),
        default=1000.0,
    )
    T0 = fnum(
        ic.get("Initial temperature [K]")
        or cell.get("Reference temperature [K]"),
        default=298.15,
    )

    # Electrolyte tables are scalarised at ce0, because PyBOP grouping expects scalar De and kappa_e.
    De = interp_table(elyte["Diffusivity [m2.s-1]"], ce0)
    kappa_e = interp_table(elyte["Conductivity [S.m-1]"], ce0)

    # Stoichiometries and initial concentrations
    x0 = fnum(neg["Minimum stoichiometry"])
    x100 = fnum(neg["Maximum stoichiometry"])
    y100 = fnum(pos["Minimum stoichiometry"])
    y0 = fnum(pos["Maximum stoichiometry"])

    cmax_n = fnum(neg["Maximum concentration [mol.m-3]"])
    cmax_p = fnum(pos["Maximum concentration [mol.m-3]"])

    x_init = x0 + (x100 - x0) * soc
    y_init = y0 + (y100 - y0) * soc

    scalars = {
        # Constants
        "Faraday constant [C.mol-1]": FARADAY,
        "Ideal gas constant [J.K-1.mol-1]": GAS_CONSTANT,
        # Cell-level values
        "Nominal cell capacity [A.h]": fnum(cell["Nominal cell capacity [A.h]"]),
        "Current function [A]": I_DC,
        "Lower voltage cut-off [V]": fnum(cell["Lower voltage cut-off [V]"]),
        "Upper voltage cut-off [V]": fnum(cell["Upper voltage cut-off [V]"]),
        # Required by PyBaMM ElectrodeSOH inside PyBOP grouping
        "Open-circuit voltage at 0% SOC [V]": fnum(
            user.get("Open-circuit voltage at 0% SOC [V]", cell["Lower voltage cut-off [V]"])
        ),
        "Open-circuit voltage at 100% SOC [V]": fnum(
            user.get("Open-circuit voltage at 100% SOC [V]", cell["Upper voltage cut-off [V]"])
        ),
        "Reference temperature [K]": T0,
        "Ambient temperature [K]": T0,
        "Initial temperature [K]": T0,
        "Initial SoC": soc,
        # Stored for bookkeeping; PyBOP grouping also computes stoichiometry limits
        # using the OCP limits above.
        "Minimum negative stoichiometry": x0,
        "Maximum negative stoichiometry": x100,
        "Minimum positive stoichiometry": y100,
        "Maximum positive stoichiometry": y0,
        "Contact resistance [Ohm]": CONTACT_R,
        # PyBaMM/PyBOP SPM, SPMe and DFN use this name to convert current to current density.
        # BPX stores the corresponding value as "Number of electrode pairs connected in parallel to make a cell".
        "Number of electrodes connected in parallel to make a cell": n_parallel,
        # Keep the BPX wording too, for bookkeeping and compatibility with scripts that read it directly.
        "Number of electrode pairs connected in parallel to make a cell": n_parallel,
        "Number of cells connected in series to make a battery": 1.0,
        "Electrode height [m]": electrode_height,
        "Electrode width [m]": electrode_width,
        # Electrolyte
        "Initial concentration in electrolyte [mol.m-3]": ce0,
        "Electrolyte diffusivity [m2.s-1]": De,
        "Electrolyte conductivity [S.m-1]": kappa_e,
        # Required by PyBaMM electrolyte-potential terms.
        # BPX does not always include this, so use 1.0 as ideal-solution default.
        "Thermodynamic factor": fnum(elyte.get("Thermodynamic factor"), default=1.0),
        "Cation transference number": fnum(elyte["Cation transference number"]),
        # Negative electrode
        "Negative electrode thickness [m]": L_n,
        "Negative electrode porosity": eps_n,
        "Negative electrode active material volume fraction": alpha_n,
        "Negative electrode Bruggeman coefficient (electrolyte)": b_n,
        "Negative electrode Bruggeman coefficient (electrode)": 1.5,
        "Negative electrode conductivity [S.m-1]": fnum(neg["Conductivity [S.m-1]"]),
        "Negative particle radius [m]": fnum(neg["Particle radius [m]"]),
        "Negative particle diffusivity [m2.s-1]": fnum(neg["Diffusivity [m2.s-1]"]),
        "Maximum concentration in negative electrode [mol.m-3]": cmax_n,
        "Initial concentration in negative electrode [mol.m-3]": x_init * cmax_n,
        "Negative electrode double-layer capacity [F.m-2]": C_DL_N,
        "Negative electrode OCP entropic change [V.K-1]": fnum(
            neg.get("Entropic change coefficient [V.K-1]", 0.0)
        ),
        # BPX reaction-rate constant and constant exchange-current-density reference.
        # The actual PyBaMM parameter below is reconstructed as a function by the loader.
        "Negative electrode reaction rate constant [mol.m-2.s-1]": fnum(
            neg.get("Reaction rate constant [mol.m-2.s-1]", 1.0e-6)
        ),
        "Negative electrode exchange-current density reference [A.m-2]": FARADAY * fnum(
            neg.get("Reaction rate constant [mol.m-2.s-1]", 1.0e-6)
        ),
        # Positive electrode
        "Positive electrode thickness [m]": L_p,
        "Positive electrode porosity": eps_p,
        "Positive electrode active material volume fraction": alpha_p,
        "Positive electrode Bruggeman coefficient (electrolyte)": b_p,
        "Positive electrode Bruggeman coefficient (electrode)": 1.5,
        "Positive electrode conductivity [S.m-1]": fnum(pos["Conductivity [S.m-1]"]),
        "Positive particle radius [m]": fnum(pos["Particle radius [m]"]),
        "Positive particle diffusivity [m2.s-1]": fnum(pos["Diffusivity [m2.s-1]"]),
        "Maximum concentration in positive electrode [mol.m-3]": cmax_p,
        "Initial concentration in positive electrode [mol.m-3]": y_init * cmax_p,
        "Positive electrode double-layer capacity [F.m-2]": C_DL_P,
        "Positive electrode OCP entropic change [V.K-1]": fnum(
            pos.get("Entropic change coefficient [V.K-1]", 0.0)
        ),
        # BPX reaction-rate constant and constant exchange-current-density reference.
        # The actual PyBaMM parameter below is reconstructed as a function by the loader.
        "Positive electrode reaction rate constant [mol.m-2.s-1]": fnum(
            pos.get("Reaction rate constant [mol.m-2.s-1]", 1.0e-6)
        ),
        "Positive electrode exchange-current density reference [A.m-2]": FARADAY * fnum(
            pos.get("Reaction rate constant [mol.m-2.s-1]", 1.0e-6)
        ),
        # Separator
        "Separator thickness [m]": L_s,
        "Separator porosity": eps_s,
        "Separator Bruggeman coefficient (electrolyte)": b_s,
    }

    ocp_tables = {
        "Negative electrode OCP [V]": {
            "name": "U_n",
            "x": neg["OCP [V]"]["x"],
            "y": neg["OCP [V]"]["y"],
        },
        "Positive electrode OCP [V]": {
            "name": "U_p",
            "x": pos["OCP [V]"]["x"],
            "y": pos["OCP [V]"]["y"],
        },
    }

    metadata = {
        "format": "bpx-derived-physical-parameter-set-v1",
        "source_bpx_file": str(path),
        "SOC_used_to_set_initial_concentrations": soc,
        "effective_total_electrode_area [m2]": area_total,
        "single_pair_electrode_area [m2]": area_single_pair,
        "parallel_electrode_pairs": n_parallel,
        "note": (
            "This folder stores physical PyBaMM-style scalar parameters individually, "
            "plus OCP tables. A loader reconstructs pybamm.ParameterValues without pickle."
        ),
    }

    return scalars, ocp_tables, metadata


# =============================================================================
# SAVE / LOAD PHYSICAL PARAMETER SET
# =============================================================================

def save_physical_parameter_set(scalars, ocp_tables, metadata, folder):
    folder = Path(folder)
    folder.mkdir(exist_ok=True)

    package = {
        **metadata,
        "physical_scalar_parameters": json_safe(scalars),
        "ocp_tables": json_safe(ocp_tables),
    }

    json_path = folder / "physical_parameters_flexible.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(package, f, indent=2)

    save_table(scalars, folder / "physical_scalar_parameters.csv")

    try:
        shutil.copy2(BPX_FILE, folder / "source_bpx_schema_copy.json")
    except Exception:
        pass

    loader_code = r'''"""
Portable loader for BPX-derived physical PyBaMM parameters.
It avoids pickle/cloudpickle and avoids pybamm.ParameterValues.create_from_bpx().
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import numpy as np
import pybamm

THIS_DIR = Path(__file__).parent
PARAM_FILE = THIS_DIR / "physical_parameters_flexible.json"


def _ocp_fun(table, default_name):
    xs = np.asarray(table["x"], dtype=float)
    ys = np.asarray(table["y"], dtype=float)
    order = np.argsort(xs)
    xs = xs[order]
    ys = ys[order]
    name = table.get("name", default_name)

    def ocp(sto):
        if hasattr(pybamm, "Symbol") and isinstance(sto, pybamm.Symbol):
            return pybamm.Interpolant(xs, ys, sto, name=name, extrapolate=True)
        return np.interp(sto, xs, ys)

    return ocp


def _constant_exchange_current_density(value):
    value = float(value)

    def j0(c_e, c_s_surf, c_s_max, T):
        if any(hasattr(pybamm, "Symbol") and isinstance(v, pybamm.Symbol) for v in [c_e, c_s_surf, c_s_max, T]):
            return pybamm.Scalar(value)
        return value

    return j0


def load_package():
    with open(PARAM_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def get_parameter_dict(copy_parameters=True):
    package = load_package()
    params = dict(package["physical_scalar_parameters"])
    params["Negative electrode OCP [V]"] = _ocp_fun(
        package["ocp_tables"]["Negative electrode OCP [V]"], "U_n"
    )
    params["Positive electrode OCP [V]"] = _ocp_fun(
        package["ocp_tables"]["Positive electrode OCP [V]"], "U_p"
    )
    params.setdefault("Thermodynamic factor", 1.0)
    params["Negative electrode exchange-current density [A.m-2]"] = _constant_exchange_current_density(
        params["Negative electrode exchange-current density reference [A.m-2]"]
    )
    params["Positive electrode exchange-current density [A.m-2]"] = _constant_exchange_current_density(
        params["Positive electrode exchange-current density reference [A.m-2]"]
    )
    return copy.deepcopy(params) if copy_parameters else params


def get_parameter_values():
    return pybamm.ParameterValues(values=get_parameter_dict(copy_parameters=True))


def list_parameter_names():
    return sorted(get_parameter_dict(copy_parameters=False).keys())
'''
    (folder / "BPXPhysicalParameterSet.py").write_text(loader_code, encoding="utf-8")

    return json_path


def load_physical_parameter_values(folder):
    with open(Path(folder) / "physical_parameters_flexible.json", "r", encoding="utf-8") as f:
        package = json.load(f)
    return make_parameter_values(
        package["physical_scalar_parameters"],
        package["ocp_tables"],
    )


# =============================================================================
# GROUP USING PYBOP apply_parameter_grouping
# =============================================================================

def apply_pybop_grouping(parameter_values):
    """
    Call PyBOP's own grouping function.

    Important:
    - Do not hide KeyError/ValueError from the grouping call.
    - Only fall back when a function is genuinely not present.
    """

    # Preferred PyBOP 25.3 route
    fn = getattr(pybop.lithium_ion.GroupedSPMe, "apply_parameter_grouping", None)
    if fn is not None:
        print("Grouping with pybop.lithium_ion.GroupedSPMe.apply_parameter_grouping(...)")
        return fn(parameter_values)

    # Alternative import route, depending on PyBOP package layout
    try:
        from pybop.models.lithium_ion.basic_SPMe import GroupedSPMe
        fn = getattr(GroupedSPMe, "apply_parameter_grouping", None)
        if fn is not None:
            print("Grouping with basic_SPMe.GroupedSPMe.apply_parameter_grouping(...)")
            return fn(parameter_values)
    except ImportError:
        pass

    # Last fallback used by some PyBOP versions
    from pybop.models.lithium_ion.basic_SPMe import convert_physical_to_grouped_parameters
    print("Grouping with convert_physical_to_grouped_parameters(...)")
    return convert_physical_to_grouped_parameters(parameter_values)

def capacity_balance_positive_electrode(scalars, ocp_tables):
    """
    Adjust positive active material volume fraction only if PyBOP's strict
    measured-capacity equality check fails.
    """
    try:
        from pybamm.models.full_battery_models.lithium_ion.electrode_soh import (
            get_min_max_stoichiometries,
        )

        pv = make_parameter_values(scalars, ocp_tables)
        x0, x100, y100, y0 = get_min_max_stoichiometries(pv)
    except Exception:
        # Fallback to the initial-concentration implied range if min/max calculation fails.
        raise

    F = scalars["Faraday constant [C.mol-1]"]
    A = scalars["Electrode height [m]"] * scalars["Electrode width [m]"]

    alpha_n = scalars["Negative electrode active material volume fraction"]
    cmax_n = scalars["Maximum concentration in negative electrode [mol.m-3]"]
    L_n = scalars["Negative electrode thickness [m]"]

    cmax_p = scalars["Maximum concentration in positive electrode [mol.m-3]"]
    L_p = scalars["Positive electrode thickness [m]"]

    Q_meas_n = (x100 - x0) * F * alpha_n * cmax_n * L_n * A
    alpha_p_new = Q_meas_n / ((y0 - y100) * F * cmax_p * L_p * A)

    scalars = dict(scalars)
    old_alpha_p = scalars["Positive electrode active material volume fraction"]
    scalars["Positive electrode active material volume fraction"] = float(alpha_p_new)

    return scalars, {
        "balanced": True,
        "old_positive_active_material_volume_fraction": old_alpha_p,
        "new_positive_active_material_volume_fraction": float(alpha_p_new),
        "x0": float(x0),
        "x100": float(x100),
        "y100": float(y100),
        "y0": float(y0),
        "reason": "Adjusted so PyBOP apply_parameter_grouping capacity equality check can pass.",
    }


def save_grouped_parameter_set(grouped, ocp_tables, metadata, folder):
    folder = Path(folder)
    folder.mkdir(exist_ok=True)

    scalar_grouped = {
        key: value
        for key, value in grouped.items()
        if key not in ["Negative electrode OCP [V]", "Positive electrode OCP [V]"]
    }

    package = {
        **metadata,
        "grouped_spme_scalar_parameters": json_safe(scalar_grouped),
        "ocp_tables": json_safe(ocp_tables),
    }

    json_path = folder / "grouped_parameters_from_apply_grouping.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(package, f, indent=2)

    save_table(scalar_grouped, folder / "grouped_spme_scalar_parameters.csv")

    loader_code = r'''"""
Portable loader for grouped-SPMe parameters produced by PyBOP apply_parameter_grouping().
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import numpy as np
import pybamm

THIS_DIR = Path(__file__).parent
PARAM_FILE = THIS_DIR / "grouped_parameters_from_apply_grouping.json"


def _ocp_fun(table, default_name):
    xs = np.asarray(table["x"], dtype=float)
    ys = np.asarray(table["y"], dtype=float)
    order = np.argsort(xs)
    xs = xs[order]
    ys = ys[order]
    name = table.get("name", default_name)

    def ocp(sto):
        if hasattr(pybamm, "Symbol") and isinstance(sto, pybamm.Symbol):
            return pybamm.Interpolant(xs, ys, sto, name=name, extrapolate=True)
        return np.interp(sto, xs, ys)

    return ocp


def _constant_exchange_current_density(value):
    value = float(value)

    def j0(c_e, c_s_surf, c_s_max, T):
        if any(hasattr(pybamm, "Symbol") and isinstance(v, pybamm.Symbol) for v in [c_e, c_s_surf, c_s_max, T]):
            return pybamm.Scalar(value)
        return value

    return j0


def load_package():
    with open(PARAM_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def get_grouped_parameters(copy_parameters=True):
    package = load_package()
    params = dict(package["grouped_spme_scalar_parameters"])
    params["Negative electrode OCP [V]"] = _ocp_fun(
        package["ocp_tables"]["Negative electrode OCP [V]"], "U_n"
    )
    params["Positive electrode OCP [V]"] = _ocp_fun(
        package["ocp_tables"]["Positive electrode OCP [V]"], "U_p"
    )
    params.setdefault("Thermodynamic factor", 1.0)
    params["Negative electrode exchange-current density [A.m-2]"] = _constant_exchange_current_density(
        params["Negative electrode exchange-current density reference [A.m-2]"]
    )
    params["Positive electrode exchange-current density [A.m-2]"] = _constant_exchange_current_density(
        params["Positive electrode exchange-current density reference [A.m-2]"]
    )
    return copy.deepcopy(params) if copy_parameters else params


def get_scalar_parameters_only():
    return dict(load_package()["grouped_spme_scalar_parameters"])


def list_parameter_names():
    return sorted(get_grouped_parameters(copy_parameters=False).keys())
'''
    (folder / "BPXGroupedParameterSet.py").write_text(loader_code, encoding="utf-8")

    usage = f"""
Usage
=====

import sys
sys.path.insert(0, r"{folder.resolve()}")
from BPXGroupedParameterSet import get_grouped_parameters

grouped_parameters = get_grouped_parameters()
"""
    (folder / "README_usage.txt").write_text(usage, encoding="utf-8")

    return json_path


# =============================================================================
# MAIN
# =============================================================================

physical_scalars, ocp_tables, metadata = physical_parameter_set_from_bpx(BPX_FILE, SOC)

# First save the individual physical parameters.
physical_json = save_physical_parameter_set(
    physical_scalars,
    ocp_tables,
    metadata,
    PHYSICAL_DIR,
)

# Reload the saved physical ParameterValues and use PyBOP's own grouping function.
physical_pv = load_physical_parameter_values(PHYSICAL_DIR)

# Required by PyBaMM ElectrodeSOH called inside PyBOP grouping.
# Keep them explicit in case an older saved parameter folder is being reused.
for _key in [
    "Negative electrode OCP entropic change [V.K-1]",
    "Positive electrode OCP entropic change [V.K-1]",
]:
    if _key not in physical_pv:
        physical_pv.update({_key: 0.0}, check_already_exists=False)

balance_report = {"balanced": False}
try:
    grouped_parameters = apply_pybop_grouping(physical_pv)
except ValueError as err:
    if not BALANCE_CAPACITY_FOR_PYBOP_GROUPING or "measured capacity" not in str(err):
        raise

    print("PyBOP capacity equality check failed; applying positive-electrode balance.")
    physical_scalars, balance_report = capacity_balance_positive_electrode(
        physical_scalars,
        ocp_tables,
    )

    physical_json = save_physical_parameter_set(
        physical_scalars,
        ocp_tables,
        {**metadata, "capacity_balance_report": balance_report},
        PHYSICAL_DIR,
    )
    physical_pv = load_physical_parameter_values(PHYSICAL_DIR)
    for _key in [
        "Negative electrode OCP entropic change [V.K-1]",
        "Positive electrode OCP entropic change [V.K-1]",
    ]:
        if _key not in physical_pv:
            physical_pv.update({_key: 0.0}, check_already_exists=False)
    grouped_parameters = apply_pybop_grouping(physical_pv)

# Use the same OCP tables from the physical parameter set for portable grouped export.
grouped_json = save_grouped_parameter_set(
    grouped_parameters,
    ocp_tables,
    {
        "format": "grouped-spme-parameters-produced-by-pybop-apply-parameter-grouping-v1",
        "source_physical_parameter_set": str(PHYSICAL_DIR.resolve()),
        "source_bpx_file": str(BPX_FILE),
        "SOC": SOC,
        "capacity_balance_report": balance_report,
        "note": "Grouped parameters were created by PyBOP apply_parameter_grouping from a pybamm.ParameterValues object.",
    },
    GROUPED_DIR,
)

save_table(
    {k: v for k, v in grouped_parameters.items() if not callable(v)},
    GROUPED_DIR / "grouped_parameters_preview.csv",
    key_name="Grouped parameter",
)

print("\nDONE")
print("Physical parameter set saved to:", PHYSICAL_DIR.resolve())
print("Physical JSON:", physical_json)
print("Grouped parameter set saved to:", GROUPED_DIR.resolve())
print("Grouped JSON:", grouped_json)
print("Capacity balance report:", balance_report)


# %%
from pathlib import Path
import sys
import json

import matplotlib.pyplot as plt
import numpy as np
import pybamm
from scipy.io import savemat
import pybop

# =============================================================================
# SETTINGS
# =============================================================================

Nfreq = 60
SOC = 0.5
fmin = 2e-4
fmax = 1e3

frequencies = np.logspace(np.log10(fmin), np.log10(fmax), Nfreq)

model_names = ["SPM", "SPMe", "DFN"]
impedances = np.zeros((Nfreq, len(model_names)), dtype=complex)

output_dir = Path(
    r"C:\Users\mugi_jo\Documents\DLR_PROJECTS\bpx_grouped_spme_apply_grouping"
)
physical_parameter_dir = output_dir / "physical_parameter_set"
save_dir = output_dir / "model_comparison_results"
save_dir.mkdir(exist_ok=True)

model_options = {
    "surface form": "differential",
    "contact resistance": "true",
}

var_pts = {
    "x_n": 100,
    "x_s": 20,
    "x_p": 100,
    "r_n": 100,
    "r_p": 100,
}

solver = pybamm.CasadiSolver()

# =============================================================================
# HELPERS
# =============================================================================

def _ocp_fun(table, default_name):
    xs = np.asarray(table["x"], dtype=float)
    ys = np.asarray(table["y"], dtype=float)
    order = np.argsort(xs)
    xs = xs[order]
    ys = ys[order]
    name = table.get("name", default_name)

    def ocp(sto):
        if isinstance(sto, pybamm.Symbol):
            return pybamm.Interpolant(xs, ys, sto, name=name, extrapolate=True)
        return np.interp(sto, xs, ys)

    return ocp


def _constant_j0(j0_ref):
    """PyBaMM-compatible constant exchange-current-density function."""
    j0_ref = float(j0_ref)

    def j0(c_e, c_s_surf, c_s_max, T):
        if any(isinstance(v, pybamm.Symbol) for v in [c_e, c_s_surf, c_s_max, T]):
            return pybamm.Scalar(j0_ref)
        return j0_ref

    return j0


def _read_saved_package(folder):
    json_path = Path(folder) / "physical_parameters_flexible.json"
    if not json_path.exists():
        raise FileNotFoundError(
            "Could not find physical_parameters_flexible.json in:\n"
            f"{folder}\n\n"
            "Run the latest exporter first."
        )
    with open(json_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _reaction_rates_from_source_bpx(folder):
    bpx_copy = Path(folder) / "source_bpx_schema_copy.json"
    if not bpx_copy.exists():
        return None, None
    with open(bpx_copy, "r", encoding="utf-8") as f:
        bpx = json.load(f)
    P = bpx["Parameterisation"]
    k_n = float(P["Negative electrode"]["Reaction rate constant [mol.m-2.s-1]"])
    k_p = float(P["Positive electrode"]["Reaction rate constant [mol.m-2.s-1]"])
    return k_n, k_p


def load_bpx_physical_dict(folder):
    """
    Load the saved BPX physical parameters as a plain dict.

    This avoids an old BPXPhysicalParameterSet.py module or a PyBaMM
    ParameterValues copy losing function-valued parameters.
    """
    folder = Path(folder)

    # Prefer direct JSON reading because it is not affected by notebook import cache.
    package = _read_saved_package(folder)
    params = dict(package["physical_scalar_parameters"])

    params["Negative electrode OCP [V]"] = _ocp_fun(
        package["ocp_tables"]["Negative electrode OCP [V]"], "U_n"
    )
    params["Positive electrode OCP [V]"] = _ocp_fun(
        package["ocp_tables"]["Positive electrode OCP [V]"], "U_p"
    )

    # Parallel-electrode alias required by PyBaMM SPM/SPMe/DFN
    required_parallel = "Number of electrodes connected in parallel to make a cell"
    bpx_parallel = "Number of electrode pairs connected in parallel to make a cell"
    if required_parallel not in params:
        params[required_parallel] = float(params.get(bpx_parallel, 1.0))
    if bpx_parallel not in params:
        params[bpx_parallel] = float(params[required_parallel])
    params.setdefault("Number of cells connected in series to make a battery", 1.0)

    # Exchange-current-density functions required by PyBaMM SPM/SPMe/DFN
    F = 96485.33212
    n_ref = "Negative electrode exchange-current density reference [A.m-2]"
    p_ref = "Positive electrode exchange-current density reference [A.m-2]"

    if n_ref not in params or p_ref not in params:
        k_n, k_p = _reaction_rates_from_source_bpx(folder)
        if k_n is None or k_p is None:
            raise KeyError(
                "Missing exchange-current-density references and source BPX reaction-rate constants.\n"
                "Run the latest v6 exporter first, or keep source_bpx_schema_copy.json in the physical parameter folder."
            )
        params[n_ref] = F * k_n
        params[p_ref] = F * k_p

    # Force these keys, even if an old loader did not save them.
    params["Negative electrode exchange-current density [A.m-2]"] = _constant_j0(params[n_ref])
    params["Positive electrode exchange-current density [A.m-2]"] = _constant_j0(params[p_ref])

    return params


def make_parameter_values(params):
    """Create a fresh ParameterValues object and verify required function keys."""
    pv = pybamm.ParameterValues(values=dict(params))

    required = [
        "Negative electrode exchange-current density [A.m-2]",
        "Positive electrode exchange-current density [A.m-2]",
        "Number of electrodes connected in parallel to make a cell",
        "Negative electrode OCP [V]",
        "Positive electrode OCP [V]",
    ]

    missing = [k for k in required if k not in pv._dict_items]
    if missing:
        raise KeyError(f"Still missing required parameters: {missing}")

    return pv


def run_eis(model_class, params, label):
    print(f"\nRunning {label} EIS...")

    # Use a fresh ParameterValues for each model so the j0 functions are definitely present.
    parameter_values = make_parameter_values(params)

    print("  has negative j0:", "Negative electrode exchange-current density [A.m-2]" in parameter_values._dict_items)
    print("  has positive j0:", "Positive electrode exchange-current density [A.m-2]" in parameter_values._dict_items)

    model = model_class(
        parameter_set=parameter_values,
        options=model_options,
        eis=True,
        var_pts=var_pts,
        solver=solver,
    )

    # Do NOT call model.build(...) before simulateEIS.
    # In this PyBOP version, simulateEIS builds the EIS model internally.
    # Calling build first and then simulateEIS can trigger:
    # RuntimeError: dictionary changed size during iteration
    simulation = model.simulateEIS(
        inputs=None,
        f_eval=frequencies,
        initial_state={"Initial SoC": SOC},
    )
    Z = np.asarray(simulation["Impedance"], dtype=complex)

    # Capacitive Nyquist convention
    if np.nanmedian(-np.imag(Z)) < 0:
        Z = np.conjugate(Z)

    return Z

# =============================================================================
# LOAD BPX PHYSICAL PARAMETERS
# =============================================================================

if not physical_parameter_dir.exists():
    raise FileNotFoundError(
        "Physical parameter folder not found:\n"
        f"{physical_parameter_dir}\n\n"
        "Run 01_export_physical_parameters_then_apply_grouping_v6_exchange_current_fix.py first."
    )

params_base = load_bpx_physical_dict(physical_parameter_dir)

print("Loaded BPX physical parameters from:")
print(physical_parameter_dir)
print("Number of scalar/function parameters:", len(params_base))
print("Negative j0 reference [A.m-2]:", params_base["Negative electrode exchange-current density reference [A.m-2]"])
print("Positive j0 reference [A.m-2]:", params_base["Positive electrode exchange-current density reference [A.m-2]"])
print("Parallel electrodes:", params_base["Number of electrodes connected in parallel to make a cell"])

# Optional contact resistance override
OVERRIDE_CONTACT_RESISTANCE = False
CONTACT_RESISTANCE_VALUE = 0.01

if OVERRIDE_CONTACT_RESISTANCE:
    params_base["Contact resistance [Ohm]"] = CONTACT_RESISTANCE_VALUE
    print(f"Overriding Contact resistance [Ohm] = {CONTACT_RESISTANCE_VALUE}")
else:
    print("Using Contact resistance [Ohm]:", params_base.get("Contact resistance [Ohm]", "not found"))

# =============================================================================
# RUN SPM, SPMe, DFN
# =============================================================================

model_classes = [
    pybop.lithium_ion.SPM,
    pybop.lithium_ion.SPMe,
    pybop.lithium_ion.DFN,
]

for ii, (name, model_class) in enumerate(zip(model_names, model_classes)):
    impedances[:, ii] = run_eis(model_class, params_base, name)

# =============================================================================
# PLOT NYQUIST
# =============================================================================

fig, ax = plt.subplots(figsize=(7, 6))

for ii, name in enumerate(model_names):
    ax.plot(
        np.real(impedances[:, ii]),
        -np.imag(impedances[:, ii]),
        linewidth=1.8,
        label=name,
    )

ax.set_xlabel(r"$Z_r(\omega)$ [$\Omega$]")
ax.set_ylabel(r"$-Z_j(\omega)$ [$\Omega$]")
ax.set_title(f"BPX-derived PyBOP model comparison\nSOC = {SOC}")
ax.grid(True)
ax.set_aspect("equal", adjustable="box")
ax.legend()

fig.tight_layout()
plt.show()

# =============================================================================
# SAVE RESULTS
# =============================================================================

mat_path = save_dir / "Z_SPM_SPMe_DFN_Pybop_BPX.mat"
savemat(
    mat_path,
    {
        "Z": impedances,
        "f": frequencies,
        "model_names": model_names,
        "SOC": SOC,
    },
)

fig_path = save_dir / "Z_SPM_SPMe_DFN_Pybop_BPX.png"
fig.savefig(fig_path, dpi=300)

print("\nSaved MAT file to:")
print(mat_path)
print("Saved figure to:")
print(fig_path)
print("\nDONE")


# %%
from pathlib import Path
import json

import matplotlib.pyplot as plt
import numpy as np
import pybamm
from scipy.io import savemat
import pybop

# =============================================================================
# SETTINGS
# =============================================================================

Nfreq = 100
SOC = 0.5
fmin = 2e-4
fmax = 1e5

frequencies = np.logspace(np.log10(fmin), np.log10(fmax), Nfreq)

model_names = ["SPM", "SPMe", "DFN"]
impedances = np.zeros((Nfreq, len(model_names)), dtype=complex)

output_dir = Path(
    r"C:\Users\mugi_jo\Documents\DLR_PROJECTS\bpx_grouped_spme_apply_grouping"
)
physical_parameter_dir = output_dir / "physical_parameter_set"
save_dir = output_dir / "model_comparison_results"
save_dir.mkdir(exist_ok=True)

model_options = {
    "surface form": "differential",
    "contact resistance": "true",
}

var_pts = {
    "x_n": 100,
    "x_s": 20,
    "x_p": 100,
    "r_n": 100,
    "r_p": 100,
}

solver = pybamm.CasadiSolver()


# =============================================================================
# CAPACITY SCALING SETTINGS
# =============================================================================
# Capacity-scaled impedance:
#
#     Z_scaled = Z * capacity_Ah
#
# Units:
#     Ohm Ah
#
# For plotting in mOhm Ah:
#
#     Z_scaled_mOhm_Ah = 1000 * Z * capacity_Ah

SCALE_IMPEDANCE_BY_CAPACITY = True

CAPACITY_SOURCE = "nominal"   # "nominal" or "manual"
MANUAL_CAPACITY_AH = 5.0

SCALED_IMPEDANCE_UNIT = "ohm_Ah"  # "mohm_Ah" or "ohm_Ah"


# =============================================================================
# HELPERS
# =============================================================================

def _ocp_fun(table, default_name):
    xs = np.asarray(table["x"], dtype=float)
    ys = np.asarray(table["y"], dtype=float)
    order = np.argsort(xs)
    xs = xs[order]
    ys = ys[order]
    name = table.get("name", default_name)

    def ocp(sto):
        if isinstance(sto, pybamm.Symbol):
            return pybamm.Interpolant(xs, ys, sto, name=name, extrapolate=True)
        return np.interp(sto, xs, ys)

    return ocp


def _constant_j0(j0_ref):
    """PyBaMM-compatible constant exchange-current-density function."""
    j0_ref = float(j0_ref)

    def j0(c_e, c_s_surf, c_s_max, T):
        if any(isinstance(v, pybamm.Symbol) for v in [c_e, c_s_surf, c_s_max, T]):
            return pybamm.Scalar(j0_ref)
        return j0_ref

    return j0


def _read_saved_package(folder):
    json_path = Path(folder) / "physical_parameters_flexible.json"
    if not json_path.exists():
        raise FileNotFoundError(
            "Could not find physical_parameters_flexible.json in:\n"
            f"{folder}\n\n"
            "Run the latest exporter first."
        )
    with open(json_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _reaction_rates_from_source_bpx(folder):
    bpx_copy = Path(folder) / "source_bpx_schema_copy.json"
    if not bpx_copy.exists():
        return None, None
    with open(bpx_copy, "r", encoding="utf-8") as f:
        bpx = json.load(f)
    P = bpx["Parameterisation"]
    k_n = float(P["Negative electrode"]["Reaction rate constant [mol.m-2.s-1]"])
    k_p = float(P["Positive electrode"]["Reaction rate constant [mol.m-2.s-1]"])
    return k_n, k_p


def load_bpx_physical_dict(folder):
    folder = Path(folder)

    package = _read_saved_package(folder)
    params = dict(package["physical_scalar_parameters"])

    params["Negative electrode OCP [V]"] = _ocp_fun(
        package["ocp_tables"]["Negative electrode OCP [V]"], "U_n"
    )
    params["Positive electrode OCP [V]"] = _ocp_fun(
        package["ocp_tables"]["Positive electrode OCP [V]"], "U_p"
    )

    required_parallel = "Number of electrodes connected in parallel to make a cell"
    bpx_parallel = "Number of electrode pairs connected in parallel to make a cell"
    if required_parallel not in params:
        params[required_parallel] = float(params.get(bpx_parallel, 1.0))
    if bpx_parallel not in params:
        params[bpx_parallel] = float(params[required_parallel])
    params.setdefault("Number of cells connected in series to make a battery", 1.0)

    params.setdefault("Thermodynamic factor", 1.0)

    F = 96485.33212
    n_ref = "Negative electrode exchange-current density reference [A.m-2]"
    p_ref = "Positive electrode exchange-current density reference [A.m-2]"

    if n_ref not in params or p_ref not in params:
        k_n, k_p = _reaction_rates_from_source_bpx(folder)
        if k_n is None or k_p is None:
            raise KeyError(
                "Missing exchange-current-density references and source BPX reaction-rate constants.\n"
                "Run the latest exporter first, or keep source_bpx_schema_copy.json in the physical parameter folder."
            )
        params[n_ref] = F * k_n
        params[p_ref] = F * k_p

    params["Negative electrode exchange-current density [A.m-2]"] = _constant_j0(params[n_ref])
    params["Positive electrode exchange-current density [A.m-2]"] = _constant_j0(params[p_ref])

    return params


def get_capacity_ah(params):
    if CAPACITY_SOURCE.lower() == "manual":
        capacity_ah = float(MANUAL_CAPACITY_AH)
    else:
        capacity_ah = float(params.get("Nominal cell capacity [A.h]", MANUAL_CAPACITY_AH))

    if not np.isfinite(capacity_ah) or capacity_ah <= 0:
        raise ValueError(f"Invalid capacity for scaling: {capacity_ah}")

    return capacity_ah


def scale_impedance_with_capacity(Z, capacity_ah):
    Z_scaled = Z * capacity_ah

    if SCALED_IMPEDANCE_UNIT.lower() == "ohm_ah":
        return Z_scaled, r"m$\Omega$ Ah", "Ohm_Ah"

    return Z_scaled, r"$\Omega$ Ah", "Ohm_Ah"


def make_parameter_values(params):
    pv = pybamm.ParameterValues(values=dict(params))

    required = [
        "Negative electrode exchange-current density [A.m-2]",
        "Positive electrode exchange-current density [A.m-2]",
        "Number of electrodes connected in parallel to make a cell",
        "Negative electrode OCP [V]",
        "Positive electrode OCP [V]",
        "Thermodynamic factor",
    ]

    missing = [k for k in required if k not in pv._dict_items]
    if missing:
        raise KeyError(f"Still missing required parameters: {missing}")

    return pv


def run_eis(model_class, params, label):
    print(f"\nRunning {label} EIS...")

    parameter_values = make_parameter_values(params)

    model = model_class(
        parameter_set=parameter_values,
        options=model_options,
        eis=True,
        var_pts=var_pts,
        solver=solver,
    )

    simulation = model.simulateEIS(
        inputs=None,
        f_eval=frequencies,
        initial_state={"Initial SoC": SOC},
    )

    Z = np.asarray(simulation["Impedance"], dtype=complex)

    if np.nanmedian(-np.imag(Z)) < 0:
        Z = np.conjugate(Z)

    return Z


# =============================================================================
# LOAD BPX PHYSICAL PARAMETERS
# =============================================================================

if not physical_parameter_dir.exists():
    raise FileNotFoundError(
        "Physical parameter folder not found:\n"
        f"{physical_parameter_dir}\n\n"
        "Run the latest BPX physical-parameter exporter first."
    )

params_base = load_bpx_physical_dict(physical_parameter_dir)
capacity_ah = get_capacity_ah(params_base)

print("Loaded BPX physical parameters from:")
print(physical_parameter_dir)
print("Capacity used for scaling [A.h]:", capacity_ah)
print("Parallel electrodes:", params_base["Number of electrodes connected in parallel to make a cell"])

OVERRIDE_CONTACT_RESISTANCE = False
CONTACT_RESISTANCE_VALUE = 0.01

if OVERRIDE_CONTACT_RESISTANCE:
    params_base["Contact resistance [Ohm]"] = CONTACT_RESISTANCE_VALUE
    print(f"Overriding Contact resistance [Ohm] = {CONTACT_RESISTANCE_VALUE}")
else:
    print("Using Contact resistance [Ohm]:", params_base.get("Contact resistance [Ohm]", "not found"))


# =============================================================================
# RUN SPM, SPMe, DFN
# =============================================================================

model_classes = [
    pybop.lithium_ion.SPM,
    pybop.lithium_ion.SPMe,
    pybop.lithium_ion.DFN,
]

for ii, (name, model_class) in enumerate(zip(model_names, model_classes)):
    impedances[:, ii] = run_eis(model_class, params_base, name)


# =============================================================================
# SCALE IMPEDANCE WITH CAPACITY
# =============================================================================

if SCALE_IMPEDANCE_BY_CAPACITY:
    impedances_plot, impedance_unit_label, impedance_unit_file = scale_impedance_with_capacity(
        impedances,
        capacity_ah,
    )
else:
    impedances_plot = impedances
    impedance_unit_label = r"$\Omega$"
    impedance_unit_file = "Ohm"

print("\nImpedance plot unit:", impedance_unit_label)


# =============================================================================
# PLOT CAPACITY-SCALED NYQUIST
# =============================================================================

fig, ax = plt.subplots(figsize=(7, 6))

for ii, name in enumerate(model_names):
    ax.plot(
        np.real(impedances_plot[:, ii]),
        -np.imag(impedances_plot[:, ii]),
        linewidth=1.8,
        label=name,
    )

if SCALE_IMPEDANCE_BY_CAPACITY:
    ax.set_xlabel(r"$Z_r(\omega) \times Q$ [" + impedance_unit_label + "]")
    ax.set_ylabel(r"$-Z_j(\omega) \times Q$ [" + impedance_unit_label + "]")
    ax.set_title(
        f"BPX-derived PyBOP model comparison\n"
        f"SOC = {SOC}, capacity-scaled with Q = {capacity_ah:.4g} Ah"
    )
else:
    ax.set_xlabel(r"$Z_r(\omega)$ [$\Omega$]")
    ax.set_ylabel(r"$-Z_j(\omega)$ [$\Omega$]")
    ax.set_title(f"BPX-derived PyBOP model comparison\nSOC = {SOC}")

ax.grid(True)
ax.set_aspect("equal", adjustable="box")
ax.legend()

fig.tight_layout()
plt.show()


# =============================================================================
# ALSO PLOT RAW IMPEDANCE
# =============================================================================

fig_raw, ax_raw = plt.subplots(figsize=(7, 6))

for ii, name in enumerate(model_names):
    ax_raw.plot(
        np.real(impedances[:, ii]),
        -np.imag(impedances[:, ii]),
        linewidth=1.8,
        label=name,
    )

ax_raw.set_xlabel(r"$Z_r(\omega)$ [$\Omega$]")
ax_raw.set_ylabel(r"$-Z_j(\omega)$ [$\Omega$]")
ax_raw.set_title(f"Raw BPX-derived PyBOP model comparison\nSOC = {SOC}")
ax_raw.grid(True)
ax_raw.set_aspect("equal", adjustable="box")
ax_raw.legend()

fig_raw.tight_layout()
plt.show()


# %%
from pathlib import Path
import sys
import json
import copy

import matplotlib.pyplot as plt
import numpy as np
import pybamm
from scipy.io import savemat

import pybop


# =============================================================================
# SETTINGS
# =============================================================================

factor = 2
Nparams = 11
SOC = 0.5
Nfreq = 100
fmin = 2e-4
fmax = 1e5

parameter_name = "Negative electrode relative porosity"

model_options = {
    "surface form": "differential",
    "contact resistance": "true",
}

var_pts = {
    "x_n": 100,
    "x_s": 20,
    "x_p": 100,
    "r_n": 100,
    "r_p": 100,
}

output_dir = Path(
    r"C:\Users\mugi_jo\Documents\DLR_PROJECTS\bpx_grouped_spme_apply_grouping"
)

grouped_parameter_dir = output_dir / "grouped_parameter_set"


# =============================================================================
# SAFE GROUPED-PARAMETER LOADER
# =============================================================================
# This avoids the old BPXGroupedParameterSet.py bug where the grouped loader tried
# to reconstruct physical exchange-current-density functions. GroupedSPMe does
# NOT need those functions. It needs charge-transfer time scales instead.

def _ocp_fun(table, default_name):
    xs = np.asarray(table["x"], dtype=float)
    ys = np.asarray(table["y"], dtype=float)
    order = np.argsort(xs)
    xs, ys = xs[order], ys[order]
    name = table.get("name", default_name)

    def ocp(sto):
        if hasattr(pybamm, "Symbol") and isinstance(sto, pybamm.Symbol):
            return pybamm.Interpolant(xs, ys, sto, name=name, extrapolate=True)
        return np.interp(sto, xs, ys)

    return ocp


def find_grouped_json(folder):
    folder = Path(folder)

    candidates = [
        folder / "grouped_parameters_from_apply_grouping.json",
        folder / "grouped_spme_parameters_flexible.json",
        folder / "grouped_spme_parameters.json",
    ]

    for path in candidates:
        if path.exists():
            return path

    json_files = sorted(folder.glob("*.json"))
    if not json_files:
        raise FileNotFoundError(f"No JSON file found in {folder}")

    return json_files[0]


def get_grouped_parameters_safe(folder):
    json_path = find_grouped_json(folder)

    with open(json_path, "r", encoding="utf-8") as f:
        package = json.load(f)

    if "grouped_spme_scalar_parameters" in package:
        params = dict(package["grouped_spme_scalar_parameters"])
    elif "grouped_parameters" in package:
        params = dict(package["grouped_parameters"])
    elif "scalar_parameters" in package:
        params = dict(package["scalar_parameters"])
    else:
        raise KeyError(
            "Could not find grouped scalar parameters in JSON. "
            "Expected one of: grouped_spme_scalar_parameters, grouped_parameters, scalar_parameters"
        )

    # Reconstruct OCP functions for GroupedSPMe
    if "ocp_tables" in package:
        ocp_tables = package["ocp_tables"]

        if "Negative electrode OCP [V]" in ocp_tables:
            params["Negative electrode OCP [V]"] = _ocp_fun(
                ocp_tables["Negative electrode OCP [V]"],
                "U_n",
            )

        if "Positive electrode OCP [V]" in ocp_tables:
            params["Positive electrode OCP [V]"] = _ocp_fun(
                ocp_tables["Positive electrode OCP [V]"],
                "U_p",
            )

    # Important: do NOT add physical exchange-current-density functions here.
    # GroupedSPMe uses these instead:
    #   Negative electrode charge transfer time scale [s]
    #   Positive electrode charge transfer time scale [s]

    required = [
        "Negative electrode OCP [V]",
        "Positive electrode OCP [V]",
        "Negative electrode charge transfer time scale [s]",
        "Positive electrode charge transfer time scale [s]",
        "Negative particle diffusion time scale [s]",
        "Positive particle diffusion time scale [s]",
        "Series resistance [Ohm]",
    ]

    missing = [k for k in required if k not in params]
    if missing:
        raise KeyError("Missing required GroupedSPMe parameters:\n" + "\n".join(missing))

    print("Loaded grouped parameters JSON:")
    print(json_path)
    print("Number of grouped parameters:", len(params))

    return copy.deepcopy(params)


if not grouped_parameter_dir.exists():
    raise FileNotFoundError(
        "Grouped BPX parameter folder not found:\n"
        f"{grouped_parameter_dir}\n\n"
        "Run the exporter first, for example:\n"
        "01_export_physical_parameters_then_apply_grouping_v7_thermodynamic_factor_fix.py"
    )

grouped_parameters_base = get_grouped_parameters_safe(grouped_parameter_dir)


# =============================================================================
# CHECK PARAMETER
# =============================================================================

if parameter_name not in grouped_parameters_base:
    print("\nAvailable grouped parameters:")
    for key in sorted(grouped_parameters_base.keys()):
        print("  ", key)
    raise KeyError(f"Parameter not found: {parameter_name}")

param0 = float(grouped_parameters_base[parameter_name])

params = np.logspace(
    np.log10(param0 / factor),
    np.log10(param0 * factor),
    Nparams,
)

frequencies = np.logspace(
    np.log10(fmin),
    np.log10(fmax),
    Nfreq,
)

print("\nParameter varied:")
print(parameter_name)
print("Base value:", param0)
print("Min value:", params[0])
print("Max value:", params[-1])

print("\nUsing BPX-derived Series resistance [Ohm]:")
print(grouped_parameters_base["Series resistance [Ohm]"])


# =============================================================================
# SIMULATE IMPEDANCE
# =============================================================================

impedances = np.zeros((Nfreq, Nparams), dtype=complex)

for ii, param in enumerate(params):
    print(f"{ii + 1}/{Nparams}: {parameter_name} = {param:.6e}")

    grouped_parameters = copy.deepcopy(grouped_parameters_base)
    grouped_parameters[parameter_name] = float(param)

    model = pybop.lithium_ion.GroupedSPMe(
        parameter_set=grouped_parameters,
        eis=True,
        options=model_options,
        var_pts=var_pts,
        solver=pybamm.CasadiSolver(),
    )

    # Do not call model.build(...) separately.
    # simulateEIS builds the EIS model internally.
    simulation = model.simulateEIS(
        inputs=None,
        f_eval=frequencies,
        initial_state={"Initial SoC": SOC},
    )

    Z = np.asarray(simulation["Impedance"], dtype=complex)

    # Capacitive Nyquist convention
    if np.nanmedian(-np.imag(Z)) < 0:
        Z = np.conjugate(Z)

    impedances[:, ii] = Z


# =============================================================================
# PLOT
# =============================================================================

fig, ax = plt.subplots(figsize=(6.5, 6.5))

for ii, param in enumerate(params):
    ax.plot(
        np.real(impedances[:, ii]),
        -np.imag(impedances[:, ii]),
        linewidth=1.6,
        label=f"{param:.2e}",
    )

ax.set_xlabel(r"$Z_r(\omega)$ [$\Omega$]")
ax.set_ylabel(r"$-Z_j(\omega)$ [$\Omega$]")
ax.set_title(f"BPX GroupedSPMe sensitivity\n{parameter_name}, SOC = {SOC}")
ax.grid(True)
ax.set_aspect("equal", adjustable="box")
ax.legend(fontsize=7)

fig.tight_layout()
plt.show()


# %%
from pathlib import Path
import json
import copy

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pybamm
from scipy.io import savemat

import pybop


# =============================================================================
# SETTINGS
# =============================================================================

SOC = 0.5

factor = 2
Nparams = 11

Nfreq = 100
fmin = 2e-4
fmax = 1e5

frequencies = np.logspace(
    np.log10(fmin),
    np.log10(fmax),
    Nfreq,
)

model_options = {
    "surface form": "differential",
    "contact resistance": "true",
}

var_pts = {
    "x_n": 100,
    "x_s": 20,
    "x_p": 100,
    "r_n": 100,
    "r_p": 100,
}

output_dir = Path(
    r"C:\Users\mugi_jo\Documents\DLR_PROJECTS\bpx_grouped_spme_apply_grouping"
)

grouped_parameter_dir = output_dir / "grouped_parameter_set"
save_dir = output_dir / "grouped_sensitivity_all_parameters"
save_dir.mkdir(parents=True, exist_ok=True)


# =============================================================================
# PARAMETERS TO TEST
# =============================================================================

sensitivity_parameter_names = [
    "Negative electrode relative porosity",
    "Positive particle diffusion time scale [s]",
    "Positive electrode electrolyte diffusion time scale [s]",
    "Separator electrolyte diffusion time scale [s]",
    "Positive electrode charge transfer time scale [s]",
    "Series resistance [Ohm]",
    "Positive electrode relative porosity",
    "Cation transference number",
    "Reference electrolyte capacity [A.s]",
    "Positive electrode capacitance [F]",
    "Positive theoretical electrode capacity [As]",
    "Positive electrode relative thickness",
    "Measured cell capacity [A.s]",
]


# =============================================================================
# SAFE GROUPED-PARAMETER LOADER
# =============================================================================
# This bypasses BPXGroupedParameterSet.py because some old generated loaders
# incorrectly try to add physical PyBaMM exchange-current-density functions.
# GroupedSPMe only needs grouped quantities such as tau_ct, tau_d, Q_e, C, etc.


def _ocp_fun(table, default_name):
    xs = np.asarray(table["x"], dtype=float)
    ys = np.asarray(table["y"], dtype=float)

    order = np.argsort(xs)
    xs = xs[order]
    ys = ys[order]

    name = table.get("name", default_name)

    def ocp(sto):
        if hasattr(pybamm, "Symbol") and isinstance(sto, pybamm.Symbol):
            return pybamm.Interpolant(
                xs,
                ys,
                sto,
                name=name,
                extrapolate=True,
            )
        return np.interp(sto, xs, ys)

    return ocp


def find_grouped_json(folder):
    folder = Path(folder)

    candidates = [
        folder / "grouped_parameters_from_apply_grouping.json",
        folder / "grouped_spme_parameters_flexible.json",
        folder / "grouped_spme_parameters.json",
    ]

    for path in candidates:
        if path.exists():
            return path

    json_files = sorted(folder.glob("*.json"))
    if not json_files:
        raise FileNotFoundError(f"No grouped-parameter JSON file found in {folder}")

    return json_files[0]


def get_grouped_parameters_safe(folder):
    json_path = find_grouped_json(folder)

    with open(json_path, "r", encoding="utf-8") as f:
        package = json.load(f)

    if "grouped_spme_scalar_parameters" in package:
        params = dict(package["grouped_spme_scalar_parameters"])
    elif "grouped_parameters" in package:
        params = dict(package["grouped_parameters"])
    elif "scalar_parameters" in package:
        params = dict(package["scalar_parameters"])
    else:
        raise KeyError(
            "Could not find grouped scalar parameters in JSON. Expected one of:\n"
            "  grouped_spme_scalar_parameters\n"
            "  grouped_parameters\n"
            "  scalar_parameters"
        )

    # Reconstruct the OCP functions needed by GroupedSPMe.
    if "ocp_tables" not in package:
        raise KeyError("The grouped JSON does not contain 'ocp_tables'.")

    ocp_tables = package["ocp_tables"]

    params["Negative electrode OCP [V]"] = _ocp_fun(
        ocp_tables["Negative electrode OCP [V]"],
        "U_n",
    )

    params["Positive electrode OCP [V]"] = _ocp_fun(
        ocp_tables["Positive electrode OCP [V]"],
        "U_p",
    )

    required = [
        "Negative electrode OCP [V]",
        "Positive electrode OCP [V]",
        "Negative electrode charge transfer time scale [s]",
        "Positive electrode charge transfer time scale [s]",
        "Negative particle diffusion time scale [s]",
        "Positive particle diffusion time scale [s]",
        "Series resistance [Ohm]",
    ]

    missing = [key for key in required if key not in params]
    if missing:
        raise KeyError(
            "Missing required GroupedSPMe parameters:\n" + "\n".join(missing)
        )

    print("Loaded grouped parameter JSON:")
    print(json_path)
    print("Number of grouped parameters:", len(params))

    return copy.deepcopy(params), json_path


if not grouped_parameter_dir.exists():
    raise FileNotFoundError(
        "Grouped BPX parameter folder not found:\n"
        f"{grouped_parameter_dir}\n\n"
        "Run your BPX exporter first."
    )

grouped_parameters_base, grouped_json_path = get_grouped_parameters_safe(
    grouped_parameter_dir
)


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def make_parameter_values(base_value, factor, n_values):
    base_value = float(base_value)

    if not np.isfinite(base_value):
        raise ValueError(f"Base value is not finite: {base_value}")

    if base_value > 0:
        return np.logspace(
            np.log10(base_value / factor),
            np.log10(base_value * factor),
            n_values,
        )

    if base_value == 0:
        # Log spacing is impossible around zero.
        return np.linspace(-1.0, 1.0, n_values)

    # Negative values are uncommon for these parameters, but this makes the
    # script robust if such a parameter is tested.
    return np.linspace(base_value / factor, base_value * factor, n_values)


def safe_filename(name):
    keep = []
    for char in name:
        if char.isalnum():
            keep.append(char)
        else:
            keep.append("_")
    return "".join(keep).strip("_")


def run_grouped_eis(parameter_name, parameter_value):
    pars = copy.deepcopy(grouped_parameters_base)
    pars[parameter_name] = float(parameter_value)

    model = pybop.lithium_ion.GroupedSPMe(
        parameter_set=pars,
        eis=True,
        options=model_options,
        var_pts=var_pts,
        solver=pybamm.CasadiSolver(),
    )

    # Do not call model.build(...) separately.
    # simulateEIS builds the EIS model internally.
    simulation = model.simulateEIS(
        inputs=None,
        f_eval=frequencies,
        initial_state={"Initial SoC": SOC},
    )

    Z = np.asarray(simulation["Impedance"], dtype=complex)

    # Capacitive Nyquist convention.
    if np.nanmedian(-np.imag(Z)) < 0:
        Z = np.conjugate(Z)

    return Z


def plot_one_parameter(parameter_name, values, Zall):
    fig, ax = plt.subplots(figsize=(6.5, 6.5))

    for j, value in enumerate(values):
        ax.plot(
            np.real(Zall[:, j]),
            -np.imag(Zall[:, j]),
            linewidth=1.5,
            label=f"{value:.2e}",
        )

    ax.set_xlabel(r"$Z_r(\omega)$ [$\Omega$]")
    ax.set_ylabel(r"$-Z_j(\omega)$ [$\Omega$]")
    ax.set_title(f"BPX GroupedSPMe sensitivity\n{parameter_name}\nSOC = {SOC}")
    ax.grid(True)
    ax.set_aspect("equal", adjustable="box")
    ax.legend(fontsize=7)

    fig.tight_layout()
    return fig


# =============================================================================
# RUN SENSITIVITY FOR ALL PARAMETERS
# =============================================================================

all_results = {}
summary_rows = []
csv_rows = []

for p_index, parameter_name in enumerate(sensitivity_parameter_names, start=1):
    print("\n" + "=" * 100)
    print(f"{p_index}/{len(sensitivity_parameter_names)}: {parameter_name}")
    print("=" * 100)

    if parameter_name not in grouped_parameters_base:
        print("SKIPPED: parameter not found in grouped parameter set.")
        summary_rows.append(
            {
                "Parameter": parameter_name,
                "Status": "skipped_missing",
                "Base value": np.nan,
                "Minimum tested": np.nan,
                "Maximum tested": np.nan,
            }
        )
        continue

    base_value = grouped_parameters_base[parameter_name]

    if not isinstance(base_value, (int, float, np.integer, np.floating)):
        print("SKIPPED: parameter is not scalar numeric.")
        summary_rows.append(
            {
                "Parameter": parameter_name,
                "Status": "skipped_not_numeric",
                "Base value": np.nan,
                "Minimum tested": np.nan,
                "Maximum tested": np.nan,
            }
        )
        continue

    values = make_parameter_values(base_value, factor, Nparams)

    print("Base value:", float(base_value))
    print("Minimum tested:", values[0])
    print("Maximum tested:", values[-1])

    Zall = np.zeros((Nfreq, Nparams), dtype=complex)

    failed = False

    for j, value in enumerate(values):
        print(f"  {j + 1}/{Nparams}: {parameter_name} = {value:.6e}")

        try:
            Zall[:, j] = run_grouped_eis(parameter_name, value)
        except Exception as err:
            failed = True
            print("  FAILED:", repr(err))
            Zall[:, j] = np.nan + 1j * np.nan

    all_results[parameter_name] = {
        "values": values,
        "Z": Zall,
        "failed": failed,
    }

    status = "completed_with_errors" if failed else "completed"

    summary_rows.append(
        {
            "Parameter": parameter_name,
            "Status": status,
            "Base value": float(base_value),
            "Minimum tested": float(values[0]),
            "Maximum tested": float(values[-1]),
        }
    )

    for j, value in enumerate(values):
        for f, Z in zip(frequencies, Zall[:, j]):
            csv_rows.append(
                {
                    "Parameter": parameter_name,
                    "Parameter value": float(value),
                    "Frequency [Hz]": float(f),
                    "Z_real [Ohm]": float(np.real(Z)),
                    "Z_imag [Ohm]": float(np.imag(Z)),
                    "-Z_imag [Ohm]": float(-np.imag(Z)),
                    "Z_abs [Ohm]": float(np.abs(Z)),
                    "Phase [deg]": float(np.angle(Z, deg=True)),
                    "SOC": SOC,
                }
            )

    # Save one figure per parameter.
    fig = plot_one_parameter(parameter_name, values, Zall)
    fig_path = save_dir / f"{safe_filename(parameter_name)}_nyquist.png"
    fig.savefig(fig_path, dpi=300)
    plt.show()
    plt.close(fig)

    # Save one MAT file per parameter.
    mat_path = save_dir / f"{safe_filename(parameter_name)}.mat"
    savemat(
        mat_path,
        {
            "Z": Zall,
            "f": frequencies,
            "params": values,
            "name": parameter_name,
            "SOC": SOC,
        },
    )

    print("Saved figure:", fig_path)
    print("Saved MAT:", mat_path)


# =============================================================================
# SAVE COMBINED RESULTS
# =============================================================================

summary_df = pd.DataFrame(summary_rows)
summary_path = save_dir / "sensitivity_summary.csv"
summary_df.to_csv(summary_path, index=False)

long_df = pd.DataFrame(csv_rows)
long_csv_path = save_dir / "all_sensitivity_results_long.csv"
long_df.to_csv(long_csv_path, index=False)

# Save combined MAT with separate keys for each parameter.
mat_dict = {
    "f": frequencies,
    "SOC": SOC,
    "source_grouped_json": str(grouped_json_path),
}

for parameter_name, result in all_results.items():
    key = safe_filename(parameter_name)
    mat_dict[f"Z_{key}"] = result["Z"]
    mat_dict[f"params_{key}"] = result["values"]

combined_mat_path = save_dir / "all_sensitivity_results.mat"
savemat(combined_mat_path, mat_dict)

print("\n" + "=" * 100)
print("DONE")
print("Saved summary CSV:", summary_path)
print("Saved long CSV:", long_csv_path)
print("Saved combined MAT:", combined_mat_path)
print("Output folder:", save_dir.resolve())
print("=" * 100)


# %%


# %%
from pathlib import Path
import json
import copy

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pybamm
import pybop
from scipy.io import savemat


# =============================================================================
# USER SETTINGS
# =============================================================================

# Use your BPX/JSON parameter-set file here.
BPX_FILE = Path(
    r"C:\Users\mugi_jo\Downloads\hydr0_graphite-lnmo_schmitt-2026_validation.bpx_1_patched_for_current_bpx.json"
)

OUT = Path(
    r"C:\Users\mugi_jo\Documents\DLR_PROJECTS\bpx_aligned_pybamm_pybop_grouped"
)
OUT.mkdir(parents=True, exist_ok=True)

SOC = 0.5

FMIN = 2e-4
FMAX = 1e5
NFREQ = 100
frequencies = np.logspace(np.log10(FMIN), np.log10(FMAX), NFREQ)

# Use the same plotting unit for all three approaches.
# Options:
#   "ohm"      -> raw Ohm
#   "mohm"     -> mOhm
#   "mohm_Ah"  -> mOhm Ah, i.e. 1000 * Z[Ohm] * capacity[Ah]
PLOT_UNIT = "ohm"

# BPX does not contain contact resistance. Use one shared value everywhere.
CONTACT_RESISTANCE_OHM = 0.0

# PyBaMM/PyBOP model options
model_options = {
    "surface form": "differential",
    "contact resistance": "true",
}

var_pts = {
    "x_n": 100,
    "x_s": 20,
    "x_p": 100,
    "r_n": 100,
    "r_p": 100,
}

solver = pybamm.CasadiSolver()


# =============================================================================
# BASIC HELPERS
# =============================================================================

FARADAY = 96485.33212


def fnum(x, default=None):
    if x is None:
        if default is None:
            raise ValueError("Expected a number, got None.")
        return float(default)
    return float(x)


def _pybamm_interpolant(x, y, child, name):
    """
    PyBaMM Interpolant wrapper robust to versions that expect child or [child].
    """
    try:
        return pybamm.Interpolant(
            x,
            y,
            child,
            interpolator="linear",
            name=name,
            extrapolate=True,
        )
    except TypeError:
        return pybamm.Interpolant(
            x,
            y,
            [child],
            interpolator="linear",
            name=name,
            extrapolate=True,
        )


def table_fun_1arg(table, name):
    x = np.asarray(table["x"], dtype=float)
    y = np.asarray(table["y"], dtype=float)
    order = np.argsort(x)
    x = x[order]
    y = y[order]

    def f(z):
        if isinstance(z, pybamm.Symbol):
            return _pybamm_interpolant(x, y, z, name)
        return np.interp(z, x, y)

    return f


def table_fun_ce(table, name):
    x = np.asarray(table["x"], dtype=float)
    y = np.asarray(table["y"], dtype=float)
    order = np.argsort(x)
    x = x[order]
    y = y[order]

    def f(c_e, T=None):
        if isinstance(c_e, pybamm.Symbol):
            return _pybamm_interpolant(x, y, c_e, name)
        return np.interp(c_e, x, y)

    return f


def interp_table_at(table, x0):
    xs = np.asarray(table["x"], dtype=float)
    ys = np.asarray(table["y"], dtype=float)
    order = np.argsort(xs)
    return float(np.interp(float(x0), xs[order], ys[order]))


def bruggeman_from_transport_efficiency(eps, transport_efficiency, default=1.5):
    try:
        eps = float(eps)
        transport_efficiency = float(transport_efficiency)
        if 0 < eps < 1 and transport_efficiency > 0:
            return float(np.log(transport_efficiency) / np.log(eps))
    except Exception:
        pass
    return float(default)


def state_initial_conditions(bpx):
    # Some BPX files store State at top level, this one stores it under Parameterisation.
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
    """
    PyBaMM/PyBOP-compatible exchange-current-density function.

    We use one consistent simple mapping from the BPX reaction-rate constants:
        j0_ref [A m-2] = F * k_BPX [mol m-2 s-1]
    """
    j0_ref = float(j0_ref)

    def j0(c_e, c_s_surf, c_s_max, T):
        if any(isinstance(v, pybamm.Symbol) for v in [c_e, c_s_surf, c_s_max, T]):
            return pybamm.Scalar(j0_ref)
        return j0_ref

    return j0


def capacity_scale(Z, capacity_Ah, unit):
    unit = unit.lower()
    if unit == "ohm":
        return Z, r"$\Omega$", "Ohm"
    if unit == "mohm":
        return 1000 * Z, r"m$\Omega$", "mOhm"
    if unit == "mohm_ah":
        return 1000 * Z * capacity_Ah, r"m$\Omega$ Ah", "mOhm_Ah"
    raise ValueError("PLOT_UNIT must be 'ohm', 'mohm', or 'mohm_Ah'.")


# =============================================================================
# ONE BPX -> ONE ALIGNED PHYSICAL PARAMETER DICTIONARY
# =============================================================================

def load_bpx(bpx_file):
    with open(bpx_file, "r", encoding="utf-8") as f:
        return json.load(f)


def make_aligned_physical_dict(bpx, soc):
    P = bpx["Parameterisation"]

    cell = P["Cell"]
    elyte = P["Electrolyte"]
    neg = P["Negative electrode"]
    pos = P["Positive electrode"]
    sep = P["Separator"]
    user = P.get("User-defined", {})

    ic = state_initial_conditions(bpx)
    thermal = state_thermal(bpx)

    # -------------------------------------------------------------------------
    # IMPORTANT AREA ALIGNMENT
    # -------------------------------------------------------------------------
    # Use the one-electrode-pair area for height*width, and use n_parallel
    # separately. Do NOT use total area and n_parallel at the same time.
    # This prevents area double counting.
    area_one_pair = fnum(cell["Electrode area [m2]"])
    n_parallel = fnum(
        cell.get(
            "Number of electrode pairs connected in parallel to make a cell",
            1.0,
        )
    )

    side = float(np.sqrt(area_one_pair))
    effective_area = area_one_pair * n_parallel

    # Stoichiometry/initial concentrations from the same SOC
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

    T0 = fnum(
        ic.get(
            "Initial temperature [K]",
            cell.get("Reference temperature [K]", 298.15),
        )
    )
    T_amb = fnum(thermal.get("Ambient temperature [K]", T0))

    # BPX reaction-rate constants -> constant j0 references
    k_n = fnum(neg.get("Reaction rate constant [mol.m-2.s-1]", 1e-6))
    k_p = fnum(pos.get("Reaction rate constant [mol.m-2.s-1]", 1e-6))
    j0_n_ref = FARADAY * k_n
    j0_p_ref = FARADAY * k_p

    eps_n = fnum(neg["Porosity"])
    eps_p = fnum(pos["Porosity"])
    eps_s = fnum(sep["Porosity"])

    alpha_n = fnum(
        user.get("Negative electrode active material volume fraction", 1.0 - eps_n)
    )
    alpha_p = fnum(
        user.get("Positive electrode active material volume fraction", 1.0 - eps_p)
    )

    b_n_e = bruggeman_from_transport_efficiency(
        eps_n,
        neg.get("Transport efficiency", None),
    )
    b_p_e = bruggeman_from_transport_efficiency(
        eps_p,
        pos.get("Transport efficiency", None),
    )
    b_s_e = bruggeman_from_transport_efficiency(
        eps_s,
        sep.get("Transport efficiency", None),
    )

    params = {
        "chemistry": "lithium_ion",

        # Geometry / current scaling
        "Electrode height [m]": side,
        "Electrode width [m]": side,
        "Cell volume [m3]": fnum(
            cell.get(
                "Volume [m3]",
                effective_area
                * (
                    fnum(neg["Thickness [m]"])
                    + fnum(sep["Thickness [m]"])
                    + fnum(pos["Thickness [m]"])
                ),
            )
        ),
        "Number of electrodes connected in parallel to make a cell": n_parallel,
        "Number of electrode pairs connected in parallel to make a cell": n_parallel,
        "Number of cells connected in series to make a battery": 1.0,

        # Capacity / current
        "Nominal cell capacity [A.h]": fnum(cell.get("Nominal cell capacity [A.h]", 1.0)),
        "Current function [A]": 0.0,
        "Initial SoC": float(soc),
        "Contact resistance [Ohm]": float(CONTACT_RESISTANCE_OHM),

        # Thicknesses
        "Negative electrode thickness [m]": fnum(neg["Thickness [m]"]),
        "Separator thickness [m]": fnum(sep["Thickness [m]"]),
        "Positive electrode thickness [m]": fnum(pos["Thickness [m]"]),
        "Negative current collector thickness [m]": 1.0e-5,
        "Positive current collector thickness [m]": 1.0e-5,

        # Negative electrode
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
        "Negative electrode OCP entropic change [V.K-1]": fnum(
            neg.get("Entropic change coefficient [V.K-1]", 0.0)
        ),

        # Positive electrode
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
        "Positive electrode OCP entropic change [V.K-1]": fnum(
            pos.get("Entropic change coefficient [V.K-1]", 0.0)
        ),

        # Separator
        "Separator porosity": eps_s,
        "Separator Bruggeman coefficient (electrolyte)": b_s_e,

        # Electrolyte
        "Initial concentration in electrolyte [mol.m-3]": c_e0,
        "Electrolyte diffusivity [m2.s-1]": table_fun_ce(
            elyte["Diffusivity [m2.s-1]"],
            "Electrolyte diffusivity [m2.s-1]",
        ),
        "Electrolyte conductivity [S.m-1]": table_fun_ce(
            elyte["Conductivity [S.m-1]"],
            "Electrolyte conductivity [S.m-1]",
        ),
        "Cation transference number": fnum(elyte["Cation transference number"]),
        "Thermodynamic factor": fnum(elyte.get("Thermodynamic factor", 1.0)),

        # Temperature / voltage
        "Reference temperature [K]": fnum(cell.get("Reference temperature [K]", T0)),
        "Ambient temperature [K]": T_amb,
        "Initial temperature [K]": T0,
        "Lower voltage cut-off [V]": fnum(cell["Lower voltage cut-off [V]"]),
        "Upper voltage cut-off [V]": fnum(cell["Upper voltage cut-off [V]"]),
        "Open-circuit voltage at 0% SOC [V]": fnum(
            user.get("Open-circuit voltage at 0% SOC [V]", cell["Lower voltage cut-off [V]"])
        ),
        "Open-circuit voltage at 100% SOC [V]": fnum(
            user.get("Open-circuit voltage at 100% SOC [V]", cell["Upper voltage cut-off [V]"])
        ),

        # Basic current collector properties
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
        "electrolyte_diffusivity_at_ce0_m2_s": interp_table_at(
            elyte["Diffusivity [m2.s-1]"],
            c_e0,
        ),
        "electrolyte_conductivity_at_ce0_S_m": interp_table_at(
            elyte["Conductivity [S.m-1]"],
            c_e0,
        ),
        "negative_j0_ref_A_m2": j0_n_ref,
        "positive_j0_ref_A_m2": j0_p_ref,
    }

    scalar_grouping_overrides = {
        "Electrolyte diffusivity [m2.s-1]": diagnostics["electrolyte_diffusivity_at_ce0_m2_s"],
        "Electrolyte conductivity [S.m-1]": diagnostics["electrolyte_conductivity_at_ce0_S_m"],
    }

    return params, diagnostics, scalar_grouping_overrides


def make_parameter_values(params):
    return pybamm.ParameterValues(values=dict(params))


# =============================================================================
# PYBOP GROUPING FROM THE SAME PHYSICAL PARAMETER SET
# =============================================================================

def make_grouped_parameters(params, scalar_grouping_overrides):
    """
    Create GroupedSPMe parameters from the same aligned physical BPX parameter set.

    Why this function adds constants:
    PyBOP's convert_physical_to_grouped_parameters in some versions still asks
    ParameterValues for old-style constants such as
        "Faraday constant [C.mol-1]"
    while PyBaMM 26.4.0 deprecates access to those constants from ParameterValues.
    Adding the constants explicitly keeps the PyBOP grouping converter compatible
    with PyBaMM 26.4.0.
    """
    grouping_params = copy.deepcopy(params)

    # GroupedSPMe grouping needs scalar electrolyte properties.
    # The physical PyBaMM/PyBOP models still use the full electrolyte tables.
    grouping_params.update(scalar_grouping_overrides)

    # Compatibility with PyBOP grouping converter + PyBaMM 26.4.0
    grouping_params["Faraday constant [C.mol-1]"] = float(pybamm.constants.F.value)
    grouping_params["Ideal gas constant [J.K-1.mol-1]"] = float(pybamm.constants.R.value)

    parameter_values_for_grouping = pybamm.ParameterValues(values=grouping_params)

    from pybop.models.lithium_ion.basic_SPMe import convert_physical_to_grouped_parameters

    print("Grouping with convert_physical_to_grouped_parameters(...)")
    try:
        grouped = convert_physical_to_grouped_parameters(
            parameter_values_for_grouping,
            measured_cell_capacity_as=params["Nominal cell capacity [A.h]"] * 3600,
            check_full_cell_capacity=False,
        )
    except TypeError:
        # Older PyBOP versions may not have these keyword arguments.
        grouped = convert_physical_to_grouped_parameters(parameter_values_for_grouping)

    # Ensure OCP functions are present for GroupedSPMe.
    grouped["Negative electrode OCP [V]"] = params["Negative electrode OCP [V]"]
    grouped["Positive electrode OCP [V]"] = params["Positive electrode OCP [V]"]

    # For model-to-model comparison, use the same nominal capacity as the physical models.
    grouped["Measured cell capacity [A.s]"] = params["Nominal cell capacity [A.h]"] * 3600

    # Avoid PyBOP/PyBaMM 26.4 set_initial_soc API mismatch by storing SOC
    # directly in the grouped parameter set instead of passing initial_state.
    grouped["Initial SoC"] = float(params.get("Initial SoC", SOC))

    return grouped


# =============================================================================
# EIS RUNNERS
# =============================================================================

def extract_impedance_from_pybamm_result(result):
    """Extract impedance from native PyBaMM EISSimulation output."""
    try:
        Z = np.asarray(result["Impedance [Ohm]"], dtype=complex)
    except Exception:
        Z = np.asarray(result["Impedance"], dtype=complex)

    if np.nanmedian(-np.imag(Z)) < 0:
        Z = np.conjugate(Z)

    return Z


def run_pybop_physical_eis(params, model_class, label):
    print(f"\nRunning PyBOP physical {label} EIS...")

    parameter_values = make_parameter_values(params)

    model = model_class(
        parameter_set=parameter_values,
        options=model_options,
        eis=True,
        var_pts=var_pts,
        solver=solver,
    )

    # Do not pass initial_state here.
    # With PyBaMM 26.4.0, some PyBOP versions call Simulation.set_initial_soc
    # with the old signature and fail. The SOC is already encoded through the
    # initial concentrations in params and through params["Initial SoC"].
    simulation = model.simulateEIS(
        inputs=None,
        f_eval=frequencies,
    )

    Z = np.asarray(simulation["Impedance"], dtype=complex)

    if np.nanmedian(-np.imag(Z)) < 0:
        Z = np.conjugate(Z)

    return Z


def run_pybop_grouped_eis(grouped_parameters):
    print("\nRunning PyBOP GroupedSPMe EIS...")

    model = pybop.lithium_ion.GroupedSPMe(
        parameter_set=copy.deepcopy(grouped_parameters),
        eis=True,
        options=model_options,
        var_pts=var_pts,
        solver=solver,
    )

    # Do not pass initial_state here.
    # With PyBaMM 26.4.0, some PyBOP versions call Simulation.set_initial_soc
    # with the old signature and fail. The SOC is already encoded through the
    # initial concentrations in params and through params["Initial SoC"].
    simulation = model.simulateEIS(
        inputs=None,
        f_eval=frequencies,
    )

    Z = np.asarray(simulation["Impedance"], dtype=complex)

    if np.nanmedian(-np.imag(Z)) < 0:
        Z = np.conjugate(Z)

    return Z


# =============================================================================
# MAIN
# =============================================================================

bpx = load_bpx(BPX_FILE)
params, diagnostics, scalar_grouping_overrides = make_aligned_physical_dict(bpx, SOC)
grouped_parameters = make_grouped_parameters(params, scalar_grouping_overrides)

capacity_Ah = params["Nominal cell capacity [A.h]"]

print("\n" + "=" * 90)
print("ALIGNED PARAMETER DIAGNOSTICS")
print("=" * 90)
print("BPX file:", BPX_FILE)
print("Nominal capacity [Ah]:", capacity_Ah)
print("Electrode area one pair [m2]:", diagnostics["area_one_pair_m2"])
print("Number parallel:", diagnostics["n_parallel"])
print("height * width [m2]:", diagnostics["height_times_width_m2"])
print("Effective area [m2]:", diagnostics["effective_area_m2"])
print("Contact resistance [Ohm]:", params["Contact resistance [Ohm]"])
print("Initial SoC used in parameter set:", params["Initial SoC"])
print("c_e0 [mol m-3]:", diagnostics["c_e0_mol_m3"])
print("D_e(c_e0) [m2 s-1]:", diagnostics["electrolyte_diffusivity_at_ce0_m2_s"])
print("kappa_e(c_e0) [S m-1]:", diagnostics["electrolyte_conductivity_at_ce0_S_m"])
print("Negative j0_ref [A m-2]:", diagnostics["negative_j0_ref_A_m2"])
print("Positive j0_ref [A m-2]:", diagnostics["positive_j0_ref_A_m2"])
print("\nGrouped parameters:")
for key in [
    "Series resistance [Ohm]",
    "Negative electrode charge transfer time scale [s]",
    "Positive electrode charge transfer time scale [s]",
    "Negative particle diffusion time scale [s]",
    "Positive particle diffusion time scale [s]",
    "Reference electrolyte capacity [A.s]",
    "Measured cell capacity [A.s]",
]:
    print(f"{key}: {grouped_parameters.get(key)}")
print("=" * 90)

# =============================================================================
# RUN THE THREE ALIGNED APPROACHES
# =============================================================================

# 1) Native PyBaMM EISSimulation
print("\nRunning native PyBaMM SPMe EIS with pybamm.EISSimulation(model, parameter_values=...)...")
print("PyBaMM version:", pybamm.__version__)
print("Has pybamm.EISSimulation:", hasattr(pybamm, "EISSimulation"))

if not hasattr(pybamm, "EISSimulation"):
    raise AttributeError(
        "pybamm.EISSimulation is not available. Restart the Jupyter kernel and "
        "make sure the notebook is using pybop_env_2 with PyBaMM 26.4.0."
    )

pybamm_parameter_values = make_parameter_values(params)
pybamm_model = pybamm.lithium_ion.SPMe(options=model_options)

pybamm_sim = pybamm.EISSimulation(
    pybamm_model,
    parameter_values=pybamm_parameter_values,
)

pybamm_result = pybamm_sim.solve(
    frequencies,
    initial_soc=SOC,
)

Z_pybamm_spme = extract_impedance_from_pybamm_result(pybamm_result)

# 2) PyBOP physical SPMe with the same aligned BPX parameters
Z_pybop_spme = run_pybop_physical_eis(params, pybop.lithium_ion.SPMe, "SPMe")

# 3) PyBOP GroupedSPMe from the same aligned BPX parameters after grouping
Z_grouped_spme = run_pybop_grouped_eis(grouped_parameters)

Z_dict = {
    "Native PyBaMM SPMe": Z_pybamm_spme,
    "PyBOP SPMe": Z_pybop_spme,
    "PyBOP GroupedSPMe": Z_grouped_spme,
}

# Scale for plotting
Z_plot_dict = {}
for label, Z in Z_dict.items():
    Z_plot_dict[label], unit_label, unit_file = capacity_scale(Z, capacity_Ah, PLOT_UNIT)

# =============================================================================
# PLOT ONE FIGURE WITH ALL THREE
# =============================================================================

fig, ax = plt.subplots(figsize=(7.5, 6.5))

for label, Zp in Z_plot_dict.items():
    ax.plot(
        np.real(Zp),
        -np.imag(Zp),
        "-o",
        markersize=3.5,
        linewidth=1.5,
        label=label,
    )

ax.set_xlabel(r"$Z_r(\omega)$ [" + unit_label + "]")
ax.set_ylabel(r"$-Z_j(\omega)$ [" + unit_label + "]")
ax.set_title(f"Aligned BPX EIS comparison, SOC = {SOC}")
ax.grid(True)
ax.set_aspect("equal", adjustable="box")
ax.legend()
fig.tight_layout()

fig_path = OUT / f"aligned_pybamm_pybop_grouped_comparison_{unit_file}.png"
fig.savefig(fig_path, dpi=300)
plt.show()

# =============================================================================
# SAVE DATA
# =============================================================================

rows = []
for label, Z in Z_dict.items():
    Zp, _, _ = capacity_scale(Z, capacity_Ah, PLOT_UNIT)
    for f, raw, plotz in zip(frequencies, Z, Zp):
        rows.append(
            {
                "Model": label,
                "Frequency [Hz]": f,
                "Z_real_raw [Ohm]": np.real(raw),
                "Z_imag_raw [Ohm]": np.imag(raw),
                "-Z_imag_raw [Ohm]": -np.imag(raw),
                f"Z_real_plot [{unit_file}]": np.real(plotz),
                f"Z_imag_plot [{unit_file}]": np.imag(plotz),
                f"-Z_imag_plot [{unit_file}]": -np.imag(plotz),
                "SOC": SOC,
                "Capacity [Ah]": capacity_Ah,
            }
        )

df = pd.DataFrame(rows)
csv_path = OUT / f"aligned_pybamm_pybop_grouped_comparison_{unit_file}.csv"
df.to_csv(csv_path, index=False)

mat_path = OUT / f"aligned_pybamm_pybop_grouped_comparison_{unit_file}.mat"
savemat(
    mat_path,
    {
        "f": frequencies,
        "Z_pybamm_spme": Z_pybamm_spme,
        "Z_pybop_spme": Z_pybop_spme,
        "Z_grouped_spme": Z_grouped_spme,
        "capacity_Ah": capacity_Ah,
        "SOC": SOC,
    },
)

diagnostics_path = OUT / "aligned_parameter_diagnostics.json"
diagnostics_to_save = {
    **diagnostics,
    "capacity_Ah": capacity_Ah,
    "contact_resistance_Ohm": CONTACT_RESISTANCE_OHM,
    "plot_unit": PLOT_UNIT,
    "grouped_parameters_selected": {
        key: float(grouped_parameters[key])
        for key in [
            "Series resistance [Ohm]",
            "Negative electrode charge transfer time scale [s]",
            "Positive electrode charge transfer time scale [s]",
            "Negative particle diffusion time scale [s]",
            "Positive particle diffusion time scale [s]",
            "Reference electrolyte capacity [A.s]",
            "Measured cell capacity [A.s]",
        ]
        if key in grouped_parameters and isinstance(grouped_parameters[key], (int, float, np.integer, np.floating))
    },
}
with open(diagnostics_path, "w", encoding="utf-8") as f:
    json.dump(diagnostics_to_save, f, indent=2)

print("\nSaved figure:", fig_path)
print("Saved CSV:", csv_path)
print("Saved MAT:", mat_path)
print("Saved diagnostics:", diagnostics_path)
print("\nDONE")


# %%
from pathlib import Path
import json
import copy

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pybamm
import pybop
from scipy.io import savemat


# =============================================================================
# USER SETTINGS
# =============================================================================

# Use your BPX/JSON parameter-set file here.
BPX_FILE = Path(
    r"C:\Users\mugi_jo\Downloads\hydr0_graphite-lnmo_schmitt-2026_validation.bpx_1_patched_for_current_bpx.json"
)

OUT = Path(
    r"C:\Users\mugi_jo\Documents\DLR_PROJECTS\bpx_aligned_pybamm_pybop_grouped_area_fixed"
)
OUT.mkdir(parents=True, exist_ok=True)

SOC = 0.5

FMIN = 2e-4
FMAX = 1e5
NFREQ = 100
frequencies = np.logspace(np.log10(FMIN), np.log10(FMAX), NFREQ)

# Use the same plotting unit for all three approaches.
# Options:
#   "ohm"      -> raw Ohm
#   "mohm"     -> mOhm
#   "mohm_Ah"  -> mOhm Ah, i.e. 1000 * Z[Ohm] * capacity[Ah]
PLOT_UNIT = "ohm"

# BPX does not contain contact resistance. Use one shared value everywhere.
CONTACT_RESISTANCE_OHM = 0.0

# PyBaMM/PyBOP model options
model_options = {
    "surface form": "differential",
    "contact resistance": "true",
}

var_pts = {
    "x_n": 100,
    "x_s": 20,
    "x_p": 100,
    "r_n": 100,
    "r_p": 100,
}

solver = pybamm.CasadiSolver()


# =============================================================================
# BASIC HELPERS
# =============================================================================

FARADAY = 96485.33212


def fnum(x, default=None):
    if x is None:
        if default is None:
            raise ValueError("Expected a number, got None.")
        return float(default)
    return float(x)


def _pybamm_interpolant(x, y, child, name):
    """
    PyBaMM Interpolant wrapper robust to versions that expect child or [child].
    """
    try:
        return pybamm.Interpolant(
            x,
            y,
            child,
            interpolator="linear",
            name=name,
            extrapolate=True,
        )
    except TypeError:
        return pybamm.Interpolant(
            x,
            y,
            [child],
            interpolator="linear",
            name=name,
            extrapolate=True,
        )


def table_fun_1arg(table, name):
    x = np.asarray(table["x"], dtype=float)
    y = np.asarray(table["y"], dtype=float)
    order = np.argsort(x)
    x = x[order]
    y = y[order]

    def f(z):
        if isinstance(z, pybamm.Symbol):
            return _pybamm_interpolant(x, y, z, name)
        return np.interp(z, x, y)

    return f


def table_fun_ce(table, name):
    x = np.asarray(table["x"], dtype=float)
    y = np.asarray(table["y"], dtype=float)
    order = np.argsort(x)
    x = x[order]
    y = y[order]

    def f(c_e, T=None):
        if isinstance(c_e, pybamm.Symbol):
            return _pybamm_interpolant(x, y, c_e, name)
        return np.interp(c_e, x, y)

    return f


def interp_table_at(table, x0):
    xs = np.asarray(table["x"], dtype=float)
    ys = np.asarray(table["y"], dtype=float)
    order = np.argsort(xs)
    return float(np.interp(float(x0), xs[order], ys[order]))


def bruggeman_from_transport_efficiency(eps, transport_efficiency, default=1.5):
    try:
        eps = float(eps)
        transport_efficiency = float(transport_efficiency)
        if 0 < eps < 1 and transport_efficiency > 0:
            return float(np.log(transport_efficiency) / np.log(eps))
    except Exception:
        pass
    return float(default)


def state_initial_conditions(bpx):
    # Some BPX files store State at top level, this one stores it under Parameterisation.
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
    """
    PyBaMM/PyBOP-compatible exchange-current-density function.

    We use one consistent simple mapping from the BPX reaction-rate constants:
        j0_ref [A m-2] = F * k_BPX [mol m-2 s-1]
    """
    j0_ref = float(j0_ref)

    def j0(c_e, c_s_surf, c_s_max, T):
        if any(isinstance(v, pybamm.Symbol) for v in [c_e, c_s_surf, c_s_max, T]):
            return pybamm.Scalar(j0_ref)
        return j0_ref

    return j0


def capacity_scale(Z, capacity_Ah, unit):
    unit = unit.lower()
    if unit == "ohm":
        return Z, r"$\Omega$", "Ohm"
    if unit == "mohm":
        return 1000 * Z, r"m$\Omega$", "mOhm"
    if unit == "mohm_ah":
        return 1000 * Z * capacity_Ah, r"m$\Omega$ Ah", "mOhm_Ah"
    raise ValueError("PLOT_UNIT must be 'ohm', 'mohm', or 'mohm_Ah'.")


# =============================================================================
# ONE BPX -> ONE ALIGNED PHYSICAL PARAMETER DICTIONARY
# =============================================================================

def load_bpx(bpx_file):
    with open(bpx_file, "r", encoding="utf-8") as f:
        return json.load(f)


def make_aligned_physical_dict(bpx, soc):
    P = bpx["Parameterisation"]

    cell = P["Cell"]
    elyte = P["Electrolyte"]
    neg = P["Negative electrode"]
    pos = P["Positive electrode"]
    sep = P["Separator"]
    user = P.get("User-defined", {})

    ic = state_initial_conditions(bpx)
    thermal = state_thermal(bpx)

    # -------------------------------------------------------------------------
    # IMPORTANT AREA ALIGNMENT
    # -------------------------------------------------------------------------
    # Use the one-electrode-pair area for height*width, and use n_parallel
    # separately. Do NOT use total area and n_parallel at the same time.
    # This prevents area double counting.
    area_one_pair = fnum(cell["Electrode area [m2]"])
    n_parallel = fnum(
        cell.get(
            "Number of electrode pairs connected in parallel to make a cell",
            1.0,
        )
    )

    side = float(np.sqrt(area_one_pair))
    effective_area = area_one_pair * n_parallel

    # Stoichiometry/initial concentrations from the same SOC
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

    T0 = fnum(
        ic.get(
            "Initial temperature [K]",
            cell.get("Reference temperature [K]", 298.15),
        )
    )
    T_amb = fnum(thermal.get("Ambient temperature [K]", T0))

    # BPX reaction-rate constants -> constant j0 references
    k_n = fnum(neg.get("Reaction rate constant [mol.m-2.s-1]", 1e-6))
    k_p = fnum(pos.get("Reaction rate constant [mol.m-2.s-1]", 1e-6))
    j0_n_ref = FARADAY * k_n
    j0_p_ref = FARADAY * k_p

    eps_n = fnum(neg["Porosity"])
    eps_p = fnum(pos["Porosity"])
    eps_s = fnum(sep["Porosity"])

    alpha_n = fnum(
        user.get("Negative electrode active material volume fraction", 1.0 - eps_n)
    )
    alpha_p = fnum(
        user.get("Positive electrode active material volume fraction", 1.0 - eps_p)
    )

    b_n_e = bruggeman_from_transport_efficiency(
        eps_n,
        neg.get("Transport efficiency", None),
    )
    b_p_e = bruggeman_from_transport_efficiency(
        eps_p,
        pos.get("Transport efficiency", None),
    )
    b_s_e = bruggeman_from_transport_efficiency(
        eps_s,
        sep.get("Transport efficiency", None),
    )

    params = {
        "chemistry": "lithium_ion",

        # Geometry / current scaling
        "Electrode height [m]": side,
        "Electrode width [m]": side,
        "Cell volume [m3]": fnum(
            cell.get(
                "Volume [m3]",
                effective_area
                * (
                    fnum(neg["Thickness [m]"])
                    + fnum(sep["Thickness [m]"])
                    + fnum(pos["Thickness [m]"])
                ),
            )
        ),
        "Number of electrodes connected in parallel to make a cell": n_parallel,
        "Number of electrode pairs connected in parallel to make a cell": n_parallel,
        "Number of cells connected in series to make a battery": 1.0,

        # Capacity / current
        "Nominal cell capacity [A.h]": fnum(cell.get("Nominal cell capacity [A.h]", 1.0)),
        "Current function [A]": 0.0,
        "Initial SoC": float(soc),
        "Contact resistance [Ohm]": float(CONTACT_RESISTANCE_OHM),

        # Thicknesses
        "Negative electrode thickness [m]": fnum(neg["Thickness [m]"]),
        "Separator thickness [m]": fnum(sep["Thickness [m]"]),
        "Positive electrode thickness [m]": fnum(pos["Thickness [m]"]),
        "Negative current collector thickness [m]": 1.0e-5,
        "Positive current collector thickness [m]": 1.0e-5,

        # Negative electrode
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
        "Negative electrode OCP entropic change [V.K-1]": fnum(
            neg.get("Entropic change coefficient [V.K-1]", 0.0)
        ),

        # Positive electrode
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
        "Positive electrode OCP entropic change [V.K-1]": fnum(
            pos.get("Entropic change coefficient [V.K-1]", 0.0)
        ),

        # Separator
        "Separator porosity": eps_s,
        "Separator Bruggeman coefficient (electrolyte)": b_s_e,

        # Electrolyte
        "Initial concentration in electrolyte [mol.m-3]": c_e0,
        "Electrolyte diffusivity [m2.s-1]": table_fun_ce(
            elyte["Diffusivity [m2.s-1]"],
            "Electrolyte diffusivity [m2.s-1]",
        ),
        "Electrolyte conductivity [S.m-1]": table_fun_ce(
            elyte["Conductivity [S.m-1]"],
            "Electrolyte conductivity [S.m-1]",
        ),
        "Cation transference number": fnum(elyte["Cation transference number"]),
        "Thermodynamic factor": fnum(elyte.get("Thermodynamic factor", 1.0)),

        # Temperature / voltage
        "Reference temperature [K]": fnum(cell.get("Reference temperature [K]", T0)),
        "Ambient temperature [K]": T_amb,
        "Initial temperature [K]": T0,
        "Lower voltage cut-off [V]": fnum(cell["Lower voltage cut-off [V]"]),
        "Upper voltage cut-off [V]": fnum(cell["Upper voltage cut-off [V]"]),
        "Open-circuit voltage at 0% SOC [V]": fnum(
            user.get("Open-circuit voltage at 0% SOC [V]", cell["Lower voltage cut-off [V]"])
        ),
        "Open-circuit voltage at 100% SOC [V]": fnum(
            user.get("Open-circuit voltage at 100% SOC [V]", cell["Upper voltage cut-off [V]"])
        ),

        # Basic current collector properties
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
        "electrolyte_diffusivity_at_ce0_m2_s": interp_table_at(
            elyte["Diffusivity [m2.s-1]"],
            c_e0,
        ),
        "electrolyte_conductivity_at_ce0_S_m": interp_table_at(
            elyte["Conductivity [S.m-1]"],
            c_e0,
        ),
        "negative_j0_ref_A_m2": j0_n_ref,
        "positive_j0_ref_A_m2": j0_p_ref,
    }

    scalar_grouping_overrides = {
        "Electrolyte diffusivity [m2.s-1]": diagnostics["electrolyte_diffusivity_at_ce0_m2_s"],
        "Electrolyte conductivity [S.m-1]": diagnostics["electrolyte_conductivity_at_ce0_S_m"],
    }

    return params, diagnostics, scalar_grouping_overrides


def make_parameter_values(params):
    return pybamm.ParameterValues(values=dict(params))


# =============================================================================
# PYBOP GROUPING FROM THE SAME PHYSICAL PARAMETER SET
# =============================================================================

def make_grouped_parameters(params, scalar_grouping_overrides):
    """
    Create GroupedSPMe parameters from the same aligned physical BPX parameter set.

    Important:
    Physical PyBaMM/PyBOP models use:
        effective area = height * width * number_parallel

    The PyBOP grouped-parameter converter uses only:
        A = height * width

    Therefore, for the grouping step only, we put the TOTAL cell area into
    height * width and set number_parallel = 1. This prevents the grouped model
    from being about n_parallel times too large in impedance.
    """
    grouping_params = copy.deepcopy(params)

    # -------------------------------------------------------------------------
    # GROUPING AREA FIX
    # -------------------------------------------------------------------------
    # Keep the physical models as one-pair area + n_parallel.
    # But for GroupedSPMe grouping, use total effective area directly because
    # the grouping converter does not multiply by n_parallel.
    area_one_pair = (
        float(params["Electrode height [m]"])
        * float(params["Electrode width [m]"])
    )
    n_parallel = float(
        params.get("Number of electrodes connected in parallel to make a cell", 1.0)
    )
    area_total = area_one_pair * n_parallel
    side_total = float(np.sqrt(area_total))

    grouping_params["Electrode height [m]"] = side_total
    grouping_params["Electrode width [m]"] = side_total
    grouping_params["Number of electrodes connected in parallel to make a cell"] = 1.0
    grouping_params["Number of electrode pairs connected in parallel to make a cell"] = 1.0

    print("\nGrouped-parameter area correction:")
    print("  physical height*width [m2]:", area_one_pair)
    print("  physical n_parallel:", n_parallel)
    print("  grouped height*width [m2]:", area_total)

    # GroupedSPMe grouping needs scalar electrolyte properties.
    # The physical PyBaMM/PyBOP models still use the full electrolyte tables.
    grouping_params.update(scalar_grouping_overrides)

    # Compatibility with PyBOP grouping converter + PyBaMM 26.4.0
    grouping_params["Faraday constant [C.mol-1]"] = float(pybamm.constants.F.value)
    grouping_params["Ideal gas constant [J.K-1.mol-1]"] = float(pybamm.constants.R.value)

    parameter_values_for_grouping = pybamm.ParameterValues(values=grouping_params)

    from pybop.models.lithium_ion.basic_SPMe import convert_physical_to_grouped_parameters

    print("Grouping with convert_physical_to_grouped_parameters(...)")
    try:
        grouped = convert_physical_to_grouped_parameters(
            parameter_values_for_grouping,
            measured_cell_capacity_as=params["Nominal cell capacity [A.h]"] * 3600,
            check_full_cell_capacity=False,
        )
    except TypeError:
        grouped = convert_physical_to_grouped_parameters(parameter_values_for_grouping)

    # Ensure OCP functions are present for GroupedSPMe.
    grouped["Negative electrode OCP [V]"] = params["Negative electrode OCP [V]"]
    grouped["Positive electrode OCP [V]"] = params["Positive electrode OCP [V]"]

    # Use the same nominal measured capacity as the physical models.
    grouped["Measured cell capacity [A.s]"] = params["Nominal cell capacity [A.h]"] * 3600

    # Avoid PyBOP/PyBaMM 26.4 set_initial_soc API mismatch by storing SOC
    # directly in the grouped parameter set instead of passing initial_state.
    grouped["Initial SoC"] = float(params.get("Initial SoC", SOC))

    return grouped


# =============================================================================
# EIS RUNNERS
# =============================================================================

def extract_impedance_from_pybamm_result(result):
    """Extract impedance from native PyBaMM EISSimulation output."""
    try:
        Z = np.asarray(result["Impedance [Ohm]"], dtype=complex)
    except Exception:
        Z = np.asarray(result["Impedance"], dtype=complex)

    if np.nanmedian(-np.imag(Z)) < 0:
        Z = np.conjugate(Z)

    return Z


def run_pybop_physical_eis(params, model_class, label):
    print(f"\nRunning PyBOP physical {label} EIS...")

    parameter_values = make_parameter_values(params)

    model = model_class(
        parameter_set=parameter_values,
        options=model_options,
        eis=True,
        var_pts=var_pts,
        solver=solver,
    )

    # Do not pass initial_state here.
    # With PyBaMM 26.4.0, some PyBOP versions call Simulation.set_initial_soc
    # with the old signature and fail. The SOC is already encoded through the
    # initial concentrations in params and through params["Initial SoC"].
    simulation = model.simulateEIS(
        inputs=None,
        f_eval=frequencies,
    )

    Z = np.asarray(simulation["Impedance"], dtype=complex)

    if np.nanmedian(-np.imag(Z)) < 0:
        Z = np.conjugate(Z)

    return Z


def run_pybop_grouped_eis(grouped_parameters):
    print("\nRunning PyBOP GroupedSPMe EIS...")

    model = pybop.lithium_ion.GroupedSPMe(
        parameter_set=copy.deepcopy(grouped_parameters),
        eis=True,
        options=model_options,
        var_pts=var_pts,
        solver=solver,
    )

    # Do not pass initial_state here.
    # With PyBaMM 26.4.0, some PyBOP versions call Simulation.set_initial_soc
    # with the old signature and fail. The SOC is already encoded through the
    # initial concentrations in params and through params["Initial SoC"].
    simulation = model.simulateEIS(
        inputs=None,
        f_eval=frequencies,
    )

    Z = np.asarray(simulation["Impedance"], dtype=complex)

    if np.nanmedian(-np.imag(Z)) < 0:
        Z = np.conjugate(Z)

    return Z


# =============================================================================
# MAIN
# =============================================================================

bpx = load_bpx(BPX_FILE)
params, diagnostics, scalar_grouping_overrides = make_aligned_physical_dict(bpx, SOC)
grouped_parameters = make_grouped_parameters(params, scalar_grouping_overrides)

capacity_Ah = params["Nominal cell capacity [A.h]"]

print("\n" + "=" * 90)
print("ALIGNED PARAMETER DIAGNOSTICS")
print("=" * 90)
print("BPX file:", BPX_FILE)
print("Nominal capacity [Ah]:", capacity_Ah)
print("Electrode area one pair [m2]:", diagnostics["area_one_pair_m2"])
print("Number parallel:", diagnostics["n_parallel"])
print("height * width [m2]:", diagnostics["height_times_width_m2"])
print("Effective area [m2]:", diagnostics["effective_area_m2"])
print("Contact resistance [Ohm]:", params["Contact resistance [Ohm]"])
print("Initial SoC used in parameter set:", params["Initial SoC"])
print("c_e0 [mol m-3]:", diagnostics["c_e0_mol_m3"])
print("D_e(c_e0) [m2 s-1]:", diagnostics["electrolyte_diffusivity_at_ce0_m2_s"])
print("kappa_e(c_e0) [S m-1]:", diagnostics["electrolyte_conductivity_at_ce0_S_m"])
print("Negative j0_ref [A m-2]:", diagnostics["negative_j0_ref_A_m2"])
print("Positive j0_ref [A m-2]:", diagnostics["positive_j0_ref_A_m2"])
print("\nGrouped parameters:")
for key in [
    "Series resistance [Ohm]",
    "Negative electrode charge transfer time scale [s]",
    "Positive electrode charge transfer time scale [s]",
    "Negative particle diffusion time scale [s]",
    "Positive particle diffusion time scale [s]",
    "Reference electrolyte capacity [A.s]",
    "Measured cell capacity [A.s]",
]:
    print(f"{key}: {grouped_parameters.get(key)}")
print("=" * 90)

# =============================================================================
# RUN THE THREE ALIGNED APPROACHES
# =============================================================================

# 1) Native PyBaMM EISSimulation
print("\nRunning native PyBaMM SPMe EIS with pybamm.EISSimulation(model, parameter_values=...)...")
print("PyBaMM version:", pybamm.__version__)
print("Has pybamm.EISSimulation:", hasattr(pybamm, "EISSimulation"))

if not hasattr(pybamm, "EISSimulation"):
    raise AttributeError(
        "pybamm.EISSimulation is not available. Restart the Jupyter kernel and "
        "make sure the notebook is using pybop_env_2 with PyBaMM 26.4.0."
    )

pybamm_parameter_values = make_parameter_values(params)
pybamm_model = pybamm.lithium_ion.SPMe(options=model_options)

pybamm_sim = pybamm.EISSimulation(
    pybamm_model,
    parameter_values=pybamm_parameter_values,
)

pybamm_result = pybamm_sim.solve(
    frequencies,
    initial_soc=SOC,
)

Z_pybamm_spme = extract_impedance_from_pybamm_result(pybamm_result)

# 2) PyBOP physical SPMe with the same aligned BPX parameters
Z_pybop_spme = run_pybop_physical_eis(params, pybop.lithium_ion.SPMe, "SPMe")

# 3) PyBOP GroupedSPMe from the same aligned BPX parameters after grouping
Z_grouped_spme = run_pybop_grouped_eis(grouped_parameters)

Z_dict = {
    "Native PyBaMM SPMe": Z_pybamm_spme,
    "PyBOP SPMe": Z_pybop_spme,
    "PyBOP GroupedSPMe": Z_grouped_spme,
}

# Scale for plotting
Z_plot_dict = {}
for label, Z in Z_dict.items():
    Z_plot_dict[label], unit_label, unit_file = capacity_scale(Z, capacity_Ah, PLOT_UNIT)

# =============================================================================
# PLOT ONE FIGURE WITH ALL THREE
# =============================================================================

fig, ax = plt.subplots(figsize=(7.5, 6.5))

for label, Zp in Z_plot_dict.items():
    ax.plot(
        np.real(Zp),
        -np.imag(Zp),
        "-o",
        markersize=3.5,
        linewidth=1.5,
        label=label,
    )

ax.set_xlabel(r"$Z_r(\omega)$ [" + unit_label + "]")
ax.set_ylabel(r"$-Z_j(\omega)$ [" + unit_label + "]")
ax.set_title(f"Aligned BPX EIS comparison, SOC = {SOC}")
ax.grid(True)
ax.set_aspect("equal", adjustable="box")
ax.legend()
fig.tight_layout()

fig_path = OUT / f"aligned_pybamm_pybop_grouped_comparison_{unit_file}.png"
fig.savefig(fig_path, dpi=300)
plt.show()

# =============================================================================
# SAVE DATA
# =============================================================================

rows = []
for label, Z in Z_dict.items():
    Zp, _, _ = capacity_scale(Z, capacity_Ah, PLOT_UNIT)
    for f, raw, plotz in zip(frequencies, Z, Zp):
        rows.append(
            {
                "Model": label,
                "Frequency [Hz]": f,
                "Z_real_raw [Ohm]": np.real(raw),
                "Z_imag_raw [Ohm]": np.imag(raw),
                "-Z_imag_raw [Ohm]": -np.imag(raw),
                f"Z_real_plot [{unit_file}]": np.real(plotz),
                f"Z_imag_plot [{unit_file}]": np.imag(plotz),
                f"-Z_imag_plot [{unit_file}]": -np.imag(plotz),
                "SOC": SOC,
                "Capacity [Ah]": capacity_Ah,
            }
        )

df = pd.DataFrame(rows)
csv_path = OUT / f"aligned_pybamm_pybop_grouped_comparison_{unit_file}.csv"
df.to_csv(csv_path, index=False)

mat_path = OUT / f"aligned_pybamm_pybop_grouped_comparison_{unit_file}.mat"
savemat(
    mat_path,
    {
        "f": frequencies,
        "Z_pybamm_spme": Z_pybamm_spme,
        "Z_pybop_spme": Z_pybop_spme,
        "Z_grouped_spme": Z_grouped_spme,
        "capacity_Ah": capacity_Ah,
        "SOC": SOC,
    },
)

diagnostics_path = OUT / "aligned_parameter_diagnostics.json"
diagnostics_to_save = {
    **diagnostics,
    "capacity_Ah": capacity_Ah,
    "contact_resistance_Ohm": CONTACT_RESISTANCE_OHM,
    "plot_unit": PLOT_UNIT,
    "grouped_parameters_selected": {
        key: float(grouped_parameters[key])
        for key in [
            "Series resistance [Ohm]",
            "Negative electrode charge transfer time scale [s]",
            "Positive electrode charge transfer time scale [s]",
            "Negative particle diffusion time scale [s]",
            "Positive particle diffusion time scale [s]",
            "Reference electrolyte capacity [A.s]",
            "Measured cell capacity [A.s]",
        ]
        if key in grouped_parameters and isinstance(grouped_parameters[key], (int, float, np.integer, np.floating))
    },
}
with open(diagnostics_path, "w", encoding="utf-8") as f:
    json.dump(diagnostics_to_save, f, indent=2)

print("\nSaved figure:", fig_path)
print("Saved CSV:", csv_path)
print("Saved MAT:", mat_path)
print("Saved diagnostics:", diagnostics_path)
print("\nDONE")


# %%
from pathlib import Path
import json
import copy

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pybamm
import pybop
from scipy.io import savemat


# =============================================================================
# USER SETTINGS
# =============================================================================

# Use your BPX/JSON parameter-set file here.
BPX_FILE = Path(
    r"C:\Users\mugi_jo\Downloads\hydr0_graphite-lnmo_schmitt-2026_validation.bpx_1_patched_for_current_bpx.json"
)

OUT = Path(
    r"C:\Users\mugi_jo\Documents\DLR_PROJECTS\bpx_aligned_pybamm_pybop_grouped_capacity_diagnostic"
)
OUT.mkdir(parents=True, exist_ok=True)

SOC = 0.5

FMIN = 2e-4
FMAX = 1e5
NFREQ = 100
frequencies = np.logspace(np.log10(FMIN), np.log10(FMAX), NFREQ)

# Use the same plotting unit for all three approaches.
# Options:
#   "ohm"      -> raw Ohm
#   "mohm"     -> mOhm
#   "mohm_Ah"  -> mOhm Ah, i.e. 1000 * Z[Ohm] * capacity[Ah]
PLOT_UNIT = "ohm"

# Plot two GroupedSPMe variants to diagnose whether the remaining difference is
# caused by capacity mismatch:
#   1) GroupedSPMe with capacity calculated by the grouping formulas
#   2) GroupedSPMe with capacity forced to the BPX nominal capacity
PLOT_BOTH_GROUPED_CAPACITY_VARIANTS = True

# BPX does not contain contact resistance. Use one shared value everywhere.
CONTACT_RESISTANCE_OHM = 0.0

# PyBaMM/PyBOP model options
model_options = {
    "surface form": "differential",
    "contact resistance": "true",
}

var_pts = {
    "x_n": 100,
    "x_s": 20,
    "x_p": 100,
    "r_n": 100,
    "r_p": 100,
}

solver = pybamm.CasadiSolver()


# =============================================================================
# BASIC HELPERS
# =============================================================================

FARADAY = 96485.33212


def fnum(x, default=None):
    if x is None:
        if default is None:
            raise ValueError("Expected a number, got None.")
        return float(default)
    return float(x)


def _pybamm_interpolant(x, y, child, name):
    """
    PyBaMM Interpolant wrapper robust to versions that expect child or [child].
    """
    try:
        return pybamm.Interpolant(
            x,
            y,
            child,
            interpolator="linear",
            name=name,
            extrapolate=True,
        )
    except TypeError:
        return pybamm.Interpolant(
            x,
            y,
            [child],
            interpolator="linear",
            name=name,
            extrapolate=True,
        )


def table_fun_1arg(table, name):
    x = np.asarray(table["x"], dtype=float)
    y = np.asarray(table["y"], dtype=float)
    order = np.argsort(x)
    x = x[order]
    y = y[order]

    def f(z):
        if isinstance(z, pybamm.Symbol):
            return _pybamm_interpolant(x, y, z, name)
        return np.interp(z, x, y)

    return f


def table_fun_ce(table, name):
    x = np.asarray(table["x"], dtype=float)
    y = np.asarray(table["y"], dtype=float)
    order = np.argsort(x)
    x = x[order]
    y = y[order]

    def f(c_e, T=None):
        if isinstance(c_e, pybamm.Symbol):
            return _pybamm_interpolant(x, y, c_e, name)
        return np.interp(c_e, x, y)

    return f


def interp_table_at(table, x0):
    xs = np.asarray(table["x"], dtype=float)
    ys = np.asarray(table["y"], dtype=float)
    order = np.argsort(xs)
    return float(np.interp(float(x0), xs[order], ys[order]))


def bruggeman_from_transport_efficiency(eps, transport_efficiency, default=1.5):
    try:
        eps = float(eps)
        transport_efficiency = float(transport_efficiency)
        if 0 < eps < 1 and transport_efficiency > 0:
            return float(np.log(transport_efficiency) / np.log(eps))
    except Exception:
        pass
    return float(default)


def state_initial_conditions(bpx):
    # Some BPX files store State at top level, this one stores it under Parameterisation.
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
    """
    PyBaMM/PyBOP-compatible exchange-current-density function.

    We use one consistent simple mapping from the BPX reaction-rate constants:
        j0_ref [A m-2] = F * k_BPX [mol m-2 s-1]
    """
    j0_ref = float(j0_ref)

    def j0(c_e, c_s_surf, c_s_max, T):
        if any(isinstance(v, pybamm.Symbol) for v in [c_e, c_s_surf, c_s_max, T]):
            return pybamm.Scalar(j0_ref)
        return j0_ref

    return j0


def capacity_scale(Z, capacity_Ah, unit):
    unit = unit.lower()
    if unit == "ohm":
        return Z, r"$\Omega$", "Ohm"
    if unit == "mohm":
        return 1000 * Z, r"m$\Omega$", "mOhm"
    if unit == "mohm_ah":
        return 1000 * Z * capacity_Ah, r"m$\Omega$ Ah", "mOhm_Ah"
    raise ValueError("PLOT_UNIT must be 'ohm', 'mohm', or 'mohm_Ah'.")


# =============================================================================
# ONE BPX -> ONE ALIGNED PHYSICAL PARAMETER DICTIONARY
# =============================================================================

def load_bpx(bpx_file):
    with open(bpx_file, "r", encoding="utf-8") as f:
        return json.load(f)


def make_aligned_physical_dict(bpx, soc):
    P = bpx["Parameterisation"]

    cell = P["Cell"]
    elyte = P["Electrolyte"]
    neg = P["Negative electrode"]
    pos = P["Positive electrode"]
    sep = P["Separator"]
    user = P.get("User-defined", {})

    ic = state_initial_conditions(bpx)
    thermal = state_thermal(bpx)

    # -------------------------------------------------------------------------
    # IMPORTANT AREA ALIGNMENT
    # -------------------------------------------------------------------------
    # Use the one-electrode-pair area for height*width, and use n_parallel
    # separately. Do NOT use total area and n_parallel at the same time.
    # This prevents area double counting.
    area_one_pair = fnum(cell["Electrode area [m2]"])
    n_parallel = fnum(
        cell.get(
            "Number of electrode pairs connected in parallel to make a cell",
            1.0,
        )
    )

    side = float(np.sqrt(area_one_pair))
    effective_area = area_one_pair * n_parallel

    # Stoichiometry/initial concentrations from the same SOC
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

    T0 = fnum(
        ic.get(
            "Initial temperature [K]",
            cell.get("Reference temperature [K]", 298.15),
        )
    )
    T_amb = fnum(thermal.get("Ambient temperature [K]", T0))

    # BPX reaction-rate constants -> constant j0 references
    k_n = fnum(neg.get("Reaction rate constant [mol.m-2.s-1]", 1e-6))
    k_p = fnum(pos.get("Reaction rate constant [mol.m-2.s-1]", 1e-6))
    j0_n_ref = FARADAY * k_n
    j0_p_ref = FARADAY * k_p

    eps_n = fnum(neg["Porosity"])
    eps_p = fnum(pos["Porosity"])
    eps_s = fnum(sep["Porosity"])

    alpha_n = fnum(
        user.get("Negative electrode active material volume fraction", 1.0 - eps_n)
    )
    alpha_p = fnum(
        user.get("Positive electrode active material volume fraction", 1.0 - eps_p)
    )

    b_n_e = bruggeman_from_transport_efficiency(
        eps_n,
        neg.get("Transport efficiency", None),
    )
    b_p_e = bruggeman_from_transport_efficiency(
        eps_p,
        pos.get("Transport efficiency", None),
    )
    b_s_e = bruggeman_from_transport_efficiency(
        eps_s,
        sep.get("Transport efficiency", None),
    )

    params = {
        "chemistry": "lithium_ion",

        # Geometry / current scaling
        "Electrode height [m]": side,
        "Electrode width [m]": side,
        "Cell volume [m3]": fnum(
            cell.get(
                "Volume [m3]",
                effective_area
                * (
                    fnum(neg["Thickness [m]"])
                    + fnum(sep["Thickness [m]"])
                    + fnum(pos["Thickness [m]"])
                ),
            )
        ),
        "Number of electrodes connected in parallel to make a cell": n_parallel,
        "Number of electrode pairs connected in parallel to make a cell": n_parallel,
        "Number of cells connected in series to make a battery": 1.0,

        # Capacity / current
        "Nominal cell capacity [A.h]": fnum(cell.get("Nominal cell capacity [A.h]", 1.0)),
        "Current function [A]": 0.0,
        "Initial SoC": float(soc),
        "Contact resistance [Ohm]": float(CONTACT_RESISTANCE_OHM),

        # Thicknesses
        "Negative electrode thickness [m]": fnum(neg["Thickness [m]"]),
        "Separator thickness [m]": fnum(sep["Thickness [m]"]),
        "Positive electrode thickness [m]": fnum(pos["Thickness [m]"]),
        "Negative current collector thickness [m]": 1.0e-5,
        "Positive current collector thickness [m]": 1.0e-5,

        # Negative electrode
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
        "Negative electrode OCP entropic change [V.K-1]": fnum(
            neg.get("Entropic change coefficient [V.K-1]", 0.0)
        ),

        # Positive electrode
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
        "Positive electrode OCP entropic change [V.K-1]": fnum(
            pos.get("Entropic change coefficient [V.K-1]", 0.0)
        ),

        # Separator
        "Separator porosity": eps_s,
        "Separator Bruggeman coefficient (electrolyte)": b_s_e,

        # Electrolyte
        "Initial concentration in electrolyte [mol.m-3]": c_e0,
        "Electrolyte diffusivity [m2.s-1]": table_fun_ce(
            elyte["Diffusivity [m2.s-1]"],
            "Electrolyte diffusivity [m2.s-1]",
        ),
        "Electrolyte conductivity [S.m-1]": table_fun_ce(
            elyte["Conductivity [S.m-1]"],
            "Electrolyte conductivity [S.m-1]",
        ),
        "Cation transference number": fnum(elyte["Cation transference number"]),
        "Thermodynamic factor": fnum(elyte.get("Thermodynamic factor", 1.0)),

        # Temperature / voltage
        "Reference temperature [K]": fnum(cell.get("Reference temperature [K]", T0)),
        "Ambient temperature [K]": T_amb,
        "Initial temperature [K]": T0,
        "Lower voltage cut-off [V]": fnum(cell["Lower voltage cut-off [V]"]),
        "Upper voltage cut-off [V]": fnum(cell["Upper voltage cut-off [V]"]),
        "Open-circuit voltage at 0% SOC [V]": fnum(
            user.get("Open-circuit voltage at 0% SOC [V]", cell["Lower voltage cut-off [V]"])
        ),
        "Open-circuit voltage at 100% SOC [V]": fnum(
            user.get("Open-circuit voltage at 100% SOC [V]", cell["Upper voltage cut-off [V]"])
        ),

        # Basic current collector properties
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
        "electrolyte_diffusivity_at_ce0_m2_s": interp_table_at(
            elyte["Diffusivity [m2.s-1]"],
            c_e0,
        ),
        "electrolyte_conductivity_at_ce0_S_m": interp_table_at(
            elyte["Conductivity [S.m-1]"],
            c_e0,
        ),
        "negative_j0_ref_A_m2": j0_n_ref,
        "positive_j0_ref_A_m2": j0_p_ref,
    }

    scalar_grouping_overrides = {
        "Electrolyte diffusivity [m2.s-1]": diagnostics["electrolyte_diffusivity_at_ce0_m2_s"],
        "Electrolyte conductivity [S.m-1]": diagnostics["electrolyte_conductivity_at_ce0_S_m"],
    }

    return params, diagnostics, scalar_grouping_overrides


def make_parameter_values(params):
    return pybamm.ParameterValues(values=dict(params))


# =============================================================================
# PYBOP GROUPING FROM THE SAME PHYSICAL PARAMETER SET
# =============================================================================

def make_grouped_parameters(params, scalar_grouping_overrides):
    """
    Create GroupedSPMe parameters from the same aligned physical BPX parameter set.

    Important:
    Physical PyBaMM/PyBOP models use:
        effective area = height * width * number_parallel

    The PyBOP grouped-parameter converter uses only:
        A = height * width

    Therefore, for the grouping step only, we put the TOTAL cell area into
    height * width and set number_parallel = 1. This prevents the grouped model
    from being about n_parallel times too large in impedance.
    """
    grouping_params = copy.deepcopy(params)

    # -------------------------------------------------------------------------
    # GROUPING AREA FIX
    # -------------------------------------------------------------------------
    # Keep the physical models as one-pair area + n_parallel.
    # But for GroupedSPMe grouping, use total effective area directly because
    # the grouping converter does not multiply by n_parallel.
    area_one_pair = (
        float(params["Electrode height [m]"])
        * float(params["Electrode width [m]"])
    )
    n_parallel = float(
        params.get("Number of electrodes connected in parallel to make a cell", 1.0)
    )
    area_total = area_one_pair * n_parallel
    side_total = float(np.sqrt(area_total))

    grouping_params["Electrode height [m]"] = side_total
    grouping_params["Electrode width [m]"] = side_total
    grouping_params["Number of electrodes connected in parallel to make a cell"] = 1.0
    grouping_params["Number of electrode pairs connected in parallel to make a cell"] = 1.0

    print("\nGrouped-parameter area correction:")
    print("  physical height*width [m2]:", area_one_pair)
    print("  physical n_parallel:", n_parallel)
    print("  grouped height*width [m2]:", area_total)

    # GroupedSPMe grouping needs scalar electrolyte properties.
    # The physical PyBaMM/PyBOP models still use the full electrolyte tables.
    grouping_params.update(scalar_grouping_overrides)

    # Compatibility with PyBOP grouping converter + PyBaMM 26.4.0
    grouping_params["Faraday constant [C.mol-1]"] = float(pybamm.constants.F.value)
    grouping_params["Ideal gas constant [J.K-1.mol-1]"] = float(pybamm.constants.R.value)

    parameter_values_for_grouping = pybamm.ParameterValues(values=grouping_params)

    from pybop.models.lithium_ion.basic_SPMe import convert_physical_to_grouped_parameters

    print("Grouping with convert_physical_to_grouped_parameters(...)")
    try:
        grouped = convert_physical_to_grouped_parameters(
            parameter_values_for_grouping,
            measured_cell_capacity_as=params["Nominal cell capacity [A.h]"] * 3600,
            check_full_cell_capacity=False,
        )
    except TypeError:
        grouped = convert_physical_to_grouped_parameters(parameter_values_for_grouping)

    # Ensure OCP functions are present for GroupedSPMe.
    grouped["Negative electrode OCP [V]"] = params["Negative electrode OCP [V]"]
    grouped["Positive electrode OCP [V]"] = params["Positive electrode OCP [V]"]

    # Preserve the capacity calculated by the grouping formulas before any override.
    grouped["Measured cell capacity from grouping [A.s]"] = float(
        grouped["Measured cell capacity [A.s]"]
    )

    # Avoid PyBOP/PyBaMM 26.4 set_initial_soc API mismatch by storing SOC
    # directly in the grouped parameter set instead of passing initial_state.
    grouped["Initial SoC"] = float(params.get("Initial SoC", SOC))

    return grouped


# =============================================================================
# EIS RUNNERS
# =============================================================================

def extract_impedance_from_pybamm_result(result):
    """Extract impedance from native PyBaMM EISSimulation output."""
    try:
        Z = np.asarray(result["Impedance [Ohm]"], dtype=complex)
    except Exception:
        Z = np.asarray(result["Impedance"], dtype=complex)

    if np.nanmedian(-np.imag(Z)) < 0:
        Z = np.conjugate(Z)

    return Z


def run_pybop_physical_eis(params, model_class, label):
    print(f"\nRunning PyBOP physical {label} EIS...")

    parameter_values = make_parameter_values(params)

    model = model_class(
        parameter_set=parameter_values,
        options=model_options,
        eis=True,
        var_pts=var_pts,
        solver=solver,
    )

    # Do not pass initial_state here.
    # With PyBaMM 26.4.0, some PyBOP versions call Simulation.set_initial_soc
    # with the old signature and fail. The SOC is already encoded through the
    # initial concentrations in params and through params["Initial SoC"].
    simulation = model.simulateEIS(
        inputs=None,
        f_eval=frequencies,
    )

    Z = np.asarray(simulation["Impedance"], dtype=complex)

    if np.nanmedian(-np.imag(Z)) < 0:
        Z = np.conjugate(Z)

    return Z


def run_pybop_grouped_eis(grouped_parameters, label="GroupedSPMe"):
    print(f"\nRunning PyBOP {label} EIS...")

    model = pybop.lithium_ion.GroupedSPMe(
        parameter_set=copy.deepcopy(grouped_parameters),
        eis=True,
        options=model_options,
        var_pts=var_pts,
        solver=solver,
    )

    # Do not pass initial_state here.
    # With PyBaMM 26.4.0, some PyBOP versions call Simulation.set_initial_soc
    # with the old signature and fail. The SOC is already encoded through the
    # initial concentrations in params and through params["Initial SoC"].
    simulation = model.simulateEIS(
        inputs=None,
        f_eval=frequencies,
    )

    Z = np.asarray(simulation["Impedance"], dtype=complex)

    if np.nanmedian(-np.imag(Z)) < 0:
        Z = np.conjugate(Z)

    return Z


# =============================================================================
# MAIN
# =============================================================================

bpx = load_bpx(BPX_FILE)
params, diagnostics, scalar_grouping_overrides = make_aligned_physical_dict(bpx, SOC)
grouped_parameters = make_grouped_parameters(params, scalar_grouping_overrides)

capacity_Ah = params["Nominal cell capacity [A.h]"]

print("\n" + "=" * 90)
print("ALIGNED PARAMETER DIAGNOSTICS")
print("=" * 90)
print("BPX file:", BPX_FILE)
print("Nominal capacity [Ah]:", capacity_Ah)
print("Electrode area one pair [m2]:", diagnostics["area_one_pair_m2"])
print("Number parallel:", diagnostics["n_parallel"])
print("height * width [m2]:", diagnostics["height_times_width_m2"])
print("Effective area [m2]:", diagnostics["effective_area_m2"])
print("Contact resistance [Ohm]:", params["Contact resistance [Ohm]"])
print("Initial SoC used in parameter set:", params["Initial SoC"])
print("c_e0 [mol m-3]:", diagnostics["c_e0_mol_m3"])
print("D_e(c_e0) [m2 s-1]:", diagnostics["electrolyte_diffusivity_at_ce0_m2_s"])
print("kappa_e(c_e0) [S m-1]:", diagnostics["electrolyte_conductivity_at_ce0_S_m"])
print("Negative j0_ref [A m-2]:", diagnostics["negative_j0_ref_A_m2"])
print("Positive j0_ref [A m-2]:", diagnostics["positive_j0_ref_A_m2"])
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
    print(f"{key}: {grouped_parameters.get(key)}")

Q_nominal_As = params["Nominal cell capacity [A.h]"] * 3600
Q_grouping_As = float(grouped_parameters["Measured cell capacity from grouping [A.s]"])
print("\nCapacity check:")
print("Nominal BPX capacity [A.s]:", Q_nominal_As)
print("Grouped formula capacity [A.s]:", Q_grouping_As)
print("Grouped / nominal capacity ratio:", Q_grouping_As / Q_nominal_As)
print("=" * 90)

# =============================================================================
# RUN THE THREE ALIGNED APPROACHES
# =============================================================================

# 1) Native PyBaMM EISSimulation
print("\nRunning native PyBaMM SPMe EIS with pybamm.EISSimulation(model, parameter_values=...)...")
print("PyBaMM version:", pybamm.__version__)
print("Has pybamm.EISSimulation:", hasattr(pybamm, "EISSimulation"))

if not hasattr(pybamm, "EISSimulation"):
    raise AttributeError(
        "pybamm.EISSimulation is not available. Restart the Jupyter kernel and "
        "make sure the notebook is using pybop_env_2 with PyBaMM 26.4.0."
    )

pybamm_parameter_values = make_parameter_values(params)
pybamm_model = pybamm.lithium_ion.SPMe(options=model_options)

pybamm_sim = pybamm.EISSimulation(
    pybamm_model,
    parameter_values=pybamm_parameter_values,
)

pybamm_result = pybamm_sim.solve(
    frequencies,
    initial_soc=SOC,
)

Z_pybamm_spme = extract_impedance_from_pybamm_result(pybamm_result)

# 2) PyBOP physical SPMe with the same aligned BPX parameters
Z_pybop_spme = run_pybop_physical_eis(params, pybop.lithium_ion.SPMe, "SPMe")

# 3) PyBOP GroupedSPMe from the same aligned BPX parameters after grouping
#    Variant A: keep the measured capacity calculated by the grouping formulas
grouped_geometry_capacity = copy.deepcopy(grouped_parameters)
grouped_geometry_capacity["Measured cell capacity [A.s]"] = float(
    grouped_parameters["Measured cell capacity from grouping [A.s]"]
)

#    Variant B: force the grouped model to use the BPX nominal capacity
grouped_nominal_capacity = copy.deepcopy(grouped_parameters)
grouped_nominal_capacity["Measured cell capacity [A.s]"] = (
    params["Nominal cell capacity [A.h]"] * 3600
)

Z_grouped_geometry_capacity = run_pybop_grouped_eis(
    grouped_geometry_capacity,
    label="GroupedSPMe, grouped capacity",
)

if PLOT_BOTH_GROUPED_CAPACITY_VARIANTS:
    Z_grouped_nominal_capacity = run_pybop_grouped_eis(
        grouped_nominal_capacity,
        label="GroupedSPMe, nominal BPX capacity",
    )
else:
    Z_grouped_nominal_capacity = None

Z_dict = {
    "Native PyBaMM SPMe": Z_pybamm_spme,
    "PyBOP SPMe": Z_pybop_spme,
    "GroupedSPMe, grouped Q": Z_grouped_geometry_capacity,
}

if PLOT_BOTH_GROUPED_CAPACITY_VARIANTS:
    Z_dict["GroupedSPMe, nominal Q"] = Z_grouped_nominal_capacity

# Scale for plotting
Z_plot_dict = {}
for label, Z in Z_dict.items():
    Z_plot_dict[label], unit_label, unit_file = capacity_scale(Z, capacity_Ah, PLOT_UNIT)

# =============================================================================
# PLOT ONE FIGURE WITH ALL THREE
# =============================================================================

fig, ax = plt.subplots(figsize=(7.5, 6.5))

for label, Zp in Z_plot_dict.items():
    ax.plot(
        np.real(Zp),
        -np.imag(Zp),
        "-o",
        markersize=3.5,
        linewidth=1.5,
        label=label,
    )

ax.set_xlabel(r"$Z_r(\omega)$ [" + unit_label + "]")
ax.set_ylabel(r"$-Z_j(\omega)$ [" + unit_label + "]")
ax.set_title(f"Aligned BPX EIS comparison, SOC = {SOC}")
ax.grid(True)
ax.set_aspect("equal", adjustable="box")
ax.legend()
fig.tight_layout()

fig_path = OUT / f"aligned_pybamm_pybop_grouped_comparison_{unit_file}.png"
fig.savefig(fig_path, dpi=300)
plt.show()

# =============================================================================
# SAVE DATA
# =============================================================================

# rows = []
# for label, Z in Z_dict.items():
#     Zp, _, _ = capacity_scale(Z, capacity_Ah, PLOT_UNIT)
#     for f, raw, plotz in zip(frequencies, Z, Zp):
#         rows.append(
#             {
#                 "Model": label,
#                 "Frequency [Hz]": f,
#                 "Z_real_raw [Ohm]": np.real(raw),
#                 "Z_imag_raw [Ohm]": np.imag(raw),
#                 "-Z_imag_raw [Ohm]": -np.imag(raw),
#                 f"Z_real_plot [{unit_file}]": np.real(plotz),
#                 f"Z_imag_plot [{unit_file}]": np.imag(plotz),
#                 f"-Z_imag_plot [{unit_file}]": -np.imag(plotz),
#                 "SOC": SOC,
#                 "Capacity [Ah]": capacity_Ah,
#             }
#         )

# df = pd.DataFrame(rows)
# csv_path = OUT / f"aligned_pybamm_pybop_grouped_comparison_{unit_file}.csv"
# df.to_csv(csv_path, index=False)

# mat_path = OUT / f"aligned_pybamm_pybop_grouped_comparison_{unit_file}.mat"
# savemat(
#     mat_path,
#     {
#         "f": frequencies,
#         "Z_pybamm_spme": Z_pybamm_spme,
#         "Z_pybop_spme": Z_pybop_spme,
#         "Z_grouped_geometry_capacity": Z_grouped_geometry_capacity,
#         "Z_grouped_nominal_capacity": Z_grouped_nominal_capacity
#             if Z_grouped_nominal_capacity is not None
#             else np.array([]),
#         "grouped_capacity_from_grouping_As": Q_grouping_As,
#         "nominal_capacity_As": Q_nominal_As,
#         "capacity_Ah": capacity_Ah,
#         "SOC": SOC,
#     },
# )

# diagnostics_path = OUT / "aligned_parameter_diagnostics.json"
# diagnostics_to_save = {
#     **diagnostics,
#     "capacity_Ah": capacity_Ah,
#     "contact_resistance_Ohm": CONTACT_RESISTANCE_OHM,
#     "plot_unit": PLOT_UNIT,
#     "grouped_parameters_selected": {
#         key: float(grouped_parameters[key])
#         for key in [
#             "Series resistance [Ohm]",
#             "Negative electrode charge transfer time scale [s]",
#             "Positive electrode charge transfer time scale [s]",
#             "Negative particle diffusion time scale [s]",
#             "Positive particle diffusion time scale [s]",
#             "Reference electrolyte capacity [A.s]",
#             "Measured cell capacity [A.s]",
#             "Measured cell capacity from grouping [A.s]",
#         ]
#         if key in grouped_parameters and isinstance(grouped_parameters[key], (int, float, np.integer, np.floating))
#     },
# }
# with open(diagnostics_path, "w", encoding="utf-8") as f:
#     json.dump(diagnostics_to_save, f, indent=2)

# print("\nSaved figure:", fig_path)
# print("Saved CSV:", csv_path)
# print("Saved MAT:", mat_path)
# print("Saved diagnostics:", diagnostics_path)
# print("\nDONE")


# %%
from pathlib import Path
import json
import copy

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pybamm
import pybop
from scipy.io import savemat


# =============================================================================
# USER SETTINGS
# =============================================================================

# Use your BPX/JSON parameter-set file here.
BPX_FILE = Path(
    r"C:\Users\mugi_jo\Downloads\hydr0_graphite-lnmo_schmitt-2026_validation.bpx_1_patched_for_current_bpx.json"
)

OUT = Path(
    r"C:\Users\mugi_jo\Documents\DLR_PROJECTS\bpx_aligned_pybamm_pybop_grouped_tau_ct_diagnostic"
)
OUT.mkdir(parents=True, exist_ok=True)

SOC = 0.5

FMIN = 2e-4
FMAX = 1e5
NFREQ = 100
frequencies = np.logspace(np.log10(FMIN), np.log10(FMAX), NFREQ)

# Use the same plotting unit for all three approaches.
# Options:
#   "ohm"      -> raw Ohm
#   "mohm"     -> mOhm
#   "mohm_Ah"  -> mOhm Ah, i.e. 1000 * Z[Ohm] * capacity[Ah]
PLOT_UNIT = "ohm"

# Plot two GroupedSPMe variants to diagnose whether the remaining difference is
# caused by capacity mismatch:
#   1) GroupedSPMe with capacity calculated by the grouping formulas
#   2) GroupedSPMe with capacity forced to the BPX nominal capacity
PLOT_BOTH_GROUPED_CAPACITY_VARIANTS = True

# Extra diagnostic:
# The capacity test usually shows that grouped Q and nominal Q overlap.
# The next likely cause of the large GroupedSPMe arc is the grouped
# charge-transfer time scale. Smaller tau_ct means faster kinetics and
# smaller charge-transfer impedance.
RUN_GROUPED_TAU_CT_DIAGNOSTIC = True
TAU_CT_MULTIPLIERS = [ 0.12]

# BPX does not contain contact resistance. Use one shared value everywhere.
CONTACT_RESISTANCE_OHM = 0.0

# PyBaMM/PyBOP model options
model_options = {
    "surface form": "differential",
    "contact resistance": "true",
}

var_pts = {
    "x_n": 100,
    "x_s": 20,
    "x_p": 100,
    "r_n": 100,
    "r_p": 100,
}

solver = pybamm.CasadiSolver()


# =============================================================================
# BASIC HELPERS
# =============================================================================

FARADAY = 96485.33212


def fnum(x, default=None):
    if x is None:
        if default is None:
            raise ValueError("Expected a number, got None.")
        return float(default)
    return float(x)


def _pybamm_interpolant(x, y, child, name):
    """
    PyBaMM Interpolant wrapper robust to versions that expect child or [child].
    """
    try:
        return pybamm.Interpolant(
            x,
            y,
            child,
            interpolator="linear",
            name=name,
            extrapolate=True,
        )
    except TypeError:
        return pybamm.Interpolant(
            x,
            y,
            [child],
            interpolator="linear",
            name=name,
            extrapolate=True,
        )


def table_fun_1arg(table, name):
    x = np.asarray(table["x"], dtype=float)
    y = np.asarray(table["y"], dtype=float)
    order = np.argsort(x)
    x = x[order]
    y = y[order]

    def f(z):
        if isinstance(z, pybamm.Symbol):
            return _pybamm_interpolant(x, y, z, name)
        return np.interp(z, x, y)

    return f


def table_fun_ce(table, name):
    x = np.asarray(table["x"], dtype=float)
    y = np.asarray(table["y"], dtype=float)
    order = np.argsort(x)
    x = x[order]
    y = y[order]

    def f(c_e, T=None):
        if isinstance(c_e, pybamm.Symbol):
            return _pybamm_interpolant(x, y, c_e, name)
        return np.interp(c_e, x, y)

    return f


def interp_table_at(table, x0):
    xs = np.asarray(table["x"], dtype=float)
    ys = np.asarray(table["y"], dtype=float)
    order = np.argsort(xs)
    return float(np.interp(float(x0), xs[order], ys[order]))


def bruggeman_from_transport_efficiency(eps, transport_efficiency, default=1.5):
    try:
        eps = float(eps)
        transport_efficiency = float(transport_efficiency)
        if 0 < eps < 1 and transport_efficiency > 0:
            return float(np.log(transport_efficiency) / np.log(eps))
    except Exception:
        pass
    return float(default)


def state_initial_conditions(bpx):
    # Some BPX files store State at top level, this one stores it under Parameterisation.
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
    """
    PyBaMM/PyBOP-compatible exchange-current-density function.

    We use one consistent simple mapping from the BPX reaction-rate constants:
        j0_ref [A m-2] = F * k_BPX [mol m-2 s-1]
    """
    j0_ref = float(j0_ref)

    def j0(c_e, c_s_surf, c_s_max, T):
        if any(isinstance(v, pybamm.Symbol) for v in [c_e, c_s_surf, c_s_max, T]):
            return pybamm.Scalar(j0_ref)
        return j0_ref

    return j0


def capacity_scale(Z, capacity_Ah, unit):
    unit = unit.lower()
    if unit == "ohm":
        return Z, r"$\Omega$", "Ohm"
    if unit == "mohm":
        return 1000 * Z, r"m$\Omega$", "mOhm"
    if unit == "mohm_ah":
        return 1000 * Z * capacity_Ah, r"m$\Omega$ Ah", "mOhm_Ah"
    raise ValueError("PLOT_UNIT must be 'ohm', 'mohm', or 'mohm_Ah'.")


# =============================================================================
# ONE BPX -> ONE ALIGNED PHYSICAL PARAMETER DICTIONARY
# =============================================================================

def load_bpx(bpx_file):
    with open(bpx_file, "r", encoding="utf-8") as f:
        return json.load(f)


def make_aligned_physical_dict(bpx, soc):
    P = bpx["Parameterisation"]

    cell = P["Cell"]
    elyte = P["Electrolyte"]
    neg = P["Negative electrode"]
    pos = P["Positive electrode"]
    sep = P["Separator"]
    user = P.get("User-defined", {})

    ic = state_initial_conditions(bpx)
    thermal = state_thermal(bpx)

    # -------------------------------------------------------------------------
    # IMPORTANT AREA ALIGNMENT
    # -------------------------------------------------------------------------
    # Use the one-electrode-pair area for height*width, and use n_parallel
    # separately. Do NOT use total area and n_parallel at the same time.
    # This prevents area double counting.
    area_one_pair = fnum(cell["Electrode area [m2]"])
    n_parallel = fnum(
        cell.get(
            "Number of electrode pairs connected in parallel to make a cell",
            1.0,
        )
    )

    side = float(np.sqrt(area_one_pair))
    effective_area = area_one_pair * n_parallel

    # Stoichiometry/initial concentrations from the same SOC
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

    T0 = fnum(
        ic.get(
            "Initial temperature [K]",
            cell.get("Reference temperature [K]", 298.15),
        )
    )
    T_amb = fnum(thermal.get("Ambient temperature [K]", T0))

    # BPX reaction-rate constants -> constant j0 references
    k_n = fnum(neg.get("Reaction rate constant [mol.m-2.s-1]", 1e-6))
    k_p = fnum(pos.get("Reaction rate constant [mol.m-2.s-1]", 1e-6))
    j0_n_ref = FARADAY * k_n
    j0_p_ref = FARADAY * k_p

    eps_n = fnum(neg["Porosity"])
    eps_p = fnum(pos["Porosity"])
    eps_s = fnum(sep["Porosity"])

    alpha_n = fnum(
        user.get("Negative electrode active material volume fraction", 1.0 - eps_n)
    )
    alpha_p = fnum(
        user.get("Positive electrode active material volume fraction", 1.0 - eps_p)
    )

    b_n_e = bruggeman_from_transport_efficiency(
        eps_n,
        neg.get("Transport efficiency", None),
    )
    b_p_e = bruggeman_from_transport_efficiency(
        eps_p,
        pos.get("Transport efficiency", None),
    )
    b_s_e = bruggeman_from_transport_efficiency(
        eps_s,
        sep.get("Transport efficiency", None),
    )

    params = {
        "chemistry": "lithium_ion",

        # Geometry / current scaling
        "Electrode height [m]": side,
        "Electrode width [m]": side,
        "Cell volume [m3]": fnum(
            cell.get(
                "Volume [m3]",
                effective_area
                * (
                    fnum(neg["Thickness [m]"])
                    + fnum(sep["Thickness [m]"])
                    + fnum(pos["Thickness [m]"])
                ),
            )
        ),
        "Number of electrodes connected in parallel to make a cell": n_parallel,
        "Number of electrode pairs connected in parallel to make a cell": n_parallel,
        "Number of cells connected in series to make a battery": 1.0,

        # Capacity / current
        "Nominal cell capacity [A.h]": fnum(cell.get("Nominal cell capacity [A.h]", 1.0)),
        "Current function [A]": 0.0,
        "Initial SoC": float(soc),
        "Contact resistance [Ohm]": float(CONTACT_RESISTANCE_OHM),

        # Thicknesses
        "Negative electrode thickness [m]": fnum(neg["Thickness [m]"]),
        "Separator thickness [m]": fnum(sep["Thickness [m]"]),
        "Positive electrode thickness [m]": fnum(pos["Thickness [m]"]),
        "Negative current collector thickness [m]": 1.0e-5,
        "Positive current collector thickness [m]": 1.0e-5,

        # Negative electrode
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
        "Negative electrode OCP entropic change [V.K-1]": fnum(
            neg.get("Entropic change coefficient [V.K-1]", 0.0)
        ),

        # Positive electrode
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
        "Positive electrode OCP entropic change [V.K-1]": fnum(
            pos.get("Entropic change coefficient [V.K-1]", 0.0)
        ),

        # Separator
        "Separator porosity": eps_s,
        "Separator Bruggeman coefficient (electrolyte)": b_s_e,

        # Electrolyte
        "Initial concentration in electrolyte [mol.m-3]": c_e0,
        "Electrolyte diffusivity [m2.s-1]": table_fun_ce(
            elyte["Diffusivity [m2.s-1]"],
            "Electrolyte diffusivity [m2.s-1]",
        ),
        "Electrolyte conductivity [S.m-1]": table_fun_ce(
            elyte["Conductivity [S.m-1]"],
            "Electrolyte conductivity [S.m-1]",
        ),
        "Cation transference number": fnum(elyte["Cation transference number"]),
        "Thermodynamic factor": fnum(elyte.get("Thermodynamic factor", 1.0)),

        # Temperature / voltage
        "Reference temperature [K]": fnum(cell.get("Reference temperature [K]", T0)),
        "Ambient temperature [K]": T_amb,
        "Initial temperature [K]": T0,
        "Lower voltage cut-off [V]": fnum(cell["Lower voltage cut-off [V]"]),
        "Upper voltage cut-off [V]": fnum(cell["Upper voltage cut-off [V]"]),
        "Open-circuit voltage at 0% SOC [V]": fnum(
            user.get("Open-circuit voltage at 0% SOC [V]", cell["Lower voltage cut-off [V]"])
        ),
        "Open-circuit voltage at 100% SOC [V]": fnum(
            user.get("Open-circuit voltage at 100% SOC [V]", cell["Upper voltage cut-off [V]"])
        ),

        # Basic current collector properties
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
        "electrolyte_diffusivity_at_ce0_m2_s": interp_table_at(
            elyte["Diffusivity [m2.s-1]"],
            c_e0,
        ),
        "electrolyte_conductivity_at_ce0_S_m": interp_table_at(
            elyte["Conductivity [S.m-1]"],
            c_e0,
        ),
        "negative_j0_ref_A_m2": j0_n_ref,
        "positive_j0_ref_A_m2": j0_p_ref,
    }

    scalar_grouping_overrides = {
        "Electrolyte diffusivity [m2.s-1]": diagnostics["electrolyte_diffusivity_at_ce0_m2_s"],
        "Electrolyte conductivity [S.m-1]": diagnostics["electrolyte_conductivity_at_ce0_S_m"],
    }

    return params, diagnostics, scalar_grouping_overrides


def make_parameter_values(params):
    return pybamm.ParameterValues(values=dict(params))


# =============================================================================
# PYBOP GROUPING FROM THE SAME PHYSICAL PARAMETER SET
# =============================================================================

def make_grouped_parameters(params, scalar_grouping_overrides):
    """
    Create GroupedSPMe parameters from the same aligned physical BPX parameter set.

    Important:
    Physical PyBaMM/PyBOP models use:
        effective area = height * width * number_parallel

    The PyBOP grouped-parameter converter uses only:
        A = height * width

    Therefore, for the grouping step only, we put the TOTAL cell area into
    height * width and set number_parallel = 1. This prevents the grouped model
    from being about n_parallel times too large in impedance.
    """
    grouping_params = copy.deepcopy(params)

    # -------------------------------------------------------------------------
    # GROUPING AREA FIX
    # -------------------------------------------------------------------------
    # Keep the physical models as one-pair area + n_parallel.
    # But for GroupedSPMe grouping, use total effective area directly because
    # the grouping converter does not multiply by n_parallel.
    area_one_pair = (
        float(params["Electrode height [m]"])
        * float(params["Electrode width [m]"])
    )
    n_parallel = float(
        params.get("Number of electrodes connected in parallel to make a cell", 1.0)
    )
    area_total = area_one_pair * n_parallel
    side_total = float(np.sqrt(area_total))

    grouping_params["Electrode height [m]"] = side_total
    grouping_params["Electrode width [m]"] = side_total
    grouping_params["Number of electrodes connected in parallel to make a cell"] = 1.0
    grouping_params["Number of electrode pairs connected in parallel to make a cell"] = 1.0

    print("\nGrouped-parameter area correction:")
    print("  physical height*width [m2]:", area_one_pair)
    print("  physical n_parallel:", n_parallel)
    print("  grouped height*width [m2]:", area_total)

    # GroupedSPMe grouping needs scalar electrolyte properties.
    # The physical PyBaMM/PyBOP models still use the full electrolyte tables.
    grouping_params.update(scalar_grouping_overrides)

    # Compatibility with PyBOP grouping converter + PyBaMM 26.4.0
    grouping_params["Faraday constant [C.mol-1]"] = float(pybamm.constants.F.value)
    grouping_params["Ideal gas constant [J.K-1.mol-1]"] = float(pybamm.constants.R.value)

    parameter_values_for_grouping = pybamm.ParameterValues(values=grouping_params)

    from pybop.models.lithium_ion.basic_SPMe import convert_physical_to_grouped_parameters

    print("Grouping with convert_physical_to_grouped_parameters(...)")
    try:
        grouped = convert_physical_to_grouped_parameters(
            parameter_values_for_grouping,
            measured_cell_capacity_as=params["Nominal cell capacity [A.h]"] * 3600,
            check_full_cell_capacity=False,
        )
    except TypeError:
        grouped = convert_physical_to_grouped_parameters(parameter_values_for_grouping)

    # Ensure OCP functions are present for GroupedSPMe.
    grouped["Negative electrode OCP [V]"] = params["Negative electrode OCP [V]"]
    grouped["Positive electrode OCP [V]"] = params["Positive electrode OCP [V]"]

    # Preserve the capacity calculated by the grouping formulas before any override.
    grouped["Measured cell capacity from grouping [A.s]"] = float(
        grouped["Measured cell capacity [A.s]"]
    )

    # Avoid PyBOP/PyBaMM 26.4 set_initial_soc API mismatch by storing SOC
    # directly in the grouped parameter set instead of passing initial_state.
    grouped["Initial SoC"] = float(params.get("Initial SoC", SOC))

    return grouped


# =============================================================================
# EIS RUNNERS
# =============================================================================

def extract_impedance_from_pybamm_result(result):
    """Extract impedance from native PyBaMM EISSimulation output."""
    try:
        Z = np.asarray(result["Impedance [Ohm]"], dtype=complex)
    except Exception:
        Z = np.asarray(result["Impedance"], dtype=complex)

    if np.nanmedian(-np.imag(Z)) < 0:
        Z = np.conjugate(Z)

    return Z


def run_pybop_physical_eis(params, model_class, label):
    print(f"\nRunning PyBOP physical {label} EIS...")

    parameter_values = make_parameter_values(params)

    model = model_class(
        parameter_set=parameter_values,
        options=model_options,
        eis=True,
        var_pts=var_pts,
        solver=solver,
    )

    # Do not pass initial_state here.
    # With PyBaMM 26.4.0, some PyBOP versions call Simulation.set_initial_soc
    # with the old signature and fail. The SOC is already encoded through the
    # initial concentrations in params and through params["Initial SoC"].
    simulation = model.simulateEIS(
        inputs=None,
        f_eval=frequencies,
    )

    Z = np.asarray(simulation["Impedance"], dtype=complex)

    if np.nanmedian(-np.imag(Z)) < 0:
        Z = np.conjugate(Z)

    return Z


def run_pybop_grouped_eis(grouped_parameters, label="GroupedSPMe"):
    print(f"\nRunning PyBOP {label} EIS...")

    model = pybop.lithium_ion.GroupedSPMe(
        parameter_set=copy.deepcopy(grouped_parameters),
        eis=True,
        options=model_options,
        var_pts=var_pts,
        solver=solver,
    )

    # Do not pass initial_state here.
    # With PyBaMM 26.4.0, some PyBOP versions call Simulation.set_initial_soc
    # with the old signature and fail. The SOC is already encoded through the
    # initial concentrations in params and through params["Initial SoC"].
    simulation = model.simulateEIS(
        inputs=None,
        f_eval=frequencies,
    )

    Z = np.asarray(simulation["Impedance"], dtype=complex)

    if np.nanmedian(-np.imag(Z)) < 0:
        Z = np.conjugate(Z)

    return Z


# =============================================================================
# MAIN
# =============================================================================

bpx = load_bpx(BPX_FILE)
params, diagnostics, scalar_grouping_overrides = make_aligned_physical_dict(bpx, SOC)
grouped_parameters = make_grouped_parameters(params, scalar_grouping_overrides)

capacity_Ah = params["Nominal cell capacity [A.h]"]

print("\n" + "=" * 90)
print("ALIGNED PARAMETER DIAGNOSTICS")
print("=" * 90)
print("BPX file:", BPX_FILE)
print("Nominal capacity [Ah]:", capacity_Ah)
print("Electrode area one pair [m2]:", diagnostics["area_one_pair_m2"])
print("Number parallel:", diagnostics["n_parallel"])
print("height * width [m2]:", diagnostics["height_times_width_m2"])
print("Effective area [m2]:", diagnostics["effective_area_m2"])
print("Contact resistance [Ohm]:", params["Contact resistance [Ohm]"])
print("Initial SoC used in parameter set:", params["Initial SoC"])
print("c_e0 [mol m-3]:", diagnostics["c_e0_mol_m3"])
print("D_e(c_e0) [m2 s-1]:", diagnostics["electrolyte_diffusivity_at_ce0_m2_s"])
print("kappa_e(c_e0) [S m-1]:", diagnostics["electrolyte_conductivity_at_ce0_S_m"])
print("Negative j0_ref [A m-2]:", diagnostics["negative_j0_ref_A_m2"])
print("Positive j0_ref [A m-2]:", diagnostics["positive_j0_ref_A_m2"])
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
    print(f"{key}: {grouped_parameters.get(key)}")

Q_nominal_As = params["Nominal cell capacity [A.h]"] * 3600
Q_grouping_As = float(grouped_parameters["Measured cell capacity from grouping [A.s]"])
print("\nCapacity check:")
print("Nominal BPX capacity [A.s]:", Q_nominal_As)
print("Grouped formula capacity [A.s]:", Q_grouping_As)
print("Grouped / nominal capacity ratio:", Q_grouping_As / Q_nominal_As)
print("=" * 90)

# =============================================================================
# RUN THE THREE ALIGNED APPROACHES
# =============================================================================

# 1) Native PyBaMM EISSimulation
print("\nRunning native PyBaMM SPMe EIS with pybamm.EISSimulation(model, parameter_values=...)...")
print("PyBaMM version:", pybamm.__version__)
print("Has pybamm.EISSimulation:", hasattr(pybamm, "EISSimulation"))

if not hasattr(pybamm, "EISSimulation"):
    raise AttributeError(
        "pybamm.EISSimulation is not available. Restart the Jupyter kernel and "
        "make sure the notebook is using pybop_env_2 with PyBaMM 26.4.0."
    )

pybamm_parameter_values = make_parameter_values(params)
pybamm_model = pybamm.lithium_ion.SPMe(options=model_options)

pybamm_sim = pybamm.EISSimulation(
    pybamm_model,
    parameter_values=pybamm_parameter_values,
)

pybamm_result = pybamm_sim.solve(
    frequencies,
    initial_soc=SOC,
)

Z_pybamm_spme = extract_impedance_from_pybamm_result(pybamm_result)

# 2) PyBOP physical SPMe with the same aligned BPX parameters
Z_pybop_spme = run_pybop_physical_eis(params, pybop.lithium_ion.SPMe, "SPMe")

# 3) PyBOP GroupedSPMe from the same aligned BPX parameters after grouping
#    Variant A: keep the measured capacity calculated by the grouping formulas
grouped_geometry_capacity = copy.deepcopy(grouped_parameters)
grouped_geometry_capacity["Measured cell capacity [A.s]"] = float(
    grouped_parameters["Measured cell capacity from grouping [A.s]"]
)

#    Variant B: force the grouped model to use the BPX nominal capacity
grouped_nominal_capacity = copy.deepcopy(grouped_parameters)
grouped_nominal_capacity["Measured cell capacity [A.s]"] = (
    params["Nominal cell capacity [A.h]"] * 3600
)

Z_grouped_geometry_capacity = run_pybop_grouped_eis(
    grouped_geometry_capacity,
    label="GroupedSPMe, grouped capacity",
)

if PLOT_BOTH_GROUPED_CAPACITY_VARIANTS:
    Z_grouped_nominal_capacity = run_pybop_grouped_eis(
        grouped_nominal_capacity,
        label="GroupedSPMe, nominal BPX capacity",
    )
else:
    Z_grouped_nominal_capacity = None

Z_dict = {
    "Native PyBaMM SPMe": Z_pybamm_spme,
    "PyBOP SPMe": Z_pybop_spme,
    "GroupedSPMe, grouped Q": Z_grouped_geometry_capacity,
}

if PLOT_BOTH_GROUPED_CAPACITY_VARIANTS:
    Z_dict["GroupedSPMe, nominal Q"] = Z_grouped_nominal_capacity

# -------------------------------------------------------------------------
# Optional tau_ct diagnostic
# -------------------------------------------------------------------------
# If grouped Q and nominal Q overlap, capacity is not responsible for the
# large GroupedSPMe arc. Then vary both grouped charge-transfer time scales.
Z_grouped_tau_ct = {}

if RUN_GROUPED_TAU_CT_DIAGNOSTIC:
    print("\n" + "=" * 90)
    print("GROUPED tau_ct DIAGNOSTIC")
    print("=" * 90)
    print("Original negative tau_ct [s]:", grouped_nominal_capacity["Negative electrode charge transfer time scale [s]"])
    print("Original positive tau_ct [s]:", grouped_nominal_capacity["Positive electrode charge transfer time scale [s]"])

    for multiplier in TAU_CT_MULTIPLIERS:
        grouped_tau = copy.deepcopy(grouped_nominal_capacity)

        grouped_tau["Negative electrode charge transfer time scale [s]"] = (
            float(grouped_tau["Negative electrode charge transfer time scale [s]"])
            * multiplier
        )
        grouped_tau["Positive electrode charge transfer time scale [s]"] = (
            float(grouped_tau["Positive electrode charge transfer time scale [s]"])
            * multiplier
        )

        label = f"GroupedSPMe tau_ct x {multiplier:g}"

        Z_grouped_tau_ct[label] = run_pybop_grouped_eis(
            grouped_tau,
            label=label,
        )

    print("=" * 90)

# Scale for plotting
Z_plot_dict = {}
for label, Z in Z_dict.items():
    Z_plot_dict[label], unit_label, unit_file = capacity_scale(Z, capacity_Ah, PLOT_UNIT)

# =============================================================================
# PLOT ONE FIGURE WITH ALL THREE
# =============================================================================

fig, ax = plt.subplots(figsize=(7.5, 6.5))

for label, Zp in Z_plot_dict.items():
    ax.plot(
        np.real(Zp),
        -np.imag(Zp),
        "-o",
        markersize=3.5,
        linewidth=1.5,
        label=label,
    )

ax.set_xlabel(r"$Z_r(\omega)$ [" + unit_label + "]")
ax.set_ylabel(r"$-Z_j(\omega)$ [" + unit_label + "]")
ax.set_title(f"Aligned BPX EIS comparison, SOC = {SOC}")
ax.grid(True)
ax.set_aspect("equal", adjustable="box")
ax.legend()
fig.tight_layout()

fig_path = OUT / f"aligned_pybamm_pybop_grouped_comparison_{unit_file}.png"
fig.savefig(fig_path, dpi=300)
plt.show()


# =============================================================================
# EXTRA PLOT: GROUPED tau_ct DIAGNOSTIC
# =============================================================================

if RUN_GROUPED_TAU_CT_DIAGNOSTIC:
    fig_tau, ax_tau = plt.subplots(figsize=(7.5, 6.5))

    # Reference physical models
    for label in ["Native PyBaMM SPMe", "PyBOP SPMe"]:
        Zp, _, _ = capacity_scale(Z_dict[label], capacity_Ah, PLOT_UNIT)
        ax_tau.plot(
            np.real(Zp),
            -np.imag(Zp),
            "-o",
            markersize=3.5,
            linewidth=1.5,
            label=label,
        )

    # Grouped tau_ct sweep
    for label, Z in Z_grouped_tau_ct.items():
        Zp, _, _ = capacity_scale(Z, capacity_Ah, PLOT_UNIT)
        ax_tau.plot(
            np.real(Zp),
            -np.imag(Zp),
            "-o",
            markersize=3.0,
            linewidth=1.3,
            label=label,
        )

    ax_tau.set_xlabel(r"$Z_r(\omega)$ [" + unit_label + "]")
    ax_tau.set_ylabel(r"$-Z_j(\omega)$ [" + unit_label + "]")
    ax_tau.set_title(f"GroupedSPMe charge-transfer time-scale diagnostic, SOC = {SOC}")
    ax_tau.grid(True)
    ax_tau.set_aspect("equal", adjustable="box")
    ax_tau.legend(fontsize=8)
    fig_tau.tight_layout()

    fig_tau_path = OUT / f"grouped_tau_ct_diagnostic_{unit_file}.png"
    fig_tau.savefig(fig_tau_path, dpi=300)
    plt.show()

# # =============================================================================
# # SAVE DATA
# # =============================================================================

# rows = []
# for label, Z in Z_dict.items():
#     Zp, _, _ = capacity_scale(Z, capacity_Ah, PLOT_UNIT)
#     for f, raw, plotz in zip(frequencies, Z, Zp):
#         rows.append(
#             {
#                 "Model": label,
#                 "Frequency [Hz]": f,
#                 "Z_real_raw [Ohm]": np.real(raw),
#                 "Z_imag_raw [Ohm]": np.imag(raw),
#                 "-Z_imag_raw [Ohm]": -np.imag(raw),
#                 f"Z_real_plot [{unit_file}]": np.real(plotz),
#                 f"Z_imag_plot [{unit_file}]": np.imag(plotz),
#                 f"-Z_imag_plot [{unit_file}]": -np.imag(plotz),
#                 "SOC": SOC,
#                 "Capacity [Ah]": capacity_Ah,
#             }
#         )

# if RUN_GROUPED_TAU_CT_DIAGNOSTIC:
#     for label, Z in Z_grouped_tau_ct.items():
#         Zp, _, _ = capacity_scale(Z, capacity_Ah, PLOT_UNIT)
#         for f, raw, plotz in zip(frequencies, Z, Zp):
#             rows.append(
#                 {
#                     "Model": label,
#                     "Frequency [Hz]": f,
#                     "Z_real_raw [Ohm]": np.real(raw),
#                     "Z_imag_raw [Ohm]": np.imag(raw),
#                     "-Z_imag_raw [Ohm]": -np.imag(raw),
#                     f"Z_real_plot [{unit_file}]": np.real(plotz),
#                     f"Z_imag_plot [{unit_file}]": np.imag(plotz),
#                     f"-Z_imag_plot [{unit_file}]": -np.imag(plotz),
#                     "SOC": SOC,
#                     "Capacity [Ah]": capacity_Ah,
#                 }
#             )

# df = pd.DataFrame(rows)
# csv_path = OUT / f"aligned_pybamm_pybop_grouped_comparison_{unit_file}.csv"
# df.to_csv(csv_path, index=False)

# mat_path = OUT / f"aligned_pybamm_pybop_grouped_comparison_{unit_file}.mat"
# savemat(
#     mat_path,
#     {
#         "f": frequencies,
#         "Z_pybamm_spme": Z_pybamm_spme,
#         "Z_pybop_spme": Z_pybop_spme,
#         "Z_grouped_geometry_capacity": Z_grouped_geometry_capacity,
#         "Z_grouped_nominal_capacity": Z_grouped_nominal_capacity
#             if Z_grouped_nominal_capacity is not None
#             else np.array([]),
#         "grouped_capacity_from_grouping_As": Q_grouping_As,
#         "nominal_capacity_As": Q_nominal_As,
#         "tau_ct_multipliers": np.asarray(TAU_CT_MULTIPLIERS, dtype=float),
#         "Z_grouped_tau_ct": np.column_stack(
#             [Z_grouped_tau_ct[label] for label in Z_grouped_tau_ct]
#         ) if RUN_GROUPED_TAU_CT_DIAGNOSTIC else np.array([]),
#         "capacity_Ah": capacity_Ah,
#         "SOC": SOC,
#     },
# )

# diagnostics_path = OUT / "aligned_parameter_diagnostics.json"
# diagnostics_to_save = {
#     **diagnostics,
#     "capacity_Ah": capacity_Ah,
#     "contact_resistance_Ohm": CONTACT_RESISTANCE_OHM,
#     "plot_unit": PLOT_UNIT,
#     "grouped_parameters_selected": {
#         key: float(grouped_parameters[key])
#         for key in [
#             "Series resistance [Ohm]",
#             "Negative electrode charge transfer time scale [s]",
#             "Positive electrode charge transfer time scale [s]",
#             "Negative particle diffusion time scale [s]",
#             "Positive particle diffusion time scale [s]",
#             "Reference electrolyte capacity [A.s]",
#             "Measured cell capacity [A.s]",
#             "Measured cell capacity from grouping [A.s]",
#         ]
#         if key in grouped_parameters and isinstance(grouped_parameters[key], (int, float, np.integer, np.floating))
#     },
# }
# with open(diagnostics_path, "w", encoding="utf-8") as f:
#     json.dump(diagnostics_to_save, f, indent=2)

# print("\nSaved figure:", fig_path)
# print("Saved CSV:", csv_path)
# print("Saved MAT:", mat_path)
# print("Saved diagnostics:", diagnostics_path)
# print("\nDONE")


# %%
from bpx_hydra_config import *
from bpx_hydra_parameters import (
    make_physical_params_from_bpx,
    make_grouped_params_from_physical,
    run_grouped_spme_eis,
)

params, diagnostics, scalar_grouping_overrides = make_physical_params_from_bpx(
    BPX_FILE,
    soc=SOC,
    contact_resistance_ohm=CONTACT_RESISTANCE_OHM,
)

grouped = make_grouped_params_from_physical(
    params,
    scalar_grouping_overrides,
    tau_ct_mode=TAU_CT_MODE,
    tau_ct_multiplier=TAU_CT_MULTIPLIER,
)

# %%
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.io import savemat

from bpx_hydra_config import *
from bpx_hydra_parameters import (
    make_physical_params_from_bpx,
    make_grouped_params_from_physical,
    print_parameter_summary,
    capacity_scale,
    run_native_pybamm_spme_eis,
    run_pybop_spme_eis,
    run_grouped_spme_eis,
)

OUT_DIR.mkdir(parents=True, exist_ok=True)

frequencies = np.logspace(np.log10(FMIN), np.log10(FMAX), NFREQ)

params, diagnostics, scalar_grouping_overrides = make_physical_params_from_bpx(
    BPX_FILE,
    soc=SOC,
    contact_resistance_ohm=CONTACT_RESISTANCE_OHM,
)

grouped, grouped_metadata = make_grouped_params_from_physical(
    params,
    scalar_grouping_overrides,
    tau_ct_mode=TAU_CT_MODE,
    tau_ct_multiplier=TAU_CT_MULTIPLIER,
    use_total_area_for_grouping=USE_TOTAL_AREA_FOR_GROUPING,
    force_nominal_capacity=FORCE_NOMINAL_CAPACITY_IN_GROUPED_MODEL,
)

print_parameter_summary(params, diagnostics, grouped, grouped_metadata)

Z_pybamm = run_native_pybamm_spme_eis(
    params,
    frequencies,
    SOC,
    model_options=MODEL_OPTIONS,
)

Z_pybop = run_pybop_spme_eis(
    params,
    frequencies,
    model_options=MODEL_OPTIONS,
    var_pts=VAR_PTS,
)

Z_grouped = run_grouped_spme_eis(
    grouped,
    frequencies,
    model_options=MODEL_OPTIONS,
    var_pts=VAR_PTS,
)

capacity_Ah = params["Nominal cell capacity [A.h]"]
tau_label = grouped_metadata["tau_ct_mode"]

Z_dict = {
    "Native PyBaMM SPMe": Z_pybamm,
    "PyBOP SPMe": Z_pybop,
    f"PyBOP GroupedSPMe ({tau_label})": Z_grouped,
}

fig, ax = plt.subplots(figsize=(7.5, 6.5))

for label, Z in Z_dict.items():
    Zp, unit_label, unit_file = capacity_scale(Z, capacity_Ah, PLOT_UNIT)
    ax.plot(
        np.real(Zp),
        -np.imag(Zp),
        "-o",
        markersize=3.5,
        linewidth=1.5,
        label=label,
    )

ax.set_xlabel(r"$Z_r(\omega)$ [" + unit_label + "]")
ax.set_ylabel(r"$-Z_j(\omega)$ [" + unit_label + "]")
ax.set_title(f"Aligned BPX EIS comparison, SOC = {SOC}")
ax.grid(True)
ax.set_aspect("equal", adjustable="box")
ax.legend(fontsize=8)
fig.tight_layout()

fig_path = OUT_DIR / f"aligned_eis_comparison_{unit_file}.png"
fig.savefig(fig_path, dpi=300)
plt.show()

# rows = []

# for label, Z in Z_dict.items():
#     Zp, _, unit_file = capacity_scale(Z, capacity_Ah, PLOT_UNIT)

#     for f, raw, plotz in zip(frequencies, Z, Zp):
#         rows.append(
#             {
#                 "Model": label,
#                 "Frequency [Hz]": float(f),
#                 "Z_real_raw [Ohm]": float(np.real(raw)),
#                 "Z_imag_raw [Ohm]": float(np.imag(raw)),
#                 "-Z_imag_raw [Ohm]": float(-np.imag(raw)),
#                 f"Z_real_plot [{unit_file}]": float(np.real(plotz)),
#                 f"Z_imag_plot [{unit_file}]": float(np.imag(plotz)),
#                 f"-Z_imag_plot [{unit_file}]": float(-np.imag(plotz)),
#                 "SOC": SOC,
#                 "Capacity [Ah]": capacity_Ah,
#             }
#         )

# csv_path = OUT_DIR / f"aligned_eis_comparison_{unit_file}.csv"
# pd.DataFrame(rows).to_csv(csv_path, index=False)

# mat_path = OUT_DIR / f"aligned_eis_comparison_{unit_file}.mat"
# savemat(
#     mat_path,
#     {
#         "f": frequencies,
#         "Z_pybamm_spme": Z_pybamm,
#         "Z_pybop_spme": Z_pybop,
#         "Z_grouped_spme": Z_grouped,
#         "capacity_Ah": capacity_Ah,
#         "SOC": SOC,
#     },
# )

# print("\nSaved figure:", fig_path)
# print("Saved CSV:", csv_path)
# print("Saved MAT:", mat_path)
# print("DONE")


# %%
import copy

import matplotlib.pyplot as plt
import numpy as np

from bpx_hydra_config import *
from bpx_hydra_parameters import (
    make_physical_params_from_bpx,
    make_grouped_params_from_physical,
    run_grouped_spme_eis,
)

parameter_name = "Positive electrode charge transfer time scale [s]"
factor = 2.0
n_values = 9

frequencies = np.logspace(np.log10(FMIN), np.log10(FMAX), NFREQ)

params, diagnostics, scalar_grouping_overrides = make_physical_params_from_bpx(
    BPX_FILE,
    soc=SOC,
    contact_resistance_ohm=CONTACT_RESISTANCE_OHM,
)

grouped_base, grouped_metadata = make_grouped_params_from_physical(
    params,
    scalar_grouping_overrides,
    tau_ct_mode=TAU_CT_MODE,
    tau_ct_multiplier=TAU_CT_MULTIPLIER,
    use_total_area_for_grouping=USE_TOTAL_AREA_FOR_GROUPING,
    force_nominal_capacity=FORCE_NOMINAL_CAPACITY_IN_GROUPED_MODEL,
)

base_value = float(grouped_base[parameter_name])

values = np.logspace(
    np.log10(base_value / factor),
    np.log10(base_value * factor),
    n_values,
)

fig, ax = plt.subplots(figsize=(7, 6))

for value in values:
    grouped = copy.deepcopy(grouped_base)
    grouped[parameter_name] = float(value)

    Z = run_grouped_spme_eis(
        grouped,
        frequencies,
        model_options=MODEL_OPTIONS,
        var_pts=VAR_PTS,
    )

    ax.plot(
        np.real(Z),
        -np.imag(Z),
        "-o",
        markersize=3,
        linewidth=1.2,
        label=f"{value:.2e}",
    )

ax.set_xlabel(r"$Z_r(\omega)$ [$\Omega$]")
ax.set_ylabel(r"$-Z_j(\omega)$ [$\Omega$]")
ax.set_title(f"GroupedSPMe sensitivity\n{parameter_name}, SOC = {SOC}")
ax.grid(True)
ax.set_aspect("equal", adjustable="box")
ax.legend(fontsize=7)
fig.tight_layout()
plt.show()



