# GW150914 Einstein Toolkit Simulation

<p align="center">
  <a href="README.md"><img src="https://img.shields.io/badge/lang-English-blue?style=for-the-badge" alt="English"></a>
  <a href="readme/README.ja.md"><img src="https://img.shields.io/badge/lang-日本語-lightgrey?style=for-the-badge" alt="日本語"></a>
</p>

[![License: GPL-2.0-or-later](https://img.shields.io/badge/license-GPL--2.0--or--later-blue.svg)](LICENSE)

A numerical-relativity reproduction of the gravitational-wave event
**GW150914** (binary black-hole merger) using the Einstein Toolkit.

## Overview

This project re-runs GW150914 — the first gravitational wave directly
detected by LIGO on 2015-09-14 09:51 UTC — with the
[Einstein Toolkit](https://einsteintoolkit.org/).

- **Event**: 36 + 29 solar-mass binary black-hole merger → 62 solar-mass
  remnant (3 solar masses radiated as gravitational waves)
- **Discovery paper**: [Phys. Rev. Lett. 116, 061102](http://dx.doi.org/10.1103/PhysRevLett.116.061102)
- **LIGO open data**: <https://losc.ligo.org/events/GW150914/>
- **Reference upstream gallery**:
  <https://einsteintoolkit.org/gallery/bbh/index.html>

### Scope

This is a hobby reproduction, not original research. The goal is to
**replay a famous gravitational-wave event** end-to-end on a workstation,
and accept the following compromises:

- Resolution dropped from the gallery default `N=28` to `N=16`
  (sacrifices accuracy; aims for qualitative reproduction of orbits and
  waveform).
- All builds and runs happen inside Docker so the host environment stays
  clean.

## Physical parameters

| Quantity | Value |
| --- | --- |
| Initial separation D | 10 M |
| Mass ratio q = m₁/m₂ | 36/29 ≈ 1.24 |
| Spin χ₁ | 0.31 |
| Spin χ₂ | -0.46 |

### Expected results from the upstream gallery

| Quantity | Value |
| --- | --- |
| Number of orbits | 6 |
| Time to merger | 899 M |
| Final BH mass | 0.95 M |
| Final BH spin (dimensionless) | 0.69 |

## Development environment

- OS: Linux (Ubuntu-family assumed)
- Container: Docker (image is built from source on top of Ubuntu 20.04)
- Einstein Toolkit: **Kruskal release (`ET_2025_05`)** built from source
- MPI: **MPICH** (matches the upstream `jupyter-et` configuration)

## Prerequisites

- Linux host (e.g. Ubuntu 24.04)
- Docker 29.x or newer + Docker Compose v2 or newer
- 16 CPU cores / 93 GiB RAM / **150 GB+ free SSD** recommended
  (image is 5–8 GB; build intermediates and run output add up)
- Host user belongs to the `docker` group (so `docker` works without `sudo`)

## Installation

### 1. Configure environment

```bash
# Copy .env.example to .env and tune (output dir, UID, etc.)
cp .env.example .env
$EDITOR .env
```

Main settings:

| Variable | Meaning | Default |
| --- | --- | --- |
| `SIM_OUTPUT_DIR` | Simulation diagnostic output directory (local SSD recommended) | `${HOME}/gw150914-output` |
| `SIM_CHECKPOINT_DIR` | Checkpoint output directory (Phase 3c+; local SSD recommended) | `${HOME}/gw150914-checkpoints` |
| `JUPYTER_PORT` | Port exposed for Jupyter Lab | `8888` |
| `CONTAINER_CPUSET` | Physical CPU cores to pin the container to | `0-15` |
| `CONTAINER_MEM_LIMIT` | Container memory limit | `80g` |
| `CONTAINER_SHM_SIZE` | Shared memory (used by MPICH) | `4gb` |
| `USER_UID` / `USER_GID` | UID/GID of the in-container `etuser` (match the host) | `1000` / `1000` |
| `MAKE_PARALLEL` | `make -j` parallelism for the Cactus build | `8` |

### 2. Build the Docker image

⚠️ **The first build takes 60–120 minutes** because the Einstein Toolkit
Kruskal release is built from source, including AMReX, ADIOS2 and the
other auxiliary libraries.

```bash
make docker-build      # host UID/GID is detected automatically
```

`make docker-rebuild` does a no-cache rebuild.

### 3. Start the container

```bash
make docker-up      # background start
make docker-token   # print the Jupyter Lab URL with token
```

Other management commands:

```bash
make docker-shell   # bash inside the container
make docker-logs    # follow logs
make docker-check   # verify mpirun / sim / cactus_sim / required thorns
make docker-down    # stop and remove
make help           # list all targets
```

## Usage

### Fetching parameter files

The official Einstein Toolkit parfiles are **not** committed to this
repository (we respect the upstream copyright). Pull them from Bitbucket:

```bash
# GW150914 itself (used by Phase 3b/3c)
make fetch-parfile    # download upstream rpar + sha256 sidecar verification
make verify-parfile   # re-check the sha256 of an already-fetched file

# qc0-mclachlan (used by Phase 3a feasibility — equal-mass, spinless light BBH)
make fetch-qc0        # download qc0-mclachlan.par + sha256 verification
make verify-qc0       # re-check the sha256 of an already-fetched file
```

### qc0-mclachlan smoke run (Phase 3a)

Before changing the GW150914 grid (Phase 3b), validate that the Einstein
Toolkit itself runs end-to-end with the qc0-mclachlan.par
(equal-mass, spinless light BBH):

```bash
make qc0-smoke-parfile  # apply overrides to produce a smoke parfile
make run-qc0-smoke      # run with np=SIM_MPI_PROCS × OMP=SIM_OMP_THREADS
```

- Parallelism is controlled by `SIM_MPI_PROCS` / `SIM_OMP_THREADS` in
  `.env` (recommended values and rationale are in `.env.example`).
- Smoke terminates at `cctk_itlast=10`; wall time on a 16-core host is
  about 30 minutes.
- Output goes to `${SIM_OUTPUT_DIR}/qc0-mclachlan-smoke/`, logs to `_logs/`.

### GW150914 N=16 feasibility run (Phase 3b-ii)

The upstream rpar has its grid structure hard-wired to `N=28`, so running
at `N=16` requires expanding `Coordinates::sphere_inner_radius` (see
Issue #9 and the Phase 3b-ii notes in CLAUDE.md):

```bash
# defaults: SIM_N16_INNER_RADIUS=77.14 (snapped to 77.10 M)
#           SIM_N16_MAXRLS=unset (uses the rpar's original value of 9)
make run-gw150914-n16-feasibility \
    SIM_MPI_PROCS=1 SIM_OMP_THREADS=16 SIM_ITLAST=16
```

Measurements (np=1 × OMP=16, 16 evolve iterations):
- wall time 4m27s, peak memory 21 GiB, 1.84 sec/iter
  (short evolve, includes AMR ramp-up)
- A 30-minute timeout (`SIM_RUN_TIMEOUT`) guards against OOM hangs
  (a 297-minute hang was observed in Phase 3b-i).

### GW150914 checkpoint validation (Phase 3c-1)

Confirm checkpoint write/restart works before committing to long runs:

```bash
# write check (clean start; both walltime=0.5h and on_terminate paths)
make run-gw150914-n16-checkpoint-test \
    SIM_MPI_PROCS=1 SIM_OMP_THREADS=16 SIM_CKPT_MODE=write
# → ~1 hour, output under ${SIM_CHECKPOINT_DIR}/checkpoint-test/

# restart check (recover=auto loads the latest checkpoint)
make run-gw150914-n16-checkpoint-test \
    SIM_MPI_PROCS=1 SIM_OMP_THREADS=16 SIM_CKPT_MODE=restart
# → ~9 minutes (TwoPunctures is skipped)
```

Measurements:
- write run: 1h03m, peak 25.7 GiB, 3 checkpoint events (iter 1956/3972/4000)
- restart run: 8m41s, peak 26.3 GiB, recovered from it_4000 → evolved to it_4500
- **Steady-state sec/iter = 0.89** (revised down from the earlier 1.84 estimate)
- **POSIX lock issue did not reappear at np=1**
  (see [HDF5 Checkpoint POSIX Lock Issue](https://github.com/s-sasaki-earthsea-wizard/gw150914-einstein-toolkit/wiki/HDF5-Checkpoint-POSIX-Lock-Issue))

Production-stage wall-time estimates (based on 0.89 sec/iter):

| Stage | evolve | iter | wall time |
| --- | --- | --- | --- |
| A | 100 M | 26,500 | 6.6 hours |
| B | 1000 M (merger + ringdown) | 265,000 | 2.7 days |
| C | 1700 M (full upstream coverage) | 451,000 | 4.7 days |

### Tests

Tests are split into two layers, separated by pytest markers:

| Level | Marker | Scope | Time | Dependency |
| --- | --- | --- | --- | --- |
| 1 | `smoke` | Pure-Python tests for the rpar → par generation pipeline | < 1 s | Python only |
| 2 | `short` | Run cactus_sim through the TwoPunctures initial-data stage | ~7 min | Docker + Cactus |

```bash
make test-host-smoke  # Level 1 on the host python3 (no Docker needed)
make test-smoke       # Level 1 inside the container
make test-short       # Level 1+2 inside the container
make test-all         # everything
```

### Phase 3c-2/3/4 staged production run

Production is split into three physical-time stages (0 → 100 / 1000 /
1700 M). After each stage finishes, results are compared against the
Zenodo N=28 reference for a go/no-go decision
([Issue #3](https://github.com/s-sasaki-earthsea-wizard/gw150914-einstein-toolkit/issues/3)).

```bash
# Stage A: 0 → 100 M (clean start, ~6.6 h)
make run-gw150914-n16-stage-a

# Stage B: 100 → 1000 M (continues from Stage A's checkpoint, ~2.7 d cumulative)
make run-gw150914-n16-stage-b

# Stage C: 1000 → 1700 M (continues from Stage B's checkpoint, ~27.9 h)
make run-gw150914-n16-stage-c
```

#### Resuming after an interruption

If a run is interrupted (walltime, OOM, manual kill), use **`resume-*`,
not `run-*`**. `run-*` is for cross-stage continuity and passes
`--continue-from`, so it would restart from the previous stage's final
checkpoint instead of from the interruption point (an actual incident
during Phase 3c-3).

```bash
# Example: Stage B was interrupted → resume from the latest checkpoint of the same stage
make resume-gw150914-n16-stage-b
```

`resume-*` invokes the parfile generator without `--continue-from`, so
`IO::recover_dir` points to the same `checkpoint_dir` as the writer.
With `IO::recover = "autoprobe"`, the simulation auto-recovers from the
latest checkpoint under `${SIM_CHECKPOINT_DIR}/<stage>/`.

#### Double-launch prevention

`run-*` / `resume-*` start with a pre-check that aborts if another
`cactus_sim` is already running inside the container (a defense against
the Phase 3c-3 incident in which `nohup make ... &` was issued twice and
two simulations ran concurrently). To intentionally clear a stale
process:

```bash
docker exec gw150914-et pkill -KILL -f cactus_sim
```

### Phase 4: analysis and visualisation

After each stage completes, you can compare against the Zenodo N=28
reference
([Issue #4](https://github.com/s-sasaki-earthsea-wizard/gw150914-einstein-toolkit/issues/4)).
The Stage C comparison concatenates Stage A+B+C and doubles as the
full-simulation comparison.

```bash
# Stage A comparison (snapshot at t=100 M)
make compare-stage-a

# Stage B comparison (t=1000 M, merger + early ringdown)
make compare-stage-b

# Stage C comparison (t=1700 M, full inspiral + merger + ringdown + ψ4 peak)
# = full-simulation comparison via Stage A+B+C concatenation
make compare-stage-c
```

Each target writes a pass/fail JSON plus 6–9 overlay plots to
`reports/stage_{a,b,c}/`. Docker-free host variants
(`compare-stage-{a,b,c}-host`) are also available.

## Project status

| Phase | Topic | Status |
| --- | --- | --- |
| 0 | Project bootstrap and documentation | ✅ Done |
| 1 | Docker environment ([#1](https://github.com/s-sasaki-earthsea-wizard/gw150914-einstein-toolkit/issues/1)) | ✅ Done |
| 2 | GW150914 parfile fetch + test foundation ([#2](https://github.com/s-sasaki-earthsea-wizard/gw150914-einstein-toolkit/issues/2)) | ✅ Done |
| 3a | qc0-mclachlan ET feasibility ([#10](https://github.com/s-sasaki-earthsea-wizard/gw150914-einstein-toolkit/issues/10)) | ✅ Done |
| 3b-i | N=28 memory/time feasibility | ✅ Done (np=1 OMP=16, 50 GiB / ~16-day projection) |
| 3b-ii | N=16 rpar grid modification ([#9](https://github.com/s-sasaki-earthsea-wizard/gw150914-einstein-toolkit/issues/9)) | ✅ Done (sphere_inner_radius enlargement, 1.84 sec/iter, 21 GiB peak, ~5.7-day ringdown projection) |
| 3c-1 | Checkpoint write/restart validation ([#3](https://github.com/s-sasaki-earthsea-wizard/gw150914-einstein-toolkit/issues/3)) | ✅ Done (no POSIX lock at np=1; both walltime + terminate paths + recover succeed; steady state 0.89 sec/iter) |
| 3c-2 | Stage A run (0 → 100 M, 6.6h) ([#3](https://github.com/s-sasaki-earthsea-wizard/gw150914-einstein-toolkit/issues/3)) | ✅ Done (6h51m, 100.013 M, peak 26.91 GiB) |
| 3c-3 | Stage B run (100 → 1000 M, +2.7 d) ([#21](https://github.com/s-sasaki-earthsea-wizard/gw150914-einstein-toolkit/issues/21)) | ✅ Done (49h39m, 1000.01 M, peak 28.76 GiB) |
| 3c-4 | Stage C run (1000 → 1700 M, +27.9 h) ([#3](https://github.com/s-sasaki-earthsea-wizard/gw150914-einstein-toolkit/issues/3)) | ✅ Done (27h54m, 1700.01 M, peak 22.79 GiB) |
| 4 | Orbit/waveform extraction + Zenodo N=28 comparison ([#4](https://github.com/s-sasaki-earthsea-wizard/gw150914-einstein-toolkit/issues/4)) | ✅ Done (Stage A/B/C all overall_pass=True; ψ4 peak amplitude -1.79% / peak time -0.28 M) |
| 5 | 3D visualisation (optional, [#5](https://github.com/s-sasaki-earthsea-wizard/gw150914-einstein-toolkit/issues/5)) | Not started |

## References

- Einstein Toolkit BBH Gallery: <https://einsteintoolkit.org/gallery/bbh/index.html>
- `docs/Binary Black Hole.pdf`: PDF copy of the page above (gitignored)
- LIGO discovery paper: [Phys. Rev. Lett. 116, 061102](http://dx.doi.org/10.1103/PhysRevLett.116.061102)
- LIGO data analysis paper: <http://arxiv.org/abs/1602.03840>
- GW150914 parameter file:
  <https://bitbucket.org/einsteintoolkit/einsteinexamples/raw/master/par/GW150914/GW150914.rpar>
- **Zenodo official N=28 diagnostic data** (Phase 4 comparison reference):
  <https://doi.org/10.5281/zenodo.155394>

## License

This repository — the parfile generators, Docker setup, Makefiles, tests
and analysis scripts authored here — is licensed under the
[GNU General Public License v2.0 or later](LICENSE)
(`SPDX-License-Identifier: GPL-2.0-or-later`).

The Einstein Toolkit itself is **not redistributed** by this repository.
The Dockerfile fetches it from the upstream Bitbucket repositories at
build time, and ET is governed by its own license terms (mostly GPL/LGPL
on the individual thorns); see <https://einsteintoolkit.org> for details.
The official `GW150914.rpar` parameter file is likewise fetched at run
time and is not committed here.
