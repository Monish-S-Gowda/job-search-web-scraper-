import logging
import re
import time

import requests
from bs4 import BeautifulSoup
import urllib3

# Playwright is needed for JavaScript-rendered pages
# Import it but handle errors gracefully
try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    logging.warning("Playwright not available - JavaScript-rendered pages won't work")

# Suppress insecure request warnings for local testing
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(message)s")


def _make_search_url(role, location, page=1):
    keywords = role.replace(" ", "+")
    location_query = location.replace(" ", "+")
    return (
        f"https://www.timesjobs.com/job-search?keywords={keywords}"
        f"&location={location_query}&experience=&refreshed=true&pg={page}"
    )


def _normalize_link(href):
    if not href:
        return "N/A"
    href = href.strip()
    if href.startswith("/"):
        href = "https://www.timesjobs.com" + href
    return href


def scrape_timesjobs(role, location, limit=999999):
    """Server-side parse (requests + BeautifulSoup) for the first result page.

    Returns list of jobs: [job_title, company, skills, location, salary, link, posted]
    """
    url = _make_search_url(role, location, page=1)
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        )
    }

    try:
        resp = requests.get(url, headers=headers, timeout=15, verify=False)
        resp.raise_for_status()
    except Exception as exc:
        logging.exception("Failed to fetch server-side results")
        return f"Error fetching data: {exc}"

    soup = BeautifulSoup(resp.content, "html.parser")
    
    # Try multiple selectors to find job cards
    job_cards = soup.find_all("li", class_="clearfix job-bx wht-shd-bx")
    
    # If first selector doesn't work, try alternatives
    if not job_cards:
        logging.info("Primary selector found no cards, trying alternatives...")
        # Try alternative selectors
        job_cards = soup.find_all("li", class_=lambda v: v and "job-bx" in " ".join(v) if v else False)
    
    if not job_cards:
        # Try div-based cards (newer structure)
        job_cards = soup.find_all("div", class_=lambda v: v and "srp-card" in " ".join(v) if v else False)
    
    if not job_cards:
        # Try any element with job-related classes
        job_cards = soup.find_all(["li", "div"], class_=lambda v: v and any(
            keyword in " ".join(v).lower() if v else False 
            for keyword in ["job", "card", "listing", "result"]
        ))
    
    logging.info(f"Found {len(job_cards)} job cards using selectors")
    
    if not job_cards:
        logging.warning("No job cards found. Website structure may have changed.")
        # Log a sample of the HTML for debugging
        logging.debug(f"Page title: {soup.title.string if soup.title else 'No title'}")
        # Try to find any list items or divs that might be job cards
        all_lis = soup.find_all("li")
        all_divs = soup.find_all("div", limit=20)
        logging.debug(f"Found {len(all_lis)} <li> elements and {len(all_divs)} <div> elements on page")
    
    results = []
    seen = set()

    for job in job_cards[:limit]:
        # Try multiple ways to find job title
        title = job.find("h2") or job.find("h3") or job.find("h1") or job.find("a", class_=lambda v: v and "title" in " ".join(v).lower() if v else False)
        job_name = title.text.strip() if title and title.text else "N/A"

        # Try multiple ways to find company name
        comp = (job.find("h3", class_="joblist-comp-name") or 
                job.find("h3", class_=lambda v: v and "company" in " ".join(v).lower() if v else False) or
                job.find("span", class_=lambda v: v and "company" in " ".join(v).lower() if v else False) or
                job.find("div", class_=lambda v: v and "company" in " ".join(v).lower() if v else False))
        company_name = comp.text.strip().split("\r")[0].strip() if comp and comp.text else "N/A"

        # Try multiple ways to find skills
        skills_tag = (job.find("span", class_="srp-skills") or 
                      job.find("span", class_=lambda v: v and "skill" in " ".join(v).lower() if v else False) or
                      job.find("div", class_=lambda v: v and "skill" in " ".join(v).lower() if v else False))
        if skills_tag and skills_tag.text:
            skills = [s.strip() for s in skills_tag.text.split(",") if s.strip()]
        else:
            skills = []

        # Try multiple ways to find location
        place_tag = (job.find("span", title=True) or 
                    job.find("span", class_=lambda v: v and "location" in " ".join(v).lower() if v else False) or
                    job.find("div", class_=lambda v: v and "location" in " ".join(v).lower() if v else False))
        if place_tag:
            place = place_tag.get("title", "") or (place_tag.text.strip() if place_tag.text else "")
            place = place if place else location
        else:
            place = location

        salary = "Not Disclosed"
        detail_list = job.find("ul", class_="top-jd-dtl clearfix")
        if detail_list:
            for li in detail_list.find_all("li"):
                if "Rs" in li.text or "Salary" in li.text:
                    salary = (
                        li.text.replace("material-icons", "")
                        .replace("attach_money", "")
                        .strip()
                    )

        posted_text_node = job.find(string=re.compile(r"posted", re.I))
        if posted_text_node:
            parent_text = posted_text_node.parent.get_text(separator=" ", strip=True)
            hosted_date = re.sub(r"(?i).*posted(?: on)?:?\s*", "", parent_text).strip()
        else:
            fallback = job.find(
                string=re.compile(r"(\b\d+\s+day|day|hour|posted)", re.I)
            )
            hosted_date = fallback.strip() if fallback else "Not Disclosed"

        a = job.find("a", href=True)
        link = _normalize_link(a["href"]) if a else "N/A"

        key = link if link != "N/A" else f"{job_name}|{company_name}|{place}"
        if key in seen:
            continue
        seen.add(key)

        results.append(
            [job_name, company_name, skills, place, salary, link, hosted_date]
        )

    return results


def scrape_first_page_playwright(role, location):
    """Use Playwright to render and parse only the first results page."""
    if not PLAYWRIGHT_AVAILABLE:
        raise Exception("Playwright not available")

    url = _make_search_url(role, location, page=1)
    logging.info(f"Rendering first page: {url}")
    results = []
    seen = set()
    browser = None

    try:
        with sync_playwright() as p:  # noqa: F821
            try:
                browser = p.chromium.launch(headless=True)
            except Exception as e:
                logging.error(f"Failed to launch browser: {e}")
                raise
            
            try:
                page = browser.new_page(
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
                    )
                )
            except Exception as e:
                logging.error(f"Failed to create page: {e}")
                browser.close()
                raise
            
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
            except Exception as e:
                logging.warning(f"Page goto failed: {e}, continuing anyway")
                # Don't raise, try to get content anyway

            # Wait for JavaScript to render content
            logging.info("Waiting for page content to load...")
            time.sleep(5)
            
            # Try to wait for job cards to appear
            try:
                page.wait_for_selector("div, article, section, li", timeout=10000)
            except:
                pass  # Continue even if selector wait times out
            
            # Additional wait for dynamic content
            time.sleep(3)
            
            try:
                rendered = page.content()
            except Exception as e:
                logging.error(f"Failed to get page content: {e}")
                rendered = ""
            
            # Always try to close browser, even if there were errors
            try:
                browser.close()
            except:
                pass  # Ignore errors when closing
            browser = None

        soup = BeautifulSoup(rendered, "html.parser")
        
        # Find job cards using the correct selector: div with srp-card class
        job_cards = soup.find_all("div", class_=lambda v: v and 'srp-card' in ' '.join(v) if v else False)
        
        if not job_cards:
            # Fallback: try finding divs with the specific classes
            job_cards = soup.find_all("div", class_="srp-card")
        
        logging.info(f"Found {len(job_cards)} job cards using srp-card selector")
        

        for job in job_cards:
            # Extract job title - h2 tag in srp-card
            title_tag = job.find("h2")
            job_name = title_tag.text.strip() if title_tag and title_tag.text else "N/A"
            
            # Skip if no valid title
            if not job_name or job_name == "N/A" or len(job_name) < 3:
                continue

            # Extract company name - first span in the text-xs div
            company_name = "N/A"
            # Find the div with text-xs that contains company info
            company_div = job.find("div", class_=lambda v: v and "text-xs" in " ".join(v) if v else False)
            if company_div:
                # Get all spans, filter out separator spans
                all_spans = company_div.find_all("span")
                for span in all_spans:
                    span_classes = " ".join(span.get("class", []))
                    # Skip separator spans (have mr-1 ml-1 classes)
                    if "mr-1" not in span_classes and "ml-1" not in span_classes:
                        company_text = span.text.strip()
                        if company_text and len(company_text) > 1:
                            # Extract company name (before "|" if present)
                            if "|" in company_text:
                                company_name = company_text.split("|")[0].strip()
                            else:
                                company_name = company_text.strip()
                            # Clean up
                            company_name = re.sub(r'\s+', ' ', company_name).strip()[:100]
                            break

            # Extract skills - span.skill-tag elements with title attribute
            skills = []
            skill_tags = job.find_all("span", class_=lambda v: v and "skill-tag" in " ".join(v) if v else False)
            for skill_tag in skill_tags:
                # Prefer title attribute, fallback to text
                skill_text = skill_tag.get("title", "").strip() or skill_tag.text.strip()
                if skill_text and not skill_text.startswith("+") and "more" not in skill_text.lower():
                    # Some tags have multiple skills separated by "  " (double space)
                    if "  " in skill_text:
                        skill_list = [s.strip() for s in skill_text.split("  ") if s.strip() and len(s.strip()) > 1]
                        skills.extend(skill_list)
                    else:
                        if len(skill_text) > 1:  # Ignore single character "skills"
                            skills.append(skill_text.strip())
            
            # Extract location - span with locations-icon
            place = location  # Default
            location_span = job.find("span", class_=lambda v: v and "locations-icon" in " ".join(v) if v else False)
            if location_span:
                place_text = location_span.text.strip()
                if place_text:
                    place = place_text.strip()

            # Extract salary - look for span with salary-icon or text containing salary info
            salary = "Not Disclosed"
            salary_span = job.find("span", class_=lambda v: v and "salary-icon" in " ".join(v) if v else False)
            if salary_span:
                # Get the next sibling span or parent text
                salary_text = ""
                if salary_span.find_next_sibling("span"):
                    salary_text = salary_span.find_next_sibling("span").text.strip()
                else:
                    # Look in parent container
                    parent = salary_span.find_parent()
                    if parent:
                        salary_text = parent.get_text()
                        # Extract salary part
                        salary_match = re.search(r'(?:salary|rs\.?|lakh|crore)[:\s]*([^\n]+)', salary_text, re.I)
                        if salary_match:
                            salary_text = salary_match.group(1).strip()
                
                if salary_text and salary_text.lower() != "not disclosed":
                    salary = salary_text.strip()
            
            # Extract posted date - look for "Posted on:" text
            hosted_date = "Not Disclosed"
            posted_text = job.find(string=re.compile(r"Posted on:", re.I))
            if posted_text:
                # Get the date after "Posted on:"
                parent = posted_text.parent if posted_text.parent else None
                if parent:
                    full_text = parent.get_text()
                    date_match = re.search(r'Posted on:\s*([^\n|]+)', full_text, re.I)
                    if date_match:
                        hosted_date = date_match.group(1).strip()
            
            # Extract job link - a tag with job-detail in href
            link = "N/A"
            job_link = job.find("a", href=lambda v: v and "job-detail" in v.lower() if v else False)
            if job_link:
                link = _normalize_link(job_link.get("href", ""))

            key = link if link != "N/A" else f"{job_name}|{company_name}|{place}"
            if key in seen:
                continue
            seen.add(key)

            results.append(
                [job_name, company_name, skills, place, salary, link, hosted_date]
            )

        return results
    except Exception as e:
        error_msg = str(e)
        # Handle EPIPE and other Playwright connection errors gracefully
        if "EPIPE" in error_msg or "broken pipe" in error_msg.lower():
            logging.warning("Playwright connection error (EPIPE), this is usually harmless")
            return []  # Return empty list instead of raising
        else:
            logging.exception(f"Playwright scraping failed: {e}")
            if browser:
                try:
                    browser.close()
                except:
                    pass
            raise


def get_jobs_for_web(keyword, location, limit=50):
    """Scrape jobs for web display.
    
    Args:
        keyword: Job keyword/title to search for
        location: Location to search in
        limit: Maximum number of jobs to return (default: 50)
    
    Returns:
        List of job cards, where each card is a list:
        [job_title, company, skills, location, salary, link, posted]
    """
    if not keyword or not location:
        return []
    
    # Try Playwright first (needed for JavaScript-rendered pages)
    if PLAYWRIGHT_AVAILABLE:
        try:
            logging.info(f"Using Playwright to scrape jobs for '{keyword}' in '{location}'")
            jobs = scrape_first_page_playwright(keyword, location)
            if isinstance(jobs, list) and len(jobs) > 0:
                logging.info(f"Playwright found {len(jobs)} jobs")
                return jobs[:limit]
            else:
                logging.warning("Playwright returned no results, trying server-side scraping")
        except Exception as e:
            error_str = str(e)
            # Handle EPIPE and connection errors gracefully
            if "EPIPE" in error_str or "broken pipe" in error_str.lower() or "Target page" in error_str:
                logging.warning(f"Playwright connection issue (usually harmless): {e}")
                # Try once more with a small delay
                try:
                    time.sleep(1)
                    jobs = scrape_first_page_playwright(keyword, location)
                    if isinstance(jobs, list) and len(jobs) > 0:
                        return jobs[:limit]
                except:
                    pass
            else:
                logging.warning(f"Playwright failed: {e}, trying server-side scraping")
    
    # Fallback to server-side scraping (may not work if page is JS-rendered)
    try:
        logging.info(f"Using server-side scraping for '{keyword}' in '{location}'")
        jobs = scrape_timesjobs(keyword, location, limit=limit)
        
        # Handle error cases
        if not isinstance(jobs, list):
            logging.error(f"Scraping returned error: {jobs}")
            return []
        
        # Limit results
        return jobs[:limit]
    except Exception as e:
        logging.error(f"Scraping failed: {e}")
        return []


def display_jobs(job_list):
    """Nicely print the list of jobs returned by the scrapers."""
    if not isinstance(job_list, list):
        print(job_list)
        return

    if not job_list:
        print("0 jobs found")
        return

    print(f"Successfully found {len(job_list)} jobs.\n")
    for i, job in enumerate(job_list, 1):
        title, company, skills, location, salary, link, posted = job
        print(f"{i}. Job: {title}")
        print(f"   Company: {company}")
        print(f"   Skills: {', '.join(skills) if skills else 'N/A'}")
        print(f"   Location: {location}")
        print(f"   Salary: {salary}")
        print(f"   Posted: {posted}")
        if link and link != "N/A":
            print(f"   Link: {link}")
        print("-" * 30)


if __name__ == "__main__":
    job_role = "data scientist"
    city = "pune"

    print(f"Scraping first page jobs for '{job_role}' in '{city}'...")
    if PLAYWRIGHT_AVAILABLE:
        logging.info("Using Playwright to scrape first page")
        jobs = scrape_first_page_playwright(job_role, city)
    else:
        logging.info("Playwright unavailable; using server-side parse")
        jobs = scrape_timesjobs(job_role, city)

    display_jobs(jobs)
