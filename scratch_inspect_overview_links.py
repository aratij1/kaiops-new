import sys
sys.stdout.reconfigure(encoding='utf-8')
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
import time

options = Options()
options.add_argument('--headless=new')
options.add_argument('--window-size=1920,1080')
driver = webdriver.Chrome(options=options)
driver.get('http://localhost:8501')
time.sleep(3)

for inp in driver.find_elements(By.TAG_NAME, 'input'):
    t = inp.get_attribute('type')
    if t == 'text': inp.send_keys('admin')
    elif t == 'password': inp.send_keys('Admin@123456')

for b in driver.find_elements(By.TAG_NAME, 'button'):
    if 'Sign in' in b.text: b.click(); break

time.sleep(6)

print("=== Links on Overview Page ===")
for a in driver.find_elements(By.TAG_NAME, 'a'):
    href = a.get_attribute('href')
    txt = a.text.strip().replace('\n', ' ')
    if href and txt:
        print(f"LINK: [{txt}] -> {href}")

# Click on one of the recent closures items
print("\n=== Trying to click on recent closures cards ===")
found_card = False
cards = driver.find_elements(By.XPATH, "//*[contains(text(), 'robot-shop-rabbitmq') or contains(text(), 'payments-api')]")
for c in cards:
    print(f"Found element: tag={c.tag_name}, text={c.text}")
    try:
        # Walk up to find clickable parent
        parent = c
        for _ in range(4):
            parent = parent.find_element(By.XPATH, "..")
            if parent.tag_name in ['a', 'button'] or parent.get_attribute('onclick'):
                print(f"Clicking parent tag: {parent.tag_name}")
                parent.click()
                found_card = True
                break
        if found_card:
            break
    except Exception as e:
        print("Click error:", e)

if not found_card:
    try:
        cards[0].click()
        found_card = True
    except Exception as e:
        print("Direct click error:", e)

time.sleep(5)
print("URL after click:", driver.current_url)
print("Page title:", driver.title)
driver.save_screenshot(r"C:\Users\arati.joshi\.gemini\antigravity-ide\brain\55c61af4-97e3-45e8-ab13-c03d60800693\incident_from_overview.png")

driver.quit()
