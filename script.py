from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import time
import logging
from datetime import datetime

# Set up logging to file and console
log_filename = f"kalvium_attendance_{datetime.now().strftime('%Y-%m-%d')}.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(log_filename),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Set paths
chrome_driver_path = r"C:/WebDrivers/chromedriver.exe"
user_data_dir = r"C:\Users\LENOVO\AppData\Local\Google\Chrome\User Data\Default"
profile_dir = "Default"

# Configure Chrome options
options = webdriver.ChromeOptions()
options.add_argument(f"--user-data-dir={user_data_dir}")
options.add_argument(f"--profile-directory={profile_dir}")

# Add headless mode options
options.add_argument("--headless=new")  # Use the new headless mode
options.add_argument("--window-size=1920,1080")  # Set window size
options.add_argument("--start-maximized")

# Disable GPU acceleration and other features that might cause issues
options.add_argument("--disable-gpu")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--no-sandbox")
options.add_experimental_option("excludeSwitches", ["enable-logging"])
options.add_argument("--use-fake-ui-for-media-stream")  # Auto-allow camera access
options.add_argument("--use-fake-device-for-media-stream")  # Use fake camera for headless mode

# Start Chrome
try:
    service = Service(chrome_driver_path)
    driver = webdriver.Chrome(service=service, options=options)
    logger.info("Chrome browser started successfully in headless mode")
except Exception as e:
    logger.error(f"Failed to start Chrome browser: {e}")
    exit(1)

def click_button_with_retry(driver, selectors, max_retries=3, description="button", wait_time=10):
    """Try to click a button using multiple selectors with retries"""
    wait = WebDriverWait(driver, wait_time)
    
    for attempt in range(max_retries):
        for selector in selectors:
            try:
                logger.info(f"Attempt {attempt+1}: Looking for {description} with selector: {selector}")
                button = wait.until(EC.element_to_be_clickable((By.XPATH, selector)))
                logger.info(f"Found {description}!")
                
                # Try JavaScript click first
                try:
                    driver.execute_script("arguments[0].click();", button)
                    logger.info(f"Clicked {description} using JavaScript")
                    time.sleep(2)  # Short wait after click
                    return True
                except Exception:
                    # Fall back to regular click
                    button.click()
                    logger.info(f"Clicked {description} using regular click")
                    time.sleep(2)  # Short wait after click
                    return True
                    
            except Exception as e:
                logger.info(f"Couldn't click with selector {selector}: {e}")
                continue
        
        # If we've tried all selectors and none worked, wait a bit before retry
        if attempt < max_retries - 1:
            logger.info(f"All selectors failed. Waiting before retry {attempt+2}...")
            time.sleep(3)
    
    logger.error(f"Failed to click {description} after {max_retries} attempts")
    return False

try:
    # Navigate to Kalvium Community
    driver.get("https://kalvium.community")
    logger.info("Navigating to Kalvium Community...")
    time.sleep(5)  # Allow page to load fully
    
    # Take a screenshot before checking for login
    driver.save_screenshot("initial_load.png")
    logger.info("Saved initial page screenshot")
    
    # Always check for login button, regardless of URL
    logger.info("Checking for login button...")
    google_button_selectors = [
        "//button[contains(text(), 'Continue with Google')]",
        "//button[contains(., 'Google')]",
        "//div[contains(@class, 'login')]//button[contains(., 'Google')]",
        "//button[contains(@class, 'google')]",
        "//button[.//span[contains(text(), 'Google')]]"
    ]
    
    # Try to find login button with short wait time
    google_button_found = click_button_with_retry(
        driver, 
        google_button_selectors, 
        max_retries=2, 
        description="Continue with Google button",
        wait_time=5  # Short wait to check if button exists
    )
    
    if google_button_found:
        logger.info("Login button found and clicked. Waiting for login to complete...")
        # Wait for login redirection to complete
        time.sleep(10)  # Longer wait for login completion
        driver.save_screenshot("after_login.png")
        logger.info("Saved post-login screenshot")
        
        # Check if we're still on a login page
        if "login" in driver.current_url or "sign-in" in driver.current_url or "accounts.google" in driver.current_url:
            logger.info("Still on login page, might need to complete additional steps")
            # Let's log the current URL to help with debugging
            logger.info(f"Current URL: {driver.current_url}")
    
    # Wait extra time to ensure page is fully loaded
    logger.info("Waiting for main page to load completely...")
    time.sleep(8)
    
    # Log current page data for debugging
    logger.info(f"Current URL: {driver.current_url}")
    logger.info(f"Page title: {driver.title}")
    driver.save_screenshot("main_page.png")
    logger.info("Saved main page screenshot")
    
    # More specific selectors for Mark Attendance button
    mark_attendance_selectors = [
        "//button[contains(text(), 'Mark Attendance')]",
        "//button[text()='Mark Attendance']",
        "//button[contains(., 'Attendance')]",
        "//button[contains(@class, 'attendance')]",
        "//*[contains(text(), 'Mark Attendance')]",
        "//div[contains(@class, 'container')]//button[contains(., 'Attendance')]",
        "//main//button[contains(., 'Attendance')]"
    ]
    
    logger.info("Looking for 'Mark Attendance' button...")
    mark_attendance_clicked = click_button_with_retry(
        driver, mark_attendance_selectors, max_retries=5, description="Mark Attendance button", wait_time=15
    )
    
    if not mark_attendance_clicked:
        # Try examining the page more closely
        try:
            screenshot_path = "kalvium_screen_no_attendance_button.png"
            driver.save_screenshot(screenshot_path)
            logger.info(f"Saved screenshot to {screenshot_path}")
            
            # Examine the page structure more thoroughly
            page_source = driver.page_source.lower()
            attendance_related_terms = ["attendance", "mark", "present", "class", "session"]
            found_terms = [term for term in attendance_related_terms if term in page_source]
            
            if found_terms:
                logger.info(f"Page contains attendance-related terms: {found_terms}")
                # Try one more time with a different strategy - look for any button that might be relevant
                buttons = driver.find_elements(By.TAG_NAME, "button")
                logger.info(f"Found {len(buttons)} buttons on the page")
                
                for i, button in enumerate(buttons):
                    try:
                        button_text = button.text.lower()
                        logger.info(f"Button {i} text: {button_text}")
                        if any(term in button_text for term in attendance_related_terms):
                            logger.info(f"Found button with text: {button_text}")
                            driver.execute_script("arguments[0].click();", button)
                            logger.info("Clicked button that might be for attendance")
                            mark_attendance_clicked = True
                            break
                    except Exception as e:
                        logger.error(f"Error processing button {i}: {e}")
                        continue
            else:
                logger.info("Page may not contain attendance functionality")
                
            # Log all buttons on page for debugging
            all_buttons = driver.find_elements(By.TAG_NAME, "button")
            logger.info("List of all buttons on page:")
            for i, btn in enumerate(all_buttons):
                try:
                    logger.info(f"Button {i}: Text='{btn.text}', Class='{btn.get_attribute('class')}'")
                except:
                    logger.info(f"Button {i}: [Failed to read properties]")
                    
        except Exception as e:
            logger.error(f"Error examining page: {e}")
    
    if mark_attendance_clicked:
        # Extended wait time for camera initialization in headless mode
        logger.info("Waiting for camera to initialize (20 seconds)...")
        time.sleep(20)
        driver.save_screenshot("camera_screen.png")
        logger.info("Saved camera screen screenshot")
        
        # More comprehensive selectors for "I'm Present" button
        present_selectors = [
            "//button[contains(text(), 'Mark as Present')]",
            "//button[contains(text(), 'I\'m Present')]",
            "//button[contains(text(), 'Present')]",
            "//button[text()='Present']",
            "//button[contains(@class, 'present')]",
            "//*[contains(text(), 'Present')][ancestor::button]",
            "//div[contains(@class, 'camera')]//button",
            "//button[contains(@class, 'primary')]"
        ]
        
        logger.info("Looking for 'I'm Present' button...")
        present_clicked = click_button_with_retry(
            driver, present_selectors, max_retries=8, description="I'm Present button", wait_time=15
        )
        
        if present_clicked:
            logger.info("Attendance marked successfully! Waiting to verify...")
            time.sleep(5)
            driver.save_screenshot("attendance_marked.png")
            logger.info("Saved attendance confirmation screenshot")
            
            # Better verification of success
            success_indicators = [
                "//div[contains(text(), 'Yay')]",
                "//div[contains(text(), 'success')]",
                "//div[contains(text(), 'marked')]",
                "//div[contains(text(), 'present')]",
                "//div[contains(text(), 'focussed')]",
                "//div[contains(text(), 'going')]"
            ]
            
            success_found = False
            for indicator in success_indicators:
                try:
                    element = driver.find_element(By.XPATH, indicator)
                    logger.info(f"Success verification found: {element.text}")
                    success_found = True
                    break
                except:
                    continue
            
            if not success_found:
                logger.info("Could not verify success message, but attendance may still be marked")
        else:
            logger.error("Could not click 'I'm Present' button")
            driver.save_screenshot("present_button_not_found.png")
    
    # Wait a bit to ensure all actions are completed
    time.sleep(5)
    logger.info("Script completed successfully")

except Exception as e:
    logger.error(f"An error occurred: {e}")
    try:
        # Take screenshot on error
        driver.save_screenshot("kalvium_error.png")
        logger.info(f"Saved error screenshot to kalvium_error.png")
    except:
        pass

finally:
    logger.info("Closing the browser")
    driver.quit()
