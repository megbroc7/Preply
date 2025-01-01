import time
import datetime
import requests
import re
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service

# CONFIGURATION
AIRTABLE_API_KEY = "patBBWNeRi3YNmuHa.23c60bd16fa64948f0c5e65c2527cbf4e0eda930125ab379eb0713f473f4b68c"
BASE_ID = "appgOV8Yi4lS0DI05"
TUTOR_TABLE_NAME = "Tutor Data"
EVENT_LOG_TABLE_NAME = "Event Log"
PREPLY_URL = "https://preply.com/en/online/businessandmanagement-tutors"
MAX_RETRIES = 3
TOTAL_PAGES = 11  # Adjust if the number of pages changes

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

def append_tutor_record(tutor_name, num_reviews, active_students, num_lessons):
    """
    Append a new record to the Tutor Data table in Airtable without price.
    """
    url = f"https://api.airtable.com/v0/{BASE_ID}/{TUTOR_TABLE_NAME}"
    headers = {
        "Authorization": f"Bearer {AIRTABLE_API_KEY}",
        "Content-Type": "application/json"
    }
    date_of_entry = datetime.datetime.now(datetime.timezone.utc).isoformat()
    data = {
        "records": [
            {
                "fields": {
                    "Tutor Name": tutor_name,
                    "Number of Reviews": num_reviews,
                    "Active Students": active_students,
                    "Number of Lessons": num_lessons,
                    "Date of Entry": date_of_entry
                }
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

def process_tutors_on_current_page(driver):
    """
    Scrapes tutor data from the currently loaded page.
    """
    tutor_cards = driver.find_elements(By.CSS_SELECTOR, "section[data-qa-group='tutor-profile']")
    all_success = True

    for card in tutor_cards:
        try:
            # Scroll card into view
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", card)
            time.sleep(1)

            # Tutor Name
            try:
                name_elem = card.find_element(By.CSS_SELECTOR, "a[data-clickable-element-name='name'] h4")
            except:
                print("Name element not found. Card HTML:", card.get_attribute('outerHTML'))
                print("Skipping this tutor.")
                continue

            tutor_name = name_elem.get_attribute("textContent").strip()
            if tutor_name == "":
                print("Tutor name is empty. Card HTML:", card.get_attribute('outerHTML'))
                continue

            # Reviews
            num_reviews = 0
            try:
                reviews_button = card.find_element(By.CSS_SELECTOR, "button[data-clickable-element-name='reviews']")
                reviews_text = reviews_button.text.strip()
                lines = reviews_text.split('\n')
                for line in lines:
                    if "reviews" in line.lower():
                        parts = line.split()
                        num_reviews = int(parts[0])
                        break
            except:
                num_reviews = 0

            # Active Students and Lessons
            try:
                stats_elements = card.find_elements(By.CSS_SELECTOR, "span.styles_StatsItem__s8Pzk p")
                if len(stats_elements) < 2:
                    print(f"Not enough stats for tutor {tutor_name}, skipping.")
                    continue

                active_students_text = stats_elements[0].text.strip()
                active_students_value = re.sub(r"[^\d]", "", active_students_text)  # remove commas or non-digits
                if active_students_value == "":
                    print(f"Cannot parse active students for {tutor_name} from '{active_students_text}'")
                    continue
                active_students_num = int(active_students_value)

                lessons_text = stats_elements[1].text.strip()
                lessons_value = re.sub(r"[^\d]", "", lessons_text)  # remove commas or non-digits
                if lessons_value == "":
                    print(f"Cannot parse lessons for {tutor_name} from '{lessons_text}'")
                    continue
                lessons_number = int(lessons_value)

            except Exception as e:
                print(f"Error extracting stats for {tutor_name}: {e}")
                continue

            success = append_tutor_record(tutor_name, num_reviews, active_students_num, lessons_number)
            if not success:
                all_success = False

        except Exception as e:
            print(f"Error processing tutor: {e}")
            all_success = False

    return all_success

def main():
    log_event("bot started", "in progress")

    options = Options()
    options.add_argument("--headless")
    service = Service('/usr/bin/chromedriver')
    driver = webdriver.Chrome(service=service, options=options)

    all_success = True
    try:
        driver.get(PREPLY_URL)
        time.sleep(5)  # Initial load of page 1

        # Handle cookie consent if present:
        try:
            consent_button = driver.find_element(By.CSS_SELECTOR, "button[data-testid='uc-accept-all-button']")
            consent_button.click()
            time.sleep(2)  # Wait for overlay to disappear
        except:
            pass  # If not found, no overlay to close

        # Process page 1
        page_success = process_tutors_on_current_page(driver)
        if not page_success:
            all_success = False

        # Now navigate through pages 2 to TOTAL_PAGES
        for page_num in range(2, TOTAL_PAGES + 1):
            try:
                # Scroll pagination into view
                pagination_container = driver.find_element(By.CSS_SELECTOR, "ul.Pager_container__wdRC6")
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", pagination_container)
                time.sleep(1)

                # Find and click the page link via JS to avoid interception
                page_link = driver.find_element(By.CSS_SELECTOR, f"a[aria-label='page-{page_num}']")
                driver.execute_script("arguments[0].click();", page_link)
                time.sleep(5)  # Wait for new page to load

                page_success = process_tutors_on_current_page(driver)
                if not page_success:
                    all_success = False
            except Exception as e:
                print(f"Error navigating to or processing page {page_num}: {e}")
                all_success = False
                break

    finally:
        driver.quit()

    if all_success:
        log_event("bot stopped", "successful")
    else:
        log_event("bot stopped", "failed")

if __name__ == "__main__":
    main()
