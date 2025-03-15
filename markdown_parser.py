import re

def markdown_to_text_ultra_clean(markdown_text):
    """
    Parses a Markdown string and extracts plain text, aggressively removing
    non-essential elements including:
    - Markdown formatting (headings, lists, bold, italics, etc.)
    - HTML tags
    - URLs and associated link text
    - Navigation, contact info, legal, social media links
    - Copyright notices
    - Anything that looks like promotional text or a call to action.
    - Empty lines and excessive whitespace.

    Keeps only paragraph-level text.
    """

    # 1. Remove HTML tags (and content within <style> and <script> tags)
    text = re.sub(r'<style[^>]*>[\s\S]*?</style>', '', markdown_text, flags=re.IGNORECASE)
    text = re.sub(r'<script[^>]*>[\s\S]*?</script>', '', text, flags=re.IGNORECASE)
    text = re.sub(r'<[^>]+>', '', text)  # Remove any other HTML tags

    # 2. Remove image tags completely.
    text = re.sub(r'!\[[^\]]*\]\([^)]*\)', '', text)

    # 3. Remove URLs and link text entirely.  This is the key change.
    text = re.sub(r'\[[^\]]*\]\([^)]*\)', '', text)
    text = re.sub(r'https?://\S+', '', text)  # Remove any remaining URLs.
    text = re.sub(r'www\.\S+', '', text)


    # 4. Remove horizontal rules (---)
    text = re.sub(r'---\n', '', text)
    text = re.sub(r'^-+', '', text, flags=re.MULTILINE)


    # 5. Remove Markdown headings (#, ##, ###, etc.)
    text = re.sub(r'^#+\s*', '', text, flags=re.MULTILINE)

    # 6. Remove Markdown list markers (*, -, +, 1., etc.)
    text = re.sub(r'^\s*[\*\-\+]+\s+', '', text, flags=re.MULTILINE)  # Unordered lists
    text = re.sub(r'^\s*\d+\.\s+', '', text, flags=re.MULTILINE)    # Ordered lists
    text = re.sub(r'^\s*>', '', text, flags=re.MULTILINE)  # Remove blockquote marker


    # 7. Remove multiple newlines and condense.
    text = re.sub(r'\n{3,}', '\n\n', text)

    # 8. Remove extra spaces at beginning and end of lines and within lines.
    text = re.sub(r'^[ \t]+', '', text, flags=re.MULTILINE)
    text = re.sub(r'[ \t]+$', '', text, flags=re.MULTILINE)
    text = re.sub(r'[ \t]+', ' ', text)  # Condense internal whitespace

    # --- AGGRESSIVE REMOVALS (as per the updated requirements) ---

    # 9. Remove common navigation/footer phrases (case-insensitive)
    #    This list is significantly expanded to catch more variations.
    nav_phrases = [
        r"Support", r"Help Center", r"Get a Demo", r"Cookie", r"Privacy",
        r"Terms", r"Accessibility", r"GDPR/CCPA", r"Follow us on \w+",
        r"Copyright.*", r"All rights reserved.*", r"Subscribe to our YouTube Channel",
        r"Hire us to make such videos", r"See video examples", r"Join \d+\+? B2B Marketers",
        r"Schedule a call", r"Main Menu", r"Services", r"USE CASE", r"Engagement Model",
        r"Resources", r"Login", r"B2B Ads Library", r"Video Marketing", r"Creative as a service",
        r"Short video subscription", r"Product launch bundle", r"Our Work", r"Case Studies",
        r"Pricing", r"Guides", r"Playbooks", r"Newsletter", r"Creative", r"Demand Generation",
        r"Product Marketing", r"Brand Marketing", r"Social Media Marketing", r"Customer Marketing",
        r"Field Marketing", r"Video Portfolio", r"Design Portfolio", r"Content Beta",
        r"Contact", r"\+\d+-\(\d+\)-\d+-\d+", r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
        r"About Us", r"FAQ", r"Compare", r"Join our team", r"Partner with us", r"Sitemap", r"Video",
        r"Design", r"Animation", r"Graphic", r"Website", r"Presentations", r"Brand",
        r"Full-Service Production", r"Blog", r"Podcast", r"Competitors", r"Customer Stories",
        r"Capabilities", r"Use Case", r"Team", r"Get B2B Marketing insights every two weeks",
        r"Creative Swipe-files", r"New AI use cases for marketing", r"B2B Ad Creative breakdowns",
        r"Start with a Product video ad for your next campaign for \$97! 🎉",
        r"New to Content Beta\? You can test our service with no strings attached\.", r"Learn more",
        r"spots left for March", r"Case study ads that work: \$2M saved, 30% less churn\. Examples inside\.",
        r"You vs\. Them: Top-performing comparative ad examples that convert\.",
        r"Webinar ads that work: Capture attention, fill seats, & expand TOFU\. Examples inside\.",
        r"Skip to content", r"We have made videos for 200\+ B2B & SaaS companies\.",
        r"Explainer Video, Product Demo, Remote Video Testimonials, and more\.",
        r"Written by.*",  # Remove "Written by" lines
        r'^\w+\s+\d+,\s+\d{4}.*$',  # Remove "Month DD, YYYY"
        r'^.*@[^@\n]+\n?',  # Remove lines containing @ (author lines)
        r'^By\s+.*',  # Remove lines starting with "By "


    ]

    for phrase in nav_phrases:
        text = re.sub(phrase, '', text, flags=re.IGNORECASE)

    # 10. Remove any text starting from specific keywords that indicate unwanted content
    unwanted_starts = [
      r"Subscribe",
      r"Read also:",
      r"Learn more",

    ]

    for phrase in unwanted_starts:
        text = re.sub(rf'{phrase}.*', '', text, flags=re.IGNORECASE | re.DOTALL)


    #11 Remove headers if there is NO content following them (before next header or end of string).
    while True:
        original_text = text
        # Find headers followed immediately by another header or end of string.
        text = re.sub(r'^(#+.*?)\n(#+.*|\s*$)', r'\2', text, flags=re.MULTILINE)
        if text == original_text: # No changes?  We're done.
            break

    # Remove lines that consist of only whitespace and punctuation.
    text = re.sub(r'^\s*[\.,;:\-\(\)]+\s*$', '', text, flags=re.MULTILINE)

    #12 remove any text with in brackets
    text = re.sub(r'\[.*?\]', '', text)

    # Remove bold/italics/strikethrough markers (*, _, ~)
    text = re.sub(r'[\*\_~]+', '', text)
    # 13. Remove empty lines and extra spaces.
    text = re.sub(r'\n\s*\n', '\n\n', text)  # Replace multiple newlines
    text = re.sub(r'[ \t]+', ' ', text)      # Replace multiple spaces



    return text.strip()

file = open("research_5d404a6c-11fb-40eb-876e-32b2de9a5c06/knowledge_5dc686fa.md", "r")

cleaned = markdown_to_text_ultra_clean(file.read())

print(cleaned)

with open("cleaned.md", "w") as f:
    f.write(cleaned)

