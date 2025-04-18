from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import time
import logging
from datetime import datetime
import os
import traceback
import psutil

#######################################################
# Chrome Profile Path - Using existing Chrome profile
#######################################################
CHROME_USER_DATA_DIR = r"C:\Users\LENOVO\AppData\Local\Google\Chrome\User Data"
CHROME_PROFILE = "Profile 1"  # Use the correct profile name for K Dinesh
#######################################################

# Set up logging
log_directory = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
os.makedirs(log_directory, exist_ok=True)
log_filename = os.path.join(log_directory, f"kalvium_attendance_{datetime.now().strftime('%Y-%m-%d')}.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(log_filename),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def kill_chrome_processes():
    """Kill any running Chrome processes to avoid profile lock issues"""
    try:
        logger.info("Attempting to close any running Chrome instances...")
        # For Windows
        for proc in psutil.process_iter(['pid', 'name']):
            # Check if process name contains chrome
            if 'chrome' in proc.info['name'].lower():
                logger.info(f"Killing Chrome process with PID {proc.info['pid']}")
                try:
                    process = psutil.Process(proc.info['pid'])
                    process.terminate()
                except Exception as e:
                    logger.warning(f"Failed to kill process {proc.info['pid']}: {e}")
        
        # Give processes time to terminate
        time.sleep(2)
        logger.info("Chrome processes terminated.")
    except Exception as e:
        logger.error(f"Error while killing Chrome processes: {e}")

def main():
    driver = None
    try:
        logger.info("=========== STARTING KALVIUM ATTENDANCE SCRIPT ===========")
        
        # Kill any running Chrome instances first
        kill_chrome_processes()
        
        # Configure Chrome options for visible mode
        options = webdriver.ChromeOptions()
        
        # Add Chrome profile path to maintain login sessions
        logger.info(f"Using Chrome profile at: {CHROME_USER_DATA_DIR} - {CHROME_PROFILE}")
        options.add_argument(f"--user-data-dir={CHROME_USER_DATA_DIR}")
        options.add_argument(f"--profile-directory={CHROME_PROFILE}")
        
        # Fix for DevToolsActivePort error
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--remote-debugging-port=9222")
        
        # Auto-allow camera
        options.add_argument("--use-fake-ui-for-media-stream")
        options.add_experimental_option("excludeSwitches", ["enable-logging"])
        
        # Disable extensions that might cause issues
        options.add_argument("--disable-extensions")
        
        # Start Chrome with visible window
        logger.info("Starting Chrome browser...")
        try:
            # Try with ChromeDriverManager
            driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
        except Exception as e:
            logger.error(f"Error with ChromeDriverManager: {e}")
            logger.info("Trying with direct path to ChromeDriver...")
            
            # Try a direct approach with system ChromeDriver
            driver_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chromedriver.exe")
            if os.path.exists(driver_path):
                driver = webdriver.Chrome(service=Service(driver_path), options=options)
            else:
                raise Exception("ChromeDriver not found. Please download it manually and place in script directory.")
        
        driver.maximize_window()
        logger.info("Chrome browser started successfully in visible mode")
        
        # Navigate to Kalvium Community
        logger.info("Navigating to Kalvium Community...")
        driver.get("https://kalvium.community")
        
        # Wait for page to load
        WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        logger.info(f"Page loaded. Current URL: {driver.current_url}")
        
        # Take a screenshot of the main page
        screenshot_path = os.path.join(log_directory, f"main_page_{datetime.now().strftime('%H%M%S')}.png")
        driver.save_screenshot(screenshot_path)
        
        # Check if we need to log in (only if not already on the main page)
        if not check_if_logged_in(driver):
            logger.info("Not logged in. Looking for Google login button...")
            
            # Try to find and click "Continue with Google" button
            google_login_successful = find_and_click_google_button(driver)
            if not google_login_successful:
                logger.warning("Couldn't find Google login button, continuing anyway...")
            
            # Wait for login completion
            time.sleep(5)
        else:
            logger.info("Already logged in to Kalvium Community")
        
        # Handle "How was the session?" emoji feedback if it appears
        handle_session_feedback_improved(driver)
        
        # Check if already marked as present before attempting to mark attendance
        already_present = check_if_already_present(driver)
        if already_present:
            logger.info("✅ User is already marked as present for today!")
            logger.info("Closing the browser in 5 seconds...")
            time.sleep(5)
            return
        
        # Find and click Mark Attendance button (with retry)
        attendance_successful = False
        for attempt in range(3):  # Try up to 3 times
            logger.info(f"Attempt {attempt+1}/3 to find and click Mark Attendance button")
            attendance_successful = find_and_click_mark_attendance(driver)
            if attendance_successful:
                break
            else:
                logger.warning(f"Attempt {attempt+1} failed, waiting 2 seconds before retry")
                time.sleep(2)
                
        if not attendance_successful:
            logger.error("Failed to find and click Mark Attendance button after multiple attempts")
            return
        
        # Handle camera and click Present button - with improved speed
        present_successful = handle_camera_and_present_button_fast(driver)
        if not present_successful:
            logger.error("Failed to click I'm Present button")
            return
        
        # Verify success
        verify_success(driver)
        
        logger.info("Script completed successfully!")
        
    except Exception as e:
        logger.error(f"An error occurred: {str(e)}")
        logger.error(traceback.format_exc())
        try:
            if driver:
                screenshot_path = os.path.join(log_directory, f"error_{datetime.now().strftime('%H%M%S')}.png")
                driver.save_screenshot(screenshot_path)
                logger.info(f"Saved error screenshot to {screenshot_path}")
        except:
            logger.error("Failed to save error screenshot")
            
    finally:
        if driver:
            # Keep browser open for 5 seconds to see final state
            time.sleep(5)
            driver.quit()
            logger.info("Browser closed")

def handle_session_feedback_improved(driver):
    """Improved function to handle the session feedback with 3 emojis"""
    logger.info("Checking for session feedback prompt (improved)...")
    
    try:
        # Take screenshot before looking for feedback form
        screenshot_path = os.path.join(log_directory, f"before_feedback_{datetime.now().strftime('%H%M%S')}.png")
        driver.save_screenshot(screenshot_path)
        
        # Check if feedback form exists
        feedback_exists = driver.execute_script("""
            const feedbackTexts = [
                'how was the session',
                'how was your session',
                'rate the session',
                'feedback'
            ];
            
            // Look for feedback prompt
            const elements = document.querySelectorAll('*');
            for (const el of elements) {
                if (el.offsetHeight === 0 || el.offsetWidth === 0) continue;
                
                const text = (el.innerText || el.textContent || '').toLowerCase();
                for (const feedbackText of feedbackTexts) {
                    if (text.includes(feedbackText)) {
                        return "Feedback form found: " + text;
                    }
                }
            }
            
            return false;
        """)
        
        if not feedback_exists:
            logger.info("No session feedback form detected")
            return True
            
        logger.info(f"Detected session feedback: {feedback_exists}")
        
        # Try to select the third (last) emoji - the most positive one
        emoji_clicked = driver.execute_script("""
            // IMPROVED EMOJI DETECTION
            // -------------------------
            
            // Function to get element's absolute position
            function getAbsolutePosition(element) {
                const rect = element.getBoundingClientRect();
                return {
                    top: rect.top + window.scrollY,
                    left: rect.left + window.scrollX,
                    width: rect.width,
                    height: rect.height,
                    bottom: rect.bottom + window.scrollY,
                    right: rect.right + window.scrollX,
                    area: rect.width * rect.height
                };
            }
            
            // Step 1: Find all possible emoji candidates (small clickable items in a horizontal row)
            const allClickable = document.querySelectorAll('button, img, svg, [role="button"], div');
            const candidates = Array.from(allClickable).filter(el => {
                // Must be visible
                if (el.offsetHeight === 0 || el.offsetWidth === 0) return false;
                
                // Typical emoji size
                const rect = el.getBoundingClientRect();
                return rect.width >= 20 && rect.width <= 80 && rect.height >= 20 && rect.height <= 80;
            });
            
            console.log("Found " + candidates.length + " potential emoji candidates");
            
            // Step 2: Group candidates that appear to be in a horizontal row (similar y-position)
            const groups = [];
            candidates.forEach(candidate => {
                const pos = getAbsolutePosition(candidate);
                
                // Find a group with similar y-position
                let foundGroup = false;
                for (const group of groups) {
                    const firstItemPos = getAbsolutePosition(group[0]);
                    // If within ~10px vertically, consider it the same row
                    if (Math.abs(pos.top - firstItemPos.top) < 20) {
                        group.push(candidate);
                        foundGroup = true;
                        break;
                    }
                }
                
                if (!foundGroup) {
                    groups.push([candidate]);
                }
            });
            
            console.log("Found " + groups.length + " potential groups");
            
            // Step 3: Find groups with exactly 3 items or closest to it
            let bestGroup = null;
            let bestScore = 0;
            
            for (const group of groups) {
                // Score based on how close to 3 items and if they're in the upper half of page
                const pos = getAbsolutePosition(group[0]);
                const pageCenter = window.innerHeight / 2;
                const scoreForPosition = (pos.top < pageCenter) ? 3 : 1; // Prefer upper half
                const scoreForCount = (group.length === 3) ? 10 : (5 - Math.abs(group.length - 3));
                
                const totalScore = scoreForPosition * scoreForCount;
                
                if (totalScore > bestScore) {
                    bestScore = totalScore;
                    bestGroup = group;
                }
            }
            
            if (!bestGroup || bestGroup.length === 0) {
                console.log("Could not identify emoji group");
                return false;
            }
            
            console.log("Found best group with " + bestGroup.length + " items");
            
            // Sort the group horizontally (left to right)
            bestGroup.sort((a, b) => {
                const posA = getAbsolutePosition(a);
                const posB = getAbsolutePosition(b);
                return posA.left - posB.left;
            });
            
            // Click the last item (3rd one if 3 items, otherwise the last one for positive)
            const emojiToClick = bestGroup[bestGroup.length - 1]; // Last/rightmost emoji
            emojiToClick.click();
            
            return "Clicked the rightmost emoji in a group of " + bestGroup.length;
        """)
        
        if emoji_clicked:
            logger.info(f"Selected emoji: {emoji_clicked}")
            time.sleep(1)
        else:
            logger.warning("Failed to select emoji")
        
        # Now look for the Submit button
        submit_clicked = driver.execute_script("""
            // IMPROVED SUBMIT BUTTON DETECTION
            // --------------------------------
            
            // First try to find submit button by text
            const submitTexts = ['submit', 'ok', 'okay', 'done', 'confirm', 'next', 'save'];
            const buttons = document.querySelectorAll('button, [role="button"], input[type="submit"]');
            
            // Try matching by text first
            for (const button of buttons) {
                if (button.offsetHeight === 0 || button.offsetWidth === 0) continue;
                
                const text = (button.innerText || button.textContent || '').toLowerCase();
                for (const submitText of submitTexts) {
                    if (text.includes(submitText)) {
                        console.log("Found submit button by text:", text);
                        button.click();
                        return "Clicked button with text: " + text;
                    }
                }
            }
            
            // Try looking for buttons below the emojis
            let emojiBottom = 0;
            let feedbackContainer = null;
            
            // Find the feedback container
            document.querySelectorAll('div, section, form').forEach(container => {
                const text = (container.innerText || container.textContent || '').toLowerCase();
                if (text.includes('how was') || text.includes('feedback') || text.includes('rate')) {
                    feedbackContainer = container;
                }
            });
            
            if (feedbackContainer) {
                // Look for buttons inside the feedback container
                const containerButtons = Array.from(feedbackContainer.querySelectorAll('button'));
                
                // Sort by vertical position (top to bottom)
                containerButtons.sort((a, b) => {
                    const rectA = a.getBoundingClientRect();
                    const rectB = b.getBoundingClientRect();
                    return rectA.top - rectB.top;
                });
                
                // The submit button is likely the last button in the container
                if (containerButtons.length > 0) {
                    const lastButton = containerButtons[containerButtons.length - 1];
                    lastButton.click();
                    return "Clicked last button in feedback container";
                }
            }
            
            // Last resort: find the most prominent button on the page
            const visibleButtons = Array.from(buttons).filter(b => 
                b.offsetHeight > 0 && b.offsetWidth > 0 && 
                window.getComputedStyle(b).display !== 'none' && 
                window.getComputedStyle(b).visibility !== 'hidden'
            );
            
            // Sort by prominence (size, styling)
            visibleButtons.sort((a, b) => {
                const aStyle = window.getComputedStyle(a);
                const bStyle = window.getComputedStyle(b);
                
                // Score based on size, color, border, etc.
                const aScore = 
                    (a.offsetWidth * a.offsetHeight) +
                    (aStyle.backgroundColor !== 'rgba(0, 0, 0, 0)' ? 1000 : 0) +
                    (aStyle.borderWidth !== '0px' ? 500 : 0) +
                    (aStyle.fontWeight === 'bold' ? 300 : 0);
                    
                const bScore = 
                    (b.offsetWidth * b.offsetHeight) +
                    (bStyle.backgroundColor !== 'rgba(0, 0, 0, 0)' ? 1000 : 0) +
                    (bStyle.borderWidth !== '0px' ? 500 : 0) +
                    (bStyle.fontWeight === 'bold' ? 300 : 0);
                    
                return bScore - aScore; // Higher score first
            });
            
            if (visibleButtons.length > 0) {
                visibleButtons[0].click();
                return "Clicked most prominent button";
            }
            
            return false;
        """)
        
        if submit_clicked:
            logger.info(f"Clicked Submit button: {submit_clicked}")
            time.sleep(2)
            return True
        else:
            logger.warning("Failed to click Submit button, continuing anyway")
            return False
            
    except Exception as e:
        logger.error(f"Error handling session feedback: {e}")
        logger.error(traceback.format_exc())
        return False

def check_if_logged_in(driver):
    """Check if user is already logged in to Kalvium Community"""
    logger.info("Checking if already logged in...")
    
    try:
        # Take screenshot
        screenshot_path = os.path.join(log_directory, f"check_login_{datetime.now().strftime('%H%M%S')}.png")
        driver.save_screenshot(screenshot_path)
        
        # Look for elements that indicate logged in state
        logged_in = driver.execute_script("""
            // Check for user greeting or profile elements
            if (document.body.innerText.includes('Hi Dinesh')) {
                return "Found user greeting";
            }
            
            // Check for other dashboard elements
            if (document.querySelector('[class*="dashboard"], [class*="schedule"], [class*="calendar"]')) {
                return "Found dashboard elements";
            }
            
            // Check if login button is present (negative indicator)
            if (document.body.innerText.toLowerCase().includes('sign in') || 
                document.body.innerText.toLowerCase().includes('login') ||
                document.body.innerText.toLowerCase().includes('continue with google')) {
                return false;
            }
            
            // If we're on a page with "My Day" or other dashboard content
            if (document.body.innerText.includes('My Day') || 
                document.body.innerText.includes('Squad') ||
                document.body.innerText.includes('Announcements')) {
                return "Found dashboard content";
            }
            
            return false;
        """)
        
        if logged_in:
            logger.info(f"User is logged in: {logged_in}")
            return True
        else:
            logger.info("User is not logged in")
            return False
            
    except Exception as e:
        logger.error(f"Error checking if logged in: {e}")
        logger.error(traceback.format_exc())
        return False

def check_if_already_present(driver):
    """Check if user is already marked as present for today"""
    logger.info("Checking if user is already marked as present...")
    
    try:
        # Wait for Kalvium page to fully load
        time.sleep(3)
        
        # Take screenshot
        screenshot_path = os.path.join(log_directory, f"checking_present_{datetime.now().strftime('%H%M%S')}.png")
        driver.save_screenshot(screenshot_path)
        
        # Method 1: Direct check for present indicator
        try:
            present_indicator = driver.find_element(By.XPATH, 
                "//div[contains(text(), 'Present')] | " +
                "//span[contains(text(), 'Present')] | " +
                "//div[contains(text(), \"You're marked as present\")]")
            
            if present_indicator:
                logger.info(f"Found present indicator: {present_indicator.text}")
                return True
        except NoSuchElementException:
            logger.info("No present indicator found via direct method")
        
        # Method 2: Look for confirmation text
        try:
            confirmation_text = driver.find_element(By.XPATH, 
                "//*[contains(text(), 'Yay! You') and contains(text(), 'marked as present')]")
            
            if confirmation_text:
                logger.info(f"Found confirmation text: {confirmation_text.text}")
                return True
        except NoSuchElementException:
            logger.info("No confirmation text found")
        
        # Method 3: JavaScript check for presence-related elements
        already_present = driver.execute_script("""
            // Check for various indicators that user is already present
            const presentTexts = [
                'present', 
                'marked as present', 
                'already marked', 
                'stay focussed',
                'you\'re marked',
                'yay!'
            ];
            
            // Look through visible elements for present indicator texts
            const elements = document.querySelectorAll('*');
            for (const el of elements) {
                if (el.offsetHeight === 0 || el.offsetWidth === 0) continue; // Skip hidden elements
                
                const text = (el.innerText || el.textContent || '').toLowerCase();
                for (const presentText of presentTexts) {
                    if (text.includes(presentText)) {
                        return "Already present indicator found: " + text;
                    }
                }
            }
            
            return false;
        """)
        
        if already_present:
            logger.info(f"JavaScript found already present indicator: {already_present}")
            return True
        
        logger.info("User is not marked as present yet")
        return False
            
    except Exception as e:
        logger.error(f"Error checking if already present: {e}")
        logger.error(traceback.format_exc())
        return False

def find_and_click_google_button(driver):
    """Find and click the Continue with Google button"""
    logger.info("Looking for 'Continue with Google' button...")
    
    try:
        # Take a screenshot before looking for the Google button
        screenshot_path = os.path.join(log_directory, f"before_google_button_{datetime.now().strftime('%H%M%S')}.png")
        driver.save_screenshot(screenshot_path)
        
        # Try several different approaches to find the Google button
        
        # Approach 1: Direct link or button text
        try:
            google_button = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Google')]"))
            )
            google_button.click()
            logger.info("Clicked Google button using approach 1")
            time.sleep(2)
            return True
        except (TimeoutException, NoSuchElementException):
            logger.info("Approach 1 failed to find Google button")
        
        # Approach 2: Look for Google icon within a button
        try:
            google_button = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button img[alt*='Google'], button img[src*='google']"))
            )
            google_button.click()
            logger.info("Clicked Google button using approach 2")
            time.sleep(2)
            return True
        except (TimeoutException, NoSuchElementException):
            logger.info("Approach 2 failed to find Google button")
        
        # Approach 3: Using JavaScript to find and click any element related to Google login
        google_clicked = driver.execute_script("""
            // Try to find the Google button
            const buttons = Array.from(document.querySelectorAll('button, a, div[role="button"]'));
            
            // First look for buttons containing "Google" text
            for (const btn of buttons) {
                const text = (btn.innerText || btn.textContent || '').toLowerCase();
                if (text.includes('google')) {
                    console.log('Found Google button by text:', text);
                    btn.click();
                    return "Clicked Google button by text";
                }
            }
            
            // Then look for buttons with Google images
            for (const btn of buttons) {
                const images = btn.querySelectorAll('img');
                for (const img of images) {
                    const src = img.src || '';
                    const alt = img.alt || '';
                    if (src.includes('google') || alt.includes('google')) {
                        console.log('Found Google button by image');
                        btn.click();
                        return "Clicked Google button by image";
                    }
                }
            }
            
            // Look for any OAuth or SSO provider buttons
            for (const btn of buttons) {
                if (btn.className.includes('oauth') || 
                    btn.className.includes('provider') || 
                    btn.className.includes('social') ||
                    btn.id.includes('google') ||
                    btn.getAttribute('data-provider') === 'google') {
                    console.log('Found Google button by class/attribute');
                    btn.click();
                    return "Clicked Google button by class/attribute";
                }
            }
            
            return false;
        """)
        
        if google_clicked:
            logger.info(f"JavaScript approach succeeded: {google_clicked}")
            time.sleep(3)
            return True
        else:
            logger.warning("All approaches failed to find Google button")
            
        # Take another screenshot to see the page state
        screenshot_path = os.path.join(log_directory, f"after_google_button_search_{datetime.now().strftime('%H%M%S')}.png")
        driver.save_screenshot(screenshot_path)
        
        return False
            
    except Exception as e:
        logger.error(f"Error finding Google button: {e}")
        return False

def find_and_click_mark_attendance(driver):
    """Find and click the Mark Attendance button"""
    logger.info("Looking for 'Mark Attendance' button...")
    
    try:
        # Wait for Kalvium page to fully load
        WebDriverWait(driver, 30).until(
            lambda d: "kalvium" in d.current_url.lower()
        )
        logger.info(f"Current URL: {driver.current_url}")
        
        # Take screenshot of the main page
        screenshot_path = os.path.join(log_directory, f"main_page_{datetime.now().strftime('%H%M%S')}.png")
        driver.save_screenshot(screenshot_path)
        
        # Wait additional time for any JavaScript to load
        time.sleep(3)
        
        # Try direct approach first
        try:
            attendance_button = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, 
                    "//button[contains(text(), 'Attendance') or contains(text(), 'attendance')] | " +
                    "//a[contains(text(), 'Attendance') or contains(text(), 'attendance')] | " +
                    "//button[contains(text(), 'Mark') or contains(text(), 'mark')] | " +
                    "//a[contains(text(), 'Mark') or contains(text(), 'mark')]"
                ))
            )
            
            logger.info(f"Found attendance button: {attendance_button.text}")
            attendance_button.click()
            logger.info("Clicked attendance button")
            time.sleep(2)
            return True
        except (TimeoutException, NoSuchElementException) as e:
            logger.warning(f"Direct approach for finding attendance button failed: {e}")
        
        # JavaScript approach as fallback
        logger.info("Trying JavaScript approach for attendance button")
        attendance_clicked = driver.execute_script("""
            // Look for any element with attendance text
            const allElements = document.querySelectorAll('*');
            for (const elem of allElements) {
                const text = (elem.innerText || elem.textContent || '').toLowerCase();
                if (text.includes('attendance') || text.includes('mark attendance')) {
                    console.log('Found element with attendance text:', elem.tagName, text);
                    
                    // If it's directly clickable
                    if (elem.tagName === 'BUTTON' || elem.tagName === 'A' || 
                        elem.role === 'button' || elem.getAttribute('role') === 'button') {
                        elem.click();
                        return "Clicked direct element: " + elem.tagName + " - " + text;
                    }
                    
                    // Check parents for clickable elements
                    let parent = elem.parentElement;
                    let level = 0;
                    while (parent && level < 5) {
                        if (parent.tagName === 'BUTTON' || parent.tagName === 'A' || 
                            parent.onclick || parent.role === 'button' || 
                            parent.getAttribute('role') === 'button' ||
                            window.getComputedStyle(parent).cursor === 'pointer') {
                            parent.click();
                            return "Clicked parent: " + parent.tagName + " - level " + level;
                        }
                        parent = parent.parentElement;
                        level++;
                    }
                    
                    // Check children for clickable elements
                    const clickableChildren = elem.querySelectorAll('button, a, [role="button"]');
                    if (clickableChildren.length > 0) {
                        clickableChildren[0].click();
                        return "Clicked child: " + clickableChildren[0].tagName;
                    }
                    
                    // Force click as last resort
                    try {
                        elem.click();
                        return "Force-clicked: " + elem.tagName + " - " + text;
                    } catch (e) {
                        console.log("Failed to click:", e);
                    }
                }
            }
            
            // Last resort - look for prominent buttons
            const prominentButtons = Array.from(document.querySelectorAll('button')).filter(b => 
                b.offsetHeight > 0 && b.offsetWidth > 0 && (
                    b.className.includes('primary') || 
                    b.className.includes('action') ||
                    b.offsetWidth > 150 ||
                    b.style.fontSize > '16px'
                )
            );
            
            if (prominentButtons.length > 0) {
                prominentButtons[0].click();
                return "Clicked prominent button: " + (prominentButtons[0].innerText || prominentButtons[0].textContent);
            }
            
            return false;
        """)
        
        if attendance_clicked:
            logger.info(f"JavaScript found and clicked attendance button: {attendance_clicked}")
            time.sleep(2)
            return True
        else:
            logger.error("Could not find 'Mark Attendance' button")
            return False
            
    except Exception as e:
        logger.error(f"Error finding Mark Attendance button: {e}")
        logger.error(traceback.format_exc())
        return False

def handle_camera_and_present_button_fast(driver):
    """Handle camera activation and clicking the I'm Present button with improved speed"""
    logger.info("Waiting for camera to initialize (fast mode)...")
    
    try:
        # Reduced wait time for camera initialization
        time.sleep(5)
        
        # Take camera screen screenshot
        screenshot_path = os.path.join(log_directory, f"camera_screen_{datetime.now().strftime('%H%M%S')}.png")
        driver.save_screenshot(screenshot_path)
        
        # Aggressive JavaScript approach to immediately find and click the Present button
        present_clicked = driver.execute_script("""
            // Aggressive Present Button finder and clicker
            function findAndClickPresentButton() {
                // Direct button text search
                const buttons = document.querySelectorAll('button');
                for (const button of buttons) {
                    const text = (button.innerText || button.textContent || '').toLowerCase();
                    if (text.includes('present') || text.includes("i'm present") || 
                        text.includes('confirm') || text.includes('submit')) {
                        button.click();
                        return "Clicked button: " + text;
                    }
                }
                
                // Visible buttons
                const visibleButtons = Array.from(buttons).filter(b => 
                    b.offsetHeight > 0 && b.offsetWidth > 0 && 
                    window.getComputedStyle(b).display !== 'none' && 
                    window.getComputedStyle(b).visibility !== 'hidden'
                );
                
                // Primary/action buttons
                for (const button of visibleButtons) {
                    if (button.className.toLowerCase().includes('primary') || 
                        button.className.toLowerCase().includes('action') ||
                        button.className.toLowerCase().includes('submit') ||
                        button.className.toLowerCase().includes('confirm') ||
                        window.getComputedStyle(button).backgroundColor !== 'rgba(0, 0, 0, 0)') {
                        button.click();
                        return "Clicked primary style button: " + button.className;
                    }
                }
                
                // Last resort - click the largest visible button
                if (visibleButtons.length > 0) {
                    visibleButtons.sort((a, b) => 
                        (b.offsetWidth * b.offsetHeight) - (a.offsetWidth * a.offsetHeight)
                    );
                    visibleButtons[0].click();
                    return "Clicked largest button";
                }
                
                return false;
            }
            
            // Try immediately
            let result = findAndClickPresentButton();
            if (result) return result;
            
            // Set up repeated attempts to find and click the button
            let attempts = 0;
            const intervalId = setInterval(() => {
                attempts++;
                console.log("Attempt", attempts, "to find Present button");
                const result = findAndClickPresentButton();
                if (result || attempts >= 15) {
                    clearInterval(intervalId);
                    if (result) return result;
                }
            }, 500);
            
            // Return that we've set up the attempts
            return "Set up repeated attempts to find Present button";
        """)
        
        logger.info(f"Started aggressive Present button detection: {present_clicked}")
        
        # Wait for a short time to give the JavaScript time to work
        time.sleep(3)
        
        # Try conventional approach as backup
        try:
            present_button = WebDriverWait(driver, 3).until(
                EC.element_to_be_clickable((By.XPATH, 
                    "//button[contains(text(), 'Present') or contains(text(), 'present')] | " +
                    "//button[contains(text(), \"I'm\") and contains(text(), 'Present')] | " +
                    "//button[contains(text(), 'Confirm') or contains(text(), 'confirm')] | " +
                    "//button[contains(text(), 'Submit') or contains(text(), 'submit')]"
                ))
            )
            
            logger.info(f"Found Present button: {present_button.text}")
            present_button.click()
            logger.info("Clicked Present button")
            return True
        except (TimeoutException, NoSuchElementException) as e:
            logger.info(f"Conventional approach didn't find button: {e}")
            
        # Check if JavaScript approach was successful
        success_check = driver.execute_script("""
            // Check if we are now on a result/success page
            const successIndicators = [
                'success',
                'thank you',
                'marked as present',
                'attendance confirmed'
            ];
            
            const pageText = document.body.innerText.toLowerCase();
            for (const indicator of successIndicators) {
                if (pageText.includes(indicator)) {
                    return "Success page detected: " + indicator;
                }
            }
            
            // Try clicking the button again - one last attempt
            const buttons = document.querySelectorAll('button');
            for (const button of buttons) {
                const text = (button.innerText || button.textContent || '').toLowerCase();
                if (text.includes('present') || text.includes("i'm present") || 
                    text.includes('confirm') || text.includes('submit')) {
                    button.click();
                    return "Clicked button in final attempt: " + text;
                }
            }
            
            return false;
        """)
        
        if success_check:
            logger.info(f"Button clicking appears successful: {success_check}")
            return True
        else:
            logger.warning("Could not verify if Present button was clicked")
            return False
            
    except Exception as e:
        logger.error(f"Error handling Present button: {e}")
        logger.error(traceback.format_exc())
        return False

def verify_success(driver):
    """Verify if attendance was successfully marked"""
    logger.info("Verifying success...")
    
    try:
        # Take final screenshot
        screenshot_path = os.path.join(log_directory, f"final_screen_{datetime.now().strftime('%H%M%S')}.png")
        driver.save_screenshot(screenshot_path)
        
        # Check for success indicators
        success_found = driver.execute_script("""
            const successTexts = ['success', 'present', 'marked', 'attendance', 'thank', 'confirmed', 'yay'];
            const elements = document.querySelectorAll('*');
            
            for (const el of elements) {
                if (el.offsetHeight === 0 || el.offsetWidth === 0) continue; // Skip hidden elements
                
                const text = (el.innerText || el.textContent || '').toLowerCase();
                for (const successText of successTexts) {
                    if (text.includes(successText)) {
                        return "Success indicator found: " + text;
                    }
                }
            }
            
            return false;
        """)
        
        if success_found:
            logger.info(f"✅ Success verification: {success_found}")
            logger.info("✅ Attendance successfully marked!")
            return True
        else:
            logger.warning("⚠️ No explicit success confirmation found")
            logger.info("Process completed but could not verify success - please check screenshots")
            return False
            
    except Exception as e:
        logger.error(f"Error during success verification: {e}")
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    main()
