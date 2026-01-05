"""Inspect the actual HTML structure from timesjobs.com"""

import requests
from bs4 import BeautifulSoup
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

keyword = "python"
location = "pune"
keywords = keyword.replace(" ", "+")
location_query = location.replace(" ", "+")
url = f"https://www.timesjobs.com/job-search?keywords={keywords}&location={location_query}&experience=&refreshed=true&pg=1"

headers = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    )
}

print("=" * 60)
print("Inspecting HTML Structure")
print("=" * 60)
print(f"URL: {url}\n")

try:
    resp = requests.get(url, headers=headers, timeout=15, verify=False)
    resp.raise_for_status()
    print(f"Status Code: {resp.status_code}")
    print(f"Content Length: {len(resp.content)} bytes\n")
    
    soup = BeautifulSoup(resp.content, "html.parser")
    
    # Check page title
    title = soup.title
    print(f"Page Title: {title.string if title else 'No title'}\n")
    
    # Look for common job listing patterns
    print("Searching for job card patterns...")
    print("-" * 60)
    
    # Pattern 1: li with job-bx
    li_job_bx = soup.find_all("li", class_=lambda v: v and "job" in " ".join(v).lower() if v else False)
    print(f"1. <li> elements with 'job' in class: {len(li_job_bx)}")
    if li_job_bx:
        print(f"   First element classes: {li_job_bx[0].get('class')}")
        print(f"   First element preview: {str(li_job_bx[0])[:200]}...")
    
    # Pattern 2: div with job or card
    div_job = soup.find_all("div", class_=lambda v: v and ("job" in " ".join(v).lower() or "card" in " ".join(v).lower()) if v else False)
    print(f"\n2. <div> elements with 'job' or 'card' in class: {len(div_job)}")
    if div_job:
        print(f"   First element classes: {div_job[0].get('class')}")
        print(f"   First element preview: {str(div_job[0])[:200]}...")
    
    # Pattern 3: Any element with srp (search results page)
    srp_elements = soup.find_all(class_=lambda v: v and "srp" in " ".join(v).lower() if v else False)
    print(f"\n3. Elements with 'srp' in class: {len(srp_elements)}")
    if srp_elements:
        print(f"   First element tag: {srp_elements[0].name}")
        print(f"   First element classes: {srp_elements[0].get('class')}")
    
    # Pattern 4: Look for article or section tags
    articles = soup.find_all("article")
    sections = soup.find_all("section")
    print(f"\n4. <article> elements: {len(articles)}")
    print(f"   <section> elements: {len(sections)}")
    
    # Pattern 5: Look for any list items
    all_lis = soup.find_all("li")
    print(f"\n5. Total <li> elements: {len(all_lis)}")
    if all_lis:
        print(f"   Sample <li> classes: {[li.get('class') for li in all_lis[:5] if li.get('class')]}")
    
    # Check if page might be JavaScript-rendered
    scripts = soup.find_all("script")
    print(f"\n6. <script> tags found: {len(scripts)}")
    
    # Look for common indicators of JS-rendered content
    body_text = soup.get_text() if soup.body else ""
    if len(body_text) < 500:
        print("   WARNING: Page content seems very short - might be JavaScript-rendered")
    
    # Save a sample of the HTML for inspection
    print("\n" + "=" * 60)
    print("Saving HTML sample to inspect_html_sample.html")
    with open("inspect_html_sample.html", "w", encoding="utf-8") as f:
        f.write(soup.prettify()[:5000])  # First 5000 chars
    print("Sample saved!")
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()

