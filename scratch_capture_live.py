from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
import os, time

options = Options()
options.add_argument('--headless=new')
options.add_argument('--window-size=1920,1080')
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')

driver = webdriver.Chrome(options=options)
driver.get('http://localhost:8501')
time.sleep(2)

sel = driver.find_element(By.TAG_NAME, 'select')
Select(sel).select_by_visible_text('robot-shop')

for inp in driver.find_elements(By.TAG_NAME, 'input'):
    t = inp.get_attribute('type')
    if t == 'text': inp.send_keys('admin')
    elif t == 'password': inp.send_keys('Admin@123456')

for b in driver.find_elements(By.TAG_NAME, 'button'):
    if 'Sign in' in b.text:
        b.click()
        break
time.sleep(3)

out_dir = r'C:\Users\arati.joshi\.gemini\antigravity-ide\brain\55c61af4-97e3-45e8-ab13-c03d60800693\live_pages'
os.makedirs(out_dir, exist_ok=True)

# Save overview
driver.save_screenshot(os.path.join(out_dir, '01_overview.png'))

# Find all clickable buttons and divs
buttons = driver.find_elements(By.TAG_NAME, 'button')
print(f"Total buttons: {len(buttons)}")

targets = ['Incidents', 'Approvals', 'Ask Kai', 'Closed Incidents', 'Platform Health']
for target in targets:
    # re-find buttons after navigation
    btns = driver.find_elements(By.TAG_NAME, 'button')
    clicked = False
    for b in btns:
        if target.lower() in b.text.lower():
            try:
                b.click()
                time.sleep(2)
                shot = os.path.join(out_dir, f"{target.replace(' ', '_').lower()}.png")
                driver.save_screenshot(shot)
                print(f"Clicked and saved {target} to {shot}")
                clicked = True
                break
            except Exception as e:
                print(f"Error clicking {target}: {e}")
    if not clicked:
        # Check links
        links = driver.find_elements(By.TAG_NAME, 'a')
        for a in links:
            if target.lower() in a.text.lower():
                try:
                    a.click()
                    time.sleep(2)
                    shot = os.path.join(out_dir, f"{target.replace(' ', '_').lower()}.png")
                    driver.save_screenshot(shot)
                    print(f"Clicked link and saved {target} to {shot}")
                    break
                except Exception as e:
                    print(f"Error clicking link {target}: {e}")

# Now let's click on one of the recent closures to view incident details
driver.get('http://localhost:8501')
time.sleep(2)
recent_cards = driver.find_elements(By.XPATH, "//*[contains(text(), 'incident')]")
print(f"Recent cards found: {len(recent_cards)}")
for card in recent_cards:
    try:
        card.click()
        time.sleep(2)
        driver.save_screenshot(os.path.join(out_dir, 'incident_detail.png'))
        print("Captured incident detail view!")
        break
    except:
        pass

driver.quit()
