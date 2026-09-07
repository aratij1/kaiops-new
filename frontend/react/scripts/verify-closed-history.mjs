import { chromium } from "@playwright/test";
import { execFileSync } from "node:child_process";
import { writeFileSync } from "node:fs";
const python = `import json,urllib.request
from common.config import get_settings
r=urllib.request.Request('http://localhost:8000/auth/login',data=json.dumps({'username':'admin','password':get_settings().admin_user_password}).encode(),headers={'Content-Type':'application/json'})
a=json.load(urllib.request.urlopen(r)); print(json.dumps({'accessToken':a['access_token'],'refreshToken':a.get('refresh_token',''),'username':'admin','password':get_settings().admin_user_password}))`;
const session = JSON.parse(execFileSync("docker", ["exec", "-i", "kaims-api-gateway-1", "python", "-"], { input: python, encoding: "utf8", windowsHide: true }));
const browser = await chromium.launch({headless:true});
const page = await browser.newPage({ viewport: { width: 1500, height: 1100 } });
try {

  const feeds = [];
  page.on("response", async (response) => { if(response.url().includes("/incidents/inbox/feed")) feeds.push({url:response.url(),status:response.status()}); });
  await page.goto("http://localhost:8501/incidents?inbox_view=resolved", {waitUntil:"domcontentloaded"});
  await page.locator('input[autocomplete="username"]').fill("admin");
  await page.locator('input[autocomplete="current-password"]').fill(session.password);
  await page.getByRole("button", {name:/sign in/i}).click();
  await page.locator(".kai-shell select").first().selectOption("KaiMS", {timeout:60000});
  await page.getByRole("button", {name:"Incidents",exact:true}).first().click({timeout:30000});
  await page.getByRole("link",{name:"Closed incident history",exact:true}).click();
  await page.getByRole("heading",{name:"Closed incident records",exact:true}).waitFor({timeout:30000});
  await page.locator(".resolution-history-workspace tbody tr .status-closed").first().waitFor({timeout:30000});
  const batch=JSON.parse((await import("node:fs")).readFileSync("../../docs/architecture/latest-50-recovery-batch-2026-09-07.json","utf8"));
  const ids=new Set(batch.incidents.map(row=>row.incident_id));
  const displayed=await page.locator(".resolution-history-workspace tbody tr").evaluateAll(rows=>rows.map(row=>({id:row.querySelector("code")?.textContent,status:row.querySelector("[class*=status-closed]")?.textContent})));
  const found=displayed.filter(row=>ids.has(row.id)&&row.status==="closed");
  if(found.length!==23) throw new Error(`Expected 23 batch closures, saw ${found.length}`);
  await page.screenshot({path:"../../docs/architecture/closed-history-visible-2026-09-07.png",fullPage:true});
  await page.getByRole("button",{name:"Incidents",exact:true}).first().click();
  await page.locator("td[data-label=Status]").first().waitFor({timeout:30000});
  const collapsed=await page.locator(".incident-blocker-details[open]").count();
  await page.setViewportSize({width:1100,height:1000});
  await page.screenshot({path:"../../docs/architecture/compact-inbox-visible-2026-09-07.png",fullPage:true});
  const overflow=await page.locator(".incident-table-wrap").evaluate(n=>n.scrollWidth>n.clientWidth+2);
  if(overflow) throw new Error("Inbox still overflows horizontally");
  const result={historyRows:displayed.length,batchClosuresVisible:found.length,blockersExpandedInitially:collapsed,inboxOverflowAt1100:overflow};
  writeFileSync("../../docs/architecture/closed-history-browser-verification-2026-09-07.json",JSON.stringify(result,null,2));
  console.log(JSON.stringify(result));
} catch (error) {
  await page.screenshot({path:"../../docs/architecture/closed-inbox-browser-diagnostic.png",fullPage:true});
  console.log(JSON.stringify({url:page.url(),body:(await page.locator("body").innerText()).slice(-8000)}));
  throw error;
} finally { await browser.close(); }
