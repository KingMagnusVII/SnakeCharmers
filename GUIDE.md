\# SnakeCharmers — Project Guide



\## 1. Project Overview



SnakeCharmers is a warehouse slotting optimization research prototype. It uses historical Brazilian e-commerce data from the Olist dataset and a synthetic warehouse layout to compare product-storage allocations.



The goal is to investigate whether a proposed storage allocation can reduce simulated picker travel compared with a baseline allocation.



\*\*Important:\*\* Warehouse locations, inventory assumptions, and walking distances are simulated. Results should not be interpreted as measurements from a real warehouse.



\## 2. Project Workflow



The main workflow consists of the following stages:



1\. \*\*Data preparation:\*\* Load and prepare the required Olist datasets.

2\. \*\*Demand analysis:\*\* Analyze product demand and assign demand classes.

3\. \*\*Demand forecasting:\*\* Use Ridge regression to estimate future weekly order-line demand.

4\. \*\*Warehouse generation:\*\* Create a synthetic warehouse with storage locations.

5\. \*\*Baseline allocation:\*\* Assign products to storage locations using the baseline method.

6\. \*\*Slotting optimization:\*\* Use a greedy heuristic and bounded feasible-swap local search to explore alternative allocations.

7\. \*\*Route simulation:\*\* Estimate picker route distances using nearest-next-SKU selection and Manhattan distance.

8\. \*\*Evaluation:\*\* Compare the baseline and selected layouts.

9\. \*\*Dashboard visualization:\*\* Explore generated results and validation reports.



The default pipeline uses a heuristic optimizer. The separate MILP assortment-selection module is not part of the default pipeline unless explicitly integrated.



\## 3. Warehouse Configuration



The project documentation describes a synthetic warehouse containing:



\- 6 aisles

\- 2 rack sides per aisle

\- 5 bays per rack side

\- 4 shelf levels

\- 4 additional oversized slots



The actual layout depends on the configuration files.



Relevant configuration files:



\- `config/warehouse\_config.json`

\- `config/simulation\_config.json`



Review these files before changing warehouse dimensions or simulation settings.



\## 4. Data Sources and Assumptions



The project uses historical Olist Brazilian e-commerce data from 2016–2018. The described default pipeline reads order, order-item, and product datasets.



The dataset represents historical e-commerce activity, not a live warehouse inventory feed.



Important limitations:



\- Each order-item line is treated as quantity `1.0` in the described pipeline.

\- Demand forecasting estimates order-line counts, not verified current inventory or necessarily actual unit sales.

\- Current inventory quantities are not directly available from the historical dataset.

\- A representative inventory quantity of one unit is a simulation assumption, not an observed inventory record.

\- Missing hazard or handling information must not be treated as verified safety compliance.



Always distinguish recorded data from assumptions and simulated values.



\## 5. Installation and Setup



Run commands from the repository root in PowerShell.



\### Install dependencies



If the virtual environment already exists:



```powershell

.\\.venv\\Scripts\\python.exe -m pip install -r requirements.txt

```



If the virtual environment does not exist, create it first:



```powershell

python -m venv .venv

.\\.venv\\Scripts\\python.exe -m pip install -r requirements.txt

```



\### Prepare the dataset



If the raw Olist datasets are missing, inspect the available download and preparation scripts before running:



```powershell

.\\.venv\\Scripts\\python.exe -m scripts.download\_olist

.\\.venv\\Scripts\\python.exe -m scripts.prepare\_data

```



Downloading data may require a configured Kaggle account and API credentials. Never commit credentials such as `kaggle.json`.



\## 6. Running the Project



\### Run tests



```powershell

.\\.venv\\Scripts\\python.exe -m pytest -q

```



\### Run the pipeline



```powershell

.\\.venv\\Scripts\\python.exe -m scripts.run\_pipeline

```



\### Validate saved layouts



```powershell

.\\.venv\\Scripts\\python.exe scripts\\validate\_saved\_layouts.py

```



\### Launch the Streamlit dashboard



```powershell

.\\.venv\\Scripts\\python.exe -m streamlit run dashboard.py

```



Run these commands from the repository root. If a command fails, inspect the full error message and traceback before deciding what needs to be fixed.



\## 7. Generated Files



Processed data is stored under:



\- `data/processed/`



Reports are stored under:



\- `reports/`



Layout validation can generate:



\- `data/processed/baseline\_violations.csv`

\- `data/processed/optimized\_violations.csv`



The presence and freshness of these files depend on successful execution of the pipeline and validation scripts.



\## 8. Understanding Validation Results



Validation reports may include the following statuses:



\- \*\*VIOLATION:\*\* A rule breach has been identified.

\- \*\*UNVERIFIED:\*\* Available information is insufficient to confirm compliance.



`UNVERIFIED` does not mean that the layout passed validation. Missing or unknown metadata must remain clearly identified.



\## 9. Understanding Optimization Results



The simulated route distance uses nearest-next-SKU routing and Manhattan distance over synthetic warehouse geometry.



Interpret the results carefully:



\- The heuristic optimizer does not guarantee a globally optimal allocation.

\- The selected layout may be identical to the baseline.

\- An improvement is not guaranteed for every dataset or configuration.

\- Simulated route distances are not real-world walking measurements.

\- Hardcoded example metrics in the dashboard must not be presented as live pipeline results.



Before reporting a performance improvement, verify that the displayed metrics come from current pipeline outputs and that the comparison uses consistent assumptions.



\## 10. Troubleshooting



\### Dependencies fail to install



Check the Python version, confirm that the intended virtual environment is being used, and inspect the error printed by pip.



\### The pipeline fails



Read the complete traceback and inspect the referenced file and line. A pipeline error should not automatically be attributed to the dashboard.



\### The dashboard fails to load



Confirm that dependencies are installed and that the expected processed files exist. Running the pipeline again will not necessarily resolve an independent dashboard code error.



\### Results appear outdated



Check the timestamps of the generated files and confirm that the pipeline completed successfully.



\### Validation reports contain UNVERIFIED entries



Inspect the relevant missing metadata and assumptions. Do not relabel an unverified result as a pass.



\## 11. Development Checklist



Before accepting a change:



1\. Confirm that you are working on the intended Git branch.

2\. Keep unrelated files unchanged.

3\. Run the relevant tests.

4\. Run the pipeline if the change affects pipeline behavior.

5\. Run layout validation when appropriate.

6\. Verify that the dashboard displays current results.

7\. Document assumptions, missing data, and simulation limitations.

8\. Review the Git diff before committing.



\---



\*\*Scope note:\*\* This guide describes the documented workflow and assumptions of the project. It does not guarantee that every command works in the current checkout. Verify the current code and runtime outputs before relying on the results.

