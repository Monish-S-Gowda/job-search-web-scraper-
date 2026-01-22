import os
from flask import Flask, send_from_directory, request, jsonify, render_template
from urllib.parse import quote

ROOT = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__, static_folder=ROOT, static_url_path='', template_folder='templates')

# Import the scraping function
from naukri_scraper import scrape_naukri_jobs


@app.route("/")
def index():
    return send_from_directory(ROOT, "main.html")


@app.route("/search", methods=["POST"])
def search():
    data = request.get_json()
    
    # Store the two inputs in variables
    keyword = data.get('keyword', '')
    location = data.get('location', '')
    
    # Return JSON with redirect URL (URL encode the parameters)
    return jsonify({
        'status': 'success',
        'redirect': f'/results?keyword={quote(keyword)}&location={quote(location)}'
    })


@app.route("/results", methods=["GET"])
def results():
    # Get keyword and location from query parameters
    keyword = request.args.get('keyword', '')
    location = request.args.get('location', '')
    
    # Scrape jobs using the function from job_scrape.py
    jobs = scrape_naukri_jobs(keyword, location)
    
    # Debug: Log the number of jobs found
    import logging
    logging.info(f"Results page: Found {len(jobs) if isinstance(jobs, list) else 0} jobs for '{keyword}' in '{location}'")
    
    # Render the results template with the scraped jobs
    return render_template('results.html', 
                         keyword=keyword, 
                         location=location, 
                         jobs=jobs)


@app.route("/<path:filename>")
def serve_file(filename):
    return send_from_directory(ROOT, filename)


if __name__ == "__main__":
    # Run Flask with debug mode
    # Note: If you experience constant reloads due to Playwright, 
    # you can disable reloader by setting use_reloader=False
    app.run(
        debug=True, 
        host="0.0.0.0", 
        port=5000,
        use_reloader=False  # Disabled to prevent Playwright file watching issues
    )
