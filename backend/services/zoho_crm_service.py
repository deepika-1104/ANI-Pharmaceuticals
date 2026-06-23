"""
Zoho CRM integration service — DISABLED, retained for future re-activation.

HOW TO RE-ENABLE:
  1. Fill in ZOHO_* variables in backend/.env (credentials already preserved there).
  2. Uncomment everything below the dashed line.
  3. In orchestrator/query_orchestrator.py uncomment the three CRM blocks
     (marked with "# ── ZOHO CRM ──").
  4. Install the requests library if not already present (it's in requirements.txt).

The integration fetches records from Zoho CRM modules (Patients, Medicines, Leads,
Contacts) in parallel with MongoDB data, merging them into the LLM context so the
AI can answer questions that span both data sources.
"""

# ──────────────────────────────────────────────────────────────────────────────
# FULL IMPLEMENTATION — uncomment to activate
# ──────────────────────────────────────────────────────────────────────────────

# import os
# import logging
# import requests
# from datetime import datetime, timezone
# from typing import Any, Optional
#
# logger = logging.getLogger("voxa.crm")
#
#
# class ZohoCRMService:
#     """
#     Fetches records from Zoho CRM modules to supplement MongoDB data.
#
#     Authentication: OAuth2 with automatic token refresh.
#     Data centre:    Configured via ZOHO_BASE_URL (defaults to India DC).
#     """
#
#     def __init__(self) -> None:
#         self.client_id     = os.getenv("ZOHO_CLIENT_ID", "")
#         self.client_secret = os.getenv("ZOHO_CLIENT_SECRET", "")
#         self.access_token  = os.getenv("ZOHO_ACCESS_TOKEN", "")
#         self.refresh_token = os.getenv("ZOHO_REFRESH_TOKEN", "")
#         self.redirect_uri  = os.getenv("ZOHO_REDIRECT_URI", "http://localhost:8000/callback")
#         self.base_url      = os.getenv("ZOHO_BASE_URL", "https://www.zohoapis.in/crm/v2")
#         self.accounts_url  = os.getenv("ZOHO_ACCOUNTS_URL", "https://accounts.zoho.in/oauth/v2/token")
#
#         # Zoho module API names — override in .env if your account uses custom names
#         self.patients_module  = os.getenv("ZOHO_PATIENTS_MODULE", "Patient")
#         self.medicines_module = os.getenv("ZOHO_MEDICINES_MODULE", "Medicines_Module")
#
#         self._session = requests.Session()
#         self._session.headers.update({"Authorization": f"Zoho-oauthtoken {self.access_token}"})
#
#     # ── Auth ──────────────────────────────────────────────────────────────────
#
#     def _refresh_access_token(self) -> bool:
#         """
#         Exchange the refresh_token for a new access_token.
#         Updates the session header in-place.
#         Returns True on success.
#         """
#         if not self.refresh_token:
#             logger.error("ZOHO_REFRESH_TOKEN is not set — cannot refresh")
#             return False
#         try:
#             resp = requests.post(
#                 self.accounts_url,
#                 params={
#                     "refresh_token": self.refresh_token,
#                     "client_id":     self.client_id,
#                     "client_secret": self.client_secret,
#                     "grant_type":    "refresh_token",
#                 },
#                 timeout=10,
#             )
#             resp.raise_for_status()
#             data = resp.json()
#             new_token = data.get("access_token")
#             if not new_token:
#                 logger.error(f"Token refresh failed — Zoho response: {data}")
#                 return False
#             self.access_token = new_token
#             self._session.headers["Authorization"] = f"Zoho-oauthtoken {new_token}"
#             logger.info("Zoho access token refreshed")
#             return True
#         except Exception as exc:
#             logger.error(f"Token refresh error: {exc}")
#             return False
#
#     # ── HTTP layer ────────────────────────────────────────────────────────────
#
#     def _get(self, path: str, params: Optional[dict] = None) -> dict:
#         """
#         GET {base_url}/{path} with auto-retry on 401 (token refresh).
#         Returns the parsed JSON body.
#         """
#         url = f"{self.base_url.rstrip('/')}/{path.lstrip('/')}"
#         resp = self._session.get(url, params=params or {}, timeout=15)
#         if resp.status_code == 401:
#             logger.warning("Zoho 401 — refreshing token and retrying")
#             if self._refresh_access_token():
#                 resp = self._session.get(url, params=params or {}, timeout=15)
#         resp.raise_for_status()
#         return resp.json()
#
#     # ── Generic record fetcher ─────────────────────────────────────────────────
#
#     def list_records(
#         self,
#         module: str,
#         fields: Optional[list[str]] = None,
#         criteria: Optional[str] = None,
#         limit: int = 50,
#     ) -> list[dict[str, Any]]:
#         """
#         Fetch up to *limit* records from any Zoho CRM module.
#
#         Args:
#             module:   API name of the CRM module (e.g. "Leads", "Patient").
#             fields:   List of field API names to return. None = all fields.
#             criteria: COQL-style filter string, e.g. "(Status:equals:Active)".
#             limit:    Max records to fetch (Zoho max per page = 200).
#         """
#         params: dict = {"per_page": min(limit, 200)}
#         if fields:
#             params["fields"] = ",".join(fields)
#         if criteria:
#             params["criteria"] = criteria
#         try:
#             data = self._get(module, params)
#             return data.get("data", [])
#         except Exception as exc:
#             logger.error(f"list_records({module}) failed: {exc}")
#             return []
#
#     # ── Module-specific helpers ───────────────────────────────────────────────
#
#     def list_patients(self, limit: int = 50) -> list[dict[str, Any]]:
#         """Fetch patient records from the Zoho Patients module."""
#         return self.list_records(self.patients_module, limit=limit)
#
#     def list_medicines(self, limit: int = 50) -> list[dict[str, Any]]:
#         """Fetch medicine/product records from the Zoho Medicines module."""
#         return self.list_records(self.medicines_module, limit=limit)
#
#     def list_leads(self, limit: int = 30) -> list[dict[str, Any]]:
#         """Fetch sales leads from the Zoho Leads module."""
#         return self.list_records("Leads", limit=limit)
#
#     def list_contacts(self, limit: int = 30) -> list[dict[str, Any]]:
#         """Fetch contacts from the Zoho Contacts module."""
#         return self.list_records("Contacts", limit=limit)
#
#     def list_deals(self, limit: int = 30) -> list[dict[str, Any]]:
#         """Fetch deals/opportunities from the Zoho Deals module."""
#         return self.list_records("Deals", limit=limit)
#
#     def search_records(
#         self,
#         module: str,
#         keyword: str,
#         limit: int = 20,
#     ) -> list[dict[str, Any]]:
#         """
#         Full-text search within a Zoho CRM module.
#         Uses the /search endpoint with the 'word' parameter.
#         """
#         try:
#             data = self._get(f"{module}/search", {"word": keyword, "per_page": min(limit, 200)})
#             return data.get("data", [])
#         except Exception as exc:
#             logger.error(f"search_records({module}, {keyword!r}) failed: {exc}")
#             return []
#
#     def upsert_record(
#         self,
#         module: str,
#         record: dict[str, Any],
#         duplicate_field_mappings: Optional[list[str]] = None,
#     ) -> Optional[str]:
#         """
#         Create or update a single record in *module*.
#         Returns the Zoho record ID on success, None on failure.
#         """
#         url = f"{self.base_url.rstrip('/')}/{module.lstrip('/')}/upsert"
#         payload = {
#             "data": [record],
#         }
#         if duplicate_field_mappings:
#             payload["duplicate_check_fields"] = duplicate_field_mappings
#         try:
#             resp = self._session.post(url, json=payload, timeout=15)
#             if resp.status_code == 401:
#                 if self._refresh_access_token():
#                     resp = self._session.post(url, json=payload, timeout=15)
#             resp.raise_for_status()
#             result = resp.json().get("data", [{}])[0]
#             return result.get("details", {}).get("id")
#         except Exception as exc:
#             logger.error(f"upsert_record({module}) failed: {exc}")
#             return None
#
#     # ── Health check ──────────────────────────────────────────────────────────
#
#     def is_available(self) -> bool:
#         """Return True if the service is configured and reachable."""
#         if not self.client_id or not self.access_token:
#             return False
#         try:
#             self._get("org")
#             return True
#         except Exception:
#             return False
#
#
# # ── Singleton ─────────────────────────────────────────────────────────────────
# _crm_service: Optional[ZohoCRMService] = None
#
#
# def get_crm_service() -> Optional[ZohoCRMService]:
#     """
#     Return the shared ZohoCRMService instance, or None if credentials
#     are not configured.
#     """
#     global _crm_service
#     if _crm_service is None:
#         required = ["ZOHO_CLIENT_ID", "ZOHO_CLIENT_SECRET", "ZOHO_ACCESS_TOKEN"]
#         if all(os.getenv(k) for k in required):
#             _crm_service = ZohoCRMService()
#             logger.info("ZohoCRMService initialised")
#         else:
#             logger.debug("Zoho CRM credentials not set — CRM disabled")
#     return _crm_service
