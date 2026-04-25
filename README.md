# California Codes

Complete plain-text versions of all California statutory codes, updated nightly from the official legislative bulk data.

## What's here

The `codes/` directory contains one `.txt` file per California code — 29 codes plus the California Constitution. Each file is a clean, readable plain-text extraction of the full code with section numbers, structural headings, and legislative history.

## Source

All data comes from the **official bulk download** published by the California Legislature:

> https://downloads.leginfo.legislature.ca.gov/

This is the same database that powers [leginfo.legislature.ca.gov](https://leginfo.legislature.ca.gov). The bulk data ZIP contains tab-delimited tables and XML content files for every active section of California law.

## How it works

`update_ca_codes.py` downloads the current session's bulk data ZIP (~764MB), extracts the legislative database tables, parses the table of contents and section content, and writes each code as a single text file in proper statutory order.

A GitHub Actions workflow runs this script nightly and commits any changes.

## Codes included

| Code | Abbreviation |
|------|-------------|
| Business and Professions Code | BPC |
| California Constitution | CONS |
| Civil Code | CIV |
| Code of Civil Procedure | CCP |
| Commercial Code | COM |
| Corporations Code | CORP |
| Education Code | EDC |
| Elections Code | ELEC |
| Evidence Code | EVID |
| Family Code | FAM |
| Financial Code | FIN |
| Fish and Game Code | FGC |
| Food and Agricultural Code | FAC |
| Government Code | GOV |
| Harbors and Navigation Code | HNC |
| Health and Safety Code | HSC |
| Insurance Code | INS |
| Labor Code | LAB |
| Military and Veterans Code | MVC |
| Penal Code | PEN |
| Probate Code | PROB |
| Public Contract Code | PCC |
| Public Resources Code | PRC |
| Public Utilities Code | PUC |
| Revenue and Taxation Code | RTC |
| Streets and Highways Code | SHC |
| Unemployment Insurance Code | UIC |
| Vehicle Code | VEH |
| Water Code | WAT |
| Welfare and Institutions Code | WIC |

## Usage

To search across all codes:

```bash
grep -r "fiduciary duty" codes/
```

To update locally:

```bash
python3 update_ca_codes.py
```

Requires `curl` and `unzip` (standard on macOS and Linux).

## License

The text of California law is public domain. This repository's automation code is provided as-is.
