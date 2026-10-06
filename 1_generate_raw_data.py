import os
import pandas as pd
import numpy as np

# Make sure that our random data is the same every time
np.random.seed(42)
total_records = 1200

print("Generating dirty marketing data...")

# 1. Create simulated raw marketing data (with messiness)
ad_ids = [f" AD-{i:04d} " for i in range(1, 101)] # Added intentional spaces to trim later
campaigns = ["Winter Surge", "Spring Blossom", "Tech Innovate", "Green Eco", None] # Included missing values
channels = ["google ads", "Meta Ads", "LINKEDIN", "Twitter/X"] # Inconsistent name casing

ads_data = {
    "AdID": np.random.choice(ad_ids, 100),
    "CampaignName": np.random.choice(campaigns, 100),
    "Channel": np.random.choice(channels, 100),
    # Some numbers are negative due  to "system erros" we need to clean up
    "AdSpend_ZAR": np.random.choice([1500.0, -250.0, 5000.55, 12000.0, 0.0], 100)
}
df_ads = pd.DataFrame(ads_data)

# 2. Create simulated CRM Leads data 
leads_data = {
    "LeadID": [f"LEA-{i:05d}" for i in range(1, total_records + 1)],
    "AdID": np.random.choice(ad_ids, total_records),
    "LeadStatus": np.random.choice(["Closed Won", "Closed Lost", "Contacted", "New", None], total_records, p=[0.2, 0.3, 0.3, 0.15, 0.05]),
    "DealValue_ZAR": np.random.choice([50000.00, 125000.00, 0.00, None], total_records),
    "CreatedDate": pd.date_range(start="2026-01-01", periods=total_records, freq='h').strftime('%Y-%m-%d')
}
df_leads = pd.DataFrame(leads_data)

# Save dataframes as raw CSV files
df_ads.to_csv("marketing_ads.csv", index=False)
df_leads.to_csv("crm_leads.csv", index=False)

print("Success! Raw 'dirty' CSV files have been created in your folder.")