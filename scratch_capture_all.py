"""
Capture all key pages from the live KAIMS UI at localhost:8501
Handles React SPA session state and renders properly.
"""
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import os, time, sys

sys.stdout.reconfigure(encoding='utf-8')

options = Options()
options.add_argument('--headless=new')
options.add_argument('--window-size=1920,1080')
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')
options.add_argument('--disable-blink-features=AutomationControlled')

driver = webdriver.Chrome(options=options)
wait = WebDriverWait(driver, 15)

out_dir = r'C:\Users\arati.joshi\.gemini\antigravity-ide\brain\55c61af4-97e3-45e8-ab13-c03d60800693\live_pages2'
os.makedirs(out_dir, exist_ok=True)

def wait_for_content():
    """Wait until the page is not in a loading/restoring state."""
    time.sleep(1)
    for _ in range(15):
        text = driver.find_element(By.TAG_NAME, 'body').text
        if 'Restoring authenticated session' not in text and len(text) > 50:
            break
        time.sleep(1)
    time.sleep(2)

def login():
    driver.get('http://localhost:8501')
    time.sleep(4)
    inputs = driver.find_elements(By.TAG_NAME, 'input')
    for inp in inputs:
        t = inp.get_attribute('type')
        if t == 'text':
            inp.clear()
            inp.send_keys('admin')
        elif t == 'password':
            inp.clear()
            inp.send_keys('Admin@123456')
    sel_elems = driver.find_elements(By.TAG_NAME, 'select')
    if sel_elems:
        Select(sel_elems[0]).select_by_visible_text('robot-shop')
    for b in driver.find_elements(By.TAG_NAME, 'button'):
        if 'Sign in' in b.text:
            b.click()
            break
    # Wait for full dashboard to load
    time.sleep(6)
    wait_for_content()
    print(f"  Logged in. URL={driver.current_url}, Title={driver.title}")

def capture(path, name, extra_wait=0):
    driver.get(f'http://localhost:8501{path}')
    wait_for_content()
    if extra_wait:
        time.sleep(extra_wait)
    shot = os.path.join(out_dir, f'{name}.png')
    driver.save_screenshot(shot)
    size_kb = os.path.getsize(shot) // 1024
    body_preview = driver.find_element(By.TAG_NAME, 'body').text[:80].replace('\n', ' ')
    print(f"[{'OK' if size_kb > 20 else 'BLANK?'}] {name}.png ({size_kb}KB) | {driver.title} | {body_preview}")
    return shot

print("=== Logging in ===")
login()

print("\n=== Capturing pages ===")
pages = [
    ('/',                      'p01_overview',             0),
    ('/incidents',             'p02_incidents',            0),
    ('/approvals',             'p03_approvals',            0),
    ('/evidence-requests',     'p04_evidence_requests',    0),
    ('/copilot',               'p05_copilot',              0),
    ('/knowledge',             'p06_runbooks_knowledge',   0),
    ('/platform',              'p07_platform_health',      0),
    ('/cloud-ops/connections', 'p08_connections',          0),
    ('/cloud-ops/cockpit',     'p09_automation_readiness', 0),
    ('/audit',                 'p10_audit_log',            0),
    ('/closed-incidents',      'p11_closed_incidents',     0),
    ('/admin/settings',        'p12_settings',             0),
]

for path, name, xwait in pages:
    try:
        capture(path, name, xwait)
    except Exception as e:
        print(f"[ERROR] {path}: {e}")

# Try to capture an incident workspace
print("\n=== Incident Workspace ===")
try:
    driver.get('http://localhost:8501/incidents')
    wait_for_content()
    # Find any clickable incident row/link
    candidates = driver.find_elements(By.XPATH, "//button[contains(@class,'incident') or contains(@class,'row') or contains(@class,'card')] | //a[contains(@href,'incident')]")
    print(f"Found {len(candidates)} candidate elements")
    # Try clicking on a row with text indicating an incident
    all_btns = driver.find_elements(By.TAG_NAME, 'button')
    for btn in all_btns:
        txt = btn.text.strip()
        if any(kw in txt.lower() for kw in ['view details', 'view', 'open', 'incident']):
            btn.click()
            wait_for_content()
            driver.save_screenshot(os.path.join(out_dir, 'p13_incident_workspace.png'))
            print(f"[OK] Incident workspace captured, title={driver.title}")
            break
    else:
        # Fallback: click the first link in the incident table
        links = driver.find_elements(By.CSS_SELECTOR, 'table a, [data-testid] a, .incident-row a')
        if links:
            links[0].click()
            wait_for_content()
            driver.save_screenshot(os.path.join(out_dir, 'p13_incident_workspace.png'))
            print("[OK] Incident workspace captured via table link")
        else:
            print("[SKIP] No incident link found")
except Exception as e:
    print(f"[ERROR] incident workspace: {e}")

# Capture RCA / agent trace view
print("\n=== Agent Flow / Trace ===")
try:
    driver.get('http://localhost:8501/incidents')
    wait_for_content()
    # Look for a recently closed incident to navigate into its workspace
    closed_links = driver.find_elements(By.XPATH, "//a[contains(@href,'workspace') or contains(@href,'alert_id')]")
    if closed_links:
        closed_links[0].click()
        wait_for_content()
        driver.save_screenshot(os.path.join(out_dir, 'p14_rca_workspace.png'))
        print(f"[OK] RCA workspace, url={driver.current_url}")
except Exception as e:
    print(f"[ERROR] trace: {e}")

print("\n=== Summary ===")
for f in sorted(os.listdir(out_dir)):
    if f.endswith('.png'):
        sz = os.path.getsize(os.path.join(out_dir, f))
        print(f"  {f:40} {sz//1024}KB")

driver.quit()
print("\nAll done.")
