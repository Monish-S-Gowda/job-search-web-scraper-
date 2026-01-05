"""Utility script to inspect job card HTML structure from timesjobs.com"""

import time
from bs4 import BeautifulSoup

# Configuration
role = "data scientist"
location = "pune"


def inspect_job_cards(role, location):
    """Inspect job card HTML structure using Playwright."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Error: Playwright is not installed.")
        print("Install it with: pip install playwright && playwright install")
        return

    # Build URL
    keywords = role.replace(' ', '+')
    location_query = location.replace(' ', '+')
    url = (
        f"https://www.timesjobs.com/job-search?keywords={keywords}"
        f"&location={location_query}&experience=&refreshed=true&pg=1"
    )

    print(f"Inspecting job cards for '{role}' in '{location}'...")
    print(f"URL: {url}\n")

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, wait_until='domcontentloaded', timeout=60000)
            time.sleep(2)
            html = page.content()
            browser.close()

        soup = BeautifulSoup(html, 'html.parser')
        
        # Find job card containers
        cards = soup.find_all('div', class_=lambda v: v and 'srp-card' in v)
        print(f"Found {len(cards)} srp-card divs")
        
        if not cards:
            # Fallback: try alternative selectors
            alt_cards = soup.find_all('li', class_='clearfix job-bx wht-shd-bx')
            if alt_cards:
                print(f"Found {len(alt_cards)} alternative job cards (li.clearfix)")
                print(alt_cards[0].prettify()[:2000])
            else:
                print("No job cards found. Printing page snippet:")
                print(soup.prettify()[:2000])
        else:
            print("\nFirst job card structure:")
            print(cards[0].prettify())
            
    except Exception as e:
        print(f"Error during inspection: {e}")


if __name__ == "__main__":
    inspect_job_cards(role, location)
