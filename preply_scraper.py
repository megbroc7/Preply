import time
import datetime
import requests
import re
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# CONFIGURATION
AIRTABLE_API_KEY = "patBBWNeRi3YNmuHa.23c60bd16fa64948f0c5e65c2527cbf4e0eda930125ab379eb0713f473f4b68c"
BASE_ID = "appgOV8Yi4lS0DI05"
TUTOR_TABLE_NAME = "Tutor Data"
EVENT_LOG_TABLE_NAME = "Event Log"
PREPLY_URL = "https://preply.com/en/online/businessandmanagement-tutors"
MAX_RETRIES = 3
MAX_WAIT_TIME = 15  # seconds to wait for page load

def log_event(event, status):
    """
    Logs an event to the Event Log table with the given event name and status.
    """
    url = f"https://api.airtable.com/v0/{BASE_ID}/{EVENT_LOG_TABLE_NAME}"
    headers = {
        "Authorization": f"Bearer {AIRTABLE_API_KEY}",
        "Content-Type": "application/json"
    }
    event_data = {
        "records": [
            {
                "fields": {
                    "Event": event,
                    "Date of Entry": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    "Status": status
                }
            }
        ]
    }

    for attempt in range(MAX_RETRIES):
        try:
            response = requests.post(url, json=event_data, headers=headers)
            response.raise_for_status()
            return True
        except Exception as e:
            if attempt == MAX_RETRIES - 1:
                print(f"Failed to log event '{event}': {e}")
                return False
            time.sleep(2)

def append_tutor_record(tutor_name, num_reviews, active_students, num_lessons, price_value=0, price_currency=""):
    """
    Append a new record to the Tutor Data table in Airtable with price information.
    """
    url = f"https://api.airtable.com/v0/{BASE_ID}/{TUTOR_TABLE_NAME}"
    headers = {
        "Authorization": f"Bearer {AIRTABLE_API_KEY}",
        "Content-Type": "application/json"
    }
    date_of_entry = datetime.datetime.now(datetime.timezone.utc).isoformat()
    
    # Create the fields dict
    fields = {
        "Tutor Name": tutor_name,
        "Number of Reviews": num_reviews,
        "Active Students": active_students,
        "Number of Lessons": num_lessons,
        "Date of Entry": date_of_entry
    }
    
    # Add price fields if available
    if price_value > 0:
        fields["Price Value"] = price_value
    if price_currency:
        fields["Price Currency"] = price_currency
    
    data = {
        "records": [
            {
                "fields": fields
            }
        ]
    }

    print("Sending to Airtable:", data)

    for attempt in range(MAX_RETRIES):
        try:
            response = requests.post(url, json=data, headers=headers)
            response.raise_for_status()
            return True
        except Exception as e:
            if attempt == MAX_RETRIES - 1:
                print(f"Failed to append tutor record for {tutor_name}: {e}")
                return False
            time.sleep(2)

def element_exists(driver, by, selector):
    """
    Check if an element exists on the page without throwing an exception.
    """
    try:
        driver.find_element(by, selector)
        return True
    except:
        return False

def extract_price_from_card(card):
    """
    Extract price from tutor card with a comprehensive approach to handle various currencies
    """
    try:
        # APPROACH 1: Look for price data attributes
        # Websites often use data attributes for important data like prices
        price_attribute_selectors = [
            "[data-qa='price']",
            "[data-qa-group='price']",
            "[data-qa-selector='price']",
            "[data-price]"
        ]
        
        for selector in price_attribute_selectors:
            try:
                elements = card.find_elements(By.CSS_SELECTOR, selector)
                if elements:
                    for elem in elements:
                        text = elem.text.strip()
                        if text and re.search(r'[\$€£¥₽₴₹]\s*\d+|\d+\s*[\$€£¥₽₴₹]', text):
                            # Extract price with regex
                            match = re.search(r'([\$€£¥₽₴₹])\s*(\d+(?:[.,]\d+)?)|(\d+(?:[.,]\d+)?)\s*([\$€£¥₽₴₹])', text)
                            if match:
                                if match.group(1):  # Format: $50
                                    currency = match.group(1)
                                    value = float(match.group(2).replace(',', ''))
                                else:  # Format: 50$
                                    currency = match.group(4)
                                    value = float(match.group(3).replace(',', ''))
                                return value, currency
            except:
                continue
                
        # APPROACH 2: Based on layout in screenshot - look for elements containing numbers 
        # near the "min lesson" text or "per hour" text
        try:
            lesson_text_selectors = [
                ".//*[contains(text(), 'min lesson')]",
                ".//*[contains(text(), 'per hour')]"
            ]
            
            for xpath_selector in lesson_text_selectors:
                try:
                    lesson_elements = card.find_elements(By.XPATH, xpath_selector)
                    if lesson_elements:
                        # Check nearby elements for price format
                        for lesson_elem in lesson_elements:
                            try:
                                # Try parent element and its children
                                parent = lesson_elem.find_element(By.XPATH, "./../..")
                                all_elements = parent.find_elements(By.XPATH, ".//*")
                                
                                for elem in all_elements:
                                    text = elem.text.strip()
                                    # Look for currency symbol followed or preceded by digits
                                    if re.search(r'[\$€£¥₽₴₹]\s*\d+|\d+\s*[\$€£¥₽₴₹]', text):
                                        match = re.search(r'([\$€£¥₽₴₹])\s*(\d+(?:[.,]\d+)?)|(\d+(?:[.,]\d+)?)\s*([\$€£¥₽₴₹])', text)
                                        if match:
                                            if match.group(1):  # Format: $50
                                                currency = match.group(1)
                                                value = float(match.group(2).replace(',', ''))
                                            else:  # Format: 50$
                                                currency = match.group(4)
                                                value = float(match.group(3).replace(',', ''))
                                            return value, currency
                            except:
                                continue
                except:
                    continue
        except:
            pass
            
        # APPROACH 3: General search through all elements
        try:
            # Get all text elements on the card
            all_elements = card.find_elements(By.XPATH, ".//*")
            
            # First look for standalone price format (e.g., "$50" or "€89" alone in an element)
            for elem in all_elements:
                try:
                    text = elem.text.strip()
                    # Look for text that is just a price (currency symbol + number)
                    if re.match(r'^[\$€£¥₽₴₹]\s*\d+(?:[.,]\d+)?$|^\d+(?:[.,]\d+)?\s*[\$€£¥₽₴₹]$', text):
                        match = re.search(r'([\$€£¥₽₴₹])\s*(\d+(?:[.,]\d+)?)|(\d+(?:[.,]\d+)?)\s*([\$€£¥₽₴₹])', text)
                        if match:
                            if match.group(1):  # Format: $50
                                currency = match.group(1)
                                value = float(match.group(2).replace(',', ''))
                            else:  # Format: 50$
                                currency = match.group(4)
                                value = float(match.group(3).replace(',', ''))
                            return value, currency
                except:
                    continue
                    
            # Then try finding price within larger text
            for elem in all_elements:
                try:
                    text = elem.text.strip()
                    # Look for currency symbol followed or preceded by digits
                    if re.search(r'[\$€£¥₽₴₹]\s*\d+|\d+\s*[\$€£¥₽₴₹]', text):
                        match = re.search(r'([\$€£¥₽₴₹])\s*(\d+(?:[.,]\d+)?)|(\d+(?:[.,]\d+)?)\s*([\$€£¥₽₴₹])', text)
                        if match:
                            if match.group(1):  # Format: $50
                                currency = match.group(1)
                                value = float(match.group(2).replace(',', ''))
                            else:  # Format: 50$
                                currency = match.group(4)
                                value = float(match.group(3).replace(',', ''))
                            return value, currency
                except:
                    continue
        except:
            pass
            
        # If nothing found, return default values
        return 0, ""
    except Exception as e:
        print(f"Error extracting price: {e}")
        return 0, ""

def debug_tutor_card(card, tutor_name):
    """
    Save the HTML of a tutor card for debugging purposes with enhanced element detection
    """
    try:
        html = card.get_attribute('outerHTML')
        with open(f"tutor_card_{tutor_name.replace(' ', '_')}.html", 'w', encoding='utf-8') as f:
            f.write(html)
        
        # Log all text elements with expanded information
        print(f"\n-- DEBUG TEXT ELEMENTS FOR {tutor_name} --")
        all_elements = card.find_elements(By.XPATH, ".//*")
        for i, elem in enumerate(all_elements):
            try:
                text = elem.text.strip()
                if text:
                    tag_name = elem.tag_name
                    class_attr = elem.get_attribute('class') or ''
                    
                    # Special highlight for potential review elements
                    highlight = ""
                    if "review" in text.lower() or re.search(r'\d+\s+review', text.lower()):
                        highlight = " [POSSIBLE REVIEWS]"
                    elif "★" in text or "stars" in text.lower() or re.match(r'^\d+(\.\d+)?$', text):
                        highlight = " [POSSIBLE RATING]"
                    elif re.match(r'^[\$€£¥₽₴₹]\s*\d+|\d+\s*[\$€£¥₽₴₹]', text):
                        highlight = " [POSSIBLE PRICE]"
                        
                    print(f"Element {i}: <{tag_name} class='{class_attr}'> '{text}'{highlight}")
            except:
                pass
    except Exception as e:
        print(f"Error in debug_tutor_card: {e}")

def verify_url_pattern(driver):
    """
    Check if the site uses the standard ?page= pattern or a different one.
    Returns the URL pattern format to use.
    """
    try:
        # Try different URL patterns
        patterns = [
            "?page=2",
            "/page/2",
            "/2"
        ]
        
        original_url = driver.current_url
        
        for pattern in patterns:
            test_url = PREPLY_URL + pattern
            driver.get(test_url)
            time.sleep(3)
            
            # Check if we have tutor cards on this page
            tutor_cards = driver.find_elements(By.CSS_SELECTOR, "section[data-qa-group='tutor-profile']")
            if len(tutor_cards) > 0:
                # We found the correct pattern
                driver.get(original_url)  # Go back to original page
                base_pattern = pattern.replace("2", "{}")
                print(f"Verified URL pattern: {base_pattern}")
                return base_pattern
        
        # Default to standard pattern if none worked
        driver.get(original_url)
        return "?page={}"
    except Exception as e:
        print(f"Error verifying URL pattern: {e}")
        return "?page={}"

def get_total_pages(driver):
    """
    Dynamically detects the total number of pages available.
    """
    try:
        # Look for pagination elements using various selectors
        pagination_selectors = [
            "ul.Pager_container__wdRC6 li a",  # Original selector
            "ul[class*='Pager'] li a",         # More flexible
            "nav[aria-label='pagination'] li a",
            ".pagination a",
            "[class*='pagination'] a"
        ]
        
        for selector in pagination_selectors:
            try:
                page_links = driver.find_elements(By.CSS_SELECTOR, selector)
                if page_links:
                    # Extract page numbers from the links
                    page_numbers = []
                    for link in page_links:
                        try:
                            # Get number from text
                            text = link.text.strip()
                            if text.isdigit():
                                page_numbers.append(int(text))
                            # Also try to get number from URL
                            href = link.get_attribute("href")
                            if href and "page=" in href:
                                page_num = int(href.split("page=")[1].split("&")[0])
                                page_numbers.append(page_num)
                        except:
                            continue
                    
                    if page_numbers:
                        # Return the highest page number found
                        max_page = max(page_numbers)
                        print(f"Detected {max_page} total pages")
                        return max_page
            except:
                continue
        
        # Alternative method: Look for "Next" or last page button
        next_selectors = [
            "a[aria-label='next-page']",
            "a[aria-label='last-page']",
            "a[class*='next']",
            "a[class*='last']",
            "li.next a",
            "li.last a"
        ]
        
        for selector in next_selectors:
            try:
                last_page_link = driver.find_element(By.CSS_SELECTOR, selector)
                href = last_page_link.get_attribute("href")
                if href and "page=" in href:
                    page_num = int(href.split("page=")[1].split("&")[0])
                    print(f"Detected {page_num} total pages from next/last button")
                    return page_num
            except:
                continue
        
        # If no pagination is found but we have tutor cards, assume there might be more pages
        tutor_cards = driver.find_elements(By.CSS_SELECTOR, "section[data-qa-group='tutor-profile']")
        if len(tutor_cards) > 0:
            print("Found tutor cards but could not detect pagination, assuming 5 pages")
            return 5  # Safe default if we have results but can't find pagination
        else:
            print("No tutor cards found, assuming single page")
            return 1
        
    except Exception as e:
        print(f"Error detecting total pages: {e}")
        # Fallback to a safe default
        print("Falling back to default of 5 pages")
        return 5  # Safe fallback

def process_tutors_on_current_page(driver):
    """
    Scrapes tutor data from the currently loaded page with improved error handling.
    """
    try:
        # Wait for tutor cards to be present
        time.sleep(3)  # Give page a moment to fully render
        tutor_cards = driver.find_elements(By.CSS_SELECTOR, "section[data-qa-group='tutor-profile']")
        print(f"Found {len(tutor_cards)} tutor cards on current page")
        
        if len(tutor_cards) == 0:
            print("WARNING: No tutor cards found on this page")
            print("Current URL:", driver.current_url)
            return False
            
        all_success = True

        for i, card in enumerate(tutor_cards):
            try:
                print(f"Processing tutor {i+1}/{len(tutor_cards)}")
                
                # Scroll card into view with a smoother approach
                driver.execute_script("arguments[0].scrollIntoView({block: 'center', behavior: 'smooth'});", card)
                time.sleep(1)  # Let the page settle after scrolling

                # Extract tutor name with multiple selector attempts
                tutor_name = ""
                name_selectors = [
                    "a[data-clickable-element-name='name'] h4",
                    "h4",
                    "a h4",
                    "[data-qa-group='tutor-name']"
                ]
                
                for selector in name_selectors:
                    try:
                        name_elem = card.find_element(By.CSS_SELECTOR, selector)
                        tutor_name = name_elem.get_attribute("textContent").strip()
                        if tutor_name:
                            break
                    except:
                        continue
                
                if not tutor_name:
                    print("Could not find tutor name, skipping this tutor")
                    continue

                # Reviews extraction with improved handling to distinguish between star rating and review count
                num_reviews = 0
                try:
                    # First look specifically for elements containing the word "reviews"
                    reviews_selectors = [
                        "*[contains(text(), 'reviews')]",  # XPath selector for any element containing "reviews"
                        "span[class*='review'] span",
                        "[data-qa-group='reviews-count']",
                        "*[class*='reviews']"
                    ]
                    
                    for selector in reviews_selectors:
                        try:
                            if selector.startswith("*[contains"):
                                # This is an XPath selector
                                reviews_elements = card.find_elements(By.XPATH, f".//{selector}")
                            else:
                                # This is a CSS selector
                                reviews_elements = card.find_elements(By.CSS_SELECTOR, selector)
                                
                            for reviews_element in reviews_elements:
                                reviews_text = reviews_element.text.strip()
                                
                                # Look specifically for patterns like "27 reviews"
                                if "reviews" in reviews_text.lower():
                                    # Extract number before the word "reviews"
                                    match = re.search(r'(\d+)\s+reviews', reviews_text.lower())
                                    if match:
                                        num_reviews = int(match.group(1))
                                        break
                                    
                                    # Try another pattern - just extract any number
                                    numbers = re.findall(r'\d+', reviews_text)
                                    if numbers:
                                        num_reviews = int(numbers[0])
                                        break
                            
                            if num_reviews > 0:
                                break
                        except Exception as e:
                            print(f"Error with reviews selector {selector}: {e}")
                            continue
                    
                    # If we still haven't found reviews, try an alternative approach 
                    # based on looking near the star rating
                    if num_reviews == 0:
                        try:
                            # Look for star ratings first (usually nearby the reviews count)
                            star_selectors = [
                                "*[contains(text(), '★')]",  # XPath for star symbol
                                "*[class*='star']",
                                "*[class*='rating']"
                            ]
                            
                            for selector in star_selectors:
                                try:
                                    if selector.startswith("*[contains"):
                                        star_elements = card.find_elements(By.XPATH, f".//{selector}")
                                    else:
                                        star_elements = card.find_elements(By.CSS_SELECTOR, selector)
                                        
                                    if star_elements:
                                        # Found the star rating, now look for nearby elements with numbers that might be reviews
                                        for star_elem in star_elements:
                                            # Try to find parent container that might have both rating and reviews
                                            parent = star_elem.find_element(By.XPATH, "./..")
                                            # Look for elements with text containing digits
                                            number_elements = parent.find_elements(By.XPATH, ".//*[contains(text(), '0') or contains(text(), '1') or contains(text(), '2')]")
                                            
                                            for elem in number_elements:
                                                text = elem.text.strip()
                                                if "reviews" in text.lower():
                                                    match = re.search(r'(\d+)\s+reviews', text.lower())
                                                    if match:
                                                        num_reviews = int(match.group(1))
                                                        break
                                        break
                                except:
                                    continue
                        except:
                            pass
                            
                except Exception as e:
                    print(f"Error extracting reviews: {e}")
                    num_reviews = 0

                # If we still have zero reviews, try one more fallback approach
                if num_reviews == 0:
                    try:
                        # Based on your screenshot layout, reviews appear near ratings
                        # Try to find any text that looks like "27 reviews"
                        all_elements = card.find_elements(By.XPATH, ".//*")
                        for elem in all_elements:
                            try:
                                text = elem.text.strip()
                                match = re.search(r'(\d+)\s+reviews', text.lower())
                                if match:
                                    num_reviews = int(match.group(1))
                                    break
                            except:
                                continue
                    except:
                        pass

                print(f"Extracted reviews count: {num_reviews}")

                # Active Students and Lessons with improved selector flexibility
                active_students_num = 0
                lessons_number = 0
                
                try:
                    stats_selectors = [
                        "span.styles_StatsItem__s8Pzk p",
                        "span[class*='StatsItem'] p",
                        "[data-qa-group='stats'] p",
                        "*[class*='stats'] p"
                    ]
                    
                    for selector in stats_selectors:
                        try:
                            stats_elements = card.find_elements(By.CSS_SELECTOR, selector)
                            if len(stats_elements) >= 2:
                                # Extract active students
                                active_students_text = stats_elements[0].text.strip()
                                active_students_value = re.sub(r"[^\d]", "", active_students_text)
                                if active_students_value:
                                    active_students_num = int(active_students_value)
                                
                                # Extract lessons
                                lessons_text = stats_elements[1].text.strip()
                                lessons_value = re.sub(r"[^\d]", "", lessons_text)
                                if lessons_value:
                                    lessons_number = int(lessons_value)
                                
                                break
                        except:
                            continue
                except Exception as e:
                    print(f"Error extracting stats for {tutor_name}: {e}")
                
                # Extract price information
                price_value, price_currency = extract_price_from_card(card)
                print(f"Extracted price: {price_currency}{price_value}")
                
                # Debug the first few cards to help with troubleshooting
                if i < 3:  # Debug only the first 3 cards to avoid excessive output
                    debug_tutor_card(card, tutor_name)
                
                # Only proceed if we have at least some valid data
                if tutor_name and (active_students_num > 0 or lessons_number > 0):
                    print(f"Sending data for {tutor_name}: Reviews: {num_reviews}, Students: {active_students_num}, Lessons: {lessons_number}, Price: {price_currency}{price_value}")
                    success = append_tutor_record(tutor_name, num_reviews, active_students_num, lessons_number, price_value, price_currency)
                    if not success:
                        all_success = False
                else:
                    print(f"Skipping {tutor_name} due to insufficient data")

            except Exception as e:
                print(f"Error processing tutor card: {e}")
                all_success = False

        return all_success
    
    except Exception as e:
        print(f"Fatal error in process_tutors_on_current_page: {e}")
        return False

def wait_for_tutor_cards(driver, timeout=MAX_WAIT_TIME):
    """
    Wait for tutor cards to appear on the page with timeout.
    Returns True if cards found, False otherwise.
    """
    try:
        start_time = time.time()
        while time.time() - start_time < timeout:
            tutor_cards = driver.find_elements(By.CSS_SELECTOR, "section[data-qa-group='tutor-profile']")
            if len(tutor_cards) > 0:
                return True
            time.sleep(1)
        return False
    except:
        return False

def main():
    log_event("bot started", "in progress")

    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-popup-blocking")
    service = Service('/usr/bin/chromedriver')
    driver = webdriver.Chrome(service=service, options=options)

    all_success = True
    try:
        # Initial page load
        print(f"Loading initial page: {PREPLY_URL}")
        driver.get(PREPLY_URL)
        time.sleep(5)  # Initial load

        # Handle cookie consent if present
        try:
            consent_button = driver.find_element(By.CSS_SELECTOR, "button[data-testid='uc-accept-all-button']")
            consent_button.click()
            time.sleep(2)
        except:
            print("No cookie consent dialog found or already accepted")
            pass
        
        # Check if tutor cards loaded on first page
        if not wait_for_tutor_cards(driver):
            print("ERROR: Could not load tutor cards on first page. Exiting.")
            log_event("bot stopped", "failed - no tutor cards on first page")
            return
            
        # Verify the URL pattern for pagination
        url_pattern = verify_url_pattern(driver)
        print(f"Using URL pattern: {url_pattern}")
            
        # Dynamically detect the total number of pages
        total_pages = get_total_pages(driver)
        print(f"Will scrape {total_pages} pages in total")

        # Process page 1
        print("Processing page 1")
        page_success = process_tutors_on_current_page(driver)
        if not page_success:
            all_success = False

        # For pages 2 to total_pages, use direct URL navigation
        for page_num in range(2, total_pages + 1):
            try:
                # Construct the URL based on the detected pattern
                page_url = f"{PREPLY_URL}{url_pattern.format(page_num)}"
                print(f"Navigating directly to page {page_num} via URL: {page_url}")
                driver.get(page_url)
                
                # Wait for tutor cards to load with better waiting strategy
                print(f"Waiting for page {page_num} to load")
                if not wait_for_tutor_cards(driver):
                    print(f"WARNING: No tutor cards found on page {page_num} after waiting {MAX_WAIT_TIME} seconds")
                    
                    # Try to refresh once
                    print(f"Trying to refresh page {page_num}")
                    driver.refresh()
                    
                    if not wait_for_tutor_cards(driver, timeout=10):
                        print(f"STILL no tutor cards after refresh. Assuming we've reached the end of results.")
                        break  # Exit the pagination loop
                    
                # Verify we're on the right page
                current_url = driver.current_url
                if f"page={page_num}" not in current_url and f"/page/{page_num}" not in current_url and f"/{page_num}" not in current_url:
                    print(f"Warning: URL doesn't contain expected page number. Current URL: {current_url}")
                
                # Process tutors on current page
                print(f"Processing tutors on page {page_num}")
                page_success = process_tutors_on_current_page(driver)
                if not page_success:
                    all_success = False
                
            except Exception as e:
                print(f"Error navigating to or processing page {page_num}: {e}")
                all_success = False
                
                # Try to continue with next page instead of giving up
                continue

    except Exception as e:
        print(f"Fatal error in main: {e}")
        all_success = False
    
    finally:
        driver.quit()

    if all_success:
        log_event("bot stopped", "successful")
    else:
        log_event("bot stopped", "failed")

if __name__ == "__main__":
    main()
