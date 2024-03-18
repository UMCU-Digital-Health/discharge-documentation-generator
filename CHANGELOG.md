# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.3.2] - 2024-03-18
- update dashboard with authentications
- update dashboard with psychiatry
- included demo patient in dashbaord
- removal of old demo dashboard

## [0.3.1] - 2024-02-19

### Added
- Added option to download local SQLite database as temporary solution until external DB is in place
- Added a warning message when deploying warning the user to export the database

### Fixed
- Fixed some small static typing errors
- Set temperature to 0.2 in dashboard to prevent users from changing it

## [0.3.0] - 2024-02-16

### Added
- Added a local sqlite database to store evaluation of the dashboard
- Added authorization to the dashboard

### Changed
- Changed the dashboard to use Bootstrap components

## [0.2.1] - 2024-01-31

### Added
- Added SQLAlchemy models and notebook to try out

## [0.2.0] - 2024-02-05

### Added
- Exploratory analysis and preprocessing code
- Visualisation dashboards of metavision and Hix data

## [0.1.3] - 2024-01-19

### Added
- Added DVC experiment setup and config files

### Changed
- Updated to python 3.10
- Updated openai package version and rewrote notebook and demo dash
- Updated DEDUCE version in notebook

### Fixed
- Demo dashboard now sometimes works, still not robust
- Removed print statement from dashboard

## [0.1.2] - 2024-01-10

### Fixed
- Load patient_ids as string, so leading 0's are kept

### Added
- Apply DEDUCE to new export from Metavision

## [0.1.1] - 2023-11-29

### Added
- Added queries to extract data from dataplatform
- Extracted data from the IC's from MetaVision
- Added notebook to apply deduce to extracted data

## [0.1.0] - 2023-11-06

### Added
- demo dashboard


