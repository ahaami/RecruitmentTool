"""Central configuration — loads .env and exposes all settings."""

import os
from dotenv import load_dotenv

load_dotenv()


# --- Supabase ---
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]

# --- Anthropic (Claude) ---
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

# --- Apollo.io ---
APOLLO_API_KEY = os.environ.get("APOLLO_API_KEY", "")

# --- Resend (email) ---
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
CALLSHEET_TO_EMAIL = os.environ.get("CALLSHEET_TO_EMAIL", "")
CALLSHEET_FROM_EMAIL = os.environ.get("CALLSHEET_FROM_EMAIL", "")

# --- Pipeline settings ---
DAILY_CALL_LIMIT = int(os.environ.get("DAILY_CALL_LIMIT", "20"))
COOLDOWN_DAYS = int(os.environ.get("COOLDOWN_DAYS", "14"))
MIN_GROWTH_SCORE = int(os.environ.get("MIN_GROWTH_SCORE", "40"))
MAX_RETRIES = int(os.environ.get("MAX_RETRIES", "3"))
RETRY_DELAY_DAYS = int(os.environ.get("RETRY_DELAY_DAYS", "3"))

# --- Target locations ---
TARGET_CITIES = [
    c.strip()
    for c in os.environ.get(
        "TARGET_CITIES", "Sydney,Melbourne,Brisbane,Perth,Canberra"
    ).split(",")
]
