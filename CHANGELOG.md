# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.5.1] - 2024-07-02

## [0.4.6] - 2024-07-18

### Added 
- working API that processes the data, pseudonomises it, generates a discharge letter and saves it to the database. 

### Changed
- the test data for the API is changed to what the real test data will look like
- updated the dashboard that gathers the last entry in the database. 

## [0.4.5] - 2024-06-19
### Added
- Added a dashboard for phase 2 of the evaluation
- Added tables for storing results of phase 2

### Changed
- Updated highlight function to change background color and font color


## [0.5.0] - 2024-06-19

### Changed
- large refactor

## [0.4.4] - 2024-06-19

### Added
- demo dashboard in english

### Changed
- restructuring of the notebooks
- updating of sql queries


## [0.4.3] - 2024-04-18

### Added
- Added filtering on the data to remove duplicated data in patient file. 
- Added a dashboard to communicate with the Posit database. 
- Added functionality to show stored GPT4 letter in eval dashboard
- Added 'refresh' functionality when switching to a new patient in eval dashboard 


## [0.4.2] - 2024-04-15

### Added
- Added endpoint to the API for deleting old generated discharge documents
- Added unit tests

## [0.4.1] - 2024-04-12

### Changed
- First working version of the API including database tables

### Added
- Added unit tests for the API

## [0.4.0] - 2024-04-11

### Changed
- changed database to the Posit Connect database
- Updated the department prompts
- automatic evaluation using GPT first version

## [0.3.3] - 2024-03-11

### Added
- Notebook to test incremental creation of the discharge documents
- Created a template for the API

### Changed
- Updated the evaluation dashboard to optionally use incremental creation instead of direct, by default this is turned off (uses the ITERATIVE constant)

### Fixed
- Use OpenAI API version `2024-02-1` instead of the outdated version, due to deprecation from Azure

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


