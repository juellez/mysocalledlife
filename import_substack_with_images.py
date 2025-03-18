import feedparser
import re
import os
import time
import requests
from urllib.parse import urlparse
from datetime import datetime
from html import unescape
from bs4 import BeautifulSoup

# Create directories if they don't exist
os.makedirs('unstruck-soundbites/images', exist_ok=True)
os.makedirs('unstruck-soundbites/audio', exist_ok=True)

# Pull from Substack RSS
feed_url = 'https://unstrucksoundbites.substack.com/feed'
print(f"Fetching feed from {feed_url}...")
feed = feedparser.parse(feed_url)
print(f"Found {len(feed.entries)} posts")

# Process each post
for i, entry in enumerate(feed.entries):
    # Extract metadata
    title = entry.title
    description = entry.description if hasattr(entry, 'description') else ""
    permalink = entry.link
    
    # Extract slug from permalink
    url_path = urlparse(permalink).path
    slug = url_path.split('/')[-1]
    
    # Parse date
    if "GMT" in entry.published:
        date_format = '%a, %d %b %Y %H:%M:%S GMT'
    else:
        date_format = '%a, %d %b %Y %H:%M:%S %z'
    
    try:
        date = datetime.strptime(entry.published, date_format)
    except ValueError:
        print(f"Warning: Could not parse date '{entry.published}', using today's date")
        date = datetime.now()
    
    # Create filename using the slug from the URL
    filename = f"unstruck-soundbites/{date.strftime('%Y-%m-%d')}-{slug}.md"
    
    # Check if file already exists
    if os.path.exists(filename):
        print(f"File {filename} already exists. Skipping...")
        continue
    
    print(f"Processing ({i+1}/{len(feed.entries)}): {title}")
    
    # Check for audio content
    has_audio = False
    audio_url = None
    if hasattr(entry, 'enclosures') and entry.enclosures:
        for enclosure in entry.enclosures:
            if enclosure.get('type', '') == 'audio/mpeg':
                has_audio = True
                audio_url = enclosure.get('url', '')
                print(f"  Post has audio: {audio_url}")
                break
            elif enclosure.get('type', '').startswith('image/'):
                # This is likely a featured image
                featured_image_url = enclosure.get('url', '')
                print(f"  Post has featured image: {featured_image_url}")
    
    # Get content from RSS feed
    content = entry.content[0].value
    
    # Check if content is truncated and contains "Read more"
    if "Read more" in content:
        print(f"  Content appears truncated. Attempting to fetch full content from {permalink}")
        try:
            # Fetch the full article
            response = requests.get(permalink)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Try different selectors for Substack posts
                selectors = [
                    'div.post-content',
                    'div.body', 
                    'div.markup',
                    'article',
                    'div.post'
                ]
                
                article_content = None
                for selector in selectors:
                    article = soup.select_one(selector)
                    if article:
                        article_content = str(article)
                        break
                
                if article_content:
                    content = article_content
                    print("  Successfully fetched full content")
                else:
                    print("  Could not find article content, using RSS content")
            else:
                print(f"  Failed to fetch full article: {response.status_code}")
        except Exception as e:
            print(f"  Error fetching full article: {e}")
    
    # Convert content to BeautifulSoup for easier parsing
    soup = BeautifulSoup(content, 'html.parser')
    
    # Handle images with captions
    for figure in soup.find_all('figure'):
        img = figure.find('img')
        figcaption = figure.find('figcaption')
        
        if img and img.get('src'):
            img_url = img['src']
            img_alt = img.get('alt', '')
            
            # Create a filename for the image
            parsed_url = urlparse(img_url)
            img_filename = os.path.basename(parsed_url.path).split('?')[0]
            
            # If filename has no extension, create a new one
            if '.' not in img_filename:
                img_filename = f"image-{date.strftime('%Y%m%d')}-{hash(img_url) % 1000}.jpg"
            
            img_path = f"images/{img_filename}"
            
            # Download the image (commented out for testing)
            print(f"  Found image: {img_url}")
            
            # Create markdown for image with caption
            md_image = f"![{img_alt}]({img_path})\n"
            
            if figcaption:
                caption_html = str(figcaption)
                # Convert caption HTML to markdown
                caption_text = figcaption.get_text()
                # Preserve links in caption
                for a in figcaption.find_all('a'):
                    href = a.get('href', '')
                    text = a.get_text()
                    caption_text = caption_text.replace(text, f"[{text}]({href})")
                
                md_image += f"<small>{caption_text}</small>\n\n"
            else:
                md_image += "\n"
            
            # Replace the figure with markdown in the original content
            figure_html = str(figure)
            content = content.replace(figure_html, md_image)
    
    # Basic HTML to Markdown conversion
    # This will be simplified - a proper HTML to Markdown converter would be better
    content = re.sub(r'<p>(.*?)</p>', r'\1\n\n', content, flags=re.DOTALL)
    content = re.sub(r'<strong>(.*?)</strong>', r'**\1**', content, flags=re.DOTALL)
    content = re.sub(r'<em>(.*?)</em>', r'*\1*', content, flags=re.DOTALL)
    content = re.sub(r'<h1>(.*?)</h1>', r'# \1\n\n', content, flags=re.DOTALL)
    content = re.sub(r'<h2>(.*?)</h2>', r'## \1\n\n', content, flags=re.DOTALL)
    content = re.sub(r'<h3>(.*?)</h3>', r'### \1\n\n', content, flags=re.DOTALL)
    content = re.sub(r'<blockquote>(.*?)</blockquote>', r'> \1\n\n', content, flags=re.DOTALL)
    content = re.sub(r'<br/?>', r'\n', content)
    
    # Process lists
    content = re.sub(r'<ul>(.*?)</ul>', lambda m: re.sub(r'<li>(.*?)</li>', r'* \1\n', m.group(1)), content, flags=re.DOTALL)
    content = re.sub(r'<ol>(.*?)</ol>', lambda m: re.sub(r'<li>(.*?)</li>', r'1. \1\n', m.group(1)), content, flags=re.DOTALL)
    
    # Clean up any remaining HTML tags
    content = re.sub(r'<[^>]+>', '', content)
    
    # Unescape HTML entities
    content = unescape(content)
    
    # Create tags
    common_themes = ['attention', 'presence', 'somatics', 'practice', 'leadership', 'healing']
    tags = [theme for theme in common_themes if theme.lower() in content.lower() or theme.lower() in title.lower()]
    tags_str = '", "'.join(tags)
    tags_formatted = f'["{tags_str}"]' if tags else '[]'
    
    # Create frontmatter
    frontmatter = f"""---
title: "{title}"
date: {date.strftime('%Y-%m-%d')}
original_url: {permalink}
platform: "Substack"
author: "jewel mlnarik"
tags: {tags_formatted}
"""

    if has_audio:
        frontmatter += f'audio_url: "{audio_url}"\n'
        frontmatter += 'has_audio: true\n'
    
    frontmatter += "---\n\n"
    
    # Add title and description at the beginning of the content
    formatted_content = f"# {title}\n\n"
    
    if description:
        formatted_content += f"*{description}*\n\n"
    
    # Combine everything
    final_content = frontmatter + formatted_content + content
    
    # Save to markdown file
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(final_content)
    
    print(f"  Saved: {filename}")
    print("  ------------------------------")
    
    # Rate limiting
    time.sleep(1)

print("Import complete!")