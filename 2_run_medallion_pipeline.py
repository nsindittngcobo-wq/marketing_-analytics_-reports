import duckdb

# Create a local database file called 'company_lakehouse.db'
conn = duckdb.connect('company_lakehouse.db')

print("Running Medallion Architecture Pipeline...")

# =============================================
# PHASE A: BRONZE LAYER (Raw Ingestion)
# =============================================
print("Loading raw data into Bronze tables...")

# Load the CSV files exactly as they are, adding a timestamp to track when it arrived
conn.execute("""
    CREATE OR REPLACE TABLE bronze_ads AS
    SELECT *, current_timestamp AS ingested_at FROM read_csv_auto('marketing_ads.csv');
""")

conn.execute("""
    CREATE OR REPLACE TABLE bronze_leads AS
    SELECT *, current_timestamp AS ingested_at FROM read_csv_auto('crm_leads.csv');
""")

# =========================================
# PHASE B: SILVER LAYER (Data Cleaning)
# =========================================
print("Cleaning data and moving to Silver tables...")

# Cleanig the Ads table
# FIXED: We use a window function (QUALIFY) to pick exactly ONE unique entry per AdID
# This completely eliminates duplicates caused by the randomw data generation mistakes 
conn.execute("""
    CREATE OR REPLACE TABLE silver_ads AS
    SELECT
    TRIM(CAST(AdID AS VARCHAR)) AS ad_id, -- Removes hidden spaces around IDs
    COALESCE(TRIM(CAST(CampaignName AS VARCHAR)), 'Unknown Campaign') AS campaign_name, -- Fixes missing values
    UPPER(TRIM(CAST(Channel AS VARCHAR))) AS marketing_channel, -- Standardises text casing (e.g. GOOGLE ADS)
    ABS(CAST(AdSpend_ZAR AS DECIMAL(18,2))) AS ad_spend_zar, -- Converts negative errors into posititve numbers
    ingested_at
FROM bronze_ads
WHERE AdID IS NOT NULL -- Eliminates corrupted rows with missing primary keys
QUALIFY ROW_NUMBER() OVER(PARTITION BY TRIM(CAST(AdID AS VARCHAR)) ORDER BY ingested_at DESC) = 1; 
""")

# Cleaning the CRM Leads table
conn.execute("""
    CREATE OR REPLACE TABLE silver_leads AS
    SELECT
    TRIM(CAST(LeadID AS VARCHAR)) AS lead_id,
    TRIM(CAST(AdID AS VARCHAR)) AS ad_id,
    COALESCE(UPPER(TRIM(CAST(LeadStatus AS VARCHAR))), 'NEW') AS lead_status,
    COALESCE(CAST(DealValue_ZAR AS DECIMAL(18,2)), 0.00) AS deal_value_zar,
    CAST(CreatedDate AS DATE) AS lead_date,
    ingested_at
FROM bronze_leads
WHERE LeadID IS NOT NULL;
""")

# =============================================
# PHASE C: GOLD LAYER (Star Schema Modeling)
# =============================================
print("Shaping data into Gold Star Schema dimensions and facts...")

# 1. Dimension Table: Ads Information
conn.execute("""
    CREATE OR REPLACE TABLE gold_dim_ads AS
    SELECT ad_id, campaign_name, marketing_channel, MAX(ad_spend_zar) AS ad_spend_zar 
    FROM silver_ads
    GROUP BY ad_id, campaign_name, marketing_channel;
""")

# 2. Dimension Table: Date (Crucial DP-600 skill for time-based metric)
conn.execute("""
    CREATE OR REPLACE TABLE gold_dim_date AS
    SELECT
        datum AS date_key,
        YEAR(datum) AS calender_year,
        MONTH(datum) AS month_number,
        MONTHNAME(datum) AS month_name,
        QUARTER(datum) AS calender_quarter
    FROM (
        SELECT CAST(range AS DATE) AS datum
        FROM range(DATE '2026-01-01', DATE '2026-12-31', INTERVAL 1 DAY)
    );
""")

# 3. Fact Table: Business Transactions (Leads)
conn.execute("""
    CREATE OR REPLACE TABLE gold_fact_leads AS
    SELECT
    silver_leads.lead_id,
    silver_leads.ad_id,
    silver_leads.lead_date AS date_key,
    silver_leads.lead_status,
    silver_leads.deal_value_zar,
    CASE WHEN silver_leads.lead_status = 'CLOSED WON' THEN 1 ELSE 0 END AS is_won -- Pre-calculated flag for easier DAX math
FROM silver_leads 
INNER JOIN silver_ads ON silver_leads.ad_id = silver_ads.ad_id; -- Ensures no orphan leads without real ads slip through
""")

# Export our perfect Gold tables to industry-standard Parquet files for Power BI
print("Exporting Gold tables to compressed Parquet files...")
conn.execute("COPY gold_dim_ads TO 'gold_dim_ads.parquet' (FORMAT PARQUET);")
conn.execute("COPY gold_dim_date TO 'gold_dim_date.parquet' (FORMAT PARQUET);")
conn.execute("COPY gold_fact_leads TO 'gold_fact_leads.parquet' (FORMAT PARQUET);")

print("All done! Data is cleaned, modeled, and ready for Power BI.")
conn.close()