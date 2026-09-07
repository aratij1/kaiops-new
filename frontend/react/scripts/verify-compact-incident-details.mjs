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
  await page.evaluate(() => { history.pushState({}, "", "/incidents/55705c30-a2b9-4d69-b0d6-9eb532c1a719"); window.dispatchEvent(new PopStateEvent("popstate")); });
  const heading=page.getByRole("heading",{name:"Evidence library",exact:true});
  try { await heading.waitFor({timeout:30000}); }
  catch { await page.getByRole("button",{name:"Retry",exact:true}).click(); await heading.waitFor({timeout:45000}); }
  const library=page.locator(".ic-evidence-browser");
  if(await library.getAttribute("open")!==null) throw new Error("Evidence should start collapsed");
  const before=await page.locator(".ic-primary").evaluate(n=>[...n.children].map(e=>e.className));
  if(before.findIndex(x=>x.includes("ic-resolution"))>before.findIndex(x=>x.includes("ic-investigation-records"))) throw new Error("Resolution buried below records");
  await page.screenshot({path:"../../docs/architecture/incident-details-compact-2026-09-07.png",fullPage:true});
  await library.locator("summary").click();
  const count=await library.locator("li").count();
  if(count>8) throw new Error("Evidence pagination failed");
  await library.locator("summary").click();
  await page.setViewportSize({width:980,height:1000});
  await page.screenshot({path:"../../docs/architecture/incident-details-compact-narrow-2026-09-07.png",fullPage:true});
  const overflow=await page.locator(".incident-command").evaluate(n=>n.scrollWidth>n.clientWidth+2);
  console.log(JSON.stringify({url:page.url(),collapsedInitially:true,recordsPerPage:count,resolutionBeforeLibrary:true,detailsOverflowAt980:overflow}));
} catch (error) {
  await page.screenshot({path:"../../docs/architecture/closed-inbox-browser-diagnostic.png",fullPage:true});
  console.log(JSON.stringify({url:page.url(),body:(await page.locator("body").innerText()).slice(-8000)}));
  throw error;
} finally { await browser.close(); }
