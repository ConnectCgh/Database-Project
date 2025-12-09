# Modification Log

## 2025-12-09
- Replaced all customer-facing view logic with raw SQL helpers to fetch and manipulate meals, merchants, discounts, and orders without using Django ORM abstractions.
- Reimplemented merchant management views (platform applications, meals, discounts, and order handling) to run explicit SQL statements while keeping template data structures intact.
- Rebuilt platform, rider, login, and register views to rely solely on direct SQL queries/updates, introducing a shared `Project/db_utils.py` helper for reusable query utilities.
