CITY_CHOICES = (
    ("NYC", "New York City"),
    ("LA", "Los Angeles"),
    ("SF", "San Francisco"),
)

RESULT_GRADES = (
    ("GREEN", "Green"),
    ("YELLOW", "Yellow"),
    ("RED", "Red"),
    ("UNDETERMINED", "Undetermined"),
)

DECISION_MODES = (
    ("AUTO_CONFIDENT", "Auto Confident"),
    ("AUTO_CONSERVATIVE", "Auto Conservative"),
)

SNAPSHOT_STATUS = (
    ("ACTIVE", "Active"),
    ("STALE", "Stale"),
    ("FAILED", "Failed"),
)

PLAN_QUOTAS = {
    "starter": 30,
    "pro": 200,
    "team": 1000,
}
