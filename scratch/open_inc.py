from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
import os, time

options = Options()
options.add_argument('--headless=new')
options.add_argument('--window-size=1920,1080')
driver = webdriver.Chrome(options=options)

driver.get('http://localhost:8501')
time.sleep(2)

inputs = driver.find_elements(By.TAG_NAME, 'input')
for inp in inputs:
    t = inp.get_attribute('type')
    auto = inp.get_attribute('autocomplete')
    if t == 'text' or auto == 'username':
        inp.clear()
        inp.send_keys('admin')
    elif t == 'password' or auto == 'current-password':
        inp.clear()
        inp.send_keys('Admin@123456')

for b in driver.find_elements(By.TAG_NAME, 'button'):
    if 'Sign in securely' in b.text or 'Sign in' in b.text:
        b.click()
        break
time.sleep(4)

# Click Incidents in sidebar
side_links = driver.find_elements(By.TAG_NAME, 'button')
for btn in side_links:
    if 'Incidents' in btn.text:
        btn.click()
        print('Clicked Incidents sidebar button')
        break
time.sleep(3)

# Click "Open incident" on the first card
open_btns = driver.find_elements(By.XPATH, "//*[contains(text(), 'Open incident')]")
print('Found open incident buttons:', len(open_btns))
if open_btns:
    open_btns[0].click()
    print('Clicked Open incident')
    time.sleep(5)
    out_dir = r'C:\Users\arati.joshi\.gemini\antigravity-ide\brain\624af5ee-c2c6-4078-8abc-bed691a9c1b6\live_pages'
    driver.save_screenshot(os.path.join(out_dir, '02b_open_incident_detail.png'))
    print('Current URL:', driver.current_url)

driver.quit()
