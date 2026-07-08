from pathlib import Path

BPX_FILE = Path(
    r"C:\Users\mugi_jo\Documents\PYBOP_2\PyBOP\Impedance_simulation_hydra0_cell\data_parameters\hydr0_graphite-lnmo_schmitt-2026_validation.bpx_1_patched_for_current_bpx.json"
)

OUT_DIR = Path("result")

SOC = 0.5

FMIN = 5e-3
FMAX = 1e5
NFREQ = 100

PLOT_UNIT = "ohm"  # "ohm", "mohm", or "mohm_Ah"

CONTACT_RESISTANCE_OHM = 0.0

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

# GroupedSPMe tau_ct handling:
#   "from_bpx_j0"  -> compute tau_ct from BPX-derived j0 references
#   "multiplier"  -> use original converter tau_ct multiplied by TAU_CT_MULTIPLIER
#   "converter"   -> use original PyBOP converter tau_ct unchanged
TAU_CT_MODE = "from_bpx_j0"
# TAU_CT_MULTIPLIER = 0.12
TAU_CT_MULTIPLIER = 1
USE_TOTAL_AREA_FOR_GROUPING = True
FORCE_NOMINAL_CAPACITY_IN_GROUPED_MODEL = True
