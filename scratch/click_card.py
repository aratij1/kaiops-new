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
time.sleep(5)

# On overview, find rs-rabbitmq card and click it
cards = driver.find_elements(By.XPATH, "//*[contains(text(), 'rs-rabbitmq')]")
print('rs-rabbitmq elements found:', len(cards))
for c in cards:
    try:
        # Find clickable ancestor or the element itself
        c.click()
        print('Clicked rs-rabbitmq element!')
        break
    except Exception as e:
        print('Could not click directly, trying parent:', e)

time.sleep(6)
out_dir = r'C:\Users\arati.joshi\.gemini\antigravity-ide\brain\624af5ee-c2c6-4078-8abc-bed691a9c1b6\live_pages'
driver.save_screenshot(os.path.join(out_dir, '03_rs_rabbitmq_clicked.png'))
print('Saved 03_rs_rabbitmq_clicked.png at URL:', driver.current_url)

driver.quit()
