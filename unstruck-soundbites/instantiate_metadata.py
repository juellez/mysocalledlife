import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin
from datetime import datetime
import re
import os
import yaml
import mimetypes

def download_first_image(soup, base_url, filename_base):
    """
    Download the first image from the Substack post's single-post element
    """
    # Find the single-post div
    single_post_div = soup.find('div', class_='single-post')
    
    if not single_post_div:
        return None, None
    
    # Try to find the first meaningful image in the single-post div
    image_candidates = single_post_div.find_all(['img', 'picture'])
    
    for img in image_candidates:
        # Try to get the image source
        if img.name == 'picture':
            # For picture tags, find the first source or img
            src_elem = img.find('source') or img.find('img')
            if not src_elem:
                continue
            src = src_elem.get('srcset') or src_elem.get('src')
        else:
            src = img.get('src')
        
        # Skip if no source found
        if not src:
            continue
        
        # Resolve relative URLs
        full_url = urljoin(base_url, src)
        
        try:
            # Download the image
            img_response = requests.get(full_url)
            img_response.raise_for_status()
            
            # Determine file extension
            content_type = img_response.headers.get('content-type', '')
            ext = mimetypes.guess_extension(content_type) or '.jpg'
            
            # Ensure images directory exists
            os.makedirs('images', exist_ok=True)
            
            # Create full image path
            img_filename = f"images/{filename_base}{ext}"
            
            # Save the image
            with open(img_filename, 'wb') as f:
                f.write(img_response.content)
            
            # Try to extract image attribution
            attribution = extract_image_attribution(img)
            
            return img_filename, attribution
        
        except Exception as e:
            print(f"Error downloading image: {e}")
            continue
    
    return None, None

def extract_image_attribution(img_elem):
    """
    Try to extract image attribution from various possible sources
    """
    # Look for a figcaption near the image
    figcaption = img_elem.find_parent('figure')
    if figcaption:
        caption_elem = figcaption.find('figcaption')
        if caption_elem:
            return caption_elem.get_text(strip=True)
    
    # Check for alt text
    alt = img_elem.get('alt', '').strip()
    
    # Check for title attribute
    title = img_elem.get('title', '').strip()
    
    # Prioritize sources of attribution
    attribution = (
        alt or 
        title or 
        "Image source unknown"
    )
    
    return attribution

def generate_tags(title, subtitle):
    """
    Generate initial tags based on the title and subtitle
    """
    # List of potential generic tags
    generic_tags = [
        "personal growth", "reflection", "life lessons", 
        "self-awareness", "mindfulness", "practice"
    ]
    
    # Convert to lowercase for easier matching
    text = f"{title} {subtitle}".lower()
    
    # Define a mapping of specific keywords to tags
    tag_mapping = {
        "forest": ["nature", "metaphor"],
        "trees": ["nature", "perspective"],
        "puppy": ["animals", "learning"],
        "attention": ["presence", "mindfulness"],
        "somatics": ["body awareness", "embodiment"],
        "practice": ["personal development", "skill building"]
    }
    
    # Collect tags
    tags = []
    for keyword, tag_list in tag_mapping.items():
        if keyword in text:
            tags.extend(tag_list)
    
    # Add some generic tags if no specific tags found
    if not tags:
        tags = generic_tags[:3]
    
    # Ensure unique tags and limit to 5
    return list(dict.fromkeys(tags))[:5]

def extract_metadata_from_substack(url):
    """
    Extract metadata from a Substack URL
    """
    try:
        # Fetch the webpage
        response = requests.get(url)
        response.raise_for_status()
        
        # Parse the HTML
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Extract title
        title_elem = soup.find('h1', class_='post-title')
        title = title_elem.text.strip() if title_elem else "Untitled"
        
        # Look for subtitle
        subtitle_elem = soup.find('h3', class_='subtitle')
        subtitle = subtitle_elem.text.strip() if subtitle_elem else ""
        
        # Try to get publication date
        date_elem = soup.find('div', class_='meta-EgzBVA')
        if date_elem:
            date_text = date_elem.find_all('div')[-1].text.strip()
            try:
                # Convert date to YYYY-MM-DD format
                parsed_date = datetime.strptime(date_text, '%b %d, %Y')
                current_date = parsed_date.strftime('%Y-%m-%d')
            except:
                current_date = datetime.now().strftime("%Y-%m-%d")
        else:
            current_date = datetime.now().strftime("%Y-%m-%d")
        
        # Generate slug
        slug = re.sub(r'[^\w\s-]', '', title.lower()).replace(' ', '-')
        
        # Generate tags
        tags = generate_tags(title, subtitle)
        
        # Generate filename base
        filename_base = f"{current_date}-{slug}"
        
        # Try to download first image
        img_path, img_attribution = download_first_image(soup, url, filename_base)
        
        # Prepare metadata dictionary
        metadata = {
            'title': title,
            'description': subtitle,
            'date': current_date,
            'original_url': url,
            'platform': 'Substack',
            'author': 'jewel mlnarik',
            'author_url': 'https://jewel.mlnarik.com',
            'tags': tags
        }
        
        # Create filename
        filename = f"{filename_base}.md"
        
        # Write to file
        with open(filename, 'w', encoding='utf-8') as f:
            # Write YAML front matter
            f.write('---\n')
            yaml.safe_dump(metadata, f, default_flow_style=False)
            f.write('---\n\n')
            
            # Add featured image if found
            if img_path:
                f.write(f"![{img_attribution}]({img_path})\n\n")
            
            # Add title and subtitle sections
            f.write(f"# {title}\n")
            f.write(f"*{subtitle}*\n\n")
            f.write("<userStyle>Normal</userStyle>\n")
        
        print(f"Metadata file created: {filename}")
        
        return filename
    
    except Exception as e:
        print(f"Error extracting metadata: {e}")
        return None

def main():
    # Get URL from user
    url = input("Enter the Substack URL: ").strip()
    
    # Validate URL
    parsed_url = urlparse(url)
    if not parsed_url.scheme or not parsed_url.netloc:
        print("Invalid URL. Please enter a complete URL.")
        return
    
    # Extract and create metadata file
    extract_metadata_from_substack(url)

if __name__ == "__main__":
    main()