"""服务层 — 用户画像"""
from backend.user_profile.profile_db import (
    get_profile, update_profile, add_search_history,
    personalize_routes, extract_and_update_preferences,
)
