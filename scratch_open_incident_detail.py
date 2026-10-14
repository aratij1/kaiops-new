from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
import os, time, sys

sys.stdout.reconfigure(encoding='utf-8')

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

time.sleep(5)

# Click Incidents sidebar
for b in driver.find_elements(By.TAG_NAME, 'button'):
    if 'Incidents' in b.text:
        b.click()
        print('Clicked Incidents button')
        break

time.sleep(5)

# Look for 'Open incident' buttons
open_btns = driver.find_elements(By.XPATH, "//*[contains(text(), 'Open incident')]")
print('Open incident buttons count:', len(open_btns))
if open_btns:
    driver.execute_script('arguments[0].scrollIntoView(true);', open_btns[0])
    time.sleep(1)
    open_btns[0].click()
    print('Clicked Open incident button!')
    time.sleep(6)
    out = r'C:\Users\arati.joshi\.gemini\antigravity-ide\brain\55c61af4-97e3-45e8-ab13-c03d60800693\live_incident_opened.png'
    driver.save_screenshot(out)
    print('Saved live_incident_opened.png. Current URL:', driver.current_url)
    print('Body text preview:\n', driver.find_element(By.TAG_NAME, 'body').text[:1200])
else:
    print('No open incident buttons found')

driver.quit()
