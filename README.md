<p align="center">
  <picture align="center">
    <source media="(prefers-color-scheme: dark)" srcset="./logo/PuReX-dark.png">
    <source media="(prefers-color-scheme: light)" srcset="./logo/PuReX-light.png">
    <img alt="PuReX logo with some description about it." src="./logo/PuReX-light.png">
  </picture>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/version-0.1.0--alpha-red" />
  <a href="https://pypi.org/project/purex/" target="_blank"><img src="https://img.shields.io/pypi/pyversions/purex.svg" /></a>
  <img src="https://img.shields.io/pypi/dm/purex" />
  <a href="https://j0m0k0.github.io/PuReX" target="_blank"><img src="https://img.shields.io/badge/view-Documentation-red?" /></a>
  <img src="http://img.shields.io/github/actions/workflow/status/j0m0k0/PuReX/purex-test.yml?branch=main">
  <img src="https://img.shields.io/github/commit-activity/m/j0m0k0/PuReX">
  <img src="https://img.shields.io/github/license/j0m0k0/PuReX">
  <a href="https://doi.org/10.5281/zenodo.15825844"><img src="https://zenodo.org/badge/DOI/10.5281/zenodo.15825844.svg" alt="DOI"></a>
</p>  



## Installation
Using pip:
```bash
pip install purex
```

Using uv (recommended):
```bash
uv add purex
```

To install the documentation, you can install `purex[doc]` instead of `purex`.

## Tutorials
First thing to do after the installation, is to set the environment variable token. This token is your GitHub token that will be used for sending the requests to GitHub REST API. Although including the token is not necessary, but it can be helpful for a faster extraction, specially for bigger projects.

In UNIX-like (GNU/Linux, Mac OS) operating systems:
```bash
export PUREX_TOKEN="YOUR TOKEN"
```

In Windows operating system:
```bash
set PUREX_TOKEN="YOUR_TOKEN"
```

For getting help about the PuReX, you can run it without any extra command or just pass the `help` option:
```bash
purex --help
Usage: purex [OPTIONS] COMMAND [ARGS]...

Options:
  --help  Show this message and exit.

Commands:
  get  Get data from GitHub repositories (PRs, maintainers, etc.)
```

### Getting Data from a Repository
```bash
Usage: purex get [OPTIONS] COMMAND [ARGS]...

  Get data from GitHub repositories (PRs, maintainers, etc.)

Options:
  --help  Show this message and exit.

Commands:
  maintainers  Get maintainers info from filtered PRs
  prs          Fetch PRs from a repository

```

For more info and tutorials, please refer to the documentation.

## About
### Publications
If you use PuReX in your research, please cite it as follows:
```bib
@software{PuReX,
  author = {Mokhtari Koushyar, Javad},
  doi = {10.5281/zenodo.15825844},
  month = {2},
  title = {{PuReX, Pull-Request Extractor}},
  url = {https://github.com/j0m0k0/PuReX},
  year = {2025}
}
```
