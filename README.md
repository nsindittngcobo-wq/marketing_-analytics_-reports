# Local Marketing Attribution Pipeline (DuckDB + Python + Power BI)

## The Problem I'm Solving
Marketing teams spend money on platforms like Google and Meta Ads, while sales teams log conversions in a completely separate CRM system. Because these systems don't talk to each other natively, it's incredibly hard for leadership to answer a simple question: **Which specific ads are actually driving revenue, and which ones are wasting budget?**

To solve this for tech-forward growth operations, I built a local, open-source data pipeline that bridges marketing spend data with sales funnel conversions. 

## The Architecture (Why I chose this stack)
Instead of relying on heavy cloud data warehouses, I built a local modern data stack using free tools:
* **Python:** To simulate raw, messy API extracts from ad networks and CRM logs.
* **DuckDB:** My local database engine. I chose DuckDB because it runs incredibly fast on-machine and processes data column-by-word without the hassle of a traditional server setup.
* **Parquet Files:** The final tables are exported as compressed Parquet files to keep local data footprints tiny.
* **Power BI Desktop:** Acts purely as a thin visualization and semantic layer, reading directly from the clean Parquet files.

## The Medallion Data Flow

### 1. Bronze (Raw Ingestion)
I loaded the raw data exactly as it arrived, appending an ingestion timestamp for historical auditing.

### 2. Silver (Data Quality & Cleaning)
Raw data is always messy. I used SQL inside DuckDB to fix multiple quality issues:
* **Trailing Spaces:** Wrapped text identifiers in `TRIM()` to prevent broken relational joins.
* **Negative Financial Values:** Used `ABS()` to flip negative ad spend figures caused by systemic software input errors.
* **Entity Resolution:** The data generation process created duplicate rows where the same Ad ID had completely different campaign descriptions. I deployed a `QUALIFY ROW_NUMBER() OVER(PARTITION BY ad_id ORDER BY ingested_at DESC) = 1` window function to isolate the latest record of truth and guarantee a unique key.

### 3. Gold (The Star Schema)
I structured the clean data into a clean Star Schema:
* `gold_dim_ads`: Unique lookup table for campaign names and marketing channels.
* `gold_dim_date`: A calculated calendar table to support time-based metrics.
* `gold_fact_leads`: Core transactional table containing individual lead conversions and financial deal values.

## Challenges Faced & How I Overcame Them

Building an end-to-end data stack locally meant facing structural blockers. Here are the three primary engineering hurdles I debugged:

### 1. The Duplicate Key Paradox (Fixing the One-to-Many Breakage)
* **The Blocker:** When I tried connecting my Ads dimension to the Leads fact table in Power BI using a standard **One-to-Many (`1:*`) active relationship**, the engine threw a critical error stating that my dimension column contained duplicate values. Because the mock data randomly assigned campaigns, multiple rows existed for the exact same `ad_id`.
* **The Fix:** I rejected a broad `SELECT DISTINCT` command because it doesn't resolve descriptive field shifts over time. Instead, I engineered a window function override inside DuckDB:
  `QUALIFY ROW_NUMBER() OVER (PARTITION BY ad_id ORDER BY ingested_at DESC) = 1`
  This grouped duplicate ads into internal buckets, sorted them by their ingestion timestamp, and isolated row #1. This approach guaranteed a 100% unique primary key list for Power BI without losing historical data context.

### 2. DuckDB Compiler Mismatches on Windows
* **The Blocker:** During early deployment phases, the DuckDB SQL compiler threw syntax parsing errors when handling multi-line strings with explicit table alias shortcuts (`FROM silver_leads l`). 
* **The Fix:** I modified the Phase C query to remove ambiguous short aliases entirely, replacing them with absolute, fully qualified table paths (`FROM silver_leads INNER JOIN silver_ads ON silver_leads.ad_id = silver_ads.ad_id`). This removed compiling ambiguity and cleared the pipeline deployment blocks.

### 3. File Deployment Locks (The Hidden Missing Dashboard Bug)
* **The Blocker:** After finalizing my Power BI visual report layouts, my dashboard file completely vanished from my tracking queue in GitHub Desktop and refused to stage for deployment.
* **The Fix:** I discovered that because Power BI Desktop was actively running, Windows placed a backend lock on the `.pbix` file to prevent data corruption, blocking Git from reading it. Closing the application freed the system file lock, allowing the asset to stage, commit, and push smoothly.

## Power BI Modeling & DAX Measures
In Power BI's Model View, I mapped out active, One-to-Many (`1:*`) relationships with a Single cross-filter direction moving down from the dimensions to the fact table. 

To ensure the report runs fast and handles errors defensively, I avoided implicit column dragging and wrote explicit DAX measures:
* `Total Closed Revenue` = `CALCULATE(SUM(gold_fact_leads[deal_value_zar]), gold_fact_leads[lead_status] = "CLOSED WON")`
* `ROAS` = `DIVIDE([Total Closed Revenue], [Total Ad Spend], 0)` *(The 0 safety parameter prevents #DIV/0! calculation crashes).*

## Key Insight from the Data
The dashboard reveals an overall **Return on Ad Spend (ROAS) of 23,93**. However, by using hierarchical row nesting to drill down into the campaign names inside the Matrix visual, you can see that this success was masking a few underperforming campaigns that had high ad spend but generated zero sales conversions.
