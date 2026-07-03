# BPX HYDRA EIS Simulation Scripts

This repository contains Python scripts for comparing PyBaMM SPMe, PyBOP SPMe, and PyBOP GroupedSPMe impedance simulations using a HYDRA BPX parameter file.

## Scripts

- `bpx_hydra_config.py`  
  Contains paths and simulation settings.

- `bpx_hydra_parameters.py`  
  Converts BPX parameters to PyBaMM/PyBOP physical and grouped parameters.

- `model_comparision.ipynb`  
  Runs aligned EIS comparison between native PyBaMM SPMe, PyBOP SPMe, and PyBOP GroupedSPMe.

- `sensitivity_analysis.ipynb`  
  Runs GroupedSPMe parameter sensitivity analysis and saves presentation-quality PNG plots.

## Setup

```bash
pip install -r requirements.txt
