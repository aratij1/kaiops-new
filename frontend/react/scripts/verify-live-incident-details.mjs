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
  const row=page.locator("tr").filter({has:page.getByRole("button",{name:"View details",exact:true})}).first();
  const rowText=await row.innerText();
  await row.getByRole("button",{name:"View details",exact:true}).click();
  await page.locator(".incident-command").waitFor({timeout:30000});
  await page.screenshot({path:"../../docs/architecture/incident-details-current-2026-09-07.png",fullPage:true});
  const result={url:page.url(),rowText,heading:await page.locator(".ic-command-header").innerText(),body:(await page.locator("main").last().innerText()).slice(0,8000)};
  writeFileSync("../../docs/architecture/incident-details-navigation-2026-09-07.json",JSON.stringify(result,null,2));
  console.log(JSON.stringify(result));
} catch (error) {
  await page.screenshot({path:"../../docs/architecture/closed-inbox-browser-diagnostic.png",fullPage:true});
  console.log(JSON.stringify({url:page.url(),body:(await page.locator("body").innerText()).slice(-8000)}));
  throw error;
} finally { await browser.close(); }
