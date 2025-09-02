<p align="center">
  <picture align="center">
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/j0m0k0/PuReX/refs/heads/main/logo/PuReX-dark.png">
    <source media="(prefers-color-scheme: light)" srcset="https://raw.githubusercontent.com/j0m0k0/PuReX/refs/heads/main/logo/PuReX-light.png">
    <img alt="PuReX logo with some description about it." src="https://raw.githubusercontent.com/j0m0k0/PuReX/refs/heads/main/logo/PuReX-light.png">
  </picture>
</p>

<p align="center">
  <a href="https://pypi.org/project/purex/" target="_blank"><img src="https://img.shields.io/pypi/pyversions/purex.svg" /></a>
<!--   <img src="https://img.shields.io/pypi/dm/purex" /> -->
<!--   <a href="https://j0m0k0.github.io/PuReX" target="_blank"><img src="https://img.shields.io/badge/view-Documentation-red?" /></a> -->
  <img src="http://img.shields.io/github/actions/workflow/status/j0m0k0/PuReX/purex-test.yml?branch=main"> <br />
  <img src="https://img.shields.io/github/commit-activity/m/j0m0k0/PuReX">
  <img src="https://img.shields.io/github/license/j0m0k0/PuReX">
  <a href="https://doi.org/10.5281/zenodo.15825844"><img src="https://zenodo.org/badge/DOI/10.5281/zenodo.15851126.svg" alt="DOI"></a>
  <img src="https://static.pepy.tech/badge/purex" />
</p>  



## Installation
PuReX can be installed from [PyPI](https://pypi.org/project/purex/).

Using pip:
```bash
pip install purex
```

Using uv (recommended):
```bash
uv add purex
```

To install the documentation, you can install `purex[doc]` instead of `purex`.
```bash
uv add purex[doc]
```

To install from the source, clone this repository, `cd` into the directory and run the following command:
```bash
pip install -e .
```


## Basic Usage
First thing to do after the installation, is to set the environment variable token. This token is your GitHub token that will be used for sending the requests to GitHub REST API. Although including the token is not necessary, but it can be helpful for a faster extraction, specially for bigger projects, since it has a higher rate limit than the public API.

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
```

It shows the general help of the tool:
```bash
Usage: purex [OPTIONS] COMMAND [ARGS]...

Options:
  --version  Show the version and exit.
  --help     Show this message and exit.

Commands:
  get  Get pull-request data of a repository.
```

### Getting Data from a Repository
The help option is also available for every subcommand. For example for `get` command:
```bash
purex get --help
```
Outputs:
```
Usage: purex get [OPTIONS] OWNER REPOSITORY

  GET pull-request data for REPOSITY from OWNER.

  OWNER is the account name that hosts the repository (e.g., torvalds).

  REPOSITORY is the name of the repository (e.g., linux).

Options:
  -t, --token TEXT         GitHub Token
  -u, --base_url TEXT      REST API url of GitHub.
  --start_date [%m-%d-%Y]  Inclusive starting date (MM-DD-YYYY) for pulling
                           the pull-request data.
  --help                   Show this message and exit.
```

Example: Let's say we want to get the pull-request information of `furo` package by `pradyunsg` starting from `01-01-2024` until the current date. We can use PuReX like this:
```bash
purex get pradyunsg furo --start_date 01-01-2024
```

PuReX will extract the information of the requested repository within the selected time delta, and finally finds the maintainers responsible for closing or merging those PRs and returns the results in JSON format:
```
{
  'pradyunsg': {'closed': 7, 'merged': 36},
  'dependabot[bot]': {'closed': 3, 'merged': 0},
  'ferdnyc': {'closed': 1, 'merged': 0},
  'M-ZubairAhmed': {'closed': 1, 'merged': 0}
}
```

The results shows the number of PRs closed/merged by each maitainer.

For more info and tutorials, please refer to the documentation.

## About
### Publications
If you use PuReX in your research, please cite it as follows:
```bib
@software{PuReX,
  author = {Mokhtari Koushyar, Javad},
  doi = {10.5281/zenodo.15851126},
  month = {2},
  title = {{PuReX, Pull-Request Extractor}},
  url = {https://github.com/j0m0k0/PuReX},
  year = {2025}
}
```
