"""KoboToolbox API v2 client."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import requests


BASE_URL = "https://kf.kobotoolbox.org"

# Default export settings that use XLSForm internal names (lang=_xml)
# Keys accepted by /export-settings/ (reusable config)
_DEFAULT_EXPORT_SETTING_KEYS: dict[str, Any] = {
    "type": "xls",
    "fields_from_all_versions": True,
    "group_sep": "/",
    "hierarchy_in_labels": False,
    "lang": "_xml",
    "multiple_select": "summary",
    "flatten": False,
    "xls_types_as_text": False,
    "include_media_url": False,
    "fields": [],
    "query": {},
}

# Keys for one-off async /exports/ (superset — allows filtering by submission IDs)
_DEFAULT_EXPORT_PAYLOAD: dict[str, Any] = {
    **_DEFAULT_EXPORT_SETTING_KEYS,
    "submission_ids": [],
}


class KoboError(Exception):
    """Raised when the KoboToolbox API returns an error response."""


class ExportTimeoutError(KoboError):
    """Raised when waiting for an export exceeds the timeout."""


class KoboClient:
    """Simple synchronous client for the KoboToolbox API v2.

    Parameters
    ----------
    api_token:
        KoboToolbox API token (found in Account Settings → Security).
    base_url:
        Base URL of the KoboToolbox instance.
        Defaults to the public server ``https://kf.kobotoolbox.org``.
    """

    def __init__(
        self,
        api_token: str,
        base_url: str = BASE_URL,
    ) -> None:
        self._base = base_url.rstrip("/")
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Authorization": f"Token {api_token}",
                "Accept": "application/json",
            }
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _url(self, path: str) -> str:
        return f"{self._base}{path}"

    def _raise_for_status(self, response: requests.Response) -> None:
        if not response.ok:
            try:
                detail = response.json()
            except Exception:
                detail = response.text
            raise KoboError(
                f"HTTP {response.status_code} {response.request.url}: {detail}"
            )

    def _get(self, path: str, **params: Any) -> Any:
        resp = self._session.get(self._url(path), params=params or None)
        self._raise_for_status(resp)
        return resp.json()

    def _post(self, path: str, payload: dict[str, Any]) -> Any:
        resp = self._session.post(self._url(path), json=payload)
        self._raise_for_status(resp)
        return resp.json()

    # ------------------------------------------------------------------
    # Surveys (assets of type "survey")
    # ------------------------------------------------------------------

    def get_surveys(
        self,
        limit: int = 100,
        offset: int = 0,
        search: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return a list of survey assets for the authenticated user.

        Parameters
        ----------
        limit:   Max results per page (API max: 300).
        offset:  Pagination offset.
        search:  Optional free-text search query.

        Returns a list of dicts with keys such as ``uid``, ``name``,
        ``deployment_status``, ``date_modified``, etc.
        """
        params: dict[str, Any] = {
            "asset_type": "survey",
            "limit": limit,
            "offset": offset,
        }
        if search:
            params["q"] = search
        data = self._get("/api/v2/assets/", **params)
        return data.get("results", [])

    def get_survey(self, uid: str) -> dict[str, Any]:
        """Return full details for a single survey asset."""
        return self._get(f"/api/v2/assets/{uid}/")

    def get_survey_content(self, uid: str) -> dict[str, Any]:
        """Return the XLSForm content of a survey (survey, choices, settings)."""
        return self._get(f"/api/v2/assets/{uid}/content/")

    # ------------------------------------------------------------------
    # Export settings (reusable configurations)
    # ------------------------------------------------------------------

    def get_or_create_export_setting(
        self,
        asset_uid: str,
        name: str,
        **overrides: Any,
    ) -> tuple[str, bool]:
        """Return the uid of an export setting with the given name, creating it if needed.

        Parameters
        ----------
        asset_uid:  UID of the survey asset.
        name:       Display name for the setting.
        **overrides:
            Any key from ``export_settings`` to override the defaults.

        Returns a ``(uid, created)`` tuple where ``created`` is ``True`` if
        the setting was newly created, or ``False`` if an existing one was found.
        """
        for setting in self.list_export_settings(asset_uid):
            if setting.get("name") == name:
                return setting["uid"], False

        uid = self.create_export_setting(asset_uid, name, **overrides)
        return uid, True

    def create_export_setting(
        self,
        asset_uid: str,
        name: str,
        **overrides: Any,
    ) -> str:
        """Create a named export setting for an asset and return its uid.

        Parameters
        ----------
        asset_uid:  UID of the survey asset.
        name:       Display name for the setting.
        **overrides:
            Any key from ``export_settings`` to override the defaults.
            Defaults use ``lang="_xml"`` (XLSForm internal field names)
            and ``type="xls"``.

        Returns the ``uid`` of the created export setting.
        Raises :exc:`KoboError` if a setting with the same name already exists.
        Use :meth:`get_or_create_export_setting` to avoid that error.
        """
        settings = {**_DEFAULT_EXPORT_SETTING_KEYS, **overrides}
        payload: dict[str, Any] = {
            "name": name,
            "export_settings": settings,
        }
        data = self._post(f"/api/v2/assets/{asset_uid}/export-settings/", payload)
        return data["uid"]

    def list_export_settings(self, asset_uid: str) -> list[dict[str, Any]]:
        """Return all saved export settings for an asset."""
        data = self._get(f"/api/v2/assets/{asset_uid}/export-settings/")
        return data.get("results", [])

    # ------------------------------------------------------------------
    # Async exports (trigger → poll → download)
    # ------------------------------------------------------------------

    def trigger_export(
        self,
        asset_uid: str,
        type: str = "xls",
        lang: str = "_xml",
        **overrides: Any,
    ) -> str:
        """Trigger an async export task and return its ``uid``.

        Parameters
        ----------
        asset_uid:  UID of the survey asset.
        type:       Export format — ``"xls"``, ``"csv"``, ``"geojson"``, etc.
        lang:       Language for labels. ``"_xml"`` uses XLSForm field names.
        **overrides:
            Extra ``ExportCreatePayload`` fields (e.g. ``fields``,
            ``query``, ``submissions_id``).

        Returns the ``uid`` of the export task. Use :meth:`wait_for_export`
        to poll for completion.
        """
        payload: dict[str, Any] = {
            **_DEFAULT_EXPORT_PAYLOAD,
            "type": type,
            "lang": lang,
            **overrides,
        }
        data = self._post(f"/api/v2/assets/{asset_uid}/exports/", payload)
        return data["uid"]

    def wait_for_export(
        self,
        asset_uid: str,
        export_uid: str,
        poll_interval: float = 3.0,
        timeout: float = 120.0,
    ) -> dict[str, Any]:
        """Poll until an export task is complete and return the response dict.

        The returned dict includes a ``result`` key with the direct download URL.

        Parameters
        ----------
        asset_uid:      UID of the survey asset.
        export_uid:     UID of the export task (from :meth:`trigger_export`).
        poll_interval:  Seconds between status checks.
        timeout:        Maximum seconds to wait before raising
                        :exc:`ExportTimeoutError`.
        """
        path = f"/api/v2/assets/{asset_uid}/exports/{export_uid}/"
        deadline = time.monotonic() + timeout

        while True:
            data = self._get(path)
            status = data.get("status", "")

            if status == "complete":
                return data
            if status == "error":
                raise KoboError(
                    f"Export {export_uid} failed: {data.get('message', 'unknown error')}"
                )
            if time.monotonic() >= deadline:
                raise ExportTimeoutError(
                    f"Export {export_uid} did not complete within {timeout}s "
                    f"(last status: {status!r})"
                )

            time.sleep(poll_interval)

    def download_export(
        self,
        asset_uid: str,
        export_uid: str,
        dest_path: str | Path,
        poll_interval: float = 3.0,
        timeout: float = 120.0,
    ) -> Path:
        """Wait for an export to complete, then download the file.

        Parameters
        ----------
        asset_uid:      UID of the survey asset.
        export_uid:     UID of the export task (from :meth:`trigger_export`).
        dest_path:      Local path to save the downloaded file.
        poll_interval:  Seconds between status checks while waiting.
        timeout:        Maximum seconds to wait for the export to finish.

        Returns the resolved :class:`~pathlib.Path` of the saved file.
        """
        result = self.wait_for_export(asset_uid, export_uid, poll_interval, timeout)
        download_url: str = result["result"]

        dest = Path(dest_path)
        dest.parent.mkdir(parents=True, exist_ok=True)

        with self._session.get(download_url, stream=True) as resp:
            self._raise_for_status(resp)
            with dest.open("wb") as fh:
                for chunk in resp.iter_content(chunk_size=8192):
                    fh.write(chunk)

        return dest.resolve()

    # ------------------------------------------------------------------
    # High-level shortcut
    # ------------------------------------------------------------------

    def get_excel(
        self,
        asset_uid: str,
        export_uid: str | None = None,
        path: str | Path = "data_survey.xlsx",
        poll_interval: float = 3.0,
        timeout: float = 120.0,
    ) -> Path:
        """Download survey data as an Excel file in one call.

        If ``export_uid`` is provided, waits for that existing export task and
        downloads it. Otherwise, ensures a reusable export setting named
        ``"python-client"`` exists (creating it if needed), triggers a new
        export with the default configuration (``type="xls"``, ``lang="_xml"``),
        and downloads the result.

        Parameters
        ----------
        asset_uid:      UID of the survey asset.
        export_uid:     Optional UID of an already-triggered export task.
                        If omitted, a new export is triggered automatically.
        path:           Destination file path. Defaults to ``data_survey.xlsx``
                        in the current working directory.
        poll_interval:  Seconds between status checks while waiting.
        timeout:        Maximum seconds to wait for the export to finish.

        Returns the resolved :class:`~pathlib.Path` of the saved file.

        Example
        -------
        >>> saved = client.get_excel("atXzmELZmQgQkWD4cAnumv")
        >>> print(saved)
        /home/user/project/data_survey.xlsx
        """
        if export_uid is None:
            self.get_or_create_export_setting(asset_uid, name="python-client")
            export_uid = self.trigger_export(asset_uid)

        return self.download_export(asset_uid, export_uid, path, poll_interval, timeout)
