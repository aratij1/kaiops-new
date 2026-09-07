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
  await page.getByRole("button", {name:/Resolved recently/}).click({timeout:60000});
  await page.screenshot({path:"../../docs/architecture/closed-inbox-browser-diagnostic.png",fullPage:true});
  await page.locator(".status-closed").first().waitFor({timeout:60000});
  const before=feeds.length;
  const refreshed=page.waitForResponse(r=>r.url().includes("/incidents/inbox/feed") && r.ok(),{timeout:60000});
  await page.getByRole("button",{name:"Refresh queue",exact:true}).click();
  await refreshed;
  await page.screenshot({path:"../../docs/architecture/closed-incidents-visible-2026-09-07.png",fullPage:true});
  const result={url:page.url(),visibleClosed:await page.locator(".status-closed").count(),refreshFetchedFeed:feeds.length>before,feeds,selectors:await page.locator("select").evaluateAll(nodes=>nodes.map(n=>({label:n.getAttribute("aria-label"),value:n.value,options:[...n.options].map(o=>({value:o.value,text:o.text}))})))};
  writeFileSync("../../docs/architecture/closed-incidents-ui-verification-2026-09-07.json",JSON.stringify(result,null,2));
  await page.locator(".kai-shell select").first().selectOption("robot-shop-payment");
  await page.getByText("c10d39a5-cd6d-43e2-89ee-741cdbdcd778",{exact:true}).waitFor({timeout:30000});
  await page.locator(".status-closed").first().waitFor({timeout:30000});
  await page.screenshot({path:"../../docs/architecture/closed-robot-shop-visible-2026-09-07.png",fullPage:true});
  result.demoVerification={project:"robot-shop-payment",visibleClosed:await page.locator(".status-closed").count(),incidentId:"c10d39a5-cd6d-43e2-89ee-741cdbdcd778"};
  writeFileSync("../../docs/architecture/closed-incidents-ui-verification-2026-09-07.json",JSON.stringify(result,null,2));
  console.log(JSON.stringify({visibleClosed:result.visibleClosed,refreshFetchedFeed:result.refreshFetchedFeed,demoVerification:result.demoVerification}));
} catch (error) {
  await page.screenshot({path:"../../docs/architecture/closed-inbox-browser-diagnostic.png",fullPage:true});
  console.log(JSON.stringify({url:page.url(),body:(await page.locator("body").innerText()).slice(-8000)}));
  throw error;
} finally { await browser.close(); }
