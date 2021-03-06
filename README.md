# HERA Quality Metrics

[![Build Status](https://travis-ci.org/HERA-Team/hera_qm.svg?branch=master)](https://travis-ci.org/HERA-Team/hera_qm)
[![Coverage Status](https://coveralls.io/repos/github/HERA-Team/hera_qm/badge.svg?branch=master)](https://coveralls.io/github/HERA-Team/hera_qm?branch=master)

`hera_qm` is a python package for calculating quality metrics of HERA data.
It is integrated in the Real-Time Pipeline (RTP), automatically generating metrics
for all HERA data as it is taken. But `hera_qm` can also be used offline for
further analysis.

## Motivation
Data quality metrics are useful and needed throughout the analysis of interferometric data.
This repository is a centralized place for the HERA team to develop metrics to 1)
run on data in the RTP and deliver to the wider collaboration; 2) store these metrics
in the Monitor and Control database for easy access; and 3) use offline in individual
analyses. As a consequence of the first two goals, contributions to `hera_qm` will
be vetted by the community and require thorough unittests. However, the code base
will also be flexible to enable the third goal, and we welcome contributions (see below).

## Installation

### Dependencies
First install dependencies.

* numpy >= 1.10
* scipy
* matplotlib
* astropy >= 2.0
* sklearn >= 0.18.0
* aipy
* h5py
* pyuvdata (`pip install pyuvdata` or use https://github.com/RadioAstronomySoftwareGroup/pyuvdata.git)
* omnical (https://github.com/HERA-Team/omnical.git)
* linsolve (https://github.com/HERA-Team/linsolve.git)
* uvtools (https://github.com/HERA-Team/uvtools.git)
* hera_cal (https://github.com/HERA-Team/hera_cal.git)

For anaconda users, we suggest using conda to install astropy, numpy and scipy and conda-forge
for aipy (```conda install -c conda-forge aipy```).

### Installing hera_qm
Clone the repo using
`git clone https://github.com/HERA-Team/hera_qm.git`

Navigate into the directory and run `python setup.py install`.

### Running Tests
Requires installation of `nose` package.
From the source `hera_qm` directory run: `nosetests hera_qm`.

## Package Details and Usage
There are currently five primary modules which drive HERA quality metrics.

### ant_metrics
A module to handle visibility-based metrics designed to identify misbehaving antennas.
The module includes methods to calculate several metrics to identify cross-polarized antennas
or dead antennas, based on either their redundancy with other antennas or their relative power.
The primary class, `AntennaMetrics`, includes interfaces to these methods and functions for
loading data, iteratively running metrics and removing misbehaving antennas, and saving the
results of those metrics in a JSON. And example of using this moduleis in
`scripts/ant_metrics_example_notebook.ipynb`.

### firstcal_metrics
A module to calculate metrics based on firstcal delay solutions. These metrics
identify large variations in delay solutions across time or across the array
for a given time. Included are functions for plotting firstcal delay solutions,
running the firstcal metrics, plotting the metrics, and writing them to file.
An example of using this module is in `scripts/firstcal_metrics.ipynb`.

### omnical_metrics
A module to calculate metrics based on omnical solutions. Currently, these metrics
aim to identify discontinuities in the phase solutions of the gains and model visibilities,
as well as outliers in the antenna-based chi-square output from omnical. Routines for
calculating the metrics, writing them to file, and plotting the metrics (as well as the
gain solutions and model visibilities) are included. For an example of how to use these
metrics see `scripts/omnical_metrics_example.ipynb`. The metrics themselves are detailed
there as well as in the doc-strings of the source code in `hera_qm.Omnical_Metrics.run_metrics()`.

### UVFlag
The UVFlag object provides a way to handle, manipulate, and store flag arrays and metrics
for identifying flags. There are two modes for a UVFlag object - `'flag'` and `'metric'`.
The flag or metric arrays can match UVData (`'baseline'` type) or UVCal (`'antenna'` type)
objects, or have (Ntimes, Nfreqs, Npols) shape (`'waterfall'` type). Reading/writing to HDF5
file format is supported. Convenience functions to combine flags, average along axes,
and convert between modes/types are also available.

### xrfi
This module contains the tools to for radio frequency interference (RFI) detection
and flagging. Low-level preprocessing functions act on 2D arrays to filter data
and/or calculate significance metrics. Flagging algorithms implement the low-level
functions or flag in other ways (e.g. "watershed" around existing flags). "Pipelines"
define the flagging strategy to apply to some data. For example, `xrfi_h1c_pipe` shows
the flagging scheme we used for H1C observing season. Wrappers handle the file I/O,
and call pipelines. `xrfi_h1c_run` is a wrapper we retroactively made to reflect
what we did for H1C.


## Known Issues and Planned Improvements
Issues are tracked in the [issue log](https://github.com/HERA-Team/hera_qm/issues).
Major current issues and planned improvements include:
* A unified metric class structure
* Develop Tsys calculations into metrics (HERA Memos 16 and 34)
* Develop closure quantities into metrics (HERA Memo 15)

## Contributing
Contributions to this package to introduce new functionality or address any of the
issues in the [issue log](https://github.com/HERA-Team/hera_qm/issues) are very welcome.
Please submit improvements as pull requests against the repo after verifying that
the existing tests pass and any new code is well covered by unit tests.

Bug reports or feature requests are also very welcome, please add them to the
issue log after verifying that the issue does not already exist.
Comments on existing issues are also welcome.
