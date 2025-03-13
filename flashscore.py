import os
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from collections import defaultdict

# Force unbuffered output
import sys
sys.stdout.reconfigure(line_buffering=True)  # Python 3.7+

# Output base directory
OUTPUT_DIR = "./output"

# Statistics tracking
stats = {
    "downloaded": 0,
    "skipped_not_png": 0,
    "error": 0,
    "regions": defaultdict(lambda: {"images": 0, "tournaments": 0}),
    "current_region": None
}

# Step 1: List of URLs to scrape
base_urls = [
    "https://www.flashscore.com/football/africa",
    "https://www.flashscore.com/football/asia"
]

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

def normalize_filename(name):
    """Convert name to lowercase and replace spaces with hyphens"""
    name = name.lower()
    name = re.sub(r'\s+', '-', name)  # Replace multiple spaces with a single hyphen
    name = re.sub(r' ', '-', name)    # Replace remaining spaces with hyphen
    return name

def sanitize_folder_name(name):
    """Sanitize name for use as folder name by replacing invalid characters"""
    # Replace slashes, backslashes and other problematic characters
    name = re.sub(r'[\\/:*?"<>|]', '-', name)
    return name

def is_png_image(url):
    """Check if the URL points to a PNG image"""
    # Check the file extension in the URL
    return url.lower().endswith('.png')

def extract_region_name_from_html(soup):
    """Extract region name from the specific breadcrumb after a span tag"""
    try:
        # Get the raw HTML as a string
        html_str = str(soup)
        
        # Use regex to find the pattern </span><a class="breadcrumb__link" href="...">Region Name</a>
        pattern = re.compile(r'</span>\s*<a\s+class="breadcrumb__link"\s+href="[^"]+">([^<]+)</a>')
        match = pattern.search(html_str)
        
        if match:
            region_name = match.group(1).strip()  # Group 1 contains the region name
            return sanitize_folder_name(region_name)
        
        # Fallback: Try using BeautifulSoup to find any breadcrumb link after a span
        for span in soup.find_all('span'):
            next_element = span.next_sibling
            if (next_element and hasattr(next_element, 'name') and 
                next_element.name == 'a' and 
                'breadcrumb__link' in next_element.get('class', [])):
                region_name = next_element.text.strip()
                return sanitize_folder_name(region_name)
        
        # Second fallback: Look for any breadcrumb link
        breadcrumbs = soup.select('a.breadcrumb__link')
        if breadcrumbs:
            for breadcrumb in breadcrumbs:
                # Check if this breadcrumb appears to be a region
                if breadcrumb.text.strip():
                    region_name = breadcrumb.text.strip()
                    return sanitize_folder_name(region_name)
        
        # Last fallback: Use the last part of the URL
        for url in base_urls:
            if url in html_str:
                path = url.split('/')[-1]
                region_name = path.replace('-', ' ').title()
                return sanitize_folder_name(region_name)
                
        return "Unknown-Region"
        
    except Exception as e:
        print(f"Error extracting region name: {e}", flush=True)
        return "Unknown-Region"

def download_image(img_url, region_folder, img_name):
    """Download and save image to specified region folder if it's a PNG"""
    try:
        # Skip if not a PNG image
        if not is_png_image(img_url):
            stats["skipped_not_png"] += 1
            return False
        
        # Keep original name for display
        original_name = img_name
            
        # Create full folder path
        full_folder_path = os.path.join(OUTPUT_DIR, region_folder)
        
        # Create folder if it doesn't exist
        if not os.path.exists(full_folder_path):
            os.makedirs(full_folder_path)
        
        # Normalize image name for filename
        normalized_name = normalize_filename(img_name)
        if not normalized_name.endswith('.png'):
            normalized_name += '.png'
            
        # Full path for saving the image
        img_path = os.path.join(full_folder_path, normalized_name)
        
        # Check if file already exists
        if os.path.exists(img_path):
            return False
        
        # Download image
        response = requests.get(img_url, headers=headers, stream=True)
        response.raise_for_status()
        
        # Save image
        with open(img_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        # Update statistics
        stats["downloaded"] += 1
        stats["regions"][region_folder]["images"] += 1
        
        # Print progress with flush=True for immediate display
        print(f"+ {original_name}", flush=True)
        return True
        
    except Exception as e:
        print(f"! Error with {img_name}: {str(e)[:50]}...", flush=True)
        stats["error"] += 1
        return False

def scrape_tournament_pages(base_url):
    """Step 2: Scrape tournament pages from base URL"""
    try:
        response = requests.get(base_url, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Get region name from the breadcrumb
        region_name = extract_region_name_from_html(soup)
        stats["current_region"] = region_name
        
        # Find all tournament links
        tournaments = []
        links = soup.select('a.leftMenu__href')
        
        for link in links:
            url = link.get('href')
            
            if url:
                full_url = urljoin(base_url, url)
                tournaments.append({
                    'url': full_url,
                    'region': region_name
                })
        
        # Update tournament count for this region        
        stats["regions"][region_name]["tournaments"] = len(tournaments)
                
        return tournaments
        
    except Exception as e:
        print(f"Error scraping {base_url}: {e}", flush=True)
        stats["error"] += 1
        return []

def scrape_images(tournament_data):
    """Step 3: Scrape images from tournament page"""
    try:
        url = tournament_data['url']
        region = tournament_data['region']
        
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Find all images
        images = soup.select('img.heading__logo.heading__logo--1')
        
        for img in images:
            img_url = img.get('src')
            img_name = img.get('alt')
            
            if img_url and img_name:
                img_url = urljoin(url, img_url)
                download_image(img_url, region, img_name)
        
    except Exception as e:
        print(f"Error processing tournament: {str(e)[:50]}...", flush=True)
        stats["error"] += 1

def main():
    # Create output directory if it doesn't exist
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    print("Flashscore...", flush=True)
    
    # Process each base URL
    for base_url in base_urls:
        tournaments = scrape_tournament_pages(base_url)
        
        if not tournaments:
            continue
            
        # Display region header with tournament count
        region_name = stats["current_region"]
        tournament_count = stats["regions"][region_name]["tournaments"]
        print(f"\n{region_name} ({tournament_count} tournaments)", flush=True)
        
        # Process each tournament and download images
        for tournament in tournaments:
            scrape_images(tournament)
            # No delay
    
    # Display final statistics
    print("\nTotal: {0} done, {1} skip, {2} error".format(
        stats["downloaded"], 
        stats["skipped_not_png"], 
        stats["error"]
    ), flush=True)
    print("\nComplete!", flush=True)

if __name__ == "__main__":
    main()
