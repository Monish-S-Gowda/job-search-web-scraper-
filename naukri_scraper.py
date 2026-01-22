import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

def scrape_naukri_jobs(job_keyword, location):
    """
    Scrapes job cards from Naukri.com using Selenium to bypass bot detection.
    
    Args:
        job_keyword (str): The job designation (e.g., 'web development')
        location (str): The city (e.g., 'bengaluru')
        
    Returns:
        list: A 2D list where each inner list contains [Title, Company, Experience, Location, Description]
    """
    
    # Format the URL with hyphens
    job_path = job_keyword.lower().replace(" ", "-")
    loc_path = location.lower().replace(" ", "-")
    
    url = f"https://www.naukri.com/{job_path}-jobs-in-{loc_path}"
    print(f"Scraping URL: {url}")

    # Setup Chrome options
    chrome_options = Options()
    chrome_options.add_argument("--headless=new") # Run in headless mode
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--window-size=1920,1080")
    # Add user agent to mimic real browser
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

    driver = None
    job_data_list = []

    try:
        # Initialize WebDriver
        print("Initializing Chrome Driver Manager...")
        service_path = ChromeDriverManager().install()
        print(f"Driver installed at: {service_path}")
        
        print("Starting Chrome Driver...")
        service = Service(service_path)
        driver = webdriver.Chrome(service=service, options=chrome_options)
        print("Driver started successfully.")
        
        driver.get(url)
        print("URL loaded. Waiting for content...")
        
        # Wait for job cards to load (timeout after 10 seconds)
        wait = WebDriverWait(driver, 10)
        try:
            wait.until(EC.presence_of_element_located((By.CLASS_NAME, "srp-jobtuple-wrapper")))
            print("Page loaded successfully.")
        except Exception:
            print("Timeout waiting for job cards. Page might not have loaded correctly or no jobs found.")
            return job_data_list

        # Find all job card wrappers
        job_cards = driver.find_elements(By.CLASS_NAME, "srp-jobtuple-wrapper")
        print(f"Found {len(job_cards)} job cards. extracting data...")

        for card in job_cards:
            try:
                # 1. Job Title & URL
                try:
                    title_elem = card.find_element(By.CLASS_NAME, "title")
                    title = title_elem.text
                    job_url = title_elem.get_attribute("href")
                except:
                    title = "N/A"
                    job_url = "N/A"
                
                # 2. Company Name
                try:
                    company_elem = card.find_element(By.CLASS_NAME, "comp-name")
                    company = company_elem.text
                except:
                    company = "N/A"
                
                # 3. Experience Required
                try:
                    # Often nested in a specific span inside expwdth
                    exp_elem = card.find_element(By.CLASS_NAME, "expwdth")
                    experience = exp_elem.text
                except:
                    experience = "N/A"
                
                # 4. Location
                try:
                    loc_elem = card.find_element(By.CLASS_NAME, "locWdth")
                    job_location = loc_elem.text
                except:
                    job_location = "N/A"
                
                # 5. Job Description (Snippet)
                try:
                    # Typically just class 'job-desc'
                    desc_elem = card.find_element(By.CLASS_NAME, "job-desc")
                    description = desc_elem.text
                except:
                    description = "N/A"
                
                # Append as a row in our 2D list
                job_data_list.append([
                    title,
                    company,
                    experience,
                    job_location,
                    description,
                    job_url
                ])
                
            except Exception as e:
                print(f"Error extracting card: {e}")
                continue

    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        if driver:
            driver.quit()

    return job_data_list

# Example Usage:
if __name__ == "__main__":
    job_input = "web development"
    location_input = "bengaluru"
    
    results = scrape_naukri_jobs(job_input, location_input)
    
    # Print the 2D list nicely
    print(f"\nTotal Jobs Scraped: {len(results)}\n")
    for i, job in enumerate(results[:5], 1): # Print first 5 for verification
        print(f"--- Job {i} ---")
        print(f"Title: {job[0]}")
        print(f"Company: {job[1]}")
        print(f"Exp: {job[2]}")
        print(f"Loc: {job[3]}")
        print(f"Desc: {job[4]}")