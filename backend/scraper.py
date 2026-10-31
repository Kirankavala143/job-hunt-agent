import logging
import sys
import os

# Force UTF-8 across all I/O to prevent Windows charmap crashes from unicode in crawled content
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

from typing import List, Dict, Any
import pandas as pd
import requests
import feedparser
import urllib.parse
import json
import concurrent.futures

def _safe(s: str) -> str:
    """Encode string to ASCII safely to prevent Windows charmap errors in logs."""
    return s.encode('ascii', errors='replace').decode('ascii') if s else ""

logger = logging.getLogger(__name__)

# â”€â”€â”€ TARGET JOB BOARDS (for SearxNG site: queries) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
JOB_BOARDS = [
    "naukri.com",
    "internshala.com",
    "linkedin.com",
    "glassdoor.co.in",
    "glassdoor.com",
    "wellfound.com",
    "workatastartup.com",
    "indeed.com",
    "instahyre.com",
    "foundit.in",
    "monster.com",
    "unstop.com",
]

class BaseJobScraper:
    def search(self, keywords: str, location: str, **kwargs) -> List[Dict[str, Any]]:
        raise NotImplementedError

# â”€â”€â”€ JobSpy Scraper â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
class JobSpyScraper(BaseJobScraper):
    def __init__(self, site_name: str, country: str = "india"):
        self.site_name = site_name
        self.country = country

    def search(self, keywords: str, location: str, **kwargs) -> List[Dict[str, Any]]:
        logger.info(f"JobSpy [{self.site_name}]: '{keywords}' in '{location}'")
        from jobspy import scrape_jobs
        jobs = []
        try:
            df = scrape_jobs(
                site_name=[self.site_name],
                search_term=keywords,
                location=location,
                results_wanted=30,
                country_indeed=self.country,
                is_remote="remote" in location.lower(),
            )
            if df is not None and not df.empty:
                df = df.fillna("")
                for _, row in df.iterrows():
                    desc = str(row.get("description", "") or "")
                    jobs.append({
                        "title": str(row.get("title", "") or ""),
                        "company": str(row.get("company", "") or ""),
                        "location": str(row.get("location", location) or ""),
                        "url": str(row.get("job_url", "") or ""),
                        "description": desc.strip() if desc else "No description available.",
                        "source": f"JobSpy/{self.site_name.capitalize()}"
                    })
        except Exception as e:
            logger.error(f"JobSpy [{self.site_name}] failed: {e}")
        logger.info(f"JobSpy [{self.site_name}]: {len(jobs)} results")
        return jobs

# â”€â”€â”€ LinkedIn Playwright Scraper â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


class LinkedInPlaywrightScraper(BaseJobScraper):
    def search(self, keywords: str, location: str, **kwargs) -> List[Dict[str, Any]]:
        from playwright.sync_api import sync_playwright
        import re

        logger.info(
            "Playwright [LinkedIn]: '%s' in '%s'",
            keywords, location
        )

        jobs = []
        max_description_fetches = 10

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)

                try:
                    page = browser.new_page()
                    page.set_default_timeout(3000)
                    page.set_default_navigation_timeout(20000)

                    params = {
                        "keywords": keywords,
                        "location": location,
                        "f_TPR": "r604800"
                    }

                    search_url = (
                        "https://www.linkedin.com/jobs/search?"
                        + urllib.parse.urlencode(params)
                    )

                    page.goto(
                        search_url,
                        wait_until="domcontentloaded",
                        timeout=30000
                    )

                    cards = page.locator(".base-card")
                    card_count = min(cards.count(), 50)

                    logger.info(
                        "LinkedIn search cards found: %s",
                        card_count
                    )

                    # Step 1: Collect job-card information.
                    for i in range(card_count):
                        try:
                            card = cards.nth(i)

                            title_el = card.locator(
                                "h3.base-search-card__title"
                            )
                            company_el = card.locator(
                                "h4.base-search-card__subtitle"
                            )

                            if not title_el.count() or not company_el.count():
                                continue

                            link_el = card.locator(
                                "a.base-card__full-link"
                            )

                            raw_url = link_el.get_attribute(
                                "href",
                                timeout=2000
                            ) if link_el.count() else ""

                            if not raw_url:
                                continue

                            location_el = card.locator(
                                "span.job-search-card__location"
                            )

                            clean_url = re.sub(
                                r"https://[a-z]{2}\.linkedin\.com",
                                "https://www.linkedin.com",
                                raw_url
                            )

                            jobs.append({
                                "title": title_el.inner_text().strip(),
                                "company": company_el.inner_text().strip(),
                                "location": (
                                    location_el.inner_text().strip()
                                    if location_el.count()
                                    else location
                                ),
                                "url": clean_url,
                                "description": "",
                                "source": "Playwright/LinkedIn"
                            })

                        except Exception as e:
                            logger.warning(
                                "Skipping LinkedIn card %s: %s",
                                i, e
                            )

                    # Step 2: Fetch public descriptions for a limited
                    # number of jobs.
                    for job in jobs[:max_description_fetches]:
                        detail_page = None

                        try:
                            detail_page = browser.new_page()

                            detail_page.goto(
                                job["url"],
                                wait_until="domcontentloaded",
                                timeout=20000
                            )

                            description_el = detail_page.locator(
                                ".description__text"
                            )

                            if description_el.count():
                                job["description"] = (
                                    description_el.first.inner_text(
                                        timeout=5000
                                    ).strip()
                                )

                        except Exception as e:
                            logger.warning(
                                "Description unavailable for %s: %s",
                                job["title"], e
                            )

                        finally:
                            if detail_page:
                                try:
                                    detail_page.close()
                                except Exception:
                                    pass

                        if not job["description"]:
                            job["description"] = (
                                "No public description available."
                            )

                    # Remaining results are retained without fetching
                    # their individual descriptions.
                    for job in jobs[max_description_fetches:]:
                        job["description"] = (
                            "Description not fetched due to request limit."
                        )

                finally:
                    browser.close()

        except Exception as e:
            logger.error(
                "LinkedIn scraper failed: %s",
                e,
                exc_info=True
            )

        logger.info(
            "Playwright [LinkedIn]: %s results",
            len(jobs)
        )

        return jobs

# â”€â”€â”€ HackerNews Scraper â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
class HackerNewsScraper(BaseJobScraper):
    def search(self, keywords: str, location: str, **kwargs) -> List[Dict[str, Any]]:
        logger.info(f"HackerNews: '{keywords}'")
        jobs = []
        try:
            url = f"https://hn.algolia.com/api/v1/search?query={urllib.parse.quote(keywords)}&tags=story"
            res = requests.get(url, timeout=10)
            if res.status_code == 200:
                for hit in res.json().get('hits', [])[:20]:
                    jobs.append({
                        "title": str(hit.get("title", "") or ""),
                        "company": "HackerNews Startup",
                        "location": "Remote",
                        "url": hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID')}",
                        "description": "HackerNews Job Posting",
                        "source": "HackerNews"
                    })
        except Exception as e:
            logger.error(f"HackerNews failed: {e}")
        return jobs

# â”€â”€â”€ RSS Scraper â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
class RSSJobScraper(BaseJobScraper):
    def search(self, keywords: str, location: str, **kwargs) -> List[Dict[str, Any]]:
        jobs = []
        feeds = [
            "https://weworkremotely.com/categories/remote-programming-jobs.rss",
            "https://remoteok.com/jobs.rss"
        ]
        kw_words = keywords.lower().split()
        for feed_url in feeds:
            try:
                feed = feedparser.parse(feed_url)
                for entry in feed.entries[:30]:
                    if not kw_words or any(w in entry.title.lower() for w in kw_words):
                        jobs.append({
                            "title": str(entry.title or ""),
                            "company": "RemoteOK/WWR",
                            "location": "Remote",
                            "url": str(entry.link or ""),
                            "description": str(getattr(entry, 'description', ""))[:300],
                            "source": "RSS Feed"
                        })
            except Exception as e:
                logger.error(f"RSS failed: {e}")
        return jobs

# â”€â”€â”€ YCombinator Scraper â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
class YCScraper(BaseJobScraper):
    def search(self, keywords: str, location: str, **kwargs) -> List[Dict[str, Any]]:
        logger.info(f"YC API: '{keywords}'")
        jobs = []
        try:
            import requests
            import json
            from bs4 import BeautifulSoup
            from concurrent.futures import ThreadPoolExecutor, as_completed

            # 1. Fetch meta.json to find recent batches
            res = requests.get("https://raw.githubusercontent.com/yc-oss/api/main/meta.json", timeout=10)
            if res.status_code != 200:
                logger.error("Failed to fetch YC meta.json")
                return jobs

            meta = res.json()
            # Sort batches by roughly recency (e.g. S24, W24, S23) or just grab all.
            # Given that YC API is just static files, fetching 20 batches is incredibly fast.
            # We'll grab the 20 most recently added (or largest ones). Let's just grab the 20 biggest for safety,
            # or all batches if there aren't many. Actually, 50 batches is just 50 concurrent GETs.
            batch_urls = [b.get("api") for b in meta.get("batches", {}).values() if b.get("api")]

            hiring_companies = []

            def fetch_batch(url):
                try:
                    r = requests.get(url, timeout=10)
                    if r.status_code == 200:
                        return r.json()
                except:
                    pass
                return []

            # 2. Concurrently fetch batches to find hiring companies
            # Use top 30 batches to save time (mostly recent/active companies)
            top_urls = list(reversed(list(meta.get("batches", {}).values())))[:30]
            top_batch_urls = [b.get("api") for b in top_urls if b.get("api")]

            all_companies = []
            with ThreadPoolExecutor(max_workers=10) as executor:
                futures = {executor.submit(fetch_batch, url): url for url in top_batch_urls}
                for future in as_completed(futures):
                    all_companies.extend(future.result())

            kw_lower = keywords.lower()

            # 3. Filter for hiring companies matching keyword
            # Extract significant words from the keyword to avoid overly strict substring matches
            kw_words = [w for w in kw_lower.split() if len(w) > 2 and w not in ('intern', 'developer', 'engineer', 'specialist', 'manager', 'lead', 'senior', 'junior', 'remote')]

            for c in all_companies:
                if not c.get("isHiring"):
                    continue

                text = f" {c.get('name', '')} {c.get('one_liner', '')} {c.get('long_description', '')} {' '.join(c.get('tags', []))} ".lower()

                matched = False
                if not kw_words and 'intern' not in kw_lower:
                    # No significant keywords, just take all and we'll cap later
                    matched = True
                else:
                    for w in kw_words:
                        if w in text:
                            matched = True
                            break
                    # Special short acronyms
                    for acr in [' ai ', ' ml ', ' llm ', ' rag ']:
                        if acr in f" {kw_lower} " and acr in text:
                            matched = True
                            break
                    # If keyword was just "intern", just match companies with "intern" in their text or just take them
                    if 'intern' in kw_lower and ' intern' in text:
                        matched = True

                if matched:
                    hiring_companies.append(c)

            logger.info(f"YC API found {len(hiring_companies)} hiring companies matching '{keywords}'")

            # 4. Fetch the jobs pages for matching companies
            def fetch_company_jobs(company):
                company_jobs = []
                slug = company.get('slug')
                if not slug: return company_jobs

                try:
                    jobs_url = f"https://www.ycombinator.com/companies/{slug}/jobs"
                    r = requests.get(jobs_url, timeout=10)
                    if r.status_code == 200:
                        soup = BeautifulSoup(r.text, 'html.parser')
                        data_div = soup.find('div', {'data-page': True})
                        if data_div:
                            data = json.loads(data_div['data-page'])
                            postings = data.get('props', {}).get('jobPostings', [])
                            for p in postings:
                                # Extra filter: does the specific job match the location and keyword?
                                job_title = p.get('title', '').lower()
                                job_desc = p.get('description', '').lower() if p.get('description') else ''
                                job_loc = p.get('location', '').lower()

                                if location:
                                    loc_lower = location.lower()
                                    # If the job is explicitly remote, it might be global, so we keep it.
                                    # Otherwise, it MUST contain the requested location.
                                    if loc_lower not in job_loc and "remote" not in job_loc:
                                        continue

                                # We already matched the company, but let's include all jobs the company has,
                                # since ATS Scorer will filter the irrelevant ones anyway.
                                company_jobs.append({
                                    "title": p.get("title", ""),
                                    "company": company.get("name", "YC Startup"),
                                    "location": p.get("location", "Remote"),
                                    "url": p.get("applyUrl") or jobs_url,
                                    "description": job_desc[:1000],
                                    "source": "YCombinator"
                                })
                except Exception as e:
                    logger.debug(f"Failed to fetch YC jobs for {slug}: {e}")
                return company_jobs

            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = {executor.submit(fetch_company_jobs, c): c for c in hiring_companies[:30]} # Cap at 30 to avoid rate limits
                for future in as_completed(futures):
                    jobs.extend(future.result())
        except Exception as e:
            logger.error(f"YC failed: {e}")
        return jobs

# â”€â”€â”€ SearxNG + Crawl4AI Scraper â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
class SearxNGCrawl4aiScraper(BaseJobScraper):
    """
    Phase 1: SearxNG fires targeted queries against major job boards.
    Phase 2: Crawl4AI visits the actual job board pages and extracts listings.
    Phase 3: LLM parses the raw markdown into structured job dicts.
    """

    def _searxng_query(self, query: str) -> List[str]:
        """Returns a list of unique URLs from SearxNG for a given query."""
        try:
            params = {"q": query, "format": "json"}
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
            res = requests.get("http://localhost:8080/search", params=params, headers=headers, timeout=10)
            if res.status_code == 200:
                return [r.get("url", "") for r in res.json().get("results", []) if r.get("url")]
        except Exception as e:
            logger.error(f"SearxNG query failed: {e}")
        return []

    # Login wall phrases â€” if page starts with these, skip to middle content
    LOGIN_SIGNALS = ["login with google", "forgot password", "sign in to", "create account", "register now", "login to continue"]


    def _crawl_and_extract(self, urls: List[str], keyword: str, location: str) -> List[Dict]:
        """Crawl job pages and extract listings using Python, without an LLM."""

        from crawl4ai import AsyncWebCrawler
        from bs4 import BeautifulSoup
        import asyncio
        import nest_asyncio
        import re

        nest_asyncio.apply()

        async def crawl_all(url_list):
            results = []

            async with AsyncWebCrawler(verbose=False) as crawler:
                for url in url_list:
                    try:
                        result = await crawler.arun(
                            url=url,
                            timeout=20
                        )

                        if result and result.html:
                            results.append((url, result.html))

                            logger.info(
                                "Crawl4AI OK: %s",
                                _safe(url)
                            )

                    except Exception as e:
                        logger.error(
                            "Crawl4AI failed for %s: %s",
                            _safe(url),
                            _safe(str(e))
                        )

            return results

        try:
            crawled = asyncio.run(crawl_all(urls))
        except Exception as e:
            logger.error("Crawl execution failed: %s", e)
            return []

        extracted_jobs = []
        seen_jobs = set()

        for url, html in crawled:
            try:
                soup = BeautifulSoup(html, "html.parser")

                # Remove irrelevant page elements.
                for element in soup([
                    "script", "style", "nav",
                    "footer", "header", "noscript"
                ]):
                    element.decompose()

                # Look for structured job posting data.
                structured_data = soup.find_all(
                    "script",
                    type="application/ld+json"
                )

                for script in structured_data:
                    try:
                        data = json.loads(script.string or script.get_text())

                        entries = data if isinstance(data, list) else [data]

                        for entry in entries:
                            if entry.get("@type") == "JobPosting":
                                organization = entry.get(
                                    "hiringOrganization", {}
                                )

                                title = entry.get("title", "").strip()
                                company = organization.get(
                                    "name", "Unknown"
                                )

                                if not title:
                                    continue

                                key = f"{title.lower()}|{company.lower()}"

                                if key in seen_jobs:
                                    continue

                                seen_jobs.add(key)

                                extracted_jobs.append({
                                    "title": title,
                                    "company": company,
                                    "location": location,
                                    "url": entry.get("url") or url,
                                    "description": BeautifulSoup(
                                        entry.get("description", ""),
                                        "html.parser"
                                    ).get_text(" ", strip=True)[:1000],
                                    "source": "Structured Job Posting"
                                })

                    except (json.JSONDecodeError, AttributeError, TypeError):
                        continue

                # Fallback: extract likely job cards from page HTML.
                job_cards = soup.select(
                    "[class*='job-card'], "
                    "[class*='job-listing'], "
                    "[class*='job-item'], "
                    "[class*='job-tile']"
                )

                for card in job_cards:
                    heading = card.find(
                        ["h1", "h2", "h3", "h4"]
                    )

                    if not heading:
                        continue

                    title = heading.get_text(" ", strip=True)

                    link = card.find("a", href=True)

                    if link:
                        job_url = urllib.parse.urljoin(
                            url, link["href"]
                        )
                    else:
                        job_url = url

                    if len(title) < 4 or len(title) > 150:
                        continue

                    # Avoid extracting unrelated navigation headings.
                    if not re.search(
                        r"developer|engineer|analyst|intern|"
                        r"manager|designer|scientist|specialist|"
                        r"consultant|architect",
                        title,
                        re.IGNORECASE
                    ):
                        continue

                    company = "Unknown"

                    company_element = card.select_one(
                        "[class*='company'], "
                        "[class*='employer']"
                    )

                    if company_element:
                        company = company_element.get_text(
                            " ", strip=True
                        )

                    key = f"{title.lower()}|{company.lower()}"

                    if key in seen_jobs:
                        continue

                    seen_jobs.add(key)

                    extracted_jobs.append({
                        "title": title,
                        "company": company,
                        "location": location,
                        "url": job_url,
                        "description": card.get_text(
                            " ", strip=True
                        )[:1000],
                        "source": "Crawl4AI"
                    })

            except Exception as e:
                logger.error(
                    "Python extraction failed for %s: %s",
                    _safe(url),
                    _safe(str(e))
                )

        logger.info(
            "Python extraction completed: %s jobs",
            len(extracted_jobs)
        )

        return extracted_jobs


    def search(self, keywords: str, location: str, **kwargs) -> List[Dict[str, Any]]:
        logger.info(f"SearxNG+Crawl4AI: '{keywords}' in '{location}'")
        all_urls = []
        seen_urls = set()
        snippet_jobs = []  # Fallback: SearxNG result snippets

        loc_str = f" {location}" if location else ""
        targeted_queries = [
            f'"{keywords}" jobs{loc_str} site:internshala.com',
            f'"{keywords}" jobs{loc_str} site:naukri.com',
            f'"{keywords}" jobs{loc_str} site:linkedin.com',
            f'"{keywords}" jobs{loc_str} site:glassdoor.co.in',
            f'"{keywords}" jobs{loc_str} site:wellfound.com',
            f'"{keywords}" jobs{loc_str} site:instahyre.com OR site:foundit.in OR site:unstop.com',
            f'"{keywords}" jobs{loc_str}',
        ]

        for query in targeted_queries:
            try:
                params = {"q": query, "format": "json"}
                headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
                res = requests.get("http://localhost:8080/search", params=params, headers=headers, timeout=10)
                if res.status_code == 200:
                    for r in res.json().get("results", [])[:4]:
                        url = r.get("url", "")
                        if url and url not in seen_urls:
                            seen_urls.add(url)
                            all_urls.append(url)
                        # Save snippet as fallback
                        if r.get("title") and r.get("url"):
                            snippet_jobs.append({
                                "title": r.get("title", ""),
                                "company": "Web Result",
                                "location": location,
                                "url": r.get("url", ""),
                                "description": r.get("content", "")[:300],
                                "source": "SearxNG"
                            })
            except Exception as e:
                logger.error(f"SearxNG query failed: {_safe(str(e))}")

        logger.info(f"SearxNG: {len(all_urls)} URLs, {len(snippet_jobs)} snippets")

        if not all_urls:
            return snippet_jobs

        extracted = self._crawl_and_extract(all_urls[:12], keywords, location)
        logger.info(f"SearxNG+Crawl4AI: {len(extracted)} extracted, {len(snippet_jobs)} snippets")
        # Return extracted if we got something, otherwise fall back to raw snippets
        return extracted if extracted else snippet_jobs

# â”€â”€â”€ Job Aggregator (for MCP server / legacy) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
class JobAggregator:
    def search_all(self, keywords: str, location: str) -> List[Dict[str, Any]]:
        loc_lower = location.lower()
        country = "usa"
        if any(w in loc_lower for w in ["india", "bangalore", "mumbai", "delhi", "hyderabad", "pune", "chennai"]):
            country = "india"
        elif any(w in loc_lower for w in ["uk", "london", "united kingdom"]):
            country = "uk"
        elif any(w in loc_lower for w in ["canada", "toronto", "vancouver"]):
            country = "canada"

        scrapers = [
            LinkedInPlaywrightScraper(),
            JobSpyScraper(site_name="indeed", country=country),
            JobSpyScraper(site_name="linkedin", country=country),
            HackerNewsScraper(),
            RSSJobScraper(),
            YCScraper(),
            SearxNGCrawl4aiScraper()
        ]
        from concurrent.futures import ThreadPoolExecutor, as_completed

        all_jobs = []
        with ThreadPoolExecutor(max_workers=len(scrapers)) as executor:
            future_to_scraper = {executor.submit(scraper.search, keywords, location): scraper for scraper in scrapers}
            for future in as_completed(future_to_scraper):
                scraper = future_to_scraper[future]
                try:
                    all_jobs.extend(future.result())
                except Exception as e:
                    logger.error(f"{scraper.__class__.__name__} failed: {e}")

        seen, deduped = set(), []
        for job in all_jobs:
            key = f"{str(job.get('title','')).lower()}|{str(job.get('company','')).lower()}"
            if key not in seen and key != "|":
                seen.add(key)
                deduped.append(job)
        logger.info(f"Aggregator: {len(deduped)} unique jobs total")
        return deduped
