# Acknowledgments & how to cite the tools this builds on

This workflow orchestrates several excellent open-source projects. If you publish
work that uses it, please cite the underlying methods software as well as this
workflow (see [`CITATION.cff`](CITATION.cff)).

## Core methods software

**Suite2p** — movie registration and ROI detection.
> Pachitariu, M., Stringer, C., Schröder, S., Dipoppa, M., Rossi, L. F.,
> Carandini, M., & Harris, K. D. (2017). *Suite2p: beyond 10,000 neurons with
> standard two-photon microscopy.* bioRxiv 061507. https://doi.org/10.1101/061507
>
> Updated description (recommended by the developers):
> Stringer, C., Ki, C., Del Grosso, N., LaFosse, P., Zhang, Q., & Pachitariu, M.
> (2026). *Extracting large-scale neural activity with Suite2p.* bioRxiv
> 2026.02.04.703741. https://doi.org/10.64898/2026.02.04.703741

**Cellpose** — segmentation of the snap stills that drive ROI extraction.
> Stringer, C., Wang, T., Michaelos, M., & Pachitariu, M. (2021). *Cellpose: a
> generalist algorithm for cellular segmentation.* Nature Methods, 18, 100–106.
> https://doi.org/10.1038/s41592-020-01018-x

**Cellpose-SAM** — the generalist backbone the `cpsam`/`cpdino` snap models build on.
> Pachitariu, M., Rariden, M., & Stringer, C. (2025). *Cellpose-SAM: superhuman
> generalization for cellular segmentation.* bioRxiv 2025.04.28.651001.
> https://doi.org/10.1101/2025.04.28.651001

**DINOv3** — the self-supervised vision backbone used by the retinal snap model.
> Siméoni, O., Vo, H. V., Seitzer, M., Baldassarre, F., Oquab, M., Jose, C., et
> al. (2025). *DINOv3.* arXiv:2508.10104. https://arxiv.org/abs/2508.10104
>
> DINOv3 is used under Meta's DINOv3 license and installed at build time; it is
> not redistributed in this repository.

**scikit-learn** — the trained ROI and spike classifiers.
> Pedregosa, F., Varoquaux, G., Gramfort, A., Michel, V., Thirion, B., Grisel, O.,
> et al. (2011). *Scikit-learn: Machine Learning in Python.* Journal of Machine
> Learning Research, 12, 2825–2830.

## Scientific-Python foundation

> Harris, C. R., et al. (2020). *Array programming with NumPy.* Nature, 585,
> 357–362. https://doi.org/10.1038/s41586-020-2649-2
>
> Virtanen, P., et al. (2020). *SciPy 1.0: fundamental algorithms for scientific
> computing in Python.* Nature Methods, 17, 261–272.
> https://doi.org/10.1038/s41592-019-0686-2
>
> Hunter, J. D. (2007). *Matplotlib: A 2D graphics environment.* Computing in
> Science & Engineering, 9(3), 90–95.
>
> Paszke, A., et al. (2019). *PyTorch: An Imperative Style, High-Performance Deep
> Learning Library.* Advances in Neural Information Processing Systems 32.

Also used: pandas, numba, tifffile, and openpyxl.

## Methods referenced in the analysis

The event-inference and grouping choices in the analysis draw on established
methods; where relevant the tool and its documentation reference, e.g., ΔF/F
baseline estimation (Dombeck et al., 2007) and event-inference approaches such as
OASIS (Friedrich et al., 2017) and CASCADE (Rupprecht et al., 2021) as points of
comparison. See the in-tool guide for details.
