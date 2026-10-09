from __future__ import annotations

import asyncio
import base64
import http.cookiejar
import importlib
import importlib.metadata
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import zlib
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urldefrag, urlparse

UPSTREAM_VERSION = "0.4.12"
ZENDRIVER_VERSION = "0.17.1"
PYCRYPTODOME_VERSION = "3.23.0"
DEPENDENCY_DIR = Path(tempfile.gettempdir()) / "ftgirl-ddl-fdm" / "pydeps-fitgirl-ng-0.4.12"
PROFILE_DIR = Path(tempfile.gettempdir()) / "ftgirl-ddl-fdm" / "browser-profile"
FF_RE = re.compile(r"https?://(?:www\.)?fuckingfast\.co/[^\s\"'<>]+", re.I)
SUFFIX_RE = re.compile(r"\.part\d+\.rar$|\.rar$", re.I)
BASE58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def emit(payload: dict[str, Any], exit_code: int = 0) -> None:
    print(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
    raise SystemExit(exit_code)


def _ensure_dependency(import_name: str, distribution_name: str, required_version: str):
    """Install the audited dependency version in an isolated, reusable directory."""
    DEPENDENCY_DIR.mkdir(parents=True, exist_ok=True)
    if str(DEPENDENCY_DIR) not in sys.path:
        sys.path.insert(0, str(DEPENDENCY_DIR))
    importlib.invalidate_caches()

    try:
        installed = importlib.metadata.version(distribution_name)
        if installed == required_version:
            return importlib.import_module(import_name)
    except (importlib.metadata.PackageNotFoundError, ImportError, ModuleNotFoundError):
        pass

    package_spec = f"{distribution_name}=={required_version}"
    cmd = [
        sys.executable, "-m", "pip", "install",
        "--disable-pip-version-check", "--no-input", "--upgrade",
        "--target", str(DEPENDENCY_DIR), package_spec,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300, shell=False)
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "pip install failed")[-1600:]
        raise RuntimeError(f"Could not install {package_spec}: {detail.strip()}")

    # The bridge is a fresh Python process for each FDM parse. Invalidate disk
    # caches after installation; do not rely on a potentially older global copy.
    importlib.invalidate_caches()
    installed = importlib.metadata.version(distribution_name)
    if installed != required_version:
        raise RuntimeError(
            f"Expected {package_spec}, found {distribution_name}=={installed}"
        )
    return importlib.import_module(import_name)


def ensure_zendriver():
    return _ensure_dependency("zendriver", "zendriver", ZENDRIVER_VERSION)


def ensure_crypto_aes():
    _ensure_dependency("Crypto", "pycryptodome", PYCRYPTODOME_VERSION)
    from Crypto.Cipher import AES  # type: ignore
    return AES

def filename_from_url(url: str) -> str:
    parsed = urlparse(url)
    name = unquote(parsed.fragment or Path(parsed.path).name or "download")
    name = re.sub(r'[<>:"/\\|?*]', "_", name).strip(" .")
    return (name or "download")[:240]


def title_from_items(items: list[str], fallback: str = "FTGirl Download") -> str:
    if not items:
        return fallback
    name = filename_from_url(items[0])
    name = re.sub(r"_--_fitgirl-repacks\.site_--_.*$", "", name, flags=re.I)
    name = SUFFIX_RE.sub("", name)
    name = name.replace("_", " ").strip()
    return name or fallback


def _validated_host(url: str, allowed_hosts: set[str]) -> str:
    parsed = urlparse(url)
    if (
        parsed.scheme != "https"
        or (parsed.hostname or "").lower() not in allowed_hosts
        or parsed.username is not None
        or parsed.password is not None
        or parsed.port is not None
    ):
        raise ValueError("Only HTTPS URLs for supported hosts are allowed")
    return (parsed.hostname or "").lower()


def is_ff_page(url: str) -> bool:
    try:
        _validated_host(url, {"fuckingfast.co", "www.fuckingfast.co"})
        parts = [p for p in urlparse(url).path.split("/") if p]
        if len(parts) == 1:
            return bool(re.fullmatch(r"[A-Za-z0-9_-]+", parts[0]))
        if len(parts) == 2 and parts[0].lower() == "f":
            return bool(re.fullmatch(r"[A-Za-z0-9_-]+", parts[1]))
        return False
    except ValueError:
        return False


def extract_file_id(url: str) -> str:
    if not is_ff_page(url):
        raise ValueError("Invalid FuckingFast page URL")
    parts = [p for p in urlparse(url).path.split("/") if p]
    if len(parts) == 2 and parts[0].lower() == "f":
        candidate = parts[1]
    elif len(parts) == 1:
        candidate = parts[0]
    else:
        raise ValueError("Unsupported FuckingFast file URL path")
    if not re.fullmatch(r"[A-Za-z0-9_-]+", candidate):
        raise ValueError("Invalid FuckingFast file id")
    return candidate

def _base58_decode(value: str) -> bytes:
    n = 0
    for ch in value:
        try:
            digit = BASE58_ALPHABET.index(ch)
        except ValueError as exc:
            raise ValueError("Invalid Base58 decryption key") from exc
        n = n * 58 + digit

    raw = b"" if n == 0 else n.to_bytes((n.bit_length() + 7) // 8, "big")
    leading_zeroes = len(value) - len(value.lstrip("1"))
    return b"\x00" * leading_zeroes + raw


def _http_open(req: urllib.request.Request, opener=None, timeout: float = 25.0):
    if opener is None:
        opener = urllib.request.build_opener()
    return opener.open(req, timeout=timeout)


def fetch_privatebin_json(url: str) -> dict[str, Any]:
    request_url, _fragment = urldefrag(url)
    req = urllib.request.Request(
        request_url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "X-Requested-With": "JSONHttpRequest",
            "Referer": request_url,
        },
    )
    with _http_open(req) as resp:
        body = resp.read(4 * 1024 * 1024)
    try:
        data = json.loads(body.decode("utf-8"))
    except Exception as exc:
        sample = body[:300].decode("utf-8", errors="replace")
        raise RuntimeError("PrivateBin did not return JSON: " + sample) from exc
    if not isinstance(data, dict):
        raise RuntimeError("PrivateBin returned an unexpected response")
    if data.get("status") not in (None, 0):
        raise RuntimeError(str(data.get("message") or "PrivateBin returned an error"))
    return data


def _decode_privatebin_payload(plaintext: bytes, compression: str) -> dict[str, Any]:
    original = plaintext
    try:
        # PrivateBin labels its current compression mode as "zlib", but its
        # browser implementation deliberately creates the zlib context with
        # NO_ZLIB_HEADER = -1. Therefore the wire payload is *raw DEFLATE*
        # (RFC 1951), not a zlib-wrapped stream (RFC 1950).
        #
        # Try raw DEFLATE first for both the current "zlib" label and the
        # older "rawdeflate" label. A standard zlib fallback is kept for
        # compatible forks/older third-party implementations.
        if compression in ("zlib", "rawdeflate"):
            decoded_candidate = None
            last_error = None
            for wbits in (-zlib.MAX_WBITS, zlib.MAX_WBITS):
                try:
                    decoded_candidate = zlib.decompress(plaintext, wbits)
                    last_error = None
                    break
                except Exception as candidate_error:
                    last_error = candidate_error
            if decoded_candidate is None:
                raise last_error or RuntimeError("Could not inflate PrivateBin payload")
            plaintext = decoded_candidate
        elif compression in ("none", "", "null"):
            pass
        else:
            # Be tolerant of PrivateBin-compatible forks using another label.
            decoded_candidate = None
            last_error = None
            for wbits in (-zlib.MAX_WBITS, zlib.MAX_WBITS):
                try:
                    decoded_candidate = zlib.decompress(plaintext, wbits)
                    last_error = None
                    break
                except Exception as candidate_error:
                    last_error = candidate_error
            if decoded_candidate is None:
                raise last_error or RuntimeError("Unsupported PrivateBin compression")
            plaintext = decoded_candidate

        decoded = plaintext.decode("utf-8")
        obj = json.loads(decoded)
        if not isinstance(obj, dict):
            raise ValueError("PrivateBin decrypted JSON is not an object")
        return obj
    except Exception as exc:
        prefix = original[:12].hex()
        raise RuntimeError(
            f"PrivateBin payload could not be decompressed/decoded "
            f"(compression={compression!r}, prefix={prefix})"
        ) from exc


def decrypt_privatebin(url: str, payload: dict[str, Any]) -> str:
    parsed = urlparse(url)
    key_text = parsed.fragment
    if not key_text:
        raise RuntimeError("PrivateBin decryption key is missing from the URL fragment")

    adata = payload.get("adata")
    ciphertext_b64 = payload.get("ct")
    if not isinstance(adata, list) or not adata or not isinstance(adata[0], list):
        raise RuntimeError("PrivateBin adata is missing or invalid")
    if not isinstance(ciphertext_b64, str) or not ciphertext_b64:
        raise RuntimeError("PrivateBin ciphertext is missing")

    # JSON.stringify(adata) in PrivateBin uses compact separators. This exact byte
    # sequence is authenticated by AES-GCM, so spaces must not be introduced.
    adata_bytes = json.dumps(adata, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    spec = list(adata[0])
    if len(spec) < 8:
        raise RuntimeError("Unsupported PrivateBin encryption specification")

    try:
        iv = base64.b64decode(spec[0])
        salt = base64.b64decode(spec[1])
        iterations = int(spec[2])
        key_bits = int(spec[3])
        tag_bits = int(spec[4])
        cipher_name = str(spec[5]).lower()
        mode_name = str(spec[6]).lower()
        compression = str(spec[7]).lower()
    except Exception as exc:
        raise RuntimeError("Invalid PrivateBin encryption specification") from exc

    if cipher_name != "aes" or mode_name != "gcm":
        raise RuntimeError(f"Unsupported PrivateBin cipher: {cipher_name}/{mode_name}")

    decoded_key = _base58_decode(key_text)
    if len(decoded_key) < 32:
        decoded_key = decoded_key.rjust(32, b"\x00")

    import hashlib
    derived = hashlib.pbkdf2_hmac(
        "sha256", decoded_key, salt, iterations, dklen=key_bits // 8
    )

    encrypted = base64.b64decode(ciphertext_b64)
    tag_len = tag_bits // 8
    if len(encrypted) <= tag_len:
        raise RuntimeError("PrivateBin ciphertext is too short")
    ciphertext, tag = encrypted[:-tag_len], encrypted[-tag_len:]

    AES = ensure_crypto_aes()
    cipher = AES.new(derived, AES.MODE_GCM, nonce=iv, mac_len=tag_len)
    cipher.update(adata_bytes)
    try:
        plaintext = cipher.decrypt_and_verify(ciphertext, tag)
    except Exception as exc:
        raise RuntimeError("PrivateBin decryption/authentication failed") from exc

    obj = _decode_privatebin_payload(plaintext, compression)

    paste = obj.get("paste")
    if not isinstance(paste, str):
        raise RuntimeError("PrivateBin decrypted payload does not contain paste text")
    return paste


def scrape_paste_http(url: str) -> list[str]:
    payload = fetch_privatebin_json(url)
    plaintext = decrypt_privatebin(url, payload)
    links = [m.rstrip(".,);]") for m in FF_RE.findall(plaintext)]
    return list(dict.fromkeys(links))


def resolve_direct_http(original_url: str) -> str:
    file_id = extract_file_id(original_url)
    post_url = f"https://fuckingfast.co/f/{file_id}/go"
    cookie_jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookie_jar))

    headers_common = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    }

    try:
        req = urllib.request.Request(
            original_url,
            headers={**headers_common, "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"},
        )
        with _http_open(req, opener=opener, timeout=20) as resp:
            resp.read(64)
    except Exception:
        # The POST sometimes succeeds even if the warm-up GET is blocked.
        pass

    post_headers = {
        **headers_common,
        "Accept": "*/*",
        "Content-Type": "application/x-www-form-urlencoded",
        "HX-Request": "true",
        "HX-Current-URL": original_url,
        "HX-Target": "body",
        "Origin": "https://fuckingfast.co",
        "Referer": original_url,
    }
    req = urllib.request.Request(post_url, data=b"", headers=post_headers, method="POST")
    try:
        with _http_open(req, opener=opener, timeout=25) as resp:
            direct = resp.headers.get("hx-redirect") or resp.headers.get("HX-Redirect")
            if direct:
                return direct.strip()
            status = getattr(resp, "status", None)
            body = resp.read(400).decode("utf-8", errors="replace")
            raise RuntimeError(f"HTTP resolver returned no HX-Redirect (status={status}, body={body[:160]!r})")
    except urllib.error.HTTPError as exc:
        direct = exc.headers.get("hx-redirect") or exc.headers.get("HX-Redirect")
        if direct:
            return direct.strip()
        body = exc.read(400).decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} from FuckingFast (body={body[:160]!r})") from exc


def find_browser_executable() -> str | None:
    candidates: list[Path] = []
    if os.name == "nt":
        for env_name in ("LOCALAPPDATA", "PROGRAMFILES", "PROGRAMFILES(X86)"):
            base = os.environ.get(env_name)
            if not base:
                continue
            root = Path(base)
            candidates.extend([
                root / "Google" / "Chrome" / "Application" / "chrome.exe",
                root / "Microsoft" / "Edge" / "Application" / "msedge.exe",
                root / "BraveSoftware" / "Brave-Browser" / "Application" / "brave.exe",
                root / "Chromium" / "Application" / "chrome.exe",
            ])
    elif sys.platform == "darwin":
        candidates.extend([
            Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
            Path("/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"),
            Path("/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"),
            Path("/Applications/Chromium.app/Contents/MacOS/Chromium"),
        ])
    else:
        for command in (
            "google-chrome-stable", "google-chrome", "chromium", "chromium-browser",
            "microsoft-edge-stable", "microsoft-edge", "brave-browser", "brave",
        ):
            found = shutil.which(command)
            if found:
                return found

    for path in candidates:
        if path.is_file():
            return str(path)
    return None


async def start_browser():
    zd = ensure_zendriver()
    browser_path = find_browser_executable()
    if not browser_path:
        raise RuntimeError("No supported Chromium browser was found (Chrome, Edge, Brave or Chromium)")

    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    config = zd.Config(
        headless=False,
        browser_executable_path=browser_path,
        user_data_dir=str(PROFILE_DIR),
        sandbox=False,
        lang="en-US",
    )
    try:
        return await zd.start(config=config)
    except Exception as exc:
        # Retry with an isolated profile in case a previous FDM process left the
        # persistent profile locked. sandbox=False adds --no-sandbox, which fixes
        # the exact failure emitted by Zendriver in restricted/elevated runtimes.
        isolated = Path(tempfile.mkdtemp(prefix="fitgirl-ddl-ng-profile-"))
        config = zd.Config(
            headless=False,
            browser_executable_path=browser_path,
            user_data_dir=str(isolated),
            sandbox=False,
            lang="en-US",
        )
        try:
            return await zd.start(config=config)
        except Exception as second:
            raise RuntimeError(
                f"Failed to launch/connect to browser at {browser_path}. "
                f"Persistent profile error: {exc}; isolated profile error: {second}"
            ) from second


async def wait_page(tab, timeout: float = 60.0) -> None:
    try:
        await tab.wait_for_ready_state(until="complete", timeout=timeout)
    except TypeError:
        await tab.wait_for_ready_state("complete", timeout=timeout)
    except Exception:
        pass


async def page_text_and_links(tab) -> tuple[str, list[str]]:
    expression = """
    (() => {
      const links = Array.from(document.querySelectorAll('a[href]')).map(a => a.href || '');
      return {text: document.body ? document.body.innerText : '', links};
    })()
    """
    result = await tab.evaluate(expression, await_promise=True, return_by_value=True)
    if not isinstance(result, dict):
        return "", []
    text = str(result.get("text") or "")
    links = [str(x) for x in (result.get("links") or []) if x]
    return text, links


async def scrape_paste_browser(tab, url: str) -> list[str]:
    await tab.get(url)
    await wait_page(tab)

    deadline = time.monotonic() + 45
    seen: list[str] = []
    while time.monotonic() < deadline:
        text, links = await page_text_and_links(tab)
        candidates = [link for link in links if "fuckingfast.co/" in link.lower()]
        candidates.extend(FF_RE.findall(text))
        for link in candidates:
            link = link.rstrip(".,);]")
            if link not in seen:
                seen.append(link)
        if seen:
            return seen
        await asyncio.sleep(1.0)

    raise RuntimeError(
        "No FuckingFast links became visible in the paste page. "
        "If the browser shows a verification page, complete it and try again."
    )


async def scrape_fitgirl_post(tab, url: str) -> list[str]:
    """Adapt the 0.4.12 selectors, keeping PrivateBin fallback for FDM."""
    _validated_host(url, {"fitgirl-repacks.site", "www.fitgirl-repacks.site"})
    await tab.get(url)
    try:
        await tab.wait_for("article.post", timeout=120)
    except TimeoutError:
        await wait_page(tab)

    single_selector = "div.entry-content ul > li:nth-child(2) > a"
    # Upstream 0.4.12 searches spoiler anchors throughout the article, not
    # exclusively inside the second list item.
    spoiler_selector = "div.su-spoiler > div.su-spoiler-content > a"
    mirror_links: list[str] = []
    try:
        anchors = await tab.query_selector_all(single_selector)
        for tag in anchors:
            if "Filehoster: FuckingFast" in str(tag.text_all or ""):
                href = tag.attrs.get("href")
                if href:
                    mirror_links.append(str(href))

        spoilers = await tab.query_selector_all(spoiler_selector)
        spoiler_urls = [
            str(href) for tag in spoilers
            if (href := tag.attrs.get("href")) and is_ff_page(str(href))
        ]
        if spoiler_urls:
            return sorted(set(spoiler_urls), key=lambda u: urlparse(u).fragment)
    except Exception:
        # FitGirl sometimes publishes malformed HTML; inspect page links below.
        pass

    # For single-file posts, the mirror itself is often a FuckingFast URL.
    ff_mirrors = [link for link in mirror_links if is_ff_page(link)]
    if ff_mirrors:
        return list(dict.fromkeys(ff_mirrors))

    page_text, page_links = await page_text_and_links(tab)
    ff_links = [link for link in page_links if is_ff_page(link)]
    ff_links.extend(link for link in FF_RE.findall(page_text) if is_ff_page(link))
    if ff_links:
        return list(dict.fromkeys(ff_links))

    pastes = [
        link for link in mirror_links + page_links
        if (urlparse(link).hostname or "").lower() == "paste.fitgirl-repacks.site"
    ]
    if pastes:
        try:
            return scrape_paste_http(pastes[0])
        except Exception:
            return await scrape_paste_browser(tab, pastes[0])
    raise RuntimeError("Filehoster: FuckingFast links were not found on the FitGirl page")

async def extract_direct_browser(tab, original_url: str) -> str:
    """Resolve a selected file using the upstream 0.4.12 HTMX POST contract."""
    file_id = extract_file_id(original_url)
    go_url = f"https://fuckingfast.co/f/{file_id}/go"
    expression = f"""
    fetch({json.dumps(go_url)}, {{
        method: "POST",
        headers: {{
            "HX-Request": "true",
            "HX-Current-URL": {json.dumps(original_url)},
            "Origin": "https://fuckingfast.co",
            "Content-Type": "application/x-www-form-urlencoded"
        }},
        body: ""
    }}).then(response => ({{
        status: response.status,
        headers: Object.fromEntries(response.headers.entries())
    }})).catch(error => ({{status: 0, headers: {{}}, error: String(error)}}))
    """

    last_error = "no HTTP response"
    for attempt in range(5):
        try:
            result = await tab.evaluate(
                expression, await_promise=True, return_by_value=True
            )
            if isinstance(result, dict):
                status = result.get("status")
                headers = result.get("headers") or {}
                direct = headers.get("hx-redirect") or headers.get("HX-Redirect")
                if isinstance(direct, str) and direct.startswith(("https://", "http://")):
                    return direct
                last_error = f"status={status}, detail={result.get('error', 'no HX-Redirect')}"
            else:
                last_error = "unexpected browser response"
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {exc}"

        if attempt == 0:
            # Browser cookie/session warm-up only if the first request failed.
            try:
                await tab.get(original_url)
                await wait_page(tab, 45)
                await tab.get("https://fuckingfast.co")
                await wait_page(tab, 45)
            except Exception:
                pass
        if attempt < 4:
            await asyncio.sleep(min(2 ** attempt, 16))

    raise RuntimeError(f"FuckingFast /go failed after 5 attempts ({last_error})")

def resolve_many_http(urls: list[str]) -> tuple[list[dict[str, str]], list[tuple[str, str]]]:
    resolved: list[dict[str, str]] = []
    failed: list[tuple[str, str]] = []
    for url in urls:
        try:
            direct = resolve_direct_http(url)
            resolved.append({
                "source_url": url,
                "direct_url": direct,
                "filename": filename_from_url(url),
            })
        except Exception as exc:
            failed.append((url, str(exc)))
    return resolved, failed


async def resolve_failed_with_browser(failed: list[tuple[str, str]]) -> tuple[list[dict[str, str]], list[str]]:
    if not failed:
        return [], []
    browser = await start_browser()
    try:
        tab = await browser.get("https://fuckingfast.co")
        await wait_page(tab)
        resolved: list[dict[str, str]] = []
        warnings: list[str] = []
        for index, (url, http_error) in enumerate(failed, start=1):
            try:
                direct = await extract_direct_browser(tab, url)
                resolved.append({
                    "source_url": url,
                    "direct_url": direct,
                    "filename": filename_from_url(url),
                })
            except Exception as exc:
                warnings.append(
                    f"{index}/{len(failed)} {filename_from_url(url)}: HTTP={http_error}; browser={exc}"
                )
            if index < len(failed):
                await asyncio.sleep(0.30)
        return resolved, warnings
    finally:
        await browser.stop()


async def resolve_one(url: str) -> dict[str, Any]:
    try:
        direct = resolve_direct_http(url)
        item = {"source_url": url, "direct_url": direct, "filename": filename_from_url(url)}
        return {"ok": True, "title": filename_from_url(url), "items": [item], "warnings": []}
    except Exception as http_exc:
        browser_items, warnings = await resolve_failed_with_browser([(url, str(http_exc))])
        if not browser_items:
            raise RuntimeError(warnings[0] if warnings else f"Direct link resolution failed: {http_exc}")
        return {"ok": True, "title": filename_from_url(url), "items": browser_items, "warnings": warnings}


async def resolve_source(url: str) -> dict[str, Any]:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    source_urls: list[str]

    if host == "paste.fitgirl-repacks.site":
        _validated_host(url, {"paste.fitgirl-repacks.site"})
        # Preserve the FDM contract: never resolve signed URLs in playlist stage.
        try:
            source_urls = scrape_paste_http(url)
        except Exception:
            browser = await start_browser()
            try:
                tab = await browser.get("about:blank")
                source_urls = await scrape_paste_browser(tab, url)
            finally:
                await browser.stop()
    elif host in {"fitgirl-repacks.site", "www.fitgirl-repacks.site"}:
        _validated_host(url, {"fitgirl-repacks.site", "www.fitgirl-repacks.site"})
        browser = await start_browser()
        try:
            tab = await browser.get("about:blank")
            source_urls = await scrape_fitgirl_post(tab, url)
        finally:
            await browser.stop()
    elif host in {"fuckingfast.co", "www.fuckingfast.co"}:
        if not is_ff_page(url):
            raise ValueError("Invalid FuckingFast page URL")
        source_urls = [url]
    else:
        raise ValueError("Unsupported source URL")

    source_urls = list(dict.fromkeys(u for u in source_urls if is_ff_page(u)))
    if not source_urls:
        raise RuntimeError("No FuckingFast page URLs were found")

    return {
        "ok": True,
        "title": title_from_items(source_urls),
        "items": [
            {"source_url": u, "filename": filename_from_url(u)}
            for u in source_urls
        ],
        "warnings": [],
    }

def main() -> None:
    if sys.version_info < (3, 11):
        emit({"ok": False, "error": "Python 3.11 or newer is required (fitgirl-ddl-ng 0.4.12)"}, 1)

    if len(sys.argv) < 3:
        emit({"ok": False, "error": "Usage: fdm_bridge.py resolve-one|resolve-source URL"}, 1)

    command = sys.argv[1]
    url = sys.argv[2].strip()
    if not url.startswith("https://"):
        emit({"ok": False, "error": "Only HTTPS URLs are supported"}, 1)

    try:
        if command == "resolve-one":
            result = asyncio.run(resolve_one(url))
        elif command == "resolve-source":
            result = asyncio.run(resolve_source(url))
        else:
            emit({"ok": False, "error": "Unknown command: " + command}, 1)
            return
        emit(result, 0)
    except SystemExit:
        raise
    except Exception as exc:
        emit({"ok": False, "error": str(exc)}, 1)


if __name__ == "__main__":
    main()
